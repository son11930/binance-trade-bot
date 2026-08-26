"""Helpers for starting uniquely named python-binance websocket listeners."""

from collections.abc import Callable, Sequence
from typing import Any


def start_unique_multiplex_socket(
    manager: Any,
    callback: Callable[[dict], Any],
    streams: Sequence[str],
    market_type: str,
) -> str:
    """Start a multiplex listener with a stable, market-specific registry key.

    python-binance derives the listener key from the stream URL. Spot and USD-M
    futures can have identical stream names, so using the public convenience
    methods can make the second listener overwrite the first one.
    """
    if market_type not in {"spot", "futures"}:
        raise ValueError(f"Unsupported websocket market: {market_type!r}")

    socket_name = "multiplex_socket" if market_type == "spot" else "futures_multiplex_socket"
    path = f"{market_type}_multiplex_socket"
    start_async = getattr(manager, "_start_async_socket", None)
    if callable(start_async):
        return start_async(
            callback=callback,
            socket_name=socket_name,
            params={"streams": list(streams)},
            path=path,
        )

    public_method = getattr(manager, f"start_{socket_name}", None)
    if not callable(public_method):
        raise RuntimeError(f"Websocket manager does not support {market_type} multiplex streams")
    return public_method(callback=callback, streams=list(streams))
