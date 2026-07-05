"""
Evolutionary Strategy Synthesizer - GPU Edition (bot_strategy_synthesizer_gpu.py)
Lightweight wrapper preserving 100% backward compatibility for run_strategy_lab_gpu.bat
and regression tests by delegating to the modular lab_gpu/ package.
"""
import sys
from lab_gpu import *
from lab_gpu import (
    _apply_four_pillar_fitness,
    _vectorized_batch_compute_fitness,
    _pack_genomes_to_flat,
    _df_to_arrays,
    _build_symbol_arrays_for_cpu,
    _GPU_FLAT_DATA,
    _GPU_DEVICE_ARRAYS,
    save_lab_progress_gpu,
    logger,
    run_gpu_synthesizer_lab
)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("stop", "--stop", "-s"):
        save_lab_progress_gpu("stopped", 0, 0, 0.0, "Stopped by user", 0)
        logger.info("GPU Lab stopped.")
        sys.exit(0)
    trials = 30
    if len(sys.argv) > 1:
        try:
            trials = int(sys.argv[1])
        except ValueError:
            pass
    if trials <= 0:
        logger.info("🔥 INFINITE EVOLUTION MODE — Press Ctrl+C to stop.")
    run_gpu_synthesizer_lab(n_trials=trials)
