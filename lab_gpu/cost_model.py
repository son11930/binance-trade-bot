"""Causal execution-cost and volume-unit helpers for the lab kernels.

The simulator receives price features in native price/volume units.  Costs are
returned as a decimal *rate* so they can be subtracted from a trade return.
Funding is deliberately not guessed here: the flat lab data has no historical
funding series, so a strategy must pass the fee and volatility-slippage model
before it is validated with real funding data.
"""

from __future__ import annotations

import math
import os


# ``FEATURE_ORDER`` is stable in the flat matrix built by data_loader.py.
# Keep this explicit in the cost model so the cost calculation cannot silently
# read the neighbouring SMA50 column as ATR.
ATR_FEATURE_INDEX = 7

# Fee assumptions are explicit because the lab does not have access to the
# private fee tier of the account that will eventually trade a candidate.
# The conservative default is the higher of the two built-in profiles so an
# unspecified market cannot make a high-frequency strategy look better than it
# is likely to be in production.
COST_MODEL_VERSION = "phase39-fee-v1"
SPOT_TAKER_FEE_RATE_PER_SIDE = 0.001
FUTURES_TAKER_FEE_RATE_PER_SIDE = 0.0005
CONSERVATIVE_TAKER_FEE_RATE_PER_SIDE = max(
    SPOT_TAKER_FEE_RATE_PER_SIDE,
    FUTURES_TAKER_FEE_RATE_PER_SIDE,
)
DEFAULT_LAB_MARKET_TYPE = "conservative"
_MARKET_FEE_RATES = {
    "spot": SPOT_TAKER_FEE_RATE_PER_SIDE,
    "futures": FUTURES_TAKER_FEE_RATE_PER_SIDE,
    "conservative": CONSERVATIVE_TAKER_FEE_RATE_PER_SIDE,
}
_MAX_REASONABLE_FEE_RATE = 0.10


def _safe_fee_rate(value: object, fallback: float) -> float:
    """Return a finite non-negative decimal rate, or the safe fallback."""
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if not math.isfinite(rate) or rate < 0.0 or rate > _MAX_REASONABLE_FEE_RATE:
        return float(fallback)
    return rate


def fee_rate_for_market(market_type: str | None) -> float:
    """Return the built-in taker rate for a market, conservatively if unknown."""
    normalized = str(market_type or "").strip().lower()
    return _MARKET_FEE_RATES.get(normalized, CONSERVATIVE_TAKER_FEE_RATE_PER_SIDE)


LAB_MARKET_TYPE = str(
    os.environ.get("LAB_MARKET_TYPE", DEFAULT_LAB_MARKET_TYPE)
).strip().lower()
if LAB_MARKET_TYPE not in _MARKET_FEE_RATES:
    LAB_MARKET_TYPE = DEFAULT_LAB_MARKET_TYPE

_configured_fee = os.environ.get("LAB_TAKER_FEE_RATE_PER_SIDE")
_default_fee_rate = fee_rate_for_market(LAB_MARKET_TYPE)
TAKER_FEE_RATE_PER_SIDE = (
    _default_fee_rate
    if _configured_fee is None
    else _safe_fee_rate(_configured_fee, _default_fee_rate)
)
ROUND_TRIP_TAKER_FEE_RATE = TAKER_FEE_RATE_PER_SIDE * 2.0

# A conservative volatility-aware execution allowance: 5% of ATR as a
# fraction of price.  At ATR/price = 1%, this adds 5 bps round trip.
ATR_SLIPPAGE_FRACTION = 0.05


def fee_amount(notional: float, fee_rate: float | None = None) -> float:
    """Calculate one-side fee in quote currency for a positive notional."""
    try:
        notional_value = float(notional)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(notional_value) or notional_value <= 0.0:
        return 0.0
    if fee_rate is None:
        rate = TAKER_FEE_RATE_PER_SIDE
    else:
        rate = _safe_fee_rate(fee_rate, TAKER_FEE_RATE_PER_SIDE)
    return notional_value * rate


def round_trip_cost(
    price: float,
    atr: float,
    fee_rate: float | None = None,
) -> float:
    """Return taker fee plus ATR-scaled slippage as a decimal rate.

    ``atr`` and ``price`` are both native price units, therefore
    ``atr / price`` is dimensionless.  The price and ATR should be the entry
    values, both known before the trade is opened; this avoids using the exit
    candle's high/low-derived ATR as look-ahead information.
    """
    try:
        price_value = float(price)
    except (TypeError, ValueError):
        return float("inf")
    if not math.isfinite(price_value) or price_value <= 0.0:
        return float("inf")
    try:
        atr_value = float(atr)
    except (TypeError, ValueError):
        atr_value = 0.0
    if not math.isfinite(atr_value):
        atr_value = 0.0
    fee_rate_value = (
        ROUND_TRIP_TAKER_FEE_RATE
        if fee_rate is None
        else _safe_fee_rate(fee_rate, TAKER_FEE_RATE_PER_SIDE) * 2.0
    )
    return fee_rate_value + max(0.0, atr_value) / price_value * ATR_SLIPPAGE_FRACTION


def cost_model_metadata() -> dict[str, object]:
    """Return immutable, serializable assumptions attached to lab evidence."""
    return {
        "fee_model_version": COST_MODEL_VERSION,
        "fee_market_type": LAB_MARKET_TYPE,
        "taker_fee_rate_per_side": round(TAKER_FEE_RATE_PER_SIDE, 8),
        "round_trip_fee_rate": round(ROUND_TRIP_TAKER_FEE_RATE, 8),
        "atr_slippage_fraction": ATR_SLIPPAGE_FRACTION,
        "funding_included": False,
    }


def estimate_round_trip_cost_rate(atr: float, reference_price: float) -> float:
    """Backward-compatible adapter using the old ``(atr, price)`` order."""
    return round_trip_cost(reference_price, atr)


def volume_is_exhausted(volume: float, volume_sma: float, exhaustion_mult: float) -> bool:
    """Whether volume is below the configured relative-volume floor.

    ``vol_exhaustion_mult`` is a ratio (for example ``0.3`` means 30% of the
    rolling average), not an absolute volume and not an upper cap.  High-volume
    rejection remains the responsibility of the separate volume-cap rules.
    """
    try:
        current = float(volume)
        average = float(volume_sma)
        threshold = float(exhaustion_mult)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(current) or not math.isfinite(average) or not math.isfinite(threshold):
        return True
    if average <= 0.0 or current < 0.0:
        return True
    return (current / average) < threshold
