"""Generate and execute the complete Phase 3.5 analytical notebook."""
from __future__ import annotations
import json
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent


def build(out: Path):
    out=out.resolve()
    from research_set50_portfolio.core import tick
    from tradeSim.CommissionService import commissionService
    levels=[1.99,2,4.99,5,9.99,10,24.99,25,99.99,100,199.99,200,399.99,400]
    import pandas as pd
    pd.DataFrame({'price':levels,'daily_tick':[tick(x) for x in levels],
                  'native_tick':[commissionService._get_slippage(x) for x in levels]}).to_csv(out/'tick_size_validation.csv',index=False)
    cells=[]
    def md(s): cells.append(nbformat.v4.new_markdown_cell(s))
    def code(s): cells.append(nbformat.v4.new_code_cell(s))
    md('''# Phase 3.5 — Execution validation and strategy diagnosis

Executed research notebook. This uses frozen Phase 3 outputs and executed Phase 3.5 experiments. All 24 evaluation windows have been examined before; exploratory variants are **not untouched out-of-sample evidence**. Currency is THB unless stated. The daily model is not the official IOC validator.''')
    code("""from pathlib import Path
import json, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
rid = '"""+out.name+"""'
candidates = [Path.cwd()/'research_set50_execution_validation'/'results'/rid,
              Path.cwd()/'research_set50_execution_validation'/'published_results'/rid,
              Path.cwd().parent/'results'/rid,
              Path.cwd().parent/'published_results'/rid,
              Path.cwd()/'results'/rid]
out = next(p for p in candidates if p.exists())
old = out.parents[2]/'research_set50_portfolio'/'published_results'/'20261027T162905Z_979c875c'
if not old.exists(): old = out.parents[2]/'research_set50_portfolio'/'results'/'20261027T162905Z_979c875c'
print('Experiment:', out.name)
print('Saved Phase 3:', old.exists())""")
    md('''## 1. Frozen Phase 3 reproduction

The comparison matches every saved row by window, role, strategy, scenario, and exit rule. A zero numerical difference proves deterministic reproduction under the same inputs; it does not validate executable prices.''')
    code("""r=json.loads((out/'phase3_reconciliation.json').read_text())
display(pd.DataFrame({'metric':list(r['max_absolute_difference']),
                      'maximum_absolute_difference':list(r['max_absolute_difference'].values())}))
print('Matched rows:',r['matched_rows'],'/',r['saved_rows'],'; tolerance:',r['tolerance'])
assert r['matched_rows']==r['saved_rows'] and max(r['max_absolute_difference'].values())<=r['tolerance']""")
    md('''## 2. Actual trading rules

A–E rank permitted, sufficiently complete stocks by **Momentum20 = Close(t)/Close(t−20) − 1**. Positive momentum is not required: −2% can rank above −5%. Six stocks are targeted. A/C use equal weights; B/D use inverse 20-day volatility. C/D use one-day reversal only as a close-rank tie breaker. E uses the development-selected A base, top-ten retention, 75% target exposure, 18% cap and a 3% weight-change threshold. Others target 80% exposure, 20% cap. Rebalance is every five sessions using the prior completed close, with modeled next-open execution. The separate SMA20/SMA60 experiment is not A–E.

Commission is 0.157% per filled side, VAT is 7% of commission, quantities use 100-share lots, and the daily model applies one adverse tick and a 1% trailing-volume participation cap. FIFO counts a buy lot only after it is fully closed. See the [rulebook](../docs/01_strategy_rulebook.md) for missing-data and accounting details.''')
    md('''## 3. Daily prices against raw ticks

The overlap covers 16 sessions. Auction prints are used for open and close. A matching OHLC is evidence about this overlap only; historical corporate-action factors and quote depth remain unavailable.''')
    code("""p=pd.read_csv(out/'daily_tick_reconciliation.csv')
t=pd.read_csv(out/'tick_session_alignment.csv')
display(pd.DataFrame([{'stock_days':len(p),'all_OHLC_match':int(p.all_ohlc_match.sum()),
 'missing_open_auction':int((~p.auction_open).sum()),'missing_close_auction':int((~p.auction_close).sum()),
 'globally_sorted_tick_files':int(t.globally_monotonic.sum()),'tick_files':len(t)}]))
fig,ax=plt.subplots(figsize=(7,3));ax.hist(p.open_difference,bins=30);ax.set(title='Daily open minus raw tick open',xlabel='THB',ylabel='Stock-days');plt.show()""")
    md('''## 4. Tick ladder and slippage uncertainty

The local daily model and native practice engine share the same ladder. That agreement does not establish that adjusted historical opens were executable at the corresponding tick levels.''')
    code("""ladder=pd.read_csv(out/'tick_size_validation.csv')
display(ladder)
assert (ladder.daily_tick==ladder.native_tick).all()""")
    md('''## 5. Cost decomposition across A–E

The gross-return proxy adds booked costs back to final NAV. It is not a separate zero-cost portfolio path. Scenario comparisons below rerun A under changed costs and preserve the signal decision rule.''')
    code("""sc=pd.read_csv(out/'strategy_cost_summary.csv')
display(sc[['strategy','gross_return_proxy','mean_net','mean_excess','mean_turnover',
            'commission_thb','vat_thb','slippage_thb','total_explicit_cost_thb']].round(4))
sc.set_index('strategy')[['commission_thb','vat_thb','slippage_thb']].plot.bar(stacked=True,figsize=(8,4),ylabel='Mean THB per 20-session window');plt.show()""")
    md('''## 6. Matched execution scenarios for A

Cost-free A is diagnostic. Commission, VAT, adverse ticks, the participation cap, and half-fill sensitivities are tested with distinct portfolio paths. The last two are execution assumptions, not observed IOC outcomes.''')
    code("""c=pd.read_csv(out/'cost_summary.csv').set_index('experiment')
display(c[['mean_excess','mean_net','mean_turnover','mean_cost_pct','mean_roundtrips','common_pass','best_alpha_pass']].round(5))
direct=c.loc['one_tick','mean_cost_pct']; gap=c.loc['zero','mean_excess']-c.loc['one_tick','mean_excess']
display(pd.DataFrame([{'zero_to_one_tick_gap':gap,'booked_cost_fraction':direct,
                       'path_and_sizing_residual':gap-direct}]))
assert abs(c.loc['one_tick','mean_excess']+0.008990066405743463)<1e-10""")
    code("""w=pd.read_csv(out/'cost_windows.csv')
pair=w[w.experiment.isin(['zero','one_tick'])].pivot(index='window',columns='experiment',values='excess_return')
pair.plot(figsize=(9,3.5),marker='o',ylabel='Excess return',title='Same historical windows under zero versus one-tick costs');plt.show()
fig,ax=plt.subplots(figsize=(7,4))
for label,g in w.groupby('experiment'):
    if label in ['zero','one_tick','two_ticks','rebalance_every_10']:
        ax.scatter(g.turnover,g.excess_return,s=18,alpha=.6,label=label)
ax.legend();ax.set(xlabel='Turnover / initial capital',ylabel='Net excess return');plt.show()""")
    md('''## 7. Break-even gross alpha

At the observed turnover and execution mix, required pre-cost alpha is approximately the booked cost fraction. This is a cost hurdle, not evidence that the signal can generate it.''')
    code("""unit_cost=direct/c.loc['one_tick','mean_turnover']
display(pd.DataFrame({'turnover_multiple':[1,2,3],
                      'approx_required_alpha':[unit_cost*x for x in [1,2,3]]}))
print('Observed no-cost mean excess:',round(c.loc['zero','mean_excess']*100,3),'%')""")
    md('''## 8. Native practice simulator on 16 tick sessions

A single real-tick buy verifies fee/cash arithmetic. The signal-driven 16-session replay uses frozen A decisions, waits for observed opposing tick volume, and submits Market orders on the first eligible chronological tick. The matched daily replay uses next-open modeled fills. This is neither an official Market-to-Limit IOC test nor a complete 20-session competition result.''')
    code("""probe=json.loads((out/'native_probe.json').read_text())
ns=json.loads((out/'native_strategy_summary.json').read_text())
display(pd.DataFrame([ns]))
print('Single-order native cash error (THB):',probe['cash_delta_error'])
nd=pd.read_csv(out/'native_strategy_daily.csv').set_index('date')
nd[['nav','daily_model_nav']].plot(figsize=(9,3.5),ylabel='THB NAV',title='Matched 16-session replay');plt.show()
display(pd.read_csv(out/'native_strategy_orders.csv').groupby('side').agg(attempts=('filled','size'),fills=('filled',lambda x:int((x>0).sum()))))""")
    md('''## 9. Momentum selection and future returns

Future returns are diagnostics measured after the decision, not inputs to that decision. Observations overlap and share market regimes. Any selected-versus-unselected difference is not independent out-of-sample alpha.''')
    code("""m=pd.read_csv(out/'momentum_selection.csv')
u=pd.read_csv(out/'momentum_forward_universe.csv')
a=m[m.strategy=='A']
display(pd.DataFrame([{'selected_A_observations':len(a),'nonpositive_momentum':int((a.momentum20<=0).sum()),
 'selected_forward_mean':u[u.selected_A].forward_5_session_return.mean(),
 'unselected_forward_mean':u[~u.selected_A].forward_5_session_return.mean()}]))
fig,ax=plt.subplots(figsize=(7,4));ax.scatter(a.momentum20,a.forward_5_session_return,s=12,alpha=.4)
ax.axvline(0,color='black',lw=1);ax.set(xlabel='Momentum20 at decision',ylabel='Five-session return');plt.show()""")
    md('''## 10. Turnover, FIFO duration, and eligibility

Actual filled orders distinguish new entries, additions, reductions, and full exits. The frozen records do not identify every exit reason. Holding-duration bins include only completed original FIFO lots, so they have exit-selection bias. Award eligibility is a gate, distinct from performance ranking.''')
    code("""cause=pd.read_csv(out/'turnover_cause_summary.csv')
display(cause[cause.strategy=='A'].round(2))
dur=pd.read_csv(out/'holding_duration_diagnostics.csv')
display(dur.round(2))
fails=pd.read_csv(out/'eligibility_failures.csv').set_index('strategy').loc[list('ABCDE')]
display(fails)
fails[['drawdown_pass','roundtrip_pass','payoff_pass']].plot.bar(figsize=(8,4),ylabel='Failed windows out of 24');plt.show()""")
    md('''## 11. Controlled hypotheses and decision

The positive-momentum filter barely changes A. Ten-session rebalancing reduces costs but collapses completed FIFO lots and yields no Best Alpha eligible windows. The 24 windows have already been inspected. Without historical executable prices, official IOC behavior, and fresh chronological data, there is no defensible corrected-execution return estimate and no case for machine learning yet.''')
    code("""display(c.loc[['one_tick','positive_momentum','rebalance_every_10'],
 ['mean_excess','mean_turnover','mean_roundtrips','mean_exposure','best_alpha_pass']].round(5))
print('Decision: validate execution and historical adjustment data; then revisit factor discovery.')""")
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    nb=NotebookClient(nb,timeout=120,kernel_name='python3').execute()
    path=ROOT/'notebooks/035_execution_diagnostics.ipynb'
    path.parent.mkdir(exist_ok=True)
    nbformat.write(nb,path)
    try:
        from nbconvert import HTMLExporter
        html,_=HTMLExporter().from_notebook_node(nb)
        publication=ROOT/'publication'
        publication.mkdir(exist_ok=True)
        (publication/'phase35_execution_diagnostics.html').write_text(html,encoding='utf-8')
    except ImportError:
        pass
    summary={'cells':len(nb.cells),'code_cells':sum(c.cell_type=='code' for c in nb.cells),
             'executed_code_cells':sum(c.cell_type=='code' and c.execution_count is not None for c in nb.cells),
             'notebook':str(path),'html':str(ROOT/'publication/phase35_execution_diagnostics.html')}
    (out/'notebook_verification.json').write_text(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    import sys
    print(json.dumps(build(Path(sys.argv[1])),indent=2))
