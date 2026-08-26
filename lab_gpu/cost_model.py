"""Causal execution-cost and volume-unit helpers for the lab kernels.

The simulator receives price features in native price/volume units.  Costs are
returned as a decimal *rate* so they can be subtracted from a trade return.
Funding is deliberately not guessed here: the flat lab data has no historical
funding series, so a strategy must pass the fee and volatility-slippage model
before it is validated with real funding data.
"""

from __future__ import annotations

import math


# ``FEATURE_ORDER`` is stable in the flat matrix built by data_loader.py.
# Keep this explicit in the cost model so the cost calculation cannot silently
# read the neighbouring SMA50 column as ATR.
ATR_FEATURE_INDEX = 7

# Binance VIP0 futures taker fee: 0.05% per side, 0.10% round trip.
TAKER_FEE_RATE_PER_SIDE = 0.0005
ROUND_TRIP_TAKER_FEE_RATE = TAKER_FEE_RATE_PER_SIDE * 2.0

# A conservative volatility-aware execution allowance: 5% of ATR as a
# fraction of price.  At ATR/price = 1%, this adds 5 bps round trip.
ATR_SLIPPAGE_FRACTION = 0.05


def round_trip_cost(price: float, atr: float) -> float:
    """Return taker fee plus ATR-scaled slippage as a decimal rate.

    ``atr`` and ``price`` are both native price units, therefore
    ``atr / price`` is dimensionless.  The price and ATR should be the entry
    values, both known before the trade is opened; this avoids using the exit
    candle's high/low-derived ATR as look-ahead information.
    """
    try:
        price_value = float(price)
        atr_value = float(atr)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(atr_value) or not math.isfinite(price_value) or price_value <= 0.0:
        return 0.0
    return ROUND_TRIP_TAKER_FEE_RATE + max(0.0, atr_value) / price_value * ATR_SLIPPAGE_FRACTION


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
