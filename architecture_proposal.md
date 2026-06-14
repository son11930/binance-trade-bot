# Architecture Proposal: Refactoring `bot/main.py`

## 1. Current State Analysis
The Binance AI Trading Bot is currently composed of three main areas:
- `api/`: A FastAPI application handling dashboard requests, WebSockets for UI, and receiving webhook updates from the bot.
- `dashboard/`: A static HTML frontend UI.
- `bot/`: The core trading bot logic.

### The Problem with `bot/main.py`
Currently, `bot/main.py` (400+ lines) acts as a "God Object." It tightly couples multiple concerns:
1. **Configuration:** Loading environment variables and initializing constants.
2. **State Management:** Using global variables (`states`, `live_usdt_balance`, `kline_buffers`, `latest_news`) to manage the bot's memory.
3. **Execution Logic:** Calculating PnL, executing trades via `binance_client`, and logging them.
4. **Risk Management:** `check_risk_management` handles dynamic stop-loss, trailing stops, and time-in-trade evaluations.
5. **Event Processing:** Managing Binance WebSocket streams and their callbacks (`process_ticker_message`, `process_kline_message`, `update_kline_buffer`).
6. **AI Orchestration:** Calling AI sentiment functions and evaluating buy/sell signals.
7. **Communication:** Dispatching state payloads to the `api/` backend via HTTP webhooks.

This architecture causes several issues:
- **Testability:** Mocking dependencies for tests is difficult due to heavy reliance on global variables and deep imports.
- **Maintainability:** Modifying risk strategies or websocket handling requires touching the main entry point, increasing the risk of introducing regressions.
- **Scalability:** Expanding to more complex multithreading, or managing multiple portfolios/accounts, becomes challenging when state is strictly global.

## 2. Requirements Gathering
To ensure scalable, maintainable system design, the refactoring must achieve:
- **Separation of Concerns (SoC):** Break `main.py` down into smaller, single-responsibility modules.
- **State Encapsulation:** Eliminate global variables in favor of a `StateManager` or injected context objects.
- **Dependency Injection:** Pass the state and required clients to the websocket and trading handlers, reducing circular dependencies.
- **No Functionality Loss:** The bot must continue to correctly orchestrate technical strategies (`strategy.py`), AI analysis (`ai_engine.py`), and Binance API interactions (`binance_client.py`).

## 3. Design Proposal

We propose splitting `bot/main.py` into focused, domain-specific modules. 

### Proposed Directory Structure (`bot/` directory)

```text
bot/
├── __init__.py
├── config.py              # Environment variables and core constants
├── state.py               # BotState, SymbolState classes to encapsulate data
├── database.py            # Existing repository layer
├── binance_client.py      # Existing REST/WebSocket client
├── strategy.py            # Existing tech indicators
├── ai_engine.py           # Existing LLM processing
├── risk_manager.py        # Centralized risk validation logic
├── trade_executor.py      # Trade execution, PnL calc, DB logging
├── webhook_notifier.py    # Sending state updates to the API
├── news_worker.py         # Background loop for fetching AI news
├── signal_evaluator.py    # Strategy+AI evaluation coordination
├── websocket_manager.py   # Binance WebSocket handlers (ticker, kline)
└── main.py                # Thin entry point: DI setup, thread initialization
```

### Module Responsibilities

1. **`bot/config.py`**
   - Parses `.env` variables and provides typed configuration classes or constants (e.g., `SYMBOLS`, `PAPER_TRADING`, `COOLDOWN_MINUTES`).

2. **`bot/state.py`**
   - Moves `SymbolState` dataclass here.
   - Introduces a `StateManager` class to encapsulate `states`, `live_usdt_balance`, `kline_buffers`, and `latest_news`.
   - Provides thread-safe getters and setters. `sync_state_with_binance()` should be a method of this class or closely tied to it.

3. **`bot/risk_manager.py`**
   - Extracts `check_risk_management()`.
   - Evaluates a `SymbolState` against market price and ATR to return risk-based exit signals (e.g., "Time-in-Trade Stop", "Take Profit", "Dynamic Stop Loss").

4. **`bot/trade_executor.py`**
   - Contains `calculate_pnl()` and `execute_trade()`.
   - Uses `binance_client` to place orders and `TradeRepository` to record them.
   - Mutates the `StateManager` accordingly when trades succeed.

5. **`bot/webhook_notifier.py`**
   - Extracts `update_bot_state()`.
   - Responsible for building the JSON payload from the `StateManager` and broadcasting it to the `WEBHOOK_URL`.

6. **`bot/news_worker.py`**
   - Extracts `news_updater_loop()`.
   - Runs on a background thread, updates the centralized `StateManager.latest_news` periodically.

7. **`bot/signal_evaluator.py`**
   - Extracts `_evaluate_buy_signal()` and `evaluate_strategy_for_symbol()`.
   - Coordinates `strategy.py` technical signals with `ai_engine.py` sentiment analysis.
   - Dispatches orders to `trade_executor.py` if conditions are met.

8. **`bot/websocket_manager.py`**
   - Contains `process_ticker_message`, `process_kline_message`, and buffer updates.
   - This module listens to streams and invokes `signal_evaluator.py` and `risk_manager.py` upon receiving data.

9. **`bot/main.py`** (The New Thin Entry Point)
   - Instantiates the `StateManager`.
   - Synchronizes initial state (`sync_state_with_binance()`).
   - Starts the `news_worker` thread.
   - Initializes the `websocket_manager` and starts the TWM (ThreadedWebsocketManager).
   - Contains a simple keep-alive block with graceful shutdown (`KeyboardInterrupt`).

## 4. Migration Plan
1. **Create `config.py` and `state.py`**: Migrate constants and state objects. Ensure no other modules break by updating their imports.
2. **Extract Utility Modules**: Move webhook and news logic to `webhook_notifier.py` and `news_worker.py`.
3. **Extract Business Logic**: Move risk and execution functions into `risk_manager.py` and `trade_executor.py`.
4. **Extract Signal & Streaming**: Shift the core bot logic to `signal_evaluator.py` and `websocket_manager.py`.
5. **Clean up `main.py`**: Remove the extracted functions and leave only the bootstrapper logic.
6. **Testing**: Leverage test suites to ensure `bot/main.py` functional parity during each extraction step.
