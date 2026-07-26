# แผนยกระดับ Strategy Synthesizer, Trading Bot และ Web Dashboard

> วันที่จัดทำ: 2026-07-26
> สถานะ: Planning only — ยังไม่มีการแก้ implementation
> ขอบเขตหลัก: `bot_strategy_synthesizer_gpu.py`, `lab_gpu/`, live bot, API และ Web Dashboard

## CAPABILITY

ผู้ดูแลระบบต้องสามารถค้นหาและคัดกรองกลยุทธ์ที่มีกำไรสุทธิหลังต้นทุน มีความถี่รวมทั้งพอร์ต 1–10 trades/day และยังคงแข็งแรงบนข้อมูลที่ optimizer ไม่เคยเห็น จากนั้นนำ candidate ผ่านลำดับ `backtest → robustness → replay → shadow/paper → canary live → live` ที่ตรวจสอบย้อนหลังและ rollback ได้ โดย live bot ต้องควบคุมความเสี่ยงด้วยกฎ deterministic ส่วน Dashboard ต้องแสดงผลกำไร ความเสี่ยง ต้นทุน และความสดของข้อมูลตามความจริง

ผลลัพธ์ที่ต้องการไม่ใช่ “win rate สูงที่สุด” แต่เป็นระบบที่หาและ deploy กลยุทธ์ซึ่งมี positive expectancy, profit factor, drawdown และความสม่ำเสมอที่ยอมรับได้ เพราะ win rate สูงยังสามารถขาดทุนสะสมได้ถ้าขาดทุนต่อครั้งใหญ่กว่ากำไรต่อครั้ง

## CONSTRAINTS

### กฎคงที่

- ตีความเป้าหมาย 1–10 trades/day เป็นจำนวน entry รวมทั้ง portfolio ไม่ใช่ต่อเหรียญ เว้นแต่เจ้าของระบบยืนยันเป็นอย่างอื่น
- ห้ามนำอันดับจาก leaderboard ไปแก้ `bot/strategy.py` หรือ deploy live โดยตรง
- Hard risk controls, position sizing, stop protection, stale-data gate และ execution gate ต้องเป็น deterministic logic; AI Council ใช้เป็น optional veto/annotation ไม่ใช่ risk authority
- ผลประเมินทุกตัวต้องรวม fee, spread, slippage และ funding ตามประเภทตลาด พร้อม cost stress
- ต้องมี untouched out-of-sample data และ reproducibility metadata ก่อนเรียก candidate ว่า “ผ่าน”
- ทุก candidate ต้องระบุ code version, data fingerprint, genome schema version, seed, cost model และผล validation
- การเปลี่ยน implementation ในอนาคตต้องใช้ TDD, coverage รวมอย่างน้อย 80% และผ่าน unit/integration/E2E ตามกฎโปรเจกต์
- ไม่มีแผนใดรับประกันกำไร เป้าหมายคือเพิ่มคุณภาพหลักฐาน ลด downside และควบคุม deployment risk

### ข้อจำกัดจากระบบปัจจุบัน

- `bot_strategy_synthesizer_gpu.py` เป็น wrapper; logic หลักอยู่ใน `lab_gpu/`
- `bot_strategy_synthesizer_gpu.py`/`lab_gpu/` คือระบบ Strategy Lab หลักที่ใช้งานจริงและเป็น optimization target ของแผนนี้
- `bot_strategy_synthesizer.py` เป็น legacy CPU รุ่นเก่าที่เลิกใช้งานแล้ว ไม่ใช่ fallback ของ wrapper ปัจจุบัน อยู่นอกขอบเขตการพัฒนาและไม่ใช่ parity target
- `lab_gpu/cpu_kernel.py` เป็น no-CUDA fallback ภายใน package หลัก จึงต้อง conform กับ active GPU genome หากยังคงรองรับ fallback นี้
- Live bot ยังไม่ได้โหลด parameters จาก leaderboard กลยุทธ์ที่ค้นพบจึงยังไม่ใช่กลยุทธ์ที่ bot ใช้จริง
- ฐานข้อมูล local `trades_spot.db`/`trades_futures.db` ไม่มี closed-trade history ชุดปัจจุบัน ส่วน `trades.db` มีเพียง legacy records จำนวนน้อย จึงยังสรุป root cause ของช่วงขาดทุนล่าสุดจาก repo อย่างเดียวไม่ได้
- ต้องขอ production trade/fill/equity data แบบตัด secrets ออกก่อนปรับ threshold หรือ risk budget จากผลจริง

## CURRENT AUDIT FINDINGS

### P0 — ความน่าเชื่อถือของ Strategy Lab

1. **80 genes แต่ GPU ใช้จริง 29 genes**
   - Search space ใน `lab_gpu/evolution_engine.py` สุ่มประมาณ 80 parameters
   - `GENOME_PARAM_ORDER` และ GPU mega-kernel pack เพียง 29 parameters
   - indicator windows หลายตัวเป็นค่าคงที่ แม้ optimizer สุ่ม window ชื่อเดียวกัน
   - ผลคือ 51 parameters ใน candidate ปัจจุบันไม่เปลี่ยนผล mega-kernel แต่ยังทำให้ JSON ดูแตกต่าง

2. **Top 10 เป็น duplicate behavior**
   - Leaderboard ปัจจุบันทั้ง 10 รายการมี fitness, 1Y return, win rate, max drawdown และ trade count เท่ากัน
   - Deduplication ใช้ JSON ของ parameters ทั้งหมด จึงมอง ignored genes ที่ต่างกันว่าเป็นคนละกลยุทธ์
   - ต้อง deduplicate ด้วย active phenotype, signal hash หรือ trade-ledger hash

3. **ยังไม่มี OOS/walk-forward จริง**
   - 1M/3M/6M/1Y ใช้ช่วงปลายของ dataset เดียวกันแบบซ้อนกัน
   - Fitness นำผลจาก nested windows มาบวกซ้ำ ทำให้ข้อมูลล่าสุดมีน้ำหนักซ้ำ
   - Optimizer เลือกและรายงานผลจากข้อมูลเดียวกัน จึงมี data-snooping risk สูง

4. **GPU main path, `lab_gpu` CPU fallback และ production semantics ยังไม่มีหลักฐานว่า conform กัน**
   - ความต่างระหว่าง legacy `bot_strategy_synthesizer.py` กับ GPU ไม่ถือเป็น regression เพราะ legacy CPU เลิกใช้งานแล้ว
   - สิ่งที่ต้องพิสูจน์คือ GPU kernel เทียบกับ `lab_gpu/cpu_kernel.py`, deterministic test oracle และ production replay ที่ใช้ specification เดียวกัน
   - GPU TP fill อาจดีกว่าราคา trigger, stop ไม่จำลอง gap/adverse fill และ open position ตอนจบช่วงไม่ถูก liquidate/mark-to-market
   - Drawdown วัด realized balance ไม่ใช่ portfolio equity ที่รวม unrealized PnL

5. **Portfolio accounting ยังไม่เหมือน live**
   - แต่ละ symbol เริ่มทุนแยกกัน จากนั้นเฉลี่ย return แต่รวม trade count
   - ไม่จำลอง concurrent positions, shared margin, leverage, portfolio exposure และ correlated losses
   - `kelly_fraction_cap × 4` ไม่ใช่ Kelly ที่คำนวณจากสถิติจริง

6. **Fitness ยังขาด robustness metrics**
   - ยังไม่มี true expectancy, payoff ratio, profit factor, Sharpe, Sortino, true Calmar, CVaR, recovery factor, losing streak, monthly consistency และ confidence interval
   - Frequency ใช้ annual average จึงอาจผ่านทั้งที่บางวันไม่เทรดและบางวันเกิน 10 ครั้ง
   - เอกสาร Phase 31 กับ threshold ใน implementation ปัจจุบันไม่ตรงกัน

7. **Search ทำซ้ำไม่ได้และ mutation อาจหลุด bounds**
   - ใช้ in-memory study และ random seed ที่ไม่กำหนด
   - Mega-batch ส่งผลกลับ Optuna เฉพาะ TPE subset ขณะที่ mutants ส่วนใหญ่ไม่เป็น observation ของ sampler
   - Mutation ไม่มี typed per-gene clamp ชุดเดียวกับ search bounds

### P0 — ความเสี่ยงของ Live Bot

1. **Position sizing ไม่ผูกกับ stop distance**
   - Futures ใช้ allocation จาก AI 10–40% ของ margin ต่อ trade
   - เปิดพร้อมกันได้ 5 positions โดยยังไม่มี portfolio heat/correlation cap
   - ไม่มี daily/weekly loss limit, rolling drawdown limit, losing-streak guard หรือ daily trade cap

2. **Futures stop ยังพึ่ง local process**
   - มี exchange-native TP/SL helper แต่ live flow ยังเก็บ SL/TP ไว้ใน state แล้วตรวจผ่าน WebSocket
   - หาก process/network/stream ค้าง position อาจไม่มี protective stop ที่ exchange

3. **ATR/RSI ระหว่างถือ position อาจ fallback ผิด scale**
   - indicator คำนวณตอน candle close แต่ risk loop อาจอ่าน buffer ที่ไม่มี calculated columns
   - fallback ATR แบบค่าคงที่ใช้ไม่ได้กับทุก symbol และอาจทำให้ trailing/stop ผิด

4. **Fill จริงไม่ใช่ source of truth**
   - Executor ได้ average fill/quantity แต่ state ตอนเปิด position ยังใช้ signal price/qty ก่อน execution
   - ยังขาด order lifecycle, idempotency, partial-fill reconciliation และ explicit FILLED validation
   - บาง error path ล้าง local state ทั้งที่ต้องพิสูจน์ก่อนว่า position ที่ exchange ปิดจริง

5. **Hedge mode กับ state model ไม่สอดคล้อง**
   - Exchange ใช้ Hedge Mode แต่ state เก็บ position เดียวต่อ symbol
   - LONG/SHORT พร้อมกันอาจ overwrite กันใน reconciliation

6. **Regime และ AI authority ยังไม่เหมาะกับ hard risk**
   - Regime ใช้ timeframe/threshold ชุดค่อนข้างหยาบและใช้ร่วม 20 symbols
   - AI model availability, prompt และ latency อาจเปลี่ยน decision behavior
   - ต้องตรวจ signal TTL, spread, liquidity และ hard risk ก่อน/หลัง AI อย่าง deterministic

7. **ยังวิเคราะห์สาเหตุขาดทุนสะสมจาก metrics ไม่ได้**
   - API มี cumulative PnL/win rate แต่ขาด equity curve, drawdown, expectancy, MAE/MFE, funding, slippage และ attribution แยก strategy/regime/symbol
   - PnL% บน Dashboard ยังไม่ใช่ portfolio return ที่สร้างจาก equity curve

### P0 — UI/UX ที่อาจทำให้เข้าใจผิด

- `SYSTEM LIVE` และ API status ยังไม่สะท้อน heartbeat/data age จริง
- หน้า Strategy Lab แสดง `running` จาก progress file เก่าโดยไม่เตือน stale
- Infinite mode แสดง progress 100% แทน indeterminate
- ปุ่ม Pause/Resume ขาด confirmation/loading/error state และหน้า Lab มี market mapping ที่ API ไม่รองรับ
- `Live Balance` เป็น USDT cash ไม่ใช่ total equity
- `Total Executed Trades` ใช้ wins + losses จึงไม่เท่าจำนวน executions จริง
- Estimated fee แสดงเหมือน actual fee
- Dashboard ยังไม่มี equity curve/drawdown view จึงมองไม่เห็นช่วงขาดทุนสะสม

## IMPLEMENTATION CONTRACT

### Actors

- Operator: ตรวจสุขภาพระบบ เลือก candidate อนุมัติ stage และ rollback
- Strategy Lab: ค้นหา/ประเมิน candidate แต่ไม่มีสิทธิ์ deploy live เอง
- Validation Pipeline: ตรวจ GPU/fallback/production conformance, OOS, robustness และ promotion gates
- Trading Bot: ใช้ strategy manifest ที่อนุมัติแล้วและบังคับ hard risk controls
- Dashboard/API: แสดงข้อมูลตาม source of truth และสถานะ deployment

### Surfaces

- Lab CLI/runner และ Optuna storage
- Versioned strategy manifest/registry
- Backtest/replay engine และ trade ledger
- Live execution/risk/reconciliation services
- Performance, risk, health และ deployment APIs
- Risk-first Dashboard และ Strategy Lab comparison view

### Candidate lifecycle

`DISCOVERED → VALIDATED_IS → VALIDATED_OOS → ROBUSTNESS_PASSED → REPLAY_PASSED → SHADOW → PAPER → CANARY → LIVE`

เส้นทางผิดพลาด:

`ANY_STAGE → REJECTED`

เส้นทางเสื่อม:

`CANARY/LIVE → PAUSED → ROLLED_BACK`

ห้ามข้าม stage และทุก transition ต้องมี actor, timestamp, evidence, version และ reason

### Required candidate artifact

- strategy ID/version และ immutable checksum
- active parameters เท่านั้น พร้อม typed schema/bounds
- code commit/version และ simulator version
- dataset hash, symbols, timeframe, date ranges และ split map
- seed/seed ensemble และ optimizer configuration
- fee/spread/slippage/funding assumptions
- IS, validation, OOS, walk-forward และ stress metrics
- trade ledger/equity curve references
- approved risk limits และ supported regimes/symbols
- promotion status, approver, rollback target และ expiry/revalidation date

## TARGET KPI AND HARD GATES

ค่าต่อไปนี้เป็น proposed defaults ต้องยืนยันก่อน implementation:

### Strategy eligibility

- OOS net return > 0 หลังต้นทุน และต้องชนะ benchmark/current bot ภายใต้ risk budget เดียวกันตาม excess-return หรือ return/drawdown gate ที่อนุมัติ
- Portfolio entries 1–10 trades/day
- วันที่เกิน 10 entries = 0 ใน validation; หากจำเป็นต้อง burst ต้องกำหนด exception เป็น policy
- Aggregate non-overlapping OOS folds มี total trades ≥ 300; final untouched holdout ใช้ sample gate แยกตามระยะ 3–6 เดือนและรายงาน confidence interval โดยห้ามรวมช่วง overlap ให้ครบจำนวน
- Profit factor ≥ 1.25 และ ≥ 1.10 ที่ cost stress 2×
- Positive expectancy หลัง fee/slippage/funding
- OOS win rate ≥ 50% และ Wilson 95% lower bound ≥ 45% เป็น secondary target ไม่ใช่ hard gate เดี่ยว; กลยุทธ์ payoff สูงอาจผ่านได้เมื่อ expectancy/PF/drawdown ผ่านเกณฑ์ที่เข้มกว่า
- Max portfolio drawdown ≤ 15%
- Sharpe ≥ 1.0, Sortino ≥ 1.5, true Calmar ≥ 0.8
- Profitable walk-forward folds ≥ 70% โดยมีจำนวน folds ขั้นต่ำที่อนุมัติ
- Profitable OOS months ≥ 70% โดยมีจำนวนเดือนขั้นต่ำที่อนุมัติ
- กำไรจาก symbol เดียวไม่เกิน 25% ของกำไรรวม
- ต้องไม่พึ่ง regime เดียวหรือ moonshot ไม่กี่รายการ
- Parameter neighborhood ±5–10% อย่างน้อย 70% ของ perturbation samples ที่กำหนดยัง PF > 1 และ net return > 0

### Live risk defaults

- Risk per trade เริ่ม 0.25–0.50% ของ equity โดยคำนวณจาก entry-to-stop distance
- Portfolio open risk cap เริ่ม 2% ของ equity
- Daily loss circuit breaker เริ่ม 1.5–2.0% ของ starting-day equity
- Weekly loss circuit breaker เริ่ม 4–5%
- Auto-pause เมื่อ losing streak, rolling expectancy, drawdown หรือ execution health เกิน threshold ที่อนุมัติ
- จำกัด 1–10 new entries/day รวม Spot/Futures ตาม policy ที่ยืนยัน
- Candidate canary เริ่มที่ 5–10% ของ normal risk budget

ตัวเลข risk budget ห้าม hardcode ตามแผนนี้จนกว่าเจ้าของระบบยืนยัน

## PHASED ROADMAP

## Phase 0 — Freeze Baseline และสร้าง Data Contract

### งาน

- นิยามให้ตรงกัน: signal, entry, fill, round trip, trade/day, fee, funding, realized/unrealized PnL, equity, drawdown, exposure และ win/loss
- ยืนยันว่า 1–10 trades/day คือ portfolio entries และกำหนด timezone/day boundary
- Export production trade, fill, funding, balance/equity snapshot, order reject และ signal log โดยตัด secrets
- สร้าง baseline report แยก Spot/Futures, symbol, strategy, regime, hour/day และ exit reason
- วัด expectancy, profit factor, avg win/loss, max drawdown, losing streak, fees, slippage, MAE/MFE และ trades/day distribution
- Freeze baseline ด้วย code hash, data hash, seed, fee tier, leverage และ symbol universe
- สร้าง metric dictionary/API schema เดียว

### Exit criteria

- ตัวเลข Dashboard, DB report และ exchange statement reconcile ได้ภายใน tolerance
- ระบุ top loss contributors ได้อย่างน้อยตาม symbol/strategy/regime/exit/cost
- ได้ risk budget และ KPI ที่เจ้าของระบบอนุมัติ

## Phase 1 — GPU Main-Path Truth และ Fallback/Production Conformance

### งาน

- กำหนด GPU simulator เป็น optimization/ranking engine หลัก และออกแบบ execution/accounting specification เดียวกับ `lab_gpu` CPU fallback, deterministic test oracle และ production replay
- กำหนด next-bar entry, same-bar SL/TP policy, gap/adverse fill, trailing update order และ end-of-window liquidation
- เพิ่ม maker/taker fee, spread, liquidity/volatility slippage และ funding
- สร้าง shared portfolio equity curve รวม unrealized PnL, shared margin, leverage, concurrency และ exposure caps
- สร้าง golden deterministic trade ledgers สำหรับ strategy fixtures
- เทียบ GPU main path/`lab_gpu` CPU fallback/reference replay ทีละ event ภายใน tolerance: timestamp, signal, side, entry/exit, reason, exposure, fee/funding, realized/unrealized PnL, equity และ drawdown
- ระบุ `bot_strategy_synthesizer.py` และ legacy backtests ว่า deprecated/non-authoritative และห้ามใช้เป็น promotion evidence
- ไม่ต้องรักษาผลลัพธ์หรือ performance parity กับ legacy CPU script
- เพิ่ม dependency test ว่า GPU wrapper และ promotion pipeline ไม่ import หรืออ่านผลจาก legacy `bot_strategy_synthesizer.py`
- แยก simulated fill conformance ออกจาก live execution reconciliation; ไม่บังคับให้ราคา live fill เท่าราคา simulation

### Tests first

- GPU main path/`lab_gpu` CPU fallback/production-replay event-ledger conformance
- Same-bar SL/TP, gap, partial fill, trailing และ end liquidation
- Fee/slippage/funding ที่ 1×/1.5×/2×
- Unrealized equity drawdown และ concurrent positions
- Long/short, spot/futures และ leverage accounting

### Exit criteria

- ไม่มี unexplained ledger divergence
- Cost model configurable/versioned
- Open positions ถูก mark-to-market หรือปิดตาม policy เสมอ

## Phase 2 — Data Quality และ Walk-Forward Validation

### งาน

- ตรวจ missing/duplicate/out-of-order candles, timestamp continuity, symbol delisting และ zero/NaN indicators
- ห้าม `fillna(0)` กลบ invalid warmup/data silently
- ใช้ข้อมูลหลาย market regimes และอย่างน้อย 2–3 ปีเมื่อ data availability รองรับ
- แยก warmup window ออกจาก measurement window
- ใช้ rolling walk-forward เช่น train 12M → validate 3M → test 3M แล้วเลื่อนหน้าต่าง
- กัน final untouched holdout 3–6M ที่ optimizer ห้ามเห็น
- เพิ่ม cross-symbol holdout และ regime buckets: trend, sideways, high-volatility, crash/recovery
- ใช้ purge/embargo เมื่อ feature/label horizon อาจ overlap

### Exit criteria

- Split manifest deterministic และผ่าน no-leakage tests
- รายงานผลแยก fold/regime/symbol พร้อม confidence intervals
- ไม่มี final holdout access ระหว่าง search

## Phase 3 — Typed Genome Schema และ Reproducible Search

### งาน

- สร้าง schema เดียวสำหรับ gene: name, type, min/max, step, default, conditional strategy, mutation rule, GPU index และ production mapping
- ตัด 51 dead genes ออกจาก search ก่อน หรือ implement ให้มีผลครบ GPU main path/`lab_gpu` CPU fallback/production replay
- เพิ่ม active-gene sensitivity test: เปลี่ยนค่าต้องเปลี่ยน signal/ledger มิฉะนั้นห้าม optimize
- Clamp mutation ด้วย schema และ reject invalid genome ก่อน evaluate/save
- ใช้ persistent Optuna storage, deterministic seed และ seed ensemble
- บันทึก study metadata/checkpoint เพื่อ resume/reproduce
- ใช้ conditional search space ต่อ strategy type
- ส่ง mutant observations กลับ sampler ตาม design ที่เลือก
- Deduplicate จาก active phenotype/signal/trade-ledger hash
- กำหนด diversity quota ต่อ strategy/regime เพื่อไม่ให้ Top 10 เป็นผลเหมือนกัน

### Exit criteria

- 100% active genes มี effect test และ production mapping
- Run เดิม reproduce ranking/metrics ได้ภายใน tolerance
- Top candidates ไม่มี duplicate phenotype

## Phase 4 — Hard Gates และ Multi-Objective Robustness

### งาน

- ใช้ hard eligibility gates ก่อน scoring
- เปลี่ยนจาก profit-dominant composite score เป็น Pareto ranking
- Objectives: OOS return, max DD, Sortino/Calmar, PF, expectancy, frequency deviation, cost sensitivity และ stability
- วัด daily trade distribution: median, P90/P95, active-day ratio และ violation days
- Bootstrap/Monte Carlo trade order และ 95% confidence intervals
- Parameter perturbation ±5–10%
- Stress fee/slippage/funding 1×/1.5×/2×
- ตรวจ IS→validation→OOS performance decay
- วัด optimizer selection bias ด้วย Deflated Sharpe Ratio และ Probability of Backtest Overfitting หรือวิธีเทียบเท่าที่คำนึงถึงจำนวน trials
- ใช้ final holdout แบบ one-shot; หาก fail ให้ reject research version และห้าม tune แล้วทดสอบ holdout เดิมซ้ำ
- Reject concentration จาก symbol/month/regime/moonshots
- ตรวจ capacity/market impact: notional ต่อ depth/volume, implementation shortfall และ slippage drift threshold
- Benchmark กับ current live bot, buy-and-hold ตาม risk budget และ no-trade baseline

### Exit criteria

- Candidate ทุกตัวผ่าน hard gates และ robustness suite
- Ranking อธิบายได้ว่าชนะเพราะอะไรและเสี่ยงตรงไหน
- KPI ใน `PROJECT_PLAN.md`, tests และ implementation ตรงกัน

## Phase 5 — Live Hard Risk และ Execution Safety

### งาน

- Position sizing แบบ fixed-fractional: `risk budget / stop distance` แล้ว cap ด้วย margin, notional, exposure และ liquidity
- เอา allocation authority ออกจาก LLM
- เพิ่ม portfolio heat, per-symbol cap, correlated exposure และ Spot/Futures combined risk
- เพิ่ม daily/weekly loss, rolling drawdown, losing-streak และ 1–10 entries/day circuit breakers
- วาง exchange-native reduce-only/close-position stop ทันทีหลัง fill
- หากวาง stop ไม่สำเร็จให้ fail closed และปิด/reconcile position ตาม policy
- ใช้ actual fill price/quantity/commission เป็น source of truth
- เพิ่ม order lifecycle และ idempotent client order identity
- รองรับ partial fills, retry, stale-signal TTL และ reconciliation-required state
- ตัดสินใจ Hedge Mode: เปลี่ยน One-way หรือปรับ state key เป็น `(symbol, side)`
- คำนวณ ATR/RSI จาก snapshot ที่มี timestamp/data-quality flag
- เพิ่ม spread/depth/volatility/funding/session/news-freshness deterministic gates
- ให้ AI Council เป็น veto/annotation หลัง hard gates

### Tests first

- Risk sizing ตาม stop distance และ equity
- Portfolio/daily/weekly/drawdown circuit breakers
- Native stop placement/verification/failure close
- Partial fill, duplicate submit, retry และ reconciliation
- Stale signal/data, spread/slippage guard และ AI timeout
- Hedge/one-way position state

### Exit criteria

- ไม่มี unprotected live position
- State reconcile กับ exchange ได้หลัง restart/network failure
- Hard loss/risk limits บังคับได้โดยไม่ขึ้นกับ AI availability

## Phase 6 — Strategy Manifest และ Promotion Pipeline

### งาน

- สร้าง immutable strategy manifest ตาม contract
- เพิ่ม mapping จาก active lab parameters ไป production strategy config
- ห้าม manual copy/paste gene JSON ลง live code
- เพิ่ม stage approval, audit trail, expiry/revalidation และ rollback target
- Production replay ต้องผ่านก่อน shadow/paper
- แยก immediate health stop ออกจาก statistical performance decay; decay gate ต้องมี minimum trades/time window/confidence ก่อน auto-demote
- กำหนด rollback policy สำหรับ position ที่ยังเปิด: flatten ทันที, ใช้ exit policy เดิมจนปิด หรือ handoff แบบ versioned ห้ามเปลี่ยน exit semantics กลาง position โดยไม่ตั้งใจ
- Auto-demote เมื่อ rolling expectancy ≤ 0, PF < 1, slippage drift, drawdown หรือ cost สูงกว่า gate หลังผ่าน minimum evidence
- เปรียบเทียบ backtest expectation กับ live results แยก strategy version/regime

### Promotion gates

1. Replay ผ่าน GPU/fallback/production conformance และ no-leakage
2. Shadow ไม่มี stale/unprotected/reconciliation breach
3. Paper อย่างน้อย 30–60 วันและจำนวน trades ขั้นต่ำที่อนุมัติ
4. Paper PF/expectancy/drawdown/frequency ผ่าน KPI หลังต้นทุน
5. Canary 1–2 symbols ที่ 5–10% risk budget หลังผ่าน capacity/market-impact gate
6. เพิ่ม risk ทีละขั้นเมื่อผ่าน minimum calendar window, minimum closed trades และ confidence gate ที่อนุมัติ
7. Auto rollback เมื่อชน hard stop หรือ health breach

## Phase 7 — Risk-First Web Dashboard

### P0 correctness

- แสดง health แยก Bot heartbeat, market tick, WebSocket, Binance API, DB และ data age
- เพิ่ม `STALE/OFFLINE/RECONNECTING` และ Last updated
- Infinite lab mode ใช้ indeterminate progress
- ซ่อน Pause ใน Lab; เพิ่ม confirmation, loading, disabled และ success/error toast
- แก้ชื่อ metric: Cash balance, Total equity, Closed trades, Executions, Portfolio return
- แยก actual fee กับ estimated fee
- ทำ API/leaderboard schema ให้ตรงกับ UI และเลิก fallback `% × 10` ที่ดูเหมือนเงินจริง

### P1 risk cockpit

- Total equity
- PnL วันนี้/7D/30D พร้อม previous-period comparison
- Realized/unrealized PnL
- Equity curve + drawdown overlay
- Daily PnL heatmap
- Current/max drawdown
- Open risk เทียบ risk budget
- Fees/funding/slippage
- Trades today เทียบช่วง 1–10
- Consecutive losses และ circuit-breaker state
- Attribution ตาม strategy/version/regime/symbol

### Positions/Trades

- แสดง SL/TP, risk USDT/% equity, distance to stop/liquidation, holding time, R-multiple, concentration และ stale price
- Filter/search/export execution history
- timezone ชัดเจน, sticky header และ mobile card view
- System Debug Log เป็น collapsible diagnostics drawer พร้อม severity/search/unread errors

### Strategy Lab

- Filter ตาม trades/day, OOS status, PF, expectancy, drawdown, win rate และ min samples
- Robustness Score และ pass/fail badges ของแต่ละ gate
- Compare 2–4 candidates: equity/drawdown, monthly returns, per-symbol/regime และ parameter diff
- ซ่อน Genome JSON หลัง Expand
- เปลี่ยน `Copy AI Command` เป็น `Stage Candidate for Review`
- แสดง active strategy version/hash, stage, deployment date และ rollback version

### Design direction

- ใช้แนว quant risk console ให้ PnL/risk เด่นกว่า AI commentary
- ลด neon/glow ของ non-interactive cards
- ไม่พึ่งสีอย่างเดียว; ใช้ icon/label/pattern
- เพิ่ม focus-visible, ARIA, modal focus trap, reduced-motion และขนาดข้อความขั้นต่ำ
- รองรับ mobile, empty/error/skeleton/reconnecting และ locale ไทย/อังกฤษ

### Proposed APIs

- `/api/performance`
- `/api/risk_snapshot`
- `/api/health`
- `/api/strategy/deployment`

API ทุกชุดต้องมี schema validation, authentication/authorization, rate limit และ data timestamp

## Phase 8 — Verification, Rollout และ Operations

### Automated verification

- Unit, integration และ E2E ครบ critical paths
- Coverage รวม ≥80%
- Reproducible backtest and walk-forward reports
- Security review สำหรับ control/deployment endpoints
- Load/latency test ของ signal→decision→order path
- Failure injection: WS down, API timeout, DB unavailable, partial fill, native stop reject

### UI E2E

- Login/session expiry
- WebSocket disconnect/reconnect/stale
- Spot/Futures/Lab switching
- Pause confirmation/error/double-click
- Stale Lab progress
- Leaderboard filter/sort/compare/stage
- Null/NaN/partial payload
- Mobile overflow, keyboard navigation และ accessibility scan

### Operational alarms

- Unprotected position
- Reconciliation mismatch
- Stale market/indicator data
- Daily/weekly/drawdown circuit breaker
- Cost/slippage drift
- Strategy performance decay
- Queue latency/expired signal
- Dashboard metric freshness

## NON-GOALS

- ไม่ปรับสูตร strategy, thresholds, leverage หรือ position size ในงาน planning รอบนี้
- ไม่รัน optimizer/backtest ใหม่เพื่อเลือก champion
- ไม่ deploy, restart, pause หรือส่ง order ใด ๆ
- ไม่รับรองว่า win rate หรือกำไรย้อนหลังจะเกิดซ้ำในอนาคต
- ไม่ใช้ UI redesign เป็นวิธีแก้ profitability โดยตรง; UI มีหน้าที่ช่วยมองเห็นและควบคุม
- ไม่เพิ่ม strategy types จน simulator conformance และ OOS gates ผ่านก่อน

## OPEN QUESTIONS

คำถามเหล่านี้ไม่ขวางการอ่านแผน แต่ต้องตอบก่อน implementation:

1. 1–10 trades/day ให้นับ entry รวม Spot+Futures หรือแยก engine?
2. Risk budget ที่ยอมรับได้ต่อ trade/day/week และ max portfolio drawdown เท่าไร?
3. ต้องการใช้ Hedge Mode ต่อ หรือยอมใช้ One-way Mode เพื่อทำ state ให้เรียบง่าย?
4. Production fee tier, maker/taker mix, funding และ slippage จริงย้อนหลังเป็นเท่าไร?
5. มี production fills/equity history อย่างน้อย 30–90 วันให้วิเคราะห์หรือไม่?
6. Candidate ต้อง paper 30 หรือ 60 วัน และต้องมี minimum closed trades เท่าไร?
7. Symbol universe จะคง 20 เหรียญ หรือเลือกตาม liquidity/spread แบบ dynamic?
8. ต้องการ separate capital/risk budgets ระหว่าง Spot และ Futures หรือ pool เดียว?
9. ผู้ใดมีสิทธิ์ approve promotion/rollback และต้องมี two-person approval หรือไม่?

## HANDOFF

สถานะปัจจุบัน: **Needs product/risk clarification and architecture review before implementation**

ลำดับ handoff เมื่ออนุมัติแผน:

1. ยืนยัน KPI/risk budget และตอบ Open Questions
2. ทำ Phase 0 baseline/data contract
3. ใช้ `tdd-workflow` สร้าง GPU main-path/fallback/production-replay conformance และ data-split tests ก่อน implementation
4. ใช้ `security-review` กับ live execution และ control/deployment APIs
5. ใช้ `verification-loop` ตรวจ simulator, risk, rollout และ UI E2E

## FILE IMPACT MAP สำหรับงานในอนาคต

ไฟล์/โมดูลที่คาดว่าจะได้รับผลกระทบ แต่ยังไม่ได้แก้ในรอบนี้:

- Strategy Lab หลัก: `bot_strategy_synthesizer_gpu.py`, `lab_gpu/config.py`, `data_loader.py`, `gpu_kernel.py`, `evaluator.py`, `fitness.py`, `evolution_engine.py`, `leaderboard_sync.py`
- Active no-CUDA fallback/reference: `lab_gpu/cpu_kernel.py`
- Legacy CPU ที่ไม่พัฒนาต่อ: `bot_strategy_synthesizer.py`
- Live bot: `bot/config.py`, `strategy.py`, `signal_evaluator.py`, `risk_manager.py`, `trade_executor.py`, `state.py`, `websocket_manager.py`, `binance_client.py`
- Data/API: `bot/database.py`, `api/server.py`
- UI: `dashboard/index.html`, `dashboard/styles.css`, `dashboard/js/ui_status.js`, `ui_trades.js`, `ui_lab.js`, `ui_logs.js`, `bot_control.js`, `websocket.js`
- Tests: GPU main-path/`lab_gpu` fallback/production-replay conformance, legacy dependency isolation, risk manager, allocation, executor, state/reconciliation, API, dashboard E2E/accessibility

## DEFINITION OF DONE ของแผนใหญ่

- Strategy candidate ผ่าน untouched OOS, walk-forward, cost stress และ robustness gates
- GPU main path/`lab_gpu` CPU fallback/production replay ให้ event ledger ตรงกันตาม tolerance โดยแยก live fill reconciliation ออกจาก simulated fill
- Frequency รวม portfolio อยู่ 1–10 entries/day ตาม policy ที่อนุมัติ
- Live bot ใช้ stop-distance risk sizing, native protection และ portfolio circuit breakers
- Strategy promotion/rollback มี versioned evidence และ audit trail
- Dashboard แสดง equity/drawdown/risk/cost/health ตาม source of truth และเตือน stale data
- Shadow/paper/canary ผ่านเกณฑ์ก่อนเพิ่ม live risk
- Test coverage ≥80%, critical unit/integration/E2E ผ่าน และไม่มี unresolved critical security finding
