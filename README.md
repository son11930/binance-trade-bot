# Binance Trade Bot 🚀

AI-powered cryptocurrency trading bot with real-time Binance Wallet Synchronization, Dynamic Position Sizing, and an elegant Glassmorphism web dashboard.

## Features
- **Multi-Coin Support:** Trades BTC, ETH, XRP, SOL, and BNB simultaneously.
- **AI Sentiment Analysis:** Uses Gemini AI to read recent crypto news and evaluate risk before buying.
- **Trend Following Strategy:** Uses MACD and SMA-200 on a 1-hour timeframe.
- **Robust State Recovery:** Syncs live with your Binance Spot Wallet to detect manual trades and network dropouts.
- **Secure Web Dashboard:** Real-time polling, live USDT balance, execution logs, and token-based authentication.

## Getting Started
1. Configure `.env` with your Binance API keys and Dashboard login credentials.
2. Run the Dashboard API: `uvicorn api.server:app --reload`
3. Run the Bot Core: `python -m bot.main`

## Versioning
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes.
