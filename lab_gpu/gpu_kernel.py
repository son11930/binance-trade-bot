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
    def _backtest_kernel(
        close_arr, high_arr, low_arr, open_arr, vol_arr,
        sma200_arr, sma50_arr, atr_arr, rsi_arr, adx_arr,
        vol_sma_arr, bb_up_arr, ema10_arr, ema50_arr,
        st_dir_arr, mfi_arr, stoch_k_arr, cci_arr, williams_arr,
        keltner_low_arr, tenkan_arr, kijun_arr, donchian_high_arr,
        g_adx_thresh, g_vol_mult, g_sl_atr, g_tp_rr, g_rsi_sniper,
        g_stoch_thresh, g_mfi_thresh, g_cci_thresh, g_williams_thresh,
        g_moonshot_trig, g_moonshot_gap, g_trail_trig, g_trail_gap,
        g_be_trig, g_be_buf, g_max_hold,
        g_sma200_buf, g_vol_floor, g_rsi_surge_ceil, g_sl_cap, g_tp_cap,
        g_cooldown, g_kelly, g_giant_mult, g_use_dual, g_req_green,
        g_strategy_type,
        g_macro_regime,
        g_trend_min_adx,
        out_profit, out_winrate, out_maxdd, out_trades,
        n_bars
    ):
        genome_idx = cuda.grid(1)
        if genome_idx >= out_profit.shape[0]:
            return

        adx_thresh = g_adx_thresh[genome_idx]
        vol_mult = g_vol_mult[genome_idx]
        sl_atr = g_sl_atr[genome_idx]
        tp_rr = g_tp_rr[genome_idx]
        rsi_sniper = g_rsi_sniper[genome_idx]
        stoch_thresh = g_stoch_thresh[genome_idx]
        mfi_thresh = g_mfi_thresh[genome_idx]
        cci_thresh = g_cci_thresh[genome_idx]
        williams_thresh = g_williams_thresh[genome_idx]
        moonshot_trig = g_moonshot_trig[genome_idx]
        moonshot_gap = g_moonshot_gap[genome_idx]
        trail_trig = g_trail_trig[genome_idx]
        trail_gap = g_trail_gap[genome_idx]
        be_trig = g_be_trig[genome_idx]
        be_buf = g_be_buf[genome_idx]
        max_hold = int(g_max_hold[genome_idx])
        sma200_buf = g_sma200_buf[genome_idx]
        vol_floor = g_vol_floor[genome_idx]
        rsi_surge_ceil = g_rsi_surge_ceil[genome_idx]
        sl_cap = g_sl_cap[genome_idx]
        tp_cap = g_tp_cap[genome_idx]
        cooldown_limit = int(g_cooldown[genome_idx])
        kelly = g_kelly[genome_idx]
        giant_mult = g_giant_mult[genome_idx]
        use_dual = g_use_dual[genome_idx] > 0.5
        req_green = g_req_green[genome_idx] > 0.5
        strat = int(g_strategy_type[genome_idx])
        macro = int(g_macro_regime[genome_idx])
        trend_min_adx = g_trend_min_adx[genome_idx]

        in_pos = False
        entry_p = 0.0
        sl_p = 0.0
        tp_p = 0.0
        balance = 1000.0
        peak_balance = 1000.0
        max_dd = 0.0
        wins = 0
        total_trades = 0
        bars_in_trade = 0
        cooldown_counter = 0

        for i in range(200, n_bars):
            c = close_arr[i]
            h = high_arr[i]
            l = low_arr[i]
            o = open_arr[i]
            v = vol_arr[i]
            atr = atr_arr[i]

            if cooldown_counter > 0:
                cooldown_counter -= 1

            if not in_pos and cooldown_counter == 0:
                if adx_arr[i] > adx_thresh and v > (vol_sma_arr[i] * vol_floor):
                    trend_ok = False
                    if macro == 0:
                        trend_ok = (c > sma200_arr[i] * sma200_buf)
                        if use_dual:
                            trend_ok = trend_ok and (sma50_arr[i] > sma200_arr[i])
                    elif macro == 1:
                        trend_ok = (c > sma200_arr[i] * sma200_buf) and (adx_arr[i] > trend_min_adx)
                    else:
                        trend_ok = True

                    is_not_blowoff = (h - l) <= (atr * giant_mult)
                    candle_ok = True
                    if req_green:
                        candle_ok = c > o

                    if trend_ok and is_not_blowoff and candle_ok and c <= bb_up_arr[i]:
                        entry_ok = False
                        if strat == 0:
                            entry_ok = (rsi_arr[i] < rsi_sniper) or (v > vol_sma_arr[i] * vol_mult and rsi_arr[i] < rsi_surge_ceil)
                        elif strat == 1:
                            entry_ok = (ema10_arr[i] > ema50_arr[i] and ema10_arr[i - 1] <= ema50_arr[i - 1])
                        elif strat == 2:
                            entry_ok = (st_dir_arr[i] == 1 and mfi_arr[i] > mfi_thresh)
                        elif strat == 3:
                            entry_ok = (c > tenkan_arr[i] and tenkan_arr[i] > kijun_arr[i] and cci_arr[i] > cci_thresh)
                        elif strat == 4:
                            entry_ok = (l <= keltner_low_arr[i] and c > keltner_low_arr[i])
                        elif strat == 5:
                            entry_ok = (stoch_k_arr[i] < stoch_thresh and mfi_arr[i] > mfi_thresh)
                        elif strat == 6:
                            entry_ok = (williams_arr[i] < williams_thresh and rsi_arr[i] < rsi_sniper)
                        elif strat == 7:
                            entry_ok = (c >= donchian_high_arr[i - 1] and adx_arr[i] > 25.0)

                        if entry_ok:
                            in_pos = True
                            entry_p = c
                            sl_val = c - (atr * sl_atr)
                            sl_floor = c * (1.0 - sl_cap)
                            sl_p = sl_val if sl_val > sl_floor else sl_floor
                            tp_val = c + (atr * sl_atr * tp_rr)
                            tp_cap_val = c * (1.0 + tp_cap)
                            tp_p = tp_val if tp_val < tp_cap_val else tp_cap_val
                            bars_in_trade = 0
            elif in_pos:
                bars_in_trade += 1
                cur_gain_pct = (h - entry_p) / entry_p
                cur_close_pct = (c - entry_p) / entry_p

                if cur_gain_pct >= be_trig:
                    be_sl = entry_p * (1.0 + be_buf)
                    if be_sl > sl_p:
                        sl_p = be_sl
                if cur_gain_pct >= trail_trig:
                    trail_sl = c * (1.0 - trail_gap)
                    if trail_sl > sl_p:
                        sl_p = trail_sl
                if cur_gain_pct >= moonshot_trig:
                    moon_sl = c * (1.0 - moonshot_gap)
                    if moon_sl > sl_p:
                        sl_p = moon_sl

                exited = False
                pnl_pct = 0.0
                if l <= sl_p:
                    pnl_pct = (sl_p - entry_p) / entry_p
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    if pnl_pct > 0.0:
                        wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    cooldown_counter = cooldown_limit
                    exited = True
                elif h >= tp_p:
                    tp_val = tp_p if tp_p > c else c
                    pnl_pct = (tp_val - entry_p) / entry_p
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    exited = True
                elif bars_in_trade >= max_hold:
                    pnl_pct = cur_close_pct
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    if pnl_pct > 0:
                        wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    exited = True

                if balance > 1e10:
                    balance = 1e10

                if not exited:
                    trailing_sl = c - (atr * sl_atr)
                    if trailing_sl > sl_p:
                        sl_p = trailing_sl

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
        out_profit[genome_idx] = net_profit
        out_winrate[genome_idx] = win_rate
        out_maxdd[genome_idx] = max_dd * 100.0
        out_trades[genome_idx] = total_trades

    @_cuda_jit_cached
    def _mega_backtest_kernel(
        price_data_flat, sym_offsets, sym_lengths, horizon_bars,
        genome_params, out_results, n_genomes, n_symbols, n_horizons
    ):
        tid = cuda.grid(1)
        total_threads = n_genomes * n_symbols * n_horizons
        if tid >= total_threads:
            return

        h_idx = tid % n_horizons
        rem = tid // n_horizons
        s_idx = rem % n_symbols
        g_idx = rem // n_symbols

        sym_start = sym_offsets[s_idx]
        sym_len   = sym_lengths[s_idx]
        h_bars    = horizon_bars[h_idx]

        if h_bars > sym_len:
            out_results[tid, 0] = 0.0
            out_results[tid, 1] = 0.0
            out_results[tid, 2] = 0.0
            out_results[tid, 3] = 0.0
            return

        start_bar = sym_start + (sym_len - h_bars)
        end_bar   = sym_start + sym_len

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
        be_buf          = genome_params[g_idx, 14]
        max_hold        = int(genome_params[g_idx, 15])
        sma200_buf      = genome_params[g_idx, 16]
        vol_floor       = genome_params[g_idx, 17]
        rsi_surge_ceil  = genome_params[g_idx, 18]
        sl_cap          = genome_params[g_idx, 19]
        tp_cap          = genome_params[g_idx, 20]
        cooldown_limit  = int(genome_params[g_idx, 21])
        kelly           = genome_params[g_idx, 22]
        giant_mult      = genome_params[g_idx, 23]
        use_dual        = genome_params[g_idx, 24] > 0.5
        req_green       = genome_params[g_idx, 25] > 0.5
        strat           = int(genome_params[g_idx, 26])
        macro           = int(genome_params[g_idx, 27])
        trend_min_adx   = genome_params[g_idx, 28]

        in_pos = False
        entry_p = 0.0
        sl_p = 0.0
        tp_p = 0.0
        balance = 1000.0
        peak_balance = 1000.0
        max_dd = 0.0
        wins = 0
        total_trades = 0
        bars_in_trade = 0
        cooldown_counter = 0

        first_sim_bar = start_bar + 200
        if first_sim_bar >= end_bar:
            out_results[tid, 0] = 0.0
            out_results[tid, 1] = 0.0
            out_results[tid, 2] = 0.0
            out_results[tid, 3] = 0.0
            return

        for i in range(first_sim_bar, end_bar):
            c = price_data_flat[i, 0]
            h = price_data_flat[i, 1]
            l = price_data_flat[i, 2]
            o = price_data_flat[i, 3]
            v = price_data_flat[i, 4]
            sma200 = price_data_flat[i, 5]
            sma50  = price_data_flat[i, 6]
            atr    = price_data_flat[i, 7]
            rsi    = price_data_flat[i, 8]
            adx    = price_data_flat[i, 9]
            vol_sma= price_data_flat[i, 10]
            bb_up  = price_data_flat[i, 11]
            ema10  = price_data_flat[i, 12]
            ema50  = price_data_flat[i, 13]
            st_dir = price_data_flat[i, 14]
            mfi    = price_data_flat[i, 15]
            stoch_k= price_data_flat[i, 16]
            cci    = price_data_flat[i, 17]
            williams=price_data_flat[i, 18]
            keltner_low=price_data_flat[i, 19]
            tenkan = price_data_flat[i, 20]
            kijun  = price_data_flat[i, 21]
            donchian_high_prev = price_data_flat[i - 1, 22]
            ema10_prev = price_data_flat[i - 1, 12]
            ema50_prev = price_data_flat[i - 1, 13]

            if cooldown_counter > 0:
                cooldown_counter -= 1

            if not in_pos and cooldown_counter == 0:
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

                    if trend_ok and is_not_blowoff and candle_ok and c <= bb_up:
                        entry_ok = False
                        if strat == 0:
                            entry_ok = (rsi < rsi_sniper) or (v > vol_sma * vol_mult and rsi < rsi_surge_ceil)
                        elif strat == 1:
                            entry_ok = (ema10 > ema50 and ema10_prev <= ema50_prev)
                        elif strat == 2:
                            entry_ok = (st_dir == 1 and mfi > mfi_thresh)
                        elif strat == 3:
                            entry_ok = (c > tenkan and tenkan > kijun and cci > cci_thresh)
                        elif strat == 4:
                            entry_ok = (l <= keltner_low and c > keltner_low)
                        elif strat == 5:
                            entry_ok = (stoch_k < stoch_thresh and mfi > mfi_thresh)
                        elif strat == 6:
                            entry_ok = (williams < williams_thresh and rsi < rsi_sniper)
                        elif strat == 7:
                            entry_ok = (c >= donchian_high_prev and adx > 25.0)

                        if entry_ok:
                            in_pos = True
                            entry_p = c
                            sl_val = c - (atr * sl_atr)
                            sl_floor = c * (1.0 - sl_cap)
                            sl_p = sl_val if sl_val > sl_floor else sl_floor
                            tp_val = c + (atr * sl_atr * tp_rr)
                            tp_cap_val = c * (1.0 + tp_cap)
                            tp_p = tp_val if tp_val < tp_cap_val else tp_cap_val
                            bars_in_trade = 0
            elif in_pos:
                bars_in_trade += 1
                cur_gain_pct = (h - entry_p) / entry_p
                cur_close_pct = (c - entry_p) / entry_p

                if cur_gain_pct >= be_trig:
                    be_sl = entry_p * (1.0 + be_buf)
                    if be_sl > sl_p:
                        sl_p = be_sl
                if cur_gain_pct >= trail_trig:
                    trail_sl = c * (1.0 - trail_gap)
                    if trail_sl > sl_p:
                        sl_p = trail_sl
                if cur_gain_pct >= moonshot_trig:
                    moon_sl = c * (1.0 - moonshot_gap)
                    if moon_sl > sl_p:
                        sl_p = moon_sl

                exited = False
                pnl_pct = 0.0
                if l <= sl_p:
                    pnl_pct = (sl_p - entry_p) / entry_p
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    if pnl_pct > 0.0:
                        wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    cooldown_counter = cooldown_limit
                    exited = True
                elif h >= tp_p:
                    tp_val = tp_p if tp_p > c else c
                    pnl_pct = (tp_val - entry_p) / entry_p
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    exited = True
                elif bars_in_trade >= max_hold:
                    pnl_pct = cur_close_pct
                    balance *= (1.0 + (pnl_pct * kelly * 4.0))
                    if pnl_pct > 0:
                        wins += 1
                    total_trades += 1
                    in_pos = False
                    bars_in_trade = 0
                    exited = True

                if balance > 1e10:
                    balance = 1e10

                if not exited:
                    trailing_sl = c - (atr * sl_atr)
                    if trailing_sl > sl_p:
                        sl_p = trailing_sl

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
        out_results[tid, 0] = net_profit
        out_results[tid, 1] = win_rate
        out_results[tid, 2] = max_dd * 100.0
        out_results[tid, 3] = total_trades
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
    logger.info("    CPU will run at ~12-17% during compile. GPU will spike to 80%+ once done.")
    t0 = time.time()

    n_g, n_s, n_h = 1, gpu_flat_data["n_symbols"], gpu_flat_data["n_horizons"]
    total_threads  = n_g * n_s * n_h
    dummy_params = np.zeros((1, N_GENOME_PARAMS), dtype=np.float32)
    dummy_params[0, 0] = 20.0
    dummy_params[0, 2] = 1.5
    dummy_params[0, 3] = 2.5
    dummy_params[0, 4] = 78.0
    d_params = nb_cuda.to_device(dummy_params)
    d_out    = nb_cuda.device_array(total_threads * 4, dtype=np.float32)
    stream   = nb_cuda.stream()
    blocks   = max(1, (total_threads + CUDA_THREADS_PER_BLOCK - 1) // CUDA_THREADS_PER_BLOCK)
    try:
        _mega_backtest_kernel[blocks, CUDA_THREADS_PER_BLOCK, stream](
            gpu_flat_data["price_flat"],
            gpu_flat_data["sym_offsets"],
            gpu_flat_data["sym_lengths"],
            gpu_flat_data["horizon_bars"],
            d_params, d_out, n_g, n_s, n_h
        )
        stream.synchronize()
        elapsed = time.time() - t0
        logger.info(f"✅ CUDA kernel compiled & cached in {elapsed:.1f}s — GPU ready! 🚀")
    except Exception as e:
        logger.warning(f"Kernel warmup error (non-fatal): {e}")
    finally:
        del d_params, d_out
