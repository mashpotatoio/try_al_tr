# SET50 algorithmic trading research

This repository publishes two stages of SET50 research for a 20-session, long-only TradeSim competition. Phase 1 compares five baseline strategies. Phase 2 tests whether stock-level factors predict subsequent cross-sectional returns before building another portfolio strategy.

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
