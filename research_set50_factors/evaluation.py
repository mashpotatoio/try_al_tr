"""Cross-sectional factor diagnostics; no trading-equity interpretation."""
from __future__ import annotations

from math import erfc, sqrt
import numpy as np
import pandas as pd


def hac_mean(values, lags=20):
    """Bartlett-kernel Newey-West uncertainty for a mean over ordered dates."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return dict(mean=float(np.mean(x)) if n else None, se=None, lo=None, hi=None, p=None)
    mean = float(x.mean()); z = x-mean
    lag = min(lags, n-1)
    lr = float(z@z/n)
    for k in range(1, lag+1):
        lr += 2*(1-k/(lag+1))*float(z[k:]@z[:-k]/n)
    se = sqrt(max(lr, 0)/n)
    p = erfc(abs(mean/se)/sqrt(2)) if se > 0 else None
    return dict(mean=mean, se=se, lo=mean-1.96*se, hi=mean+1.96*se, p=p)


def bh_fdr(pvalues):
    """Benjamini-Hochberg adjusted q values; undefined p remains missing."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full(len(p), np.nan); valid = np.flatnonzero(np.isfinite(p)); m=len(valid)
    if not m: return out
    order = valid[np.argsort(p[valid])]
    q = p[order]*m/np.arange(1,m+1)
    out[order] = np.minimum.accumulate(q[::-1])[::-1].clip(0,1)
    return out


def role_for_date(date, config):
    if date < pd.Timestamp(config["development_first_signal"]): return "warmup"
    if date <= pd.Timestamp(config["development_last_signal"]): return "development"
    if pd.Timestamp(config["evaluation_first_signal"]) <= date <= pd.Timestamp(config["evaluation_last_signal"]): return "evaluation"
    return "tail"


def assign_quantiles(scores: pd.Series, quintile_min=30, tercile_min=15):
    n=len(scores)
    q=5 if n>=quintile_min else 3 if n>=tercile_min else 0
    if not q: return pd.Series(dtype="Int64"), "insufficient_stocks"
    ranks=scores.rank(method="average", pct=True)
    group=np.ceil(ranks*q).clip(1,q).astype(int)
    if group.nunique()<q: return group, "collapsed_by_ties"
    return group, "ok"


def evaluate(factors, labels, benchmark_labels, config, allowed_roles=None):
    """Return date ICs, summary, date quantiles, summary quantiles and status rows."""
    ic_rows=[]; quant_rows=[]; status=[]
    for factor_name, frame in factors.items():
        for h, target in labels.items():
            bench=benchmark_labels[h]
            for date in frame.index:
                role=role_for_date(date, config)
                if allowed_roles is not None and role not in allowed_roles: continue
                joined=pd.DataFrame({"factor":frame.loc[date], "future":target.loc[date]}).dropna()
                joined=joined[np.isfinite(joined.factor)&np.isfinite(joined.future)]
                n=len(joined)
                if n<config["min_ic_stocks"] or not np.isfinite(bench.loc[date]):
                    status.append(dict(factor=factor_name,horizon=h,date=date,role=role,stocks=n,status="insufficient_or_missing_label"))
                    continue
                if joined.factor.nunique()<2 or joined.future.nunique()<2:
                    status.append(dict(factor=factor_name,horizon=h,date=date,role=role,stocks=n,status="constant_cross_section"))
                    continue
                pearson=float(joined.factor.corr(joined.future))
                rank=float(joined.factor.rank(method="average").corr(joined.future.rank(method="average")))
                ic_rows.append(dict(factor=factor_name,horizon=h,date=date,role=role,stocks=n,
                                    ic=pearson,rank_ic=rank,benchmark_future=float(bench.loc[date]),
                                    entry_date=frame.index[frame.index.get_loc(date)+1] if frame.index.get_loc(date)+1<len(frame.index) else pd.NaT,
                                    exit_date=frame.index[frame.index.get_loc(date)+h+1] if frame.index.get_loc(date)+h+1<len(frame.index) else pd.NaT))
                groups, state=assign_quantiles(joined.factor,config["quintile_min_stocks"],config["tercile_min_stocks"])
                status.append(dict(factor=factor_name,horizon=h,date=date,role=role,stocks=n,status=state))
                if state == "insufficient_stocks": continue
                q=int(groups.max())
                for group in sorted(groups.unique()):
                    returns=joined.future[groups==group]
                    quant_rows.append(dict(factor=factor_name,horizon=h,date=date,role=role,quantile=int(group),
                                           total_quantiles=q,stocks=len(returns),mean_return=float(returns.mean()),
                                           median_return=float(returns.median()),
                                           benchmark_relative=float(returns.mean()-bench.loc[date]),
                                           status=state))
    ic=pd.DataFrame(ic_rows); quant=pd.DataFrame(quant_rows); statuses=pd.DataFrame(status)
    summaries=[]
    for (factor,h,role),g in ic.groupby(["factor","horizon","role"],sort=True):
        g=g.sort_values("date")
        a=hac_mean(g.ic, max(config["hac_lags"],h))
        b=hac_mean(g.rank_ic, max(config["hac_lags"],h))
        summaries.append(dict(factor=factor,horizon=h,role=role,dates=len(g),observations=int(g.stocks.sum()),
                              min_stocks=int(g.stocks.min()),median_stocks=float(g.stocks.median()),
                              mean_ic=a["mean"],sd_ic=float(g.ic.std(ddof=1)) if len(g)>1 else np.nan,
                              median_ic=float(g.ic.median()),positive_ic_fraction=float((g.ic>0).mean()),
                              ic_ir=float(g.ic.mean()/g.ic.std(ddof=1)) if len(g)>1 and g.ic.std(ddof=1)>0 else np.nan,
                              ic_hac_lo=a["lo"],ic_hac_hi=a["hi"],ic_p=a["p"],
                              mean_rank_ic=b["mean"],rank_hac_lo=b["lo"],rank_hac_hi=b["hi"],rank_p=b["p"]))
    summary=pd.DataFrame(summaries)
    if not summary.empty:
        summary["rank_fdr_q"] = np.nan
        for role in ["development","evaluation"]:
            mask=summary.role.eq(role)
            summary.loc[mask,"rank_fdr_q"]=bh_fdr(summary.loc[mask,"rank_p"])
    q_summary=[]
    for (factor,h,role,q),g in quant.groupby(["factor","horizon","role","quantile"],sort=True):
        g=g.sort_values("date"); a=hac_mean(g.mean_return,max(config["hac_lags"],h)); b=hac_mean(g.benchmark_relative,max(config["hac_lags"],h))
        q_summary.append(dict(factor=factor,horizon=h,role=role,quantile=q,dates=len(g),observations=int(g.stocks.sum()),
                              mean_return=a["mean"],median_date_return=float(g.mean_return.median()),
                              return_hac_lo=a["lo"],return_hac_hi=a["hi"],
                              benchmark_relative=b["mean"],relative_hac_lo=b["lo"],relative_hac_hi=b["hi"]))
    return ic,summary,quant,pd.DataFrame(q_summary),statuses


def spread_diagnostic(quant):
    rows=[]
    for (factor,h,role,date),g in quant.groupby(["factor","horizon","role","date"]):
        if g.status.eq("ok").all() and g["quantile"].min()==1 and g["quantile"].max()==g.total_quantiles.max():
            rows.append(dict(factor=factor,horizon=h,role=role,date=date,
                             spread=float(g.loc[g["quantile"]==g["quantile"].max(),"mean_return"].iloc[0]-g.loc[g["quantile"]==1,"mean_return"].iloc[0])))
    return pd.DataFrame(rows)


def regime_summary(ic, regimes):
    rows=[]
    for name in regimes:
        values=regimes[name]
        for (factor,h,role),g in ic.groupby(["factor","horizon","role"]):
            g=g.copy(); g["regime"]=values.reindex(g.date).to_numpy()
            for state in [True,False]:
                part=g[g.regime==state]
                if len(part):
                    a=hac_mean(part.rank_ic,max(20,h))
                    rows.append(dict(regime=name,state=state,factor=factor,horizon=h,role=role,dates=len(part),mean_rank_ic=a["mean"],lo=a["lo"],hi=a["hi"]))
    return pd.DataFrame(rows)


def factor_correlations(factors, dates):
    names=list(factors); pearson=np.zeros((len(names),len(names))); spearman=np.zeros_like(pearson); counts=np.zeros_like(pearson)
    for date in dates:
        panel=pd.DataFrame({n:factors[n].loc[date] for n in names})
        p=panel.corr(min_periods=15).to_numpy(); s=panel.rank(method="average").corr(min_periods=15).to_numpy()
        valid=np.isfinite(p); pearson+=np.nan_to_num(p); spearman+=np.nan_to_num(s); counts+=valid
    return pd.DataFrame(np.divide(pearson,counts,out=np.full_like(pearson,np.nan),where=counts>0),index=names,columns=names),pd.DataFrame(np.divide(spearman,counts,out=np.full_like(spearman,np.nan),where=counts>0),index=names,columns=names)


def interaction_diagnostics(factors, labels, regimes, config):
    """Four frozen conditional tests; stock modifiers split within each date."""
    rows=[]; h=5
    for factor,condition in config["interaction_tests"]:
        signal=factors[factor]; target=labels[h]
        for date in signal.index:
            role=role_for_date(date,config)
            if role not in {"development","evaluation"}:continue
            panel=pd.DataFrame({"signal":signal.loc[date],"future":target.loc[date]}).dropna()
            if condition in regimes:
                regime=regimes.loc[date,condition]
                if pd.isna(regime):continue
                subsets={bool(regime):panel}
                unit="market_dates"
            else:
                panel["condition"]=factors[condition].loc[date]
                panel=panel.dropna()
                if len(panel)<15:continue
                median=panel.condition.median()
                subsets={False:panel[panel.condition<=median],True:panel[panel.condition>median]}
                unit="stocks_within_date"
            for state,group in subsets.items():
                if len(group)<7 or group.signal.nunique()<2 or group.future.nunique()<2:continue
                rank=float(group.signal.rank(method="average").corr(group.future.rank(method="average")))
                rows.append(dict(factor=factor,condition=condition,condition_state=state,conditioning_unit=unit,
                                 role=role,horizon=h,date=date,stocks=len(group),rank_ic=rank))
    daily=pd.DataFrame(rows);summaries=[]
    for (factor,condition,state,unit,role),g in daily.groupby(["factor","condition","condition_state","conditioning_unit","role"]):
        g=g.sort_values("date");a=hac_mean(g.rank_ic,20)
        summaries.append(dict(factor=factor,condition=condition,condition_state=state,conditioning_unit=unit,
                              role=role,horizon=h,dates=len(g),observations=int(g.stocks.sum()),
                              mean_rank_ic=a["mean"],lo=a["lo"],hi=a["hi"]))
    return daily,pd.DataFrame(summaries)


def segment_diagnostics(ic, schedule):
    """IC stability in Phase 1's predeclared non-overlapping 20-session windows."""
    rows=[]
    for period in schedule:
        if period["role"] not in {"development","evaluation"}:continue
        days=set(pd.to_datetime(period["days"]))
        part=ic[ic.date.isin(days)]
        for (factor,horizon),g in part.groupby(["factor","horizon"]):
            rows.append(dict(period_id=period["period_id"],role=period["role"],start=period["days"][0],
                             end=period["days"][-1],factor=factor,horizon=horizon,dates=len(g),
                             mean_ic=float(g.ic.mean()),mean_rank_ic=float(g.rank_ic.mean())))
    return pd.DataFrame(rows)


def factor_distribution(factors, config):
    """Cross-sectional median, quartiles and eligible count per completed signal date."""
    rows=[]
    for name,frame in factors.items():
        count=frame.count(axis=1);median=frame.median(axis=1);q1=frame.quantile(.25,axis=1);q3=frame.quantile(.75,axis=1)
        for date in frame.index:
            if count.loc[date]==0:continue
            rows.append(dict(factor=name,date=date,role=role_for_date(date,config),stocks=int(count.loc[date]),
                             q25=float(q1.loc[date]),median=float(median.loc[date]),q75=float(q3.loc[date])))
    return pd.DataFrame(rows)


def spread_summary(spread, config):
    rows=[]
    for (factor,h,role),g in spread.groupby(["factor","horizon","role"]):
        a=hac_mean(g.sort_values("date").spread,max(config["hac_lags"],h))
        rows.append(dict(factor=factor,horizon=h,role=role,dates=len(g),mean_top_minus_bottom=a["mean"],
                         hac_lo=a["lo"],hac_hi=a["hi"],p=a["p"],
                         interpretation="long_short_factor_diagnostic_not_tradable"))
    return pd.DataFrame(rows)
