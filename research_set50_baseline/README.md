# SET50 baseline research

This folder contains five reproducible research configurations: equal-weight buy-and-hold, cross-sectional momentum, relative strength with inverse-volatility sizing, its equal-weight sizing control, and cross-sectional RSI(14) oversold. RSI selects up to ten stocks with RSI below 30, lowest first, and holds cash when fewer names qualify. There is no Machine Learning or parameter search.

The original project is read-only input. Native experiments use the actual TradeSim execution and portfolio classes, with a chronological research runner. They are **not official competition validation**: the local engine uses Market orders without IOC or partial fills, and only 16 execution sessions are supplied. The modular research package is not a single-file organizer submission.

## Run in Windows PowerShell

Start at the original project root:

The checked-in comparison notebook is `research_set50_baseline/notebooks/01_set50_baseline_comparison.ipynb`. Its saved outputs and compact tables can be viewed without market data. Open it with Jupyter to rerun the displays; regenerating the underlying research requires the TradeSim project and local market data.

```powershell
Set-Location 'C:\Users\Windows 10\Downloads\tradeSim0.2.5'
$py = '.\tradeSimEnv\Scripts\python.exe'
& $py -X utf8 -B -m unittest discover -s .\research_set50_baseline\tests -v
& $py -X utf8 -B -m research_set50_baseline validate
& $py -X utf8 -B -m research_set50_baseline smoke
& $py -X utf8 -B -m research_set50_baseline run-native
& $py -X utf8 -B -m research_set50_baseline run-daily
```

Every command prints a new experiment path. `smoke` runs all five configurations on the first two tick sessions. `run-native` runs all 16 supplied sessions, September 9–30, 2026. `run-daily` runs all 35 complete, non-overlapping 20-session windows, a 17-session tail, and a separately labeled 16-session overlap comparison. These are independent portfolios, each starting with THB 10 million. Never stitch the reset windows into a compounded portfolio curve.

To regenerate a report without overwriting its predecessor:

```powershell
& $py -X utf8 -B -m research_set50_baseline report --experiment '<experiment-id>'
```

The initial report is `reports/`; subsequent versions use unique `reports_<timestamp>_<id>/` directories. `RESEARCH_FINDINGS.md` identifies the reviewed runs. Failed runs remain available with `status.json` and `failure.log`.

## Dependencies

Research uses the existing environment's pandas/NumPy and Python's `unittest`. Plotting packages have been copied into task-owned `vendor/` from the already installed Python 3.13 base packages. The global installation and `tradeSimEnv` were not changed. `plotting_environment.json` records versions, origins, and file hashes. Network installation was attempted but denied by the environment; the initial smoke report failure is retained.

On this machine, rebuild the plotting copy if needed:

```powershell
& $py -X utf8 -B -m research_set50_baseline.bootstrap_plotting
```

On a machine without those local packages, where network access is available:

```powershell
& $py -m pip install --no-deps --target .\research_set50_baseline\vendor -r .\research_set50_baseline\plotting-requirements.txt
```

This command assumes the original environment already provides NumPy, packaging and python-dateutil. Do not install into the global interpreter. Matplotlib's cache also stays inside this research folder.

## Configuration and outputs

`config.json` is intentionally small: 20-session lookback, top 10, rebalance every 5 sessions, 98% exposure, 15% cap, and 0.5% daily volatility floor. Capital, lot size and costs must match the engine. To try an explicitly justified configuration, save a separate JSON and pass `--config <path>`; every attempt is recorded in a new experiment. The completed study uses only the starting specification.

Each experiment includes a configuration, fixed schedule, source snapshot, source/data SHA-256 manifests, interpreter and package versions, and status. Each strategy/window has signals with their information cutoffs, target quantities and weights, orders, confirmed fills, original-lot FIFO records, daily holdings, equity, exposure, metrics, eligibility rows, and a run log. Native runs also retain original engine portfolio JSON, transaction/error logs and raw metric summaries. `comparison.csv`, `window_summary.csv`, and PNG/SVG charts are in the report directory.

Metric returns are fractions in machine-readable files; tables in the findings convert them to percentages. Payoff is THB per completed non-breakeven original buy lot. Undefined values are JSON `null` with a reason, not zero. Engine zero substitutions are preserved separately in raw engine output.

## Interpretation boundaries

- Native Market fills include one adverse tick plus 0.157% commission and 7% VAT on commission. They are not the supplied Limit/Market-to-Limit IOC rules. The engine also gates quantity using cumulative opposite-side volume, not available order-book liquidity.
- Historical daily prices are revised for capital actions. There is no vintage dataset, adjustment ledger, dividend ledger, or historical membership list. Date cutoffs are enforced, but complete point-in-time integrity cannot be certified.
- Daily executions use adjusted opening prices, assume liquidity, and charge the same price-dependent tick ladder. Historical 100-share lot economics and tick costs on adjusted prices are approximations. Daily results cannot establish official eligibility.
- The research benchmark uses prior-session close through final-session close. Native engine scoring uses first measured session close through final close. Both conventions are reported; they are not mixed silently.
- Terminal holdings remain open. Buy-and-hold is expected to fail the completed-trade criterion.

Read `STRATEGY_WALKTHROUGH.md` for the financial logic, `PROJECT_INSPECTION.md` for simulator findings, and `ROLLBACK.md` for recovery.
