# SET50 baseline research findings

## RSI comparison extension — October 25, 2026

RSI(14) oversold was added as a fifth transparent rule: use 14-period Wilder RSI from completed closes at the prior-session cutoff, select only names below 30, rank lowest RSI first, rebalance on the same five-session schedule, and use equal target weights subject to the shared 15% name cap. When fewer than ten symbols qualify, the unallocated capital remains cash. This threshold is a starting specification, not a tuned value.

The new smoke run completed on two sessions. The new native TradeSim run completed all **16 available sessions**, September 9–30, 2026. RSI returned **−2.9185%**, versus the SET50 price benchmark at **−4.1544%**, for **+1.2358 percentage points** excess return. Maximum drawdown was 2.9185%; average exposure was 34.1971%; it completed six FIFO round-trips with mean payoff **−THB 21,897**. Eight orders were rejected, 14 filled, and none were partial fills. Ending cash was THB 6,843,026.50. Fees were THB 28,045 commission plus THB 1,963 VAT; adverse-tick slippage of THB 110,085 is embedded in fills. The relative outperformance over this short sample is not evidence of a proven edge.

Against the supplied local provisional thresholds, native RSI passes the drawdown and round-trip checks and fails exposure (34.20% versus 50%) and expected payoff (negative versus greater than zero). Best Alpha total return fails and excess return passes. Therefore it fails the Common Criteria overall and is not eligible for Best Alpha. Official eligibility remains unverified because the available period is shorter than 20 sessions and the native engine does not implement the required IOC order behavior.

In the 24 non-overlapping, chronological daily evaluation windows, RSI mean return was **−1.3508%**, median return **−0.6958%**, and worst return **−8.8569%**. Mean excess return was **−2.1969 percentage points**; it was profitable in 8/24 windows and beat the benchmark in 5/24. The daily adapter assumes next-open liquidity and is not official TradeSim validation. These results do not support an RSI edge under the tested fixed rule.

The executed comparison notebook is [01_set50_baseline_comparison.ipynb](notebooks/01_set50_baseline_comparison.ipynb). Compact results are in `results/`; raw logs, per-order runs, market inputs and plotting vendor packages are intentionally excluded from the shareable result set.

The original four-strategy fixed specification did not demonstrate a reliable edge. All four lost money and underperformed SET50 in the available native execution period. Across the 24 historical evaluation windows, all four had negative mean returns and negative mean excess returns. Inverse-volatility sizing did not improve the observed return comparison. The subsequent RSI comparison is reported separately above. These are research findings under the assumptions below, not evidence that a strategy can never work.

No performance-driven parameter tuning was performed. The equal-weight relative-strength control reproduced momentum exactly; subtracting a common benchmark return did not create an independent signal.

## Reviewed experiments and evidence

| Experiment | ID | Outcome |
|---|---|---|
| Full input validation | `20261025T155740Z_validate_dd6ea2aa` | Completed; 507 market CSVs inspected |
| First smoke attempt | `20261025T155740Z_smoke_d95db3a9` | All four simulations completed; report failed because matplotlib was unavailable |
| Completed smoke | `20261025T155958Z_smoke_9eff3584` | Four strategies, two execution sessions, charts and reports completed |
| Native comparison | `20261025T160035Z_run-native_dde2ee84` | Four strategies, all 16 available execution sessions |
| Daily research | `20261025T155958Z_run-daily_dbb0f380` | 148 strategy/window runs, all scheduled periods reported |
| Independent artifact audit | `checks/20261025T160618Z_3dec183a` | 156 completed runs reconciled; repeated smoke financial paths identical |
| RSI smoke | `20261025T163437Z_smoke_d8a1a004` | Five strategies, two execution sessions, completed |
| Five-strategy native comparison | `20261025T163506Z_run-native_14fbba1f` | Five strategies, all 16 available execution sessions |
| Five-strategy daily research | `20261025T163641Z_run-daily_7f6c0946` | 120 evaluation strategy/windows plus all predefined development and tail periods |

The environment denied network installation of plotting packages. Existing compatible Python 3.13 plotting packages were copied into task-owned `vendor/`; neither the base installation nor the original virtual environment was changed. The first failed attempt remains inspectable.

Sixteen tests passed, including RSI smoothing and cross-sectional selection, actual-engine rejection/cancellation/full-fill behavior, synthetic partial fills, FIFO closure, fee-inclusive affordability, exact tick boundaries, fresh state, undefined metrics, signal timing, and future-data invariance. A daily test changes the execution day's close/high/low/volume and confirms that its opening orders remain identical. The artifact audit independently rebuilt the original saved portfolios from fills, checked cash/holdings/equity/fees/lots, verified chronological fills and prior-session feature cutoffs, and compared B with C-EW. The RSI runs use isolated experiment directories; all 539 recorded original files remained unchanged.

## Original four-strategy native results: September 9–30, 2026, 16 sessions

Each strategy starts with THB 10,000,000. Terminal holdings are marked to market; there is no forced liquidation. Returns include actual native fees and adverse-tick execution. SET50 research return is **−4.1544%**, measured from September 8 close through September 30 close. There is no full 20-session native backtest.

| Strategy | Final equity THB | Net return | Excess return, percentage points | Research max drawdown | Competition Calmar |
|---|---:|---:|---:|---:|---:|
| A: Buy-and-hold | 9,533,531.70 | −4.6647% | −0.5103 | 4.6647% | −1.0000 |
| B: Momentum | 9,344,558.01 | −6.5544% | −2.4001 | 7.0525% | −0.9294 |
| C: Relative strength / inverse volatility | 9,318,897.17 | −6.8110% | −2.6567 | 7.1216% | −0.9564 |
| C-EW: Equal-weight control | 9,344,558.01 | −6.5544% | −2.4001 | 7.0525% | −0.9294 |

Research drawdown includes initial capital and EOD valuations. The benchmark research drawdown is 4.1544%. Calmar uses cumulative return, without annualization; a less negative ratio must not be mistaken for profitability or an eligibility pass.

| Strategy | Mean exposure | Completed FIFO lots | Expected payoff THB | Win rate | Turnover | Ending cash THB |
|---|---:|---:|---:|---:|---:|---:|
| A | 97.1536% | 0 | Undefined | Undefined | 0.9865 | 279,966.70 |
| B | 95.4491% | 16 | −24,999.71 | 18.75% | 3.5147 | 903,725.01 |
| C | 97.5525% | 15 | −28,801.15 | 20.00% | 3.9240 | 940,936.17 |
| C-EW | 95.4491% | 16 | −24,999.71 | 18.75% | 3.5147 | 903,725.01 |

Turnover is total absolute fill notional / mean daily equity. Payoff and win rate exclude breakeven completed original FIFO lots, matching the supplied engine's definition. A has no completed trades; its undefined payoff is not replaced with the engine's displayed zero.

| Strategy | Submitted | Filled | Rejected | Partial fills | Canceled | Commission THB | VAT THB | Embedded slippage THB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 49 | 48 | 1 | 0 | 0 | 15,234.86 | 1,066.44 | 54,033.00 |
| B | 62 | 53 | 9 | 0 | 0 | 54,316.82 | 3,802.18 | 211,222.00 |
| C | 61 | 52 | 9 | 0 | 0 | 60,562.46 | 4,239.37 | 235,363.00 |
| C-EW | 62 | 53 | 9 | 0 | 0 | 54,316.82 | 3,802.18 | 211,222.00 |

All native rejections in these runs came from cumulative opposite-side volume gates. Native partial fills are unsupported; zero observed partial fills does not demonstrate realistic fill completeness. Slippage is already embedded in fill prices. Its reported amount is the absolute fill-versus-current-tick price difference times shares, not a second cash deduction. Gross returns were not reconstructed.

### Allocation shortfalls and cash sequencing

A completed its initial rounded share targets after one OR rejection/retry; zero residual target shares does not mean 100% investment. Costs, price changes, lot rounding and the 98% target leave cash.

B ended THB 685,462 below its frozen share targets, with a maximum daily residual of THB 777,200. C ended THB 708,402 below target. Both had zero residual sell notional on the final day. These are share-target gaps valued at current marks, not promises that the cash could have been invested at prior prices.

Confirmed-sale timing materially constrained purchases. For B, the September 16 SCC purchase was reduced from 3,700 desired shares to 800, when cash supported only 800; the September 30 AWC purchase was reduced from 286,500 to 68,200 shares. C had cash-limited RATCH, THAI and AWC purchases, plus price/cap reductions in PTT and TTB. Cash arriving after an accepted purchase is not used to top up that same symbol under the one-accepted-order-per-rebalance rule. This explains why substantial cash and residual targets can coexist at the close. The starting execution rule was retained rather than optimized after seeing these outcomes.

### Local metric conventions and eligibility

The engine's benchmark starts at the first measured session's close, giving **−4.0995%** rather than −4.1544%. Its EOD-only drawdown for A is **4.3101%**, versus the research 4.6647% that includes initial capital. B/C drawdowns are effectively unchanged. Raw engine metrics are retained in every native run; `engine_convention_eligibility.csv` in the audit directory provides the corresponding threshold checks. The criterion conclusions below do not change under those engine conventions.

| Criterion | Threshold | A | B and C-EW | C |
|---|---|---|---|---|
| Portfolio drawdown | Strictly < 6.2315% using research benchmark | Pass: 4.6647% | Fail: 7.0525% | Fail: 7.1216% |
| Completed FIFO lots | ≥ 5 | Fail: 0 | Pass: 16 | Pass: 15 |
| Average exposure | ≥ 50% | Pass: 97.1536% | Pass: 95.4491% | Pass: 97.5525% |
| Expected payoff | > THB 0 | Unverified/undefined | Fail: −24,999.71 | Fail: −28,801.15 |
| Best Alpha portfolio return | ≥ 0% | Fail | Fail | Fail |
| Best Alpha excess return | ≥ 0 percentage points | Fail | Fail | Fail |

**No strategy passes all local Common Criteria. Official eligibility remains unverified for every strategy.** The local calculations are provisional research, supported by inspected engine definitions where available. Native Market orders are not the supplied IOC order rule, the full execution period is unavailable, and organizer validation scripts/full rulebook are absent. Eligibility is not inferred from performance ranking.

## Original four-strategy historical daily research

The schedule was fixed from the SET50 calendar after 21 warm-up observations: 35 non-overlapping 20-session windows from October 24, 2023 through September 11, 2026. The first 11 are development windows. The remaining **24 evaluation windows begin September 18, 2024**. A separate 17-session tail covers September 14–October 6, 2026. A further 16-session daily/native overlap comparison is explicitly dependent on this schedule and is excluded from the main evaluation summary.

Daily execution assumes feasible orders fill at adjusted next-session opening prices, with sales before buys, one adverse tick and the same commission/VAT. It does not model tick volume gates, queue priority or partial fills. Each window resets capital; averages below are per-window arithmetic summaries, not annualized or compounded strategy performance.

| Strategy | Mean evaluation return | Median return | Worst return | Mean excess, percentage points | Nonnegative-return windows | Outperformance windows | Local Common Criteria passes |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | −0.1878% | −0.6799% | −6.3064% | −1.0339 | 11/24 | 7/24 | 0/24 |
| B | −0.8632% | −1.3458% | −9.2135% | −1.7093 | 10/24 | 8/24 | 1/24 |
| C | −1.2985% | −1.5206% | −9.0986% | −2.1445 | 10/24 | 6/24 | 1/24 |
| C-EW | −0.8632% | −1.3458% | −9.2135% | −1.7093 | 10/24 | 8/24 | 1/24 |

All development windows and the tail are included in `comparison.csv` and `window_summary.csv`. There was no selection of a favorable month. The evaluation periods are a historical holdout for this fixed specification, not a prospective live trial.

Over the same 16 dates as native execution, daily returns were A −4.2858%, B/C-EW −6.4800%, and C −6.9769%. Differences from native results reflect opening prices, intraday purchase/sale timing, volume-gate rejections, and cash sequencing. Daily results are not evidence of official competition eligibility.

## Data and remaining external limitations

- The universe contains 48 permitted stocks, not a reconstructed historical SET50 membership series. Survivorship bias remains.
- Daily prices are adjusted for capital actions according to the supplied guide. No adjustment ledger, as-published vintages, dividend records or share-conversion events are provided. Date filters pass, but complete point-in-time integrity cannot be established. Historical lot/tick economics on adjusted prices are approximate.
- The 2,906,167 tick rows contain 1,046,005 identical-row repetitions. They are retained because there are no trade IDs proving accidental duplication. Liquidity inference remains limited.
- All observed tick/daily closing-price overlaps match, as do historical/scoring SET50 closes. This does not certify the external provenance of either series.
- One SET50 row has Open above High; its valid close is retained for close-only calculations. Large CCET and MRDIYT returns were inspected and retained. No winsorization or removal of market stress was performed.
- Native chronological replay intentionally differs from the notebook's row-number interleaving. Organizer event-order behavior cannot be verified without its runner.
- Missing sessions beyond September 30 cannot be manufactured. A complete 20-day native competition run, realistic IOC/partial-fill validation, historical point-in-time reconstruction and official eligibility remain externally blocked.

## Read the artifacts

- [Native comparison table](experiments/20261025T160035Z_run-native_dde2ee84/reports/comparison.md)
- [Native equity, drawdown and exposure chart](experiments/20261025T160035Z_run-native_dde2ee84/reports/native_16sessions.png)
- [All daily-window results](experiments/20261025T155958Z_run-daily_dbb0f380/reports/comparison.csv)
- [Daily summary](experiments/20261025T155958Z_run-daily_dbb0f380/reports/window_summary.csv)
- [Independent verification](checks/20261025T160618Z_3dec183a/verification.json)
- [Data quality](DATA_QUALITY_REPORT.md)
- [Reproduction commands](README.md)
- [Rollback instructions](ROLLBACK.md)
