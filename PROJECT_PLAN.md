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
