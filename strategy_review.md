# Quantitative Review: MACD/RSI Strategy

This document provides a mathematical and quantitative evaluation of the trading logic implemented in `bot/strategy.py` and the corresponding AI evaluation in `bot/ai_engine.py`.

## 1. Market Regime Detection (`detect_regime`)

### Current Logic
- Determines a `TRENDING` regime if $ADX_{current} > 25$ AND $ADX_{current} > ADX_{previous}$.
- Otherwise, defaults to `SIDEWAYS`.

### Quantitative Critique
- **Noise Susceptibility:** Comparing $ADX_t > ADX_{t-1}$ point-to-point is highly vulnerable to micro-fluctuations on lower timeframes. ADX can temporarily tick down for a single candle while the macro trend remains entirely intact.

### Recommended Enhancements
- **Slope Smoothing:** Apply a short moving average to ADX (e.g., $SMA(ADX, 3) > SMA(ADX, 5)$) to determine the true gradient, or require $ADX$ to be strictly increasing for 2-3 consecutive periods before classifying the regime as trending.

## 2. Trend Following Strategy (`execute_trend_strategy`)

### Current Logic
- **Entry:** MACD crossover above Signal AND Price > SMA 200 AND RSI < 65 AND Volume > 1.5x SMA.
- **Exit:** Fixed Stop Loss (SL) at $Price - 1.5 \times ATR$ and Take Profit (TP) at $Price + 2.5 \times ATR$.

### Quantitative Critique
- **Probability of Exact Alignment:** A MACD crossover is derived from lagging EMAs, while a volume spike is an instantaneous event. The mathematical probability $P(MACD_{cross} \cap Volume_{spike})$ occurring on the exact same discrete time step (candle) is extremely low, leading to missed valid setups.
- **Truncated Right Tail (Expected Value):** Trend following strategies rely on a few massive winners to offset numerous small losers (positive skewness). Imposing a static TP of $2.5 \times ATR$ artificially truncates the right tail of the return distribution, preventing the capture of macro trends.

### Recommended Enhancements
- **Signal Memory Window:** Allow a lookback window for the entry. For example, trigger if MACD crossed above the signal line within the *last 3 periods* and a volume spike confirms it now.
- **Dynamic Trailing Exits:** Remove the fixed TP. Rely on an ATR-based Trailing Stop (e.g., Chandelier Exit) or use the MACD bearish crossover as the primary exit mechanism to ride the trend to exhaustion.

## 3. Mean Reversion Strategy (`execute_sideways_strategy`)

### Current Logic
- **Entry:** RSI crosses above 30 AND Price $\le$ Lower Bollinger Band AND Volume > 1.5x SMA.
- **Exit:** Fixed TP at $Price + 2.5 \times ATR$.

### Quantitative Critique
- **Volume Contradiction in Mean Reversion:** In a stationary (sideways) process, a volume spike of 1.5x at the lower Bollinger Band often signifies a momentum breakdown and a potential regime shift to a downward trend, rather than a mean-reverting bounce. Mean reversion thrives on momentum *exhaustion*.
- **Misaligned Target Bounds:** In a sideways market, price reverts to the mean $\mu$ (SMA 20). Setting a static TP of $2.5 \times ATR$ ignores the local volatility bounds. If $2.5 \times ATR$ exceeds the Upper Bollinger Band, the target will rarely be hit.

### Recommended Enhancements
- **Volume Exhaustion Filter:** Remove the volume spike requirement for mean reversion, or explicitly require volume to be *average or declining* to confirm selling exhaustion.
- **Statistical Targets:** Tie the Take Profit dynamically to the Bollinger Band Midline (SMA 20) or the Upper Band, which mathematically represents the bounds of the current stationary distribution.

## 4. AI Engine Context (`bot/ai_engine.py`)

### Current Logic
- The `tech_context` passed to the AI Committee only contains the `strategy_used`, `ADX`, and `RSI`.

### Quantitative Critique
- The system prompts the LLM to evaluate "Reward-to-Risk (R:R) targets" and "bearish divergence", but starves it of the necessary quantitative inputs to perform this analysis mathematically.

### Recommended Enhancements
- **Context Enrichment:** Inject critical quantitative metrics into `tech_data` before passing it to the LLM:
  - `MACD_Histogram` (to allow divergence detection)
  - `ATR` and `Bollinger_Band_Width` (to define risk boundaries)
  - Percentage distance to `SMA_200` (to contextualize macro trend extension)
