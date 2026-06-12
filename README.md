# Binance Trade Bot 🚀

AI-powered cryptocurrency trading bot with real-time Binance Wallet Synchronization, Dynamic Position Sizing, and an elegant Glassmorphism web dashboard.

บอทเทรดคริปโตอัตโนมัติด้วยพลัง AI (Gemini) พร้อมระบบซิงค์ยอดเงินจริงจาก Binance, ระบบคำนวณการเข้าซื้ออัตโนมัติ (Dynamic Position Sizing) และหน้าเว็บ Dashboard สไตล์ Glassmorphism ที่สวยงาม

## Features (ฟีเจอร์เด่น)
- **Event-Driven WebSocket Architecture:** `bot/main.py` utilizes a `ThreadedWebsocketManager` to stream live prices directly from Binance without hitting rate limits. The bot engine communicates with the `api/server.py` backend via an authenticated internal webhook (`POST /api/internal/broadcast`) rather than legacy file polling. (สถาปัตยกรรมแบบ Event-Driven ใช้ WebSocket ดึงราคาจาก Binance โดยตรงแบบไร้ดีเลย์ และเชื่อมต่อกับ API ภายในผ่าน Webhook แทนการอ่านไฟล์)
- **Multi-Coin Support:** Trades BTC, ETH, XRP, SOL, and BNB simultaneously. (รองรับการเทรด 5 เหรียญพร้อมกัน)
- **AI Sentiment Analysis:** Uses Gemini AI to read recent crypto news and evaluate risk before buying. (ใช้ AI ช่วยอ่านข่าวและประเมินความเสี่ยงก่อนตัดสินใจเข้าซื้อ)
- **Trend Following Strategy:** Uses MACD and SMA-200 on a 1-hour timeframe. (กลยุทธ์ตามเทรนด์ด้วย MACD และเส้นค่าเฉลี่ย SMA 200 บนกราฟ 1 ชั่วโมง)
- **Robust State Recovery:** Syncs live with your Binance Spot Wallet to detect manual trades and network dropouts. (ซิงค์ยอดเงินจริงจากบัญชีเพื่อกู้คืนสถานะ ป้องกันเน็ตหลุด)
- **Real-Time Web Dashboard:** Includes a "Live Positions" table displaying real-time PNL ($ and %) via WebSocket updates, execution logs, and token-based authentication. (หน้าเว็บแบบ Real-time แสดงตารางกำไร/ขาดทุน (PNL) ของไม้ที่กำลังถืออยู่ พร้อมระบบยืนยันตัวตน)

## Getting Started (การติดตั้งและใช้งาน)
1. Configure `.env` with your Binance API keys and Dashboard login credentials. (ตั้งค่า API Key และรหัสผ่านหน้าเว็บในไฟล์ `.env`)
2. Run the Dashboard API: `uvicorn api.server:app --reload` (รัน API Server สำหรับหน้าเว็บ)
3. Run the Bot Core: `python -m bot.main` (รันตัวบอทเทรดหลัก)

## Versioning (ประวัติการอัปเดต)
See [CHANGELOG.md](CHANGELOG.md) for the detailed version history and patch notes. (ดูประวัติการอัปเดตทั้งหมดได้ที่ไฟล์ CHANGELOG.md)
