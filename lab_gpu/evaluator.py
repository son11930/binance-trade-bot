"""
evaluator.py — Orchestrates CUDA kernels and CPU fallbacks for evaluating genome batches across time horizons.
"""
import numpy as np
from typing import Dict, List, Any

from .config import logger, CUDA_THREADS_PER_BLOCK, _STRAT_MAP_MB, _MACRO_MAP_MB
from .gpu_kernel import GPU_AVAILABLE, _backtest_kernel, _mega_backtest_kernel
from .cpu_kernel import simulate_strategy_genome_cpu
from .data_loader import _GPU_FLAT_DATA, _GPU_DEVICE_ARRAYS, _build_symbol_arrays_for_cpu
from .fitness import _pack_genomes_to_flat, _vectorized_batch_compute_fitness, _apply_four_pillar_fitness

def _cpu_eval_from_arrays(arrays: Dict[str, np.ndarray], genome: Dict[str, Any], bars: int) -> Dict[str, float]:
    """CPU fallback evaluation directly from numpy arrays."""
    import pandas as pd
    n = arrays["close"].shape[0]
    slice_n = min(bars, n)
    df_data = {
        "close": arrays["close"][-slice_n:],
        "high":  arrays["high"][-slice_n:],
        "low":   arrays["low"][-slice_n:],
        "open":  arrays["open"][-slice_n:],
        "volume":arrays["vol"][-slice_n:],
        "SMA_200":   arrays["sma200"][-slice_n:],
        "SMA_50":    arrays["sma50"][-slice_n:],
        "ATR":       arrays["atr"][-slice_n:],
        "RSI":       arrays["rsi"][-slice_n:],
        "ADX":       arrays["adx"][-slice_n:],
        "SMA_20_Vol":arrays["vol_sma"][-slice_n:],
        "BB_Upper":  arrays["bb_up"][-slice_n:],
        "EMA_10":    arrays["ema10"][-slice_n:],
        "EMA_50":    arrays["ema50"][-slice_n:],
        "supertrend_dir": arrays["st_dir"][-slice_n:],
        "mfi":       arrays["mfi"][-slice_n:],
        "stoch_rsi_k": arrays["stoch_k"][-slice_n:],
        "cci":       arrays["cci"][-slice_n:],
        "williams_r":arrays["williams"][-slice_n:],
        "keltner_lower": arrays["keltner_low"][-slice_n:],
        "ichimoku_tenkan": arrays["tenkan"][-slice_n:],
        "ichimoku_kijun":  arrays["kijun"][-slice_n:],
        "donchian_high_20":arrays["donchian_high"][-slice_n:],
    }
    return simulate_strategy_genome_cpu(pd.DataFrame(df_data), genome)

def _batch_gpu_backtest(
    df_arrays: Dict[str, np.ndarray],
    genome_batch: List[Dict[str, Any]],
    n_bars: int,
    _use_preloaded: bool = False
) -> List[Dict[str, float]]:
    """Evaluate a batch of genome candidates on the GPU simultaneously."""
    if not genome_batch:
        return []

    n = len(genome_batch)
    sort_order = [_STRAT_MAP_MB.get(gn.get("strategy_type", "rsi_sniper"), 0) for gn in genome_batch]
    sorted_pairs = sorted(zip(sort_order, range(n), genome_batch), key=lambda x: x[0])
    genome_batch_sorted = [p[2] for p in sorted_pairs]
    original_order = [p[1] for p in sorted_pairs]

    def g(key, default=0.0):
        if key == "kelly_fraction_cap":
            return np.array([max(0.20, min(0.40, float(gn.get(key, default)))) for gn in genome_batch_sorted], dtype=np.float32)
        return np.array([float(gn.get(key, default)) for gn in genome_batch_sorted], dtype=np.float32)

    is_device = _use_preloaded or hasattr(df_arrays["close"], "copy_to_host")
    if is_device and GPU_AVAILABLE:
        preloaded = df_arrays
        bars = min(n_bars, int(preloaded["close"].shape[0]))
        d_ca  = preloaded["close"][-bars:]
        d_ha  = preloaded["high"][-bars:]
        d_la  = preloaded["low"][-bars:]
        d_oa  = preloaded["open"][-bars:]
        d_va  = preloaded["vol"][-bars:]
        d_s200= preloaded["sma200"][-bars:]
        d_s50 = preloaded["sma50"][-bars:]
        d_atr = preloaded["atr"][-bars:]
        d_rsi = preloaded["rsi"][-bars:]
        d_adx = preloaded["adx"][-bars:]
        d_vsm = preloaded["vol_sma"][-bars:]
        d_bbu = preloaded["bb_up"][-bars:]
        d_e10 = preloaded["ema10"][-bars:]
        d_e50 = preloaded["ema50"][-bars:]
        d_std = preloaded["st_dir"][-bars:]
        d_mfi = preloaded["mfi"][-bars:]
        d_stk = preloaded["stoch_k"][-bars:]
        d_cci = preloaded["cci"][-bars:]
        d_wlr = preloaded["williams"][-bars:]
        d_kel = preloaded["keltner_low"][-bars:]
        d_ten = preloaded["tenkan"][-bars:]
        d_kij = preloaded["kijun"][-bars:]
        d_don = preloaded["donchian_high"][-bars:]
        price_device_vars = []
    else:
        from numba import cuda as nb_cuda
        bars = min(n_bars, df_arrays["close"].shape[0])
        d_ca  = nb_cuda.to_device(df_arrays["close"][-bars:].astype(np.float32))
        d_ha  = nb_cuda.to_device(df_arrays["high"][-bars:].astype(np.float32))
        d_la  = nb_cuda.to_device(df_arrays["low"][-bars:].astype(np.float32))
        d_oa  = nb_cuda.to_device(df_arrays["open"][-bars:].astype(np.float32))
        d_va  = nb_cuda.to_device(df_arrays["vol"][-bars:].astype(np.float32))
        d_s200= nb_cuda.to_device(df_arrays["sma200"][-bars:].astype(np.float32))
        d_s50 = nb_cuda.to_device(df_arrays["sma50"][-bars:].astype(np.float32))
        d_atr = nb_cuda.to_device(df_arrays["atr"][-bars:].astype(np.float32))
        d_rsi = nb_cuda.to_device(df_arrays["rsi"][-bars:].astype(np.float32))
        d_adx = nb_cuda.to_device(df_arrays["adx"][-bars:].astype(np.float32))
        d_vsm = nb_cuda.to_device(df_arrays["vol_sma"][-bars:].astype(np.float32))
        d_bbu = nb_cuda.to_device(df_arrays["bb_up"][-bars:].astype(np.float32))
        d_e10 = nb_cuda.to_device(df_arrays["ema10"][-bars:].astype(np.float32))
        d_e50 = nb_cuda.to_device(df_arrays["ema50"][-bars:].astype(np.float32))
        d_std = nb_cuda.to_device(df_arrays["st_dir"][-bars:].astype(np.float32))
        d_mfi = nb_cuda.to_device(df_arrays["mfi"][-bars:].astype(np.float32))
        d_stk = nb_cuda.to_device(df_arrays["stoch_k"][-bars:].astype(np.float32))
        d_cci = nb_cuda.to_device(df_arrays["cci"][-bars:].astype(np.float32))
        d_wlr = nb_cuda.to_device(df_arrays["williams"][-bars:].astype(np.float32))
        d_kel = nb_cuda.to_device(df_arrays["keltner_low"][-bars:].astype(np.float32))
        d_ten = nb_cuda.to_device(df_arrays["tenkan"][-bars:].astype(np.float32))
        d_kij = nb_cuda.to_device(df_arrays["kijun"][-bars:].astype(np.float32))
        d_don = nb_cuda.to_device(df_arrays["donchian_high"][-bars:].astype(np.float32))
        price_device_vars = [d_ca, d_ha, d_la, d_oa, d_va, d_s200, d_s50, d_atr,
                             d_rsi, d_adx, d_vsm, d_bbu, d_e10, d_e50, d_std,
                             d_mfi, d_stk, d_cci, d_wlr, d_kel, d_ten, d_kij, d_don]

    from numba import cuda as nb_cuda
    d_adx_t = nb_cuda.to_device(g("adx_trend_thresh", 20.0))
    d_vol_m = nb_cuda.to_device(g("vol_surge_mult", 1.2))
    d_sl_a  = nb_cuda.to_device(g("sl_atr_mult", 1.5))
    d_tp_r  = nb_cuda.to_device(g("tp_rr_mult", 2.5))
    d_rsisn = nb_cuda.to_device(g("gear1_rsi_sniper", 78.0))
    d_stkt  = nb_cuda.to_device(g("stoch_k_thresh", 80.0))
    d_mfit  = nb_cuda.to_device(g("mfi_bull_thresh", 40.0))
    d_ccit  = nb_cuda.to_device(g("cci_trend_thresh", 0.0))
    d_wilt  = nb_cuda.to_device(g("williams_r_thresh", -80.0))
    d_mntg  = nb_cuda.to_device(g("gear2_moonshot_trigger_pct", 0.02))
    d_mngp  = nb_cuda.to_device(g("gear2_moonshot_gap_pct", 0.005))
    d_trtg  = nb_cuda.to_device(g("gear3_trailing_trigger_pct", 0.012))
    d_trgp  = nb_cuda.to_device(g("gear3_trailing_gap_pct", 0.008))
    d_betg  = nb_cuda.to_device(g("gear4_breakeven_trigger_pct", 0.006))
    d_bebf  = nb_cuda.to_device(g("gear4_breakeven_buffer_pct", 0.001))
    d_mxhd  = nb_cuda.to_device(g("max_hold_bars", 36.0))
    d_s2b   = nb_cuda.to_device(g("sma200_buffer_pct", 0.995))
    d_vflr  = nb_cuda.to_device(g("volume_floor_mult", 0.7))
    d_rssc  = nb_cuda.to_device(g("rsi_surge_ceiling", 82.0))
    d_slcp  = nb_cuda.to_device(g("sl_hard_cap_pct", 0.04))
    d_tpcp  = nb_cuda.to_device(g("tp_hard_cap_pct", 0.10))
    d_cool  = nb_cuda.to_device(g("cooldown_bars_after_sl", 2.0))
    d_kell  = nb_cuda.to_device(g("kelly_fraction_cap", 0.25))
    d_gntm  = nb_cuda.to_device(g("giant_candle_atr_mult", 2.0))
    use_dual_arr = np.array([1.0 if gn.get("use_dual_trend", True) else 0.0 for gn in genome_batch_sorted], dtype=np.float32)
    req_grn_arr  = np.array([1.0 if gn.get("require_green_candle", False) else 0.0 for gn in genome_batch_sorted], dtype=np.float32)
    strat_arr    = np.array([float(_STRAT_MAP_MB.get(gn.get("strategy_type", "rsi_sniper"), 0)) for gn in genome_batch_sorted], dtype=np.float32)
    macro_arr    = np.array([float(_MACRO_MAP_MB.get(gn.get("macro_regime_filter", "sma200_only"), 0)) for gn in genome_batch_sorted], dtype=np.float32)
    d_udual = nb_cuda.to_device(use_dual_arr)
    d_rqgrn = nb_cuda.to_device(req_grn_arr)
    d_strat = nb_cuda.to_device(strat_arr)
    d_macro = nb_cuda.to_device(macro_arr)
    d_tmadx = nb_cuda.to_device(g("trend_strength_min_adx", 15.0))

    genome_device_vars = [d_adx_t, d_vol_m, d_sl_a, d_tp_r, d_rsisn, d_stkt, d_mfit,
                          d_ccit, d_wilt, d_mntg, d_mngp, d_trtg, d_trgp, d_betg, d_bebf,
                          d_mxhd, d_s2b, d_vflr, d_rssc, d_slcp, d_tpcp, d_cool, d_kell,
                          d_gntm, d_udual, d_rqgrn, d_strat, d_macro, d_tmadx]

    d_out_profit  = nb_cuda.device_array(n, dtype=np.float32)
    d_out_winrate = nb_cuda.device_array(n, dtype=np.float32)
    d_out_maxdd   = nb_cuda.device_array(n, dtype=np.float32)
    d_out_trades  = nb_cuda.device_array(n, dtype=np.float32)
    output_device_vars = [d_out_profit, d_out_winrate, d_out_maxdd, d_out_trades]

    stream = nb_cuda.stream()
    try:
        threads_per_block = CUDA_THREADS_PER_BLOCK
        blocks = (n + threads_per_block - 1) // threads_per_block
        _backtest_kernel[blocks, threads_per_block, stream](
            d_ca, d_ha, d_la, d_oa, d_va,
            d_s200, d_s50, d_atr, d_rsi, d_adx,
            d_vsm, d_bbu, d_e10, d_e50,
            d_std, d_mfi, d_stk, d_cci, d_wlr,
            d_kel, d_ten, d_kij, d_don,
            d_adx_t, d_vol_m, d_sl_a, d_tp_r, d_rsisn,
            d_stkt, d_mfit, d_ccit, d_wilt,
            d_mntg, d_mngp, d_trtg, d_trgp,
            d_betg, d_bebf, d_mxhd,
            d_s2b, d_vflr, d_rssc, d_slcp, d_tpcp,
            d_cool, d_kell, d_gntm, d_udual, d_rqgrn,
            d_strat, d_macro, d_tmadx,
            d_out_profit, d_out_winrate, d_out_maxdd, d_out_trades,
            bars
        )
        try:
            stream.synchronize()
        except Exception as cuda_err:
            logger.error(f"CUDA kernel execution error: {cuda_err}")
            return [{"net_profit_pct": 0.0, "win_rate": 0.0, "max_dd": 0.0, "trades": 0}] * n

        profits  = np.nan_to_num(d_out_profit.copy_to_host(stream=stream),  nan=0.0, posinf=0.0, neginf=0.0)
        winrates = np.nan_to_num(d_out_winrate.copy_to_host(stream=stream), nan=0.0, posinf=0.0, neginf=0.0)
        maxdds   = np.nan_to_num(d_out_maxdd.copy_to_host(stream=stream),   nan=0.0, posinf=0.0, neginf=0.0)
        trades   = np.nan_to_num(d_out_trades.copy_to_host(stream=stream),  nan=0.0, posinf=0.0, neginf=0.0)
    finally:
        for arr in price_device_vars + genome_device_vars + output_device_vars:
            del arr

    unsorted_results = [None] * n
    for sorted_idx, orig_idx in enumerate(original_order):
        unsorted_results[orig_idx] = {
            "net_profit_pct": float(profits[sorted_idx]),
            "win_rate":       float(winrates[sorted_idx]),
            "max_dd":         float(maxdds[sorted_idx]),
            "trades":         int(trades[sorted_idx])
        }
    return unsorted_results

def evaluate_genome_gpu(
    symbol_arrays: Dict[str, Dict[str, np.ndarray]],
    genome: Dict[str, Any]
) -> Dict[str, Any]:
    """Evaluate a genome across 4 time horizons on GPU (or CPU fallback) across all symbols."""
    horizons = {"1m": 30 * 48, "3m": 90 * 48, "6m": 180 * 48, "1y": 365 * 48}
    res: Dict[str, Any] = {}
    total_trades_1y = 0; win_rate_1y = 0.0; max_dd_all = 0.0; moonshots = 0

    for h_name, bars in horizons.items():
        h_profits: List[float] = []
        h_trades_list: List[int] = []
        h_wins_list: List[float] = []
        for sym, arrays in symbol_arrays.items():
            n_available = arrays["close"].shape[0]
            if n_available < bars:
                continue
            if GPU_AVAILABLE:
                arrs_to_use = _GPU_DEVICE_ARRAYS.get(sym, arrays) if _GPU_DEVICE_ARRAYS else arrays
                use_pre = (arrs_to_use is not arrays) or hasattr(arrs_to_use["close"], "copy_to_host")
                stats_list = _batch_gpu_backtest(arrs_to_use, [genome], bars, _use_preloaded=use_pre)
                stats = stats_list[0]
            else:
                stats = _cpu_eval_from_arrays(arrays, genome, bars)
            h_profits.append(stats["net_profit_pct"])
            if h_name == "1y":
                h_trades_list.append(stats["trades"])
                h_wins_list.append(stats["win_rate"] * stats["trades"] / 100.0)
                if stats["max_dd"] > max_dd_all:
                    max_dd_all = stats["max_dd"]
                if stats["net_profit_pct"] > 30.0:
                    moonshots += 1
        avg = float(np.mean(h_profits)) if h_profits else 0.0
        res[f"net_profit_{h_name}"]        = round(avg, 2)
        res[f"net_profit_{h_name}_dollar"] = round(avg * 10.0, 2)
        if h_name == "1y":
            total_trades_1y = sum(h_trades_list)
            total_wins      = sum(h_wins_list)
            win_rate_1y     = round((total_wins / total_trades_1y * 100.0), 2) if total_trades_1y > 0 else 0.0

    res["win_rate_1y"]    = win_rate_1y
    res["max_dd"]         = round(max_dd_all, 2)
    res["total_trades_1y"]= total_trades_1y
    res["moonshots_1y"]   = moonshots
    res["avg_trades_month"]= round(total_trades_1y / 12.0, 1)
    res["avg_trades_day"]  = round(total_trades_1y / 365.0, 1)

    return _apply_four_pillar_fitness(res, ["1y", "6m", "3m", "1m"])

def _mega_batch_gpu_backtest(genome_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Single mega-kernel call: evaluates genome_batch across ALL symbols × ALL horizons simultaneously."""
    if not GPU_AVAILABLE or not _GPU_FLAT_DATA:
        return [evaluate_genome_gpu(_build_symbol_arrays_for_cpu(), g) for g in genome_batch]

    from numba import cuda as nb_cuda

    n_g  = len(genome_batch)
    n_s  = _GPU_FLAT_DATA["n_symbols"]
    n_h  = _GPU_FLAT_DATA["n_horizons"]
    total_threads = n_g * n_s * n_h

    genome_mat      = _pack_genomes_to_flat(genome_batch)
    d_genome_params = nb_cuda.to_device(genome_mat)
    d_out           = nb_cuda.device_array(total_threads * 4, dtype=np.float32)
    stream          = nb_cuda.stream()

    try:
        blocks = (total_threads + CUDA_THREADS_PER_BLOCK - 1) // CUDA_THREADS_PER_BLOCK
        _mega_backtest_kernel[blocks, CUDA_THREADS_PER_BLOCK, stream](
            _GPU_FLAT_DATA["price_flat"],
            _GPU_FLAT_DATA["sym_offsets"],
            _GPU_FLAT_DATA["sym_lengths"],
            _GPU_FLAT_DATA["horizon_bars"],
            d_genome_params,
            d_out,
            n_g, n_s, n_h
        )
        try:
            stream.synchronize()
        except Exception as cuda_err:
            logger.error(f"Mega-kernel CUDA error: {cuda_err}")
            return [{"fitness_score": 0.0, "net_profit_1y": 0.0, "net_profit_6m": 0.0,
                     "net_profit_3m": 0.0, "net_profit_1m": 0.0, "win_rate_1y": 0.0,
                     "max_dd": 0.0, "total_trades_1y": 0, "moonshots_1y": 0,
                     "avg_trades_month": 0.0, "avg_trades_day": 0.0}] * n_g

        raw = np.nan_to_num(
            d_out.copy_to_host(stream=stream),
            nan=0.0, posinf=0.0, neginf=0.0
        ).reshape(n_g, n_s, n_h, 4)
    finally:
        del d_genome_params, d_out

    h_names = ["1m", "3m", "6m", "1y"]
    return _vectorized_batch_compute_fitness(raw, n_g, n_s)
