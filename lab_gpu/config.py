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

# Genome parameter order for flat pack (29 parameters total)
N_GENOME_PARAMS = 29
GENOME_PARAM_ORDER = [
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
]

_STRAT_MAP_MB  = {"rsi_sniper": 0, "ema_cross": 1, "supertrend_momentum": 2,
                  "ichimoku_cloud": 3, "keltner_bounce": 4, "stoch_mfi_flow": 5,
                  "williams_mean_rev": 6, "donchian_breakout": 7,
                  "macd_momentum_surge": 8, "bollinger_squeeze_explosion": 9,
                  "parabolic_sar_vortex": 10, "fibonacci_golden_pullback": 11}
_MACRO_MAP_MB  = {"sma200_only": 0, "sma200_and_adx": 1, "none": 2}

BARSPERDAY = 48  # Named constant — 30m candles per day (24h × 2)
