import unittest
import numpy as np
import pandas as pd
from research_set50_portfolio.core import Account, eligibility, max_drawdown, rank, signals, tick, weights
from research_set50_portfolio.runner import run_window


class PortfolioTests(unittest.TestCase):
    def test_tick_and_costs_and_cash(self):
        self.assertEqual(tick(2), .02)
        a = Account(10000)
        d = pd.Timestamp("2024-01-02")
        a.trade(d,"ABC","buy",100,10,100, ticks=1)
        self.assertEqual(a.shares["ABC"],100)
        self.assertAlmostEqual(a.orders[-1]["price"],10.10)
        self.assertAlmostEqual(a.fees,1010*.00157)
        self.assertAlmostEqual(a.vat,a.fees*.07)
        self.assertAlmostEqual(a.equity({"ABC":10}),a.cash+1000)
        self.assertGreaterEqual(a.cash,0)
        a.trade(d,"ABC","sell",100,10,100,ticks=1)
        self.assertEqual(len(a.trips),1)
        self.assertLess(a.trips[0]["pnl"],0)

    def test_fifo_partial_lot(self):
        a = Account(100000)
        d = pd.Timestamp("2024-01-02")
        a.trade(d,"ABC","buy",200,10,200,ticks=0)
        a.trade(d+pd.Timedelta(days=1),"ABC","sell",100,11,100,ticks=0)
        self.assertEqual(len(a.trips),0)
        a.trade(d+pd.Timedelta(days=2),"ABC","sell",100,12,100,ticks=0)
        self.assertEqual(len(a.trips),1)
        self.assertEqual(a.trips[0]["shares"],200)
        self.assertAlmostEqual(a.trips[0]["pnl"],300-(2000+2300)*.00157*1.07)

    def test_rejected_and_partial_orders(self):
        a=Account(10000)
        d=pd.Timestamp("2024-01-02")
        a.trade(d,"ABC","buy",100,10,0)
        self.assertEqual(a.orders[-1]["status"],"no_fill")
        a.trade(d,"ABC","buy",100,float("nan"),100)
        self.assertEqual(a.orders[-1]["status"],"missing_open")
        a.trade(d,"ABC","buy",200,10,100,fill_fraction=.5)
        self.assertEqual(a.orders[-1]["accepted"],100)
        self.assertEqual(a.orders[-1]["filled"],0) # 50 shares cannot fill as a board lot
        self.assertEqual(a.shares["ABC"],0)
        with self.assertRaises(AssertionError):
            a.trade(d,"ABC","buy",150,10,200)

    def test_weights_and_rank(self):
        f = pd.DataFrame({"vol":[.01,.04,.02],"mom20":[.3,.2,.1],"reversal1":[0,.5,0]},index=list("ABC"))
        self.assertAlmostEqual(sum(weights(list("ABC"),f,"equal",.8,.4).values()),.8)
        self.assertLessEqual(max(weights(list("ABC"),f,"inverse_vol",.8,.4).values()),.4)
        self.assertEqual(rank(f,"mom20",True,.05)[0],"A")
        chain=pd.DataFrame({"mom20":[1,.96,.92,.88,0],"reversal1":[0,0,0,10,0]},index=list("ABCDE"))
        self.assertEqual(rank(chain,"mom20",True,.05)[0],"A")

    def test_eligibility_strict_and_drawdown(self):
        self.assertAlmostEqual(max_drawdown([100,120,90]),.25)
        self.assertFalse(eligibility(.15,.1,5,.5,1,0,0)["drawdown_pass"])
        self.assertFalse(eligibility(0,0,5,.5,1,0,0)["drawdown_pass"])
        self.assertTrue(eligibility(.149,.1,5,.5,1,0,0)["best_alpha_eligible"])

    def test_future_append_cannot_change_signal(self):
        dates = pd.bdate_range("2024-01-01", periods=85)
        p = np.arange(85,dtype=float)+10
        def frame(vals, ds):
            return pd.DataFrame({"Close":vals,"Volume":100000,"valid":True},index=ds)
        past = frame(p[:80],dates[:80]); future=frame(p,dates)
        x=signals({"ABC":past},["ABC"],dates[79])
        y=signals({"ABC":future},["ABC"],dates[79])
        pd.testing.assert_frame_equal(x,y)

    def test_window_boundaries_and_benchmark_alignment(self):
        dates=pd.bdate_range("2024-01-01",periods=85)
        def make(start):
            close=np.full(85,start,dtype=float)
            return pd.DataFrame({"Open":close,"Close":close,"Volume":1_000_000,"valid":True},index=dates)
        stock=make(10); index=make(100)
        index.loc[dates[80],"Close"]=110
        schedule={"days":[str(x.date()) for x in dates[61:81]],"period_id":"synthetic","role":"evaluation"}
        cfg={"initial_cash":10_000_000,"volatility_window":20,"rebalance_every":5,"holdings":1,
             "target_exposure":.8,"max_weight":.8,"participation_rate":.01,"commission":.00157,"vat":.07,"slippage_ticks":1,
             "primary":"mom20","tie_percentile_gap":.05,"threshold_weight":.03,"hysteresis_exit_rank":10}
        # Slight stock variation is needed for a finite volatility estimate.
        stock["Close"] += np.arange(85)*.001
        summary,daily,_,orders,_,_=run_window(schedule,"buy_hold",(["ABC"],dates,{"ABC":stock,"SET50":index},{}),cfg)
        self.assertEqual(len(daily),20)
        self.assertEqual(daily[0]["date"],str(dates[61].date()))
        self.assertEqual(daily[-1]["date"],str(dates[80].date()))
        self.assertAlmostEqual(summary["benchmark_return"],.1)
        self.assertTrue(all(o["date"]==str(dates[61].date()) for o in orders))
        with self.assertRaises(ValueError):
            run_window({**schedule,"days":schedule["days"][:-1]},"buy_hold",(["ABC"],dates,{"ABC":stock,"SET50":index},{}),cfg)

if __name__ == "__main__":
    unittest.main()
