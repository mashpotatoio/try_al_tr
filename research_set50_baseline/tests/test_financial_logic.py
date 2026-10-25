"""Small examples catch financial errors that a profitable chart would conceal."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research_set50_baseline.core import (
    Ledger, capped_weights, features, select_targets, feasible_buy, lots,
    tick_size, maximum_drawdown, fill_price, rsi_wilder)
from research_set50_baseline.data import config, MARKET, read_history
from research_set50_baseline.runner import ResearchState, daily_schedule
from research_set50_baseline.evaluation import evaluate, eligibility


class FinancialTests(unittest.TestCase):
    def setUp(self):
        self.c=config()

    def fixture(self):
        dates=pd.bdate_range("2024-01-01",periods=30)
        history={}
        for s,trend in [("AAA",1.01),("BBB",1.005),("SET50",1.002)]:
            p=100*trend**np.arange(30)
            history[s]=pd.DataFrame(dict(Open=p,High=p,Low=p,Close=p,Volume=10000,feature_valid=True),index=dates)
        return history,dates

    def test_no_future_and_first_signal(self):
        h,d=self.fixture()
        self.assertTrue(features(h,d,d[20],["AAA"],20).empty)
        expected=features(h,d,d[21],["AAA","BBB"],20)
        self.assertEqual(expected.feature_end.iloc[0],str(d[20].date()))
        for frame in h.values():
            frame.loc[d[21]:,"Close"]=999999
        pd.testing.assert_frame_equal(expected,features(h,d,d[21],["AAA","BBB"],20))

    def test_missing_history_no_backfill(self):
        h,d=self.fixture(); h["AAA"].loc[d[10],"Close"]=np.nan
        f=features(h,d,d[21],["AAA","BBB"],20)
        self.assertEqual(f.symbol.tolist(),["BBB"])

    def test_momentum_relative_control(self):
        h,d=self.fixture(); f=features(h,d,d[21],["AAA","BBB"],20)
        self.assertAlmostEqual(f.iloc[0].momentum,1.01**20-1)
        self.assertEqual(select_targets("momentum",f,self.c),select_targets("relative_equal",f,self.c))
        tied=f.copy(); tied["momentum"]=0
        self.assertEqual(select_targets("momentum",tied.iloc[::-1],self.c)[1],["AAA","BBB"])

    def test_rsi_wilder_and_oversold_selection(self):
        self.assertEqual(rsi_wilder(np.arange(15, dtype=float)), 100.0)
        self.assertEqual(rsi_wilder(np.arange(15, 0, -1, dtype=float)), 0.0)
        self.assertIsNone(rsi_wilder(np.ones(15)))
        table=pd.DataFrame([
            {"symbol":"ZED","rsi14":10.0,"volatility":.02,"momentum":.1,"relative_strength":.05},
            {"symbol":"AAA","rsi14":10.0,"volatility":.03,"momentum":.2,"relative_strength":.15},
            {"symbol":"MID","rsi14":29.9,"volatility":.01,"momentum":.3,"relative_strength":.25},
            {"symbol":"AT30","rsi14":30.0,"volatility":.02,"momentum":.4,"relative_strength":.35},
            {"symbol":"NONE","rsi14":np.nan,"volatility":.02,"momentum":.5,"relative_strength":.45},
        ])
        weights, selected=select_targets("rsi_oversold",table,dict(self.c,holdings=2))
        self.assertEqual(selected,["AAA","ZED"])  # lowest RSI first; alphabetical tie break.
        self.assertEqual(weights,{"AAA":.15,"ZED":.15})

    def test_inverse_weights_and_cap(self):
        w=capped_weights({"A":100,"B":50,"C":25},.98,.4)
        self.assertAlmostEqual(sum(w.values()),.98)
        self.assertLessEqual(max(w.values()),.4+1e-12)
        self.assertEqual(capped_weights({"A":1,"B":1},.98,.15),{"A":.15,"B":.15})

    def test_lots_fees_and_reservations(self):
        self.assertEqual(lots(199.99),100)
        q=feasible_buy(10000,100,10000,0,0,10000,1,self.c)
        self.assertEqual(q,0)  # 100 shares cost more than 10,000 after fees.
        l=Ledger(100000,self.c)
        l.reserve("a","AAA","Buy",500,100)
        self.assertGreater(l.reserved_cash(),50000)
        with self.assertRaises(ValueError): l.reserve("b","BBB","Buy",500,100)
        l.cancel("a"); self.assertEqual(l.cash,100000); self.assertEqual(l.quantities(),{})

    def test_partial_fills_and_fifo(self):
        l=Ledger(100000,self.c)
        l.reserve("a","AAA","Buy",200,101)
        l.fill("a","AAA","Buy",100,100,"t1",fill_id="a1")
        self.assertEqual(l.quantity("AAA"),100)
        self.assertGreater(l.reserved_cash(),0)
        self.assertFalse(l.fill("a","AAA","Buy",100,100,"t1",fill_id="a1"))
        l.fill("a","AAA","Buy",100,101,"t2",fill_id="a2")
        self.assertEqual(l.reserved_cash(),0)
        l.fill("s1","AAA","Sell",100,110,"t3")
        self.assertEqual(len(l.round_trips),0)
        l.fill("s2","AAA","Sell",100,112,"t4")
        self.assertEqual(len(l.round_trips),1)
        fee=self.c["commission"]*(1+self.c["vat"])
        self.assertAlmostEqual(l.round_trips[0]["realized_pnl"],22200*(1-fee)-20100*(1+fee))
        self.assertAlmostEqual(l.cash,100000+l.round_trips[0]["realized_pnl"])
        with self.assertRaises(AssertionError): l.fill("s3","AAA","Sell",100,100,"t5")

    def test_ioc_remainder_release_synthetic(self):
        l=Ledger(100000,self.c); l.reserve("a","AAA","Buy",300,100)
        l.fill("a","AAA","Buy",100,100,"t1",fill_id="a1")
        l.cancel("a")
        self.assertEqual(l.quantity("AAA"),100); self.assertEqual(l.reserved_cash(),0)

    def test_multiple_original_fifo_lots(self):
        l=Ledger(100000,self.c)
        l.fill("b1","AAA","Buy",100,100,"t1")
        l.fill("b2","AAA","Buy",200,101,"t2")
        l.fill("s","AAA","Sell",200,110,"t3")
        self.assertEqual(len(l.round_trips),1)
        self.assertEqual(l.quantity("AAA"),100)
        self.assertEqual(l.round_trips[0]["order_id"],"b1")

    def test_tick_boundaries(self):
        for p,t in [(1.99,.01),(2,.02),(5,.05),(10,.1),(25,.25),(100,.5),(200,1),(400,2)]:
            self.assertEqual(tick_size(p),t)
            self.assertAlmostEqual(fill_price(p,"Buy"),p+t)

    def test_undefined_and_strict_thresholds(self):
        l=Ledger(100000,self.c)
        e=[dict(date="2024-01-02",equity=100000,cash=100000,exposure=0,unfilled_target=0)]
        m=evaluate(e,l,[100,100],100000,[])
        self.assertIsNone(m["competition_calmar"]); self.assertIsNone(m["expected_payoff"])
        self.assertEqual(m["eligibility"][0]["status"],"fail") # 0 < 1.5*0 is false.
        missing=evaluate(e,l,[np.nan,100],100000,[])
        self.assertIsNone(missing["excess_return"])
        self.assertEqual(missing["eligibility"][0]["status"],"unverified")
        self.assertAlmostEqual(maximum_drawdown([100,120,90,110]),.25)
        m.update(max_drawdown=.15,benchmark_max_drawdown=.1)
        # Use binary-exact values for a strict equality boundary.
        m.update(max_drawdown=.375,benchmark_max_drawdown=.25)
        self.assertEqual(eligibility(m)[0]["status"],"fail")

    def test_fresh_state(self):
        h,d=self.fixture()
        a=ResearchState("momentum",self.c,h,d,["AAA"])
        b=ResearchState("momentum",self.c,h,d,["AAA"])
        a.ledger.fill("buy","AAA","Buy",100,100,"now")
        self.assertEqual(b.ledger.cash,10_000_000)
        self.assertEqual(b.ledger.quantities(),{})

    def test_original_history_api_cutoff(self):
        from tradeSim.HistoricalData import historical_data
        reader=historical_data(str(MARKET/"ticks"),str(MARKET/"daily_history"),str(MARKET/"intraday_history"))
        data=reader.get_ohlcv("ADVANC",pd.Timestamp("2026-09-09").date(),21)
        self.assertEqual(len(data),21)
        self.assertTrue(all(x["Date"]<"2026-09-09" for x in data))

    def test_schedule_is_frozen_nonoverlapping(self):
        _,_,calendar=read_history()
        schedule=daily_schedule(calendar,self.c)
        full=[p for p in schedule if len(p["days"])==20]
        self.assertEqual(len(full),35)
        self.assertEqual(len(set(d for p in full for d in p["days"])),700)
        self.assertEqual(full[11]["days"][0],"2024-09-18")

    def test_daily_orders_ignore_current_close_high_low_volume(self):
        from research_set50_baseline.runner import run_daily
        from research_set50_baseline.data import PACKAGE
        h,d=self.fixture(); day=str(d[21].date())
        with tempfile.TemporaryDirectory(dir=PACKAGE) as folder:
            a=Path(folder)/"a"; b=Path(folder)/"b"
            run_daily("momentum",self.c,[day],a,"test","test",(["AAA","BBB"],h,d))
            for s in ["AAA","BBB"]:
                h[s].loc[d[21],["Close","High","Low","Volume"]]=[900,1000,.01,999999999]
            run_daily("momentum",self.c,[day],b,"test","test",(["AAA","BBB"],h,d))
            pd.testing.assert_frame_equal(pd.read_csv(a/"orders.csv"),pd.read_csv(b/"orders.csv"))
            self.assertNotEqual(pd.read_csv(a/"equity.csv").equity.iloc[0],pd.read_csv(b/"equity.csv").equity.iloc[0])


if __name__=="__main__": unittest.main()
