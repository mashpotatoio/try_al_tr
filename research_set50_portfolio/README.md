# Phase 3 SET50 portfolio research

Run from repository root with `tradeSimEnv/Scripts/python.exe -X utf8 -B -m research_set50_portfolio.runner`, then `python -m research_set50_portfolio.reporting <result path>`. The 20-session schedule is copied exactly from the completed Phase 2 experiment. The daily model is a research approximation and is not an official IOC simulation.

Final recorded commands (PowerShell; use the project environment in place of `python`):

```powershell
& .\tradeSimEnv\Scripts\python.exe -X utf8 -B -m unittest discover -s research_set50_portfolio/tests -v
& .\tradeSimEnv\Scripts\python.exe -X utf8 -B -m research_set50_portfolio.runner
& .\tradeSimEnv\Scripts\python.exe -X utf8 -B -m research_set50_portfolio.reporting research_set50_portfolio/results/20261027T162905Z_979c875c
& .\tradeSimEnv\Scripts\python.exe -X utf8 -B research_set50_portfolio/build_notebook.py research_set50_portfolio/results/20261027T162905Z_979c875c
& .\tradeSimEnv\Scripts\python.exe -X utf8 -B -m research_set50_portfolio.verify research_set50_portfolio/results/20261027T162905Z_979c875c
```

The final run passed 7 automated tests, executed 6 notebook code cells, and passed the independent output verifier. The verifier found no changes among 5,259 protected Phase 1 files. Earlier result directories are retained as superseded development attempts.

The five principal ablations are A trend/equal, B trend/inverse volatility, C trend with reversal tie-breaker/equal, D trend with reversal tie-breaker/inverse volatility, and E a development-selected A–D base with hysteresis, a 3 percentage-point weight threshold, 75% target exposure and 18% stock cap. A separate `risk_only` strategy applies only the latter two risk controls to the selected base. Development selection maximizes Best Alpha pass rate then median excess return; ties resolve alphabetically. The alternative SMA trend, buy-and-hold, alternative exits, cost scenarios, and one-at-a-time sensitivity runs are recorded separately.

Each run writes a unique timestamped result directory with frozen config, data hashes, source identity, daily marks, target weights, order events, holdings, FIFO completions, metrics, robustness, and plots. Existing Phase 1 and 2 files are read only.
