## [4.1.0] - 2026-06-16
### AI Autonomous Allocation & 20-Coin Expansion
**English:**
- **Asset Universe Expansion**: Expanded the `SYMBOLS` scan list from 10 to 20 Top Cryptocurrencies (L1/DeFi), strictly excluding Meme coins to improve fundamental indicator reliability.
- **Dynamic AI Position Sizing**: Upgraded the AI `chief_prompt` to dynamically calculate and output a precise `allocation_percentage` based on Risk/EV evaluation.
- **Failsafe Circuit Breaker**: Implemented a mathematical boundary in `signal_evaluator.py` that intercepts the AI's allocation and strictly bounds it between a minimum of 10% and a maximum of 40% of total equity to prevent model hallucination risks.
- **Dashboard Log Scaling**: Increased the live WebSocket `SystemLog` broadcast limit from 50 to 500 rows to allow 1-2 days of observability on the frontend without impacting database performance due to O(1) B-Tree indexing.

**Thai (ภาษาไทย):**
- **ขยายตลาด 20 เหรียญ**: เพิ่มลิสต์สแกนเหรียญจาก 10 เป็น 20 เหรียญ (เน้นสาย L1/DeFi) และคัดเหรียญ Meme ออกทั้งหมดเพื่อให้กราฟนิ่งขึ้น
- **AI คุมเงินทุน (Dynamic Sizing)**: ปรับ Prompt ให้ AI คิดสัดส่วนการลงทุน (% ของพอร์ต) ให้เองตามความเสี่ยงที่วิเคราะห์ได้ในแต่ละรอบ
- **ระบบบอดี้การ์ดคุม AI**: เขียนโค้ดดักจับ % ที่ AI สั่งมา เพื่อป้องกันปัญหา AI หลอน โดยบังคับให้อยู่ในกรอบปลอดภัยคือ "ซื้อขั้นต่ำ 10% และสูงสุดไม่เกิน 40%" เสมอ
- **ขยายประวัติ Log**: ปรับ Backend ให้ส่งข้อมูล Debug Log ให้หน้าเว็บทีละ 500 บรรทัด (ดูย้อนหลังได้ 1-2 วัน) โดยไม่กระทบความเร็วเซิฟเวอร์


### Cloud Database & 10-Coin Ecosystem
**English:**
- **Cloud Database (Aiven PostgreSQL)**: Completely migrated the core database from local SQLite to Aiven PostgreSQL to ensure data persistence, scalability, and seamless deployment across multiple instances.
- **10-Coin Support**: Expanded the bot's trading capability from 5 to 10 highly liquid symbols (BTC, ETH, XRP, SOL, BNB, ADA, AVAX, DOGE, DOT, LINK).
- **Timeframe Optimization**: Shifted the mathematical analysis interval from 1 Hour down to 15 Minutes (15m), significantly increasing trade frequency to capitalize on micro-trends.
- **UI & Timezone Fixes**: Resolved a critical silent bug where `api.server.py` would default to an empty SQLite database due to an import order issue. Re-engineered timestamp parsing to ensure all dashboard logs display in localized local time instead of UTC.
- **Enhanced Log Observability**: Bootstrapped the bot to safely log directly to the remote Aiven Database with fail-safes and connected the web interface's "System Debug Log" directly to the cloud log repository.

**Thai (ภาษาไทย):**
- **เปลี่ยนผ่านสู่ระบบคลาวด์ (Aiven PostgreSQL)**: ย้ายฐานข้อมูลหลักจากไฟล์ SQLite ในเครื่อง ไปใช้ PostgreSQL บนคลาวด์ของ Aiven แบบเต็มรูปแบบ ป้องกันข้อมูลหายและรองรับการขยายตัวในอนาคต
- **ลุยตลาด 10 เหรียญ**: เพิ่มเหรียญที่บอทสามารถเทรดได้พร้อมกันเป็น 10 เหรียญ (BTC, ETH, XRP, SOL, BNB, ADA, AVAX, DOGE, DOT, LINK)
- **ปรับความไวเป็น 15 นาที**: ปรับความละเอียดของกราฟเทคนิคอลจาก 1 ชั่วโมง (1h) เป็น 15 นาที (15m) เพื่อเพิ่มโอกาสการเข้าทำกำไรที่รวดเร็วขึ้น
- **แก้บั๊กเวลาและฐานข้อมูล**: แก้บั๊กใหญ่ที่หน้าเว็บไม่ยอมดึงข้อมูลเพราะโหลดตัวแปร `.env` ผิดจังหวะ และแก้ระบบเวลาให้หน้าเว็บแปลงเป็น "เวลาไทย" อัตโนมัติ (ไม่ต้องทนดูเวลา UTC แล้ว)
- **ระบบ Log ทะลุเมฆ**: ปรับให้บอทส่งสถานะการทำงานทุกอย่างขึ้นไปเก็บไว้บน Aiven ทันที และให้หน้าเว็บดึงข้อมูลมาแสดงผลแบบ Real-time โดยไม่ผ่านไฟล์ในเครื่อง

## [3.7.1] - 2026-06-14
### Security & Code Quality Overhaul
**English:**
- **Authentication**: Replaced static SHA256 dashboard token with expiring JSON Web Tokens (JWT) for secure authentication.
- **Passwords**: Updated login system to use `bcrypt` password hashing instead of `.env` plaintext comparisons.
- **Rate Limit DoS Prevention**: Implemented IP cleanup mechanism to prevent memory leak DoS on login endpoint.
- **Asynchronous AI Evaluation**: Dispatched the blocking AI Sentiment Analysis to a background thread to prevent WebSocket disconnections during heavy Gemini API processing.
- **Error Handling**: Fixed silent error swallowing in the crypto news fetch loop.

**Thai (ภาษาไทย):**
- **ปรับปรุงระบบความปลอดภัย (JWT & Bcrypt)**: เปลี่ยนระบบ Token เป็นแบบ JWT ที่มีวันหมดอายุ และบังคับใช้การเข้ารหัสรหัสผ่านด้วย `bcrypt` แทนการอ่านข้อความธรรมดา
- **ป้องกันระบบล่ม (Anti-DoS)**: เพิ่มระบบล้างข้อมูล IP เก่าๆ บนหน้า Login ป้องกันคนสแปมจนเซิร์ฟเวอร์แรมเต็ม
- **แก้ปัญหาหลุดการเชื่อมต่อ (Async Threads)**: แยกส่วนของ AI ออกไปคิดใน Thread เบื้องหลัง เพื่อไม่ให้บล็อกการรับราคาแบบเรียลไทม์จาก Binance (ช่วยแก้ปัญหาบอทหลุด/ค้างบ่อย)
- **ระบบ Log ที่ดีขึ้น**: เพิ่มการแจ้งเตือน Error ชัดเจนเมื่อระบบดึงข่าวไม่สำเร็จ แทนที่จะข้ามไปเงียบๆ

## [3.7.0] - 2026-06-14
### Added
- **Auto-Update Mechanism**: Integrated `git fetch` and `git pull origin main` into `start.bat` and `start.sh` to automatically pull the latest code updates before starting the bot.
- **VPS Deployment Guide**: Added `UBUNTU_VPS_DEPLOYMENT.md` with step-by-step instructions for deploying the bot on an Ubuntu VPS, including Python venv setup and `systemd` background service configuration.

## [3.6.0] - 2026-06-13
### Added
- Implemented Time-Filtered PNL dashboard with 1D, 7D, 1M, and ALL options.
- Added Profit Percentage metric calculated dynamically against total capital used per timeframe.
### Security & Review
- Applied code-reviewer fixes to avoid AttributeError parsing timestamps and optimized loop passes.

## [3.5.0] - 2026-06-13
### Added
- Implemented robust AI Model Fallback mechanism in `bot/ai_engine.py` using `gemini-3.5-flash`, `gemini-3.1-flash-lite`, and `gemini-3.0-flash` to prevent rate limit crashes.
- Added prompt injection sanitization and API key masking in AI engine logs.

# Changelog

## [3.4.0] - 2026-06-13
### Strategy Safe Mode & Risk Management (ปรับกลยุทธ์ให้ปลอดภัยและทำกำไรสม่ำเสมอ)
**English:**
- **RSI Filter:** Added RSI (< 65) to the `analyze_market` strategy to prevent buying at overbought peaks.
- **Dynamic Risk Management:** Replaced fixed Stop Loss with dynamic ATR (Average True Range) calculations.
- **Take Profit & Trailing Stop:** Added a strict Take Profit at 3% and a Trailing Stop trigger at 1.5% profit, locking in gains.
- **Symbol-Specific AI Prompt:** Modified `analyze_sentiment` to evaluate news risk specifically for the target asset rather than generic Bitcoin sentiment.

**Thai (ภาษาไทย):**
- **เพิ่มตัวกรอง RSI:** บอทจะไม่ซื้อเหรียญถ้าราคาพุ่งจนตึงเกินไป (RSI > 65) ช่วยป้องกันปัญหาซื้อแล้วติดดอย
- **จัดการความเสี่ยงด้วยความผันผวน (ATR):** เปลี่ยนระบบตัดขาดทุนแบบตายตัว ให้ยืดหยุ่นตามความผันผวนของตลาด
- **ระบบแบ่งขายและเลื่อนจุดตัดขาดทุน (Take Profit & Trailing Stop):** บอทจะเริ่มเลื่อนจุดขายเมื่อกำไรถึง 1.5% และจะตั้งเป้าขายทำกำไรทันทีเมื่อถึง 3% เพื่อให้มีกำไรเก็บเข้าพอร์ตทุกวัน
- **AI เจาะจงเหรียญ:** อัปเดตสมอง AI ให้เน้นอ่านข่าวเพื่อวิเคราะห์ความเสี่ยงของเหรียญนั้นๆ โดยเฉพาะ ไม่เอาข่าวรวมตลาดมาเหมาจ่าย
## [3.3.0] - 2026-06-13
### Architecture Upgrade & Live Positions (อัปเกรดระบบและตารางสถานะเรียลไทม์)
**English:**
- **Event-Driven WebSocket Architecture:** The backend has been completely rewritten to an event-driven model.
- **Direct Price Streaming:** `bot/main.py` now utilizes `ThreadedWebsocketManager` to stream live prices directly from Binance without hitting rate limits.
- **Webhook Integration:** The bot core now communicates with `api/server.py` via an authenticated internal webhook (`POST /api/internal/broadcast`), replacing the legacy file polling method.
- **Live Positions Dashboard:** The UI now includes a "Live Positions" table that dynamically displays real-time PNL ($ and %) using WebSocket updates.

**Thai (ภาษาไทย):**
- **สถาปัตยกรรม Event-Driven WebSocket:** อัปเกรดระบบหลังบ้านใหม่ทั้งหมดให้เป็นแบบ Event-Driven
- **ดึงราคาแบบสตรีมมิ่ง:** `bot/main.py` เปลี่ยนมาใช้ `ThreadedWebsocketManager` เพื่อรับข้อมูลราคาแบบเรียลไทม์จาก Binance โดยตรง ช่วยแก้ปัญหาการติด Rate Limit
- **เชื่อมต่อผ่าน Webhook:** บอทหลักสื่อสารกับเซิร์ฟเวอร์ `api/server.py` ผ่านทาง Webhook ภายใน (`POST /api/internal/broadcast`) แบบเข้ารหัส แทนที่การอ่านเขียนไฟล์แบบเก่า
- **ตารางสถานะเหรียญแบบเรียลไทม์:** หน้าเว็บ Dashboard มีตาราง "Live Positions" ที่คอยอัปเดตตัวเลขกำไร/ขาดทุน (PNL) ทั้งแบบดอลลาร์และเปอร์เซ็นต์แบบสดๆ ผ่าน WebSocket

## [3.2.0] - 2026-06-12
### Features & Analytics (สถิติและข้อมูลการเทรด)
**English:**
- Implemented real-time Fee and execution price extraction from Binance `fills`.
- Added cumulative PNL (Profit & Loss) amount and percentage calculation for each SELL trade.
- Added live Win Rate and Win/Loss counter to the Dashboard UI.
- Fixed timezone offset display bug on the frontend (added UTC timezone info).
- Fixed CSS truncation on the AI Reasoning text to allow multi-line reading.
- Added sync logic to detect and log manual sells from Binance into the Database.

**Thai (ภาษาไทย):**
- ดึงข้อมูลค่าธรรมเนียม (Fee) และราคาซื้อขายจริงระดับจุดทศนิยมจากบิลของ Binance โดยตรง
- เพิ่มระบบคำนวณกำไร/ขาดทุน (PNL) เป็นตัวเงินและเปอร์เซ็นต์ทุกครั้งที่มีการกดขาย
- เพิ่มการแสดงผล Win Rate และจำนวนครั้งที่ชนะ/แพ้ บนหน้าจอ Dashboard หลัก
- แก้ปัญหาเวลาโชว์ช้าไป 7 ชั่วโมงให้ตรงกับเวลาจริงในไทย
- แก้ไขปัญหาข้อความ AI เหตุผลการเทรดโดนตัดตกขอบ ให้อ่านได้เต็มบรรทัด
- ระบบดักจับการขายเหรียญด้วยตัวเอง (Manual Sell): หากเราชิงกดขายเหรียญทิ้งเอง บอทจะรู้ตัวและบันทึกประวัติลงฐานข้อมูลให้หน้าเว็บอัปเดตทันที

## [3.1.0] - 2026-06-12
### Debugging & Observability (ระบบแสดงผลข้อผิดพลาด)
**English:**
- Added a real-time "System Debug Log" panel to the Web Dashboard to monitor errors, warnings, and system events.
- Integrated `LogRepository` to persist logs in the SQLite database (`trades.db`).
- Replaced `print` and `logging` statements in the bot engine to capture Binance API errors (e.g. `LOT_SIZE` rejections, connectivity issues) directly to the database.
- Implemented a new `logs_update` WebSocket broadcast in the backend to stream logs to connected clients in real-time.

**Thai (ภาษาไทย):**
- เพิ่มแผง "System Debug Log" บนหน้าเว็บ เพื่อแสดงเวลาและรายละเอียดการทำงาน รวมถึงข้อผิดพลาดของบอทแบบเรียลไทม์
- สร้าง `LogRepository` เพื่อเก็บประวัติ Log (เช่น INFO, WARNING, ERROR) ลงในฐานข้อมูล SQLite
- ปรับปรุงการเก็บ Log ในตัวบอทเทรดให้จับข้อมูล Error ต่างๆ เช่น การถูก Binance ปฏิเสธคำสั่งซื้อ มาแสดงผลบนหน้าเว็บแทนที่จะอยู่ใน Terminal อย่างเดียว
- เพิ่มระบบกระจายสัญญาณ Log ผ่าน WebSockets ให้หน้าเว็บอัปเดตบรรทัดต่อบรรทัดแบบเรียลไทม์

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
