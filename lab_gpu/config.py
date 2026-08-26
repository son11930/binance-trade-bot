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
from bot.strategy_contract import STRATEGY_MAP, MACRO_REGIME_MAP

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

# Cheap-screen policy. The screen is a ranking signal only; candidates in the
# rescue set are still evaluated on all horizons before they can qualify.
SCREENING_TOP_K = 64
SCREENING_MIN_1M_PROFIT = -5.0
SCREENING_MIN_3M_PROFIT = -2.0
SCREENING_FITNESS_BASE = -999.0

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

_STRAT_MAP_MB = dict(STRATEGY_MAP)

# Canonical Mapping for JSON export (Lab -> Live/Paper Engine)
REVERSE_STRAT_MAP = {v: k for k, v in _STRAT_MAP_MB.items()}

_MACRO_MAP_MB = dict(MACRO_REGIME_MAP)

# Single typed source of truth for the active Optuna schema and evolutionary
# mutation bounds. Tuple formats are:
#   ("float"|"int", low, high, step)
#   ("categorical", (value, ...))
GENOME_SEARCH_SPACE = {
    "adx_trend_thresh": ("float", 15.0, 35.0, 1.0),
    "vol_surge_mult": ("float", 1.1, 3.0, 0.1),
    "sl_atr_mult": ("float", 1.0, 3.0, 0.1),
    "tp_rr_mult": ("float", 1.5, 4.5, 0.2),
    "gear1_rsi_sniper": ("float", 68.0, 86.0, 1.0),
    "stoch_k_thresh": ("float", 65.0, 88.0, 1.0),
    "mfi_bull_thresh": ("float", 30.0, 60.0, 2.0),
    "cci_trend_thresh": ("float", -50.0, 100.0, 10.0),
    "williams_r_thresh": ("float", -90.0, -66.0, 2.0),
    "gear2_moonshot_trigger_pct": ("float", 0.015, 0.04, 0.005),
    "gear2_moonshot_gap_pct": ("float", 0.003, 0.01, 0.001),
    "gear3_trailing_trigger_pct": ("float", 0.008, 0.024, 0.002),
    "gear3_trailing_gap_pct": ("float", 0.005, 0.015, 0.001),
    "gear4_breakeven_trigger_pct": ("float", 0.004, 0.012, 0.001),
    "gear4_breakeven_buffer_pct": ("float", 0.0005, 0.003, 0.0005),
    "max_hold_bars": ("int", 12, 72, 6),
    "sma200_buffer_pct": ("float", 0.985, 1.015, 0.005),
    "volume_floor_mult": ("float", 0.5, 1.2, 0.1),
    "rsi_surge_ceiling": ("float", 76.0, 90.0, 2.0),
    "sl_hard_cap_pct": ("float", 0.02, 0.06, 0.01),
    "tp_hard_cap_pct": ("float", 0.05, 0.15, 0.02),
    "cooldown_bars_after_sl": ("int", 0, 6, 2),
    "kelly_fraction_cap": ("float", 0.15, 0.40, 0.05),
    "giant_candle_atr_mult": ("float", 1.5, 3.5, 0.5),
    "use_dual_trend": ("categorical", (True, False)),
    "require_green_candle": ("categorical", (True, False)),
    "strategy_type": ("categorical", tuple(_STRAT_MAP_MB.keys())),
    "macro_regime_filter": ("categorical", tuple(_MACRO_MAP_MB.keys())),
    "trend_strength_min_adx": ("float", 20.0, 35.0, 2.5),
    "rsi_hook_oversold": ("float", 26.0, 48.0, 2.0),
    "rsi_reversal_exit_thresh": ("float", 56.0, 74.0, 2.0),
    "bb_lower_buffer": ("float", 0.99, 1.04, 0.01),
    "bb_upper_buffer": ("float", 0.97, 1.01, 0.01),
    "macd_cross_lookback": ("int", 3, 15, 2),
    "mfi_bear_thresh": ("float", 70.0, 90.0, 5.0),
    "momentum_req_pos_hist": ("categorical", (True, False)),
    "supertrend_mult": ("float", 2.0, 4.5, 0.5),
    "ichi_cloud_buffer": ("float", 0.996, 1.004, 0.002),
    "keltner_mult": ("float", 1.5, 3.0, 0.5),
    "cci_extreme_exit": ("float", 150.0, 250.0, 25.0),
    "williams_r_exit": ("float", -25.0, -5.0, 5.0),
    "rejection_wick_ratio": ("float", 0.25, 0.55, 0.05),
    "vol_cap_rejection": ("float", 3.0, 6.0, 0.5),
    "vol_cap_normal": ("float", 2.0, 3.5, 0.5),
    "body_min_atr_pct": ("float", 0.1, 0.5, 0.1),
    "high_low_spread_cap": ("float", 3.0, 6.0, 0.5),
    "spot_step_trigger1": ("float", 0.015, 0.03, 0.005),
    "spot_step_lock1": ("float", 0.005, 0.015, 0.005),
    "spot_step_trigger2": ("float", 0.035, 0.055, 0.01),
    "spot_step_lock2": ("float", 0.02, 0.035, 0.005),
    "spot_step_trigger3": ("float", 0.06, 0.09, 0.01),
    "spot_step_lock3": ("float", 0.045, 0.07, 0.005),
    "gear1_sniper_slope": ("float", 1.0, 2.5, 0.5),
    "gear1_sniper_max_rsi": ("float", 80.0, 92.0, 2.0),
    "gear1_sniper_min_rsi": ("float", 10.0, 22.0, 3.0),
    "gear2_moonshot_atr_mult": ("float", 1.5, 3.0, 0.5),
    "gear3_trailing_atr_mult": ("float", 1.0, 2.0, 0.2),
    "mom_tp_roe_thresh": ("float", 0.025, 0.05, 0.005),
    "mom_tp_rsi_thresh": ("float", 72.0, 84.0, 2.0),
    "mom_tp_drop_pct": ("float", 0.0015, 0.0045, 0.001),
    "max_pos_alloc_pct": ("float", 0.10, 0.25, 0.05),
    "min_trade_notional": ("float", 5.0, 15.0, 2.5),
    "pyramid_scaling_mult": ("float", 0.5, 1.0, 0.1),
    "sideways_max_adx": ("float", 15.0, 25.0, 2.5),
    "adx_slope_check": ("categorical", (True, False)),
    "vol_exhaustion_mult": ("float", 0.3, 0.8, 0.1),
}

if set(GENOME_SEARCH_SPACE) != set(GENOME_PARAM_ORDER):
    raise ValueError("GENOME_SEARCH_SPACE must exactly match GENOME_PARAM_ORDER")

BARSPERDAY = 48  # Named constant — 30m candles per day (24h × 2)
