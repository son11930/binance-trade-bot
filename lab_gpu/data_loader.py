"""
data_loader.py — Historical kline loading, caching, array conversions, and VRAM pre-loading.
"""
import os
import pickle
import time
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any

from .config import (
    CACHE_DIR, logger, N_FEATURES, FEATURE_ORDER, HORIZON_BARS
)
from bot.indicators_library import (
    calc_supertrend, calc_ichimoku, calc_keltner_channels,
    calc_momentum_flow, calc_volatility_volume
)

# Global VRAM storage structures
_GPU_DEVICE_ARRAYS: Dict[str, Dict] = {}
_GPU_FLAT_DATA: Dict[str, Any] = {}

def _load_and_cache_symbol(sym: str) -> Optional[pd.DataFrame]:
    """Load symbol from local pkl cache and compute all indicators."""
    import ta
    file_path = os.path.join(CACHE_DIR, f"{sym}_30m_365d.pkl")
    if not os.path.exists(file_path):
        logger.warning(f"[{sym}] Cache not found at {file_path}. Run CPU synthesizer first to download data.")
        return None
    try:
        with open(file_path, "rb") as f:
            df = pickle.load(f)
        if df.empty or len(df) < 300:
            return None
        df["SMA_200"] = ta.trend.sma_indicator(df["close"], window=200)
        df["SMA_50"]  = ta.trend.sma_indicator(df["close"], window=50)
        df["ATR"]     = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)
        df["RSI"]     = ta.momentum.rsi(df["close"], window=14)
        df["ADX"]     = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
        df["SMA_20_Vol"] = df["volume"].rolling(window=20).mean()
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2.0)
        df["BB_Upper"] = bb.bollinger_hband()
        df["EMA_10"] = ta.trend.ema_indicator(df["close"], window=10)
        df["EMA_50"] = ta.trend.ema_indicator(df["close"], window=50)
        df = calc_supertrend(df, period=10, multiplier=3.0)
        df = calc_ichimoku(df)
        df = calc_keltner_channels(df, window=20, mult=2.0)
        df = calc_momentum_flow(df)
        df = calc_volatility_volume(df)
        df = df.fillna(0.0)
        return df
    except Exception as e:
        logger.error(f"[{sym}] Failed to load/process cache: {e}")
        return None

def _df_to_arrays(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Convert indicator DataFrame to contiguous float32 numpy arrays for fast CPU/GPU access."""
    def g(col: str, default: float = 0.0) -> np.ndarray:
        if col in df.columns:
            return df[col].values.astype(np.float32)
        return np.full(len(df), default, dtype=np.float32)
    return {
        "close":       df["close"].values.astype(np.float32),
        "high":        df["high"].values.astype(np.float32),
        "low":         df["low"].values.astype(np.float32),
        "open":        df["open"].values.astype(np.float32),
        "vol":         df["volume"].values.astype(np.float32),
        "sma200":      g("SMA_200"), "sma50": g("SMA_50"),
        "atr":         g("ATR"),     "rsi":   g("RSI"),
        "adx":         g("ADX"),     "vol_sma": g("SMA_20_Vol"),
        "bb_up":       g("BB_Upper"),"ema10": g("EMA_10"),
        "ema50":       g("EMA_50"),  "st_dir": g("supertrend_dir"),
        "mfi":         g("mfi", 50.0), "stoch_k": g("stoch_rsi_k", 50.0),
        "cci":         g("cci"),     "williams": g("williams_r", -50.0),
        "keltner_low": g("keltner_lower"), "tenkan": g("ichimoku_tenkan"),
        "kijun":       g("ichimoku_kijun"),
        "donchian_high": g("donchian_high_20", df["close"].values.mean()),
    }

def align_symbols_to_arrays(symbol_dfs: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, np.ndarray]]:
    """Aligns all dataframes to a universal datetime index to prevent causality bugs and time-shifts."""
    # Try to find a timestamp index
    all_indices = []
    for sym, df in symbol_dfs.items():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        # Drop duplicates if any
        df = df[~df.index.duplicated(keep='first')]
        symbol_dfs[sym] = df
        all_indices.append(df.index)
        
    if not all_indices:
        return {sym: _df_to_arrays(df) for sym, df in symbol_dfs.items()}
        
    # Create master index
    master_index = all_indices[0]
    for idx in all_indices[1:]:
        master_index = master_index.union(idx)
    master_index = master_index.sort_values()
    
    symbol_arrays = {}
    for sym, df in symbol_dfs.items():
        # Forward fill prices, fillna(0) for missing leading data
        aligned_df = df.reindex(master_index, method='ffill').fillna(0.0)
        # Force volume to 0 where it was missing to avoid fake trading volume during gaps
        missing_mask = ~master_index.isin(df.index)
        if "volume" in aligned_df.columns:
            aligned_df.loc[missing_mask, "volume"] = 0.0
            
        symbol_arrays[sym] = _df_to_arrays(aligned_df)
        
    return symbol_arrays

def preload_all_symbols_to_gpu(symbol_arrays: Dict[str, Dict[str, np.ndarray]], gpu_available: bool) -> None:
    """Transfer ALL 20 symbols' price data to GPU VRAM exactly once at startup."""
    global _GPU_DEVICE_ARRAYS
    if not gpu_available:
        return
    from numba import cuda as nb_cuda
    _GPU_DEVICE_ARRAYS.clear()
    total_bytes = 0
    for sym, arrays in symbol_arrays.items():
        _GPU_DEVICE_ARRAYS[sym] = {key: nb_cuda.to_device(arr) for key, arr in arrays.items()}
        total_bytes += sum(arr.nbytes for arr in arrays.values())
    logger.info(f"✅ VRAM Pre-load: {len(_GPU_DEVICE_ARRAYS)} symbols locked in GPU VRAM ({total_bytes/1e6:.1f} MB / 8,192 MB)")

def _pack_symbols_to_flat_gpu(symbol_arrays: Dict[str, Dict[str, np.ndarray]], gpu_available: bool, warmup_fn: Optional[Any] = None) -> None:
    """
    Pack all 20 symbols into a single contiguous [total_bars, 23] float32 VRAM tensor.
    Also stores sym_offsets, sym_lengths, and horizon_bars on device.
    """
    global _GPU_FLAT_DATA
    
    sym_list = list(symbol_arrays.keys())
    lengths  = [symbol_arrays[s]["close"].shape[0] for s in sym_list]
    
    # Time-align symbols
    min_len = min(lengths) if lengths else 0
    total_bars = len(sym_list) * min_len if sym_list else 0
    offsets = np.arange(len(sym_list), dtype=np.int32) * min_len

    flat = np.zeros((total_bars, N_FEATURES), dtype=np.float32)
    for i, sym in enumerate(sym_list):
        start = int(offsets[i])
        end   = start + min_len
        arr   = symbol_arrays[sym]
        for fi, feat in enumerate(FEATURE_ORDER):
            if feat in arr:
                # Take the last min_len elements to implicitly align ends
                flat[start:end, fi] = arr[feat][-min_len:]

    _GPU_FLAT_DATA.clear()
    
    if gpu_available:
        from numba import cuda as nb_cuda
        _GPU_FLAT_DATA.update({
            "price_flat":   nb_cuda.to_device(flat),
            "sym_offsets":  nb_cuda.to_device(offsets),
            "sym_lengths":  nb_cuda.to_device(np.array(lengths, dtype=np.int32)),
            "horizon_bars": nb_cuda.to_device(np.array(HORIZON_BARS, dtype=np.int32)),
            "sym_list":     sym_list,
            "n_symbols":    len(sym_list),
            "n_horizons":   len(HORIZON_BARS),
            "min_len":      min_len
        })
    else:
        _GPU_FLAT_DATA.update({
            "price_flat":   flat,
            "sym_offsets":  offsets,
            "sym_lengths":  np.array(lengths, dtype=np.int32),
            "horizon_bars": np.array(HORIZON_BARS, dtype=np.int32),
            "sym_list":     sym_list,
            "n_symbols":    len(sym_list),
            "n_horizons":   len(HORIZON_BARS),
            "min_len":      min_len
        })
    logger.info(
        f"✅ Mega-Batch VRAM pack: {flat.nbytes/1e6:.1f} MB "
        f"({len(sym_list)} syms × {max(lengths)} bars × {N_FEATURES} feats) ready."
    )
    if warmup_fn:
        warmup_fn()

def _build_symbol_arrays_for_cpu() -> Dict[str, Dict[str, np.ndarray]]:
    """CPU-fallback stub."""
    return {}
