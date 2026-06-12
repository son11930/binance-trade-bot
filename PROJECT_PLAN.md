# Project Plan: Debug UI & Bot Logging System

## Goal
Implement a real-time Debug UI on the web dashboard to monitor the trading bot's actions, errors, and Binance rejections.

## Architecture
Since `bot/main.py` (the trading engine) and `api/server.py` (the dashboard backend) run in separate processes, we will use the shared SQLite database (`trades.db`) as the communication bridge.
- **Bot**: Will log events (INFO, WARNING, ERROR) to a new `system_logs` table.
- **API Server**: Will continuously poll the `system_logs` table and broadcast new entries to the frontend via WebSockets.
- **Frontend**: Will display these logs in a dedicated "System Debug Log" terminal-like panel.

## Phases
1. **Data Layer**: Extend `bot/database.py` with a `SystemLog` table and a helper repository.
2. **Bot Logging**: Route `print()` and `logging.error()` statements in `main.py` and `binance_client.py` to the database.
3. **API Broadcasting**: Extend `api/server.py`'s background broadcaster to stream new logs to connected WebSocket clients.
4. **UI Integration**: Add the Debug panel to `dashboard/index.html`.

## Constraints & Rules
- Minimal performance overhead: Logs should be fetched efficiently (LIMIT 100).
- Robust error handling: DB insertions must not crash the bot.
- Real-time updates: Must use the existing WebSocket connection.
