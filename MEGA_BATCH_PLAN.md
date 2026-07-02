# 🚀 Implementation Plan: GPU Mega-Batch Kernel
## Target: 2M–10M trials/day (RTX 3070) — from current ~80K–200K

---

## ปัญหาหลักที่ยังเหลืออยู่

ตอนนี้หลังแก้ไข Critical/High แล้ว โค้ดยังทำงานแบบนี้:

```
[ปัจจุบัน] — 1 genome ต่อ Optuna trial
  Optuna.ask(1 genome)
    └── 20 symbols × 4 horizons = 80 ครั้ง kernel launch
          └── แต่ละครั้ง: 1 active thread / 2560 CUDA cores
                → ใช้ GPU แค่ ~2.5%
```

```
[เป้าหมาย Mega-batch] — 256 genomes ต่อ batch
  Optuna.ask(256 genomes)
    └── 1 kernel launch เดียว: 256g × 20s × 4h = 20,480 threads พร้อมกัน
          → GPU ใช้งาน ~50-70% ✅
```

---

## 4 ส่วนที่ต้องสร้าง

### ส่วนที่ 1 — CUDA Kernel ใหม่ `_mega_backtest_kernel`

แทนที่ kernel เดิม (thread = 1 genome) ด้วย 3D indexing:

```python
# เดิม:  thread_idx → genome_idx (1 thread per genome)
# ใหม่:  thread_idx → (genome_idx, sym_idx, horizon_idx)

@cuda.jit
def _mega_backtest_kernel(
    price_data_flat,   # [total_bars_all_symbols, N_FEATURES=23]
    sym_offsets,       # [n_symbols] — start bar index per symbol
    sym_lengths,       # [n_symbols] — bar count per symbol
    horizon_bars,      # [4] = [1440, 4320, 8640, 17520]
    genome_params,     # [n_genomes, N_GENOME_PARAMS=29]
    out_results,       # [n_genomes × n_symbols × n_horizons × 4]
    n_genomes, n_symbols, n_horizons
):
    tid = cuda.grid(1)
    if tid >= n_genomes * n_symbols * n_horizons:
        return

    genome_idx  = tid // (n_symbols * n_horizons)
    sym_idx     = (tid // n_horizons) % n_symbols
    horizon_idx = tid % n_horizons

    bars   = horizon_bars[horizon_idx]
    offset = sym_offsets[sym_idx]
    length = sym_lengths[sym_idx]
    if length < bars:
        return

    # ... backtest loop using price_data_flat[offset + length - bars : offset + length] ...
    # ... read genome_params[genome_idx] for this thread's parameters ...

    base = (genome_idx * n_symbols * n_horizons + sym_idx * n_horizons + horizon_idx) * 4
    out_results[base + 0] = net_profit
    out_results[base + 1] = win_rate
    out_results[base + 2] = max_dd
    out_results[base + 3] = float32(trades)
```

**Launch config สำหรับ RTX 3070:**
```
total_threads = 256 genomes × 20 symbols × 4 horizons = 20,480
blocks = 20480 / 256 = 80 blocks
RTX 3070: 80 blocks / 20 SMs = 4 blocks/SM → ~50-70% occupancy ✅
```

---

### ส่วนที่ 2 — Data Packing `_pack_symbols_to_flat_gpu()`

จัดข้อมูลทั้ง 20 เหรียญเป็น flat array เดียวใน VRAM (ทำครั้งเดียวตอน startup):

```python
N_FEATURES = 23
FEATURE_ORDER = ["close","high","low","open","vol","sma200","sma50","atr","rsi","adx",
                 "vol_sma","bb_up","ema10","ema50","st_dir","mfi","stoch_k","cci",
                 "williams","keltner_low","tenkan","kijun","donchian_high"]

_GPU_FLAT_DATA = {}  # เก็บ device arrays ที่ pack แล้ว

def _pack_symbols_to_flat_gpu(symbol_arrays):
    """
    VRAM layout: [total_bars_all_syms, 23 features] — ONE contiguous array
    Memory: 20 sym × 17,520 bars × 23 × 4 bytes ≈ 32 MB
    """
    sym_list = list(symbol_arrays.keys())
    lengths  = [symbol_arrays[s]["close"].shape[0] for s in sym_list]
    offsets  = np.cumsum([0] + lengths[:-1]).astype(np.int32)

    flat = np.zeros((sum(lengths), N_FEATURES), dtype=np.float32)
    for i, sym in enumerate(sym_list):
        start, end = offsets[i], offsets[i] + lengths[i]
        for fi, feat in enumerate(FEATURE_ORDER):
            flat[start:end, fi] = symbol_arrays[sym][feat]

    _GPU_FLAT_DATA.update({
        "price_flat":  cuda.to_device(flat),
        "sym_offsets": cuda.to_device(offsets),
        "sym_lengths": cuda.to_device(np.array(lengths, np.int32)),
        "sym_list":    sym_list,
    })
    logger.info(f"✅ Flat VRAM pack: {flat.nbytes/1e6:.1f} MB for {len(sym_list)} symbols")
```

---

### ส่วนที่ 3 — `_mega_batch_gpu_backtest(genome_batch)`

เรียก kernel ครั้งเดียวสำหรับ 256 genomes × 20 symbols × 4 horizons:

```python
GENOME_BATCH_SIZE = 256
HORIZON_BARS = [30*48, 90*48, 180*48, 365*48]  # 1M, 3M, 6M, 1Y

def _mega_batch_gpu_backtest(genome_batch: List[Dict]) -> List[Dict]:
    n_g = len(genome_batch)
    n_s = len(_GPU_FLAT_DATA["sym_list"])
    n_h = len(HORIZON_BARS)
    total = n_g * n_s * n_h   # 256 × 20 × 4 = 20,480

    # Pack genomes → float32 [n_g, 29]
    d_genome_params = cuda.to_device(_pack_genomes_to_flat(genome_batch))
    d_horizon_bars  = cuda.to_device(np.array(HORIZON_BARS, np.int32))
    d_out           = cuda.device_array(total * 4, dtype=np.float32)
    stream = cuda.stream()

    try:
        _mega_backtest_kernel[(total+255)//256, 256, stream](
            _GPU_FLAT_DATA["price_flat"],
            _GPU_FLAT_DATA["sym_offsets"],
            _GPU_FLAT_DATA["sym_lengths"],
            d_horizon_bars, d_genome_params, d_out,
            n_g, n_s, n_h
        )
        stream.synchronize()
        raw = np.nan_to_num(d_out.copy_to_host(), nan=0.0).reshape(n_g, n_s, n_h, 4)
    finally:
        del d_genome_params, d_horizon_bars, d_out

    # Aggregate fitness for each genome (fast numpy on CPU — [256,20,4,4] is tiny)
    return [_compute_fitness_from_matrix(raw[gi]) for gi in range(n_g)]
```

---

### ส่วนที่ 4 — Ask-and-Tell Loop แทน `study.optimize()`

```python
# แทนที่:
# study.optimize(objective, n_trials=n_trials, n_jobs=N_CPU_WORKERS)

# ด้วย:
completed = 0
while (n_trials is None) or (completed < n_trials):
    batch_size = min(GENOME_BATCH_SIZE,
                     (n_trials - completed) if n_trials else GENOME_BATCH_SIZE)

    # 1. TPE suggest batch ของ genomes ทั้งหมดพร้อมกัน
    optuna_trials = [study.ask() for _ in range(batch_size)]
    genomes = [_build_genome_from_trial(t) for t in optuna_trials]

    # 2. ONE kernel call: ทำ backtest batch พร้อมกัน
    batch_results = _mega_batch_gpu_backtest(genomes)

    # 3. Tell Optuna ผลลัพธ์ทุก genome ใน batch
    for t, res in zip(optuna_trials, batch_results):
        study.tell(t, res["fitness_score"])

    # 4. Update leaderboard + progress
    with lock:
        for t, res in zip(optuna_trials, batch_results):
            leaderboard_map[f"trial_{t.number}"] = res
    completed += batch_size
    # ... save_progress, sync leaderboard every 5 batches ...
```

---

## สรุปงานทั้งหมด

| # | งาน | ไฟล์ที่แก้ | ความยาก | เวลา (มนุษย์) | เวลา (AI) |
|---|-----|-----------|---------|--------------|----------|
| 1 | เขียน `_mega_backtest_kernel` (3D thread indexing + backtest loop) | `bot_strategy_synthesizer_gpu.py` | สูง | ~2 ชม. | ~5 นาที |
| 2 | เขียน `_pack_symbols_to_flat_gpu()` + global `_GPU_FLAT_DATA` | `bot_strategy_synthesizer_gpu.py` | กลาง | ~30 นาที | ~1 นาที |
| 3 | เขียน `_pack_genomes_to_flat()` (Dict → float32 matrix) | `bot_strategy_synthesizer_gpu.py` | ง่าย | ~20 นาที | ~1 นาที |
| 4 | เขียน `_mega_batch_gpu_backtest()` (single kernel call) | `bot_strategy_synthesizer_gpu.py` | กลาง | ~45 นาที | ~2 นาที |
| 5 | เขียน `_compute_fitness_from_matrix()` (numpy aggregation) | `bot_strategy_synthesizer_gpu.py` | ง่าย | ~20 นาที | ~1 นาที |
| 6 | แทนที่ `study.optimize()` ด้วย Ask-and-Tell loop | `bot_strategy_synthesizer_gpu.py` | กลาง | ~30 นาที | ~2 นาที |
| 7 | Syntax check + ทดสอบ import | Terminal | — | ~1 ชม. | ~2 นาที |

**เวลารวม (มนุษย์): ~5–6 ชั่วโมง**
**เวลารวม (AI เขียนให้): ~15–20 นาที** ✅

---

## ผลลัพธ์ที่คาดหวัง

| Metric | ก่อน Mega-Batch | หลัง Mega-Batch |
|--------|----------------|----------------|
| Genomes/batch | 1 | 256 |
| Kernel calls/batch | 80 | **1** |
| GPU occupancy | ~2.5% | **~50–70%** |
| Trials/วัน (RTX 3070) | ~80K–200K | **~2M–10M** |
| Speedup vs CPU original | ~15× | **~700–3,000×** |

---

## VRAM Budget Check (RTX 3070 = 8,192 MB)

| Data | Size |
|------|------|
| Flat price data (20 sym × 17,520 bars × 23 feat × 4B) | **32.3 MB** |
| Genome batch (256 × 29 params × 4B) | **~30 KB** |
| Output array (256 × 20 × 4 horizons × 4 stats × 4B) | **~640 KB** |
| **Total** | **~33 MB = 0.4% of 8,192 MB** ✅ |

> สามารถเพิ่ม batch size จาก 256 → **4,096 genomes** ถ้าต้องการได้เลย!
