# Strategy failure diagnosis

Phase 3 official A–E summary (24 previously examined windows each):

| strategy | mean_excess | mean_turnover | mean_roundtrips | best_alpha |
|---|---|---|---|---|
| A | -0.00899 | 2.79395 | 9.0 | 2 |
| B | -0.01223 | 2.9861 | 9.29167 | 3 |
| C | -0.0103 | 2.84067 | 9.08333 | 2 |
| D | -0.01434 | 3.08728 | 8.95833 | 3 |
| E | -0.00275 | 1.92575 | 4.625 | 0 |

Actual target selection for A contains 4/576 nonpositive Momentum20 observations. The five-session open-to-close diagnostic mean is 0.613% for selected A stock-date observations and 0.078% for nonselected eligible stock-date observations. These overlapping observations share market regimes and are not a tradable portfolio return or untouched holdout. Momentum strength and dispersion are in `momentum_selection.csv` and `momentum_forward_universe.csv`. Phase 2 factor evidence reported weak Momentum20 rank IC; the positive cross-sectional difference here cannot establish robust actionable alpha after costs.

A filled turnover by action (THB, all windows): {'add_to_holding': 24960127.0, 'full_exit': 213775735.0, 'new_entry': 402994095.0, 'reduce_holding': 28818107.0}. These are actual order fills. `new_entry` and `full_exit` show replacement, while `add_to_holding` and `reduce_holding` include target drift correction. Exact rank-change versus risk-overlay attribution is not identifiable from recorded target and fill fields alone; E's retention and threshold are controlled comparisons. E lowered mean turnover to 1.926× but only 4.625 fully closed FIFO lots on average. The five-trip gate fails in 11/24 windows. A payoff fails in 21/24; E in 21/24. The exposure gate fails in zero A–E windows. A drawdown fails in 10/24. Detailed simultaneous failures are recorded per window in `eligibility_windows.csv`; failure counts overlap and should not be added.

The exploratory positive Momentum20 filter changes A's mean excess from -0.8990% to -0.8961%, with mean exposure 78.85% and 2/24 best-alpha passes. A ten-session rebalance changes mean turnover from 2.794× to 1.584×, mean excess to 0.1065%, and completed lots to 3.00; it has 0/24 best-alpha passes. This lower-turnover result fails the five-trip constraint frequently and is not a viable competition improvement as tested. Do not add artificial trades to satisfy it.

Completed A original-lot holding duration uses calendar days as recorded by Phase 3, not session count. Exploratory bins show:

| duration_bin | lots | mean_pnl | win_rate |
|---|---|---|---|
| 0-7 days | 123 | -38293.1 | 0.23 |
| 8-14 days | 47 | -27292.46 | 0.23 |
| 15-30 days | 46 | -14626.97 | 0.35 |
| 31+ days | 0 | 0.0 | 0.0 |

This completed-lot sample excludes still-open holdings and is subject to exit-selection bias. Post-exit prices and matched trade reasons are not recorded in the frozen run, so no claim about post-exit alpha or payoff by exit reason is made.
