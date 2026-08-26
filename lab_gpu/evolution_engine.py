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
import pandas as pd
from typing import Dict, List, Any

from .config import (
    logger,
    SYMBOLS,
    N_CPU_WORKERS,
    GENOME_BATCH_SIZE,
    DASHBOARD_DATA_DIR,
    BENCHMARK_MODE,
    GENOME_PARAM_ORDER,
    GENOME_SEARCH_SPACE,
    _STRAT_MAP_MB,
    _MACRO_MAP_MB,
)
from .gpu_kernel import GPU_AVAILABLE
from .data_loader import _load_and_cache_symbol, _df_to_arrays, preload_all_symbols_to_gpu, _pack_symbols_to_flat_gpu, _GPU_FLAT_DATA
from .evaluator import _mega_batch_gpu_backtest, evaluate_genome_gpu, _is_qualified_result
from .leaderboard_sync import save_lab_progress_gpu, push_leaderboard_to_db_and_json_gpu, get_deduplicated_top10_gpu, flush_sync_worker
from bot.strategy_contract import canonical_macro_regime, canonical_strategy_type

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna not installed. Running in standalone CPU mode without TPE optimization.")

def _schema_default(name: str) -> Any:
    spec = GENOME_SEARCH_SPACE[name]
    return spec[1][0] if spec[0] == "categorical" else (int(spec[1]) if spec[0] == "int" else float(spec[1]))


def _coerce_gene_value(name: str, value: Any) -> Any:
    """Normalize one genome value to the same type/range used by Optuna."""
    spec = GENOME_SEARCH_SPACE[name]
    kind = spec[0]
    if kind == "categorical":
        choices = spec[1]
        if value in choices:
            return value
        if name == "strategy_type":
            return canonical_strategy_type(value)
        if name == "macro_regime_filter":
            return canonical_macro_regime(value)
        raise ValueError(f"Unknown categorical gene {name}: {value!r}")

    low, high, step = spec[1], spec[2], float(spec[3])
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = float(low)
    if not np.isfinite(numeric):
        numeric = float(low)
    numeric = min(float(high), max(float(low), numeric))
    numeric = float(low) + round((numeric - float(low)) / step) * step
    numeric = min(float(high), max(float(low), numeric))
    return int(round(numeric)) if kind == "int" else round(numeric, 10)


def _mutate_genome(
    parent: Dict[str, Any],
    target_strategy: str,
    rng: Any = random,
    exploration: bool = False,
    defaults: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a bounded mutant without mutating the parent or fixed genes."""
    base = dict(defaults or {})
    base.update(parent or {})
    mutant = dict(base)

    for name in GENOME_PARAM_ORDER:
        mutant[name] = _coerce_gene_value(name, mutant.get(name, _schema_default(name)))

    float_rate = 0.30 if exploration else 0.10
    bool_rate = 0.20 if exploration else 0.05
    for name in GENOME_PARAM_ORDER:
        kind = GENOME_SEARCH_SPACE[name][0]
        if name in {"strategy_type", "macro_regime_filter"}:
            continue
        if kind in {"float", "int"} and rng.random() < float_rate:
            current = float(mutant[name])
            scale = rng.uniform(0.5, 1.5) if exploration else rng.uniform(0.9, 1.1)
            mutant[name] = _coerce_gene_value(name, current * scale)
        elif kind == "categorical" and rng.random() < bool_rate:
            choices = GENOME_SEARCH_SPACE[name][1]
            mutant[name] = not bool(mutant[name]) if set(choices) == {True, False} else choices[0]

    mutant["strategy_type"] = _coerce_gene_value("strategy_type", target_strategy)
    return mutant


def _is_usable_parent(result: Dict[str, Any]) -> bool:
    """Only complete, positive candidates may seed evolutionary mutations."""
    return (
        isinstance(result, dict)
        and isinstance(result.get("parameters"), dict)
        and _is_qualified_result(result)
    )


def _build_genome_from_trial(trial: Any) -> dict:
    """Build a genome from the same schema used by mutation and packing."""
    genome = {}
    for name in GENOME_PARAM_ORDER:
        spec = GENOME_SEARCH_SPACE[name]
        kind = spec[0]
        if kind == "categorical":
            genome[name] = trial.suggest_categorical(name, list(spec[1]))
        elif kind == "int":
            genome[name] = trial.suggest_int(name, int(spec[1]), int(spec[2]), step=int(spec[3]))
        else:
            genome[name] = trial.suggest_float(name, float(spec[1]), float(spec[2]), step=float(spec[3]))

    # Inject fixed canonical lookback windows for Live Strategy compatibility.
    genome.update({
        "macro_sma_fast_win": 50,
        "macro_sma_slow_win": 200,
        "ema_fast_win": 10,
        "ema_slow_win": 50,
        "macd_fast_win": 12,
        "macd_slow_win": 26,
        "macd_sig_win": 9,
        "supertrend_period": 10,
        "stoch_win": 14,
        "keltner_win": 20,
        "donchian_win": 20,
        "donchian_exit_win": 10,
        "cci_win": 20,
        "williams_win": 14,
    })
    return genome


def run_gpu_synthesizer_lab(n_trials: int = 30):
    """Main entry: Runs the GPU-accelerated Evolutionary Strategy Lab."""
    start_time = time.time()
    if n_trials <= 0:
        n_trials = None

    mode_str = "INFINITE (Unlimited)" if not n_trials else str(n_trials)
    engine_str = f"GPU CUDA (RTX 3070)" if GPU_AVAILABLE else f"CPU Multi-Core ({N_CPU_WORKERS} workers)"

    if BENCHMARK_MODE:
        save_lab_progress_gpu("running", 0, n_trials or 0, 0.0, "GPU Lab Initializing (Benchmark Mode)...", 0)
        logger.info("=" * 70)
        logger.info(f"  🏎️ BENCHMARK MODE ENABLED (DB Writes Disabled)")
    else:
        save_lab_progress_gpu("running", 0, n_trials or 0, 0.0, "GPU Lab Initializing...", 0)
    logger.info("=" * 70)
    logger.info(f"  🚀 GPU EVOLUTIONARY STRATEGY LAB (Bot Strategy Synthesizer GPU)")
    logger.info(f"  Engine : {engine_str}")
    logger.info(f"  Trials : {mode_str}")
    logger.info(f"  Workers: {N_CPU_WORKERS} Optuna parallel workers")
    logger.info(f"  Symbols: {len(SYMBOLS)} (20 Binance Futures)")
    logger.info("=" * 70)

    logger.info("Loading historical data from local cache (binace_backtest1y/)...")
    symbol_dfs: Dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        df = _load_and_cache_symbol(sym)
        if df is not None:
            symbol_dfs[sym] = df
            logger.info(f"  ✅ [{sym}] {len(df)} bars loaded")
            
    symbol_arrays: Dict[str, Dict[str, np.ndarray]] = {}
    if symbol_dfs:
        from .data_loader import align_symbols_to_arrays
        logger.info("Aligning all symbols to a universal time axis to prevent lookahead/causal bugs...")
        symbol_arrays = align_symbols_to_arrays(symbol_dfs)
        logger.info("Time alignment complete. Converted to GPU-ready float32 arrays.")
    
    if not symbol_arrays:
        logger.error("❌ No symbol data found! Run the CPU synthesizer first to download data.")
        save_lab_progress_gpu("stopped", 0, 0, 0.0, "No data - run CPU synthesizer first!", 0)
        return []

    logger.info(f"✅ {len(symbol_arrays)}/{len(SYMBOLS)} symbols loaded and ready!")

    if not OPTUNA_AVAILABLE:
        logger.error("Optuna not installed! pip install optuna")
        return []

    _optuna_storage = optuna.storages.InMemoryStorage()
    logger.info("Optuna storage: InMemoryStorage (High Speed, No DB Bloat)")

    import warnings
    warnings.filterwarnings("ignore", category=optuna.exceptions.ExperimentalWarning)

    study = optuna.create_study(
        study_name="alpha_genome_80genes_gpu_v1",
        storage=_optuna_storage,
        load_if_exists=True,
        direction="maximize",
        sampler=TPESampler(seed=42, n_startup_trials=30, multivariate=False),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1)
    )

    if symbol_arrays:
        # We skip individual preload_all_symbols_to_gpu because _GPU_FLAT_DATA handles the mega-batch.
        _pack_symbols_to_flat_gpu(symbol_arrays, GPU_AVAILABLE)

    leaderboard_map: Dict[str, Any] = {}
    lb_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
    historical_champions = []
    historical_candidates = []
    if os.path.exists(lb_path):
        try:
            with open(lb_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            historical_champions = saved.get("strategies", [])
            historical_candidates = [champ for champ in historical_champions if _is_usable_parent(champ)]
            valid_champs = [champ["parameters"] for champ in historical_candidates]
            if valid_champs:
                logger.info(f"⚡ Re-evaluating {len(valid_champs)} qualified historical champions against active Phase 31 profit hurdles...")
                reeval_results = _mega_batch_gpu_backtest(valid_champs)
                for idx, res in enumerate(reeval_results):
                    if res.get("full_evaluated", False):
                        champ_copy = historical_candidates[idx].copy()
                        champ_copy.update(res)
                        leaderboard_map[f"hist_{idx}"] = champ_copy
                logger.info(f"🧠 {len(leaderboard_map)}/{len(valid_champs)} historical Alpha champions survived Phase 31 rules!")
            else:
                logger.info("🧠 No qualified historical candidates available; starting from the active search schema.")
        except Exception as e:
            logger.warning(f"Could not load historical leaderboard: {e}")

    best_so_far_score = max(
        [v.get("fitness_score", -1e9) for v in leaderboard_map.values() if v.get("full_evaluated", False)]
        or [-1e9]
    )
    best_so_far_name  = "Historical Champion"
    best_screen_score = -1e9
    best_screen_name = "No complete evaluation yet"

    enqueued = 0
    for champ in historical_candidates:
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
    validated_winners = 0
    screened_count = 0
    full_evaluated_count = 0
    try:
        while True:
            if n_trials and completed >= n_trials:
                break
            if os.path.exists("stop_lab.txt"):
                logger.info("Graceful stop signal (stop_lab.txt) detected. Shutting down...")
                try: os.remove("stop_lab.txt")
                except: pass
                break

            if USE_MEGA_BATCH:
                batch_size = min(GENOME_BATCH_SIZE, (n_trials - completed) if n_trials else GENOME_BATCH_SIZE)
                
                with lock:
                    n_tpe = min(64, batch_size)
                    optuna_trials = [study.ask() for _ in range(n_tpe)]
                    genomes = [_build_genome_from_trial(t) for t in optuna_trials]

                    n_mutants = batch_size - len(genomes)
                    if n_mutants > 0:
                        elites_by_strat = {}
                        for res in leaderboard_map.values():
                            if _is_usable_parent(res):
                                p = res["parameters"]
                                st = p.get("strategy_type", "rsi_sniper")
                                elites_by_strat.setdefault(st, []).append(p)
                        
                        fallback_parent = genomes[0]
                        STRATEGY_TYPES = list(_STRAT_MAP_MB.keys())

                        for m_idx in range(n_mutants):
                            is_exploration = random.random() < 0.25
                            target_strat = random.choice(STRATEGY_TYPES)
                            
                            if is_exploration or target_strat not in elites_by_strat:
                                parent = fallback_parent
                            else:
                                parent = random.choice(elites_by_strat[target_strat])
                            mutant = _mutate_genome(
                                parent,
                                target_strategy=target_strat,
                                rng=random,
                                exploration=is_exploration,
                                defaults=fallback_parent,
                            )
                            genomes.append(mutant)

                paired_tpe = [(t, g) for t, g in zip(optuna_trials, genomes[:n_tpe])]
                paired_mut = [(None, g) for g in genomes[n_tpe:]]
                all_paired = paired_tpe + paired_mut
                all_paired.sort(key=lambda pair: str(pair[1].get("strategy_type", "")))
                
                sorted_genomes = [pair[1] for pair in all_paired]
                force_full_indices = [
                    idx for idx, pair in enumerate(all_paired) if pair[0] is not None
                ]
                batch_results = _mega_batch_gpu_backtest(
                    sorted_genomes,
                    force_full_indices=force_full_indices,
                )

                with lock:
                    m_idx = 0
                    for (trial, genome), res in zip(all_paired, batch_results):
                        st_name = str(genome.get("strategy_type", "rsi")).upper()
                        res = {**res, "parameters": genome}
                        
                        if trial is not None:
                            res["name"] = f"[{st_name}] Evolved Alpha TPE #{trial.number}"
                            leaderboard_map[f"trial_{trial.number}"] = res
                            study.tell(trial, float(res.get("search_score", res.get("fitness_score", -1e9))))
                        else:
                            mut_id = completed + n_tpe + m_idx + 1
                            m_idx += 1
                            res["name"] = f"[{st_name}] Evolved Alpha Mutant #{mut_id}"
                            leaderboard_map[f"mutant_{mut_id}"] = res
                            
                        screen_value = res.get("screening_score")
                        screen_score = float(screen_value) if screen_value is not None else float(res.get("search_score", -1e9))
                        if screen_score > best_screen_score:
                            best_screen_score = screen_score
                            best_screen_name = res["name"]

                        if res.get("full_evaluated", False) and res.get("fitness_score", -1e9) > best_so_far_score:
                            best_so_far_score = res["fitness_score"]
                            best_so_far_name  = res["name"]
                        if res.get("full_evaluated", False):
                            full_evaluated_count += 1

                        # KPI: only complete, finite candidates with positive fitness qualify.
                        if _is_qualified_result(res):
                            validated_winners += 1

                    if len(leaderboard_map) > 50:
                        top_keys = sorted(
                            leaderboard_map.keys(),
                            key=lambda k: (
                                int(leaderboard_map[k].get("full_evaluated", False)),
                                int(leaderboard_map[k].get("qualified", False)),
                                leaderboard_map[k].get("fitness_score", -1e9),
                            ),
                            reverse=True,
                        )[:50]
                        leaderboard_map = {k: leaderboard_map[k] for k in top_keys}

                completed += batch_size
                batch_idx += 1
                screened_count += batch_size
                elapsed = int(time.time() - start_time)
                elapsed_hrs = elapsed / 3600.0 if elapsed > 0 else 0.0001
                rate = validated_winners / elapsed_hrs
                
                logger.info(
                    f"[Batch {batch_idx}] {completed} genomes | "
                    f"Screened: {screened_count} | Full: {full_evaluated_count} | "
                    f"Qualified: {validated_winners} ({rate:.1f}/hr) | "
                    f"Best full: {best_so_far_score:.2f} | Best screen: {best_screen_score:.2f} | "
                    f"Elapsed: {elapsed//60}m{elapsed%60}s"
                )
                if not BENCHMARK_MODE:
                    save_lab_progress_gpu(
                        "running", completed, n_trials or 0,
                        best_so_far_score if full_evaluated_count else best_screen_score,
                        best_so_far_name if full_evaluated_count else best_screen_name,
                        elapsed,
                        total_db_trials=completed,
                        best_full_score=best_so_far_score,
                        best_screen_score=best_screen_score,
                        screened_count=screened_count,
                        full_evaluated_count=full_evaluated_count,
                        qualified_count=validated_winners,
                    )

                if batch_idx % 5 == 0:
                    try:
                        with lock:
                            top_10 = get_deduplicated_top10_gpu(leaderboard_map)
                        if not BENCHMARK_MODE:
                            push_leaderboard_to_db_and_json_gpu(top_10)
                    except Exception as e:
                        logger.error(f"Leaderboard sync error: {e}")

            else:
                def objective(trial):
                    nonlocal best_so_far_score, best_so_far_name, best_screen_score, best_screen_name
                    nonlocal validated_winners, screened_count, full_evaluated_count
                    cur_step = max(1, (trial.number - session_start_id) + 1)
                    genome = _build_genome_from_trial(trial)

                    # Pruning disabled for shared portfolio

                    full_res = evaluate_genome_gpu(symbol_arrays, genome)
                    st_name = str(genome.get("strategy_type", "rsi")).upper()
                    full_res = {
                        **full_res,
                        "name": f"[{st_name}] Evolved Alpha TPE #{trial.number}",
                        "parameters": genome,
                    }

                    with lock:
                        leaderboard_map[f"trial_{trial.number}"] = full_res
                        screen_value = full_res.get("screening_score")
                        screen_score = float(screen_value) if screen_value is not None else float(full_res.get("search_score", -1e9))
                        best_screen_is_new = screen_score > best_screen_score
                        if best_screen_is_new:
                            best_screen_score = screen_score
                            best_screen_name = full_res["name"]
                        full_evaluated_count += int(full_res.get("full_evaluated", False))
                        screened_count += 1
                        is_new_best = full_res.get("full_evaluated", False) and full_res["fitness_score"] > best_so_far_score
                        if is_new_best:
                            best_so_far_score = full_res["fitness_score"]
                            best_so_far_name  = full_res["name"]
                        if _is_qualified_result(full_res):
                            validated_winners += 1

                    elapsed = int(time.time() - start_time)
                    if not BENCHMARK_MODE:
                        save_lab_progress_gpu("running", cur_step, n_trials or 0,
                                              best_so_far_score if full_evaluated_count else best_screen_score,
                                              best_so_far_name if full_evaluated_count else best_screen_name,
                                              elapsed,
                                              total_db_trials=trial.number + 1,
                                              best_full_score=best_so_far_score,
                                              best_screen_score=best_screen_score,
                                              screened_count=screened_count,
                                              full_evaluated_count=full_evaluated_count,
                                              qualified_count=validated_winners)
                    if trial.number % 10 == 0 or is_new_best:
                        try:
                            with lock:
                                top_10 = get_deduplicated_top10_gpu(leaderboard_map)
                            if not BENCHMARK_MODE:
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
    if not BENCHMARK_MODE:
        push_leaderboard_to_db_and_json_gpu(top_10, force=True)
    elapsed = int(time.time() - start_time)
    best_item = top_10[0] if top_10 else {}
    best_val = best_so_far_score if full_evaluated_count else best_screen_score
    best_display_name = best_so_far_name if full_evaluated_count else best_screen_name
    final_status = "stopped" if not n_trials else "completed"
    if not BENCHMARK_MODE:
        save_lab_progress_gpu(final_status, n_trials or len(leaderboard_map), n_trials or 0,
                               best_val, best_display_name, elapsed,
                               best_full_score=best_so_far_score,
                               best_screen_score=best_screen_score,
                               screened_count=screened_count,
                               full_evaluated_count=full_evaluated_count,
                               qualified_count=validated_winners)
        flush_sync_worker()
    logger.info(f"GPU Lab finished! {completed} genomes evaluated in {elapsed//60}m {elapsed%60}s ({len(leaderboard_map)} retained)")
    logger.info(f"Best full: {best_display_name} | Score: {best_val:.2f}")
    return top_10
