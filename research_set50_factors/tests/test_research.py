import unittest
import numpy as np
import pandas as pd
from research_set50_factors.data import load_daily, verify_phase1_manifest
from research_set50_factors.factors import make_factors, wilder_rsi
from research_set50_factors.labels import make_labels
from research_set50_factors.evaluation import assign_quantiles, hac_mean, bh_fdr, evaluate, role_for_date
from research_set50_factors.proxy import tick_size, ranking_proxy
from research_set50_factors.runner import CONFIG
import json


class FactorResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.symbols,cls.calendar,cls.daily,cls.audit=load_daily()
        cls.factors,cls.regimes,cls.benchmark=make_factors(cls.symbols,cls.calendar,cls.daily)

    def test_phase1_preserved(self):
        self.assertEqual(verify_phase1_manifest()["changed"],[])

    def test_momentum_and_relative_rank(self):
        d=self.calendar[100]
        m=self.factors["mom_5"].loc[d].dropna()
        s=m.index[0]
        close=self.daily[s].Close
        self.assertAlmostEqual(m[s],close.loc[d]/close.loc[self.calendar[95]]-1)
        rel=self.factors["relative_5"].loc[d].dropna()
        self.assertEqual(m.sort_values().index.tolist(),rel.sort_values().index.tolist())
        benchmark=self.daily["SET50"].Close
        bm=benchmark.loc[d]/benchmark.loc[self.calendar[95]]-1
        self.assertAlmostEqual(rel[s],m[s]-bm)

    def test_later_prices_do_not_change_earlier_factor(self):
        date=self.calendar[130]; before=self.factors["mom_20"].loc[date].copy()
        symbol=self.symbols[0]; original=self.daily[symbol].copy()
        original.loc[self.calendar[131]:,"Close"]*=10
        altered=dict(self.daily);altered[symbol]=original
        after=make_factors(self.symbols,self.calendar,altered)[0]["mom_20"].loc[date]
        pd.testing.assert_series_equal(before,after)

    def test_labels_are_future_open_to_open(self):
        labels,bench,_=make_labels(self.symbols,self.calendar,self.daily,[1,5])
        d=self.calendar[100];symbol=self.symbols[0]
        self.assertAlmostEqual(labels[5].loc[d,symbol],self.daily[symbol].Open.loc[self.calendar[106]]/self.daily[symbol].Open.loc[self.calendar[101]]-1)
        self.assertAlmostEqual(bench[1].loc[d],self.daily["SET50"].Open.loc[self.calendar[102]]/self.daily["SET50"].Open.loc[self.calendar[101]]-1)
        self.assertTrue(labels[5].iloc[-6:].isna().all().all())

    def test_missing_middle_open_invalidates_label(self):
        symbol=self.symbols[0];altered=dict(self.daily);d=self.daily[symbol].copy();d.loc[self.calendar[103],"Open"]=np.nan;altered[symbol]=d
        labels,_,_=make_labels(self.symbols,self.calendar,altered,[5])
        self.assertTrue(np.isnan(labels[5].loc[self.calendar[100],symbol]))

    def test_rsi_and_volatility_and_volume(self):
        c=pd.DataFrame({"X":[float(x) for x in range(1,20)]})
        self.assertAlmostEqual(wilder_rsi(c).X.iloc[-1],100)
        d=self.calendar[100];symbol=self.symbols[0]
        vol=self.daily[symbol].Volume
        expected=vol.loc[d]/vol.loc[self.calendar[80:100]].mean()
        self.assertAlmostEqual(self.factors["volume_surprise"].loc[d,symbol],expected)
        rets=self.daily[symbol].Close.pct_change(fill_method=None)
        self.assertAlmostEqual(self.factors["low_vol_10"].loc[d,symbol],-rets.loc[self.calendar[91:101]].std(ddof=1))

    def test_trend_and_short_history(self):
        d=self.calendar[100];symbol=self.symbols[0];close=self.daily[symbol].Close
        sma20=close.loc[self.calendar[81:101]].mean();sma60=close.loc[self.calendar[41:101]].mean()
        self.assertAlmostEqual(self.factors["above_sma20"].loc[d,symbol],close.loc[d]/sma20-1)
        self.assertAlmostEqual(self.factors["sma20_above_sma60"].loc[d,symbol],sma20/sma60-1)
        self.assertTrue(np.isnan(self.factors["mom_20"].loc[self.calendar[100],"BANPU"]))
        self.assertTrue(np.isnan(wilder_rsi(pd.DataFrame({"X":range(10)})).X.iloc[-1]))

    def test_ties_and_small_quantiles(self):
        self.assertEqual(assign_quantiles(pd.Series(range(14)))[1],"insufficient_stocks")
        group,state=assign_quantiles(pd.Series([1]*15))
        self.assertEqual(state,"collapsed_by_ties")
        self.assertEqual(group.nunique(),1)
        group,state=assign_quantiles(pd.Series(range(30)))
        self.assertEqual((state,group.nunique()),("ok",5))

    def test_statistics_and_tick_boundaries(self):
        self.assertAlmostEqual(hac_mean([1,2,3],0)["mean"],2)
        self.assertLessEqual(bh_fdr([.001,.02,.9])[0],.0031)
        self.assertEqual(tick_size(2),.02)
        self.assertEqual(tick_size(25),.25)

    def test_ic_and_constant_cross_section(self):
        dates=pd.date_range("2024-01-01",periods=3,freq="B");names=[f"S{i:02}" for i in range(15)]
        values=pd.DataFrame([range(15)]*3,index=dates,columns=names,dtype=float)
        constant=pd.DataFrame(1.,index=dates,columns=names)
        bench={1:pd.Series(0.,index=dates)}
        cfg=json.loads(CONFIG.read_text());cfg["development_first_signal"]="2024-01-01";cfg["development_last_signal"]="2024-01-31"
        ic,summary,quant,_,status=evaluate({"perfect":values,"constant":constant},{1:values},bench,cfg,{"development"})
        self.assertTrue(np.allclose(ic[ic.factor=="perfect"].ic,1))
        self.assertTrue(np.allclose(ic[ic.factor=="perfect"].rank_ic,1))
        self.assertEqual(len(ic[ic.factor=="constant"]),0)
        self.assertEqual(len(quant[quant.factor=="perfect"].groupby("date")),3)
        self.assertEqual(set(status[status.factor=="constant"].status),{"constant_cross_section"})

    def test_split_boundaries_and_hac_dependence(self):
        cfg=json.loads(CONFIG.read_text())
        self.assertEqual(role_for_date(pd.Timestamp("2023-10-23"),cfg),"warmup")
        self.assertEqual(role_for_date(pd.Timestamp("2023-10-24"),cfg),"development")
        self.assertEqual(role_for_date(pd.Timestamp("2024-09-18"),cfg),"evaluation")
        self.assertEqual(role_for_date(pd.Timestamp("2026-09-14"),cfg),"tail")
        x=[1,1,1,-1,-1,-1]
        self.assertGreater(hac_mean(x,1)["se"],hac_mean(x,0)["se"])

    def test_cash_limited_proxy_does_not_invent_fills(self):
        dates=pd.date_range("2024-01-01",periods=23,freq="B")
        frame=pd.DataFrame({"S":1.},index=dates)
        daily={"S":pd.DataFrame({"Open":10.,"Volume":100.,"valid":True},index=dates)}
        cfg=json.loads(CONFIG.read_text());cfg["proxy_top_n"]=1
        schedule=[{"period_id":"test","role":"development","days":[str(d.date()) for d in dates[21:22]]}]
        summary,detail=ranking_proxy({"signal":frame},daily,dates,schedule,cfg)
        self.assertEqual(summary.scenario_total_turnover.iloc[0],0)
        self.assertEqual(summary.scenario_final_cash_thb.iloc[0],cfg["proxy_initial_cash"])
        self.assertGreater(detail.scenario_unfilled_shares.iloc[0],0)


if __name__=="__main__":unittest.main()
