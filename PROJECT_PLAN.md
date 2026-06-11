# Project Plan: AI Trading Bot with 2-Layer Decision Engine

## Objective
Create a full-stack Python application that executes an automated crypto trading bot on Binance and hosts a modern HTML/CSS dashboard for live monitoring.

## Architecture
- **Backend & Trading Logic**: Python 3.11+, `python-binance`, `pandas_ta`, `google-generativeai`.
- **API Server**: FastAPI + Uvicorn.
- **Frontend Dashboard**: HTML5, Tailwind CSS, Chart.js.

## Trading Strategy (v2.0)
1. **Layer 1 (Technical)**: Trend Following on 1H Chart. Buy on MACD Golden Cross if Price > SMA 200. Sell on MACD Death Cross.
2. **Layer 2 (AI Sentiment)**: When Layer 1 triggers a buy, fetch news and analyze with Gemini Flash. If Risk Score > 40, abort buy.
3. **Execution (5 Coins)**: Monitors BTC, ETH, XRP, SOL, BNB.
4. **Position Sizing**: Live Binance Sync. Compounding 5-Tranches (20% of Real Equity per trade). 2.5% strict Stop Loss.

## Status & Evolution
- Moved from Mean Reversion (RSI < 30) to Trend Following (MACD + SMA 200) after backtesting proved 15m/1H mean reversion generates net losses during strong bear trends.
- Upgraded to Live Binance Wallet Sync (State Recovery via SQLite `trades.db`) to ensure the bot can safely resume after VM reboots without losing position state.
- Upgraded Frontend to Glassmorphism UI with Live USDT tracking and auto-polling AI status.

## Execution Steps
- [x] **Phase 1**: Scaffold project, create `requirements.txt` and `.env`.
- [x] **Phase 2**: Build `binance_client.py` and Layer 1 indicator logic (`strategy.py`).
- [x] **Phase 3**: Integrate `google-generativeai` for Layer 2 (`ai_engine.py`).
- [x] **Phase 4**: Build FastAPI backend (`server.py`) and SQLite database.
- [x] **Phase 5**: Develop modern Premium Glassmorphism dashboard (`index.html`).
- [x] **Phase 6**: Live Wallet Sync, State Recovery, and Compounding Position Sizing.
