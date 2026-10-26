"""Long-only ranking turnover proxy, deliberately separate from factor ICs."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from .data import MARKET


def tick_size(price: float) -> float:
    if not np.isfinite(price) or price <= 0: raise ValueError("Invalid raw execution price")
    return [0.01,0.02,0.05,0.10,0.25,0.50,1.0,2.0][np.searchsorted([2,5,10,25,100,200,400],price,side="right")]


def ranking_proxy(factors, daily, calendar, schedule, config):
    """Adjusted-open turnover/commission scenarios; no historical tick-sized fills."""
    rows=[]; details=[]
    opening=pd.DataFrame({s:daily[s].Open.where(daily[s].valid & (daily[s].Volume>0)) for s in factors[next(iter(factors))]},index=calendar)
    prior_volume=pd.DataFrame({s:daily[s].Volume.where(daily[s].valid).shift(1).rolling(20,min_periods=20).mean() for s in opening},index=calendar)
    fee=config["commission"]*(1+config["vat"])
    for period in schedule:
        if period["role"] not in {"development","evaluation"}: continue
        days=[pd.Timestamp(x) for x in period["days"]]
        for factor,frame in factors.items():
            for frequency in config["proxy_rebalance_sessions"]:
                previous=set(); changes=[]; turnovers=[]; commission=[]; capped_fraction=[]
                cash=float(config["proxy_initial_cash"]);held={};scenario_turnover=[];scenario_fees=[];scenario_cash=[];unfilled=[]
                for i in range(0,len(days),frequency):
                    entry=days[i]; pos=calendar.get_loc(entry)
                    if pos==0: continue
                    signal=calendar[pos-1]
                    eligible=frame.loc[signal].dropna()
                    eligible=eligible[opening.loc[entry,eligible.index].notna()]
                    if len(eligible)<config["proxy_top_n"]: continue
                    selected=set(eligible.sort_values(ascending=False,kind="stable").head(config["proxy_top_n"]).index)
                    overlap=len(selected&previous)/config["proxy_top_n"] if previous else np.nan
                    changed=len(selected^previous)
                    # One fifth of initial cash per name; only changed names incur turnover.
                    notional=0.; capped=0.; desired=0.
                    for symbol in selected^previous:
                        price=float(opening.loc[entry,symbol]); qty=int((config["proxy_initial_cash"]/config["proxy_top_n"]/price)//config["proxy_lot"])*config["proxy_lot"]
                        desired+=qty
                        cap=prior_volume.loc[entry,symbol]
                        allowed=int((cap*config["liquidity_cap_fraction_of_prior_20d_volume"])//config["proxy_lot"])*config["proxy_lot"] if np.isfinite(cap) else 0
                        capped+=min(qty,allowed)
                        notional+=qty*price
                    turnover=notional/config["proxy_initial_cash"]
                    changes.append(changed); turnovers.append(turnover); commission.append(notional*fee)
                    capped_fraction.append(capped/desired if desired else np.nan)
                    executed=0.;fees_paid=0.;unfilled_shares=0
                    # Adjusted-open scenario: sales precede purchases; caps use only prior 20-day volume.
                    for symbol in sorted(set(held)-selected):
                        qty=held[symbol];price=float(opening.loc[entry,symbol]) if np.isfinite(opening.loc[entry,symbol]) else np.nan
                        cap=prior_volume.loc[entry,symbol]
                        if not np.isfinite(price) or not np.isfinite(cap):unfilled_shares+=qty;continue
                        allowed=max(0,int(cap*config["liquidity_cap_fraction_of_prior_20d_volume"]//config["proxy_lot"])*config["proxy_lot"])
                        sold=min(qty,allowed);value=sold*price;charge=value*fee
                        cash+=value-charge;held[symbol]-=sold;executed+=value;fees_paid+=charge
                        unfilled_shares+=qty-sold
                        if held[symbol]==0:del held[symbol]
                    for symbol in sorted(selected):
                        price=float(opening.loc[entry,symbol]);cap=prior_volume.loc[entry,symbol]
                        target=int((config["proxy_initial_cash"]/config["proxy_top_n"]/price)//config["proxy_lot"])*config["proxy_lot"]
                        need=max(0,target-held.get(symbol,0))
                        allowed=max(0,int(cap*config["liquidity_cap_fraction_of_prior_20d_volume"]//config["proxy_lot"])*config["proxy_lot"]) if np.isfinite(cap) else 0
                        affordable=max(0,int(cash/(price*(1+fee))//config["proxy_lot"])*config["proxy_lot"])
                        bought=min(need,allowed,affordable);value=bought*price;charge=value*fee
                        cash-=value+charge;held[symbol]=held.get(symbol,0)+bought;executed+=value;fees_paid+=charge
                        unfilled_shares+=need-bought
                    scenario_turnover.append(executed/config["proxy_initial_cash"]);scenario_fees.append(fees_paid);scenario_cash.append(cash);unfilled.append(unfilled_shares)
                    details.append(dict(factor=factor,role=period["role"],period_id=period["period_id"],frequency=frequency,
                                        signal_date=signal,entry_date=entry,selected=";".join(sorted(selected)),
                                        prior_overlap=overlap,changed_names=changed,one_way_turnover=turnover,
                                        commission_vat_thb=notional*fee,liquidity_cap_share_fraction=capped_fraction[-1],
                                        scenario_turnover=scenario_turnover[-1],scenario_commission_vat_thb=fees_paid,
                                        scenario_cash_thb=cash,scenario_unfilled_shares=unfilled_shares,
                                        price_basis="adjusted_open_not_executable"))
                    previous=selected
                if turnovers:
                    rows.append(dict(factor=factor,role=period["role"],period_id=period["period_id"],frequency=frequency,
                                     rebalances=len(turnovers),mean_changed_names=float(np.mean(changes)),
                                     total_one_way_turnover=float(np.sum(turnovers)),
                                     commission_vat_thb=float(np.sum(commission)),
                                     mean_liquidity_cap_share_fraction=float(np.nanmean(capped_fraction)),
                                     scenario_total_turnover=float(np.sum(scenario_turnover)),
                                     scenario_commission_vat_thb=float(np.sum(scenario_fees)),
                                     scenario_final_cash_thb=float(cash),scenario_unfilled_shares=int(np.sum(unfilled))))
    return pd.DataFrame(rows),pd.DataFrame(details)


def raw_tick_cost_sample(factors, calendar, config):
    """Observed first-tick reference prices on 16 raw sessions; no fill assertion."""
    rows=[]; fee=config["commission"]*(1+config["vat"])
    files=sorted((MARKET/"ticks").glob("*.csv"))
    for path in files:
        entry=pd.Timestamp(path.stem)
        pos=calendar.get_indexer([entry])[0]
        if pos<=0: continue
        signal=calendar[pos-1]
        ticks=pd.read_csv(path,usecols=["ShareCode","TradeDateTime","LastPrice"])
        first=ticks.sort_values("TradeDateTime",kind="stable").drop_duplicates("ShareCode").set_index("ShareCode").LastPrice
        for name,frame in factors.items():
            ranks=frame.loc[signal].dropna()
            ranks=ranks[ranks.index.isin(first.index)]
            if len(ranks)<config["proxy_top_n"]: continue
            selected=ranks.sort_values(ascending=False,kind="stable").head(config["proxy_top_n"]).index
            for symbol in selected:
                price=float(first[symbol]); step=tick_size(price)
                rows.append(dict(factor=name,signal_date=signal,entry_date=entry,symbol=symbol,
                                 raw_first_tick_price=price,tick_size=step,
                                 hypothetical_buy_price=price+step,hypothetical_sell_price=price-step,
                                 roundtrip_commission_vat_fraction=2*fee,
                                 reference_roundtrip_tick_fraction=2*step/price,
                                 reference_total_roundtrip_fraction=2*fee+2*step/price,
                                 status="reference_only_no_book_or_fill"))
    return pd.DataFrame(rows)
