"""
evolution_engine.py — The evolutionary algorithm engine (Optuna TPE + genetic mutation/crossover loop).
"""
import os
import sys
import time
import json
import random
import threading
import numpy as np
from typing import Dict, List, Any

from .config import logger, SYMBOLS, N_CPU_WORKERS, GENOME_BATCH_SIZE, DASHBOARD_DATA_DIR
from .gpu_kernel import GPU_AVAILABLE
from .data_loader import _load_and_cache_symbol, _df_to_arrays, preload_all_symbols_to_gpu, _pack_symbols_to_flat_gpu, _GPU_FLAT_DATA
from .evaluator import _mega_batch_gpu_backtest, _cpu_eval_from_arrays, evaluate_genome_gpu
from .leaderboard_sync import save_lab_progress_gpu, push_leaderboard_to_db_and_json_gpu, get_deduplicated_top10_gpu

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna not installed. Running in standalone CPU mode without TPE optimization.")

def _build_genome_from_trial(trial) -> Dict[str, Any]:
    return {
        "strategy_type": trial.suggest_categorical("strategy_type", ["rsi_sniper","ema_cross","supertrend_momentum","ichimoku_cloud","keltner_bounce","stoch_mfi_flow","williams_mean_rev","donchian_breakout","macd_momentum_surge","bollinger_squeeze_explosion","parabolic_sar_vortex","fibonacci_golden_pullback"]),
        "adx_trend_thresh":   trial.suggest_float("adx_trend_thresh", 15.0, 35.0, step=1.0),
        "use_dual_trend":     trial.suggest_categorical("use_dual_trend", [True, False]),
        "vol_surge_mult":     trial.suggest_float("vol_surge_mult", 1.1, 3.0, step=0.1),
        "sl_atr_mult":        trial.suggest_float("sl_atr_mult", 1.0, 3.0, step=0.1),
        "tp_rr_mult":         trial.suggest_float("tp_rr_mult", 1.5, 4.5, step=0.2),
        "gear1_rsi_sniper":   trial.suggest_float("gear1_rsi_sniper", 68.0, 86.0, step=1.0),
        "stoch_k_thresh":     trial.suggest_float("stoch_k_thresh", 65.0, 88.0, step=1.0),
        "mfi_bull_thresh":    trial.suggest_float("mfi_bull_thresh", 30.0, 60.0, step=2.0),
        "cci_trend_thresh":   trial.suggest_float("cci_trend_thresh", -50.0, 100.0, step=10.0),
        "williams_r_thresh":  trial.suggest_float("williams_r_thresh", -90.0, -66.0, step=2.0),
        "gear2_moonshot_trigger_pct": trial.suggest_float("gear2_moonshot_trigger_pct", 0.015, 0.04, step=0.005),
        "gear2_moonshot_gap_pct":     trial.suggest_float("gear2_moonshot_gap_pct", 0.003, 0.01, step=0.001),
        "gear3_trailing_trigger_pct": trial.suggest_float("gear3_trailing_trigger_pct", 0.008, 0.024, step=0.002),
        "gear3_trailing_gap_pct":     trial.suggest_float("gear3_trailing_gap_pct", 0.005, 0.015, step=0.001),
        "gear4_breakeven_trigger_pct":trial.suggest_float("gear4_breakeven_trigger_pct", 0.004, 0.012, step=0.001),
        "gear4_breakeven_buffer_pct": trial.suggest_float("gear4_breakeven_buffer_pct", 0.0005, 0.003, step=0.0005),
        "max_hold_bars":      trial.suggest_int("max_hold_bars", 12, 72, step=6),
        "vol_exhaustion_mult":trial.suggest_float("vol_exhaustion_mult", 0.3, 0.8, step=0.1),
        "macro_sma_fast_win": trial.suggest_int("macro_sma_fast_win", 30, 70, step=10),
        "macro_sma_slow_win": trial.suggest_int("macro_sma_slow_win", 150, 250, step=25),
        "sma200_buffer_pct":  trial.suggest_float("sma200_buffer_pct", 0.985, 1.015, step=0.005),
        "adx_slope_check":    trial.suggest_categorical("adx_slope_check", [True, False]),
        "volume_floor_mult":  trial.suggest_float("volume_floor_mult", 0.5, 1.2, step=0.1),
        "rsi_surge_ceiling":  trial.suggest_float("rsi_surge_ceiling", 76.0, 90.0, step=2.0),
        "rsi_hook_oversold":  trial.suggest_float("rsi_hook_oversold", 26.0, 48.0, step=2.0),
        "rsi_reversal_exit_thresh": trial.suggest_float("rsi_reversal_exit_thresh", 56.0, 74.0, step=2.0),
        "bb_lower_buffer":    trial.suggest_float("bb_lower_buffer", 0.99, 1.04, step=0.01),
        "bb_upper_buffer":    trial.suggest_float("bb_upper_buffer", 0.97, 1.01, step=0.01),
        "ema_fast_win":       trial.suggest_int("ema_fast_win", 5, 15, step=2),
        "ema_slow_win":       trial.suggest_int("ema_slow_win", 20, 60, step=5),
        "macd_fast_win":      trial.suggest_int("macd_fast_win", 8, 16, step=2),
        "macd_slow_win":      trial.suggest_int("macd_slow_win", 20, 32, step=2),
        "macd_sig_win":       trial.suggest_int("macd_sig_win", 5, 11, step=2),
        "macd_cross_lookback":trial.suggest_int("macd_cross_lookback", 3, 15, step=2),
        "mfi_bear_thresh":    trial.suggest_float("mfi_bear_thresh", 70.0, 90.0, step=5.0),
        "momentum_req_pos_hist": trial.suggest_categorical("momentum_req_pos_hist", [True, False]),
        "supertrend_period":  trial.suggest_int("supertrend_period", 7, 15, step=2),
        "supertrend_mult":    trial.suggest_float("supertrend_mult", 2.0, 4.5, step=0.5),
        "ichi_cloud_buffer":  trial.suggest_float("ichi_cloud_buffer", 0.996, 1.004, step=0.002),
        "stoch_win":          trial.suggest_int("stoch_win", 10, 20, step=2),
        "keltner_win":        trial.suggest_int("keltner_win", 14, 30, step=4),
        "keltner_mult":       trial.suggest_float("keltner_mult", 1.5, 3.0, step=0.5),
        "donchian_win":       trial.suggest_int("donchian_win", 15, 40, step=5),
        "donchian_exit_win":  trial.suggest_int("donchian_exit_win", 5, 20, step=5),
        "cci_win":            trial.suggest_int("cci_win", 14, 30, step=4),
        "cci_extreme_exit":   trial.suggest_float("cci_extreme_exit", 150.0, 250.0, step=25.0),
        "williams_win":       trial.suggest_int("williams_win", 10, 20, step=2),
        "williams_r_exit":    trial.suggest_float("williams_r_exit", -25.0, -5.0, step=5.0),
        "giant_candle_atr_mult": trial.suggest_float("giant_candle_atr_mult", 1.5, 3.5, step=0.5),
        "rejection_wick_ratio":  trial.suggest_float("rejection_wick_ratio", 0.25, 0.55, step=0.05),
        "vol_cap_rejection":  trial.suggest_float("vol_cap_rejection", 3.0, 6.0, step=0.5),
        "vol_cap_normal":     trial.suggest_float("vol_cap_normal", 2.0, 3.5, step=0.5),
        "body_min_atr_pct":   trial.suggest_float("body_min_atr_pct", 0.1, 0.5, step=0.1),
        "require_green_candle": trial.suggest_categorical("require_green_candle", [True, False]),
        "high_low_spread_cap":trial.suggest_float("high_low_spread_cap", 3.0, 6.0, step=0.5),
        "sl_hard_cap_pct":    trial.suggest_float("sl_hard_cap_pct", 0.02, 0.06, step=0.01),
        "tp_hard_cap_pct":    trial.suggest_float("tp_hard_cap_pct", 0.05, 0.15, step=0.02),
        "spot_step_trigger1": trial.suggest_float("spot_step_trigger1", 0.015, 0.03, step=0.005),
        "spot_step_lock1":    trial.suggest_float("spot_step_lock1", 0.005, 0.015, step=0.005),
        "spot_step_trigger2": trial.suggest_float("spot_step_trigger2", 0.035, 0.055, step=0.01),
        "spot_step_lock2":    trial.suggest_float("spot_step_lock2", 0.02, 0.035, step=0.005),
        "spot_step_trigger3": trial.suggest_float("spot_step_trigger3", 0.06, 0.09, step=0.01),
        "spot_step_lock3":    trial.suggest_float("spot_step_lock3", 0.045, 0.07, step=0.005),
        "gear1_sniper_slope": trial.suggest_float("gear1_sniper_slope", 1.0, 2.5, step=0.5),
        "gear1_sniper_max_rsi": trial.suggest_float("gear1_sniper_max_rsi", 80.0, 92.0, step=2.0),
        "gear1_sniper_min_rsi": trial.suggest_float("gear1_sniper_min_rsi", 10.0, 22.0, step=3.0),
        "gear2_moonshot_atr_mult": trial.suggest_float("gear2_moonshot_atr_mult", 1.5, 3.0, step=0.5),
        "gear3_trailing_atr_mult": trial.suggest_float("gear3_trailing_atr_mult", 1.0, 2.0, step=0.2),
        "mom_tp_roe_thresh":  trial.suggest_float("mom_tp_roe_thresh", 0.025, 0.05, step=0.005),
        "mom_tp_rsi_thresh":  trial.suggest_float("mom_tp_rsi_thresh", 72.0, 84.0, step=2.0),
        "mom_tp_drop_pct":    trial.suggest_float("mom_tp_drop_pct", 0.0015, 0.0045, step=0.001),
        "kelly_fraction_cap": trial.suggest_float("kelly_fraction_cap", 0.15, 0.40, step=0.05),
        "max_pos_alloc_pct":  trial.suggest_float("max_pos_alloc_pct", 0.10, 0.25, step=0.05),
        "min_trade_notional": trial.suggest_float("min_trade_notional", 5.0, 15.0, step=2.5),
        "cooldown_bars_after_sl": trial.suggest_int("cooldown_bars_after_sl", 0, 6, step=2),
        "pyramid_scaling_mult": trial.suggest_float("pyramid_scaling_mult", 0.5, 1.5, step=0.2),
        "trend_strength_min_adx": trial.suggest_float("trend_strength_min_adx", 10.0, 25.0, step=2.5),
        "sideways_max_adx":   trial.suggest_float("sideways_max_adx", 20.0, 35.0, step=2.5),
        "macro_regime_filter": trial.suggest_categorical("macro_regime_filter", ["sma200_only","sma200_and_adx","none"])
    }

def run_gpu_synthesizer_lab(n_trials: int = 30):
    """Main entry: Runs the GPU-accelerated Evolutionary Strategy Lab."""
    start_time = time.time()
    if n_trials <= 0:
        n_trials = None

    mode_str = "INFINITE (Unlimited)" if not n_trials else str(n_trials)
    engine_str = f"GPU CUDA (RTX 3070)" if GPU_AVAILABLE else f"CPU Multi-Core ({N_CPU_WORKERS} workers)"

    save_lab_progress_gpu("running", 0, n_trials or 0, 0.0, "GPU Lab Initializing...", 0)
    logger.info("=" * 70)
    logger.info(f"  🚀 GPU EVOLUTIONARY STRATEGY LAB (Bot Strategy Synthesizer GPU)")
    logger.info(f"  Engine : {engine_str}")
    logger.info(f"  Trials : {mode_str}")
    logger.info(f"  Workers: {N_CPU_WORKERS} Optuna parallel workers")
    logger.info(f"  Symbols: {len(SYMBOLS)} (20 Binance Futures)")
    logger.info("=" * 70)

    logger.info("Loading historical data from local cache (binace_backtest1y/)...")
    symbol_arrays: Dict[str, Dict[str, np.ndarray]] = {}
    for sym in SYMBOLS:
        df = _load_and_cache_symbol(sym)
        if df is not None:
            symbol_arrays[sym] = _df_to_arrays(df)
            logger.info(f"  ✅ [{sym}] {len(df)} bars loaded → GPU-ready float32 arrays")
    
    if not symbol_arrays:
        logger.error("❌ No symbol data found! Run the CPU synthesizer first to download data.")
        save_lab_progress_gpu("stopped", 0, 0, 0.0, "No data - run CPU synthesizer first!", 0)
        return []

    logger.info(f"✅ {len(symbol_arrays)}/{len(SYMBOLS)} symbols loaded and ready!")

    if not OPTUNA_AVAILABLE:
        logger.error("Optuna not installed! pip install optuna")
        return []

    _optuna_storage = optuna.storages.InMemoryStorage()
    logger.info(f"Optuna storage: InMemoryStorage (lightning-fast 0.001s Ask-and-Tell loop)")

    import warnings
    warnings.filterwarnings("ignore", category=optuna.exceptions.ExperimentalWarning)

    study = optuna.create_study(
        study_name="alpha_genome_80genes_gpu_v1",
        storage=_optuna_storage,
        load_if_exists=True,
        direction="maximize",
        sampler=TPESampler(seed=None, n_startup_trials=30, multivariate=False),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1)
    )

    if GPU_AVAILABLE:
        preload_all_symbols_to_gpu(symbol_arrays, GPU_AVAILABLE)
        _pack_symbols_to_flat_gpu(symbol_arrays, GPU_AVAILABLE)

    leaderboard_map: Dict[str, Any] = {}
    lb_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
    historical_champions = []
    if os.path.exists(lb_path):
        try:
            with open(lb_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            historical_champions = saved.get("strategies", [])
            valid_champs = [champ["parameters"] for champ in historical_champions if "parameters" in champ and isinstance(champ["parameters"], dict)]
            if valid_champs:
                logger.info(f"⚡ Re-evaluating {len(valid_champs)} historical champions against active Phase 31 profit hurdles...")
                reeval_results = _mega_batch_gpu_backtest(valid_champs)
                for idx, res in enumerate(reeval_results):
                    if res.get("fitness_score", -9999) > 0.0:
                        champ_copy = historical_champions[idx].copy()
                        champ_copy["fitness_score"] = res["fitness_score"]
                        champ_copy.update({k: res[k] for k in ["net_profit_1y", "net_profit_6m", "net_profit_3m", "net_profit_1m", "win_rate_1y", "max_dd_1y", "total_trades_1y"] if k in res})
                        leaderboard_map[f"hist_{idx}"] = champ_copy
                logger.info(f"🧠 {len(leaderboard_map)}/{len(valid_champs)} historical Alpha champions survived Phase 31 rules!")
        except Exception as e:
            logger.warning(f"Could not load historical leaderboard: {e}")

    best_so_far_score = max((v.get("fitness_score", -9999) for v in leaderboard_map.values()), default=0.0)
    best_so_far_name  = "Historical Champion"

    enqueued = 0
    for champ in historical_champions:
        params = champ.get("parameters")
        if params and isinstance(params, dict) and len(params) >= 70:
            try:
                study.enqueue_trial(params, skip_if_exists=True)
                enqueued += 1
            except Exception:
                pass
    if enqueued:
        logger.info(f"⚡ Enqueued {enqueued} historical champions into GPU Optuna study!")

    session_start_id = len(study.trials)
    lock = threading.Lock()

    USE_MEGA_BATCH = GPU_AVAILABLE and bool(_GPU_FLAT_DATA)
    if USE_MEGA_BATCH:
        logger.info(f"🚀 MEGA-BATCH MODE: {GENOME_BATCH_SIZE} genomes per kernel call (RTX 3070)")
    else:
        logger.info(f"🧬 Standard mode: 1 genome per trial, {N_CPU_WORKERS} parallel workers")

    completed = 0
    batch_idx = 0
    try:
        while True:
            if n_trials is not None and completed >= n_trials:
                break

            if USE_MEGA_BATCH:
                remaining = (n_trials - completed) if n_trials else GENOME_BATCH_SIZE
                batch_size = min(GENOME_BATCH_SIZE, remaining)
                n_tpe = min(32, batch_size)
                optuna_trials = [study.ask() for _ in range(n_tpe)]
                genomes = [_build_genome_from_trial(t) for t in optuna_trials]

                n_mutants = batch_size - len(genomes)
                if n_mutants > 0:
                    elites = [res["parameters"] for res in leaderboard_map.values() if isinstance(res, dict) and "parameters" in res]
                    if not elites:
                        elites = [g for g in genomes]
                    if not elites and historical_champions:
                        elites = [c["parameters"] for c in historical_champions if isinstance(c, dict) and "parameters" in c]
                    float_keys = [k for k, v in genomes[0].items() if isinstance(v, float)]
                    int_keys   = [k for k, v in genomes[0].items() if isinstance(v, int) and not isinstance(v, bool)]
                    bool_keys  = [k for k, v in genomes[0].items() if isinstance(v, bool)]
                    for m_idx in range(n_mutants):
                        parent = random.choice(elites) if elites else genomes[0]
                        mutant = parent.copy()
                        for k in float_keys:
                            if random.random() < 0.15:
                                val = parent[k] * random.uniform(0.85, 1.15)
                                if k == "kelly_fraction_cap":
                                    val = max(0.20, min(0.40, val))
                                elif "thresh" in k or "rsi" in k or "stoch" in k or "mfi" in k:
                                    if "williams" in k or "cci" in k:
                                        val = max(-300.0, min(300.0, val))
                                    else:
                                        val = max(5.0, min(95.0, val))
                                mutant[k] = round(val, 5)
                        for k in int_keys:
                            if random.random() < 0.15:
                                mutant[k] = max(1, int(parent[k] * random.uniform(0.85, 1.15)))
                        for k in bool_keys:
                            if random.random() < 0.05:
                                mutant[k] = not parent[k]
                        mutant["strategy_type"] = parent.get("strategy_type", "rsi_sniper")
                        genomes.append(mutant)

                batch_results = _mega_batch_gpu_backtest(genomes)

                with lock:
                    for t, genome, res in zip(optuna_trials, genomes[:n_tpe], batch_results[:n_tpe]):
                        st_name = str(genome.get("strategy_type", "rsi")).upper()
                        res["name"] = f"[{st_name}] Evolved Alpha TPE #{t.number}"
                        res["parameters"] = genome
                        leaderboard_map[f"trial_{t.number}"] = res
                        study.tell(t, res["fitness_score"])
                        if res["fitness_score"] > best_so_far_score:
                            best_so_far_score = res["fitness_score"]
                            best_so_far_name  = res["name"]

                    for m_idx, (genome, res) in enumerate(zip(genomes[n_tpe:], batch_results[n_tpe:])):
                        st_name = str(genome.get("strategy_type", "rsi")).upper()
                        mut_id = completed + n_tpe + m_idx + 1
                        res["name"] = f"[{st_name}] Evolved Alpha Mutant #{mut_id}"
                        res["parameters"] = genome
                        leaderboard_map[f"mutant_{mut_id}"] = res
                        if res["fitness_score"] > best_so_far_score:
                            best_so_far_score = res["fitness_score"]
                            best_so_far_name  = res["name"]

                    if len(leaderboard_map) > 50:
                        top_keys = sorted(leaderboard_map.keys(), key=lambda k: leaderboard_map[k].get("fitness_score", 0.0), reverse=True)[:50]
                        leaderboard_map = {k: leaderboard_map[k] for k in top_keys}

                completed += batch_size
                batch_idx += 1
                elapsed = int(time.time() - start_time)
                logger.info(
                    f"[Batch {batch_idx}] {completed} genomes done | "
                    f"Best: {best_so_far_score:.2f} ({best_so_far_name[:40]}) | "
                    f"Elapsed: {elapsed//60}m{elapsed%60}s"
                )
                save_lab_progress_gpu(
                    "running", completed, n_trials or 0,
                    best_so_far_score, best_so_far_name, elapsed,
                    total_db_trials=completed
                )

                if batch_idx % 5 == 0 or best_so_far_score > (batch_idx - 1) * 0:
                    try:
                        with lock:
                            top_10 = get_deduplicated_top10_gpu(leaderboard_map)
                        push_leaderboard_to_db_and_json_gpu(top_10)
                    except Exception as e:
                        logger.error(f"Leaderboard sync error: {e}")

            else:
                def objective(trial):
                    nonlocal best_so_far_score, best_so_far_name
                    cur_step = max(1, (trial.number - session_start_id) + 1)
                    genome = _build_genome_from_trial(trial)

                    p_1m_list = []
                    for sym, arrays in symbol_arrays.items():
                        bars = 30 * 48
                        if arrays["close"].shape[0] < bars: continue
                        stats = _cpu_eval_from_arrays(arrays, genome, bars)
                        p_1m_list.append(stats["net_profit_pct"])
                    p_1m = float(np.mean(p_1m_list)) if p_1m_list else 0.0
                    trial.report(p_1m, step=1)
                    if trial.should_prune():
                        elapsed = int(time.time() - start_time)
                        save_lab_progress_gpu("running", cur_step, n_trials or 0,
                                              best_so_far_score, best_so_far_name, elapsed,
                                              total_db_trials=trial.number + 1)
                        raise optuna.TrialPruned()

                    full_res = evaluate_genome_gpu(symbol_arrays, genome)
                    st_name = str(genome.get("strategy_type", "rsi")).upper()
                    full_res["name"] = f"[{st_name}] Evolved Alpha TPE #{trial.number}"
                    full_res["parameters"] = genome

                    with lock:
                        leaderboard_map[f"trial_{trial.number}"] = full_res
                        is_new_best = full_res["fitness_score"] > best_so_far_score
                        if is_new_best:
                            best_so_far_score = full_res["fitness_score"]
                            best_so_far_name  = full_res["name"]

                    elapsed = int(time.time() - start_time)
                    save_lab_progress_gpu("running", cur_step, n_trials or 0,
                                          best_so_far_score, best_so_far_name, elapsed,
                                          total_db_trials=trial.number + 1)
                    if trial.number % 10 == 0 or is_new_best:
                        try:
                            with lock:
                                top_10 = get_deduplicated_top10_gpu(leaderboard_map)
                            push_leaderboard_to_db_and_json_gpu(top_10)
                        except Exception as e:
                            logger.error(f"Leaderboard sync error: {e}")
                    return full_res["fitness_score"]

                try:
                    study.optimize(
                        objective,
                        n_trials=n_trials,
                        n_jobs=N_CPU_WORKERS,
                        show_progress_bar=True
                    )
                except (KeyboardInterrupt, SystemExit):
                    logger.info("Interrupted.")
                break

    except (KeyboardInterrupt, SystemExit):
        logger.info("GPU Lab interrupted by user. Saving final leaderboard...")

    with lock:
        top_10 = get_deduplicated_top10_gpu(leaderboard_map)
    push_leaderboard_to_db_and_json_gpu(top_10)
    elapsed = int(time.time() - start_time)
    best_item = top_10[0] if top_10 else {}
    try:
        best_val = study.best_value
    except Exception:
        best_val = best_item.get("fitness_score", 0.0)
    final_status = "stopped" if not n_trials else "completed"
    save_lab_progress_gpu(final_status, n_trials or len(leaderboard_map), n_trials or 0,
                           best_val, best_item.get("name", "N/A"), elapsed)
    logger.info(f"GPU Lab finished! {len(leaderboard_map)} genomes evaluated in {elapsed//60}m {elapsed%60}s")
    logger.info(f"Best: {best_item.get('name', 'N/A')} | Score: {best_val:.2f}")
    return top_10
