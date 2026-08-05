"""
gpu_kernel.py — Numba CUDA device kernels for high-speed parallel strategy simulation.
"""
import time
import numpy as np
from typing import Dict, Any, Optional
from .config import logger, CUDA_THREADS_PER_BLOCK, N_GENOME_PARAMS

GPU_AVAILABLE = False
CUPY_AVAILABLE = False
_cuda_jit = None
_cuda_jit_cached = None

try:
    from numba import cuda, njit
    from numba import float32 as nb_f32
    import numba
    GPU_AVAILABLE = cuda.is_available()
    _cuda_jit = cuda.jit
    _cuda_jit_cached = cuda.jit(cache=True, fastmath=True)
    if GPU_AVAILABLE:
        gpu = cuda.get_current_device()
        print(f"[GPU] ✅ CUDA GPU detected: {gpu.name.decode('utf-8')} | CC {gpu.compute_capability}")
    else:
        print("[GPU] ⚠️  Numba installed but no CUDA GPU found. Falling back to CPU multi-core mode.")
except ImportError:
    print("[GPU] ⚠️  Numba not installed. Falling back to CPU multi-core mode.")
    print("[GPU]     To enable GPU: pip install numba")

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    pass

if GPU_AVAILABLE and _cuda_jit:
    @_cuda_jit_cached
    def _backtest_kernel(*args, **kwargs):
        pass # Deprecated in Phase 1

    @_cuda_jit_cached
    def _mega_backtest_kernel(
        price_data_flat, sym_offsets, sym_lengths, horizon_bars,
        genome_params, out_results, n_genomes, n_symbols, n_horizons, min_len
    ):
        # 1 Thread = 1 Genome x 1 Horizon
        tid = cuda.grid(1)
        total_threads = n_genomes * n_horizons
        if tid >= total_threads:
            return

        # Horizon-Major layout: Threads in the same block (warp) process the SAME horizon.
        # This completely eliminates warp divergence caused by different loop lengths (In-Sample vs Out-of-Sample).
        g_idx = tid % n_genomes
        h_idx = tid // n_genomes
        
        h_bars = horizon_bars[h_idx]
        
        base = tid * 16
        
        if h_bars > min_len:
            for i in range(16):
                out_results[base + i] = 0.0
            return

        start_bar = min_len - h_bars
        end_bar = min_len
        first_sim_bar = start_bar + 200
        
        if first_sim_bar >= end_bar:
            for i in range(16):
                out_results[base + i] = 0.0
            return
            
        total_trading_bars = end_bar - first_sim_bar
        is_end_bar = first_sim_bar + int(total_trading_bars * 0.7)

        # Load genome params
        adx_thresh      = genome_params[g_idx, 0]
        vol_mult        = genome_params[g_idx, 1]
        sl_atr          = genome_params[g_idx, 2]
        tp_rr           = genome_params[g_idx, 3]
        rsi_sniper      = genome_params[g_idx, 4]
        stoch_thresh    = genome_params[g_idx, 5]
        mfi_thresh      = genome_params[g_idx, 6]
        cci_thresh      = genome_params[g_idx, 7]
        williams_thresh = genome_params[g_idx, 8]
        moonshot_trig   = genome_params[g_idx, 9]
        moonshot_gap    = genome_params[g_idx, 10]
        trail_trig      = genome_params[g_idx, 11]
        trail_gap       = genome_params[g_idx, 12]
        be_trig         = genome_params[g_idx, 13]
        be_buf          = genome_params[g_idx, 14] if genome_params[g_idx, 14] > 0.02 else 0.02
        max_hold        = int(genome_params[g_idx, 15])
        sma200_buf      = genome_params[g_idx, 16]
        vol_floor       = genome_params[g_idx, 17]
        rsi_surge_ceil  = genome_params[g_idx, 18]
        sl_cap          = genome_params[g_idx, 19]
        tp_cap          = genome_params[g_idx, 20]
        cooldown_limit  = float(int(genome_params[g_idx, 21]))
        kelly           = genome_params[g_idx, 22]
        giant_mult      = genome_params[g_idx, 23]
        use_dual        = genome_params[g_idx, 24] > 0.5
        req_green       = genome_params[g_idx, 25] > 0.5
        strat           = int(genome_params[g_idx, 26])
        macro           = int(genome_params[g_idx, 27])
        trend_min_adx   = genome_params[g_idx, 28]
        
        rsi_hook_oversold = genome_params[g_idx, 29]
        rsi_reversal_exit_thresh = genome_params[g_idx, 30]
        bb_lower_buffer = genome_params[g_idx, 31]
        bb_upper_buffer = genome_params[g_idx, 32]
        macd_cross_lookback = genome_params[g_idx, 33]
        mfi_bear_thresh = genome_params[g_idx, 34]
        momentum_req_pos_hist = genome_params[g_idx, 35]
        supertrend_mult = genome_params[g_idx, 36]
        ichi_cloud_buffer = genome_params[g_idx, 37]
        keltner_mult = genome_params[g_idx, 38]
        cci_extreme_exit = genome_params[g_idx, 39]
        williams_r_exit = genome_params[g_idx, 40]
        rejection_wick_ratio = genome_params[g_idx, 41]
        vol_cap_rejection = genome_params[g_idx, 42]
        vol_cap_normal = genome_params[g_idx, 43]
        body_min_atr_pct = genome_params[g_idx, 44]
        high_low_spread_cap = genome_params[g_idx, 45]
        spot_step_trigger1 = genome_params[g_idx, 46]
        spot_step_lock1 = genome_params[g_idx, 47]
        spot_step_trigger2 = genome_params[g_idx, 48]
        spot_step_lock2 = genome_params[g_idx, 49]
        spot_step_trigger3 = genome_params[g_idx, 50]
        spot_step_lock3 = genome_params[g_idx, 51]
        gear1_sniper_slope = genome_params[g_idx, 52]
        gear1_sniper_max_rsi = genome_params[g_idx, 53]
        gear1_sniper_min_rsi = genome_params[g_idx, 54]
        gear2_moonshot_atr_mult = genome_params[g_idx, 55]
        gear3_trailing_atr_mult = genome_params[g_idx, 56]
        mom_tp_roe_thresh = genome_params[g_idx, 57]
        mom_tp_rsi_thresh = genome_params[g_idx, 58]
        mom_tp_drop_pct = genome_params[g_idx, 59]
        max_pos_alloc_pct = genome_params[g_idx, 60]
        min_trade_notional = genome_params[g_idx, 61]
        pyramid_scaling_mult = genome_params[g_idx, 62]
        sideways_max_adx = genome_params[g_idx, 63]
        adx_slope_check = genome_params[g_idx, 64]
        vol_exhaustion_mult = genome_params[g_idx, 65]

        # Shared Portfolio State
        balance = 1000.0
        peak_balance = 1000.0
        max_dd = 0.0
        wins = 0
        total_trades = 0
        gross_profit = 0.0
        gross_loss = 0.0
        curr_streak = 0.0
        max_streak = 0.0
        
        # Local Arrays for exactly 20 symbols (Reduced from 32 to lower register pressure & boost occupancy)
        in_pos = cuda.local.array(20, dtype=nb_f32)
        entry_p = cuda.local.array(20, dtype=nb_f32)
        sl_p = cuda.local.array(20, dtype=nb_f32)
        tp_p = cuda.local.array(20, dtype=nb_f32)
        bars_in_trade = cuda.local.array(20, dtype=nb_f32)
        cooldown_counter = cuda.local.array(20, dtype=nb_f32)
        
        for s in range(n_symbols):
            in_pos[s] = 0.0
            entry_p[s] = 0.0
            sl_p[s] = 0.0
            tp_p[s] = 0.0
            bars_in_trade[s] = 0.0
            cooldown_counter[s] = 0.0
            
        max_concurrent = 10.0
        
        for t in range(first_sim_bar, end_bar):
            if t == is_end_bar:
                net_p = ((balance - 1000.0) / 1000.0) * 100.0
                if net_p > 10000.0: net_p = 10000.0
                w_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
                out_results[base + 0] = net_p
                out_results[base + 1] = w_rate
                out_results[base + 2] = max_dd * 100.0
                out_results[base + 3] = total_trades
                out_results[base + 4] = gross_profit * 100.0
                out_results[base + 5] = gross_loss * 100.0
                out_results[base + 6] = max_streak
                out_results[base + 7] = 0.0
                
                balance = 1000.0
                peak_balance = 1000.0
                max_dd = 0.0
                wins = 0
                total_trades = 0
                gross_profit = 0.0
                gross_loss = 0.0
                curr_streak = 0.0
                max_streak = 0.0
                for s in range(n_symbols):
                    in_pos[s] = 0.0
                    bars_in_trade[s] = 0.0
                    cooldown_counter[s] = 0.0
            
            open_positions = 0.0
            for s in range(n_symbols):
                if in_pos[s] > 0.5:
                    open_positions += 1.0
                    
            # Check Exits first
            for s in range(n_symbols):
                idx = sym_offsets[s] + t
                c = price_data_flat[idx, 0]
                h = price_data_flat[idx, 1]
                l = price_data_flat[idx, 2]
                o = price_data_flat[idx, 3]
                atr = price_data_flat[idx, 7]
                
                if in_pos[s] > 0.5:
                    rsi = price_data_flat[idx, 8]
                    mfi = price_data_flat[idx, 15]
                    cci = price_data_flat[idx, 17]
                    williams = price_data_flat[idx, 18]
                    bars_in_trade[s] += 1.0
                    exited = False
                    pnl_pct = 0.0
                    
                    actual_sl_fill = sl_p[s]
                    if o < sl_p[s]:
                        actual_sl_fill = o
                    
                    actual_tp_fill = tp_p[s]
                    if o > tp_p[s]:
                        actual_tp_fill = o
                        
                    atr_s = price_data_flat[idx, 6]
                    round_trip_cost = 0.0010 + (atr_s / c) * 0.05
                    
                    if l <= actual_sl_fill:
                        pnl_pct = ((actual_sl_fill - entry_p[s]) / entry_p[s]) - round_trip_cost
                        exited = True
                    elif h >= actual_tp_fill:
                        pnl_pct = ((actual_tp_fill - entry_p[s]) / entry_p[s]) - round_trip_cost
                        exited = True
                    elif bars_in_trade[s] >= max_hold:
                        pnl_pct = ((c - entry_p[s]) / entry_p[s]) - round_trip_cost
                        exited = True
                    elif rsi > rsi_reversal_exit_thresh or cci > cci_extreme_exit or williams > williams_r_exit or mfi < mfi_bear_thresh:
                        pnl_pct = ((c - entry_p[s]) / entry_p[s]) - round_trip_cost
                        exited = True
                        
                    if exited:
                        adj_kelly = kelly * pyramid_scaling_mult
                        if adj_kelly > max_pos_alloc_pct:
                            adj_kelly = max_pos_alloc_pct
                        trade_impact = pnl_pct * adj_kelly * 4.0
                        balance *= (1.0 + trade_impact)
                        if trade_impact > 0.0:
                            wins += 1
                            gross_profit += trade_impact
                            curr_streak = 0.0
                        else:
                            gross_loss -= trade_impact
                            curr_streak += 1.0
                            if curr_streak > max_streak:
                                max_streak = curr_streak
                        total_trades += 1
                        in_pos[s] = 0.0
                        bars_in_trade[s] = 0.0
                        cooldown_counter[s] = cooldown_limit
                        open_positions -= 1.0
                    else:
                        cur_gain_pct = (h - entry_p[s]) / entry_p[s]
                        if cur_gain_pct >= be_trig:
                            be_sl = entry_p[s] * (1.0 + be_buf)
                            if be_sl > sl_p[s]:
                                sl_p[s] = be_sl
                        if cur_gain_pct >= trail_trig:
                            trail_sl = c * (1.0 - trail_gap)
                            if trail_sl > sl_p[s]:
                                sl_p[s] = trail_sl
                            trail_sl2 = c - (atr * gear3_trailing_atr_mult)
                            if trail_sl2 > sl_p[s]:
                                sl_p[s] = trail_sl2
                        if cur_gain_pct >= moonshot_trig:
                            moon_sl = c * (1.0 - moonshot_gap)
                            if moon_sl > sl_p[s]:
                                sl_p[s] = moon_sl
                            moon_sl2 = c - (atr * gear2_moonshot_atr_mult)
                            if moon_sl2 > sl_p[s]:
                                sl_p[s] = moon_sl2
                        if cur_gain_pct >= spot_step_trigger2:
                            step_sl2 = entry_p[s] * (1.0 + spot_step_lock2)
                            if step_sl2 > sl_p[s]:
                                sl_p[s] = step_sl2
                        if cur_gain_pct >= spot_step_trigger3:
                            step_sl3 = entry_p[s] * (1.0 + spot_step_lock3)
                            if step_sl3 > sl_p[s]:
                                sl_p[s] = step_sl3
                        if cur_gain_pct > mom_tp_roe_thresh and rsi < mom_tp_rsi_thresh:
                            mom_sl = c * (1.0 - mom_tp_drop_pct)
                            if mom_sl > sl_p[s]:
                                sl_p[s] = mom_sl
                        trailing_sl = c - (atr * supertrend_mult)
                        if trailing_sl > sl_p[s]:
                            sl_p[s] = trailing_sl
                        if sl_p[s] > c:
                            sl_p[s] = c
            
            # Check Entries
            for s in range(n_symbols):
                if in_pos[s] < 0.5:
                    if cooldown_counter[s] > 0.0:
                        cooldown_counter[s] -= 1.0
                    elif open_positions < max_concurrent:
                        idx = sym_offsets[s] + t
                        c = price_data_flat[idx, 0]
                        h = price_data_flat[idx, 1]
                        l = price_data_flat[idx, 2]
                        o = price_data_flat[idx, 3]
                        v = price_data_flat[idx, 4]
                        sma200 = price_data_flat[idx, 5]
                        sma50 = price_data_flat[idx, 6]
                        atr = price_data_flat[idx, 7]
                        rsi = price_data_flat[idx, 8]
                        adx = price_data_flat[idx, 9]
                        vol_sma = price_data_flat[idx, 10]
                        bb_up = price_data_flat[idx, 11]
                        ema10 = price_data_flat[idx, 12]
                        ema50 = price_data_flat[idx, 13]
                        st_dir = price_data_flat[idx, 14]
                        mfi = price_data_flat[idx, 15]
                        stoch_k = price_data_flat[idx, 16]
                        cci = price_data_flat[idx, 17]
                        williams = price_data_flat[idx, 18]
                        keltner_low = price_data_flat[idx, 19]
                        tenkan = price_data_flat[idx, 20]
                        kijun = price_data_flat[idx, 21]
                        donchian_high_prev = price_data_flat[idx - 1, 22]
                        ema10_prev = price_data_flat[idx - 1, 12]
                        ema50_prev = price_data_flat[idx - 1, 13]
                        
                        if adx > adx_thresh and v > (vol_sma * vol_floor):
                            trend_ok = False
                            if macro == 0:
                                trend_ok = (c > sma200 * sma200_buf)
                                if use_dual:
                                    trend_ok = trend_ok and (sma50 > sma200)
                            elif macro == 1:
                                trend_ok = (c > sma200 * sma200_buf) and (adx > trend_min_adx)
                            else:
                                trend_ok = True

                            is_not_blowoff = (h - l) <= (atr * giant_mult)
                            candle_ok = True
                            if req_green:
                                candle_ok = c > o

                            if adx < sideways_max_adx:
                                trend_ok = False
                            if adx_slope_check > 0.5 and adx < 20.0:
                                trend_ok = False
                            if v > vol_sma * vol_exhaustion_mult:
                                candle_ok = False
                                
                            is_rejection = False
                            if h - l > 0.00001:
                                is_rejection = ((o if o < c else c) - l) / (h - l) > rejection_wick_ratio
                            
                            vol_cap = v < (vol_sma * vol_cap_normal)
                            if is_rejection:
                                vol_cap = v < (vol_sma * vol_cap_rejection)
                            if not vol_cap:
                                candle_ok = False
                                
                            body_pct = 0.0
                            if atr > 0.00001:
                                body_pct = abs(c - o) / atr
                            if body_pct < body_min_atr_pct:
                                candle_ok = False
                                
                            if c > 0.00001 and (h - l) / c > high_low_spread_cap:
                                candle_ok = False
                                
                            if balance * kelly < min_trade_notional:
                                candle_ok = False

                            if trend_ok and is_not_blowoff and candle_ok and (c <= bb_up * (1.0 + bb_upper_buffer) or strat == 9):
                                entry_ok = False
                                if strat == 0:
                                    entry_ok = (rsi < rsi_sniper and rsi > gear1_sniper_min_rsi and rsi < gear1_sniper_max_rsi and ema10 > ema10_prev * gear1_sniper_slope) or (v > vol_sma * vol_mult and rsi < rsi_surge_ceil)
                                elif strat == 1:
                                    entry_ok = (ema10 > ema50 and ema10_prev <= ema50_prev and macd_cross_lookback > 0.0)
                                elif strat == 2:
                                    entry_ok = (st_dir == 1 and mfi > mfi_thresh and cci > momentum_req_pos_hist)
                                elif strat == 3:
                                    entry_ok = (c > tenkan + ichi_cloud_buffer and tenkan > kijun and cci > cci_thresh)
                                elif strat == 4:
                                    entry_ok = (l <= keltner_low * keltner_mult and c > keltner_low)
                                elif strat == 5:
                                    entry_ok = (stoch_k < stoch_thresh and mfi > mfi_thresh)
                                elif strat == 6:
                                    entry_ok = (williams < williams_thresh and rsi < rsi_sniper)
                                elif strat == 7:
                                    entry_ok = (c >= donchian_high_prev and adx > trend_min_adx)
                                elif strat == 8:
                                    entry_ok = ((ema10 - ema50) / c > 0.005 and ema10 > ema10_prev and v > vol_sma * vol_mult)
                                elif strat == 9:
                                    entry_ok = (c > bb_up * (1.0 - bb_lower_buffer) and adx > adx_thresh and (atr / c) < 0.03)
                                elif strat == 10:
                                    entry_ok = (st_dir == 1 and tenkan > kijun and mfi > mfi_thresh and rsi > 50.0)
                                elif strat == 11:
                                    entry_ok = (c > sma200 and donchian_high_prev > 0.0 and (donchian_high_prev - c) / donchian_high_prev >= spot_step_trigger1 and (donchian_high_prev - c) / donchian_high_prev <= spot_step_lock1 and rsi < rsi_hook_oversold)

                                if entry_ok:
                                    in_pos[s] = 1.0
                                    entry_p[s] = c
                                    sl_val = c - (atr * sl_atr)
                                    sl_floor = c * (1.0 - sl_cap)
                                    sl_p[s] = sl_val if sl_val > sl_floor else sl_floor
                                    tp_val = c + (atr * sl_atr * tp_rr)
                                    tp_cap_val = c * (1.0 + tp_cap)
                                    tp_p[s] = tp_val if tp_val < tp_cap_val else tp_cap_val
                                    bars_in_trade[s] = 0.0
                                    open_positions += 1.0

            if balance > peak_balance:
                peak_balance = balance
            if peak_balance > 0.0:
                dd = (peak_balance - balance) / peak_balance
                if dd > max_dd:
                    max_dd = dd

        net_profit = ((balance - 1000.0) / 1000.0) * 100.0
        if net_profit > 10000.0:
            net_profit = 10000.0
        win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
        out_results[base + 8] = net_profit
        out_results[base + 9] = win_rate
        out_results[base + 10] = max_dd * 100.0
        out_results[base + 11] = total_trades
        out_results[base + 12] = gross_profit * 100.0
        out_results[base + 13] = gross_loss * 100.0
        out_results[base + 14] = max_streak
        out_results[base + 15] = 0.0

else:
    def _backtest_kernel(*args, **kwargs):
        pass
    def _mega_backtest_kernel(*args, **kwargs):
        pass

def warmup_mega_kernel(gpu_flat_data: Dict[str, Any]) -> None:
    """Trigger JIT compilation of _mega_backtest_kernel with a tiny 1-genome dummy batch."""
    if not GPU_AVAILABLE or not gpu_flat_data:
        return
    from numba import cuda as nb_cuda

    logger.info("⚙️  Compiling CUDA mega-kernel for RTX 3070... (one-time, ~5-15 min, then cached forever)")
    t0 = time.time()

    n_g = 1
    n_s = gpu_flat_data["n_symbols"]
    n_h = gpu_flat_data["n_horizons"]
    min_len = gpu_flat_data["min_len"]
    total_threads = n_g * n_h
    
    dummy_params = np.zeros((1, N_GENOME_PARAMS), dtype=np.float32)
    dummy_params[0, 0] = 20.0
    dummy_params[0, 2] = 1.5
    dummy_params[0, 3] = 2.5
    dummy_params[0, 4] = 78.0
    d_params = nb_cuda.to_device(dummy_params)
    d_out    = nb_cuda.device_array(total_threads * 16, dtype=np.float32)
    stream   = nb_cuda.stream()
    blocks   = max(1, (total_threads + CUDA_THREADS_PER_BLOCK - 1) // CUDA_THREADS_PER_BLOCK)
    try:
        _mega_backtest_kernel[blocks, CUDA_THREADS_PER_BLOCK, stream](
            gpu_flat_data["price_flat"],
            gpu_flat_data["sym_offsets"],
            gpu_flat_data["sym_lengths"],
            gpu_flat_data["horizon_bars"],
            d_params, d_out, n_g, n_s, n_h, min_len
        )
        stream.synchronize()
        elapsed = time.time() - t0
        logger.info(f"✅ CUDA kernel compiled & cached in {elapsed:.1f}s — GPU ready! 🚀")
    except Exception as e:
        logger.warning(f"Kernel warmup error (non-fatal): {e}")
    finally:
        del d_params, d_out
