# แผนเร่ง GPU Strategy Lab และยกระดับความพร้อมสำหรับเทรดเงินจริง

> วันที่ตรวจ: 2026-08-05
> สถานะ: Planning only — สำหรับส่งต่อให้ Luna; ยังไม่มีการแก้ implementation, config, process หรือคำสั่งซื้อขาย
> ขอบเขต: `run_strategy_lab_gpu.bat`, `bot_strategy_synthesizer_gpu.py`, `lab_gpu/`, live bot, API, strategy promotion และ monitoring

## CAPABILITY

ผู้ดูแลต้องสามารถค้นหา strategy candidate ได้เร็วขึ้นโดยไม่แลกกับความถูกต้อง วัดผลด้วย `validated genomes/second` และ `qualified candidates/hour` แทนการพยายามทำให้กราฟ GPU เป็น 100% จากนั้นต้องคัดกรอง candidate ด้วย simulator ที่ causal และ reproducible, walk-forward และ untouched holdout, realistic cost/fill model, shadow/paper และ canary ก่อนเพิ่มเงินจริง พร้อม deterministic risk controls, exchange-native protection, reconciliation, monitoring และ rollback

ไม่มีระบบใดรับประกัน “กำไรจริง” ได้ เป้าหมายของแผนนี้คือสร้างหลักฐานว่า strategy มี positive expectancy หลังต้นทุนภายใต้หลาย market regimes และจำกัดความเสียหายเมื่อผลจริงเบี่ยงจาก backtest

## สรุปคำตอบจากการตรวจ

### GPU ทำงานจริงหรือไม่

**ทำงานจริง** หลักฐานจาก run ปัจจุบัน:

- Log ระบุ `GPU CUDA (RTX 3070)`, preload ข้อมูล 20 symbols เข้า VRAM และใช้ mega-batch 4,096 genomes
- Python ตรวจพบ Numba CUDA และ CuPy; CUDA device คือ RTX 3070 Laptop GPU
- Progress เพิ่มต่อเนื่องและทำได้ประมาณ **330–334 genomes/วินาที** รวมช่วงสร้าง candidate, fitness และ I/O
- ใช้ VRAM ประมาณ 0.6–0.7 GB; การใช้ VRAM น้อยไม่ใช่ปัญหาในตัวเอง เพราะ dataset มีขนาดเพียงประมาณ 32 MB และ workload ไม่ได้ต้องใช้ VRAM ทั้ง 8 GB
- ภาพ Task Manager แสดง engine `3D` ไม่ใช่ `CUDA/Compute` จึงไม่ควรใช้ค่า 0% ในภาพตัดสินว่า CUDA ไม่ทำงาน

### ทำไม GPU ดูทำงานน้อยและเป็นช่วง ๆ

1. **Default run เล็กเกินไป**
   เมนู default รัน 100 trials เท่ากับเพียง 100 × 4 horizons = 400 CUDA threads หรือประมาณ 4 blocks ที่ 128 threads จึง underfill RTX 3070 อย่างมาก แม้ชื่อเมนูจะเรียก GPU Edition

2. **หนึ่ง thread ทำงานอนุกรมหนักเกินไป**
   Kernel กำหนด `1 thread = 1 genome × 1 horizon` แล้ว thread เดียววนทุก bar และทุก 20 symbols ทำให้ parallelism อยู่ที่ระดับ genome แต่ time/symbol loop ยังเป็น serial

3. **Warp divergence จากการปน 4 horizons**
   `tid % 4` ทำให้ warp เดียวมี 1M/3M/6M/1Y ปนกัน Thread 1M จบก่อนแต่ต้องรอ thread 1Y และ branch ของ 12 strategy types ยิ่งเพิ่ม divergence

4. **Local-memory/register pressure สูง**
   แต่ละ thread มี local arrays 6 ชุด × 32 ค่าเพื่อเก็บสถานะ portfolio มีความเสี่ยงเกิด register spill ไป local/global memory จึงสอดคล้องกับ memory activity สูงแต่ compute percentage ต่ำ

5. **Pipeline synchronous และมี bubble ทุก batch**
   ทุก batch สร้าง stream ใหม่, allocate/copy genome, launch, `synchronize()`, copy กลับ host แล้วจึงทำ fitness/I/O ไม่มี double buffering และไม่ overlap CPU preparation, GPU kernel, D2H และ DB write

6. **Leaderboard/Aiven I/O บล็อกแทบทุก batch**
   เงื่อนไข sync มีส่วน `best_so_far_score > (batch_idx - 1) * 0` ซึ่งเท่ากับ `best_score > 0` ทำให้ sync ทุก batch หลังมีผลบวก Log แสดง JSON/DB ใช้เวลาราว 1.7–2.2 วินาทีต่อครั้ง และ GPU ต้องรอ

7. **ตัวเลข trials สูง แต่ search ที่มีคุณภาพต่ำกว่าที่เห็น**
   ใน batch 4,096 มี TPE ask/tell เพียง 32 ตัว หรือประมาณ 0.78%; อีก 4,064 ตัวเป็น mutants ที่ไม่ถูก `study.tell()` จึงไม่ควรวัดความเร็วจาก raw trials อย่างเดียว

8. **80 genes แต่ GPU ใช้จริง 29 genes**
   มี 51 genes ที่ optimizer สุ่มและ leaderboard แสดง แต่ไม่เข้า kernel จึงไม่เปลี่ยน fitness ทำให้เสีย search budget, เกิด duplicate phenotype และสร้างความมั่นใจผิด ๆ

9. **Environment และคำโฆษณายังไม่ reproducible**
   Launcher เรียก `python` แบบไม่ล็อก interpreter, dependencies GPU ไม่ได้ pin ใน requirements และข้อความ `~1000x faster` ไม่มี benchmark ใน repo รองรับ CuPy ถูก import แต่ execution path หลักที่ตรวจพบใช้ Numba CUDA; ติดตั้ง CuPy เพิ่มอย่างเดียวไม่ทำให้เร็วขึ้น

### ทำไม Top 10 เป็น WILLIAMS_MEAN_REV ทั้งหมด

Top 10 ปัจจุบันเป็น `williams_mean_rev` 10/10 และมี fitness/return/drawdown/trade count เท่ากัน จึงยังสรุปไม่ได้ว่า Williams ดีที่สุดจริง ภาพนี้เป็นหลักฐานของ **search collapse และ behavioral duplicates** มากกว่าหลักฐานว่ากลยุทธ์อื่นแพ้โดยยุติธรรม

- ใน batch 4,096 มี TPE candidates อิสระเพียง 32 ตัว ส่วน 4,064 mutants รับ parent จาก global elite pool
- Mutant ถูกบังคับให้ใช้ `strategy_type` เดิมของ parent เมื่อ Williams ขึ้นนำ จึงเกิดวงจร `Williams ชนะ → สร้าง Williams เพิ่ม → Williams ครอง Top 50`
- ไม่มี archive/quota แยกตาม 12 strategy types และ mutants ที่ชนะไม่ถูกส่งกลับเข้า TPE
- Dedup ใช้ full 80-gene JSON ทั้งที่ GPU ใช้ 29 genes ทำให้ JSON ต่างแต่พฤติกรรมและผลลัพธ์เหมือนกันยังติด Top 10 ได้
- Strategy-specific genes หลายตัวไม่ทำงานจริง เพราะ indicator windows ถูกคำนวณเป็นค่าคงที่ก่อนเข้า kernel ทำให้การแข่งขันระหว่าง strategy ไม่เท่าเทียม
- Lab และ live bot ใช้ชื่อ strategy mapping ไม่ตรงกันหลายชื่อ; unknown live strategy ยัง fallback ไป index 0 ขณะที่ `williams_mean_rev` เป็นชื่อที่ตรงกัน จึงยิ่งทำให้ Williams ดู deployable กว่าคู่แข่ง
- Fitness ให้รางวัลช่วงความถี่ 500–2,500 trades/ปี จึงอาจเอียงเข้าหา mean-reversion ที่ออกสัญญาณถี่กว่ากลยุทธ์ breakout
- `gear4_breakeven_buffer_pct` ถูกสุ่มที่ 0.0005–0.003 แต่ kernel บังคับค่าต่ำกว่า 0.02 เป็น 0.02 ทั้งหมด จึงไม่มี diversity จริง

Williams สามารถเก็บไว้เป็น candidate ได้ แต่ leaderboard ชุดปัจจุบันต้องติดสถานะ `RESEARCH / INVALIDATED_BY_SEARCH_BIAS` และห้ามส่งไป PAPER/LIVE จนผ่าน equal-budget multi-strategy benchmark และ search-fairness gate

### สถานะ Paper/Live และความหมายของปุ่มใน UI

ระบบมี paper execution, `paper_trade` ในฐานข้อมูล, stats แยก PAPER/LIVE และ trade-table filter แล้ว แต่ยังไม่เป็น paper environment ที่แยกและปลอดภัยครบวงจร

- Toggle `PAPER | LIVE` บน header เป็น **VIEW FILTER เท่านั้น** เปลี่ยนรายการ trades/stats ที่แสดง ไม่ได้เปลี่ยน execution mode
- Positions, balance, runtime state, cooldown, daily risk counters และ logs ยังใช้ state ชุดเดียวหรือไม่กรองตาม view mode
- ปุ่ม `PAPER TRADE`/`LIVE TRADE` บน Strategy Lab ไม่ได้ส่ง order ทันที แต่ POST ไป promotion API และเขียน strategy/stage ทับ single active manifest จากนั้น Futures bot hot-load ตอนประเมินสัญญาณถัดไป
- ปุ่มไม่ start/resume bot; ถ้า bot offline จะเป็นการ “arm” manifest ไว้สำหรับรอบถัดไป
- เมื่อ global `PAPER_TRADING=false`, การกด `LIVE TRADE` แล้วกด OK สามารถนำไปสู่ Binance Futures order จริงเมื่อ bot ทำงานและเกิดสัญญาณ
- Spot ยังอิง global `PAPER_TRADING` และไม่ได้ใช้ manifest stage เหมือน Futures
- Futures entry บางเส้นทางใช้ manifest stage แต่ real-time exits, cancel และ native stop หลายเส้นทางใช้ global mode จึงมี mode authority สองชุดที่ขัดกัน
- ผลที่เป็นไปได้คือ simulated order ถูกบันทึกเป็น LIVE หรือ paper position ไปเรียก real exit/stop เมื่อ config กับ manifest ไม่ตรงกัน
- Promotion API ปัจจุบันตรวจเพียง rank/stage และ browser confirm ครั้งเดียว ยังไม่มี validation gate, re-auth, flat-position check, canary, independent live-enable หรือ atomic manifest revision

ดังนั้นคำตอบสำหรับภาพที่ 4 คือ **ปุ่มทำงานจริงระดับ deployment manifest แต่ยังไม่ปลอดภัยพอให้ใช้** โดยเฉพาะ `LIVE TRADE` ห้ามกดจน Phase 0A ผ่าน และ `PAPER TRADE` ก็ยังไม่ควรถือว่า isolated 100%

## CONSTRAINTS

### กฎคงที่

- Correctness และ CPU/GPU/live semantic parity ต้องผ่านก่อน optimization
- ห้าม promote strategy จาก leaderboard ไป LIVE โดยตรง
- ห้าม promote leaderboard ชุดปัจจุบันไป PAPER เพราะยังไม่ผ่าน search-fairness gate
- ต้องมี execution-mode authority เพียงชุดเดียว; หาก environment, manifest และ runtime context ไม่ตรงกันให้ fail closed เป็น PAUSED
- Stage/view mode/execution mode ต้องเป็นคนละค่าและแสดงแยกกันชัดเจน
- ห้ามเปลี่ยน PAPER↔LIVE ขณะมี open position, open order หรือ reconciliation mismatch
- ทุก tunable gene ต้องถูก simulator ใช้จริง หรือเอาออกจาก schema/search space
- Signal บน bar `t` ห้าม fill ก่อน `t+1` หรือก่อน bid/ask ที่ causal ตาม execution model
- ทุกผลต้องรวม maker/taker fee, spread, slippage, funding, latency, partial fill และ market impact ตามขนาด order
- Final holdout ห้ามถูกใช้ใน fitness, tuning, leaderboard ranking หรือ threshold adjustment
- ทุก run ต้องมี master seed, code/data/config/kernel hash และ checkpoint ที่ resume ได้
- Hard risk controls เป็น deterministic logic; AI เป็นได้เพียง filter/veto/annotation
- งาน implementation ในอนาคตใช้ TDD และ coverage รวมอย่างน้อย 80% พร้อม unit/integration/E2E
- ห้ามตั้งเป้า “GPU 100%” เป็น Definition of Done; ต้องวัด throughput, latency, search quality และ parity

### สิ่งที่ระบบมีแล้วและต้องรักษา

- มี fixed-fractional futures sizing ผูกกับ stop distance
- มี daily trade/loss และ portfolio heat circuit breakers
- มี exchange-native futures stop พร้อม fail-closed flow เมื่อวาง stop ไม่สำเร็จ
- มี strategy manifest และ authenticated promotion endpoint
- มี IS/OOS split ภายใน kernel และ cost บางส่วนแล้ว แต่ยังไม่ถือเป็น untouched validation หรือ realistic execution model

## IMPLEMENTATION CONTRACT

### Actors

- **Research operator**: เริ่ม/หยุด run, ดู benchmark และเลือก candidate เพื่อ review
- **Strategy Lab**: สร้าง candidates, simulate, score, checkpoint และเผยแพร่ research evidence
- **Validator**: ทำ walk-forward, cost stress, final holdout และ parity checks โดยไม่แก้ candidate
- **Promotion controller**: บังคับ state `RESEARCH → VALIDATED → SHADOW → PAPER → CANARY → LIVE → DEMOTED`
- **Live execution/risk engine**: เป็น source of truth ด้าน order, fill, position, protection และ risk
- **Luna**: implement ตาม phase และหยุดเมื่อ gate ของ phase ก่อนหน้าไม่ผ่าน

### Data and identity invariants

- ใช้ canonical strategy enum และ parameter schema ชุดเดียวใน lab, manifest และ live bot
- Unknown strategy/parameter ต้อง reject แบบ fail closed ห้าม default ไป strategy 0
- Candidate ID ต้องผูกกับ strategy schema version, code commit, dataset hash, feature hash, seed, cost model และ validation report
- Market data ทุก symbol ต้อง join ด้วย UTC timestamp intersection ไม่ใช่ตัดท้ายให้จำนวนแถวเท่ากัน
- Candle ต้อง unique, monotonic, spacing 30 นาทีตาม contract และมี gap policy ชัดเจน
- Event/trade ledger เป็น output หลักสำหรับ parity ไม่ใช่ดู aggregate return อย่างเดียว
- ทุก order/position/fill/log ต้องมี immutable `execution_mode`, `deployment_id`, `strategy_id`, version/hash และ provenance
- Execution mode ต้องถูกผูกกับ position ตั้งแต่ entry จน exit ห้ามอ่าน mode ใหม่กลาง position
- Paper และ Live ต้องแยก position, balance, PnL, cooldown, risk counters, recovery state และ query scope

### Observability contract

ต้องมี metric แยกอย่างน้อย:

- CPU load/cache time
- candidate generation/validation/packing time
- H2D time
- kernel time แยก horizon/strategy
- D2H time
- fitness time
- JSON/DB queue and write time
- batch throughput p50/p95
- GPU active time, occupancy, warp execution efficiency, register/local spill และ global-load efficiency
- candidates generated, candidates told to optimizer, unique phenotype ratio และ qualified candidates/hour
- generated/evaluated/qualified counts, score quantiles, unique phenotype และ trade-ledger diversity แยกตาม strategy type
- effective execution mode, manifest stage, environment mode และ mismatch alarm

## แผนดำเนินงานสำหรับ Luna

### Phase 0A — Immediate deployment containment (ต้องทำก่อนทุก Phase)

- ปิด direct `LIVE` activation ทั้ง UI และ server เป็นค่าเริ่มต้น; `LIVE` เป็น request จนกว่าจะผ่าน promotion gates
- เพิ่ม server-side `ALLOW_LIVE`/independent arming control ที่ default เป็น false; ห้ามพึ่งการ disable ปุ่มหน้าเว็บอย่างเดียว
- สร้าง immutable `ExecutionContext` เป็น single source of truth และส่งเข้า entry, exit, native stop, cancel, risk, DB และ reconciliation ทุกเส้นทาง
- หาก global config, manifest stage และ ExecutionContext ขัดกัน ให้ block new orders, pause และแจ้ง critical alert
- Reject stage transition เมื่อ bot ไม่ paused, มี local/exchange position/order หรือ reconciliation ไม่สะอาด
- เปลี่ยน manifest write เป็น schema-validated, locked, atomic replace, revision/CAS, idempotency key และ audit trail
- Manifest เสีย/อ่านไม่ครบต้อง fail closed เป็น PAUSED ห้าม fallback cached LIVE
- เพิ่ม typed confirmation + fresh re-auth สำหรับ live request พร้อมแสดง account, symbols, leverage, max risk และ kill switch

**Exit gates**

- Truth-table tests ครบ global PAPER/LIVE × manifest PAPER/LIVE × Spot/Futures × entry/exit/stop/cancel
- Exchange-mutating calls = 0 ทุกกรณี ยกเว้น LIVE context ที่ผ่าน server-side arming เท่านั้น
- DB execution mode ตรงกับ exchange/simulator receipt 100%
- 0 cross-mode exits และ stage transition ขณะมี position ถูก reject 100%
- Corrupt/partial manifest ทำให้ระบบ PAUSED และไม่มี order

### Phase 0 — Freeze baseline และสร้าง performance/correctness harness

**ทำก่อนแก้ performance ใด ๆ**

- เพิ่ม benchmark mode ที่ไม่เขียน Aiven และบันทึก phase timings ด้วย CPU timers + CUDA Events
- เก็บ Nsight Systems/Compute baseline และ `nvidia-smi dmon`; ใน Task Manager เลือก CUDA/Compute graph
- Benchmark batch 100, 1K, 2K, 4K, 8K และ block 64/128/256 หลัง warm-up
- แยก startup/JIT/data-load ออกจาก steady-state throughput
- สร้าง deterministic mini dataset และ fixed genomes สำหรับ golden CPU↔GPU test
- เปรียบเทียบ raw 16 metrics, trade ledger และ final fitness ไม่ใช่เฉพาะ shape
- เพิ่ม contract test ที่ fail หากมี suggested gene ไม่อยู่ใน consumed schema
- บันทึก current baseline ประมาณ 330–334 genomes/s และ batch interval p50 ประมาณ 9.85s เป็น reference ไม่ใช่ guarantee

**Exit gates**

- Same seed + same hashes ให้ candidate sequence และ Top-K เดิม
- CPU/GPU raw metrics และ ledger ตรงตาม tolerance ที่ประกาศ (`<=1e-5` สำหรับ float ที่เหมาะสม)
- Benchmark report ระบุ p50/p95 ของทุก phase และไม่รวม JIT ใน steady state
- ทราบ register count, local spills, occupancy และ warp efficiency จาก profiler

### Phase 1 — แก้ search truth ก่อนเพิ่มจำนวน trials

- เลือกทางใดทางหนึ่ง: ลด schema ให้เหลือ 29 active genesอย่างซื่อสัตย์ หรือ implement 51 genes ที่เหลือใน feature/kernel/live path ให้ครบ
- Deduplicate ด้วย active phenotype/signal hash/trade-ledger hash ไม่ใช่ full JSON
- ทำ canonical mapping ของ 12 strategy types ระหว่าง lab และ live; ห้าม unknown fallback
- Clamp mutation ตาม typed per-gene bounds ชุดเดียวกับ search schema
- กำหนด master seed ให้ Python `random`, NumPy และ Optuna
- เปลี่ยน persistent study/checkpoint เพื่อ resume ได้และไม่ทำ trials ซ้ำ
- ออกแบบ optimizer batch policy ให้ชัด: ทุก candidate ต้อง register/tell หรือใช้ evolutionary population ที่มี selection/replacement contract ชัดเจน
- แยก per-strategy archive/niche ทั้ง 12 แบบพร้อม global archive และให้ equal exploration budget ก่อน global exploitation
- ให้แต่ละ strategy มี exploration floor อย่างน้อย 5% ต่อ batch ในช่วงค้นหาเริ่มต้น และคง random exploration 10–20% หลังเริ่ม exploit
- ทำให้ `strategy_type` mutate แบบ controlled categorical ได้ หรือแยก optimizer/study ต่อ strategy
- ใช้ conditional search space ที่สุ่มเฉพาะ genes ที่ strategy นั้นใช้จริง พร้อม sensitivity test ว่า perturb gene แล้ว output ต้องเปลี่ยน
- Audit ทุก search bound/default กับ kernel clamp รวมถึง breakeven buffer mismatch
- ทำ equal-budget benchmark: 12 strategies × หลาย seeds × หลาย regimes × cost model เดียวกัน
- เพิ่ม buy-and-hold, random-entry ที่ match frequency และ fixed Williams เป็น control baselines
- จำกัด Top 10 ไม่เกิน 2 behavioral phenotypes ต่อ strategy จน search-fairness ผ่าน

**Exit gates**

- 0 unused tunable genes
- 100% strategy enum และ parameter mapping parity
- Same run identity ให้ผลซ้ำได้
- Dashboard แยก `raw candidates`, `optimizer observations`, `unique phenotypes` และ `qualified candidates`
- ไม่มี strategy ใดได้ exploration ต่ำกว่า floor ก่อน convergence และ leaderboard ไม่มี trade-ledger duplicates
- จะประกาศ Williams ว่าดีกว่าได้เมื่อ median/CI ของ OOS PF, expectancy และ drawdown ชนะอย่างสม่ำเสมอข้าม seeds/regimes/final holdout

### Phase 2 — Quick wins เพื่อลด GPU idle โดยไม่เปลี่ยน semantics

- แก้ leaderboard sync predicate ให้ sync เมื่อถึง interval หรือมี new global best จริง
- แยก JSON/DB เป็น bounded async single-writer queue; GPU loop ห้ามรอ network
- ใช้ atomic JSON snapshot, pooled DB connection และ upsert; เอา create/delete-all ออกจาก hot path
- Throttle progress DB write ตามเวลา ไม่ใช่ทุก event
- สำหรับ GPU mode กำหนด minimum useful batch; งานเล็ก 100 trials ให้เตือนหรือใช้ CPU path
- ลบข้อความ `~1000x faster` แล้วแสดง measured throughput จาก benchmark ล่าสุด
- Pin interpreter/environment และเพิ่ม startup preflight สำหรับ CUDA driver, Numba, compute capability และ package versions
- เอา redundant per-symbol VRAM preload ออกเมื่อ mega flat buffer เป็น path เดียว
- Preallocate/reuse device buffers, host pinned buffers และ streams

**Exit gates**

- DB/API ล่มหรือช้าไม่ทำให้ kernel pipeline stall
- ไม่มี leaderboard corruption/duplicate write หลัง restart
- End-to-end throughput เพิ่มอย่างน้อย 20–30% จาก baselineโดย raw metrics/ledger ไม่เปลี่ยน
- Default launcher ไม่สร้าง GPU run ที่ underfill โดยไม่เตือนผู้ใช้

### Phase 3 — ลด warp divergence และทำ pipeline overlap

- แยก launch ตาม horizon หรือจัด horizon-major เพื่อให้ warp เดียวมี loop length เดียวกัน
- หลัง parity ผ่าน ให้ group ตาม strategy type และใช้ strategy-specialized kernels เพื่อลด branch divergence
- เปลี่ยน layout เป็น structure-of-arrays หรือ feature subsets ตาม strategy เมื่อ profiler ยืนยันประโยชน์
- ลด/compact per-thread portfolio state และแก้ open-position count แบบ incremental แทน scan ทุก symbol ทุก bar
- ใช้ double buffer/อย่างน้อย 2 streams เพื่อ overlap candidate generation + H2D ของ batch N+1 กับ kernel/D2H ของ batch N
- พิจารณา CUDA Graphs หลัง launch pattern คงที่
- ห้าม parallelize symbols แบบตรง ๆ ถ้ายังรักษา shared balance, max concurrent positions และลำดับ event แบบ deterministic ไม่ได้

**Exit gates**

- Golden parity ยังผ่านทุก strategy/horizon
- End-to-end validated genomes/s หรือ qualified candidates/hour เพิ่มอย่างน้อย 2× จาก baseline
- ไม่มี throughput regression >10% ใน p95 จาก run ซ้ำ 5 ครั้ง
- Profiler ยืนยัน warp efficiency/occupancy ดีขึ้นและ local spills ลดลง

### Phase 4 — Multi-fidelity search โดยไม่ลดมาตรฐานผู้ชนะ

- ใช้ short horizon/symbol subset เป็น cheap screening เท่านั้น
- Candidate ที่รอดต้อง re-evaluate ด้วย canonical 20-symbol/4-horizon simulation เต็มรูปแบบ
- วัด false-negative rate ของ screening และ diversity ของ survivors
- ใช้ metric `validated winners/hour`, repeat-run stability และ phenotype diversity ไม่ใช่ trials/hour

**Exit gates**

- Champion ทุกตัวมี full canonical evaluation
- Screening ไม่เปลี่ยน final evidence contract และไม่แตะ final holdout
- Winner discovery rate ดีขึ้นโดย robustness ไม่ลดจาก baseline

### Phase 5 — Causal simulator และ validation ที่เชื่อถือได้

- Join symbols ด้วย timestamp และเพิ่ม gap/data-quality report
- Signal bar `t` fill ที่ next tradable bid/ask หลัง latency; ห้าม same-close fill
- เพิ่ม symbol/time-varying maker/taker fee, spread, slippage, funding timestamps, depth impact, partial/rejected fill, margin และ liquidation
- ทำ rolling walk-forward อย่างน้อย 6 folds บนข้อมูล 3–5 ปี ครอบคลุม bull/bear/sideways/high-vol
- Purge อย่างน้อย max lookback 200 bars และ embargo อย่างน้อย max hold 72 bars
- สร้าง immutable final holdout ล่าสุด 6–12 เดือนที่ optimizer และ leaderboard ไม่เคยเห็น และประเมินครั้งเดียว
- เพิ่ม bootstrap confidence interval, Deflated Sharpe และ PBO/equivalent สำหรับ multiple-testing bias จาก trials จำนวนมาก

**Validation gates ก่อนเรียก candidate ว่า VALIDATED**

- Positive net return และ expectancy อย่างน้อย 70% ของ folds
- OOS PF `>=1.20`, OOS max drawdown `<=15%`, median OOS Sharpe `>=1.0`
- ไม่มี fold ใด PF `<0.90`
- Bootstrap 95% CI lower bound ของ net expectancy `>0` หลังต้นทุน
- OOS degradation ของ risk-adjusted metric ไม่เกิน 40% จาก IS
- Cost stress 2× ยังมี PF `>=1.05`, expectancy `>0`, drawdown `<=20%`
- Final holdout ผ่าน one-shot; หาก fail ให้ reject research version ห้าม tune แล้วทดสอบ holdout เดิมซ้ำ

### Phase 6 — Shadow/Paper engine ที่จำลอง execution จริง

- แยก paper service/account/state จาก live โดย paper credentials/network policy ต้องไม่มีสิทธิ์สร้าง exchange order
- แยก paper/live positions, balance/equity, PnL, cooldown, daily limits, drawdown, recovery snapshot และ reconciliation namespace
- เพิ่ม `execution_mode`, `deployment_id`, strategy version/hash, client/exchange order ID และ fill provenance ลง trade/log/event schema
- บังคับทุก repository/query/cache/learning pipeline ระบุ execution mode ห้าม aggregate ข้าม mode โดยปริยาย
- ใช้ event-driven engine กับ live bid/ask/order book
- บันทึก signal, submit, ack, partial fill, final fill, cancel/reject, fee, funding และ expected-vs-actual slippage
- Fault injection: stale data, websocket down, API timeout, partial fill, duplicate submit, DB down, restart และ native-stop reject
- Reconcile order/fill/position กับ exchange source of truth

**Promotion gate PAPER → CANARY**

- Run อย่างน้อย 8 สัปดาห์และอย่างน้อย 300 closed trades โดยใช้เงื่อนไขที่ใช้เวลานานกว่า
- PF `>=1.15`; 95% CI lower bound ของ expectancy `>0`; drawdown `<=10%`
- Fill ratio `>=98%`; p95 order ack `<2s`
- p95 realized slippage ไม่เกิน model +10 bps
- ไม่มี unreconciled position เกิน 60 วินาที
- Paper-vs-backtest metric drift ไม่เกิน 20%
- Activity ใน PAPER ต้องไม่เปลี่ยน LIVE state/metrics และ activity ใน LIVE ต้องไม่เปลี่ยน PAPER state/metrics

### Phase 6A — Paper/Live UI และ deployment workflow

- เปลี่ยน header toggle เป็น `VIEW: PAPER | LIVE` เพื่อยืนยันว่าเป็นตัวกรอง ไม่ใช่ execution switch
- เพิ่ม banner แยก `EXECUTION: PAPER/LIVE/PAUSED/MISMATCH` จาก effective server context
- แต่ละ view ต้องแสดง balance/equity, positions, trades, stats, PnL, risk counters และ logs ของ mode นั้นเท่านั้น
- แสดง active strategy ID/version/hash, deployment time, evidence status และ data freshness
- เปลี่ยนปุ่ม Lab เป็น `Stage for Paper Review`; ปุ่ม LIVE เป็น `Request Live Canary` และ disable จน server gates ผ่าน
- หลัง action ต้อง refresh deployment state และแสดงผลสำเร็จจาก server revision ไม่ใช่ toast อย่างเดียว
- LIVE challenge ต้องใช้ fresh re-auth, typed phrase และสรุป account/risk; การอนุมัติยังต้องผ่าน server-side policy

**UI/data exit gates**

- สลับ VIEW แล้วทุก widget เปลี่ยน mode สอดคล้องกัน ไม่มี shared positions/balance/log leakage
- Mismatch ระหว่าง manifest/config/runtime แสดง CRITICAL และปิดปุ่ม execution
- UI E2E ยืนยันว่า browser bypass ไม่สามารถข้าม server gate

### Phase 7 — Hard risk, execution safety และ promotion governance

- เริ่ม canary ด้วย risk/trade 0.25–0.5%, portfolio heat 2–3%, daily loss 1.5–2%, weekly loss 4% และ hard equity drawdown kill 8–10%
- เพิ่ม consecutive-loss pause, correlation/sector caps, liquidation-distance floor, stale-data/API/clock-drift kill switches
- ทุก live position ต้องมี verified exchange-native reduce-only stop; หากวางไม่ได้ให้ fail closed
- ใช้ actual fill/commission/funding เป็น accounting source of truth
- เพิ่ม idempotent client order ID, order state machine, partial fill handling และ restart reconciliation
- Manifest ต้อง immutable/versioned และมี dataset/code/config hashes, validation evidence, approver, expiry และ rollback target
- เปลี่ยน state ได้เฉพาะ `VALIDATED → SHADOW → PAPER → CANARY → LIVE`; ห้าม leaderboard → LIVE
- Canary ใช้ทุนไม่เกิน 5%; scale 5→15→30→50→100% เมื่อผ่าน rolling evidence เท่านั้น

**Canary gates**

- อย่างน้อย 4 สัปดาห์และ 50 closed trades
- Rolling PF `>=1.10`; drawdown อยู่ใน budget; fill/slippage SLO ผ่าน
- 0 duplicate orders, 0 unprotected positions, 100% restart reconciliation
- เมื่อ hard stop หรือ health breach ให้ block new entries และ rollback/demote ตาม policy

### Phase 8 — Production monitoring และ continuous validation

- Reconcile orders, fills, fees, funding, realized/unrealized PnL และ equity ทุกวัน
- Alert: missing stop, stale feed, reject/partial, reconciliation mismatch, breaker, drawdown, slippage/cost drift และ strategy decay
- Dashboard แสดง strategy/version/stage/hash, data age, risk budget, open risk, DD, fees/funding/slippage และ backtest-vs-live drift
- Auto-demote ใช้ minimum trades/time/confidence gate ห้ามตัดสินจากแพ้ไม่กี่ไม้
- ทำ quarterly recovery/rollback drill

**Operations gates**

- Daily equity discrepancy `<=0.1%` หรือ `$1` แล้วแต่มูลค่าที่มากกว่า
- Unmatched fills = 0
- Alert delivery `>=99.9%`
- ไม่มี new trade เมื่อ data stale, exchange disconnect หรือ breaker ทำงาน

## TEST-FIRST MATRIX สำหรับ Luna

1. Parameter schema/unused gene/strategy enum contract tests
2. Deterministic seed, checkpoint/resume และ candidate sequence tests
3. Timestamp alignment, gap, no-lookahead และ next-bar fill tests
4. CPU↔GPU raw metric + event/trade-ledger golden parity ทุก strategy/horizon
5. Cost/funding/slippage/partial-fill/liquidation tests
6. DB queue failure, atomic snapshot และ restart tests
7. Native stop, duplicate submit, order lifecycle และ reconciliation integration tests
8. Walk-forward/holdout isolation และ multiple-testing correction tests
9. Shadow/paper drift, canary promotion และ rollback E2E tests
10. Performance regression benchmark โดยมี p50/p95 และ quality-adjusted throughput
11. Strategy exploration balance, per-strategy archive, phenotype dedup และ equal-budget multi-seed tests
12. Execution-mode truth table, cross-mode entry/exit/stop/cancel และ DB provenance integration tests
13. Promotion API authorization, stage transition, manifest atomicity/CAS และ corrupt-manifest failure tests
14. PAPER/LIVE view isolation และ live challenge UI E2E tests

Coverage รวมต้อง `>=80%` และ critical risk/execution paths ต้องมี branch coverage ที่เพียงพอ ห้ามแก้ test เพื่อให้ implementation ที่ผิดผ่าน

## NON-GOALS

- ไม่แก้โค้ด, config, dependencies, process หรือ trading parameters ในงาน planning รอบนี้
- ไม่ restart/stop run ปัจจุบันและไม่ส่ง order ใด ๆ
- ไม่รับรองกำไรจาก leaderboard, win rate หรือ backtest return
- ไม่เพิ่ม leverage/risk เพื่อทำให้ผลตอบแทนดูดีขึ้น
- ไม่ optimize GPU ก่อนมี golden parity และ search-truth contract
- ไม่ใช้ GPU utilization percentage เป็น KPI เดี่ยว
- ไม่ auto-promote strategy

## OPEN QUESTIONS ที่เจ้าของระบบต้องยืนยันก่อน Phase 6–7

1. ยอมรับ paper/shadow อย่างน้อย 8 สัปดาห์หรือไม่ แม้แผนเดิมใน `PROJECT_PLAN.md` ระบุว่าจะลงเงินจริงโดยไม่ paper?
2. Max loss budget ที่ยอมรับได้จริงต่อ trade/day/week/portfolio drawdown เท่าไร?
3. จะคง Hedge Mode หรือเปลี่ยน One-way Mode โดยอิง correctness/operational simplicity ก่อนกำไรหรือไม่?
4. มี historical production fills, fee tier, funding และ order-book/slippage data 6–12 เดือนให้ calibrate simulator หรือไม่?
5. Final untouched holdout จะกันช่วงวันใดและใครมีสิทธิ์เปิดผล one-shot?
6. เกณฑ์ขั้นต่ำ paper/canary จะยึดตามแผนนี้ หรือมีข้อจำกัดด้านเวลา/ทุนอื่น?
7. อนุมัติให้ปิดปุ่ม direct LIVE และบังคับ paper/canary gate เป็นนโยบายถาวรหรือไม่?
8. ต้องการให้ Paper และ Live รันพร้อมกันแบบแยก process/account หรือให้รันได้ทีละ mode?

คำถามเหล่านี้ไม่ขวาง Phase 0–5 แต่ต้องตอบก่อนอนุญาตเงินจริง

## HANDOFF

สถานะ: **พร้อมส่งให้ Luna ทำตามแผนแบบทีละ Phase โดยเริ่ม Phase 0A เท่านั้น; ห้ามสั่งทำทุก Phase รวดเดียวและห้าม LIVE rollout ข้าม gate**

ลำดับที่ Luna ต้องทำ:

1. ใช้ `tdd-workflow` ทำ Phase 0A execution-mode truth table และปิด direct LIVE activation ก่อน
2. ให้ security-reviewer ตรวจ Phase 0A และปิด CRITICAL/HIGH ทั้งหมด
3. ทำ Phase 0 baseline, parameter contract, deterministic seed และ CPU/GPU golden parity tests
4. ส่งผล Phase 0 ให้ architect + trade-strategist review
5. ทำ Phase 1 search-fairness; invalidate leaderboard เดิมและห้าม PAPER promotion จน gate ผ่าน
6. ถ้า parity/search truth ไม่ผ่าน ห้ามแตะ kernel optimization
7. ทำ Phase 2–3 ทีละ change พร้อม parity/performance report ทุก PR
8. ใช้ `verification-loop` ตรวจ Phase 4–6A และใช้ `security-review` ก่อน promotion/live changes ทุกครั้ง
9. ให้ code-reviewer และ security-reviewer ปิด CRITICAL/HIGH ก่อน merge

## DEFINITION OF DONE ของแผนทั้งหมด

- ไม่มี unused genes และ strategy mapping ตรงกันตลอด lab→manifest→live
- Same seed/data/code ให้ผล reproduce และ resume ได้
- CPU/GPU/live replay parity ผ่าน
- End-to-end qualified candidate throughput เพิ่มอย่างน้อย 2× โดย evidence quality ไม่ลด
- Candidate ผ่าน rolling walk-forward, cost stress และ untouched holdout
- Strategy search ผ่าน equal-budget fairness และ leaderboard ไม่มี behavioral duplicates
- Shadow/paper/canary ผ่านเกณฑ์ก่อนเพิ่มเงินจริง
- Paper/Live execution contexts และ UI/data ถูกแยก ไม่มี cross-mode mutation
- ไม่มี unprotected position, duplicate order หรือ unresolved reconciliation
- Risk/rollback/monitoring ทำงานได้เมื่อ component ล้มเหลว
- Unit/integration/E2E ผ่านและ coverage รวม `>=80%`
- ไม่มี unresolved critical security finding
