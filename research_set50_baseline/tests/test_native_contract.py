"""Exercise real TradeSim order behavior in a task-local temporary directory."""
import os
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from research_set50_baseline.data import MARKET, PACKAGE
from tradeSim.TradeSim import tradeSim
from tradeSim.Order import order


class NativeContractTests(unittest.TestCase):
    def test_rejection_limit_cancel_and_native_full_fill(self):
        old=Path.cwd()
        with tempfile.TemporaryDirectory(dir=PACKAGE) as directory:
            try:
                os.chdir(directory)
                order._csv_loaded=False; order._set50_symbols=set()
                order.load_set50_symbols(str(MARKET/"symbolSET50/Symbol_SET50.csv"))
                sim=tradeSim("test",load_existing=False,current_date="2026-09-09")
                row=dict(ShareCode="AOT",TradeDateTime=pd.Timestamp("2026-09-09 10:05:00"),LastPrice=50.,Volume=100,Flag="Buy")
                rejected=sim.create_order_at_market(100,"Sell","AOT",10000,10000,row)
                self.assertIsInstance(rejected,ValueError)
                self.assertEqual(sim.portfolio.get_cash_balance(),10_000_000)
                sim.create_order_to_limit(100,40.,"Buy","AOT",10000,10000,row)
                sim.isMatch(row)
                resting=sim.get_open_orders()
                self.assertEqual(len(resting),1)
                self.assertEqual(sim.portfolio.get_total_stock_volume_by_symbol("AOT"),0)
                self.assertTrue(sim.cancel_order(resting[0]["Order Number"]))
                self.assertEqual(sim.get_open_orders(),[])
                # Native engine fills full 200 despite this tick having only 100.
                sim.create_order_at_market(200,"Buy","AOT",10000,10000,row)
                self.assertEqual(sim.portfolio.get_total_stock_volume_by_symbol("AOT"),200)
                fill=sim.execution.tranLog.transaction_log[-1]
                self.assertEqual(fill["Price"],50.25)
                expected=10_000_000-200*50.25*(1+.00157*1.07)
                self.assertAlmostEqual(sim.portfolio.get_cash_balance(),expected)
                sim.save_portfolio()
                fresh=tradeSim("fresh",load_existing=False,current_date="2026-09-09")
                self.assertEqual(fresh.portfolio.get_cash_balance(),10_000_000)
                self.assertEqual(fresh.get_open_orders(),[])
            finally:
                os.chdir(old)


if __name__=="__main__": unittest.main()
