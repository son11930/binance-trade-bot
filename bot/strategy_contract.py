"""Canonical strategy names and parameter compatibility for lab and live.

The GPU kernel consumes numeric strategy ids while the live engine consumes
JSON.  Keeping the conversion here prevents an unknown or legacy name from
silently falling back to a different strategy.
"""

from __future__ import annotations

import math
from typing import Any, Dict


STRATEGY_MAP = {
    "rsi_sniper": 0,
    "ema_cross": 1,
    "supertrend_momentum": 2,
    "ichi_cloud": 3,
    "keltner_bounce": 4,
    "stoch_mfi_diverge": 5,
    "williams_mean_rev": 6,
    "donchian_breakout": 7,
    "macd_momentum": 8,
    "bb_squeeze": 9,
    "adx_trend_rider": 10,
    "fibo_pullback": 11,
}

MACRO_REGIME_MAP = {
    "sma200_only": 0,
    "sma200_and_adx": 1,
    "none": 2,
}

# Names used by the pre-GPU live evaluator.  They remain readable when an old
# manifest is loaded, but are normalized before any signal is evaluated.
LEGACY_STRATEGY_ALIASES = {
    "fibonacci_golden_pullback": "rsi_sniper",
    "ema_crossover_momentum": "ema_cross",
    "supertrend_mfi_confluence": "supertrend_momentum",
    "ichimoku_cci_breakout": "ichi_cloud",
    "stoch_mfi_divergence": "stoch_mfi_diverge",
    "macd_momentum_surge": "macd_momentum",
    "bb_squeeze_breakout": "bb_squeeze",
    "multi_timeframe_momentum": "adx_trend_rider",
    "sma_pullback_divergence": "fibo_pullback",
}

LEGACY_PARAMETER_ALIASES = {
    "rsi_sniper_thresh": "gear1_rsi_sniper",
    "tp_rr_ratio": "tp_rr_mult",
    "trail_trig_roe": "gear3_trailing_trigger_pct",
    "trail_gap_roe": "gear3_trailing_gap_pct",
    "be_trig_roe": "gear4_breakeven_trigger_pct",
    "be_buffer_roe": "gear4_breakeven_buffer_pct",
    "moonshot_trig_roe": "gear2_moonshot_trigger_pct",
    "moonshot_gap_roe": "gear2_moonshot_gap_pct",
    "vol_floor": "volume_floor_mult",
}

# Defaults intentionally match the units used by the active lab schema.  The
# live path still rejects an unknown strategy instead of selecting id 0.
DEFAULT_PARAMETERS = {
    "adx_trend_thresh": 20.0,
    "vol_surge_mult": 1.5,
    "sl_atr_mult": 1.5,
    "tp_rr_mult": 2.0,
    "gear1_rsi_sniper": 78.0,
    "stoch_k_thresh": 80.0,
    "mfi_bull_thresh": 40.0,
    "cci_trend_thresh": 0.0,
    "williams_r_thresh": -80.0,
    "gear2_moonshot_trigger_pct": 0.02,
    "gear2_moonshot_gap_pct": 0.005,
    "gear3_trailing_trigger_pct": 0.012,
    "gear3_trailing_gap_pct": 0.008,
    "gear4_breakeven_trigger_pct": 0.006,
    "gear4_breakeven_buffer_pct": 0.001,
    "max_hold_bars": 36,
    "sma200_buffer_pct": 0.995,
    "volume_floor_mult": 0.7,
    "rsi_surge_ceiling": 82.0,
    "sl_hard_cap_pct": 0.04,
    "tp_hard_cap_pct": 0.10,
    "cooldown_bars_after_sl": 2,
    "kelly_fraction_cap": 0.25,
    "giant_candle_atr_mult": 2.0,
    "use_dual_trend": True,
    "require_green_candle": False,
    "strategy_type": "rsi_sniper",
    "macro_regime_filter": "sma200_only",
    "trend_strength_min_adx": 20.0,
    "rsi_hook_oversold": 36.0,
    "rsi_reversal_exit_thresh": 65.0,
    "bb_lower_buffer": 1.0,
    "bb_upper_buffer": 1.0,
    "macd_cross_lookback": 8,
    "mfi_bear_thresh": 70.0,
    "momentum_req_pos_hist": True,
    "supertrend_mult": 3.0,
    "ichi_cloud_buffer": 1.0,
    "keltner_mult": 2.0,
    "cci_extreme_exit": 200.0,
    "williams_r_exit": -20.0,
    "rejection_wick_ratio": 0.4,
    "vol_cap_rejection": 4.0,
    "vol_cap_normal": 2.5,
    "body_min_atr_pct": 0.1,
    "high_low_spread_cap": 4.0,
    "spot_step_trigger1": 0.02,
    "spot_step_lock1": 0.01,
    "spot_step_trigger2": 0.04,
    "spot_step_lock2": 0.025,
    "spot_step_trigger3": 0.07,
    "spot_step_lock3": 0.055,
    "gear1_sniper_slope": 1.0,
    "gear1_sniper_max_rsi": 88.0,
    "gear1_sniper_min_rsi": 15.0,
    "gear2_moonshot_atr_mult": 2.0,
    "gear3_trailing_atr_mult": 1.5,
    "mom_tp_roe_thresh": 0.03,
    "mom_tp_rsi_thresh": 78.0,
    "mom_tp_drop_pct": 0.003,
    "max_pos_alloc_pct": 0.15,
    "min_trade_notional": 5.0,
    "pyramid_scaling_mult": 0.7,
    "sideways_max_adx": 20.0,
    "adx_slope_check": True,
    "vol_exhaustion_mult": 0.5,
}

LOOKBACK_DEFAULTS = {
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
}


def _canonical_id(value: Any, mapping: Dict[str, int], aliases: Dict[str, str], label: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"Unknown {label}: {value!r}")
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric) and numeric.is_integer():
            reverse = {item: key for key, item in mapping.items()}
            if int(numeric) in reverse:
                return reverse[int(numeric)]
    text = str(value).strip().lower()
    canonical = aliases.get(text, text)
    if canonical not in mapping:
        raise ValueError(f"Unknown {label}: {value!r}")
    return canonical


def canonical_strategy_type(value: Any) -> str:
    return _canonical_id(value, STRATEGY_MAP, LEGACY_STRATEGY_ALIASES, "strategy_type")


def strategy_id(value: Any) -> int:
    return STRATEGY_MAP[canonical_strategy_type(value)]


def canonical_macro_regime(value: Any) -> str:
    return _canonical_id(value, MACRO_REGIME_MAP, {}, "macro_regime_filter")


def normalize_strategy_parameters(parameters: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a new, canonical parameter object suitable for live evaluation."""
    source = dict(parameters or {})
    translated = dict(source)
    for legacy_name, canonical_name in LEGACY_PARAMETER_ALIASES.items():
        if canonical_name not in translated and legacy_name in translated:
            translated[canonical_name] = translated[legacy_name]

    result = {**DEFAULT_PARAMETERS, **LOOKBACK_DEFAULTS, **translated}
    result["strategy_type"] = canonical_strategy_type(result["strategy_type"])
    result["macro_regime_filter"] = canonical_macro_regime(result["macro_regime_filter"])
    return result
