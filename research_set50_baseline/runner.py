"""Common portfolio decisions with native TradeSim and daily-open adapters."""
from datetime import datetime
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .core import Ledger, features, select_targets, lots, feasible_buy, fill_price
from .data import ROOT, MARKET, read_history, ticks, write_json
from .evaluation import evaluate, save_run


class ResearchState:
    """Own one experiment's decisions; never share mutable state across portfolios."""
    def __init__(self, strategy, config, history, calendar, universe):
        self.strategy, self.config = strategy, config
        self.history, self.calendar, self.universe = history, calendar, universe
        self.ledger=Ledger(config["initial_cash"],config)
        self.marks={}
        self.targets={}
        self.weights={}
        self.signals=[]; self.target_log=[]; self.orders=[]; self.equity=[]; self.holdings=[]
        self.attempts={}; self.accepted=set()
        self.signal_active=False

    def start_day(self, day, day_number):
        """Prior-close data only; target quantities stay fixed for the decision day."""
        self.day=day
        c=self.config
        self.signal_active=(day_number==0 or (self.strategy!="buy_hold" and day_number%c["rebalance_sessions"]==0))
        self.attempts={}; self.accepted=set()
        if not self.signal_active:
            return
        f=features(self.history,self.calendar,day,self.universe,c["lookback"])
        if not f.empty:
            for row in f.to_dict("records"):
                self.signals.append(dict(date=day,decision_time=day+" 09:30:00+07:00",**row))
        self.weights, _=select_targets(self.strategy,f,c)
        # An empty target set means cash, including exiting previously held names.
        previous=self.calendar[self.calendar < pd.Timestamp(day)]
        if len(previous):
            for s in self.universe:
                d=self.history[s]
                if previous[-1] in d.index and d.loc[previous[-1],"feature_valid"]:
                    self.marks[s]=float(d.loc[previous[-1],"Close"])
        nav=self.ledger.equity(self.marks)
        self.targets={s:lots(nav*w/self.marks[s],c["lot_size"]) for s,w in self.weights.items()}
        for s in sorted(set(self.targets)|set(self.ledger.quantities())):
            self.target_log.append(dict(date=day,symbol=s,weight=self.weights.get(s,0),
                quantity=self.targets.get(s,0),reference_price=self.marks.get(s),reference_equity=nav,
                decision_time=day+" 09:30:00+07:00"))

    def wanted(self,symbol,side,price):
        """Convert frozen targets into current cash/position-feasible quantities."""
        held=self.ledger.quantity(symbol)
        delta=self.targets.get(symbol,0)-held
        if side=="Sell":
            return lots(min(held,max(0,-delta)),self.config["lot_size"])
        cap=1.0 if self.strategy=="buy_hold" else self.config["max_weight"]
        return feasible_buy(max(0,delta),price,self.ledger.cash,self.ledger.reserved_cash(),held,
                            self.ledger.equity(self.marks),cap,self.config)

    def close_day(self,day,seen):
        """Mark to last observed price; stale held symbols are explicitly listed."""
        nav=self.ledger.equity(self.marks)
        cash=self.ledger.cash
        if cash < -1e-5 or nav<=0:
            raise AssertionError("Cash/equity invariant failed")
        quantities=self.ledger.quantities()
        unfilled=sum(max(0,self.targets.get(s,0)-quantities.get(s,0))*self.marks[s] for s in self.targets)
        residual_sells=sum(max(0,n-self.targets.get(s,0))*self.marks[s] for s,n in quantities.items())
        self.equity.append(dict(date=day,equity=nav,cash=cash,invested=nav-cash,exposure=(nav-cash)/nav,
            unfilled_target=unfilled,residual_sell_notional=residual_sells,
            stale_symbols=";".join(sorted(set(quantities)-set(seen)))))
        self.holdings.extend(dict(date=day,symbol=s,quantity=n,mark=self.marks[s],
                                  stale=s not in seen) for s,n in quantities.items())


def benchmark_series(history,calendar,days):
    """Use the preceding session as research anchor; require each measured close."""
    earlier=calendar[calendar<pd.Timestamp(days[0])]
    anchor=earlier[-1] if len(earlier) else pd.NaT
    dates=[anchor,*pd.to_datetime(days)]
    return history["SET50"].Close.reindex(dates).to_numpy(dtype=float)


def finish(state,path,days,mode,period_id,role,engine=None):
    bm=benchmark_series(state.history,state.calendar,days)
    for i,row in enumerate(state.equity):
        row["benchmark_equity"]=float(bm[i+1]) if np.isfinite(bm[i+1]) else None
        row["benchmark_anchor"]=float(bm[0]) if np.isfinite(bm[0]) else None
    m=evaluate(state.equity,state.ledger,bm,state.config["initial_cash"],state.orders,engine)
    m.update(strategy=state.strategy,mode=mode,period_id=period_id,period_role=role,
             execution_compliant=False,official_eligibility="unverified",
             limitations=["current permitted universe; survivorship bias", "adjusted history has no point-in-time vintage",
                          "native Market is not IOC; no native partial fills" if mode=="native" else
                          "adjusted daily-open fills assume liquidity; historical lot/tick economics approximate",
                          "no dividends or corporate-action ledger", "organizer validation and full rulebook unavailable"])
    save_run(path,state.ledger,state.equity,state.orders,state.signals,state.target_log,m,state.holdings)
    write_json(Path(path)/"config.json",dict(**state.config,strategy=state.strategy,days=days,mode=mode))
    (Path(path)/"run.log").write_text(
        f"Completed {mode}: {state.strategy}, {days[0]} to {days[-1]}, {len(days)} sessions.\n"
        f"Confirmed fills: {len(state.ledger.fills)}; final equity: {m['final_equity']:.8f}.\n"
        "Fill ledger checked for cash, share, and lot invariants. Original inputs unchanged by this runner.\n"
        "Official eligibility unverified; see metrics.json limitations and definitions.\n",encoding="utf-8")
    return m


def run_daily(strategy,c,days,path,period_id,role,loaded=None):
    """Decision at prior close -> next open, then EOD valuation.

    All sell fills precede buy fills under an explicit opening-liquidity model.
    Current-day volume, high, low, and close never size or authorize an order.
    """
    universe,history,calendar=loaded or read_history()
    state=ResearchState(strategy,c,history,calendar,universe)
    for number,day in enumerate(days):
        state.start_day(day,number)
        date=pd.Timestamp(day)
        opens={s:float(h.loc[date,"Open"]) for s,h in history.items()
               if s!="SET50" and date in h.index and np.isfinite(h.loc[date,"Open"]) and h.loc[date,"Open"]>0}
        if state.signal_active:
            # Full opening snapshot is an explicitly simultaneous auction assumption.
            state.marks.update(opens)
            for side in ["Sell","Buy"]:
                for s in sorted(set(state.targets)|set(state.ledger.quantities())):
                    if s not in opens:
                        continue
                    price=fill_price(opens[s],side)
                    quantity=state.wanted(s,side,price)
                    if not quantity:
                        continue
                    order_id=f"{day}-{len(state.orders)+1:06d}"
                    timestamp=day+" 10:00:00+07:00"
                    state.ledger.reserve(order_id,s,side,quantity,price)
                    state.ledger.fill(order_id,s,side,quantity,price,timestamp,opens[s])
                    state.orders.append(dict(order_id=order_id,symbol=s,side=side,quantity=quantity,
                        timestamp=timestamp,status="filled",reason="assumed daily-open liquidity",price=price))
        seen=[]
        for s in universe:
            h=history[s]
            if date in h.index and np.isfinite(h.loc[date,"Close"]) and h.loc[date,"Close"]>0:
                state.marks[s]=float(h.loc[date,"Close"]); seen.append(s)
        state.close_day(day,seen)
    return finish(state,path,days,"daily",period_id,role)


def run_native(strategy,c,days,path,period_id,role):
    """Run original TradeSim classes in an isolated process/cwd and reconcile fills.

    No engine source patches. A shared coordinator supplies targets to separate
    per-symbol StrategyHandlers, as required by BarAggregator's one-symbol state.
    Market-price updates are batched before orders and EOD; the coordinator keeps
    every observed mark, so no future symbol prices enter cash/cap calculations.
    """
    from tradeSim.TradeSim import tradeSim
    from tradeSim.HistoricalData import historical_data
    from tradeSim.StrategyHandler import StrategyHandler
    from tradeSim.Benchmark import benchmark
    from tradeSim.Order import order
    from strategy.Strategies_template import Strategy_template

    path=Path(path).resolve(); path.mkdir(parents=True,exist_ok=False)
    os.chdir(path)
    universe,history,calendar=read_history()
    state=ResearchState(strategy,c,history,calendar,universe)
    order._order_counter=1
    order._csv_loaded=False; order._set50_symbols=set()
    order.load_set50_symbols(str(MARKET/"symbolSET50/Symbol_SET50.csv"))
    bm=benchmark(str(MARKET/"benchmark"))
    sim=None

    class NativeStrategy(Strategy_template):
        """Research-only callback adapter; not an organizer submission artifact."""
        def __init__(self,handler):
            super().__init__("research",strategy,handler,"1min")

        def on_data(self,bar):
            if not state.signal_active:
                return
            s=bar["ShareCode"]
            ts=pd.Timestamp(bar["Timestamp"])
            time=ts.strftime("%H:%M")
            if time<c["sell_time"] or time>=c["stop_time"] or s in state.accepted:
                return
            row=self.handler._current_row
            if row["Flag"] not in ("Buy","Sell"):
                return
            held=state.ledger.quantity(s)
            side="Sell" if held>state.targets.get(s,0) else "Buy"
            if side=="Buy" and time<c["buy_time"]:
                return
            if s in state.attempts and (ts-state.attempts[s]).total_seconds()<c["retry_minutes"]*60:
                return
            market=float(row["LastPrice"])
            price=fill_price(market,side)
            quantity=state.wanted(s,side,price)
            if not quantity:
                return
            state.attempts[s]=ts
            sim.update_market_prices(state.marks)
            before=len(sim.execution.tranLog.transaction_log)
            result=self.handler.create_order_at_market(quantity,side,s)
            confirmed=sim.execution.tranLog.transaction_log[before:]
            timestamp=str(pd.Timestamp(row["TradeDateTime"]).tz_localize("Asia/Bangkok"))
            status="filled" if confirmed else "rejected"
            oid=confirmed[0]["Order Number"] if confirmed else f"rejected-{len(state.orders)+1}"
            state.orders.append(dict(order_id=oid,symbol=s,side=side,quantity=quantity,
                timestamp=timestamp,status=status,reason=str(result),price=price))
            if confirmed:
                state.accepted.add(s)
                for f in confirmed:
                    state.ledger.fill(f["Order Number"],f["Symbol"],f["Side"],f["Volume"],f["Price"],
                                      timestamp,f["Market Price"])
                sim.update_market_prices(state.marks)
                reconcile(sim,state)

    engine_daily=[]
    for number,day in enumerate(days):
        state.start_day(day,number)
        sim=tradeSim("research",load_existing=number>0,current_date=day)
        sim._historical_data_reader=historical_data(str(MARKET/"ticks"),str(MARKET/"daily_history"),str(MARKET/"intraday_history"))
        sim.update_market_prices(state.marks)
        handlers={s:StrategyHandler(NativeStrategy,sim.get_strategy_runner()) for s in universe}
        d=ticks(day)
        seen=set()
        # Process callbacks through the final possible action minute. Afterwards
        # there are no pending orders or possible signals; only marks can change.
        active_end=pd.Timestamp(day+" "+c["stop_time"])
        for row in d.itertuples(index=False,name=None):
            s,ts,price,volume,value,flag=row
            if s not in handlers:
                continue
            state.marks[s]=float(price); seen.add(s)
            if state.signal_active and ts<active_end:
                handlers[s].process_row(dict(ShareCode=s,TradeDateTime=ts,LastPrice=price,Volume=volume,Value=value,Flag=flag))
        if sim.get_open_orders():
            raise AssertionError("Unexpected resting native order")
        sim.update_market_prices(state.marks)
        reconcile(sim,state)
        state.close_day(day,seen)
        sim.portfolio.finalize_day(pd.Timestamp(day))
        closes=bm._load_daily_closes(day,start_date=days[0])
        complete=[x[0] for x in closes]==days[:number+1]
        br=bm.get_benchmark_return(day,start_date=days[0]) if complete else None
        bd=bm.get_benchmark_max_dd(day,start_date=days[0]) if complete else None
        sim.portfolio.save_summary_csv(pd.Timestamp(day),br,bd)
        sim.save_portfolio()
        sim.flushTransactionLog(); sim.flushErrorLogger()
        raw=sim.portfolio.get_portfolio_info()
        engine_daily.append(dict(date=day,**raw))
        print(f"{strategy} {day}: equity={state.equity[-1]['equity']:.2f}, fills={len(state.ledger.fills)}",flush=True)
    pd.DataFrame(engine_daily).to_csv(path/"engine_daily_metrics.csv",index=False)
    engine=engine_daily[-1]
    if len(sim.portfolio.round_trips)!=len(state.ledger.round_trips):
        raise AssertionError("FIFO round-trip count differs from engine")
    for native, independent in zip(sim.portfolio.round_trips,state.ledger.round_trips):
        if abs(native["realized_pnl"]-independent["realized_pnl"])>1e-5:
            raise AssertionError("FIFO P&L differs from engine")
    return finish(state,path,days,"native",period_id,role,engine)


def reconcile(sim,state):
    """Fail loudly if real holdings, cash, or marked equity diverge from fills."""
    actual={s:sim.portfolio.get_total_stock_volume_by_symbol(s) for s in state.universe}
    actual={s:n for s,n in actual.items() if n}
    if actual!=state.ledger.quantities():
        raise AssertionError(f"Holding mismatch: {actual} != {state.ledger.quantities()}")
    if abs(sim.portfolio.get_cash_balance()-state.ledger.cash)>1e-5:
        raise AssertionError("Cash accounting mismatch")
    if abs(sim.portfolio.get_nav()-state.ledger.equity(state.marks))>1e-4:
        raise AssertionError("Equity accounting mismatch")
    if any(n<0 or n%100 for n in actual.values()):
        raise AssertionError("Short or fractional lot")


def daily_schedule(calendar,c):
    """Freeze chronological blocks before seeing strategy performance."""
    dates=[x.strftime("%Y-%m-%d") for x in calendar]
    start=c["lookback"]+1; width=c["window_sessions"]
    result=[]
    for i,offset in enumerate(range(start,len(dates),width)):
        block=dates[offset:offset+width]
        role=("incomplete_tail" if len(block)<width else
              "development" if i<c["development_windows"] else "evaluation")
        result.append(dict(period_id=f"window_{i+1:02d}",role=role,days=block))
    return result
