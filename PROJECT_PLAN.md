# Strategy Optimization Project Plan

## Current State Analysis
The bot currently uses a MACD (12, 26, 9) cross strategy combined with an SMA 200 trend filter on the 1-hour timeframe. It also employs a Gemini 3.5 AI sentiment filter based on CoinTelegraph RSS feeds, and a hard 2.5% Stop Loss.

## Core Problems Identified (Why 4 positions are at a loss)
1. **Lagging Entry (Buying the Top):** MACD on a 1H timeframe is a lagging indicator. By the time it crosses AND the price breaks above the SMA 200, the bullish impulse is often already exhausted, causing the bot to buy at local peaks.
2. **Missing Take Profit / Trailing Stop:** The bot only exits on a MACD Death Cross or a 2.5% Stop Loss. Because MACD is lagging, a Death Cross often happens *after* the price has already crashed. This turns profitable trades into losing trades because the bot "rides it all the way back down".
3. **Stop Loss is Too Tight:** A 2.5% fixed stop loss is very tight for crypto volatility. Normal market noise (wicks) can easily trigger the stop loss before the trend continues upwards.
4. **AI News Mismatch:** The AI fetches generic Bitcoin/Crypto news but the bot trades multiple altcoins. Generic news doesn't reflect altcoin-specific momentum.

## Planned Improvements
- **Phase 1:** Analyze and propose better indicator combinations (e.g., adding RSI to prevent buying when Overbought, or using ATR for dynamic stop losses).
- **Phase 2:** Implement a Trailing Stop or Take Profit (TP) target to lock in gains before the MACD Death Cross.
- **Phase 3:** Refine the AI Prompt to be asset-specific, and adjust the Stop Loss logic.
- **Phase 4:** Implement a fallback AI model mechanism in `bot/ai_engine.py` to handle rate limits and API failures smoothly, ensuring the bot doesn't crash or miss trades when the primary model is down.
- **Phase 5:** Implement Time-Filtered PNL calculations (1D, 7D, 1M, All-Time) and add Profit Percentage metric to the dashboard.
