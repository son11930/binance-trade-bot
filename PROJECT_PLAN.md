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

## Phase 6: Operational Enhancements & Deployment (Current Focus)
Ensure the bot is easy to deploy, update, and manage in production environments.

1. **Auto-Update Mechanism**:
   - Integrated `git fetch` and `git pull origin main` into `start.bat` and `start.sh` so the system automatically pulls the latest code before starting.
2. **VPS Deployment Documentation**:
   - Created `UBUNTU_VPS_DEPLOYMENT.md` providing step-by-step instructions for installing dependencies, cloning the repository, and setting up the bot as a background service via `systemd` on an Ubuntu VPS.
