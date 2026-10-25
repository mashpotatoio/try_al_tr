"""Explicit metric definitions; performance and eligibility are separate outputs."""
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .core import maximum_drawdown
from .data import PACKAGE, write_json


def evaluate(equity, ledger, benchmark, initial, orders, engine=None):
    """Evaluate EOD observations with initial equity included in research DD.

    benchmark contains a prior-session anchor followed by every measured day.
    A gap makes benchmark-dependent metrics unavailable, never silently zero.
    Engine metrics are retained under a separate key with their conventions.
    """
    e = pd.DataFrame(equity)
    values = e.equity.to_numpy()
    ret = float(values[-1] / initial - 1)
    dd = maximum_drawdown([initial, *values])
    valid_benchmark = (len(benchmark) == len(e) + 1 and np.isfinite(benchmark).all()
                       and (np.asarray(benchmark) > 0).all())
    bm_ret = float(benchmark[-1] / benchmark[0] - 1) if valid_benchmark else None
    bm_dd = maximum_drawdown(benchmark) if valid_benchmark else None
    pnl = [r["realized_pnl"] for r in ledger.round_trips if r["realized_pnl"] != 0]
    payoff = float(np.mean(pnl)) if pnl else None
    win_rate = sum(p > 0 for p in pnl) / len(pnl) if pnl else None
    status = pd.Series([o["status"] for o in orders], dtype="object").value_counts().to_dict()
    metrics = dict(start=e.date.iloc[0], end=e.date.iloc[-1], sessions=len(e), initial_equity=initial,
        final_equity=float(values[-1]), net_return=ret, benchmark_return=bm_ret,
        excess_return=ret-bm_ret if bm_ret is not None else None, max_drawdown=dd,
        benchmark_max_drawdown=bm_dd, competition_calmar=ret/dd if dd else None,
        average_exposure=float(e.exposure.mean()), round_trips=len(ledger.round_trips),
        expected_payoff=payoff, win_rate=win_rate,
        turnover=sum(f["notional"] for f in ledger.fills)/float(e.equity.mean()),
        commission=sum(f["commission"] for f in ledger.fills), vat=sum(f["vat"] for f in ledger.fills),
        slippage_thb=sum(f["slippage_thb"] or 0 for f in ledger.fills),
        submitted=len(orders), filled=status.get("filled",0), partially_filled=status.get("partially_filled",0),
        rejected=status.get("rejected",0), canceled=status.get("canceled",0),
        final_cash=float(e.cash.iloc[-1]), final_unfilled_target=float(e.unfilled_target.iloc[-1]),
        max_unfilled_target=float(e.unfilled_target.max()), gross_return=None,
        engine_metrics=engine,
        definitions=dict(return_units="fraction", payoff_units="THB per non-breakeven completed original FIFO lot",
             turnover="sum(abs(fill notional)) / mean daily equity", exposure="mean(EOD holdings market value / EOD equity)",
             terminal="mark to market, no forced liquidation", benchmark="prior-session close to final close; price return",
             drawdown="EOD equity plus initial capital; engine EOD-only convention recorded separately",
             gross_return="not reconstructed", partial_fills="native engine unsupported; daily model assumes full feasible fill"),
        undefined_reasons={})
    for name in ["benchmark_return","benchmark_max_drawdown","excess_return"]:
        if metrics[name] is None:
            metrics["undefined_reasons"][name] = "Missing or invalid exact benchmark observations/anchor"
    if not dd:
        metrics["undefined_reasons"]["competition_calmar"] = "Zero or undefined maximum drawdown"
    if not pnl:
        metrics["undefined_reasons"]["expected_payoff"] = "No completed non-breakeven FIFO lots"
        metrics["undefined_reasons"]["win_rate"] = "No completed non-breakeven FIFO lots"
    metrics["eligibility"] = eligibility(metrics)
    return metrics


def eligibility(m):
    """Strict inequalities matter. Local pass does not imply organizer approval."""
    dd_bound = 1.5*m["benchmark_max_drawdown"] if m["benchmark_max_drawdown"] is not None else None
    rules = [("drawdown", "< 1.5 * benchmark drawdown",m["max_drawdown"],dd_bound,"lt"),
        ("round_trips",">= 5",m["round_trips"],5,"ge"),
        ("exposure",">= 0.50",m["average_exposure"],.5,"ge"),
        ("payoff","> 0",m["expected_payoff"],0,"gt"),
        ("best_alpha_return",">= 0",m["net_return"],0,"ge"),
        ("best_alpha_excess",">= 0",m["excess_return"],0,"ge")]
    rows=[]
    for name,threshold,value,bound,op in rules:
        passed = None if value is None or bound is None else (
            value < bound if op=="lt" else value > bound if op=="gt" else value >= bound)
        rows.append(dict(criterion=name, threshold=threshold, numeric_threshold=bound, observed=value,
                         status="unverified" if passed is None else "pass" if passed else "fail",
                         calculation="provisional research; local engine definitions cross-checked",
                         official_status="unverified"))
    return rows


def save_run(path, ledger, equity, orders, signals, targets, metrics, holdings):
    """Write inspectable records, including empty tables with useful headers."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for name, records, columns in [
        ("fills",ledger.fills,["order_id","symbol","side","quantity","price","timestamp"]),
        ("round_trips",ledger.round_trips,["symbol","order_id","realized_pnl"]),
        ("equity",equity,["date","equity","cash","exposure"]),
        ("orders",orders,["order_id","symbol","side","quantity","status","timestamp","reason"]),
        ("signals",signals,["date","symbol","momentum","relative_strength","volatility"]),
        ("targets",targets,["date","symbol","weight","quantity"]),
        ("holdings",holdings,["date","symbol","quantity","mark"]),
        ("eligibility",metrics["eligibility"],["criterion","status"])]:
        pd.DataFrame(records, columns=None if records else columns).to_csv(path / (name+".csv"),index=False)
    write_json(path / "metrics.json",metrics)
    write_json(path / "ledger_final.json",dict(cash=ledger.cash,quantities=ledger.quantities(),pending=ledger.pending))


def plotting():
    """Load optional task-local matplotlib without altering the global interpreter."""
    import os
    os.environ["MPLCONFIGDIR"]=str(PACKAGE/".plot_cache")
    vendor=PACKAGE/"vendor"
    if vendor.exists():
        sys.path.insert(0,str(vendor))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def make_report(experiment):
    """Tables retain all windows; charts show native/daily panels and window spread."""
    import json
    experiment=Path(experiment)
    paths=sorted(experiment.glob("runs/*/metrics.json"))
    rows=[]
    for p in paths:
        m=json.loads(p.read_text())
        row={k:v for k,v in m.items() if not isinstance(v,(dict,list))}
        row.update(run=p.parent.name)
        row["common_pass"]=all(r["status"]=="pass" for r in m["eligibility"][:4])
        row["best_alpha_conditions_pass"]=all(r["status"]=="pass" for r in m["eligibility"])
        row["official_eligibility"]="unverified"
        rows.append(row)
    table=pd.DataFrame(rows)
    if table.empty:
        raise ValueError("No completed run metrics")
    report=experiment/"reports"
    if report.exists():
        from datetime import datetime, timezone
        import uuid
        report=experiment/("reports_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:6])
    report.mkdir(exist_ok=False)
    table.to_csv(report/"comparison.csv",index=False)
    columns=["run","sessions","net_return","excess_return","max_drawdown","average_exposure","round_trips","expected_payoff","common_pass"]
    lines=["# Strategy comparison", "", "Returns and drawdowns are fractions; payoff is THB. Official eligibility is unverified.", "",
           "|"+"|".join(columns)+"|", "|"+"|".join(["---"]*len(columns))+"|"]
    for _,r in table.iterrows():
        lines.append("|"+"|".join(f"{r[k]:.6g}" if isinstance(r[k],float) else str(r[k]) for k in columns)+"|")
    (report/"comparison.md").write_text("\n".join(lines),encoding="utf-8")
    summary=table.groupby(["period_role","strategy"],dropna=False).agg(
        windows=("run","count"),mean_return=("net_return","mean"),median_return=("net_return","median"),
        worst_return=("net_return","min"),mean_excess=("excess_return","mean"),
        profitable_fraction=("net_return",lambda s:float((s>=0).mean())),
        outperform_fraction=("excess_return",lambda s:float((s>=0).mean())),
        common_pass_fraction=("common_pass","mean"))
    summary.to_csv(report/"window_summary.csv")
    plt=plotting()
    # One self-contained chart per period: no stitched resets masquerading as a portfolio.
    for period, group in table.groupby("period_id"):
        fig,axs=plt.subplots(3,1,figsize=(11,9),sharex=True)
        for _,r in group.iterrows():
            e=pd.read_csv(experiment/"runs"/r.run/"equity.csv")
            dates=pd.to_datetime(e.date)
            nav=e.equity / r.initial_equity
            peaks=np.maximum.accumulate(np.r_[1,nav.to_numpy()])[1:]
            axs[0].plot(dates,nav,label=r.strategy)
            axs[1].plot(dates,(nav/peaks-1)*100)
            axs[2].plot(dates,e.exposure*100)
        if "benchmark_equity" in e and e.benchmark_equity.notna().all():
            b=e.benchmark_equity/e.benchmark_anchor.iloc[0]
            axs[0].plot(dates,b,"k--",label="SET50 price")
            axs[1].plot(dates,(b/np.maximum.accumulate(np.r_[1,b])[1:]-1)*100,"k--")
        axs[0].legend(fontsize=8,ncol=3)
        for ax,label in zip(axs,["Equity / initial", "Drawdown (%)", "Exposure (%)"]):
            ax.set_ylabel(label); ax.grid(alpha=.25)
        fig.suptitle(f"{period} — research assumptions; official eligibility unverified")
        fig.autofmt_xdate(); fig.tight_layout()
        fig.savefig(report/f"{period}.png",dpi=130)
        fig.savefig(report/f"{period}.svg")
        plt.close(fig)
    write_json(report/"report_status.json",{"runs":len(rows),"charts":table.period_id.nunique()})
    return table
