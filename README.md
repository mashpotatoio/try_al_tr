# SET50 algorithmic trading research

This repository publishes Phase 1–3 and Phase 3.5 research for a 20-session, long-only TradeSim competition. Phase 3.5 audits execution assumptions, trading costs, signal quality, and competition eligibility.

## Phase 3.5: execution validation and diagnosis

Start with the [executed 24-cell analytical notebook](research_set50_execution_validation/notebooks/035_execution_diagnostics.ipynb), [standalone HTML report](research_set50_execution_validation/publication/phase35_execution_diagnostics.html), [research decision](research_set50_execution_validation/docs/05_research_recommendations.md), and [published result snapshot](research_set50_execution_validation/published_results/20261027T174032Z). The notebook has 12 executed code cells and seven embedded plots. The frozen Phase 3 run reproduced exactly across 356 rows. A's mean excess changed from +1.22% with zero explicit costs to −0.90% with one modeled adverse tick; booked costs averaged 2.116% of capital. Daily and raw-tick OHLC matched across 768 overlapping stock-days, but historical corporate-action adjustments and official IOC fills remain unvalidated. A 16-session native practice replay found a THB 38,794 ending NAV difference from the matched daily model; it is not a complete 20-session result.

Run `python research_set50_execution_validation/verify_publication.py` from this publication root to execute every notebook code cell against the bundled snapshot. Full Phase 3.5 experiments require the preserved TradeSim workspace and raw market data.

## Phase 3: portfolio construction and risk

Start with the [executed portfolio notebook](research_set50_portfolio/notebooks/03_portfolio_research.ipynb), [findings](research_set50_portfolio/docs/04_backtest_findings.md), and [published result snapshot](research_set50_portfolio/published_results/README.md). The publication includes source code, frozen configuration, tests, all final-run window and trade records, eligibility and cost audits, and 11 figures. The 24 historical evaluation windows were previously exposed to research inspection.

The primary trend/equal-weight strategy averaged **−0.90% net excess return** and met all Best Alpha conditions in **2/24** windows. Adding the reversal tie-breaker under matched allocation and execution produced **−1.03%** mean net excess and **2/24** eligibility. The low-turnover overlay reduced trading but qualified in **0/24** windows. **No defensible net edge was established.** One-tick costs on vendor-adjusted daily prices are a research scenario, not verified IOC fills. The available 16 tick-data sessions do not establish a full 20-session native result.

## Phase 2: factors and signals

Start with the [executed research notebook](research_set50_factors/notebooks/02_factor_signal_research.ipynb), [findings](research_set50_factors/RESEARCH_FINDINGS.md), and [methodology](research_set50_factors/FACTOR_METHODOLOGY.md). The [published results](research_set50_factors/published_results/README.md) contain the complete run's compact summary tables, verification records, and selected figures. The preregistered [configuration](research_set50_factors/configs/preregistered.json), Python modules, and tests are included.

The completed experiment tested 25 factor definitions at 1, 3, 5, 10, and 20 trading-session horizons on 48 currently permitted stocks. One-day reversal had a positive evaluation one-session Rank IC of 0.0477, but its top-quintile mean SET50-relative return of 0.124% was below the 0.33598% commission-and-VAT round trip before slippage. Short-horizon momentum continuation and RSI(14) oversold were unsupported. Relative strength formed by subtracting the same benchmark return from each stock has exactly the same cross-sectional ranking as momentum. **No factor was proven net profitable or competition eligible.**

The evaluation interval is chronological but not completely unseen: Phase 1 results for those dates were examined before Phase 2. Historical adjusted opens support research labels, not confirmed executable fills; exchange tick calculations use only the separate observed raw-tick reference. A 20-session predictive label generally requires an exit beyond a 20-session competition window.

## Phase 1: baseline strategies

The [Phase 1 notebook](research_set50_baseline/notebooks/01_set50_baseline_comparison.ipynb) compares buy-and-hold, cross-sectional momentum, two relative-strength sizing methods, and RSI(14) oversold. Read its [architecture](research_set50_baseline/docs/ARCHITECTURE.md), [roadmap](research_set50_baseline/docs/ROADMAP.md), and [findings](research_set50_baseline/RESEARCH_FINDINGS.md). Its native simulator run covers 16 available sessions and did not establish a reliable positive edge.

## Reproduce

The raw TradeSim market data and virtual environment are separate from this publication repository. The runner also uses the original Phase 1 schedule at `research_set50_baseline/experiments/20261025T163641Z_run-daily_7f6c0946/schedule.json` and the original `phase1_prephase2_sha256.json` integrity manifest. Place this repository's Phase 2 directory in that preserved TradeSim 0.2.5 workspace; this publication checkout alone is not a standalone dataset. From the original workspace in PowerShell:

```powershell
$py = '.\tradeSimEnv\Scripts\python.exe'
& $py -X utf8 -B -m unittest discover -s .\research_set50_factors\tests -v
& $py -X utf8 -B -m unittest discover -s .\research_set50_baseline\tests -v
& $py -X utf8 -B -m research_set50_factors run
$run = (Get-ChildItem .\research_set50_factors\results -Directory | Sort-Object Name | Select-Object -Last 1).FullName
& $py -X utf8 -B -m research_set50_factors verify $run
$env:PATH = (Resolve-Path '.\tradeSimEnv\Scripts').Path + ';' + $env:PATH
& $py -X utf8 -B -m research_set50_factors.build_notebook $run
```

Each new run creates its own result directory. Select one with `status.json` marked `complete`. The published summaries document the completed run `20261026T161657Z_64b58b98`; they do not replace the raw data or full date-level run needed for independent recomputation. See the [data-quality report](research_set50_factors/DATA_QUALITY_REPORT.md) and [statistical limitations](research_set50_factors/STATISTICAL_LIMITATIONS.md) before interpreting the estimates.
