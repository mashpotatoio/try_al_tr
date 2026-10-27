import unittest
import pandas as pd
from research_set50_portfolio.core import Account, eligibility, max_drawdown, signals, tick
from tradeSim.CommissionService import commissionService


class AccountingTests(unittest.TestCase):
    def test_tick_ladder_matches_native(self):
        for p in [1.99,2,4.99,5,9.99,10,24.99,25,99.99,100,199.99,200,399.99,400]:
            self.assertEqual(tick(p),commissionService._get_slippage(p))

    def test_fees_lots_cash_and_fifo(self):
        a=Account(100000)
        d=pd.Timestamp('2026-09-09')
        a.trade(d,'AOT','buy',100,50,100,commission=.00157,vat_rate=.07,ticks=1)
        self.assertEqual(a.shares['AOT'],100)
        self.assertAlmostEqual(a.vat,a.fees*.07)
        self.assertAlmostEqual(a.cash,100000-100*(50+tick(50))-a.fees-a.vat)
        a.trade(d+pd.Timedelta(days=1),'AOT','sell',100,51,100,commission=.00157,vat_rate=.07,ticks=1)
        self.assertEqual(len(a.trips),1)
        self.assertEqual(a.shares['AOT'],0)
        self.assertGreater(a.trips[0]['pnl'],0)

    def test_drawdown_and_eligibility(self):
        self.assertAlmostEqual(max_drawdown([100,110,99]),.1)
        x=eligibility(.1,.1,5,.5,1,.01,.01)
        self.assertTrue(x['best_alpha_eligible'])
        self.assertFalse(eligibility(.15,.1,5,.5,1,.01,.01)['drawdown_pass'])

    def test_no_lookahead(self):
        ix=pd.bdate_range('2026-01-01',periods=65)
        f=pd.DataFrame({'Close':[10.]*65,'Volume':[1000.]*65,'valid':[True]*65},index=ix)
        before=signals({'X':f},['X'],ix[-2]); f.loc[ix[-1],'Close']=1000
        after=signals({'X':f},['X'],ix[-2])
        pd.testing.assert_frame_equal(before,after)


if __name__=='__main__': unittest.main()
