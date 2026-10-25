# From completed prices to reconciled results

## 1. Read data without giving the strategy tomorrow's close

`data.read_history()` loads the supplied tables and assigns validation flags. Loading a file containing future rows is safe only because `core.features()` restricts every calculation to a calendar slice strictly before the decision date. For a 20-session return, it requires **21 closes**, not 20. All stocks and SET50 use exactly the same dates. A missing close, invalid stock OHLC, or insufficient history excludes that symbol; no backfill is used. Prior-session zero volume also excludes a stock. This is evidence of recent observability, not proof that it can trade today.

At 09:30 on decision day d, the newest admissible close is the preceding trading session. Signals and their first/last input dates are exported. For comparability, buy-and-hold also uses this conservative 21-close eligibility set at inception, but does not rank or refresh it afterwards. New listings cannot enter a portfolio before sufficient observed history exists. The research universe still has survivorship bias because historical constituent lists are absent.

The simulator's history reader has the same prior-day boundary and is tested directly. Its current callbacks instead contain forming bars. We never treat a callback's `Close` as a completed daily close. Native callback prices are used only for feasible execution on the currently observed symbol.

## 2. Features and targets

Momentum is `close[t-1] / close[t-21] - 1`. A score of 0.10 means a 10% trailing return. Rank descending and break ties alphabetically. B selects the top 10, then uses equal weights.

Relative strength is stock momentum minus SET50's return over the identical dates. Subtracting the same number from every score preserves their ordering. C-EW intentionally uses the same equal weights as B; its identical results are a control check, not independent confirmation of alpha.

Daily simple returns are `close[i] / close[i-1] - 1`. C estimates their sample standard deviation (`ddof=1`) over 20 returns. It is daily volatility, not annualized volatility. Inverse-volatility scores are `1 / max(volatility, 0.005)`. The floor prevents a near-constant price series from taking almost the entire portfolio.

`capped_weights()` distributes 98% exposure proportionally, caps any stock at 15%, then redistributes the remaining budget among uncapped names. If the selected set has fewer than seven names, 98% exposure may be infeasible; the function leaves the infeasible allocation in cash. It never rescales above a cap or borrows. A's equal-weight baseline has no additional concentration cap beyond its equal allocation. Target exposure and caps constrain purchases, not subsequent passive price drift; a rally may temporarily push a holding above its cap until the next scheduled rebalance.

The fifth strategy adds RSI(14) oversold. For each prior-close price change, `rsi_wilder()` separates positive gains and losses, seeds each average with the mean of the first 14 changes, then smooths subsequent values using Wilder's recurrence: `new_average = (13 * old_average + current_change) / 14`. RSI is `100 - 100 / (1 + average_gain / average_loss)`. A flat sequence has undefined RSI and is excluded; no losses gives 100, and no gains gives 0. At a rebalance, only names with RSI strictly below 30 qualify, sorted by ascending RSI and then ticker for deterministic ties. Equal weights pass through the same 15% cap; if only two stocks qualify, at most 30% of NAV is invested and the rest stays cash. The strategy does not buy simply because a price is low; it buys only when the historical signal and trading checks both pass.

## 3. Weights become shares, then feasible orders

`ResearchState.start_day()` forms fixed targets on sessions 1, 6, 11 and 16. Target shares are `floor(equity * weight / prior_close / 100) * 100`. Holdings outside the selected set get target zero. A targets only its first session and then holds.

`wanted()` subtracts actual filled holdings from target shares. Sales cannot exceed held shares. For buys, `feasible_buy()` also limits the quantity by available cash after pending reservations and by the current price-based position cap. Fees are included before rounding down. It never assumes a sale occurred just because it was requested.

Native sales start on the stock's own continuous-trading callback at or after 10:00; purchases start at 10:05. Rejections can retry every five minutes before 10:30. There is at most one accepted order per stock per rebalance. Unfilled targets are reported rather than completed through a stream of tiny trades. Confirmed sale proceeds become usable immediately; there is no anticipation of proceeds from unfilled sales. A suspended or absent symbol gets no invented execution.

Native main runs use actual engine Market orders. The engine immediately applies one adverse tick, commission, and VAT. These orders do **not** prove IOC compliance. Cumulative opposite-side volumes gate native orders but do not model available depth or participation. The daily adapter instead assumes all feasible orders fill at the next session's open plus/minus one tick, with sales processed before purchases. Daily time labels of 10:00 are model labels, not reconstructed auction timestamps. Same-day volume/high/low/close never determine that order's size or fill eligibility.

## 4. Reconcile orders, fills and FIFO lots

`Ledger.reserve()` records pending buy cash or sell shares. `cancel()` releases only the remaining commitment. `Ledger.fill()` is the sole route that changes cash and holdings. Unique fill IDs prevent double booking; partial fills can extend the same original buy-order lot. The supplied native simulator never produces partial fills, so this path is tested synthetically rather than claimed as observed engine behavior.

Native order submission returns a string or exception object. The adapter checks confirmed engine transaction-log entries and reconciles the actual portfolio; the word “successfully” never establishes ownership. After every fill, engine cash, quantities and equity must match the independent ledger. Every native day's saved state is reloaded on the next day, testing the actual persistence path.

FIFO sells consume the oldest original buy lot first. Each consumed share receives the net sale proceeds and carries its fee-inclusive acquisition cost. Partial exits accumulate realized P&L but count no completed round-trip until the original lot reaches zero. A sell spanning two original lots may close one and leave another partial. Transaction counts therefore differ from round-trip counts.

## 5. Costs and a worked example

Suppose three eligible stocks have the following trailing data. This is an illustration with THB 100,000 and a **40% cap**, not the study's 15% cap:

| Stock | Old close | Recent close | Momentum | SET50 return | Relative strength | Daily volatility |
|---|---:|---:|---:|---:|---:|---:|
| A | 8 | 10 | 25% | 5% | 20% | 1% |
| B | 18 | 20 | 11.111% | 5% | 6.111% | 2% |
| C | 38 | 40 | 5.263% | 5% | 0.263% | 4% |

Inverse-volatility scores are 100, 50, 25. At 98% exposure, uncapped weights would be 56%, 28%, 14%. Capping A at 40% redistributes the remaining 58% in a 2:1 ratio: **40%, 38.6667%, 19.3333%**.

Prior-close target shares are 4,000 A, 1,900 B, and 400 C after 100-share rounding. Suppose current prices equal those closes. One adverse tick produces buy fills of 10.10, 20.10, and 40.25. A's 40,000 baht position budget permits only **3,900** shares at 10.10. B and C remain 1,900 and 400 shares. Total notional is 93,680; commission is 147.0776; VAT is 10.295432; ending cash is **6,162.626968**. A has a residual 100-share target, which is reported. No second slippage charge is added after using the fill price.

The actual sequential cap calculation uses current marked equity, so caps for later orders can shrink slightly after fees. In this illustration that does not change the rounded B/C quantities. A separate affordability example: THB 10,000 cannot buy 100 shares at THB 100 because commission and VAT make the cash debit exceed THB 10,000.

## 6. Evaluation without hiding undefined quantities

Research return is final marked equity / initial cash - 1. Drawdown is the maximum decline from a preceding peak, including initial capital and EOD observations. The engine's raw EOD-only drawdown is retained separately. Competition Calmar is cumulative return / absolute maximum drawdown, without annualization. Zero drawdown means undefined Calmar, not zero.

Exposure is the mean of each EOD holdings market value / equity. Turnover is total absolute fill notional divided by mean daily equity; it is not halved. Payoff and win rate exclude breakeven completed lots according to the local engine. No completed non-breakeven lots means undefined payoff/win rate. Gross returns are not reconstructed by adding costs to final equity.

The research SET50 return uses the preceding session's close as anchor. Engine benchmark output instead starts at the first measured day's close. Exact expected observations are required; missing data leaves benchmark-dependent metrics unverified. SET50 is a price index, not a dividend-reinvested total-return index. Terminal positions remain open and are marked to the latest observed close; stale marks are labeled in the equity and holdings tables.

Each criterion gets its threshold, value, and pass/fail/unverified result. The drawdown test is strictly `<`; equality fails. The local status is provisional even when formulas match source code, since the full organizer rulebook and validator are absent. The missing 20-session execution period and IOC mismatch independently prevent an official eligibility claim.

## 7. Learning and reproduction map

Read `core.py` first for pure calculations, then `runner.py` for portfolio decisions and adapter boundaries. `data.py` makes input identities and validation explicit; `evaluation.py` generates metrics and charts; `verify.py` independently rebuilds saved portfolios. Tests include hand-computed cash/FIFO examples and a real-engine contract test. The original notebook is not edited or executed because its fresh-start cell deletes existing team results.

The daily windows are selected by calendar before returns are evaluated, with 11 development and 24 evaluation windows plus a separately reported tail. Parameters are fixed. Evaluation history is a historical holdout for this specification, not a live prospective trial. Current adjusted data may encode later corporate-action revisions, so strict point-in-time reconstruction remains externally blocked even though all software date-cutoff checks pass.
