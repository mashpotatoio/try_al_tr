# SET50 factor and signal research

This package studies whether completed daily stock observations rank subsequent SET50 stock returns. It is Phase 2 of `research_set50_baseline`, not a replacement for that package. Factor diagnostics, adjusted-open turnover estimates, and the 16-session raw-tick cost reference are distinct outputs. None establish official competition eligibility.

This publication copy includes selected compact tables and plots in [`published_results/`](published_results/README.md). The original TradeSim data and full date-level result directory are required to rerun and independently verify every result; see the repository [README](../README.md) for workspace setup.

## Reproduce

From `C:\Users\Windows 10\Downloads\tradeSim0.2.5` in PowerShell:

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

The `run` command always creates a new timestamp/UUID directory. Select a directory whose `status.json` says `complete`; a failed attempt is retained. Each run holds its exact configuration, source/data hashes, schedule, library versions, date-level ICs and quantiles, non-overlapping segment and factor-distribution diagnostics, summaries, cost references, plots, warnings, and verification output. Results are excluded from Git to prevent accidental overwrites. The notebook uses an explicit run directory and its saved outputs can be read without rerunning the experiments. Prepending the project's virtual environment to `PATH` makes the installed `python3` Jupyter kernelspec launch that environment instead of the system Python.

The environment has NumPy, Pandas, `unittest`, `nbformat`, and `nbclient`. It lacks SciPy and Statsmodels; the implementation uses average-rank Pearson for Spearman and a documented Newey-West uncertainty estimate. Matplotlib is loaded from the Phase 1 local `vendor/` copy; no global installation is modified.

## Layout

- `configs/preregistered.json`: frozen hypotheses, horizons, splits, regimes, and evidence rule.
- `data.py`, `factors.py`, `labels.py`: source audit, completed-bar factors, and strictly future open-to-open targets.
- `evaluation.py`: IC, rank IC, quantiles, HAC uncertainty, false-discovery adjustments, regimes, redundancy.
- `proxy.py`: turnover and commission floor on adjusted opens; separate raw-tick cost reference.
- `visualization.py`, `runner.py`: research figures, execution and artifact verification.
- `tests/`, `notebooks/`, `results/`: tests, executed exposition, and immutable run folders.

For a signal after session `t` closes, the first hypothetical entry is `t+1` open. An `h`-session label exits at `t+1+h` open. Missing intermediate sessions invalidate the label. The 20-session forecast needs an exit 21 sessions after its signal; it cannot necessarily be opened and closed inside a 20-session competition window. The historical daily OHLCV files are vendor-revised for capital actions, without adjustment vintages. Their opens support internally consistent research labels, but are not confirmed executable prices. Tick costs are calculated only on actual observed raw-tick prices in the 16 supplied September 2026 sessions. See the methodology and data-quality reports before interpreting a chart.

The evaluation interval is chronological but **not completely unseen**: Phase 1 results on those dates have already been examined. Phase 2 factor definitions were frozen before its own evaluation run; this is weaker evidence than a prospective untouched holdout.
