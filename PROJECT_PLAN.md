# Project Plan: Binance Trading Bot Enhancements

## Goals
1. **Fee Calculation**: Extract exact trading fees and execution prices directly from Binance API `fills`.
2. **Timezone Fix**: Correct the 7-hour discrepancy caused by SQLite stripping timezone info from UTC timestamps.
3. **PNL Tracking**: Calculate Profit and Loss (PNL) in both USD amount and percentage for all SELL trades. Maintain a cumulative profit record.
4. **Win/Loss Stats**: Calculate and display Win Rate percentage and Win/Loss counts.
5. **UI Improvements**: Fix the CSS truncation on the "AI Reasoning" text so it is fully readable, and display the new PNL/Stats data.
6. **Manual Sells**: Detect manual sells on Binance and log them in the database during the sync cycle so the UI stays up-to-date.

## Phases

### Phase 1: Database Schema Updates [x]
- **Target**: `bot/database.py` and existing `trades.db`
- Add new columns to the `trades` table:
  - `fee` (Float, nullable)
  - `fee_asset` (String, nullable)
  - `pnl_amount` (Float, nullable)
  - `pnl_percent` (Float, nullable)
- Update `TradeRepository.create_trade` to accept and save these new fields.

### Phase 2: Bot Core Execution Logic [x]
- **Target**: `bot/binance_client.py` and `bot/main.py`
- Modify `place_market_order` to parse the `fills` array from Binance. Calculate the true average fill price, total executed quantity, and total commission/fee.
- Modify `execute_trade` to:
  - Receive the enhanced execution data.
  - Calculate PNL for SELL orders by comparing the actual sell price against the average buy price stored in state (`buy_prices[symbol]`).
- In `sync_state_with_binance`, when a manual sell is detected (balance drops to zero), log it directly to the database using `TradeRepository.create_trade` with a custom "Manual SELL" reason, allowing the UI to reflect it.

### Phase 3: API & Server Adjustments [x]
- **Target**: `api/server.py`
- **Timezone Fix**: When serializing `t.timestamp`, explicitly append `tzinfo=timezone.utc` to the naive SQLite datetime before calling `.isoformat()`. This ensures the browser parses it as UTC and converts it to the user's local timezone (+7 hours).
- **Stats Calculation**: Create a new function `get_trade_stats(db)` to aggregate cumulative PNL, total wins, total losses, and win rate.
- Include these stats in the periodic WebSocket broadcasts (`status_update` or a new `stats_update`).
- Update `TradeSchema` to include the new DB fields.

### Phase 4: Dashboard UI Enhancements [x]
- **Target**: `dashboard/index.html`
- **CSS Fix**: Remove the `truncate` and `max-w-md` classes from the AI Reasoning column, replacing them with `whitespace-normal break-words max-w-xs` to allow multi-line reading.
- **PNL Display**: Add columns to the trade history table to show Fee and PNL (Amount & %).
- **Stats Header**: Add a top-level stats bar showing the Win Rate, Win/Loss count, and Cumulative Profit.
- Parse the UTC timestamps correctly to display the user's local time.
