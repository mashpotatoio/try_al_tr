# Actual project and competition discrepancies

No Git root or applicable AGENTS.md was present. The task therefore lives in an isolated directory with hash manifests and source archives rather than Git commits. Original files requiring modification: none.

## Loading, timing, and state

`TradingSimulation.ipynb` imports `strategy.<name>`, finds the matching class, creates `TradeSim.tradeSim`, and creates one `StrategyHandler` per symbol. Each handler owns a strategy instance and a single-symbol BarAggregator. `process_row` updates that symbol's cumulative Buy/Sell volume before calling `on_data`. Every tick delivers a forming OHLCV bar; `Timestamp` is the start of its bucket, not the tick time. History is available in constructors when `current_date` is supplied, excludes that date, and is capped at 1,000 bars.

The notebook interleaves each symbol's nth row. It does not establish global chronology. The research runner stable-sorts by tick time and retains source row order for ties. Signals use only prior-day history, so they do not assume all same-time cross-symbol events have arrived. Handlers run until 10:30 on decision days; beyond that, and on holding days, no strategy action is possible and no orders rest, so the runner reads the remaining ticks for marks only. Equity supplied to decisions is independently marked from observations already replayed; engine marks are refreshed before fills and at EOD.

`TradeSim` defaults to loading persistent portfolio JSON. Portfolio, error and transaction-log paths are hardcoded under relative `result/`; the constructor's `folder` parameter does not consistently redirect them. Every native strategy run therefore gets its own subprocess and working directory. Portfolios carry across sessions only within that run. Handlers and execution books are reconstructed each day; order counters start fresh per experiment. Finalization precedes saving so EOD snapshots survive reload.

## Orders and accounting

`create_order_at_market` accepts only the current tick's symbol and executes synchronously at last price plus/minus one tick. `create_order_to_limit` adds a resting order. The notebook matches after the callback, so a new limit can match the current tick. First-match quote estimates depend on the tick's Buy/Sell flag; resting limits subsequently match at their limit. Auctions do not match limits.

Orders are full quantity or no fill. There is no IOC instruction or partial-fill model. A contract test verifies that a 200-share native market order can fill on a 100-share tick when the cumulative-volume gate allows it. Pending buys reserve no engine cash. The research order layer reserves commitments and updates holdings only on confirmed fills; synthetic tests cover partial fills and canceled remainders. Native main runs have immediate Market orders, so pending commitments do not persist.

The engine applies commission 0.00157 and VAT 0.07 of commission. The ladder is 0.01 below 2; 0.02 below 5; 0.05 below 10; 0.10 below 25; 0.25 below 100; 0.50 below 200; 1 below 400; 2 thereafter. This matches the [SET price-band and tick-size page](https://www.set.or.th/en/market/information/trading-procedure/price-bands-and-tick-sizes). Native slippage follows the engine's exact last-price-band arithmetic, including band boundaries; it is not a reconstructed order book.

`Portfolio` holds original FIFO stock lots. Full closure of an original lot counts as a round-trip; partial exits accumulate its net P&L. Breakeven lots count as round-trips but are excluded from win rate and payoff. Exposure is the unweighted mean of EOD invested value / EOD NAV. Drawdown advances only at EOD and omits an initial-capital anchor; research drawdown also reports that anchor. `PortSummarize` is an auxiliary transaction summary; the research FIFO reconciliation uses Portfolio and confirmed fills as the accounting source of truth.

## Data and benchmark

There are 48 permitted common shares, 16 execution files, 49 daily files including SET50, and nine historical intraday intervals: 1, 3, 5, 10, 15, 30, 60, 120 and 240 minutes. History is feature data, not additional tick execution sessions. Daily histories range from 45 to 738 rows. BANPU, GULF, MRDIYT, THAI and TIDLOR have shorter histories; the supplied guide describes restructurings, mergers, relisting or IPOs. Current membership is not historical membership.

The scorer reads `marketInfo/benchmark/SET50.csv` (16 Date/Close rows). Strategy history uses `daily_history/SET50.csv` (738 OHLCV rows). Overlapping closes match exactly. SET50 is treated as a price-return index, distinct from SET50 TRI, consistent with [SET index methodology](https://media.set.or.th/set/Documents/2025/Feb/Index_Ground_Rule_EN.pdf). The CSV alone does not certify vendor provenance or dividend adjustment policy.

## Requirements versus evidence

| Supplied requirement | Evidence/status |
|---|---|
| THB 10 million, cash only, 100-share lots | Engine capital and cash/holding gates agree; wrapper additionally validates positive quantities and no leverage |
| SET50 universe | Use exactly 48 locally permitted names; do not invent two additional constituents |
| 20 execution sessions | Only 16 supplied; native full-competition validation unavailable |
| Commission/VAT/one tick | Native market behavior agrees; do not add a second cost charge |
| Limit or Market-to-Limit with IOC | Engine exposes Limit and Market; no IOC, no partial fills; main native execution is noncompliant with this supplied requirement |
| Common criteria | Four thresholds agree with competitor_guide.md; local formulas inspected in Portfolio.py |
| Best Alpha nonnegative return and excess | Applied as supplied; complete organizer rulebook unavailable |
| Organizer validation | Guide references CI, roster and organizer scripts; those scripts, roster and the referenced root README are absent |
| Official results | Guide explicitly states that only organizer VPS results decide competition outcomes |

No composite scoring weights are invented. Local metric threshold checks are separate from official eligibility, which remains unverified.
