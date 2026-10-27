"""Build evidence-based tables, narrative, figures, and executed notebook."""
from __future__ import annotations
import ast, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from research_set50_factors.data import load_daily
from research_set50_portfolio.core import signals, rank
from .run import HERE, OLD

def markdown_table(frame):
    f=frame.reset_index()
    return '| '+' | '.join(map(str,f.columns))+' |\n|'+ '|'.join(['---']*len(f.columns))+'|\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in f.itertuples(index=False,name=None))


def main(out: Path):
    out=out.resolve(); docs=HERE/'docs'; docs.mkdir(exist_ok=True)
    costs=pd.read_csv(out/'cost_summary.csv').set_index('experiment')
    cw=pd.read_csv(out/'cost_windows.csv')
    saved=pd.read_csv(OLD/'windows.csv')
    ev=saved[(saved.role=='evaluation')&(saved.scenario=='official')&(saved.exit_rule=='scheduled')]
    prices=pd.read_csv(out/'daily_tick_reconciliation.csv')
    failures=pd.read_csv(out/'eligibility_failures.csv').set_index('strategy')
    orders=pd.read_csv(OLD/'orders.csv'); orders=orders[(orders.scenario=='official')&(orders.exit_rule=='scheduled')&(orders.strategy.isin(list('ABCDE')))&(orders.window.isin(ev.window))].copy()
    holdings=pd.read_csv(OLD/'holdings.csv'); holdings=holdings[(holdings.scenario=='official')&(holdings.strategy.isin(list('ABCDE')))&(holdings.window.isin(ev.window))]
    targets=pd.read_csv(OLD/'targets.csv'); targets=targets[targets.strategy.isin(list('ABCDE'))]
    de=pd.read_csv(OLD/'daily_equity.csv')
    evaluation_dates=set(de[(de.strategy=='A')&(de.scenario=='official')&(de.window.isin(ev.window))].date)
    # The target file has no window/scenario columns and repeats exploratory runs.
    targets=targets[targets.date.isin(evaluation_dates)].drop_duplicates(['date','strategy'])
    syms,cal,frames,_=load_daily()
    signal_cache={}
    def signal_at(prior):
        if prior not in signal_cache:
            signal_cache[prior]=signals(frames,syms,prior)
        return signal_cache[prior]
    records=[]
    for _,r in targets.iterrows():
        day=pd.Timestamp(r.date); prior=cal[cal.get_loc(day)-1]
        s=signal_at(prior)
        target=ast.literal_eval(re.sub(r'np\.float64\(([^()]*)\)',r'\1',r.target))
        for sym,weight in target.items():
            if sym not in s.index: continue
            i=cal.get_loc(day); end=cal[min(i+4,len(cal)-1)]
            future=frames[sym].loc[end,'Close']/frames[sym].loc[day,'Open']-1
            records.append({'strategy':r.strategy,'date':r.date,'symbol':sym,'weight':weight,
              'momentum20':s.loc[sym,'mom20'],'forward_5_session_return':future,
              'entry_market_momentum20':frames['SET50'].loc[prior,'Close']/frames['SET50'].loc[cal[cal.get_loc(prior)-20],'Close']-1})
    sel=pd.DataFrame(records); sel.to_csv(out/'momentum_selection.csv',index=False)
    allforward=[]
    for day in sorted(sel.date.unique()):
        d=pd.Timestamp(day); prior=cal[cal.get_loc(d)-1]; i=cal.get_loc(d); end=cal[min(i+4,len(cal)-1)]
        s=signal_at(prior)
        for sym in s.index:
            a=frames[sym].loc[d,'Open']; b=frames[sym].loc[end,'Close']
            if np.isfinite(a) and a>0 and np.isfinite(b):
                allforward.append({'date':day,'symbol':sym,'momentum20':s.loc[sym,'mom20'],'forward_5_session_return':b/a-1,
                                   'selected_A':bool(((sel.date==day)&(sel.symbol==sym)&(sel.strategy=='A')).any())})
    pd.DataFrame(allforward).to_csv(out/'momentum_forward_universe.csv',index=False)
    # Actual fills, classified from prior close holdings and requested targets.
    priorhold={(r.window,r.strategy,r.date,r.symbol):r.shares for r in holdings.itertuples()}
    window_days={w:sorted(g.date.unique()) for w,g in holdings.groupby('window')}
    causes=[]
    for r in orders.itertuples():
        dates=window_days.get(r.window,[])
        prior_dates=[x for x in dates if x<r.date]
        old=priorhold.get((r.window,r.strategy,prior_dates[-1],r.symbol),0) if prior_dates else 0
        if r.side=='buy': cause='new_entry' if old==0 else 'add_to_holding'
        else: cause='full_exit' if r.filled>=old and old>0 else 'reduce_holding'
        causes.append({'window':r.window,'strategy':r.strategy,'date':r.date,'symbol':r.symbol,'side':r.side,
                       'cause':cause,'filled':r.filled,'notional':r.filled*r.open,'commission':r.commission if np.isfinite(r.commission) else 0,
                       'vat':r.vat if np.isfinite(r.vat) else 0,'slippage':r.slippage if np.isfinite(r.slippage) else 0})
    cause=pd.DataFrame(causes); cause.to_csv(out/'turnover_cause_orders.csv',index=False)
    cause.groupby(['strategy','cause'])[['notional','commission','vat','slippage']].sum().to_csv(out/'turnover_cause_summary.csv')
    a=sel[sel.strategy=='A']; universe=pd.read_csv(out/'momentum_forward_universe.csv')
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4)); ax.scatter(a.momentum20,a.forward_5_session_return,s=12,alpha=.45); ax.axvline(0,color='black',lw=1);ax.set(xlabel='Momentum20 at decision',ylabel='Next five-session return',title='Selected A holdings');fig.tight_layout();fig.savefig(out/'momentum_selection.png',dpi=130);plt.close(fig)
    rec=json.loads((out/'phase3_reconciliation.json').read_text())
    native=json.loads((out/'native_probe.json').read_text()) if (out/'native_probe.json').exists() else {}
    native_strategy=json.loads((out/'native_strategy_summary.json').read_text()) if (out/'native_strategy_summary.json').exists() else {}
    p3=ev[ev.strategy.isin(list('ABCDE'))].groupby('strategy').agg(mean_excess=('excess_return','mean'),mean_turnover=('turnover','mean'),mean_roundtrips=('roundtrips','mean'),best_alpha=('best_alpha_eligible','sum'))
    p3.to_csv(out/'phase3_strategy_summary.csv')
    strategy_cost=ev[ev.strategy.isin(list('ABCDE'))].groupby('strategy').agg(
        gross_return_proxy=('gross_return_proxy','mean'),mean_net=('net_return','mean'),mean_excess=('excess_return','mean'),
        mean_turnover=('turnover','mean'),commission_thb=('commission_thb','mean'),vat_thb=('vat_thb','mean'),
        slippage_thb=('slippage_thb','mean'))
    strategy_cost['total_explicit_cost_thb']=strategy_cost[['commission_thb','vat_thb','slippage_thb']].sum(axis=1)
    strategy_cost.to_csv(out/'strategy_cost_summary.csv')
    completed=pd.read_csv(OLD/'fifo_roundtrips.csv')
    completed=completed[(completed.strategy=='A')&(completed.scenario=='official')&(completed.exit_rule=='scheduled')&(completed.window.isin(ev.window))].copy()
    completed['duration_bin']=pd.cut(completed.holding_sessions_proxy,bins=[-1,7,14,30,10000],labels=['0-7 days','8-14 days','15-30 days','31+ days'])
    duration=completed.groupby('duration_bin',observed=False).agg(lots=('pnl','size'),mean_pnl=('pnl','mean'),win_rate=('pnl',lambda x:float((x>0).mean()))).fillna(0)
    duration.to_csv(out/'holding_duration_diagnostics.csv')
    rulebook='''# Exact Phase 3 strategy rulebook

Source: `research_set50_portfolio/core.py`, `runner.py`, frozen config. All decisions use completed prior-session data, with intended execution at the next session's adjusted open. These are research fills, not official IOC orders.

| Rule | A | B | C | D | E |
|---|---|---|---|---|---|
| Primary rank | Momentum20 descending | Same | Same | Same | Same, A base selected on development windows |
| Reversal tie | No | No | Yes | Yes | No for selected A base |
| Weights | Equal | Inverse 20-day daily return volatility | Equal | Inverse volatility | Equal |
| Holdings | Six | Six | Six | Six | Six |
| Target exposure / cap | 80% / 20% | 80% / 20% | 80% / 20% | 80% / 20% | 75% / 18% |
| Scheduled rebalance | Every five sessions including first | Same | Same | Same | Same |
| Retention | None | None | None | None | Keep former names in top ten ranks |
| Weight-change threshold | None | None | None | None | Skip change below 3% of NAV after first session |

Momentum20 = Close(t)/Close(t-20)-1. A stock at -2% can be selected if it is among the six highest scores; **positive momentum is not required**. For example, -2% ranks above -5%. SMA20/SMA60 = mean(last 20 closes)/mean(last 60 closes)-1 is the separate `sma_trend` comparator, not A–E. Reversal1 = 1-Close(t)/Close(t-1); C and D use it only within contiguous groups whose primary-score gap from the group's first member is at most 5% of the full cross-sectional Momentum20 span. For equal weighting, six names receive roughly 13.33% each under the 20% cap; E receives 12.5% each under its 18% cap. Inverse-volatility allocation redistributes under the same caps.

Eligibility requires 61 valid trailing bars for a stock, finite positive volatility and positive mean trailing 20-session volume. All 61 bars must pass the daily OHLCV validity check. No missing-bar forward fill enters the signal. Ranking is stable on ties. Target shares use prior close and round down to 100. Sells are attempted before buys; each order is capped at 1% of prior 20-session average volume, cash and share availability. Modeled execution uses adjusted next open plus/minus one local tick, full capped fill, 0.157% commission and 7% VAT on commission. End-session close marks holdings; open lots are not forced closed. FIFO round-trips count only fully closed original buy lots. Thus order count, sell count, and completed round-trip count differ. Exposure is mean end-session invested NAV fraction; expected payoff is mean nonzero net P&L of completed lots. Calmar is cumulative net return divided by maximum drawdown (undefined at zero drawdown).
'''
    (docs/'01_strategy_rulebook.md').write_text(rulebook)
    match=int(prices.all_ohlc_match.sum()); n=len(prices)
    (docs/'02_execution_validation.md').write_text(f'''# Execution and data validation

The frozen Phase 3 run reproduced {rec['matched_rows']}/{rec['saved_rows']} rows exactly: maximum absolute difference across the 14 checked numerical and eligibility fields is {max(rec['max_absolute_difference'].values()):.3g}, tolerance {rec['tolerance']}. This validates deterministic reproduction, not economic realism.

Raw tick coverage is 16 sessions (2026-09-09 through 2026-09-30). Across {n} overlapping stock-days, {match} have identical daily and tick OHLC under auction-aware reconstruction. The 16 tick files are **not globally timestamp sorted**; within-symbol timestamps were sorted before reconciliation. This confirms no visible adjustment difference in this short overlap. It does not establish historical adjustment factors for 2023–2026 or validate a one-tick fill on adjusted daily prices. Earlier corporate-action ratios require raw historical prices or vendor adjustment metadata. The tick reconstruction uses OPEN1_E and ATC prints where present; absence is flagged in the CSV. A matching OHLC does not reveal executable bid/ask depth.

Local tick ladder equals `tradeSim.CommissionService`: steps are THB 0.01 below 2, .02 from 2, .05 from 5, .10 from 10, .25 from 25, .50 from 100, 1 from 200, and 2 from 400. At boundary prices the higher step applies. Applying that ladder to adjusted historical prices may produce non-executable levels when adjustment factors differ from one.

The isolated native probe on {native.get('tick_session','unavailable')} submitted a 100-share {native.get('tick_symbol','')} Market buy at raw last price {native.get('tick_price','')}. Cash debit was THB {native.get('cash_debit',float('nan')):,.5f}, differing from the independently computed one-tick plus fee/VAT debit by THB {native.get('cash_delta_error',float('nan')):.3g}. This checks a single native fill and cash entry. A separate frozen-A signal replay across all {native_strategy.get('sessions','?')} tick sessions made {native_strategy.get('attempted_orders','?')} native order attempts and {native_strategy.get('filled_orders','?')} fills. Its ending NAV was THB {native_strategy.get('ending_nav',float('nan')):,.2f} versus THB {native_strategy.get('daily_model_ending_nav',float('nan')):,.2f} for a matched 16-session daily-model replay, a THB {native_strategy.get('ending_nav_difference',float('nan')):,.2f} difference. Native completed {native_strategy.get('completed_fifo_lots','?')} original FIFO lots versus {native_strategy.get('daily_model_completed_fifo_lots','?')} in the daily model. The native adapter waits for observed opposing cumulative tick volume and orders at the first eligible chronological tick, while the daily model assumes capped next open fills; therefore both price and holdings paths differ. The replay is a practice-engine diagnostic, not an official IOC backtest or a 20-session competition outcome. Native `Order.py` accepts Limit and Market; `Execution.py` models immediate one-tick market fills and resting tick-flag-based limit fills. No native Market-to-Limit IOC depth model or official validator was found.

Reconciliation: `daily_tick_reconciliation.csv`, `tick_session_alignment.csv`, `inferred_adjustment_ratios.csv`, `native_probe.json`. Differences are not automatically labeled corporate actions; this overlap shows none. Future earlier-date discrepancies must be classified with vendor metadata before changing the backtester.
''')
    costs_table=markdown_table(costs[['mean_excess','mean_turnover','mean_commission','mean_vat','mean_slippage','mean_cost_pct','mean_roundtrips','common_pass','best_alpha_pass']].round(5))
    direct=costs.loc['one_tick','mean_cost_pct']; total=costs.loc['zero','mean_excess']-costs.loc['one_tick','mean_excess']
    (docs/'03_cost_analysis.md').write_text(f'''# Trading cost decomposition

The same frozen decisions and 24 evaluation windows were rerun for every A scenario. Price changes alter affordable shares and later holdings, so scenario differences are path effects as well as paid fees. Gross-return proxy in Phase 3 adds booked costs to final NAV but is **not** a separate no-cost portfolio path. Saved Phase 3 costs for all A–E are:

{markdown_table(strategy_cost.round(5))}

{costs_table}

For A, no-cost mean excess is {costs.loc['zero','mean_excess']:.4%}; one-tick net mean excess is {costs.loc['one_tick','mean_excess']:.4%}. The gap is {total:.4%} of initial capital. Mean booked commission is THB {costs.loc['one_tick','mean_commission']:,.2f}, VAT THB {costs.loc['one_tick','mean_vat']:,.2f}, adverse-tick impact THB {costs.loc['one_tick','mean_slippage']:,.2f}, jointly {direct:.4%} of initial capital. The residual {total-direct:.4%} is execution-path/sizing difference at mean level, including changed cash and holdings. It is not a separately charged fee. Commission-only leaves {costs.loc['commission','mean_excess']:.4%} mean excess; commission plus VAT leaves {costs.loc['commission_vat','mean_excess']:.4%}. Two adverse ticks give {costs.loc['two_ticks','mean_excess']:.4%}. Removing only the 1% prior-volume cap gives {costs.loc['unconstrained_cap','mean_excess']:.4%}; half fills give {costs.loc['half_fills','mean_excess']:.4%}. These are sensitivity bounds, not verified IOC outcomes.

At turnover {costs.loc['one_tick','mean_turnover']:.3f}× initial capital, the booked cost hurdle is {direct:.3%}. An approximate per-notional cost is {direct/costs.loc['one_tick','mean_turnover']:.3%}; at turnover 1×, 2×, and 3× initial capital, corresponding break-even gross alpha is about {direct/costs.loc['one_tick','mean_turnover']:.3%}, {2*direct/costs.loc['one_tick','mean_turnover']:.3%}, and {3*direct/costs.loc['one_tick','mean_turnover']:.3%}. This linear approximation holds execution mix fixed. The apparent pre-cost 1.22% mean excess is smaller than the 2.12% booked hurdle and is not proof of a predictive signal. Adjusted-open tick slippage could overstate or understate real spread/impact; quote depth, latency and historical raw prices are missing.
''')
    neg=int((a.momentum20<=0).sum()); total_sel=len(a)
    selmean=float(universe[universe.selected_A].forward_5_session_return.mean()); nonmean=float(universe[~universe.selected_A].forward_5_session_return.mean())
    a_cause=cause[cause.strategy=='A'].groupby('cause').notional.sum()
    (docs/'04_strategy_failure_analysis.md').write_text(f'''# Strategy failure diagnosis

Phase 3 official A–E summary (24 previously examined windows each):

{markdown_table(p3.round(5))}

Actual target selection for A contains {neg}/{total_sel} nonpositive Momentum20 observations. The five-session open-to-close diagnostic mean is {selmean:.3%} for selected A stock-date observations and {nonmean:.3%} for nonselected eligible stock-date observations. These overlapping observations share market regimes and are not a tradable portfolio return or untouched holdout. Momentum strength and dispersion are in `momentum_selection.csv` and `momentum_forward_universe.csv`. Phase 2 factor evidence reported weak Momentum20 rank IC; the positive cross-sectional difference here cannot establish robust actionable alpha after costs.

A filled turnover by action (THB, all windows): {a_cause.to_dict()}. These are actual order fills. `new_entry` and `full_exit` show replacement, while `add_to_holding` and `reduce_holding` include target drift correction. Exact rank-change versus risk-overlay attribution is not identifiable from recorded target and fill fields alone; E's retention and threshold are controlled comparisons. E lowered mean turnover to {p3.loc['E','mean_turnover']:.3f}× but only {p3.loc['E','mean_roundtrips']:.3f} fully closed FIFO lots on average. The five-trip gate fails in {int(failures.loc['E','roundtrip_pass'])}/24 windows. A payoff fails in {int(failures.loc['A','payoff_pass'])}/24; E in {int(failures.loc['E','payoff_pass'])}/24. The exposure gate fails in zero A–E windows. A drawdown fails in {int(failures.loc['A','drawdown_pass'])}/24. Detailed simultaneous failures are recorded per window in `eligibility_windows.csv`; failure counts overlap and should not be added.

The exploratory positive Momentum20 filter changes A's mean excess from {costs.loc['one_tick','mean_excess']:.4%} to {costs.loc['positive_momentum','mean_excess']:.4%}, with mean exposure {costs.loc['positive_momentum','mean_exposure']:.2%} and {int(costs.loc['positive_momentum','best_alpha_pass'])}/24 best-alpha passes. A ten-session rebalance changes mean turnover from {costs.loc['one_tick','mean_turnover']:.3f}× to {costs.loc['rebalance_every_10','mean_turnover']:.3f}×, mean excess to {costs.loc['rebalance_every_10','mean_excess']:.4%}, and completed lots to {costs.loc['rebalance_every_10','mean_roundtrips']:.2f}; it has {int(costs.loc['rebalance_every_10','best_alpha_pass'])}/24 best-alpha passes. This lower-turnover result fails the five-trip constraint frequently and is not a viable competition improvement as tested. Do not add artificial trades to satisfy it.

Completed A original-lot holding duration uses calendar days as recorded by Phase 3, not session count. Exploratory bins show:

{markdown_table(duration.round(2))}

This completed-lot sample excludes still-open holdings and is subject to exit-selection bias. Post-exit prices and matched trade reasons are not recorded in the frozen run, so no claim about post-exit alpha or payoff by exit reason is made.
''')
    (docs/'05_research_recommendations.md').write_text('''# Research decision

**C: improve execution/data validation before further strategy research; then B: return to factor discovery if the signal remains uneconomic.** The frozen daily model reproduces exactly and the 16-session native practice replay exposes a material execution-path difference, but historical adjusted-price ticks, executable spread/depth and official IOC behavior remain unresolved. The 16 raw tick sessions cannot validate a 20-session competition run. No original or exploratory A variant establishes reliable net excess with eligibility. All 24 windows have been examined; fresh chronological data are needed for any new out-of-sample claim. Machine learning is premature without a concrete predictive target, adequate chronological data, and an economically credible edge above costs. Do not select the best exploratory parameter by historical return alone.

Competition eligibility is a gate, not a scoring weight or rank. Calmar is cumulative return divided by maximum drawdown under the local organizer implementation. The original versus corrected execution table is the cost-scenario table: no validated corrected historical execution model exists, so no corrected-performance claim is made.
''')
    from .build_notebook import build
    build(out)
    print('Reports written',docs)

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
