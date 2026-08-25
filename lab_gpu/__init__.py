"""
lab_gpu — Modular High-Performance GPU Strategy Synthesizer Package
"""
from .config import (
    SYMBOLS, N_CPU_WORKERS, GENOME_BATCH_SIZE, N_FEATURES,
    FEATURE_ORDER, HORIZON_BARS, GENOME_PARAM_ORDER, N_GENOME_PARAMS,
    logger, CACHE_DIR, DASHBOARD_DATA_DIR, DATABASE_URL_FUTURES, DATABASE_URL_SPOT
)
from .gpu_kernel import GPU_AVAILABLE, CUPY_AVAILABLE, warmup_mega_kernel
from .data_loader import (
    _load_and_cache_symbol, _df_to_arrays, _build_symbol_arrays_for_cpu,
    preload_all_symbols_to_gpu, _pack_symbols_to_flat_gpu, _GPU_FLAT_DATA,
    _GPU_DEVICE_ARRAYS
)
from .cpu_kernel import _cpu_mega_batch_fallback
from .fitness import (
    _apply_four_pillar_fitness, _pack_genomes_to_flat,
    _compute_fitness_from_matrix, _vectorized_batch_compute_fitness
)
from .evaluator import (
    _batch_gpu_backtest, _mega_batch_gpu_backtest, evaluate_genome_gpu
)
from .leaderboard_sync import (
    save_lab_progress_gpu, push_leaderboard_to_db_and_json_gpu,
    get_deduplicated_top10_gpu, StrategyLeaderboard, flush_sync_worker
)
from .evolution_engine import run_gpu_synthesizer_lab

__all__ = [
    "run_gpu_synthesizer_lab",
    "evaluate_genome_gpu",
    "_cpu_mega_batch_fallback",
    "_apply_four_pillar_fitness",
    "_vectorized_batch_compute_fitness",
    "_pack_genomes_to_flat",
    "_df_to_arrays",
    "GPU_AVAILABLE",
    "CUPY_AVAILABLE"
]
