# Research roadmap

## Phase 1 — Baseline implementation (complete)

Implemented reproducible backtest, data validation, fill-driven accounting, FIFO round-trips, benchmark alignment, provisional competition checks, and comparable strategies: equal-weight buy-and-hold, cross-sectional momentum, relative strength with inverse-volatility sizing, an equal-weight sizing control, and RSI(14) cross-sectional oversold. The RSI comparison is included to make the initial rules easy to inspect. Results are historical research, not proof of an edge or official eligibility.

## Phase 2 — Factor and signal research (next)

Measure IC, rank IC, forward quantile returns, horizon sensitivity, turnover and statistical stability with date-safe features. Predeclare development and evaluation periods, preserve chronological holdouts, account for transaction costs, and report uncertainty. Advance a signal only when its evidence survives multiple periods and a controlled baseline comparison.

## Phase 3 — Portfolio construction

Compare equal weight, inverse volatility and risk-constrained allocation with the same signal, dates, execution assumptions and trading costs. Include concentration, exposure, cash drag, turnover and competition criteria. Separate allocation effects from signal effects.

## Phase 4 — Machine learning and walk-forward

Only after Phase 2 shows predictive feature evidence, evaluate a small set such as Ridge, Random Forest or Gradient Boosting. Train chronologically, tune only within training folds, freeze a final out-of-sample period, and compare with the Phase 1 baselines. Record feature availability and leakage checks.

## Phase 5 — Competition strategy and validation

Validate exact organizer order types, timing, IOC handling, fills, fees, valuation, benchmark and eligibility rules using the official simulator and full 20 trading sessions. Test drawdown and robustness across periods before preparing the final `.py` submission. Official acceptance remains unverified until the organizer validator is available.

## Evidence gate

Do not move from a phase because a single return is attractive. Keep all predefined windows, record each attempted configuration, and distinguish profitability, benchmark outperformance, eligibility and robustness in every report.
