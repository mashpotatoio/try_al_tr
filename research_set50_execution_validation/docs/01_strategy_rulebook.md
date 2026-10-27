# Exact Phase 3 strategy rulebook

Source: `research_set50_portfolio/core.py`, `runner.py`, frozen config. All decisions use completed prior-session data, with intended execution at the next session's adjusted open. These are research fills, not official IOC orders.

| Rule | A | B | C | D | E |
|---|---|---|---|---|---|
| Primary rank | Momentum20 descending | Same | Same | Same | Same, A base selected on development windows |
| Reversal tie | No | No | Yes | Yes | No for selected A base |
| Weights | Equal | Inverse 20-day daily return volatility | Equal | Inverse volatility | Equal |
| Holdings | Six | Six | Six | Six | Six |
| Target exposure / cap | 80% / 20% | 80% / 20% | 80% / 20% | 80% / 20% | 75% / 18% |
| Scheduled rebalance | Every five sessions including first | Same | Same | Same | Same |
| Retention | None | None | None | None | Keep former names in top ten ranks |
| Weight-change threshold | None | None | None | None | Skip change below 3% of NAV after first session |

Momentum20 = Close(t)/Close(t-20)-1. A stock at -2% can be selected if it is among the six highest scores; **positive momentum is not required**. For example, -2% ranks above -5%. SMA20/SMA60 = mean(last 20 closes)/mean(last 60 closes)-1 is the separate `sma_trend` comparator, not A–E. Reversal1 = 1-Close(t)/Close(t-1); C and D use it only within contiguous groups whose primary-score gap from the group's first member is at most 5% of the full cross-sectional Momentum20 span. For equal weighting, six names receive roughly 13.33% each under the 20% cap; E receives 12.5% each under its 18% cap. Inverse-volatility allocation redistributes under the same caps.

Eligibility requires 61 valid trailing bars for a stock, finite positive volatility and positive mean trailing 20-session volume. All 61 bars must pass the daily OHLCV validity check. No missing-bar forward fill enters the signal. Ranking is stable on ties. Target shares use prior close and round down to 100. Sells are attempted before buys; each order is capped at 1% of prior 20-session average volume, cash and share availability. Modeled execution uses adjusted next open plus/minus one local tick, full capped fill, 0.157% commission and 7% VAT on commission. End-session close marks holdings; open lots are not forced closed. FIFO round-trips count only fully closed original buy lots. Thus order count, sell count, and completed round-trip count differ. Exposure is mean end-session invested NAV fraction; expected payoff is mean nonzero net P&L of completed lots. Calmar is cumulative net return divided by maximum drawdown (undefined at zero drawdown).
