# Binance Trade Bot 🚀 (v4.6.0)

AI-powered cryptocurrency trading bot with a massively parallel **CUDA GPU Strategy Evolution Lab**, Cloud PostgreSQL persistence, real-time Binance Wallet Synchronization, Dynamic Position Sizing, API Security (SlowAPI), and an elegant Glassmorphism web dashboard.

บอทเทรดคริปโตอัตโนมัติด้วยพลัง AI (Gemini) ที่มาพร้อม **ห้องแล็บจำลองกลยุทธ์บนการ์ดจอ (GPU CUDA)**, ฐานข้อมูลคลาวด์ PostgreSQL, ระบบซิงค์ยอดเงินจริงจาก Binance, ระบบคำนวณการเข้าซื้ออัตโนมัติ (Dynamic Position Sizing), ระบบความปลอดภัย API ขั้นสูง และหน้าเว็บ Dashboard สไตล์ Glassmorphism ที่สวยงาม

## Features (ฟีเจอร์เด่น)
- **🚀 Massive GPU Strategy Synthesizer:** Numba CUDA kernels capable of evaluating millions of genome parameters per second across 20 symbols simultaneously. (รัน Backtest กลยุทธ์นับล้านรูปแบบต่อวินาทีด้วยสถาปัตยกรรมขนานบนการ์ดจอ CUDA)
- **🧬 AI Evolution Engine (Optuna):** Employs Tree-structured Parzen Estimator (TPE) via Optuna to automatically hunt for the best multi-strategy threshold genes. Protected by an Exploration Floor and Niche Preservation rules to maintain genetic diversity. (ใช้ AI ค้นหาค่า Parameter เทรดที่ดีที่สุดแบบอัตโนมัติ พร้อมระบบป้องกันการผูกขาดของสายพันธุ์)
- **⚔️ 12-Strategy Arsenal:** Built-in multi-strategy support ranging from RSI Sniper, MACD Momentum Surge, to Supertrend Riders. The AI automatically allocates budgets and deduplicates redundant behaviors. (รองรับกลยุทธ์ 12 รูปแบบที่ AI สามารถเลือกหยิบมาผสมผสานและเทรนให้เก่งที่สุดได้)
- **🛡️ Walk-Forward Validation:** Strict 70/30 In-Sample/Out-Of-Sample data splitting with hard state resets to actively penalize and reject overfitted models. (ระบบป้องกัน AI ท่องจำกราฟ โดยแบ่งข้อมูลทดสอบและวัดผลแยกกันอย่างเด็ดขาด)
- **☁️ Cloud Database Persistence:** Seamlessly connects to Aiven PostgreSQL/SQLite to ensure your trade history, system logs, and Optuna study trials are safe and accessible. (ใช้ฐานข้อมูลบนคลาวด์ ป้องกันข้อมูลและผลการเทรน AI สูญหาย)
- **⚡ Event-Driven WebSocket Architecture:** `bot/main.py` utilizes a `ThreadedWebsocketManager` to stream live prices directly from Binance without hitting rate limits. (สถาปัตยกรรมแบบ Event-Driven ใช้ WebSocket ดึงราคาจาก Binance โดยตรงแบบไร้ดีเลย์)
- **🌐 20-Coin Ecosystem:** Trades top 20 L1/DeFi tokens simultaneously on a fast-paced 15-minute timeframe. (รองรับการเทรด 20 เหรียญ L1/DeFi ชั้นนำพร้อมกัน บนความละเอียด 15 นาที)
- **🧠 AI Sentiment & Dynamic Sizing:** Uses Gemini to read recent crypto news specific to the target asset, evaluate risk, and dynamically size the position (10%-40%). (ใช้ AI ช่วยอ่านข่าวแบบเจาะจงรายเหรียญเพื่อกำหนดสัดส่วนเงินลงทุน)
- **🔒 Robust State Recovery & Safe Mode:** Syncs live with your Binance Spot Wallet to detect manual trades and network dropouts. Actively tracks and logs "Near Misses". (ซิงค์ยอดเงินจริงจากบัญชีเพื่อกู้คืนสถานะ และมีระบบบันทึกสาเหตุการพลาดโอกาสเข้าซื้อ)
- **💻 Real-Time Secure Web Dashboards:** Includes a "Live Positions" dashboard and a newly added **"GPU Strategy Lab"** dashboard displaying real-time AI evolution, genomes generated per second, and leaderboard rankings via WebSocket updates. (หน้าเว็บแบบ Real-time แสดงทั้งพอร์ตปัจจุบัน และสถานะการเทรน AI แบบสดๆ)

## Getting Started (การติดตั้งและใช้งาน)
1. Configure `.env` with your Binance API keys and Dashboard login credentials. (ตั้งค่า API Key ในไฟล์ `.env`)
2. Run the Dashboard API: `uvicorn api.server:app --reload` (รัน API Server สำหรับหน้าเว็บ)
3. Run the Bot Core: `python -m bot.main` (รันตัวบอทเทรดหลัก)
4. (New) Run the GPU Lab: `python scripts/run_benchmarks.bat` (รันห้องแล็บจำลองกลยุทธ์ AI)

### Lab trading-cost assumptions

The AI Lab reports returns after the configured taker fee and ATR-based execution allowance. It defaults to the conservative profile (`0.10%` per side, `0.20%` round trip) so frequent trading is not made to look artificially profitable. Choose the target market explicitly when needed:

```text
LAB_MARKET_TYPE=futures       # 0.05% taker fee per side
LAB_MARKET_TYPE=spot          # 0.10% taker fee per side
LAB_MARKET_TYPE=conservative  # 0.10% taker fee per side (default)
```

If the Binance account has a verified fee tier, `LAB_TAKER_FEE_RATE_PER_SIDE` can override the profile with the decimal rate (for example, `0.0004`). Use the same cost-model settings on the lab machine and the dashboard server. Historical funding, partial fills, latency, and order-book impact are not available in the candle-only lab, so paper-trade a candidate before enabling live execution.

### Execution lanes and Lab audit

Spot and Futures each expose independent Paper and Live execution controls. Paper can run while the server-side Live unlock is off; Live remains paused until a validated LIVE manifest and explicit server unlock are present. Every queued order is checked again at the execution boundary, so a pause or manifest change invalidates stale work. Protective exits remain available for an existing position. The dashboard's `PAPER` / `LIVE DATA` selector changes telemetry only and never grants order permission.

The Lab audit panel separates generated, screened, TPE samples, mutants, exploratory mutants, full evaluations, qualified candidates, rejected full evaluations, the retained archive, and published leaderboard rows. Per-strategy counters make it possible to confirm that strategy families outside the visible leaderboard were sampled and evaluated; old snapshots without this telemetry are shown as unavailable until a new checkpoint is written.

## Versioning (ประวัติการอัปเดต)
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes. (ดูประวัติการอัปเดตทั้งหมดได้ที่ไฟล์ CHANGELOG.md)
