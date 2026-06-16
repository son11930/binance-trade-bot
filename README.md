# Binance Trade Bot 🚀 (v4.2.0)

AI-powered cryptocurrency trading bot with Cloud PostgreSQL persistence, real-time Binance Wallet Synchronization, Dynamic Position Sizing, API Security (SlowAPI), and an elegant Glassmorphism web dashboard.

บอทเทรดคริปโตอัตโนมัติด้วยพลัง AI (Gemini) พร้อมฐานข้อมูลคลาวด์ PostgreSQL, ระบบซิงค์ยอดเงินจริงจาก Binance, ระบบคำนวณการเข้าซื้ออัตโนมัติ (Dynamic Position Sizing), ระบบความปลอดภัย API ขั้นสูง (Rate Limit) และหน้าเว็บ Dashboard สไตล์ Glassmorphism ที่สวยงาม

## Features (ฟีเจอร์เด่น)
- **Cloud Database Persistence:** Seamlessly connects to Aiven PostgreSQL to ensure your trade history and system logs are safe, accessible everywhere, and ready for multi-server scaling. (ใช้ฐานข้อมูล PostgreSQL บนคลาวด์ ป้องกันข้อมูลหายและรองรับการขยายตัว)
- **Event-Driven WebSocket Architecture:** `bot/main.py` utilizes a `ThreadedWebsocketManager` to stream live prices directly from Binance without hitting rate limits. The bot engine communicates with the `api/server.py` backend via an authenticated internal webhook. (สถาปัตยกรรมแบบ Event-Driven ใช้ WebSocket ดึงราคาจาก Binance โดยตรงแบบไร้ดีเลย์)
- **20-Coin Ecosystem:** Trades top 20 L1/DeFi tokens simultaneously on a fast-paced 15-minute timeframe, strictly excluding Meme coins for signal reliability. (รองรับการเทรด 20 เหรียญ L1/DeFi ชั้นนำพร้อมกัน บนความละเอียด 15 นาที เพื่อลดความผันผวนของเหรียญมีม)
- **AI Sentiment & Dynamic Sizing:** Uses an AI Committee powered by Gemini to read recent crypto news specific to the target asset, evaluate risk, and dynamically size the position (10%-40%) before buying. (ใช้ AI ช่วยอ่านข่าวแบบเจาะจงรายเหรียญเพื่อประเมินความเสี่ยงและกำหนดสัดส่วนเงินลงทุนให้เหมาะสมอัตโนมัติ)
- **Near Miss Tracking & Safe Mode:** Trend following with MACD, SMA-200, and dynamic RSI Filters. Actively tracks and logs "Near Misses" (why a trade wasn't executed) to allow UI filtering. (กลยุทธ์ตามเทรนด์พร้อมฟิลเตอร์ RSI แบบไดนามิก มีการแทร็กข้อมูลสาเหตุการไม่เข้าซื้อเพื่อช่วยในการวิเคราะห์และพัฒนากลยุทธ์)
- **Robust State Recovery:** Syncs live with your Binance Spot Wallet to detect manual trades and network dropouts. (ซิงค์ยอดเงินจริงจากบัญชีเพื่อกู้คืนสถานะ ป้องกันเน็ตหลุด)
- **Real-Time Secure Web Dashboard:** Includes a "Live Positions" table displaying real-time PNL via WebSocket updates, 24-hour debug execution logs, SlowAPI rate limiting, and token-based JWT authentication. (หน้าเว็บแบบ Real-time แสดง PNL พร้อมระบบกรอง Log 24 ชม. และระบบป้องกันการยิง API ด้วย SlowAPI)

## Getting Started (การติดตั้งและใช้งาน)
1. Configure `.env` with your Binance API keys and Dashboard login credentials. (ตั้งค่า API Key และรหัสผ่านหน้าเว็บในไฟล์ `.env`)
2. Run the Dashboard API: `uvicorn api.server:app --reload` (รัน API Server สำหรับหน้าเว็บ)
3. Run the Bot Core: `python -m bot.main` (รันตัวบอทเทรดหลัก)

## Versioning (ประวัติการอัปเดต)
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes. (ดูประวัติการอัปเดตทั้งหมดได้ที่ไฟล์ CHANGELOG.md)
