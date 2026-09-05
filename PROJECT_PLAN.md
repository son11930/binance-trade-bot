# Project Plan: Market Regime Detector & Multi-Strategy System

## Objective
Enhance the existing trading bot, which currently relies solely on a MACD trend-following strategy, by introducing a dynamic **Multi-Strategy System**. The AI will act as a **Market Regime Detector**, routing trading decisions to the most appropriate strategy (Trend vs. Sideways) based on current market conditions. 

Additionally, ensure robust system debug logging is visible on the frontend dashboard to monitor these dynamic strategy shifts and log system events.

## Phase 1: Regime Detection Setup
To properly identify the market regime, we need to introduce volatility and trend strength indicators.

1. **Implement ADX (Average Directional Index)**:
   - Used to measure the strength of a trend.
   - **Condition**: ADX > 25 indicates a strong trend; ADX < 25 indicates a ranging/sideways market.
2. **Implement Bollinger Bands**:
   - Used to identify volatility and mean-reversion points.
   - **Condition**: Narrowing bands (low BBW) indicate consolidation; wide bands indicate trend/volatility.

## Phase 2: Strategy Arsenal Expansion
We will refactor `bot/strategy.py` to support multiple distinct strategies.

1. **Trend Strategy (MACD + SMA 200)**:
   - *Regime*: ADX > 25.
   - *Logic*: (Current Logic) Buy on MACD crossover when Price > SMA 200.
2. **Sideways/Mean Reversion Strategy (RSI + Bollinger Bands)**:
   - *Regime*: ADX < 25.
   - *Logic*: Buy when price hits the Lower Bollinger Band and RSI < 30. Sell when price hits Upper Bollinger Band or RSI > 70.
3. **Capital Preservation Strategy**:
   - *Regime*: Price strongly below SMA 200 + Bearish AI Sentiment.
   - *Logic*: Strictly HOLD or tight trailing stops.

## Phase 3: AI Market Regime Detector (The Decision Loop)
Integrate the AI into the core decision-making loop to select the active strategy.

1. **Data Gathering**: `bot/main.py` calculates ADX, Bollinger Bands, MACD, and RSI.
2. **AI Regime Analysis**: Feed the current technical data (ADX, RSI, price vs SMA) and recent news sentiment to the AI via `bot/ai_engine.py`.
3. **AI Output**: The AI outputs a JSON response identifying the `regime` ("TRENDING", "SIDEWAYS", "BEARISH") and `confidence_score`.
4. **Strategy Routing**: Based on the AI's determined regime, `bot/main.py` routes the dataframe to the corresponding strategy function.

## Phase 4: Debug UI & Real-Time Logging (Verification)
Ensure the system logs are adequately captured and broadcasted.
- Verify `bot/database.py` `SystemLog` table captures strategy routing events.
- Verify `api/server.py` broadcasts `logs_update` over WebSockets.
- Verify `dashboard/index.html` displays the `debug-log-container` correctly.

## Phase 5: 3-Agent "AI Committee" Feature & UI Overhaul
Evolve the single AI decision-maker into a multi-agent debate system to improve risk assessment.

1. **Frontend Layout Redesign (Current Focus)**:
   - Replace the single "Live AI Status" box with a premium glassmorphism 3-column layout.
   - Visually represent three agents: **Bullish Analyst**, **Bearish Analyst**, and **Chief Strategist**.
   - Show individual risk scores, status (thinking/idle), and the final consolidated decision.
   - Use high-end visual cues (glowing borders, pulsing animations, avatars/icons).
2. **Backend Committee Implementation (Future)**:
   - Refactor `bot/ai_engine.py` to prompt three distinct personas.
   - Combine their outputs into a single JSON response containing individual reasoning and the Chief Strategist's final verdict.
3. **WebSocket Integration (Future)**:
   - Update `api/server.py` to broadcast the new committee data structure.
   - Update the UI Javascript to parse and display the live debates and scores.

## Phase 6: Operational Enhancements & Security Remediation

1. **Auto-Update Mechanism**: 
   - Add `git fetch origin main` and `git pull origin main` to `start.bat` and `start.sh` to automatically update the codebase on startup.
2. **Ubuntu VPS Deployment**:
   - Create `UBUNTU_VPS_DEPLOYMENT.md` providing step-by-step instructions for deploying via `systemd` on a 3 Core, 3GB RAM VPS.
3. **Security Audit Remediation**:
   - Replaced static SHA256 auth tokens with expiring JSON Web Tokens (JWT) for dashboard access.
   - Refactored login system to use bcrypt password hashing instead of plaintext string comparisons.
   - Prevented memory leak DoS on login endpoint by enforcing periodic IP cleanup.
4. **Code Quality & Stability Overhaul**:
   - Decoupled the synchronous AI sentiment analysis from the WebSocket callback using background threads to prevent stream blocking and dropped frames.
   - Refactored `evaluate_strategy_for_symbol` to remove deep nesting.
   - Fixed silent error swallowing in the crypto news fetch loop.

## Phase 7: Frontend UI/UX Modernization (Current Focus)
The trading logic and cloud architecture have matured significantly. The next objective is to transform the `dashboard/index.html` interface into a highly premium, state-of-the-art web application.

1. **Design System & Aesthetics**:
   - Implement a cohesive, curated HSL dark mode color palette with smooth gradients.
   - Upgrade typography to modern Google Fonts (e.g., 'Inter' or 'Outfit').
   - Enhance the existing glassmorphism (glass-card) with subtle micro-animations and glowing hover effects to make the interface feel responsive and alive.
2. **Component Redesign**:
   - Revamp the AI Committee cards (Bull, Bear, Chief) with pulsing animations and better visual hierarchy.
   - Beautify the tables (Positions & Trades) with hover states, row highlights, and badge styling for PNL numbers.
   - Refine the System Debug Log container for better readability of critical events.

## Phase 8: Quantitative Strategy Optimization (Agent Trade Review)
After monitoring the bot over a 2-day period with the new 20-coin universe on 15m intervals, the system correctly identified 781 valid structural setups (333 Trend, 448 Sideways). However, 0 trades were executed due to overly restrictive secondary parameters.
- **Goal:** Safely recover missed high-probability setups by implementing dynamic thresholds rather than static caps.
- **Trend Strategy:** Shift the absolute `RSI < 65` limit to a dynamic `RSI < 75` bound when accompanied by a volume surge > 3x average volume.
- **Sideways Strategy:** Shift the static `RSI <= 30` oversold trigger to an "RSI Hook" logic turning up from `<= 40`, and slightly relax the volume requirement.
- **AI Enhancement:** Feed `Volume_Surge_Multiplier` into the `ai_engine.py` context so the Chief Strategist can mathematically justify high-momentum breakouts without flagging them as false overbought signals.

## Phase 9: Near Miss Tracking & Production Security
After relaxing strategy thresholds, the system requires better observability of "Near Miss" trading opportunities and stricter API security for production stability.

1. **Near Miss Log Filter**:
   - Implemented a detailed reason-tracking feature returning strings like "RSI_TOO_HIGH" or "NO_VOLUME_SURGE".
   - Added a "Show Near Miss Logs" toggle in the Dashboard UI to filter these high-frequency events out of the main view unless actively debugging.
2. **24-Hour Logs Persistence**:
   - Optimized database queries to fetch `SystemLog` entries from the last 24 hours.
   - Live WebSocket `SystemLog` broadcast limit scaled to 1000 rows.
3. **API Security & Rate Limiting**:
   - Integrated `slowapi` to enforce strict rate limits on `/api/login` (5/minute) to prevent brute force attacks.
   - Restricted `/api/ws` concurrent connections to 20 per IP.
   - Removed generic `*` CORS origins and allowed dynamic configuration via `.env` (`ALLOWED_ORIGINS`).

## Phase 10: Hybrid Query Log Optimization
Due to performance issues with sending high-frequency "Queued" and "Order Book Check" events via WebSocket (which caused payload bloat), we implemented a Hybrid Query approach. 
1. The database continues to store all events completely intact.
2. The `api/server.py` queries critical logs (aborts, errors, trades) over a 24-hour window, but limits noisy logs (queued, order book checks) to a 1-hour window.
3. The WebSocket limit is reverted to 1000 rows to ensure snappy UI loading, while still technically spanning 24+ hours of relevant critical history.

## Phase 11: Dual-Engine Architecture (Spot & Futures)
The system will be upgraded to a concurrent Dual-Engine architecture, running both Spot and Futures trading bots simultaneously.
- **Goal**: Run Spot (15m) and Futures (5m) bots simultaneously.
- **Database Separation**: Databases must be completely and clearly separated (using `DATABASE_URL_SPOT` and `DATABASE_URL_FUTURES` or separate schemas/DBs, not just a column).
- **UI/UX Dashboard**: Implement a unified web dashboard that visually separates Spot and Futures with tabs or toggles, ensuring data on the UI never mixes.
- **Futures Logic**: Support Long/Short positions, use 3x Leverage, ISOLATED margin, and aim for high APY (no grid bot).
- **Core Engine Upgrade**: Refactor `bot/main.py`, `bot/binance_client.py`, and `bot/trade_executor.py` to route and manage dual execution paths independently.

## Phase 12: TDD Stabilization & Live PNL Accuracy (Completed)
- **Goal**: Restore the test suite to 100% passing after major async/sync threading refactors, and fix UI PNL delays.
- **TDD Restored**: Fixed deep mocking issues in `pytest` where `_execution_pool.submit` was running real threads and breaking synchronous state assertions.
- **PNL Calculation Shift**: The system now locally calculates the exact PNL %, Margin, and Fee instantly at the time of execution. It no longer waits for Binance's delayed REST API.
- **UI Expansion**: Added Margin (USDT) and Fee columns to the Execution Log. Removed the deprecated AI Risk column to clean up the dashboard.

## Phase 13: UI Refinements & Security Hardening (Completed)
- **Goal**: Reduce dashboard lag, fix minor fee accounting bugs, and patch security vulnerabilities.
- **Performance**: Reduced polling latency from 60s to 5s.
- **Accounting**: Enforced 0.01 USDT minimum fee and swapped availableBalance for marginBalance to correctly calculate capacity.
- **Security**: Handled dictionary injection vulnerability in Webhooks and masked Binance exception payloads from the dashboard UI.

## Phase 14: Enhanced Data Sources & Intelligent Prompts
To make the AI committee smarter for both Spot and Futures trading, the bot will transition from relying solely on RSS news to analyzing quantitative market context.

1. **Alternative Data Integration**:
   - Refactor `bot/news_worker.py` into a robust `market_context_worker.py`.
   - **Binance API**: Fetch Funding Rates, Open Interest (OI), and Long/Short Ratios to gauge leverage and smart money positioning.
   - **Alternative APIs**: Fetch the daily Crypto Fear & Greed Index.
2. **AI Prompt Upgrades**:
   - Update `bot/ai_engine.py` to inject `funding_rate`, `ls_ratio`, and `fear_greed` into the XML prompt context.
   - Instruct the AI to act as a Quantitative Analyst, actively looking for Contrarian signals (e.g., Extreme Greed + High Positive Funding Rate = High risk of a Long Squeeze / Bearish outlook).
   - Adapt the output schema to support `LONG`, `SHORT`, or `HOLD` decisions specifically for the Futures engine.
3. **State Management**:
   - Expand `StateManager` to cache these metrics asynchronously, ensuring the main trading loop and AI evaluation remain unblocked.

## Phase 15: Data Ingestion Pipeline & Multi-Source News Aggregation
To prevent token limits from blowing up while scaling alternative news sources, we will implement a 3-Layer Architecture.
1. **Layer 1 (Data Collectors)**: Run asynchronous fetchers (CryptoPanic, RSS, Twitter KOLs) that save raw data to a database.
2. **Layer 2 (Processing & Filtering)**: Deduplicate stories, tag entities (e.g. BTC, ETH), and assign an `Impact Score` using a fast/cheap local NLP model (e.g. Groq).
3. **Layer 3 (AI Evaluation)**: The main `ai_engine.py` will query only the top 3 highest-impact news items (in bullet points) for the relevant coin, saving tokens while improving signal-to-noise ratio.

## Phase 17: Stability, Security, and Performance Optimization (Subagent Review)
Based on direct audits by dedicated Code, Security, and Performance subagents, the architecture requires critical optimization:
1. **Parallel Execution**: `market_context_worker.py` loops over 20+ symbols synchronously (4 APIs each). This will be refactored to use `concurrent.futures.ThreadPoolExecutor`. In `ai_engine.py`, the `Bull` and `Bear` agents will be executed in parallel.
2. **Lock Starvation Prevention**: Removed `time.sleep()` from within the `GROQ_API_LOCK` block to prevent thread freezing across the entire application.
3. **Prompt Injection Defense**: All user/external RSS news data is encapsulated in XML `<news_data>` tags with strict system instructions to ignore embedded commands.
4. **SRP Refactor**: Decoupling `fetch_crypto_news` into `bot/news_client.py` and API fetchers into `bot/binance_client.py`.

## Phase 18: Fixing Trade Direction & Entry Logic
- **Goal**: Prevent the bot from chasing trends and entering trades at structural extremes.
- **Action**: Modified bot/strategy.py to enforce Pullback entries (price within 1.5% of EMA50) and dynamic RSI regime bounds for Bear/Bull markets.
- **Status**: Completed.

## Phase 19: Hybrid Capped ATR Trailing Stop & Momentum Exit
- **Goal**: Prevent the bot from giving back too much profit on Futures trades during reversals (eliminating the wide 1.5%-3% gaps in the old step ladder), while still allowing profits to run in massive trends.
- **Action**: Combine the Momentum Exit (Sniper) with a Hybrid Capped ATR Trailing Stop. The new trailing stop will dynamically adapt to volatility (ATR) but strictly enforce a floor (e.g. 0.8%) and a cap (e.g. 1.2%) on the trailing distance.
- **Status**: Completed.

## Phase 20: API Rate Limit & Weight Management
- **Goal**: Prevent the VPS IP from being banned by Binance (HTTP 418/429/403) by dynamically tracking API weights and respecting rate limits.
- **Action**: Implement global exception handling to intercept Binance API limits. Track `X-MBX-USED-WEIGHT-1M`, respect `Retry-After` headers, and automatically pause the bot's REST API polling when nearing the 6,000 limit.
- **Status**: Planning.

## Phase 21: Advanced AI Learning System
- **Goal**: Upgrade the AI to a Self-Improving Autonomous System by learning from missed opportunities and past wins.
- **Action**: 
  - Add `AIDecision` table to the database to track all HOLD decisions.
  - Create `opportunity_tracker.py` to retroactively grade past HOLD decisions by pulling historical klines, marking them as Missed Opportunities or Good Blocks.
  - Create `global_memory_agent.py` to summarize daily market outcomes into `global_memory.txt` (detecting Spoofing and Macro Trends).
  - Update AI Prompts to inject recent winning trades and global memory.
  - Implement Discord notification webhook for Missed Opportunities.
- **Status**: Completed.

## Phase 22: Migration to 30m Timeframe & High-Accuracy Snipe Entries
- **Goal**: Reduce false positive signals and prevent the bot from opening trades against strong resistance by migrating to a more stable 30m timeframe and enforcing strict momentum/trend indicators.
- **Action**:
  - Update all historical data fetches and WebSocket streams from `15m` to `30m`.
  - Fix Long trend definition bug (enforce `ema_50 > sma_200` to prevent buying in a macro downtrend).
  - Integrate `MA(99)` as a strict support/resistance filter. Do not Long under it; do not Short over it.
  - Enforce `ADX > 25` to filter out sideways chop markets.
  - Expand Stop Loss multiplier to `1.2 ATR` to align with the larger 30m candle wicks.
- **Status**: Completed.

## Phase 23: Production-Grade Core Engine Refactoring & Simplification
- **Goal**: Refactor and simplify the core trading engine (`bot/strategy.py`, `bot/risk_manager.py`, `bot/signal_evaluator.py`, `bot/websocket_manager.py`) to improve maintainability, eliminate dead code, and break down complex if-else blocks into clean modular helper functions (<50 lines per function, <800 lines per file), while enforcing **100% zero regression of mathematical and trading invariants** for System 3 (30m V-Shape Sniper + 4-Gear Trailing Stop + `FUTURES_30M_EXIT` + AI Council + safe PnL extraction).
- **Critical Invariants**:
  1. Zero deviation in trading behavior: Every entry condition, macro filter, 4-Gear trailing stop threshold, and RSI hook exit must produce identical signals and backtest metrics.
  2. Test-Driven Development (TDD): Run automated unit tests and backtest simulation (`python test_30m_multiperiod.py`) before and after every phase.
  3. Clean modular architecture: Every helper function must be <50 lines, and every file must remain <800 lines.
- **Execution Phases**:
  - **Step 1: TDD Stabilization & Baseline Verification**: Update legacy unit tests in `tests/test_risk_manager.py` to reflect current System 3 invariants (removing obsolete time limit assertions and aligning 3x leverage expectations). Verify 100% unit test pass rate and record baseline metrics from `python test_30m_multiperiod.py`.
  - **Step 2: Strategy Modularization (`bot/strategy.py`)**: Remove unused variables (`macd_prev`, `sig_prev`). Decompose `analyze_futures_market` by extracting structural pattern recognition into focused helper functions (`_check_liquidity_sweeps`, `_check_rsi_divergence`, `_check_sma200_rejections`).
  - **Step 3: Risk Manager Simplification (`bot/risk_manager.py`)**: Decompose `check_spot_risk_management` and `check_futures_risk_management` into modular helpers (`_check_dynamic_sl_tp`, `_check_gear1_rsi_sniper`, `_check_gears_2_3_4_trailing`, `_check_fallback_stop`).
  - **Step 4: Signal Evaluator Decoupling (`bot/signal_evaluator.py`)**: Eliminate code duplication between Spot and Futures in `_evaluate_buy_signal` and `_evaluate_futures_trade_signal` by extracting modular domain helpers (`_check_trading_paused`, `_build_ai_tech_context`, `_process_ai_decision`, `_check_slippage_guard`, `_calculate_futures_position_size`, `_execute_reversal_exit`).
  - **Step 5: WebSocket Manager Cleanup (`bot/websocket_manager.py`)**: Clean up nested risk monitoring blocks in `process_kline_message` by extracting indicator extraction (`_extract_kline_indicators`) and async trade closure helpers (`_execute_risk_close_async`).
- **Status**: Completed.

## Phase 24: Evolutionary Strategy Synthesizer & AI Strategy Lab (Human-in-the-Loop Quant Workflow)
- **Goal**: Create an automated R&D Alpha Lab running locally on Windows across all 20 symbols defined in `bot/config.py`. It discovers, evolves, and evaluates Strategy Genomes (Trend DNA, Momentum Gate DNA, Entry DNA, Exit DNA) across 4 Time Horizons (1M, 3M, 6M, 1Y).
- **Architecture & Workflow**:
  1. **Alpha Feature Library (`bot/indicators_library.py`)**: A standalone library of 15-20 technical indicators (Supertrend, Ichimoku, Parabolic SAR, Keltner, StochRSI, MFI, CCI, Williams %R, Donchian, VWAP, OBV, Chaikin, BB Width) isolated from production code.
  2. **Safe Auto-Downloader (`bot_strategy_synthesizer.py`)**: Automatically fetches missing 1-year 30m klines from Binance's public endpoint with rate-limiting (`time.sleep(0.3)`) to guarantee zero IP bans.
  3. **Aiven DB Leaderboard Integration**: Pushes Top 10 discovered strategy blueprints to our existing Aiven MySQL/PostgreSQL/SQLite database into a lightweight `strategy_leaderboard` table (~5 KB size, zero live bot interference).
  4. **Interactive AI Strategy Lab UI (`dashboard/`)**: Adds an "🧬 AI Strategy Lab" tab to the web dashboard. Displays comparative Leaderboard Cards with 1M/3M/6M/1Y net profits, win rates, drawdowns, Strategy DNA code blocks, and a "📋 Copy AI Command" button for safe Human-in-the-Loop deployment.
  5. **Subagent Verification**: Upon completion, invoke parallel subagents (`code-reviewer`, `security-reviewer`, `performance-optimizer` / `trade-strategist`) to audit the implementation.
- **Status**: Completed.

## Phase 25: Refactoring GPU Strategy Synthesizer into a Dedicated Modular Package (`strategy_lab/`)
- **Goal**: Refactor our monolithic `bot_strategy_synthesizer_gpu.py` (~2,056 lines) into a clean, modular Python package inside a dedicated folder (`strategy_lab/`) to reduce file complexity (<800 lines per file, <50 lines per function), save token overhead, keep the workspace organized, and guarantee 100% zero regression of mathematical and trading invariants.
- **Module Architecture (`strategy_lab/`)**:
  - `strategy_lab/__init__.py` (~20 lines): Package entrypoint exposing `run_gpu_synthesizer_lab`.
  - `strategy_lab/config.py` (~100 lines): Package constants (`N_CPU_WORKERS`, `CUDA_THREADS_PER_BLOCK`, `GENOME_BATCH_SIZE`, `HORIZON_BARS`, `FEATURE_ORDER`, `GENOME_PARAM_ORDER`, `STRAT_MAP`, `MACRO_MAP`), file paths (`CACHE_DIR`, `DASHBOARD_DATA_DIR`), and logger setup.
  - `strategy_lab/data_loader.py` (~140 lines): Historical kline cache loading (`_load_and_cache_symbol`), NumPy array conversion (`_df_to_arrays`, `_build_symbol_arrays_for_cpu`), and GPU VRAM pre-loading/flat packing state (`preload_all_symbols_to_gpu`, `_pack_symbols_to_flat_gpu`, `_GPU_DEVICE_ARRAYS`, `_GPU_FLAT_DATA`).
  - `strategy_lab/gpu_kernel.py` (~320 lines): CUDA/Numba/CuPy hardware detection (`GPU_AVAILABLE`, `CUPY_AVAILABLE`), Numba JIT device kernels (`_backtest_kernel`, `_mega_backtest_kernel`), and startup compilation warmup (`_warmup_mega_kernel`).
  - `strategy_lab/cpu_kernel.py` (~130 lines): Pure Python/NumPy multi-core fallback simulation logic (`simulate_strategy_genome_cpu`, `_cpu_eval_from_arrays`).
  - `strategy_lab/fitness.py` (~150 lines): The 4-Pillar Practical Fitness Framework grading (`_apply_four_pillar_fitness`), matrix aggregation (`_compute_fitness_from_matrix`), vectorized batch grading (`_vectorized_batch_compute_fitness`), and genome parameter packing (`_pack_genomes_to_flat`).
  - `strategy_lab/evaluator.py` (~160 lines): Kernel orchestration and PCIe data transfer bridging (`_batch_gpu_backtest`, `_mega_batch_gpu_backtest`, `evaluate_genome_gpu`).
  - `strategy_lab/leaderboard_sync.py` (~130 lines): SQLAlchemy models and DB connection pooling (`StrategyLeaderboard`, `_get_db_engine`), thread-safe progress logging (`save_lab_progress_gpu`), Aiven PostgreSQL Top 10 sync (`push_leaderboard_to_db_and_json_gpu`), and genome deduplication (`get_deduplicated_top10_gpu`).
  - `strategy_lab/evolution_engine.py` (~320 lines): Optuna TPE study configuration (`InMemoryStorage`, `TPESampler`, `MedianPruner`), genome parameter space definition (`_build_genome_from_trial`), genetic mutation/crossover loop, and main execution orchestrator (`run_gpu_synthesizer_lab`).
- **Backward Compatibility Guarantee**:
  - Preserve `bot_strategy_synthesizer_gpu.py` in the root directory as an ultra-lightweight ~35-line executable wrapper that parses CLI arguments (`stop`, trial counts, infinite mode) and calls `run_gpu_synthesizer_lab()` from `strategy_lab`.
  - Ensures zero modification required for `run_strategy_lab_gpu.bat`, PowerShell process monitoring (`Win32_Process`), or taskkill termination scripts.
- **5-Step TDD & Zero Regression Verification Protocol**:
  - **Step 1 (Baseline Snapshot)**: Create automated regression test suite (`tests/test_gpu_lab_regression.py`) BEFORE refactoring. Run against monolithic `bot_strategy_synthesizer_gpu.py` on fixed test genomes across all 4 horizons (1M, 3M, 6M, 1Y). Record exact floating-point outputs for PnL %, win rate, max drawdown, total trades, and 4-Pillar fitness score to 6 decimal places (`1e-6` tolerance).
  - **Step 2 (Modular Implementation)**: Extract and move functions file-by-file into `strategy_lab/` adhering strictly to high cohesion and low coupling (no circular imports).
  - **Step 3 (Automated Regression Verification)**: Point `tests/test_gpu_lab_regression.py` to `strategy_lab` modules. Run `pytest -v` and verify `np.testing.assert_allclose(..., rtol=1e-6)` passes with 100% zero deviation.
  - **Step 4 (Integration & E2E Verification)**: Execute wrapper `python bot_strategy_synthesizer_gpu.py 2` and check that `gpu_lab.log`, `lab_progress.json`, `strategy_leaderboard.json`, and Aiven PostgreSQL DB sync execute cleanly without errors or memory leaks.
- **Status**: Completed.

## Phase 26: Modular Refactoring & Optimization of Web Dashboard (`dashboard/js/`)
- **Goal**: Decompose the monolithic frontend script `dashboard/app.js` (~779 lines, ~46 KB) into a clean, modular JavaScript package inside `dashboard/js/` to improve code readability, maintainability, and token efficiency, strictly enforcing the project's `<800 lines max (200-400 lines typical)` rule and guaranteeing **100% Zero Regression** in UI interactivity, WebSocket auto-reconnection, AI Council rendering, and live Strategy Lab progress polling.
- **Module Architecture (`dashboard/js/`)**:
  - `dashboard/js/config_utils.js` (~50 lines): Global state/constants (`currentMarket`, `ws`, `token`, `isPaused`), HTML escaping (`escapeHTML`), and global error logging handler (`window.onerror`).
  - `dashboard/js/auth.js` (~60 lines): Session authentication, login/logout workflows, and JWT token storage.
  - `dashboard/js/websocket.js` (~100 lines): WebSocket lifecycle management, automatic reconnect loop, heartbeat pings, and message routing to UI renderers.
  - `dashboard/js/bot_control.js` (~80 lines): Bot pause/resume controls (`fetchBotControl`, `togglePause`, `updatePauseUI`), market switching (`setMarket`), and app startup initialization (`startApp`).
  - `dashboard/js/ui_status.js` (~120 lines): Rendering AI Council cards, Market Context banner, 4-Gear Trailing Stop status, and account balance indicators (`updateStatusUI`).
  - `dashboard/js/ui_trades.js` (~130 lines): Rendering Spot and Futures trade tables, delta deduplication, PnL badge formatting, and trade history updates (`updateTradesUI`).
  - `dashboard/js/ui_logs.js` (~80 lines): Rendering real-time system log terminal (`renderLogsUI`) and periodic performance stat summaries (`renderStatsUI`).
  - `dashboard/js/ui_lab.js` (~200 lines): Rendering the AI Strategy Lab tab, live animated progress banner (`fetchLabProgress`), Top 10 leaderboard cards (`fetchLeaderboard`), and safe index-based Copy AI Command workflow (`copyAICommandFromIndex`).
- **Backward Compatibility Guarantee**:
  - Load modules sequentially via standard `<script src="js/...">` tags in `dashboard/index.html` (or maintain a lightweight `app.js` entrypoint) to ensure zero CORS issues and 100% compatibility across all browsers and server environments without requiring Webpack/Vite build tools.
- **TDD & Zero Regression Verification Plan**:
  - **Step 1 (Automated Regression Verification)**: Run full Python pytest suite (`pytest tests/ -v`) to ensure server static file serving and API endpoints remain unaffected.
  - **Step 2 (Syntax & Linter Verification)**: Check JavaScript syntax across all new modules in `dashboard/js/` using Node/built-in validation to ensure zero runtime syntax errors.
  - **Step 3 (E2E & Human-in-the-Loop Review)**: Verify tab switching between Live Trading and AI Strategy Lab, check WebSocket real-time updates, and confirm Leaderboard card rendering.
- **Status**: Completed.

## Phase 27: Calmar-Ratio & Quadratic Drawdown Fitness Upgrade + Average Profit per Trade Metric
- **Objective**: Address critical real-world trading viability concerns where existing alpha strategies saturate at the +10,000% profit ceiling while exhibiting unacceptably high Max Drawdowns (50%–70%). Enhance the **Four Pillar Fitness Framework** to penalize high drawdown exponentially, reward capital preservation (Calmar Ratio), and introduce a transparent **Average Profit per Trade** (`avg_profit_per_trade`) metric to filter out dust-scalping strategies vulnerable to live fee/slippage drag.
- **Key Algorithmic Upgrades**:
  1. **Average Profit per Trade Metric**:
     - Compute `avg_profit_per_trade_pct = net_profit_1y / total_trades_1y` and `avg_profit_per_trade_dollar = net_profit_1y_dollar / total_trades_1y` across all backtest evaluators (`lab_gpu/fitness.py`, `lab_gpu/evaluator.py`, `lab_gpu/cpu_kernel.py`).
     - Expose these metrics in `strategy_leaderboard.json` and render a dedicated badge in the Web Dashboard (`dashboard/js/ui_lab.js`) so traders can immediately identify strategies with robust trade-level margins (> $1.00 or > 0.5% net per trade).
  2. **Calmar-Weighted Profit Scaling (Risk-Adjusted Return)**:
     - Replace linear profit summation with a Calmar-ratio decay curve for strategies exceeding a safe drawdown threshold (`SAFE_DD = 25.0%`).
     - If `max_dd_1y > 25.0%`, apply a profit scaling multiplier: `dd_factor = min(1.0, (25.0 / max_dd_1y) ** 1.5)`. This naturally slashes the profit score of high-drawdown strategies (e.g. a 70% drawdown slashes the profit score by ~80%), eliminating profit saturation.
  3. **Quadratic Drawdown Penalty (Institutional Risk Hurdle)**:
     - Upgraded from a mild linear penalty (`max_dd * 2.5`) to an exponential quadratic penalty when Max Drawdown exceeds 30.0%:
       `dd_penalty = (max_dd * 2.5) + ((max_dd - 30.0) ** 2 * 15.0)` for `max_dd > 30.0%`.
     - A strategy exhibiting 60% Max Drawdown will incur a ~13,650-point penalty, ensuring Optuna aggressively prunes risky genomes and evolves stable, institutional-grade strategies with Max Drawdown < 25%–30%.
- **Verification Plan**:
  - Update unit regression tests (`tests/test_gpu_lab_regression.py`) with the new mathematical formulas.
  - Run benchmark test (`python bot_strategy_synthesizer_gpu.py 100`) to confirm evolved Top 10 Alpha Blueprints exhibit significantly lower Max Drawdowns (< 30%) and high Average Profit per Trade.
- **Status**: Completed.

## Phase 28: GPU Lab Simulation Kernel Calibration (Intracandle Stop & In-Loop Fee Fix)
- **Objective**: Honor the user's core architecture principles: (1) **The 3-Agent AI Committee evaluates EVERY trade exactly as before without modification**, and (2) **We do NOT randomly adjust or hardcode trading strategy formulas manually**—the GPU Lab exists specifically to evolve and discover optimal parameters automatically! Eliminate the mathematical illusion in backtested win rates (~90%+) and returns (>10,000%) by correcting two critical simulation bugs inside `lab_gpu/gpu_kernel.py` and `cpu_kernel.py`. Once the lab's simulation engine is 100% mathematically realistic, Optuna will automatically evolve blueprints that are genuinely profitable under live 3x leverage without false assumptions.
- **Key Algorithmic Upgrades in Lab Kernel (`lab_gpu/gpu_kernel.py` & `cpu_kernel.py`)**:
  1. **Intracandle Stop Look-Ahead Fix**:
     - In the simulation continuation loop, reorder the evaluation sequence: check if candle Low (`l`) hits the existing stop loss (`sl_p`) **before** upgrading the stop loss using the current bar's High (`h`) or Close (`c`).
     - Previously, checking High first allowed the simulator to raise stop losses to breakeven/trailing before checking Low, artificially turning losing trades into trailing-stop winners and inflating backtest win rates to 90%+.
  2. **True In-Loop Fee Drag & Compounding**:
     - Deduct realistic Binance VIP0 Futures taker fee + slippage friction (`0.15%` round-trip) directly inside each trade's net return calculation before applying Kelly exponential compounding (`balance *= (1.0 + (pnl_pct_net * kelly * 4.0))`).
     - Previously, omitting fee deduction from inside the compounding loop allowed hyper-active scalping genomes to snowball equity exponentially without paying friction, fooling Optuna into ranking high-fee genomes as champions.
- **Verification Plan**:
  - Update unit regression suite (`tests/test_gpu_lab_regression.py`) to verify in-loop fee drag and correct stop-loss evaluation order.
  - Run GPU lab synthesis (`python bot_strategy_synthesizer_gpu.py 50`) to confirm that evolved Top 10 Alpha Blueprints reflect realistic, live-deployable win rates and ROI without mathematical inflation.
- **Status**: Completed.

---

### Phase 29: GPU/CPU Kernel Safety Clamping & Leaderboard Reset
- **Objective**: Prevent historical or mutated genomes from exploiting unbounded stop-loss upgrade parameters (such as `"gear4_breakeven_buffer_pct": 30.12133`), which previously set stop loss prices above entry by 3,000%+ ($93,000 on a $3,000 asset) and produced artificial 10,000%+ returns on the dashboard.
- **Key Algorithmic Upgrades**:
  1. **Kernel Safety Clamping**:
     - In `lab_gpu/cpu_kernel.py` and `lab_gpu/gpu_kernel.py` (`_backtest_kernel` and `_mega_backtest_kernel`), enforce strict safety limits when setting or upgrading stop loss prices: clamp `be_buf = min(be_buf, 0.02)` (maximum 2% breakeven buffer above entry) and enforce `sl_p = min(sl_p, c)` (or `if sl_p > c: sl_p = c`), ensuring a stop loss can never exceed the current market price.
  2. **Leaderboard & Database Cache Reset**:
     - Clear legacy corrupted historical champions from `dashboard/data/strategy_leaderboard.json` and sync a fresh leaderboard state to Aiven DB so Optuna does not re-enqueue obsolete +10,000% illusion genomes.
- **Verification Plan**:
  - Run regression test suite (`python -m pytest tests/test_gpu_lab_regression.py -v`).
  - Run full repository test suite (`python -m pytest tests/ -v`).
  - Run GPU lab synthesis (`python bot_strategy_synthesizer_gpu.py 50`) starting from a clean slate to verify realistic, live-deployable performance numbers on the dashboard.
- **Status**: Completed.

---

### Phase 30: Expand Strategy Synthesis Pool to 12 Elite Quant Engines
- **Objective**: Expand the GPU strategy evolutionary synthesizer from 8 entry core engines (`strat == 0..7`) to 12 institutional-grade quantitative engines (`strat == 0..11`), enabling exhaustive combinatorial synthesis across all major technical trading paradigms.
- **Key Algorithmic Upgrades**:
  1. **Add 4 New Institutional Trading Engines**:
     - `strat == 8`: `macd_momentum_surge` (MACD Histogram zero-cross surge + MACD line > signal line + volume confirmation).
     - `strat == 9`: `bollinger_squeeze_explosion` (Bollinger Bandwidth squeeze + Upper Band breakout + ADX momentum).
     - `strat == 10`: `parabolic_sar_vortex` (Parabolic SAR bullish flip + Vortex VI+ > VI- + MFI flow).
     - `strat == 11`: `fibonacci_golden_pullback` (Swing pullback into 50%–61.8% Fibonacci Golden Ratio zone during SMA 200 uptrend).
  2. **Data & Indicator Pipeline Integration**:
     - Update `bot/bot_strategy_synthesizer.py` (`calculate_all_indicators`) and `lab_gpu/data_loader.py` to compute and supply required arrays (MACD histogram, Bollinger upper/bandwidth, SAR, Vortex VI+/VI-, Fibonacci 20-bar swing levels) to VRAM float32 matrices.
  3. **Kernel Evolution & Strategy Synthesis**:
     - Extend `_backtest_kernel`, `_mega_backtest_kernel`, and `cpu_kernel.py` to evaluate strategies 0 through 11, combining them with multi-layer regime filters and 4-gear dynamic exits.
- **Verification Plan**:
  - Verify indicator array computation and matrix packing.
  - Run regression test suite (`python -m pytest tests/test_gpu_lab_regression.py -v`).
  - Run full repository test suite (`python -m pytest tests/ -v`).
- **Status**: Completed.

---

### Phase 31: Alpha Lab Profit Hurdle & Kelly Position Sizing Floor
- **Objective**: Eradicate an evolutionary optimization loophole where the genetic algorithm games win rate (~87%) and consistency bonuses by setting microscopic `kelly_fraction_cap` values (`0.0003` to `0.012`), yielding negligible real profit (`+0.18%` over 1 year). Enforce institutional position sizing floors and strict live profit hurdles.
- **Key Algorithmic Upgrades**:
  1. **Kelly Position Sizing Floor (`>= 0.20`)**:
     - Clamp `kelly_fraction_cap` between `0.20` and `0.40` across CPU kernel (`lab_gpu/cpu_kernel.py`), GPU kernel helper functions (`lab_gpu/evaluator.py`), and evolutionary mutation operators (`lab_gpu/evolution_engine.py`). Ensures every trade allocates 0.8x to 1.6x equity, maximizing returns under Binance Futures x3 leverage.
  2. **Real-World Profit Hurdles & Dominant Weighting**:
     - Upgrade `lab_gpu/fitness.py` (`_apply_four_pillar_fitness` and `_vectorized_batch_compute_fitness`). Tie the `+1000.0` point all-horizon consistency bonus to strict net profit hurdles (`net_profit_1y >= 15.0%`, `6m >= 8.0%`, `3m >= 4.0%`, `1m >= 1.0%`).
     - Introduce a severe kill-switch penalty (`-2500.0` pts) for any strategy yielding under +15% annual return across 20 symbols, and triple the weight of live net profit (`total_profit_live * 3.0`).
- **Verification Plan**:
  - Add regression test cases for low-profit penalties in `tests/test_gpu_lab_regression.py`.
  - Verify 100% test suite pass rate (`python -m pytest tests/test_gpu_lab_regression.py -v`).
- **Status**: Completed.

---

### Phase 32: VPS Log Flood & Disk Exhaustion Defense (Python Throttling, WebSocket Backoff, Linux Quotas)
- **Objective**: Prevent the critical disk exhaustion failure (`~100 MB / 4 mins` filling up the 29 GB Ubuntu VPS disk) caused by infinite `python-binance` websocket `Read loop has been closed` errors when websocket streams drop. Establish a defense-in-depth architecture across three distinct layers: (1) Python application log throttling, (2) WebSocket health monitoring with exponential backoff, and (3) Linux systemd/journald/logrotate rate limiting and disk quotas.
- **Key Architecture & Technical Upgrades**:
  1. **Python Throttled & Duplicate Logging Filter (`bot/utils/log_filter.py` & `setup_logging()`)**:
     - Implement `ThrottledLogFilter`, a `logging.Filter` attached to root and sub-loggers (`binance.streams`, `binance.websockets`).
     - Tracks message hashes/patterns (`Read loop has been closed`, `Error receiving message`) and suppresses repeated duplicates occurring within a 60-second window (`interval=60.0`).
     - Emits a periodic summary `[Suppressed X duplicate log entries in the last 60s for: '...']` when the suppression window resets, ensuring complete visibility without disk flooding.
  2. **WebSocket Graceful Reconnect & Health Monitor (`bot/websocket_manager.py` & `bot/main.py`)**:
     - Add `last_message_time` heartbeat timestamp to `WebSocketManager` (`spot` and `futures`) updated on every `24hrTicker` and `kline` frame received.
     - Replace static `twm.is_alive()` check in `bot/main.py` with an intelligent health check loop assessing both thread vitality and stream activity (`time.time() - max_last_message_time > 30s`).
     - When stream silence (`>30s`) or read loop errors occur, invoke clean reconnect sequence with exponential backoff (`backoff_delay = min(60, 5 * (2 ** attempt))`, starting at 5s up to 60s max) using safe `twm.stop()` and re-initialization rather than immediate hard restart (`os.execv`).
  3. **Linux Systemd, Journald, & Logrotate Quotas (`UBUNTU_VPS_DEPLOYMENT.md` & Live Server Configuration)**:
     - **Systemd Rate Limit**: Add `LogRateLimitIntervalSec=30s` and `LogRateLimitBurst=100` to `/etc/systemd/system/binance-bot.service` (`[Service]` block) to drop service output exceeding 100 lines/30 seconds.
     - **Journald Disk Quota**: Configure `/etc/systemd/journald.conf` with `SystemMaxUse=500M`, `SystemMaxFileSize=100M`, `SystemMaxFiles=5`, `RateLimitIntervalSec=30s`, `RateLimitBurst=1000`. Run `sudo journalctl --vacuum-size=500M` to reclaim disk space immediately.
     - **Logrotate Policy**: Create `/etc/logrotate.d/binance-bot` for `/var/log/syslog` and application logs enforcing daily rotation, `size 50M`, `rotate 7`, `compress`, and `missingok`.
- **Verification Plan**:
  - Run unit tests to verify `ThrottledLogFilter` suppresses duplicate strings and emits count summaries after window expiration (`pytest tests/test_log_filter.py -v`).
  - Verify WebSocket reconnect logic cleanly handles mock disconnection exceptions with exponential backoff.
  - Inspect remote VPS logs (`journalctl -u binance-bot.service -n 50`) and storage quotas (`df -h`, `journalctl --disk-usage`) via SSH/paramiko before and after applying configurations.
- **Status**: Completed.

---

### Phase 33: Strategy Robustness, Live Risk Controls, and Risk-First Dashboard

- **Objective**: วางแผนยกระดับ GPU strategy synthesizer ให้ค้นหา candidate ที่มีผลกำไรสุทธิและความสม่ำเสมอแบบ out-of-sample โดยมีความถี่รวมทั้งพอร์ต 1–10 trades/day พร้อมสร้าง promotion gate ก่อนนำกลยุทธ์ไปใช้จริง ปรับ hard risk/execution controls ของ live bot และปรับ Web Dashboard ให้แสดง equity, drawdown, exposure, cost และ data freshness ตามความจริง
- **Primary Engine Boundary**: `bot_strategy_synthesizer_gpu.py` และ `lab_gpu/` เป็นระบบหลักที่ใช้งานจริง ส่วน `bot_strategy_synthesizer.py` เป็น legacy CPU ที่เลิกใช้งานแล้ว จึงไม่ใช่ implementation หรือ parity target ของ Phase 33
- **Critical Planning Findings**:
  1. Search space มีประมาณ 80 genes แต่ GPU mega-kernel ใช้จริง 29 genes ทำให้ leaderboard ปัจจุบันเกิด duplicate phenotype และยังไม่พร้อมใช้เป็นหลักฐานสำหรับ live deployment
  2. ผล 1M/3M/6M/1Y มาจาก nested windows ที่ซ้อนกันและยังไม่มี untouched OOS/walk-forward validation
  3. Live position sizing ยังอิง allocation 10–40% จาก AI โดยไม่ผูกกับ stop distance และยังขาด portfolio/daily drawdown circuit breakers
  4. Protective stop ของ Futures อยู่ใน local process แม้มี exchange-native TP/SL helper อยู่แล้ว จึงต้องออกแบบ fail-closed protection และ fill reconciliation ก่อนเพิ่ม risk
  5. Dashboard ยังมี metric/status ที่อาจทำให้เข้าใจผิด เช่น hard-coded live state, stale lab progress และ PnL% ที่ไม่ใช่ portfolio return
- **Canonical Detailed Plan**: ดู `plam.md` สำหรับ capability contract, KPI gates, phased backlog, TDD/verification matrix, rollout/rollback criteria และ open decisions
- **Scope Boundary**: ระยะนี้เป็น planning/documentation และได้ดำเนินการตั้งค่า Baseline ใน Phase 0 แล้ว
- **Confirmed KPI / Risk Budget (2026-07-27)**:
  1. **Trade Counting**: นับแยกตาม engine (Spot และ Futures)
  2. **Risk Budget**: 20% max portfolio drawdown
  3. **Hedge vs One-way**: เลือก Mode ที่กำไรมากที่สุดตามข้อมูลจริง (Default: Hedge Mode สำหรับ Futures เพื่อลด conflict ทาง State หากมี Signal สวนทาง, หรือตาม backtest ที่ให้ PnL สูงสุด)
  4. **Cost Assumptions**: ตามจริงทั้งหมด (Maker 0.02%, Taker 0.05%, historical funding & slippage)
  5. **Data Availability**: ใช้ฐานข้อมูลเดิมวิเคราะห์ baseline 
  6. **Promotion Pipeline**: ลงเทรดจริง ไม่มี paper trading
  7. **Symbol Universe**: คงเดิมที่ 20 เหรียญ
  8. **Capital Allocation**: แยก Spot และ Futures อย่างชัดเจน
  9. **Approvals**: ทำด้วยมือโดยระบบผู้ใช้เพียงคนเดียว ไม่มีระบบ Auto-promote
- **Status**: **Phase 0 Baseline Frozen**. Moving to Phase 1 (GPU Main-Path Truth and Fallback/Production Conformance).

---

### Phase 34: GPU Throughput and Evidence-Based Live Readiness (Planning Handoff)

- **Objective**: เพิ่มความเร็วในการค้นหา strategy โดยวัด end-to-end throughput และ qualified candidates/hour พร้อมปิดช่องว่างด้าน search correctness, simulator parity, validation, execution safety และ staged rollout ก่อนใช้เงินจริง
- **Observed Baseline (2026-08-05)**:
  1. CUDA ทำงานจริงบน RTX 3070 และ mega-batch ขนาด 4,096 ทำ throughput ได้ประมาณ 330–334 genomes/วินาทีรวม I/O
  2. Task Manager ในภาพแสดงกราฟ 3D ไม่ใช่ CUDA/Compute จึงใช้ 0% เป็นหลักฐานว่า GPU ไม่ทำงานไม่ได้
  3. Default 100 trials สร้างเพียง 400 CUDA threads และ underfill GPU อย่างชัดเจน
  4. Search space มี 80 genes แต่ GPU ใช้ 29 genes; 51 genes ไม่มีผลต่อ fitness
  5. แต่ละ batch มี TPE ask/tell เพียง 32 จาก 4,096 candidates; raw trials จึงไม่ใช่ตัวชี้วัดคุณภาพ search
  6. Leaderboard/DB sync ถูกเรียกแทบทุก batch และบล็อก GPU pipeline
  7. Top 10 ปัจจุบันเป็น `williams_mean_rev` 10/10 พร้อมผลลัพธ์เหมือนกัน เป็น search collapse/behavioral duplication ไม่ใช่หลักฐานว่า Williams ชนะอย่างยุติธรรม
  8. PAPER/LIVE header toggle เป็น view filter เท่านั้น ขณะที่ Strategy Lab promotion buttons เขียน active manifest จริง
  9. Manifest stage และ global `PAPER_TRADING` เป็น mode authority สองชุดที่ขัดกันได้ ทำให้เกิด simulated-as-live record หรือ cross-mode exit/stop risk
- **Canonical Detailed Plan**: ใช้ `plam.md` ฉบับ 2026-08-05 เป็นเอกสาร handoff สำหรับ Luna โดยเริ่มจาก correctness/measurement gates ก่อน optimization และห้าม promote จาก leaderboard ไป LIVE โดยตรง
- **Immediate Priority**: Luna ต้องเริ่ม Phase 0A เพื่อปิด direct LIVE activation, รวม execution mode ให้เป็น single source of truth และเพิ่ม cross-mode safety tests ก่อน Phase 0 performance baseline
- **Scope Boundary**: planning/documentation only; ไม่มีการแก้ kernel, optimizer, live bot, configuration, process หรือ order ในรอบนี้
- **Status**: **Plan refreshed for Luna; Phase 0A implementation not started**

---

### Phase 35: Scoring Gradient and Qualified Strategy Recovery

- **Objective**: แก้กรณี GPU Strategy Lab ประเมิน genomes ต่อเนื่องแต่ `Best` ติดลบและ `Winners = 0` โดยทำให้ screening เป็นสัญญาณต่อเนื่อง, full evaluation ตรวจสอบได้ และ candidate ที่จะนำไป promotion มีหลักฐานจริง
- **Scope**: `lab_gpu/evaluator.py`, `lab_gpu/evolution_engine.py`, `lab_gpu/fitness.py`, `lab_gpu/config.py`, kernel parity, leaderboard/promotion evidence และ regression tests ที่เกี่ยวข้อง; ไม่เปลี่ยน execution-mode/risk controls ที่ทำเสร็จแล้ว
- **Required behavior**:
  1. ผล screening ต้องไม่ถูกแสดงเป็น full 1Y result และต้องแยก `screened`, `full_evaluated`, `qualified` อย่างชัดเจน
  2. Screening ต้องเก็บ top-K/continuous score เพื่อไม่ให้ optimizer เจอ zero-gradient เมื่อไม่มี candidate ผ่าน hard gate
  3. Mutation ต้อง clamp ด้วย typed per-gene bounds เดียวกับ search schema และห้ามใช้ failed-screen placeholder เป็น elite parent โดยไม่มีสถานะรองรับ
  4. Full evaluation ต้องทำกับ candidate ที่คัดเลือกตาม policy และต้องมี raw metrics/fitness ครบก่อนนับเป็น winner
  5. Promotion evidence ต้องอ้างอิง candidate identity/version/hash ไม่ใช่คะแนน placeholder หรือ rank ที่เปลี่ยนได้
  6. Historical rows ที่ไม่ qualified ต้องไม่ถูก enqueue หรือใช้เป็น parent ของ mutation รอบใหม่
- **TDD/verification**:
  - unit tests สำหรับ screening fallback, top-K retention, mutation bounds และ candidate status transitions
  - regression test ยืนยันว่า `Best` ที่มาจาก screening ไม่ถูกส่งออกเป็น full 1Y champion
  - integration test ยืนยันว่า full-evaluated candidate มี 1Y metrics/trade count ก่อนถูกนับเป็น qualified
  - benchmark แยก generated/screened/full-evaluated/qualified และตรวจ CPU/GPU raw-metric parity
- **Exit gates**:
  - ไม่มี placeholder candidate ถูกนับเป็น qualified หรือ promotion-ready
  - มี qualified-candidate rate และ score quantiles ที่วัดได้ แม้รอบหนึ่งยังไม่มี winner
  - mutation ทุก gene อยู่ใน schema bounds
  - regression suite ผ่านและ coverage ของส่วนที่แก้ไม่น้อยกว่า 80%
  - strategy ที่จะนำไปเทรดจริงต้องผ่าน validation/promotion gates เดิมครบ ไม่ใช้คะแนน search อย่างเดียว
- **Status**: **Implemented — focused verification passed; unrelated network-bound repository tests remain environment-blocked**

---

### Phase 36: Correct Backtest Signal Parity and Separated Trading Dashboard

- **Objective**: Restore non-zero, causally correct strategy evaluation and make any promoted strategy execute the same signal contract in paper/live modes.
- **Scope**: GPU/CPU kernel correctness, shared strategy-parameter normalization, realistic fee/slippage accounting, candidate validation metadata, promotion flow, and separate Spot/Futures/Lab dashboard pages.
- **Required behavior**:
  1. Volume, candle, spread, ATR, and trend filters must use the units implied by their schema and must not silently suppress every entry.
  2. CPU and GPU simulators must use the same feature indexes, stop/target ordering, position sizing, and end-of-window liquidation behavior.
  3. Lab-generated parameters must map to the live evaluator without strategy-name or threshold semantic drift.
  4. Search ranking must reward robust out-of-sample net returns after costs, but promotion must require complete evidence, minimum trades, bounded drawdown, and walk-forward checks.
  5. Paper promotion remains available; direct LIVE promotion is available only when explicit live permission, pause/open-position checks, and candidate evidence gates pass.
  6. Dashboard navigation must use separate routes/pages for Spot, Futures, and AI Lab instead of rendering all large views behind one tabbed page.
- **TDD/verification**:
  - regression tests for entry-filter liveness, ATR cost column, strategy parameter parity, and closed-trade metrics
  - API tests for candidate evidence and paper/direct-live promotion guards
  - dashboard structure tests for separate pages and route links
  - CPU/GPU parity test when CUDA is available and deterministic CPU smoke tests otherwise
- **Exit gates**:
  - default genomes produce diagnosable non-zero trade counts on valid fixture data, or an explicit no-signal reason is reported
  - no candidate with incomplete or stale evidence can reach paper/live promotion
  - tests pass for the changed modules and no secrets are added
- **Status**: **Completed — implementation and focused verification passed; full repository collection remains blocked by pre-existing network/database-dependent tests**

### Phase 37: Deployment and Runtime Verification

- **Objective**: Push the completed Phase 36 changes, restart the server through the approved project workflow, and verify the deployed dashboard and local GPU lab without enabling live orders.
- **Checks**: Git status/diff audit, `run_strategy_lab_gpu.bat`, dashboard route/API smoke checks, `restart_bot.bat`, and post-restart dashboard checks.
- **Safety**: Keep execution in PAPER/paused mode; do not place live orders during verification.
- **Status**: **Completed — pushed and verified on the server; local GPU launcher and remote service are healthy**

### Phase 38: Authenticated Dashboard Home and Clear Page Navigation

- **Objective**: Replace the root redirect with a real authenticated Home/Control Center so users can sign in, sign out, and reach Spot Engine, Futures Engine, and AI Strategy Lab through clear, consistent navigation.
- **Scope**: `dashboard/index.html`, shared dashboard header/navigation, authentication affordances, route handling, cache-busted dashboard assets, and responsive styling. Trading execution behavior remains unchanged and verification stays in PAPER/paused mode.
- **Required behavior**:
  1. `/index.html` must render a Home/Control Center and must not redirect directly to Spot.
  2. Every dashboard page must expose the complete primary navigation: Home, Spot Engine, Futures Engine, and AI Strategy Lab.
  3. Logged-out users must see an obvious sign-in form; logged-in users must see an obvious Sign out action that returns to the sign-in state.
  4. Home must summarize the available workspaces and keep live execution visibly server-gated.
  5. Asset URLs must be cache-busted so an older browser stylesheet/script cannot hide the navigation after deployment.
- **TDD/verification**:
  - dashboard structure regression tests for the Home route, navigation, auth markers, and cache-busted assets
  - JavaScript syntax checks and focused existing dashboard/API tests
  - deployed HTTP smoke checks for all routes/assets and unauthenticated API protection
- **Status**: **Completed — Home route, navigation/auth shell, focused tests, GPU run, push, restart, and deployed HTTP smoke verification passed**

### Phase 39: End-to-End Trading Fee Accounting

- **Objective**: Make strategy evaluation and monitoring reflect the cost of repeated trading by applying explicit entry/exit fees exactly once per completed trade and exposing the assumptions used.
- **Scope**: Lab cost model and CPU/GPU parity, fee-aware regression tests, paper/live fee-boundary audit, leaderboard/dashboard metric labels, and changelog documentation. Runtime paper/live execution remains separately gated; no live orders or live execution permission changes.
- **Required behavior**:
  1. Every backtest/OOS round trip deducts the configured fee plus execution-cost allowance exactly once; open positions are settled consistently at the evaluation boundary.
  2. CPU and GPU kernels produce identical fee-adjusted metrics and the fee assumptions are visible/auditable.
  3. The lab never substitutes its modeled fee for a realized exchange commission; paper/live execution remains separately gated and unchanged by this phase.
  4. Invalid, missing, or negative fee inputs fail safely and cannot improve a candidate's score.
- **TDD/verification**:
  - unit tests for fee math, boundary values, repeated trades, and no-double-charge behavior
  - CPU/GPU fee-adjusted parity regression
  - focused bot/accounting tests and a safe GPU smoke run without live orders
- **Exit gates**:
  - displayed net returns are net of documented fees/cost assumptions
  - no fee-related regression or metric inflation is observed
  - paper/live execution remains paused or paper-only during verification
- **Status**: **Completed — fee-aware lab metrics, evidence validation, dashboard visibility, focused tests, and safe GPU smoke verification passed; live execution was not enabled**

### Phase 40: Independent Paper/Live Controls and GPU Exploration Transparency

- **Objective**: Keep Paper Trading and Live Trading execution controls independent, and make GPU Lab exploration/leader retention observable so a small leaderboard cannot be mistaken for a small search.
- **Scope**: Shared execution control state/API, Spot/Futures dashboard control wiring, authorization and cross-mode safety tests, GPU search accounting/leaderboard diagnostics, and changelog documentation. No live orders are permitted during implementation or verification.
- **Required behavior**:
  1. Paper resume/stop changes only the paper runtime; Live resume/stop changes only the live runtime.
  2. Paper-only operation must be possible while the server-side live execution unlock remains off; a paper action must never enable live execution.
  3. Every control request must carry and validate its execution mode server-side; the UI cannot select or infer a different mode after the request is sent.
  4. GPU Lab must report generated, screened, full-evaluated, qualified, retained, and rejected counts separately, and show whether new genomes continue after historical leaders are loaded.
  5. Leaderboard display must distinguish retained top candidates from total exploration and must not imply that only the displayed rows were searched.
- **TDD/verification**:
  - API/control tests for mode isolation, invalid mode rejection, live-unlock gating, and idempotent stop/resume behavior
  - dashboard structure/wiring tests for distinct Paper and Live actions and status labels
  - GPU Lab tests for new-genome sampling, champion seeding, count accounting, and leaderboard metadata
  - focused syntax, regression, and safe paper-only smoke verification
- **Exit gates**:
  - Paper can be resumed and stopped without changing live state
  - Live remains blocked unless its explicit server-side unlock and evidence gates pass
  - Lab output exposes exploration counts and retained-leader limits
  - no live order is placed during verification
- **Verification**:
  - Focused execution/API/dashboard/fee/GPU regression suite: 72 passed, 1 skipped
  - Python compilation and dashboard JavaScript syntax checks passed
  - Local artifacts confirm the previous leaderboard's two visible rows were not the total search; the persisted Optuna study contains strategy-type observations across multiple families. New checkpoints now expose the same evidence directly in the Lab UI.
  - No live order was placed during verification
- **Status**: **Completed - independent execution lanes, Live UI metadata refresh, rejection/retention telemetry, and strategy-family exploration visibility implemented and verified**

### Phase 41: Execution Boundary and Lab Evidence Hardening

- **Objective**: Close the residual race windows identified during the Phase 40 security review before the separated controls and Lab telemetry are deployed to the server.
- **Scope**: order-boundary revalidation, immutable execution context checks, cross-process control locking, fail-closed pause persistence, protective-exit handling, promotion post-conditions, and unambiguous Lab run/family/archive counters.
- **Required behavior**:
  1. A queued or delayed order must revalidate its immutable market/mode/deployment context immediately before exchange submission; a pause or manifest change must invalidate the order.
  2. Paper and Live mode cannot be changed by a later manifest read inside an evaluator; the lane context remains authoritative and must match the state manager.
  3. Control updates from the API process and bot process are serialized across processes, and a failed safety pause is treated as a fail-closed condition.
  4. Pausing Live blocks new entries but does not suppress emergency exits/reconciliation for an already-open live position.
  5. Promotion verifies all required control post-conditions and leaves Live disarmed on any persistence mismatch.
  6. Lab telemetry initializes every strategy family, distinguishes family selection from exploratory mutation intensity, preserves truthful archive/published counts, and reports partial runs as stopped rather than completed.
  7. Exchange-confirmed fills cannot be mistaken for failed orders when journaling is unavailable; native protection and cancellation stay behind the same live lane boundary.
  8. A new Lab run clears the published snapshot and the API refuses unversioned or stale evidence for display and promotion.
  9. A confirmed fill that cannot be written to the trade database is durably journaled, reconciled before lane resume, and never replaced with requested-quantity fiction.
  10. Existing shared databases are upgraded with the fixed Lab telemetry columns before ORM reads/writes, because `create_all()` does not alter an already-created table.
- **TDD/verification**:
  - regression tests for pause/manifest invalidation at the order boundary and cross-process control updates
  - mode-context tests for both evaluator paths and protective-exit behavior
  - Lab tests for zero-count families, minimum family coverage, run status, archive/published counts, and rejected/full semantics
  - focused suite, Python/JavaScript syntax checks, and static no-live-order audit before Git deployment
- **Exit gates**:
  - no mocked exchange order is reached after a pause/context mismatch
  - Paper-only default remains available and Live remains fail-closed
  - Lab counters cannot be mistaken for leaderboard-card count
  - no live order is placed during verification
- **Verification**:
  - Focused execution/API/dashboard/fee/GPU hardening suite: 76 passed, 1 skipped; phase hardening subset: 25 passed
  - Python compilation, dashboard JavaScript syntax checks, and Git whitespace checks passed
  - Boundary regression tests confirm stale Paper/Live orders are refused, protective exits remain available, failed control writes latch fail-closed, confirmed fills are durably recoverable, native stops require verified exchange positions, cleanup failures remain `CLOSING`, and partial Lab runs are reported as stopped
  - Versioned leaderboard/progress tests confirm old snapshots cannot be served or promoted as current, while same-run snapshots use authoritative freshness and failed leaderboard writes are retried
  - GPU launcher smoke completed 100 genomes in 16 seconds with CUDA, 20/20 symbols, all 12 strategy families represented, schema 2 telemetry, and successful progress/leaderboard flush against the existing shared database schema
  - No live order was placed during verification
- **Status**: **Completed - execution boundary revalidation, cross-process control safety, promotion post-conditions, and transparent Lab telemetry implemented and verified**

### Phase 42: Explicit Futures Execution Lane Controls

- **Objective**: Remove the ambiguous market-wide Resume/Stop path so Futures Paper and Live execution are visibly and behaviorally separate, including when an older cached dashboard is still open.
- **Scope**: legacy control endpoint behavior, scheduler lane admission, dashboard control labels, static asset cache policy, regression tests, changelog, and safe deployment verification. No live orders are permitted.
- **Required behavior**:
  1. A control request that cannot identify PAPER or LIVE must not mutate execution state.
  2. Resuming Futures PAPER must admit only the staged, unpaused PAPER lane; LIVE must remain locked/paused unless its own explicit gates pass.
  3. The dashboard must expose only explicit Paper/Live controls and explain that telemetry and protective reconciliation are distinct from opening new positions; the validated strategy stage selects the lane that may open entries.
  4. HTML/JavaScript cache policy and asset versioning must prevent an older market-wide Resume button from changing execution state ambiguously after deployment.
- **TDD/verification**:
  - API tests for Paper-only resume, legacy endpoint rejection, and staged lane admission
  - dashboard structure tests for explicit controls, no legacy button/fallback, cache policy, and explanatory labels
  - Python compilation, JavaScript syntax checks, focused regression suite, web smoke, and paper-only runtime verification
- **Exit gates**:
  - no legacy market-wide endpoint can resume or unpause a lane
  - a Paper resume cannot schedule the Futures LIVE evaluator
  - no live order is placed during verification
- **Status**: **Completed - explicit lane admission, fail-safe emergency stop, effective pause handling, cache policy, regression suite, and deployment verification passed**

### Phase 43: Paper Promotion Evidence Parity

- **Objective**: Make the Paper Review promotion path accept the same immutable candidate evidence that the Lab UI displays, while keeping stale, tampered, or incomplete evidence rejected.
- **Scope**: Shared-database leaderboard row reconstruction, candidate artifact hashing, Paper promotion regression coverage, dashboard error clarity, and safe paper-only deployment verification. No live orders are permitted.
- **Required behavior**:
  1. A leaderboard snapshot read from the shared database must preserve the exact hash-bound evidence published by the Lab.
  2. Staging a qualified candidate to PAPER must succeed when the UI submits the candidate ID and artifact hash from the current snapshot.
  3. Candidate hashes, full-evaluation, qualification, fee-model, OOS, and run-freshness gates remain fail-closed.
  4. The recent-vs-long-horizon metrics must remain explicitly labeled as historical backtest evidence, not a live-profit guarantee.
- **TDD/verification**:
  - regression test for DB leaderboard evidence round-trip and Paper promotion
  - stale/tampered evidence rejection tests remain green
  - Python compilation, dashboard JavaScript syntax checks, focused API/evidence suite, and paper-only deployment smoke
- **Exit gates**:
  - Stage Paper Review works with the current DB-backed snapshot
  - invalid or stale candidate evidence is still refused
  - Live remains locked and no live order is placed during verification
- **Verification**:
  - DB-backed Paper promotion regression and the focused API/evidence/dashboard suite passed: 76 passed
  - Python compilation, dashboard JavaScript syntax checks, and Git whitespace checks passed
  - Local DB snapshot verification confirms the selected candidate hashes now match the Lab-published evidence
  - No live order was placed during verification
- **Status**: **Completed - DB evidence round-trip and Paper promotion hash parity fixed and verified; Live remained disarmed**

### Phase 44: Paper Promotion Manifest Storage Bootstrap

- **Objective**: Make Stage Paper Review work on a freshly deployed server where the ignored runtime manifest directory does not yet exist.
- **Scope**: promotion-route storage initialization, safe error responses, regression coverage, deployment smoke, and browser verification. No live orders are permitted.
- **Required behavior**:
  1. The Paper promotion route creates `dashboard/data` before reading or atomically writing `strategy_manifest.json`.
  2. Storage failures are logged server-side without exposing filesystem paths or exception details to the browser.
  3. Existing candidate evidence, pause, Paper/Live separation, and Live-unlock gates remain unchanged.
- **TDD/verification**:
  - regression test stages a DB-backed qualified candidate when the manifest directory is absent
  - focused promotion/API/security/dashboard tests, Python/JavaScript syntax checks, and Git whitespace checks
  - deploy/restart verification, authenticated Stage Paper Review browser smoke where the existing session permits, and no-live-order audit
- **Exit gates**:
  - Stage Paper Review succeeds on a clean runtime data directory
  - invalid/stale candidate evidence remains refused
  - Live remains locked and no live order is placed during verification
- **Verification**:
  - Missing-directory Paper promotion regression and focused API/evidence/fee/dashboard suite passed: 77 tests passed
  - Python compilation, dashboard JavaScript syntax checks, and Git whitespace checks passed
  - Commit `0614eee` was pushed; the restart workflow completed the server update, remote HEAD and `binance-bot.service` were verified, and all dashboard static pages returned 200
  - Authenticated browser smoke confirmed the qualified candidate can be staged to PAPER on the deployed server; the manifest is in PAPER stage, the page remained healthy, and no old path-leaking error appeared
  - Post-test controls remained `paper_trading=true`, `allow_live=false`, and both Live lanes paused; no live order was placed
- **Status**: **Completed - fresh-deployment manifest storage and safe Paper Review error handling verified; Live remained disarmed**

### Phase 45: Paper Runtime Recovery and Robust GPU Search

- **Objective**: Restore truthful Futures Paper operation when an effective market pause is active, and improve Lab throughput only where the speed change does not weaken cost-aware, out-of-sample validation.
- **Scope**: effective Paper/Live pause visibility, explicit Paper recovery behavior, GPU Lab benchmark instrumentation, search-vs-holdout separation, cost/regime/stability evidence, and regression coverage. Live execution remains locked and no live orders are permitted.
- **Required behavior**:
  1. The dashboard must show the effective execution state used by the scheduler, including a market-wide kill switch, rather than only the lane flag.
  2. Paper recovery must be explicit and authenticated; it may not clear Live pause/lock state or silently bypass safety controls.
  3. Lab search scores must not be presented as untouched OOS evidence; promotion evidence must remain full-evaluation, cost-aware, and holdout/fold aware.
  4. Any throughput optimization must preserve causal fills, fees/slippage/funding assumptions, full-evaluation coverage, family coverage, and reproducible run telemetry.
  5. Future-profit claims must be framed as uncertainty-managed evidence; no backtest result may be treated as a guarantee of future profit.
- **TDD/verification**:
  - tests for effective pause state, Paper-only recovery, Live fail-closed behavior, and stale/ambiguous controls
  - tests for search-score versus untouched holdout separation and cost-aware qualification
  - fixed-seed finite GPU benchmark with `Screened`, `Full`, `Qualified`, `Best full`, and per-family counters
  - focused execution/Lab tests, syntax checks, and no-live-order audit
- **Exit gates**:
  - Paper cannot be reported as running while the scheduler is effectively paused
  - Live remains locked and no live order is placed during verification
  - speed changes do not remove full validation or hide fee/slippage effects
  - no deployment is performed without an explicit deploy/restart request
- **Status**: **Completed locally - effective Paper recovery, IS-only search separation, launcher hardening, focused tests, and finite GPU verification passed; remote deployment remains a separate operator-approved step**
