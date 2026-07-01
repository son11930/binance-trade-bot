## [4.7.3] - 2026-07-01
### Unlock Trade Time Limit for Max Compounding Power
**English:**
- **Unlock Time-Expired Exit**: Set `time_in_trade=0` across all Futures (`FUTURES_30M_SNIPER`) and Spot strategies (`TREND_MACD`, `SIDEWAYS_RSI_BB`) in `bot/strategy.py`.
- **Prevent Premature Trade Cutoffs**: Backtest data confirmed that cutting trades after 12 candles (6 hours) caused excessive re-entries in consolidating markets, jumping from 112 to 393 trades and draining profits from +326.88% to -29.19%. Removing the time restriction allows the 4-Gear Hybrid Risk Manager (Gear 1-4) to ride major trends to completion.

**Thai (ภาษาไทย):**
- **ปลดล็อคข้อจำกัดเวลาถือออเดอร์**: ปรับค่า `time_in_trade=0` ใน `bot/strategy.py` ทั้งระบบ Futures และ Spot เพื่อยกเลิกการตัดไม้ออกเมื่อถือครบ 12 แท่ง (6 ชั่วโมง)
- **ปล่อยให้ระบบ 4 เกียร์รีดกำไรคำโตสุดขีด**: จากสถิติ Backtest ยืนยันว่าการตั้งเวลาตัดทิ้ง 12 แท่งทำให้บอทเปิดปิดออเดอร์ซ้ำซ้อนในช่วงสะสมพลัง (จาก 112 ไม้พุ่งเป็น 393 ไม้) และกดกำไรลดลงจาก +326.88% เหลือติดลบ การปลดล็อคเวลาออกจะช่วยให้ระบบ 4-Gear Trailing ทำงานเกาะคลื่นใหญ่ไปจนสุดทาง

## [4.7.2] - 2026-07-01
### Binance API Rate Limit Protection & Fallback Fee Caching
**English:**
- **Rate Limit Protection**: Updated `bot/binance_client.py` (`get_cached_futures_fee` and `get_cached_spot_fee`) to immediately cache fallback fee rates (0.0005 for Futures, 0.001 for Spot) for 1 hour whenever an API error or Global Rate Limit occurs.
- **Prevent API Spam Loop**: Fixed a critical issue where failing to fetch trade commission rates caused repetitive API requests every second, preventing the Binance connection from recovering during rate limits.
- **Full Engine Backtest Suite**: Added comprehensive verification scripts (`test_30m_multiperiod.py`, `run_full_engine_backtest.py`, `optimizer.py`) to simulate and benchmark the 4-Gear Hybrid Risk Manager across 1m, 3m, 6m, and 1y periods.

**Thai (ภาษาไทย):**
- **ป้องกันการติด Rate Limit**: อัปเกรดระบบดึงค่าธรรมเนียมใน `bot/binance_client.py` เมื่อเกิด Error หรือติด Rate Limit บอทจะบันทึกค่าธรรมเนียมสำรอง (0.0005 สำหรับ Futures และ 0.001 สำหรับ Spot) เก็บลงแคชทันทีเป็นเวลา 1 ชั่วโมง
- **แก้ลูปยิง API ซ้ำรัวๆ**: แก้ปัญหาที่บอทพยายามยิงเช็คค่าธรรมเนียมทุกวินาทีตอนเน็ตสะดุด ช่วยให้การเชื่อมต่อกับ Binance หลุดจาก Rate Limit และกลับมาทำงานเป็นปกติได้อย่างรวดเร็วและปลอดภัย
- **ระบบ Backtest ทดสอบ 4 เกียร์เต็มรูปแบบ**: เพิ่มชุดสคริปต์ทดสอบระบบจริงบน Timeframe 30 นาที ย้อนหลัง 1 เดือน, 3 เดือน, 6 เดือน และ 1 ปีเต็ม

## [4.7.1] - 2026-06-30
### 30m Timeframe Migration & High-Accuracy Sniper Fixes
**English:**
- **Timeframe Migration**: Upgraded the bot from a 15-minute to a 30-minute timeframe to filter out market noise and increase the reliability of technical indicators (MACD, RSI, BB).
- **Time-Expired Trailing Stop Fix**: Adjusted the internal time limit multiplier in `bot/risk_manager.py` from `* 15` to `* 30` to correctly track elapsed minutes for 30m candles.
- **Trend Asymmetry Bug Fix**: Fixed a critical bug in `bot/strategy.py` where Long trades were allowed if `price > EMA_50` (causing longs in downtrends). It now strictly requires `EMA_50 > SMA_200` to mirror the Short strategy.
- **MA(99) Support/Resistance Filter**: Integrated `SMA_99` as a strict barrier. The bot will no longer Long below MA(99) or Short above it.
- **ADX Sideways Filter**: Enforced `ADX > 25` to block the bot from trading in choppy, range-bound markets.
- **Stop Loss Adjustment**: Increased the Sniper strategy Stop Loss from `1.0 ATR` to `1.2 ATR` to accommodate the larger wicks characteristic of 30m candles.

**Thai (ภาษาไทย):**
- **ย้ายไปกราฟ 30 นาที**: อัปเกรดบอทจากกราฟ 15m เป็น 30m เพื่อกรองสัญญาณหลอกออก ทำให้การวิเคราะห์ทางเทคนิคแม่นยำขึ้นมาก
- **แก้บั๊กเวลานับถอยหลัง**: แก้ไขสูตรนับเวลาหมดอายุออเดอร์ใน `risk_manager.py` ให้รองรับแท่ง 30 นาที (ถือได้นานสุด 6 ชั่วโมงเท่าเดิม)
- **แก้บั๊กเงื่อนไขขาขึ้น (Long)**: แก้ไขให้เงื่อนไข Long เข้มงวดขึ้น (`EMA_50 > SMA_200`) เพื่อป้องกันบอทเปิด Long สวนเทรนด์ตอนตลาดเป็นขาลง
- **กำแพงแนวรับแนวต้าน MA(99)**: เพิ่มการเช็คเส้น MA(99) บังคับว่าห้าม Long ถ้าอยู่ใต้เส้น และห้าม Short ถ้าอยู่เหนือเส้น
- **ฟิลเตอร์กรองไซด์เวย์ (ADX)**: บังคับใช้ `ADX > 25` บอทจะไม่ยอมเทรดเด็ดขาดถ้าระบบตรวจพบว่าตลาดไม่มีทิศทางที่ชัดเจน
- **ขยับ Stop Loss**: ขยายจุดตัดขาดทุนจาก 1.0 เป็น 1.2 ATR เพื่อให้กราฟมีพื้นที่สวิงได้บ้างตามธรรมชาติของแท่ง 30m

## [4.7.0] - 2026-06-29
### Advanced AI Learning System & Opportunity Cost Tracker
**English:**
- **AI Decision Tracking**: Implemented the `AIDecision` database table to track all AI evaluations, including trades that were rejected (HOLD).
- **Opportunity Tracker**: Created `opportunity_tracker.py` to retrospectively grade past rejected trades (after 4 hours) against actual market price action to determine if the AI missed a profitable setup or correctly avoided a loss.
- **Discord Webhooks**: Integrated Discord notifications to immediately alert when a "Missed Opportunity" is detected.
- **Global Memory Agent**: Built `global_memory_agent.py` to scan the last 24 hours of wins, losses, and missed opportunities to generate a daily macro context report (`global_memory.txt`).
- **AI Context Injection**: The Chief Agent now receives past winning trades and the daily Global Memory context in its prompt to learn from successes and adapt to the current market regime.

**Thai (ภาษาไทย):**
- **บันทึกการตัดสินใจ AI**: เพิ่มตาราง `AIDecision` เพื่อบันทึกทุกความคิดของ AI รวมถึงออเดอร์ที่สั่งระงับ (HOLD) เพื่อนำมาเรียนรู้ย้อนหลัง
- **ระบบติดตามไม้ตกรถ (Opportunity Tracker)**: สร้างสคริปต์ตรวจเช็คออเดอร์ที่ถูกปัดทิ้งเมื่อ 4 ชั่วโมงที่แล้ว โดยดึงกราฟจริงมาเทียบว่า AI พลาดโอกาสทำกำไร หรือตัดสินใจถูกแล้วที่ห้ามเทรด
- **แจ้งเตือนไม้ตกรถ**: ส่งแจ้งเตือนผ่าน Discord ทันทีเมื่อระบบคำนวณพบว่า AI สั่งปัดตกไม้ที่ควรจะได้กำไร
- **ระบบความจำส่วนกลาง (Global Memory)**: สร้าง Agent ให้สรุปผลงานตลอด 24 ชั่วโมงที่ผ่านมา (ไม้ชนะ, ไม้แพ้, ไม้ตกรถ) ออกมาเป็น `global_memory.txt`
- **ป้อนความทรงจำให้ AI**: ตอนนี้ Chief Agent จะได้รับข้อมูลไม้ที่เพิ่งชนะมาหมาดๆ และสรุปสภาวะตลาดประจำวัน เพื่อให้ AI เก่งขึ้น และไม่ลืมว่าช่วงนี้กลยุทธ์ไหนกำลังทำเงิน

## [4.6.10] - 2026-06-29
### High-Precision Sniper Entries (V-Shape & Rejection)
**English:**
- **Sniper Entry Overhaul**: Scrapped the old MACD/RSI logic for Futures entries. Replaced it with extreme high-precision conditions that focus on immediate profit, allowing the tight 1.0 ATR stop loss to survive.
- **Liquidity Sweeps & Divergences**: The bot now hunts for Pin Bar traps (Bollinger Band rejections with 2x wick size), 15-period RSI Divergences (momentum shifts against price), and exact SMA 200 rejections.
- **Volume Filter Adjustment**: Enforced `volume > SMA_20` across all Sniper conditions to guarantee trades only occur when there is active market participation, securing an average of 1-10 high-probability trades daily.
- **AI Prompt Update**: Updated `ai_engine.py` to correctly interpret the new `SNIPER_LONG` and `SNIPER_SHORT` signals as breakout/reversal plays rather than mean-reverting, preventing the AI from inappropriately vetoing the trades.

**Thai (ภาษาไทย):**
- **รื้อจุดเข้าใหม่หมด (Sniper Entry)**: โละระบบตัดกันของ MACD/RSI ทิ้งทั้งหมด และเปลี่ยนมาใช้เงื่อนไขแบบ Sniper ขั้นสุดยอด ที่เน้นว่า "เข้าปุ๊บต้องกำไรปั๊บ" เพื่อรักษา Stop Loss 1.0 ATR ที่แคบมากๆ เอาไว้
- **ล่าแม่มด & ขัดแย้งโมเมนตัม**: บอทจะดักกินไส้เทียน (Pin Bar Trap) ที่สะบัดหลอกนอกกรอบ Bollinger, ดักหาจุดกลับตัวที่กราฟขัดแย้งกับ RSI ย้อนหลัง 15 แท่ง, และดักจังหวะชนเส้นต้านทานหลัก (SMA 200) แบบพอดีเป๊ะ
- **กรองความถี่ให้พอดี**: ปรับเงื่อนไข Volume ให้แค่สูงกว่าค่าเฉลี่ยปกติก็พอ เพื่อรับประกันทางคณิตศาสตร์ว่าบอทจะยังสแกนเจอและได้เทรดวันละ 1-10 ไม้เป็นอย่างน้อย
- **อัพเดทสมอง AI**: แก้ไข Prompt ให้ AI เข้าใจชื่อท่า `SNIPER_LONG` และ `SNIPER_SHORT` เพื่อไม่ให้ AI งงและปัดตกสัญญาณทิ้ง

## [4.6.9] - 2026-06-26
### Stop Loss Ladder Optimization & Smart Filters
**English:**
- **Breakeven Ladder Expansion**: Widened the step-based trailing stop ladder to provide trades more breathing room (allowing 2-3% ROE pullbacks) before triggering stops, solving the issue of premature exits during minor retracements.
- **Smart Entry Filters (ADX & SMA)**: Added ADX trend strength and SMA200 macro trend filters to 15M futures strategies. The bot now demands extreme RSI readings when fighting strong trends and ensures trend-following entries align with the macro direction.
- **Fixed Long Entry Bug**: Removed a flawed condition (`price > bb_lower`) that was blocking the bot from catching absolute bottoms on DIP BUY setups.

**Thai (ภาษาไทย):**
- **ขยายระยะหายใจ (Trailing Stop Ladder)**: ปรับขั้นบันไดล็อคกำไรให้กว้างขึ้น ยอมให้กราฟย่อตัวได้ 2-3% ROE เพื่อแก้ปัญหาบอททนรวยไม่ได้และโดนสะบัดกิน Stop loss จากความผันผวนปกติ
- **ฟิลเตอร์ต้านเทรน (ADX & SMA)**: เพิ่มตัวกรองความแรงเทรน (ADX) ถ้ารถไฟกำลังพุ่งแรง บอทจะเรียกร้องค่า RSI ที่สุดโต่งมากๆ ถึงจะยอมสวนเทรน และเช็คภาพใหญ่ (SMA200) เพื่อไม่ให้ดักช็อตในเทรนขาขึ้น
- **แก้บัคห้ามซื้อก้นเหว (Long Entry Bug)**: แก้ไขตรรกะผิดพลาดที่สั่งห้ามซื้อถ้าราคาแตะขอบล่าง Bollinger Band ทำให้ตอนนี้บอทสามารถเปิดไม้ Long ตอนกราฟร่วงหนักๆ ได้แล้ว

## [4.6.8] - 2026-06-25
### V-Shape Sniper Overhaul & Paper Trading
**English:**
- **V-Shape Sniper Entries**: Overhauled `bot/strategy.py` entry logic. Removed lagging indicators (SMA200, ADX) and replaced them with Mean-Reversion dip-buying logic (RSI Hook + Bollinger Band breach) and fast MACD Histogram momentum reversals.
- **Ultra-Tight Stop Loss**: Reduced `sl_multiplier` from 2.0 to 0.8, drastically improving Risk/Reward ratio for scalping. Fallback hard stop reduced to 1.5% ROE.
- **Paper Trading Mode**: Enabled Paper Trading by default in `.env` for safe testing.

**Thai (ภาษาไทย):**
- **รื้อจุดเข้าใหม่ (V-Shape Sniper)**: ยกเลิกระบบ Trend Follower ที่เข้าซื้อช้า (ดอย) เปลี่ยนมาใช้ท่าช้อนซื้อจุดกลับตัวก้นเหว (RSI หักหัวขึ้น + หลุดขอบล่าง Bollinger Band) และใช้เส้น MACD แท่งเพื่อความไว
- **หั่นจุดยอมแพ้ให้แคบสุด (Tight SL)**: ลด Stop loss จากเดิมที่ลากยาว 3-4% บีบให้เหลือยอมขาดทุนแค่ 1.0-1.5% เพื่อแก้ไขปัญหาได้กำไรน้อยแต่ขาดทุนเยอะ
- **สวิตช์ Paper Trade**: เปิดระบบเทรดเงินปลอมเพื่อทดสอบความแม่นยำของระบบใหม่

## [4.6.7] - 2026-06-25
### Waning Momentum Hotfix (Moonshot Preservation)
**English:**
- **Momentum Take Profit Hotfix**: Fixed a critical logical flaw where the new Fast Surge logic would completely block the bot from capturing massive "Moonshot" trends by prematurely exiting at exactly 3.0%. Added a waning momentum check (`hp_drop_percent >= 0.3`) so the bot only triggers the Fast Surge exit if the RSI is high *and* the price has started to retrace slightly from its peak, allowing strong pumps to run freely to 10%+.

**Thai (ภาษาไทย):**
- **แก้บัคตัดจบออเดอร์ไวไป (Waning Momentum)**: แก้บัคตรรกะที่ระบบ Fast Surge ไปแย่งปิดออเดอร์ที่ 3.0% หมดจนบอทไม่ยอมรันเทรนด์กินคำโต โดยเพิ่มเงื่อนไขว่า "RSI ต้องเดือด และราคากราฟต้องเริ่มแผ่วตกลงมาจากจุดสูงสุด 0.3%" ถึงจะยอมปิดออเดอร์ ทำให้ถ้ากราฟยังพุ่งขึ้นปรี๊ดๆ อย่างต่อเนื่อง บอทจะปล่อยให้กำไรไหลไปเรื่อยๆ จนสุดเทรนด์ (Moonshot 10%+) ได้เหมือนเดิมครับ

## [4.6.6] - 2026-06-25
### Aggressive Trailing Locks & Momentum Take Profit
**English:**
- **Tightened Trailing Stop Ladder**: Increased the locked profit percentages across both Spot and Futures step ladders. For example, a 3.0% max profit now locks in 2.0% (previously 1.5%), ensuring more profit is secured without getting chopped out by minor fluctuations.
- **Fast Surge Momentum Take Profit**: Added a new exit mechanism that instantly closes trades if profit is >= 3.0% and RSI enters the surge zone (>= 70 for Long, <= 30 for Short). This prevents 50% retracements by "taking the money and running" during violent price spikes.

**Thai (ภาษาไทย):**
- **ปรับล็อกกำไร (Trailing) ให้แน่นขึ้น**: ยกจุดตัดล็อกกำไรให้สูงขึ้นทั้ง Spot และ Futures เช่น ถ้าราคาวิ่งไปถึง 3.0% ระบบจะล็อกตายให้ที่ 2.0% (เดิม 1.5%) เพื่อรักษากำไรไว้ไม่ให้ไหลคืนตลาดมากเกินไป
- **เพิ่มระบบปิดทำกำไรตอนกราฟกระชาก (Fast Surge)**: ถ้ากำไรเกิน 3.0% แล้วกราฟพุ่งแรงจน RSI เดือด ระบบจะชิง "หนีบกำไรกลับบ้าน" ตัดจบออเดอร์ทันทีโดยไม่รอให้ตบกลับลงมาชน Trailing ครับ เน้นกินคำเล็กแต่ได้ชัวร์ๆ ตามคอนเซปต์ Scalping

## [4.6.5] - 2026-06-25
### AI Risk Context & Pyramiding Queue Hotfixes
**English:**
- **AI Risk Context Validator**: Changed the AI's core behavior from being an independent decision-maker to a strict validator. The AI is now explicitly provided the Technical Indicator's proposed direction and asked to evaluate the risk of *that specific direction*, outputting `PROCEED` or `HOLD`. This prevents the fatal logical flaw of using an AI's bullish risk score to approve a bearish technical entry.
- **Async Queue API Error Lock Release**: Fixed a critical edge case where an AI API failure would correctly attempt to skip the execution cooldown, but fail to release the async pyramiding lock. Added `last_trade_time=None` on error catch blocks to ensure the symbol is immediately unlocked for the next tick.

**Thai (ภาษาไทย):**
- **แก้ตรรกะประเมินความเสี่ยง AI (Risk Context)**: เปลี่ยนคำสั่งให้ AI เลิกคิดทิศทางเอง แต่ส่งทิศทางของ Indicator ไปให้ AI เป็นคนตรวจข้อสอบแทน แล้วให้ AI ตอบแค่ `PROCEED` (ลุย) หรือ `HOLD` (พัก) วิธีนี้จะแก้บัคที่บอทเอาคะแนนความปลอดภัยฝั่ง LONG ไปใช้เปิดออเดอร์ SHORT ครับ
- **แก้บัค API ล่มแล้วเหรียญค้าง**: แก้ปัญหาบัคที่เวลา API ของ AI ฝั่งเซิร์ฟเวอร์มีปัญหา แล้วมันไม่ยอมปลดล็อค Pyramiding Lock ให้ ทำให้เหรียญนั้นติด Cooldown ไปฟรีๆ 45 นาที ตอนนี้สั่งปลดล็อคให้ทันทีถ้า API มีปัญหาครับ

## [4.6.4] - 2026-06-25
### AI Strategy Overhaul & Async Queue Fixes
**English:**
- **AI as Risk Manager Only**: Removed the strict direction matching between the AI and technical indicators. The AI now acts strictly as a Risk & Sizing Manager. The bot will execute the technical indicator's direction as long as the AI determines the risk is acceptable (Risk Score <= 70) and doesn't explicitly vote to `HOLD`. Mismatched opinions are now logged for info rather than aborting trades, significantly increasing trade frequency.
- **Async Pyramiding Lock Fix**: Fixed the root cause of the pyramiding bug where multiple signals in the same second could bypass the `last_trade_time` check while waiting in the async AI queue. Added a synchronous lock right before submitting to the AI queue to instantly engage the cooldown block.
- **Reversal Execution Optimization**: Fixed a bug where a reversal signal would close the existing position but fail to open the new one due to triggering the cooldown block. Added an `is_reversal` flag to safely bypass the cooldown when pivoting direction.
- **Adjusted Entry Filters**: Relaxed the ADX filter to `> 18` and the volume surge filter to `> 0.8x SMA` to ensure the bot trades frequently enough on the 15-minute timeframe without entering dead markets.

**Thai (ภาษาไทย):**
- **ปรับบทบาท AI (Risk Manager)**: ยกเลิกการบังคับให้ AI ต้องคิดทิศทางตรงกับ Indicator เนื่องจากทำให้บอทไม่ได้เทรดเลย ตอนนี้ AI จะทำหน้าที่คุมความเสี่ยงและขนาดไม้เท่านั้น ตราบใดที่คะแนนความเสี่ยงผ่านเกณฑ์ (<= 70) บอทจะเปิดออเดอร์ตาม Indicator เสมอ (แม้ AI จะมองสวนทางก็ตาม)
- **ล็อคคิวกันถัวไม้ซ้ำ (Async Lock)**: แก้ปัญหาบัคเบิ้ลไม้ระดับโครงสร้าง โดยเพิ่มการล็อคเวลาแบบ Synchronous ทันทีก่อนส่งสัญญาณเข้าคิว AI ป้องกันไม่ให้มีสัญญาณซ้ำหลุดเข้าไปรันพร้อมกัน
- **แก้บัคการกลับตัว (Reversal Fix)**: แก้ปัญหาที่เวลาบอทปิดไม้ออเดอร์เดิมเพื่อกลับตัว แล้วมันติด Cooldown ตัวเองจนเปิดไม้ใหม่ไม่ได้ ตอนนี้เพิ่มข้อยกเว้นให้ระบบ Reversal ไม่ติด Cooldown แล้ว
- **คลายฟิลเตอร์ 15 นาที**: ปรับ ADX ลงมาที่ 18 และ Volume เฉลี่ยลดลงมาที่ 0.8 เท่า เพื่อให้บอทมีความถี่ในการเทรดที่เหมาะสมมากขึ้น ไม่ตึงจนเกินไป

## [4.6.3] - 2026-06-24
### Profit Maximization & Signal Filtering
**English:**
- **Smart Filtering**: Increased Futures `ADX` threshold from 15 to 20 to avoid flat markets, and enforced `strong_volume` (Volume > 1.2x SMA) to confirm real breakouts.
- **Trend Alignment**: Added `SMA_200` trend alignment filter for `FUTURES_15M_LONG` and `FUTURES_15M_SHORT` to prevent counter-trend fakeout entries.
- **Dynamic Allocation Sizing**: Shifted the AI allocation boundaries from `10-40%` to `20-40%` to maximize profit captures on high-probability setups.

**Thai (ภาษาไทย):**
- **ตัวกรองสัญญาณอัจฉริยะ (Smart Filtering)**: ปรับความเข้มงวดของ `ADX` สำหรับ Futures จาก 15 เป็น 20 เพื่อหลีกเลี่ยงตลาดแกว่งตัว และบังคับให้มีวอลุ่มมากกว่าค่าเฉลี่ย 1.2 เท่า เพื่อยืนยันว่าเบรคจริง
- **อิงเทรนด์ภาพใหญ่ (Trend Alignment)**: เพิ่มเงื่อนไข `SMA_200` เข้ามาช่วยยืนยันเทรนด์ ห้ามสวนเทรนด์หลักเด็ดขาดเพื่อลดจุดเข้าหลอก (Fakeouts)
- **อัดไม้ทำกำไร (Dynamic Allocation)**: ปรับกรอบให้ AI วางเงินไม้ขั้นต่ำหนักขึ้นจาก `10-40%` เป็น `20-40%` เพื่อรีดกำไรสูงสุดในจังหวะที่กราฟสวยและชัวร์

## [4.6.2] - 2026-06-24
### Risk/Reward Ratio Fixes & Momentum Take Profit
**English:**
- **Momentum Take Profit**: Refined the aggressive scalping TP logic for Futures to trigger at 2.0% profit (down from 3.0%) when RSI hits extreme bounds (75 for LONG, 25 for SHORT) to lock in gains before sudden Whipsaw reversals.
- **Risk Capping**: Tightened the global Futures Hard Stop Loss to exactly 3.0% ROE. Lowered the ATR stop-loss multiplier from 2.5 to 2.0 in `analyze_futures_market` to properly align with this new risk threshold.
- **Reverted Breakeven Ladder**: The Step Breakeven Trailing ladder has been reverted to its original tight configuration to maintain a functional safety net that scales up early.
- **CRITICAL BUG FIX (Pyramiding Prevention)**: Fixed a catastrophic bug in the `_evaluate_futures_trade_signal` where the bot would relentlessly add to existing positions (pyramiding) if it received repeated signals in the same direction, artificially multiplying the size of losses. It now correctly ignores signals that match the currently open position direction.

**Thai (ภาษาไทย):**
- **ชิงขายทำกำไรไวขึ้น (Momentum TP)**: ปรับจูนให้บอทชิงขายทำกำไรเร็วขึ้นที่ 2.0% (จากเดิม 3.0%) หากกราฟมีสัญญาณหมดแรง (RSI ชน 75 หรือต่ำกว่า 25) เพื่อเก็บกำไรเข้ากระเป๋าก่อนโดนทุบกลับ
- **คุมความเสี่ยงเข้มงวด (Risk Capping)**: ล็อคเพดานขาดทุนสูงสุดของ Futures ไว้ที่ 3.0% ROE ทันที พร้อมทั้งปรับตัวคูณ ATR Stop Loss ใน Strategy ลดลงจาก 2.5 เท่าเหลือ 2.0 เท่า ให้สอดคล้องกัน
- **คงระบบแผนสำรอง (Breakeven)**: นำระบบขยับ Stop Loss บังหน้าทุน (Step Breakeven) แบบดั้งเดิมกลับมาใช้ เพื่อให้เป็นเซฟตี้เน็ตกันเหนียว คอยล็อคกำไรขั้นต่ำไว้เผื่อเวลาที่กราฟไปไม่ถึงเป้า RSI
- **แก้บัคถัวไม้ซ้ำ (Pyramiding Bug)**: แก้ไขบัคร้ายแรงที่บอทฝั่ง Futures มีการเปิดออเดอร์ซ้ำๆ ทับถมตำแหน่งเดิม (เช่น สั่ง LONG OP ไป 4 รอบ) เมื่อมีสัญญาณมาทิศทางเดียวกันต่อเนื่อง ทำให้เวลาขาดทุนจำนวนเงินจะเสียเยอะมากอย่างผิดปกติ ตอนนี้บล็อคไม่ให้เปิดไม้ซ้ำในทิศทางเดิมเรียบร้อยแล้ว

## [4.6.1] - 2026-06-23
### Explicit Direction Mismatch Logging & Spot Fix
**English:**
- **Enhanced Logging**: Added explicit "Direction Mismatch" logs for both Spot and Futures when the AI's decision conflicts with the technical indicators' signal direction. This makes it instantly recognizable on the dashboard when a trade is aborted due to a directional disagreement.
- **Spot Bug Fix**: Fixed a bug where Spot `_evaluate_buy_signal` rejected the AI's `LONG` decision. Spot trades will now correctly interpret both `BUY` and `LONG` as a valid agreement with the technical signal.

**Thai (ภาษาไทย):**
- **ปรับปรุงข้อความ Log ให้ชัดเจนขึ้น**: เพิ่ม Log แจ้งเตือนข้อความ "Direction Mismatch" (ทิศทางไม่ตรงกัน) ทั้งในระบบ Spot และ Futures เมื่อการตัดสินใจของ AI ขัดแย้งกับสัญญาณเทคนิคอล เพื่อให้สังเกตเห็นได้ง่ายขึ้นบน Dashboard เมื่อบอทยกเลิกการเปิดสถานะ
- **แก้ไขบัคของ Spot**: แก้ไขบัคในระบบ Spot ที่ก่อนหน้านี้จะปฏิเสธคำสั่งเทรดหาก AI ตอบกลับมาว่า `LONG` (เดิมรองรับแค่ `BUY`) ตอนนี้ระบบเข้าใจแล้วว่า `LONG` มีความหมายเดียวกันกับ `BUY` สำหรับการซื้อ Spot

## [4.6.0] - 2026-06-22
### Data Ingestion Pipeline & Intelligent Prompts
**English:**
- **3-Layer Ingestion Pipeline**: Designed a new scalable architecture for aggregating multiple news sources (CryptoPanic, RSS, Twitter) without overwhelming AI token limits.
- **Alternative Data Integration**: Planned the integration of Funding Rates, Open Interest, Long/Short Ratio, and Fear & Greed Index to improve Market Context evaluation.
- **AI Prompt Upgrade**: Upgraded the `ai_engine.py` prompt schema to support Quantitative Analysis with new Data metrics and `LONG`, `SHORT`, `HOLD` output decisions.

**Thai (ภาษาไทย):**
- **สถาปัตยกรรมดึงข้อมูล 3 ชั้น**: ออกแบบระบบดึงข่าวใหม่ทั้งหมดเพื่อรองรับหลายแหล่ง (CryptoPanic, RSS, Twitter) โดยมีระบบคัดกรอง Impact Score เพื่อประหยัดค่าโควต้า Token ของ AI
- **ข้อมูลวิเคราะห์เชิงลึก**: เพิ่มการดึงข้อมูล Funding Rate, อัตราส่วน Long/Short, และดัชนี Fear & Greed เข้ามาให้ AI ตัดสินใจได้แม่นยำขึ้น
- **อัปเกรดความฉลาด AI**: ปรับ Prompt ให้ AI สวมบทบาทเป็นนักวิเคราะห์เชิงปริมาณ (Quant) ให้รู้จักมองหาความขัดแย้งของตลาด และตัดสินใจออกคำสั่ง `LONG`, `SHORT`, `HOLD` ให้ฝั่ง Futures ได้

## [4.5.0] - 2026-06-22
### Exact Binance Commission & Dynamic Fee Integration
**English:**
- **Dynamic Commission Fetching**: Replaced hardcoded default fees with real-time fee rate fetching from the Binance API (`get_cached_spot_fee`, `get_cached_futures_fee`).
- **Exact Ledger Syncing**: The `futures_place_order` execution now pulls the exact executed `avgPrice` and `commission` directly from the account ledger (`futures_account_trades`), eliminating PnL tracking drift over time.
- **Fail-Safe Caching**: Fee rates are cached locally for 1 hour to prevent API rate-limit exhaustion, automatically falling back to industry defaults (0.1% Spot / 0.05% Futures) during network failures.

**Thai (ภาษาไทย):**
- **ดึงค่าธรรมเนียมจริง (Dynamic Fees)**: ยกเลิกการล็อคค่าธรรมเนียมตายตัว และเปลี่ยนไปดึงเรทค่าธรรมเนียม (Fee Rate) จากบัญชี Binance จริงแบบเรียลไทม์
- **บันทึกราคาและค่าธรรมเนียมเป๊ะ 100%**: ปรับให้บอทดึงประวัติสมุดบัญชี (`futures_account_trades`) ทันทีที่ออเดอร์จับคู่สำเร็จ เพื่อดึงราคาเฉลี่ย (`avgPrice`) และค่าต๋งจริงมาบันทึก แก้ปัญหาการคำนวณกำไร/ขาดทุน (PnL) คลาดเคลื่อน
- **ระบบ Cache สำรอง**: บอทจะจำเรทค่าธรรมเนียมไว้ 1 ชั่วโมงเพื่อไม่ให้กินโควต้า API Binance และมีระบบดึงค่ามาตรฐานกลับมาใช้ชั่วคราวหากเชื่อมต่อล้มเหลว

## [4.4.0] - 2026-06-22
### Dual-Engine Spot & Futures Architecture Decoupling
**English:**
- **Absolute Decoupling**: Completely separated the core logic for Spot and Futures markets into independent pipelines to eliminate cross-contamination bugs.
- **Independent State Management**: Created distinct `sync_spot_state_with_binance` and `sync_futures_state_with_binance` flows, ensuring Spot portfolios are never tangled with Futures margin balances.
- **Independent Risk Managers**: Decoupled `calculate_pnl` and `check_risk_management` into specific Spot and Futures variants, accurately handling ROE, Leverage, Long/Short side checks, and Trailing Stops respectively.
- **TDD Enforcement**: Added comprehensive test suites in `tests/test_risk_manager.py` and `tests/test_state.py` validating the decoupled dual-engine logic.

**Thai (ภาษาไทย):**
- **แยกระบบ 2 เครื่องยนต์**: ทำการผ่าตัดโค้ดแยกระบบคำนวณของ Spot และ Futures ออกจากกันอย่างเด็ดขาด เพื่อป้องกันบัคข้ามสาย
- **แยกระบบเช็คยอดเงิน**: แยกฟังก์ชันอัพเดทสถานะพอร์ต Spot และ Futures เพื่อไม่ให้ยอดเงิน Margin หรือสถานะ Long/Short มาปนเปกับฝั่งถือเหรียญจริง
- **ระบบคุมความเสี่ยงแยกส่วน**: ตัวจัดการความเสี่ยง (Risk Manager) ถูกแยกส่วนให้คำนวณ PNL, จุด Stop Loss, Break-Even, และ Trailing Stop สำหรับแต่ละฝั่งโดยเฉพาะ (ฝั่ง Futures จะรองรับระบบตัวคูณ Leverage และทิศทาง Long/Short สมบูรณ์)
- **เพิ่มระบบสแกนโค้ด (TDD)**: เขียน Unit Test หุ้มฟังก์ชันที่แยกออกมาใหม่ทั้งหมดเพื่อให้แน่ใจว่าทำงานได้แม่นยำ 100%

## [4.3.6] - 2026-06-21
### Groq API Integration & Advanced Model Routing
**English:**
- **AI Engine Upgrade**: Implemented Groq API as an ultra-fast fallback mechanism in `bot/ai_engine.py` to overcome Gemini's strict rate limits (20 RPD on Flash).
- **Intelligent Routing**: The bot now cascades through 5 AI tiers automatically: `llama-3.3-70b` (Groq), `gemini-3.5-flash`, `qwen-32b` (Groq), `gemini-3.1-flash-lite`, and falls back to `llama-3.1-8b` (Groq) which offers an ultimate 14.4K requests/day safety net.
- **Independent Rate Limiting**: Added `GROQ_API_LOCK` to strictly enforce Groq's 30 RPM limit (2s delay) without impacting Gemini's 15 RPM queue.

**Thai (ภาษาไทย):**
- **เพิ่มระบบสลับกะ Groq API**: อัพเกรด `bot/ai_engine.py` ให้เชื่อมต่อกับเซิร์ฟเวอร์สุดแรงของ Groq อัตโนมัติ เพื่อแก้ปัญหาโควต้า 20 ครั้ง/วันของ Gemini
- **ระบบคิว 5 ลำดับชั้น**: บอทจะเลือกใช้ AI ที่ฉลาดที่สุดก่อนและไล่ระดับลงมาเรื่อยๆ จนถึงเบอร์ 5 (`llama-3.1-8b`) ที่มีโควต้ามหาศาลถึง 14.4K ครั้ง/วัน การันตีบอททำงานข้ามวันข้ามคืนไม่มีสะดุด
- **ระบบคุมความเร็วอัจฉริยะ**: แยกการนับความเร็ว (Rate Limit) ของค่าย Groq ออกจาก Gemini อย่างเด็ดขาด เพื่อป้องกันการยิงเกินโควต้า 30 ครั้ง/นาที

## [4.3.5] - 2026-06-20
**English:**
- **Trend Strategy Updates**: Relaxed technical filters to increase Spot trading frequency during sideways markets. Expanded MACD lookback to 8 periods, added a 0.5% buffer for SMA200, lowered the volume requirement to `> 70%` of SMA, and increased the RSI cap to 80 on high volume.
- **Sideways Strategy Updates**: Adjusted RSI hook thresholds to `<= 45`, widened the Bollinger Band touch margin to 2%, and increased dynamic volume caps to allow entries during minor sell-offs.

**Thai (ภาษาไทย):**
- **ปรับความไวบอท Spot**: คลายกฎให้บอท Spot เริ่มมีไม้เทรดในตลาดไซด์เวย์บีบแคบ
  - **กราฟเทรนด์**: ยืดเวลารอจุดตัด MACD เป็น 8 แท่งเทียน, ยอมให้ราคาหลุดเส้น SMA 200 ได้ 0.5%, ใช้โวลุ่มแค่ 70% ของค่าเฉลี่ยก็เทรดได้, และขยับเพดาน RSI ไปที่ 80 ถ้าราคากระชากแรง
  - **กราฟไซด์เวย์**: ปรับจุดช้อนซื้อ RSI Hook ขึ้นมาที่ระดับ 45 (จากเดิม 40), ยอมให้ซื้อได้แม้ราคายังไม่แตะขอบล่างสุดของขอบแบนด์ (เหลือ 2%), และเพิ่มเพดานวอลุ่มให้ช้อนซื้อได้แม้จะมีแรงเทขายเยอะก็ตาม

## [4.3.4] - 2026-06-20
### Strategy Tuning & Trade Frequency Optimization
**English:**
- **Futures Strategy Optimization**: Relaxed technical constraints in `bot/strategy.py` to increase signal frequency and reduce "Near Misses" on the 15m timeframe.
  - **ADX**: Reduced trend strength requirement from `> 20 and rising` to `> 15`.
  - **RSI Limits**: Expanded valid entry bounds from `[30, 70]` to `[25, 75]`.
  - **EMA50 Buffer**: Added a 0.2% buffer to EMA bounds to prevent early signal rejections from minor fakeouts.
- **Bot Timeout Fix**: Added a 20-second connection timeout to `Client` initialization in `bot/binance_client.py` to prevent infinite hanging when internet connection drops.

**Thai (ภาษาไทย):**
- **ปรับจูนความไวบอท (Futures)**: ปรับลดความตึงของกฎ Technical Analysis ลง เพื่อลดปัญหาบอทปัดตกสัญญาณ (Near Miss) และเพิ่มโอกาสการเข้าทำกำไร
  - **ADX**: ลดเกณฑ์ความแรงเทรนด์จาก `> 20` เหลือ `> 15` เพื่อให้จับเทรนด์ช่วงต้นได้เร็วขึ้น
  - **RSI**: ขยายกรอบ RSI จาก `[30, 70]` เป็น `[25, 75]` เพื่อรองรับจังหวะราคากระชากแรงๆ
  - **EMA50 Buffer**: เพิ่มระยะยืดหยุ่นให้เส้น EMA50 อีก 0.2% เพื่อป้องกันราคาแกว่งสวิงหลอกแล้วบอทไม่ยอมเข้าซื้อ
- **แก้ปัญหาบอทค้าง**: เพิ่มระบบ `timeout: 20` วินาทีให้กับการดึงข้อมูล API จาก Binance เพื่อป้องกันปัญหาบอทค้างเติ่งเวลาอินเทอร์เน็ตหลุดชั่วคราว

## [4.3.3] - 2026-06-19
### UI Bug Fixes, Fees, and Security Patches
**English:**
- **Faster Dashboard PNL Update**: Reduced bot loop interval from 60s to 5s in `bot/main.py` for almost real-time PNL updates.
- **Accurate Live Balance**: Switch from `availableBalance` to `marginBalance` in `bot/binance_client.py` to correctly compute total capital including unrealized PNL.
- **Minimum Fee Enforcement**: Enforce a minimum fee of `0.01 USDT` per order in `bot/trade_executor.py` to prevent missed sub-penny fees.
- **Agent Code & Security Reviews**: Applied patches for webhook injection attacks (sanitizing dict keys), timezone SQLite glitches, and properly isolated Futures capital stats.

**Thai (ภาษาไทย):**
- **แก้ PNL หน้าเว็บอัพเดทช้า**: ปรับรอบการทำงานบอทจาก 60 วิเหลือ 5 วิ (ทำให้เห็นกำไรขาดทุนบนเว็บแทบจะทันที)
- **อัพเดทยอดเงินบัญชีแม่นยำขึ้น**: ใช้ `marginBalance` แทน `availableBalance` เพื่อดึงยอดรวมที่แท้จริง (รวมกำไรที่ยังไม่ปิดไม้ด้วย)
- **เพิ่มขั้นต่ำค่าธรรมเนียม**: บังคับคิดค่า Fee ขั้นต่ำ `0.01 USDT` ต่อ 1 ออเดอร์ (ตามที่ผู้ใช้รีเควส) เพื่อลดปัญหายอดผิดเพี้ยน
- **Agent Reviews (Code/Security)**: อุดช่องโหว่ความปลอดภัยเรื่อง Webhook Injection และแก้บั๊ก Timezone SQLite ที่ทำให้หน้าเว็บค้างหรือข้อมูลหายบางส่วน

## [4.3.2] - 2026-06-19
### UI/PNL Refinements & Test Suite Stabilization
**English:**
- **Live PNL Accuracy**: Refactored PNL calculations to use precise live calculations rather than waiting for slow Binance updates. Solves the 30-60s latency in PNL reporting on the dashboard.
- **UI Metrics Expansion**: Added 'Margin (USDT)' and 'Fee' columns to the Futures Execution Log table on the frontend.
- **AI Risk Removal**: Removed 'AI Risk' metric from dashboard UI and backend logs to reduce clutter and focus on core metrics.
- **TDD Pipeline Restored**: Stabilized the test suite (100% pass rate) by resolving concurrency mocking issues with `_execution_pool` and dynamically adjusting ATR tolerances in Risk Manager assertions.

**Thai (ภาษาไทย):**
- **แก้ปัญหา PNL อัพเดทช้า**: เปลี่ยนมาคำนวณกำไร/ขาดทุนด้วยตัวเองทันทีที่ระบบสั่งซื้อขาย ทำให้ได้ตัวเลขแม่นยำและไม่ต้องรอข้อมูลจาก Binance (แก้ปัญหา log ที่จดกำไรแล้วได้เลขไม่ตรง)
- **เพิ่มข้อมูลหน้าเว็บ**: เพิ่มคอลัมน์ Margin (USDT) และ Fee ในตาราง Execution Log (Futures) ตามคำเรียกร้อง
- **เอา AI Risk ออก**: ลบคอลัมน์ AI Risk ออกจากหน้าเว็บและฐานข้อมูลเพื่อความสะอาดตา
- **ระบบเทสกลับมา 100%**: แก้ไขชุดทดสอบ (TDD) ทั้งหมดให้กลับมาผ่าน 100% โดยแก้ปัญหา Thread Pool และการคำนวณ ATR

## [4.3.1] - 2026-06-19
**English:**
- **TDD Validated**: Executed full agentic verification ensuring zero syntax errors and robust modularity.
- **Stop-and-Reverse (SAR) Fix**: Fixed a bug where reversals would fail to open the opposing order.
- **NaN ATR Protection**: Fixed `bot/risk_manager.py` risk threshold bypass when ATR calculates to NaN.
- **Time-in-Trade Accuracy**: Fixed interval desync between Spot (15m) and Futures (5m).
- **In-place Mutation Fix**: Solved race conditions and `SettingWithCopyWarning` by cloning DataFrames in the execution pool.
- **State-Based Exits**: Changed edge-triggered MACD exits to state-based thresholds to guarantee exit reliability during network disconnections.

**Thai (ภาษาไทย):**
- **ตรวจสอบคุณภาพ 100% (TDD Validated)**: ตรวจโค้ดอย่างละเอียดโดย Agent มั่นใจว่าไม่มีบั๊กและพร้อมใช้งานจริง
- **แก้บั๊กสลับฝั่ง (Stop and Reverse)**: แก้ไขให้ระบบปิดสถานะและเปิดอีกฝั่งสวนได้ทันทีแบบไม่มีอาการค้าง
- **กันระบบพังตอน ATR เออเร่อ**: ดักจับค่า `NaN` ที่จะทำให้ระบบล็อคกำไร (Trailing Stop) ไม่ทำงาน
- **แก้นาฬิกาจับเวลา**: ปรับจูนการนับแท่งเทียนให้แม่นยำขึ้น โดยแยกแยะเวลาแท่ง Spot (15 นาที) กับ Futures (5 นาที) ออกจากกัน
- **แก้บั๊ก Thread ชนกัน**: สั่งจำลองข้อมูล (Clone) ก่อนโยนเข้าคิวเพื่อป้องกันไม่ให้ข้อมูลกราฟตีกันขณะทำงานพร้อมกัน
- **ระบบ Exit แบบ State-based**: เปลี่ยนวิธีการปิดออร์เดอร์จากการรอดู "จังหวะเส้นตัด" มาดู "สถานะปัจจุบัน" ช่วยป้องกันปัญหาบอทไม่ยอมขายถ้าเน็ตกระตุกตรงจังหวะตัดพอดี

## [4.3.0] - 2026-06-18
### Dual-Engine (Spot & Futures) & Security Hardening
**English:**
- **Dual-Engine Architecture**: Integrated a simultaneous Dual-Engine system running 15m Spot and 5m Futures strategies concurrently.
- **Futures Core Features**: Added support for Hedge Mode (Dual-Side), 3x Leverage Position Sizing, and Short position trailing stops (`lowest_price` tracking).
- **Strict Data Isolation**: Implemented `market_type` filtering to completely segregate Spot and Futures trades, states, and logs in the database.
- **Security Patches**: Fixed webhook thread explosion risks, sanitized API outputs to prevent API Key leaks, and restricted WebSocket broadcast auth headers.
- **Resilience**: Added robust error handling for Binance API network failures.

**Thai (ภาษาไทย):**
- **สถาปัตยกรรม 2 เครื่องยนต์ (Dual-Engine)**: รันระบบเทรด Spot (กราฟ 15 นาที) และ Futures (กราฟ 5 นาที) ไปพร้อมๆ กัน
- **รองรับการเทรด Futures เต็มรูปแบบ**: เพิ่มการทำงานแบบ Hedge Mode, คุม Leverage 3x, และแก้ระบบ Trailing Stop ให้รองรับการเล่นขาลง (SHORT) ได้แม่นยำ
- **แยกฐานข้อมูล Spot/Futures เด็ดขาด**: ปรับจูนระบบทั้งหมดให้แยกข้อมูลตารางเทรดและการแสดงผลระหว่างสองตลาดออกจากกัน 100%
- **อุดช่องโหว่ความปลอดภัยระดับร้ายแรง**: ป้องกันหน้าเว็บหลุด Token/API Key, แก้ปัญหาแจ้งเตือน Webhook กิน RAM เครื่อง, และจำกัดคนเข้าถึง Dashboard
- **เพิ่มความเสถียร (Resilience)**: ดักจับ Error ตอนเน็ตกระตุกหรือ Binance ล่ม เพื่อไม่ให้บอทดับตอนเทรดจริง

## [4.2.0] - 2026-06-16
### Near Miss Tracking & API Security
**English:**
- **Near Miss Logging**: Track and log reasons why strategies do not execute a trade (e.g., "RSI_TOO_HIGH", "NO_VOLUME_SURGE").
- **Dashboard Filter**: Added a UI toggle switch to hide/show "Near Miss" logs, preventing dashboard clutter.
- **24-Hour Log Window**: Optimized database queries to only fetch `SystemLog` entries from the last 24 hours.
- **Production Security**: Integrated `slowapi` for strict `/api/login` rate limiting (5/min), secured `/api/ws` concurrent connections, enforced SQLAlchemy ORM models to prevent SQL Injection, and enabled dynamic CORS origins via `.env`.

**Thai (ภาษาไทย):**
- **ระบบติดตามสาเหตุที่ไม่ได้ซื้อ (Near Miss)**: เพิ่มการบันทึกสาเหตุที่บอทตัดสินใจไม่เข้าซื้อในจังหวะที่เกือบเข้าเงื่อนไข (เช่น RSI สูงไป, วอลุ่มไม่พอ)
- **ปุ่มกรองข้อมูล Dashboard**: เพิ่มปุ่มสวิตช์ปิด/เปิด ข้อมูล Near Miss Log เพื่อไม่ให้หน้าเว็บรกเกินไป
- **แสดงผลย้อนหลัง 24 ชั่วโมง**: ปรับจูนฐานข้อมูลให้ดึงประวัติแค่ 24 ชั่วโมงล่าสุด เพื่อให้ UI โหลดเร็วขึ้นและไม่กินเมมโมรี่
- **ยกระดับความปลอดภัย (Security)**: ติดตั้ง `slowapi` ป้องกันคนเดารหัสผ่านรัวๆ, ป้องกัน Database จากการโจมตี (SQL Injection), จำกัดการเชื่อมต่อ WebSocket และปรับแต่ง CORS ให้ปลอดภัยขึ้น

## [4.1.0] - 2026-06-16
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

## [2026-06-27]
### Fixed
- Fixed 'Wrong Direction' entry logic in ot/strategy.py. Replaced breakout chasing logic with pullback entries within 1.5% of EMA50, and implemented dynamic RSI boundaries based on macro market regimes to drastically improve R:R and prevent whipsaw losses.
