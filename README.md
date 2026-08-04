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

## Versioning (ประวัติการอัปเดต)
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes. (ดูประวัติการอัปเดตทั้งหมดได้ที่ไฟล์ CHANGELOG.md)
