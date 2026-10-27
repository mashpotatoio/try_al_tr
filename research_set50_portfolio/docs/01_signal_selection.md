# Signal selection, frozen before portfolio evaluation

The completed Phase 2 run (`20261026T161657Z_64b58b98`) covers 48 permitted stocks and 738 SET50 sessions, 2023-09-21 to 2026-10-06. The 24 evaluation windows were previously inspected in Phase 1. The Phase 2 factor summary, quintile summary, robustness discussion, and methodology were read before coding.

| Signal | Statistical evidence | Economic evidence | Stability and feasibility | Decision |
|---|---|---|---|---|
| Momentum20 | Five-session evaluation Rank IC 0.0039, interval includes zero, FDR q 0.914 | Top quintile five-session SET50 relative return 0.244%, below 0.336% commission-only round trip | Nonmonotonic longer-horizon results; turnover unproven | Exploratory primary trend hypothesis |
| SMA20/SMA60 | Five-session Rank IC 0.0221, interval includes zero, FDR q 0.786 | Top quintile relative return 0.235%, below commission-only round trip | Requires 60 completed bars; test as separate alternative | Exploratory alternative trend |
| One-day reversal | One-session Rank IC 0.0477, HAC interval 0.0346–0.0607, FDR q about 1e-10 | Top quintile relative return 0.124%, below commission-only round trip | Weakens sharply at longer horizons; daily turnover high | Tie-breaker only, never standalone trade |

The tie threshold is 5% of that decision date's cross-sectional primary-score range. Every member of a tie group must be within that distance of the group's strongest score. This dimensionless normalization prevents raw-unit mismatch and prevents a chain of small adjacent gaps from overriding a materially stronger trend. It can still increase trading; the A/C and B/D comparisons directly test its incremental value. The two trend scores are inconclusive hypotheses, not validated alpha.
