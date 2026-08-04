"""
config.py — Configuration, constants, feature mappings, and logging for lab_gpu.
"""
import os
import sys
import logging
import multiprocessing
import warnings

# Configure console encoding
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Fixed parameter.*")
warnings.filterwarnings("ignore", message=".*out of range for distribution.*")
warnings.filterwarnings("ignore", message=".*Grid size.*")
try:
    from numba.core.errors import NumbaPerformanceWarning
    warnings.filterwarnings("ignore", category=NumbaPerformanceWarning)
except Exception:
    pass

from bot.config import SYMBOLS, DATABASE_URL_FUTURES, DATABASE_URL_SPOT

# Check if running in benchmark mode (disables Aiven DB writes and records timings)
BENCHMARK_MODE = os.environ.get("BENCHMARK_MODE", "false").lower() == "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [GPU-LAB] %(message)s")
logger = logging.getLogger("GPUSynthesizer")

# Silence noisy third-party libraries (especially Numba CUDA allocator dealloc logs)
for _noisy in ["numba", "numba.cuda", "numba.cuda.cudadrv", "numba.cuda.cudadrv.driver", "numba.core", "cupy", "optuna", "matplotlib", "urllib3", "asyncio"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ──────────────────────────────────────────────────────────
#  Constants & Paths
# ──────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "binace_backtest1y")
DASHBOARD_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data")

# Number of CPU workers for parallel Optuna (use all physical cores up to 8)
N_CPU_WORKERS = min(multiprocessing.cpu_count(), 8)

# GPU thread block size (tune for RTX 3070: 2560 CUDA cores)
CUDA_THREADS_PER_BLOCK = 128

# Mega-Batch Kernel Constants
GENOME_BATCH_SIZE = 4096

# Horizon bars for 1M, 3M, 6M, 1Y at 30-min candles (48 bars/day)
HORIZON_BARS = [30 * 48, 90 * 48, 180 * 48, 365 * 48]  # [1440, 4320, 8640, 17520]

# Feature column order for flat VRAM pack
N_FEATURES = 23
FEATURE_ORDER = [
    "close", "high", "low", "open", "vol",
    "sma200", "sma50", "atr", "rsi", "adx",
    "vol_sma", "bb_up", "ema10", "ema50", "st_dir",
    "mfi", "stoch_k", "cci", "williams",
    "keltner_low", "tenkan", "kijun", "donchian_high",
]

# Genome parameter order for flat pack (66 parameters total after Phase 1)
N_GENOME_PARAMS = 66
GENOME_PARAM_ORDER = [
    # Original 29
    "adx_trend_thresh", "vol_surge_mult", "sl_atr_mult", "tp_rr_mult", "gear1_rsi_sniper",
    "stoch_k_thresh", "mfi_bull_thresh", "cci_trend_thresh", "williams_r_thresh",
    "gear2_moonshot_trigger_pct", "gear2_moonshot_gap_pct",
    "gear3_trailing_trigger_pct", "gear3_trailing_gap_pct",
    "gear4_breakeven_trigger_pct", "gear4_breakeven_buffer_pct",
    "max_hold_bars", "sma200_buffer_pct", "volume_floor_mult",
    "rsi_surge_ceiling", "sl_hard_cap_pct", "tp_hard_cap_pct",
    "cooldown_bars_after_sl", "kelly_fraction_cap", "giant_candle_atr_mult",
    "use_dual_trend",       # bool → 1.0/0.0
    "require_green_candle", # bool → 1.0/0.0
    "strategy_type",        # str  → 0..11
    "macro_regime_filter",  # str  → 0..2
    "trend_strength_min_adx",
    
    # 37 New Threshold Genes (Phase 1)
    "rsi_hook_oversold", "rsi_reversal_exit_thresh", "bb_lower_buffer", "bb_upper_buffer",
    "macd_cross_lookback", "mfi_bear_thresh", "momentum_req_pos_hist", "supertrend_mult",
    "ichi_cloud_buffer", "keltner_mult", "cci_extreme_exit", "williams_r_exit",
    "rejection_wick_ratio", "vol_cap_rejection", "vol_cap_normal", "body_min_atr_pct",
    "high_low_spread_cap", "spot_step_trigger1", "spot_step_lock1", "spot_step_trigger2",
    "spot_step_lock2", "spot_step_trigger3", "spot_step_lock3", "gear1_sniper_slope",
    "gear1_sniper_max_rsi", "gear1_sniper_min_rsi", "gear2_moonshot_atr_mult",
    "gear3_trailing_atr_mult", "mom_tp_roe_thresh", "mom_tp_rsi_thresh", "mom_tp_drop_pct",
    "max_pos_alloc_pct", "min_trade_notional", "pyramid_scaling_mult", "sideways_max_adx",
    "adx_slope_check", "vol_exhaustion_mult"
]

_STRAT_MAP_MB  = {"rsi_sniper": 0, "ema_cross": 1, "supertrend_momentum": 2,
                  "ichi_cloud": 3, "keltner_bounce": 4, "stoch_mfi_diverge": 5,
                  "williams_overbought": 6, "donchian_breakout": 7, "macd_momentum": 8,
                  "bb_squeeze": 9, "adx_trend_rider": 10, "fibo_pullback": 11}

# Canonical Mapping for JSON export (Lab -> Live/Paper Engine)
REVERSE_STRAT_MAP = {v: k for k, v in _STRAT_MAP_MB.items()}

_MACRO_MAP_MB  = {"sma200_only": 0, "sma200_and_adx": 1, "none": 2}

BARSPERDAY = 48  # Named constant — 30m candles per day (24h × 2)
