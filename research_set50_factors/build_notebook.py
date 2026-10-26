"""Create and execute a results-backed notebook in a fresh Python kernel."""
from __future__ import annotations

from pathlib import Path
import sys
import nbformat as nbf
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parent.parent
PACKAGE=Path(__file__).resolve().parent


def build(run_folder:Path):
    run_folder=run_folder.resolve()
    if not (run_folder/"status.json").exists():raise ValueError("Missing run")
    import json
    if json.loads((run_folder/"status.json").read_text())["status"]!="complete":raise ValueError("Run incomplete")
    nb=nbf.v4.new_notebook(metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},
                                    "language_info":{"name":"python"}})
    C=nbf.v4.new_code_cell; M=nbf.v4.new_markdown_cell
    nb.cells=[
      M("# SET50 Phase 2: Factor and signal research\n\nPre-registered cross-sectional study. Historical adjusted opens are research labels, not confirmed execution prices. Evaluation is chronological but was not wholly unseen after Phase 1."),
      C(f"from pathlib import Path\nimport pandas as pd, json\nfrom IPython.display import display, Image\nrun=Path({str(run_folder)!r})\nassert json.loads((run/'status.json').read_text())['status']=='complete'\nprint('Run:',run.name)"),
      M("## Objectives and data overview\n\nTest predictive ranking, economic magnitude, stability, and feasibility separately. The permitted list is current and historical membership is unavailable."),
      C("audit=pd.read_csv(run/'data_inventory.csv'); display(audit[['symbol','rows','first','last','missing_calendar_sessions','invalid_ohlc_rows']].head(12)); display(Image(filename=str(run/'figures/data_coverage.png')))"),
      M("## Feature definitions and timing\n\nAll features use completed closes and volume through `t`. The earliest entry is `t+1` open; horizon `h` exits at `t+1+h` open. Relative strength subtracts the same benchmark return from every stock, so it does not create a new same-date ranking."),
      C("config=json.loads((run/'config.json').read_text()); print('Factors:',len(config['factor_directions']),'Horizons:',config['horizons']); display(pd.read_csv(run/'timeline.csv').head()); from research_set50_factors.data import load_daily; from research_set50_factors.factors import make_factors; symbols,calendar,daily,_=load_daily(); factors,_,_=make_factors(symbols,calendar,daily); date=calendar[100]; symbol='ADVANC'; print('Example 5-session momentum:',symbol,str(date.date()),round(float(factors['mom_5'].loc[date,symbol]),5))"),
      M("## Predictive power: IC and Rank IC\n\nCorrelations are computed separately each date, then summarized across dates. The information ratio is unannualized mean IC divided by daily IC standard deviation. Intervals use a time-series-aware HAC estimate."),
      C("summary=pd.read_csv(run/'factor_summary.csv'); ev=summary[(summary.role=='evaluation')&(summary.horizon==5)].sort_values('mean_rank_ic',ascending=False); display(ev[['factor','dates','mean_ic','mean_rank_ic','rank_hac_lo','rank_hac_hi','rank_fdr_q']]); display(Image(filename=str(run/'figures/evaluation_rank_ic_comparison.png')))"),
      M("## Quantile analysis\n\nTop minus bottom is only a factor diagnostic. A long-only portfolio needs absolute and benchmark-relative top-group returns to be useful."),
      C("q=pd.read_csv(run/'quantile_summary.csv'); display(q[(q.role=='evaluation')&(q.horizon==5)&(q['quantile']==5)][['factor','dates','mean_return','benchmark_relative']].sort_values('benchmark_relative',ascending=False).head(12)); display(Image(filename=str(run/'figures/evaluation_quantile_mom_5.png')))"),
      M("## Horizon sensitivity\n\nEvery predeclared horizon appears here; no best horizon is selected and called independently validated."),
      C("display(Image(filename=str(run/'figures/evaluation_horizon_heatmap.png'))); display(summary[summary.role=='evaluation'].pivot(index='factor',columns='horizon',values='mean_rank_ic').round(3))"),
      M("## Stability, regimes, and redundancy\n\nRolling and cumulative IC are diagnostics, never equity curves. Regimes use information available at signal time. The correlation matrix measures overlapping factor information."),
      C("display(Image(filename=str(run/'figures/evaluation_rolling_ic.png'))); display(Image(filename=str(run/'figures/evaluation_cumulative_ic.png'))); display(Image(filename=str(run/'figures/evaluation_regime.png'))); display(Image(filename=str(run/'figures/factor_correlation.png'))); segments=pd.read_csv(run/'segment_ic.csv'); display(segments[(segments.factor=='reversal_1')&(segments.horizon==1)&(segments.role=='evaluation')][['period_id','mean_rank_ic']].head(10))"),
      M("## Turnover and cost diagnostics\n\nAdjusted-open notionals estimate ranking changes and commission floors only. One-tick amounts below use actual raw first-tick reference prices for 16 sessions and are not claimed as fills."),
      C("proxy=pd.read_csv(run/'ranking_proxy.csv'); raw=pd.read_csv(run/'raw_tick_cost_reference.csv'); display(proxy[(proxy.role=='evaluation')&(proxy.frequency==5)].groupby('factor')[['total_one_way_turnover','commission_vat_thb']].mean().sort_values('total_one_way_turnover').head(12)); print('Raw tick reference rows:',len(raw)); display(raw[['reference_roundtrip_tick_fraction','reference_total_roundtrip_fraction']].describe()); display(Image(filename=str(run/'figures/evaluation_turnover.png')))"),
      M("## Phase 1 comparison and statistical interpretation\n\nPhase 1 native momentum and relative equal-weight performance were identical, consistent with their identical rankings. Inverse-volatility sizing changed portfolio outcomes, not the ranking. RSI's native relative outperformance coincided with low exposure and negative expected payoff. Phase 2 date-level IC and quantiles test whether any raw ranking had information before portfolio mechanics. The evaluation dates were already viewed in Phase 1, and revised data plus current-universe membership limit causal claims."),
      C("phase1=pd.read_csv('research_set50_baseline/results/native_comparison_16_sessions.csv'); display(phase1[['strategy','net_return','excess_return','average_exposure','expected_payoff','turnover']]); display(ev[['factor','mean_rank_ic','rank_fdr_q']].head(10))"),
      M("## Conclusions and Phase 3 decision\n\nOne-day reversal has repeatable short-horizon ranking information, but its top-group mean advantage is smaller than the commission-only round trip and its turnover is high. It merits testing only as a tie-breaker for already-planned trades, with incremental turnover measured. Momentum's one-session continuation hypothesis is contradicted; longer-horizon results are unstable and a 20-session target may exit outside the competition window. RSI oversold is unsupported here. No factor is proven profitable or competition eligible. Phase 3 must test completed round-trips, exposure, drawdown, payoff, and actual order fills separately. See `RESEARCH_FINDINGS.md` for the full evidence table.")
    ]
    path=PACKAGE/"notebooks/02_factor_signal_research.ipynb";path.parent.mkdir(exist_ok=True)
    client=NotebookClient(nb,timeout=600,kernel_name="python3",resources={"metadata":{"path":str(ROOT)}})
    executed=client.execute()
    nbf.write(executed,path)
    print("Executed notebook",path)
    return path


if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: python -m research_set50_factors.build_notebook <completed-run>")
    build(Path(sys.argv[1]))
