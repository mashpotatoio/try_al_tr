"""Execute independent Phase 3.5 checks without changing Phase 3 files."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from research_set50_factors.data import load_daily, sha256
from research_set50_portfolio import runner
from research_set50_portfolio.core import Account, tick

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / 'research_set50_portfolio/results/20261027T162905Z_979c875c'


def prices(out: Path):
    daily_dir = ROOT / 'marketInfo/daily_history'
    rows, time_rows = [], []
    for path in sorted((ROOT / 'marketInfo/ticks').glob('*.csv')):
        t = pd.read_csv(path, parse_dates=['TradeDateTime'])
        if t.empty:
            continue
        time_rows.append({'date': path.stem, 'rows': len(t), 'globally_monotonic': t.TradeDateTime.is_monotonic_increasing,
                          'first_timestamp': str(t.TradeDateTime.min()), 'last_timestamp': str(t.TradeDateTime.max())})
        for sym, g in t.groupby('ShareCode', sort=False):
            p = daily_dir / f'{sym}.csv'
            if not p.exists():
                continue
            d = pd.read_csv(p)
            match = d[d.Date == path.stem]
            if match.empty:
                continue
            m = match.iloc[0]
            g = g.sort_values('TradeDateTime', kind='stable')
            a = g[g.Flag == 'OPEN1_E']
            close = g[g.Flag == 'ATC']
            raw = {'Open': float(a.LastPrice.iloc[0]) if len(a) else float(g.LastPrice.iloc[0]),
                   'High': float(g.LastPrice.max()), 'Low': float(g.LastPrice.min()),
                   'Close': float(close.LastPrice.iloc[-1]) if len(close) else float(g.LastPrice.iloc[-1])}
            row = {'date': path.stem, 'symbol': sym, 'tick_rows': len(g), 'auction_open': bool(len(a)), 'auction_close': bool(len(close)),
                   'tick_first': str(g.TradeDateTime.iloc[0]), 'tick_last': str(g.TradeDateTime.iloc[-1]),
                   'raw_tick_valid_open': bool(abs(raw['Open'] / tick(raw['Open']) - round(raw['Open'] / tick(raw['Open']))) < 1e-6)}
            for col in raw:
                row[f'daily_{col.lower()}'] = float(m[col]); row[f'tick_{col.lower()}'] = raw[col]
                row[f'{col.lower()}_difference'] = float(m[col]) - raw[col]
                row[f'{col.lower()}_ratio'] = float(m[col]) / raw[col] if raw[col] else np.nan
            row['all_ohlc_match'] = all(abs(row[f'{c.lower()}_difference']) < 1e-6 for c in raw)
            row['status'] = 'verified_match' if row['all_ohlc_match'] else 'difference_unattributed'
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(out / 'daily_tick_reconciliation.csv', index=False)
    pd.DataFrame(time_rows).to_csv(out / 'tick_session_alignment.csv', index=False)
    if not df.empty:
        ratios = df.groupby('symbol').open_ratio.agg(['min', 'max', 'count'])
        ratios['range'] = ratios['max'] - ratios['min']
        ratios.to_csv(out / 'inferred_adjustment_ratios.csv')
    return df


def phase3(out: Path):
    saved = pd.read_csv(OLD / 'windows.csv')
    newest = sorted((ROOT / 'research_set50_portfolio/results').glob('*/windows.csv'), key=lambda p: p.stat().st_mtime)[-1]
    reproduced = pd.read_csv(newest)
    keys = ['window', 'role', 'strategy', 'scenario', 'exit_rule']
    cols = ['net_return', 'gross_return_proxy', 'benchmark_return', 'excess_return', 'commission_thb', 'vat_thb',
            'slippage_thb', 'turnover', 'max_drawdown', 'average_exposure', 'roundtrips', 'expected_payoff_thb',
            'common_eligible', 'best_alpha_eligible']
    a = saved[keys + cols].merge(reproduced[keys + cols], on=keys, suffixes=('_saved', '_reproduced'), validate='one_to_one')
    for c in cols:
        a[c + '_difference'] = a[c + '_reproduced'].astype(float) - a[c + '_saved'].astype(float)
    a[keys + [c + '_difference' for c in cols]].to_csv(out / 'phase3_reconciliation.csv', index=False)
    summary = {c: float(a[c + '_difference'].abs().max()) for c in cols}
    (out / 'phase3_reconciliation.json').write_text(json.dumps({'saved_rows':len(saved), 'reproduced_rows':len(reproduced),
        'matched_rows':len(a), 'max_absolute_difference':summary, 'tolerance':1e-10, 'reproduced_path':str(newest)}, indent=2))
    if len(a) != len(saved) or any(v > 1e-10 for v in summary.values()):
        raise RuntimeError('Phase 3 reproduction discrepancy; stop hypothesis tests')
    return saved


def _run_with_cost(w, data, cfg, mode, *, positive=False, rebalance=None):
    original_trade, original_rank = Account.trade, runner.rank
    choices = {'zero':(0,0,0,False,1), 'commission':(.00157,0,0,False,1),
               'commission_vat':(.00157,.07,0,False,1), 'one_tick':(.00157,.07,1,False,1),
               'two_ticks':(.00157,.07,2,False,1), 'unconstrained_cap':(.00157,.07,1,True,1),
               'half_fills':(.00157,.07,1,False,.5)}
    comm, vat, ticks, uncap, fraction = choices[mode]
    def trade(self, date, sym, side, requested, open_price, cap_shares, **kwargs):
        return original_trade(self,date,sym,side,requested,open_price,
                              10**12 if uncap else cap_shares, commission=comm,vat_rate=vat,ticks=ticks,fill_fraction=fraction)
    def rank(frame, primary='mom20', tie=False, gap=.05):
        if positive and not frame.empty:
            frame=frame[frame.mom20 > 0]
        return original_rank(frame,primary,tie,gap)
    Account.trade, runner.rank = trade, rank
    try:
        par = {'e_base':'A'}
        if rebalance is not None: par['rebalance_every']=rebalance
        result = runner.run_window(w,'A',data,cfg,params=par)
    finally:
        Account.trade, runner.rank = original_trade, original_rank
    return result


def scenarios(out: Path):
    cfg=json.loads((ROOT/'research_set50_portfolio/configs/preregistered.json').read_text())
    schedule=json.loads((runner.PHASE2/'schedule.json').read_text())
    ev=[w for w in schedule if w['role']=='evaluation']
    syms,cal,frames,_=load_daily(); data=(syms,cal,frames,{})
    records=[]; orders=[]; trips=[]; holdings=[]
    configs=[(m,False,None) for m in ['zero','commission','commission_vat','one_tick','two_ticks','unconstrained_cap','half_fills']]
    configs += [('positive_momentum',True,None),('rebalance_every_10',False,10)]
    for mode,positive,rebal in configs:
        for w in ev:
            r=_run_with_cost(w,data,cfg,'one_tick' if positive or rebal else mode,positive=positive,rebalance=rebal)
            s=dict(r[0]); s['experiment']=mode
            o=pd.DataFrame(r[3]); filled=o[o.filled>0] if not o.empty else o
            s['buy_notional']=float((filled.loc[filled.side=='buy','filled']*filled.loc[filled.side=='buy','price']).sum())
            s['sell_notional']=float((filled.loc[filled.side=='sell','filled']*filled.loc[filled.side=='sell','price']).sum())
            s['gross_trading_notional']=s['buy_notional']+s['sell_notional']
            s['total_explicit_cost']=s['commission_thb']+s['vat_thb']+s['slippage_thb']
            s['cost_pct_initial']=s['total_explicit_cost']/cfg['initial_cash']
            records.append(s)
            for x in r[3]: orders.append({**x,'experiment':mode})
            for x in r[4]: trips.append({**x,'experiment':mode})
            for x in r[2]: holdings.append({**x,'experiment':mode})
    df=pd.DataFrame(records); df.to_csv(out/'cost_windows.csv',index=False)
    pd.DataFrame(orders).to_csv(out/'scenario_orders.csv',index=False)
    pd.DataFrame(trips).to_csv(out/'scenario_roundtrips.csv',index=False)
    pd.DataFrame(holdings).to_csv(out/'scenario_holdings.csv',index=False)
    df.groupby('experiment').agg(windows=('window','size'),mean_excess=('excess_return','mean'),mean_net=('net_return','mean'),
      mean_turnover=('turnover','mean'),mean_commission=('commission_thb','mean'),mean_vat=('vat_thb','mean'),
      mean_slippage=('slippage_thb','mean'),mean_cost_pct=('cost_pct_initial','mean'),mean_roundtrips=('roundtrips','mean'),
      mean_exposure=('average_exposure','mean'),common_pass=('common_eligible','sum'),best_alpha_pass=('best_alpha_eligible','sum')).to_csv(out/'cost_summary.csv')
    return df


def saved_diagnostics(out: Path, saved: pd.DataFrame):
    ev=saved[(saved.role=='evaluation')&(saved.scenario=='official')&(saved.exit_rule=='scheduled')]
    flags=['drawdown_pass','roundtrip_pass','exposure_pass','payoff_pass','nonnegative_return','nonnegative_excess']
    ev[['window','strategy']+flags+['common_eligible','best_alpha_eligible','roundtrips','expected_payoff_thb','average_exposure','turnover','excess_return']].to_csv(out/'eligibility_windows.csv',index=False)
    ev.groupby('strategy')[flags].agg(lambda x:int((~x.astype(bool)).sum())).to_csv(out/'eligibility_failures.csv')
    orders=pd.read_csv(OLD/'orders.csv'); orders=orders[(orders.scenario=='official')&(orders.exit_rule=='scheduled')]
    targets=pd.read_csv(OLD/'targets.csv'); targets=targets[targets.strategy.isin(list('ABCDE'))]
    # Causes are based on actual filled orders and prior holdings, not just target changes.
    orders=orders[orders.strategy.isin(list('ABCDE'))].copy()
    orders['notional']=orders.filled*orders.open
    orders['cause']='scheduled_rebalance'
    orders.loc[(orders.side=='buy')&(orders.requested>0),'cause']='entry_or_addition'
    orders.loc[(orders.side=='sell')&(orders.requested>0),'cause']='exit_or_reduction'
    orders.groupby(['strategy','cause']).agg(filled_notional=('notional','sum'),filled_orders=('filled','count')).to_csv(out/'turnover_by_action.csv')
    trips=pd.read_csv(OLD/'fifo_roundtrips.csv'); trips=trips[(trips.scenario=='official')&(trips.exit_rule=='scheduled')]
    trips.groupby('strategy').agg(completed_lots=('pnl','size'),mean_pnl=('pnl','mean'),median_pnl=('pnl','median'),
      win_fraction=('pnl',lambda x:float((x>0).mean())),mean_calendar_days=('holding_sessions_proxy','mean')).to_csv(out/'fifo_diagnostics.csv')


def figures(out: Path, df: pd.DataFrame, price: pd.DataFrame):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    saved=pd.read_csv(OLD/'windows.csv')
    ev=saved[(saved.role=='evaluation')&(saved.scenario=='official')&(saved.exit_rule=='scheduled')&saved.strategy.isin(list('ABCDE'))]
    zero=saved[(saved.role=='evaluation')&(saved.scenario=='zero')&(saved.strategy=='A')]
    a=ev[ev.strategy=='A'].merge(zero[['window','excess_return']],on='window',suffixes=('_net','_zero'))
    plots=[('gross_vs_net_excess',lambda ax: ax.scatter(a.excess_return_zero,a.excess_return_net)),
           ('turnover_vs_net',lambda ax: ax.scatter(ev.turnover,ev.excess_return,c=ev.strategy.map(dict(zip('ABCDE',range(5)))))),
           ('cost_breakdown',lambda ax: ev.groupby('strategy')[['commission_thb','vat_thb','slippage_thb']].mean().plot.bar(stacked=True,ax=ax)),
           ('execution_sensitivity',lambda ax: df.groupby('experiment').excess_return.mean().sort_values().plot.bar(ax=ax)),
           ('trade_pnl',lambda ax: pd.read_csv(OLD/'fifo_roundtrips.csv').query("scenario == 'official' and exit_rule == 'scheduled'").pnl.hist(bins=40,ax=ax)),
           ('eligibility_failures',lambda ax: pd.read_csv(out/'eligibility_failures.csv',index_col=0).plot.bar(ax=ax)),
           ('daily_tick_difference',lambda ax: price.open_difference.hist(bins=40,ax=ax) if not price.empty else ax.text(.1,.5,'No overlap'))]
    for name,fun in plots:
        fig,ax=plt.subplots(figsize=(8,4)); fun(ax); ax.set_title(name.replace('_',' ')); fig.tight_layout(); fig.savefig(out/(name+'.png'),dpi=130); plt.close(fig)


def main():
    out=HERE/'results'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True,exist_ok=False)
    source={str(p.relative_to(ROOT)):sha256(p) for p in [ROOT/'research_set50_portfolio/core.py',ROOT/'research_set50_portfolio/runner.py',ROOT/'research_set50_portfolio/configs/preregistered.json']}
    (out/'manifest.json').write_text(json.dumps({'source_hashes':source,'phase3_saved':str(OLD),'command':'python -m research_set50_execution_validation.run'},indent=2))
    saved=phase3(out)
    price=prices(out)
    df=scenarios(out)
    saved_diagnostics(out,saved)
    figures(out,df,price)
    print(out)

if __name__=='__main__': main()
