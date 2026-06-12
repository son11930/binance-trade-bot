# Changelog

## [3.0.0] - 2026-06-12
### Architecture & Performance (สถาปัตยกรรมและประสิทธิภาพ)
**English:**
- Migrated dashboard from HTTP Polling to real-time WebSockets with "Auth-on-Connect".
- Optimized frontend CSS by removing GPU-heavy backdrop-filters and using hardware acceleration.
- Eliminated Uvicorn infinite restart loop by moving bot state to `tmp/` directory.
- Refactored database logic to use `TradeRepository` pattern.
- Fixed `LOT_SIZE` precision errors when placing live market orders on Binance.
- Solved O(N²) API rate limit vulnerability during portfolio value calculation.
- Fixed `backtest.py` script to support the new MACD + SMA strategy.

**Thai (ภาษาไทย):**
- อัปเกรดระบบหน้าเว็บจากการยิงโหลดซ้ำๆ (Polling) เป็น WebSockets ที่รับส่งข้อมูลแบบ Real-time แท้จริง
- ปลดล็อกภาระการ์ดจอ (GPU) โดยลบโค้ด CSS แอนิเมชันที่กินสเปคสูงออกและใช้ Hardware Acceleration
- แก้บั๊กเว็บเซิร์ฟเวอร์ Uvicorn รีสตาร์ทตัวเองรัวๆ จนกิน CPU i7 โดยย้ายไฟล์สถานะไปไว้ที่ `tmp/`
- ปรับโครงสร้างระบบฐานข้อมูลให้ใช้มาตรฐาน `TradeRepository`
- แก้ปัญหาทศนิยม (LOT_SIZE) ที่ทำให้บอทซื้อเหรียญจริงไม่ได้
- แก้โค้ดรันทดสอบย้อนหลัง (Backtest) ให้รันกับกลยุทธ์ MACD ตัวใหม่ล่าสุดได้แล้ว
## [2.1.0] - 2026-06-12
### Security & System Hardening (ความปลอดภัยและเสถียรภาพ)
**English:**
- Implemented secure token-based authentication for the web dashboard.
- Protected API endpoints (`/api/status`, `/api/trades`) with Bearer token authorization.
- Fixed a critical state corruption bug where API timeouts would wipe Stop-Loss history.
- Resolved SQLite database connection leaks by wrapping queries in `try...finally`.
- Implemented atomic file writes for `bot_state.json` to eliminate frontend crash loops.
- Added localized error handling in the main loop to prevent single-coin failures from crashing the entire trading cycle.

**ภาษาไทย:**
- เพิ่มระบบยืนยันตัวตนด้วยรหัสผ่านและ Token สำหรับหน้าเว็บ Dashboard ป้องกันการเข้าถึงโดยไม่ได้รับอนุญาต
- ล็อคความปลอดภัยให้ API ป้องกันการถูกดึงข้อมูลยอดเงินและประวัติการเทรด
- แก้ไขบั๊กร้ายแรง: ป้องกันบอทล้างข้อมูลจุดตัดขาดทุน (Stop-loss) หากระบบเน็ตเวิร์คของ Binance ขัดข้องชั่วคราว
- อุดรอยรั่วการเชื่อมต่อฐานข้อมูล (Database Connection leaks) เพื่อให้รันบอทระยะยาวได้โดยไม่กินแรม
- ปรับปรุงการอ่าน/เขียนไฟล์สถานะบอท (Atomic Write) เพื่อแก้ปัญหาหน้าเว็บค้างหรือ Error
- เพิ่มระบบจัดการ Error แยกรายเหรียญ: หากระบบดึงข้อมูลเหรียญหนึ่งไม่สำเร็จ บอทจะยังคงเทรดเหรียญอื่นต่อไปได้โดยไม่หลุดวงจรการทำงาน

## [2.0.0] - 2026-06-12
### Added
- Multi-coin support (BTC, ETH, XRP, SOL, BNB).
- Live Binance Wallet Synchronization (Auto-Resume functionality).
- SQLite Database (`trades.db`) for robust state recovery across reboots.
- Premium Glassmorphism UI with real-time AI Status polling (2s intervals) and Live USDT tracking.
- Dynamic Position Sizing (Compounding 5-Tranche system using 20% of total equity).

### Changed
- Strategy updated from Mean Reversion (RSI + BB) to Trend Following (MACD + SMA 200 on 1H timeframe) based on backtest results.
- Moved away from simulated local memory balancing to fetching real API balances.

## [1.0.0] - 2026-06-10
### Initial Release (เวอร์ชันเริ่มต้น)
**English:**
- Initial prototype of the AI Crypto Bot.
- Mean Reversion strategy using RSI and Bollinger Bands.
- Single-coin trading support (BTC).
- Simulated paper-trading logic using local memory variables.
- Basic terminal-based logging.

**ภาษาไทย:**
- ปล่อยบอทเทรดคริปโตพลัง AI เวอร์ชันต้นแบบ
- ใช้กลยุทธ์ Mean Reversion (RSI + Bollinger Bands)
- รองรับการเทรดแบบเหรียญเดียว (BTC)
- ใช้ระบบจำลองเงินกระเป๋าจำลอง (Paper Trading) เก็บข้อมูลไว้ในหน่วยความจำชั่วคราว
- แสดงผลการทำงานผ่าน Terminal เบื้องต้น
