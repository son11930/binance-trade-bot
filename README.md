# Binance Trade Bot 🚀 (v4.0.0)

AI-powered cryptocurrency trading bot with Cloud PostgreSQL persistence, real-time Binance Wallet Synchronization, Dynamic Position Sizing, and an elegant Glassmorphism web dashboard.

บอทเทรดคริปโตอัตโนมัติด้วยพลัง AI (Gemini) พร้อมฐานข้อมูลคลาวด์ PostgreSQL, ระบบซิงค์ยอดเงินจริงจาก Binance, ระบบคำนวณการเข้าซื้ออัตโนมัติ (Dynamic Position Sizing) และหน้าเว็บ Dashboard สไตล์ Glassmorphism ที่สวยงาม

## Features (ฟีเจอร์เด่น)
- **Cloud Database Persistence:** Seamlessly connects to Aiven PostgreSQL to ensure your trade history and system logs are safe, accessible everywhere, and ready for multi-server scaling. (ใช้ฐานข้อมูล PostgreSQL บนคลาวด์ ป้องกันข้อมูลหายและรองรับการขยายตัว)
- **Event-Driven WebSocket Architecture:** `bot/main.py` utilizes a `ThreadedWebsocketManager` to stream live prices directly from Binance without hitting rate limits. The bot engine communicates with the `api/server.py` backend via an authenticated internal webhook. (สถาปัตยกรรมแบบ Event-Driven ใช้ WebSocket ดึงราคาจาก Binance โดยตรงแบบไร้ดีเลย์)
- **10-Coin Ecosystem:** Trades BTC, ETH, XRP, SOL, BNB, ADA, AVAX, DOGE, DOT, and LINK simultaneously on a fast-paced 15-minute timeframe. (รองรับการเทรด 10 เหรียญพร้อมกัน บนความละเอียด 15 นาที)
- **AI Sentiment Analysis:** Uses an AI Committee (Bullish, Bearish, Chief Strategist) powered by Gemini to read recent crypto news specific to the target asset and evaluate risk before buying. (ใช้ AI 3 ตัวช่วยอ่านข่าวแบบเจาะจงรายเหรียญเพื่อประเมินความเสี่ยงและถกเถียงกันก่อนเข้าซื้อ)
- **Safe Mode Strategy:** Trend following with MACD, SMA-200, and RSI Filter to prevent overbought entries. Includes Take Profit tiers, Trailing Stops, and Dynamic ATR Stop Loss. (กลยุทธ์ตามเทรนด์ด้วย MACD + SMA 200 พร้อมเพิ่มตัวกรอง RSI กันติดดอย และระบบจัดการความเสี่ยงแบบจัดเต็ม)
- **Robust State Recovery:** Syncs live with your Binance Spot Wallet to detect manual trades and network dropouts. (ซิงค์ยอดเงินจริงจากบัญชีเพื่อกู้คืนสถานะ ป้องกันเน็ตหลุด)
- **Real-Time Web Dashboard:** Includes a "Live Positions" table displaying real-time PNL ($ and %) via WebSocket updates, execution logs, and token-based JWT authentication. (หน้าเว็บแบบ Real-time แสดงกำไร/ขาดทุน (PNL) พร้อมระบบยืนยันตัวตนความปลอดภัยสูง)

## Getting Started (การติดตั้งและใช้งาน)
1. Configure `.env` with your Binance API keys and Dashboard login credentials. (ตั้งค่า API Key และรหัสผ่านหน้าเว็บในไฟล์ `.env`)
2. Run the Dashboard API: `uvicorn api.server:app --reload` (รัน API Server สำหรับหน้าเว็บ)
3. Run the Bot Core: `python -m bot.main` (รันตัวบอทเทรดหลัก)

## Versioning (ประวัติการอัปเดต)
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes. (ดูประวัติการอัปเดตทั้งหมดได้ที่ไฟล์ CHANGELOG.md)
