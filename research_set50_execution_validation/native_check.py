"""Isolated, reproducible native TradeSim order-path probe on a real tick."""
import json
from pathlib import Path
import pandas as pd
from tradeSim.TradeSim import tradeSim
from tradeSim.CommissionService import commissionService
from research_set50_factors.data import load_daily
from research_set50_portfolio.core import signals, rank, weights, Account


def run(out: Path):
    root=Path(__file__).resolve().parent.parent
    files=sorted((root/'marketInfo/ticks').glob('*.csv'))
    t=pd.read_csv(files[0],parse_dates=['TradeDateTime'])
    universe=set(pd.read_csv(root/'marketInfo/symbolSET50/Symbol_SET50.csv').Symbol)
    row=t[(t.ShareCode.isin(universe))&(t.LastPrice>0)].iloc[0].to_dict()
    sim=tradeSim('phase35_native_probe',load_existing=False,folder=str(out/'native_sandbox'),current_date=files[0].stem)
    symbol=row['ShareCode']; price=float(row['LastPrice'])
    rejected=sim.create_order_at_market(100,'Buy','SET50',0,1000,row)
    before=sim.portfolio.get_cash_balance()
    accepted=sim.create_order_at_market(100,'Buy',symbol,1000,1000,row)
    after=sim.portfolio.get_cash_balance()
    expected=100*commissionService.market_fill_price(price,'Buy')*(1+commissionService.comm*(1+commissionService.vat))
    result={'tick_session':files[0].stem,'tick_symbol':symbol,'tick_price':price,
            'index_order_response':str(rejected),'market_order_response':str(accepted),
            'cash_before':before,'cash_after':after,'cash_debit':before-after,
            'expected_cash_debit':expected,'cash_delta_error':(before-after)-expected,
            'roundtrips':sim.portfolio.get_number_of_sells(),
            'scope':'single native order on real tick, not 20-session or official IOC validation'}
    (out/'native_probe.json').write_text(json.dumps(result,indent=2,default=str))
    return result


def run_strategy(out: Path):
    """Replay frozen A decisions across available ticks; report 16-session native path."""
    root=Path(__file__).resolve().parent.parent
    files=sorted((root/'marketInfo/ticks').glob('*.csv'))
    syms,cal,frames,_=load_daily()
    sim=tradeSim('phase35_native_A',load_existing=False,folder=str(out/'native_strategy_sandbox'),current_date=files[0].stem)
    research=Account()
    daily=[]; orders=[]; target_rows=[]
    for i,path in enumerate(files):
        day=pd.Timestamp(path.stem); prior=cal[cal.get_loc(day)-1]
        intent={}
        if i%5==0:
            sig=signals(frames,syms,prior)
            selected=rank(sig)[:6]
            target=weights(selected,sig,'equal',.8,.2)
            target_rows.append({'date':path.stem,'names':selected,'target':target})
            rnav=research.cash+sum(q*float(frames[s].loc[prior,'Close']) for s,q in research.shares.items() if q)
            research_intents=[]
            for sym in set(selected)|{s for s,q in research.shares.items() if q}:
                prior_close=float(frames[sym].loc[prior,'Close'])
                desired=int(rnav*target.get(sym,0)/prior_close//100)*100
                change=desired-research.shares[sym]
                if change:
                    research_intents.append((sym,'sell' if change<0 else 'buy',abs(change)))
            for sym,side,qty in sorted(research_intents,key=lambda x:x[1]!='sell'):
                cap=int(float(sig.loc[sym,'prior_volume'])*.01) if sym in sig.index else 0
                research.trade(day,sym,side,qty,float(frames[sym].loc[day,'Open']),cap)
            held={s:sim.portfolio.get_total_stock_volume_by_symbol(s) for s in syms}
            nav=sim.portfolio.get_cash_balance()+sum(q*float(frames[s].loc[prior,'Close']) for s,q in held.items() if q)
            for sym in set(selected)|{s for s,q in held.items() if q}:
                prior_close=float(frames[sym].loc[prior,'Close'])
                desired=int(nav*target.get(sym,0)/prior_close//100)*100
                delta=desired-held[sym]
                if delta:
                    cap=int(float(sig.loc[sym,'prior_volume'])*.01//100)*100 if sym in sig.index else 0
                    qty=min(abs(delta),cap)
                    if qty>0: intent[sym]=('Buy' if delta>0 else 'Sell',qty)
        if intent:
            t=pd.read_csv(path,parse_dates=['TradeDateTime'])
            t=t[t.ShareCode.isin(intent)].sort_values('TradeDateTime',kind='stable')
            cum={s:{'Buy':0,'Sell':0} for s in intent}
            done=set()
            for r in t.itertuples(index=False):
                sym=r.ShareCode
                if r.Flag in ('Buy','Sell'): cum[sym][r.Flag]+=int(r.Volume)
                if sym in done: continue
                side,qty=intent[sym]
                opposite='Sell' if side=='Buy' else 'Buy'
                if cum[sym][opposite]<qty: continue
                row={'ShareCode':sym,'TradeDateTime':r.TradeDateTime,'LastPrice':float(r.LastPrice),'Volume':int(r.Volume),'Flag':r.Flag}
                before_cash=sim.portfolio.get_cash_balance(); before_shares=sim.portfolio.get_total_stock_volume_by_symbol(sym)
                response=sim.create_order_at_market(qty,side,sym,cum[sym]['Sell'],cum[sym]['Buy'],row)
                after_shares=sim.portfolio.get_total_stock_volume_by_symbol(sym)
                orders.append({'date':path.stem,'time':str(r.TradeDateTime),'symbol':sym,'side':side,'requested':qty,
                               'filled':abs(after_shares-before_shares),'last_price':float(r.LastPrice),
                               'cash_change':sim.portfolio.get_cash_balance()-before_cash,'response':str(response)})
                done.add(sym)
            for sym,(side,qty) in intent.items():
                if sym not in done:
                    orders.append({'date':path.stem,'symbol':sym,'side':side,'requested':qty,'filled':0,'response':'opposing_tick_volume_unavailable'})
        sim.portfolio.update_market_prices({s:float(frames[s].loc[day,'Close']) for s in syms if pd.notna(frames[s].loc[day,'Close'])})
        nav=sim.portfolio.get_nav()
        research_marks={s:float(frames[s].loc[day,'Close']) for s,q in research.shares.items() if q}
        research_nav=research.equity(research_marks)
        daily.append({'date':path.stem,'nav':nav,'cash':sim.portfolio.get_cash_balance(),
                      'daily_model_nav':research_nav,'nav_difference':nav-research_nav,
                      'holdings':sum(sim.portfolio.get_total_stock_volume_by_symbol(s)>0 for s in syms),
                      'roundtrips':sim.portfolio.get_number_of_sells()})
    pd.DataFrame(orders).to_csv(out/'native_strategy_orders.csv',index=False)
    pd.DataFrame(daily).to_csv(out/'native_strategy_daily.csv',index=False)
    (out/'native_strategy_targets.json').write_text(json.dumps(target_rows,indent=2,default=str))
    result={'sessions':len(files),'rebalance_sessions':len(target_rows),'attempted_orders':len(orders),
            'filled_orders':sum(x['filled']>0 for x in orders),'ending_nav':daily[-1]['nav'],
            'daily_model_ending_nav':daily[-1]['daily_model_nav'],
            'ending_nav_difference':daily[-1]['nav_difference'],
            'ending_cash':daily[-1]['cash'],'completed_fifo_lots':daily[-1]['roundtrips'],
            'daily_model_completed_fifo_lots':len(research.trips),
            'scope':'16-session native practice replay using frozen A signals and real tick volume; not official IOC or full competition window'}
    (out/'native_strategy_summary.json').write_text(json.dumps(result,indent=2,default=str))
    return result

if __name__=='__main__':
    import sys
    output=Path(sys.argv[1]); run(output)
    print(json.dumps(run_strategy(output),indent=2,default=str))
