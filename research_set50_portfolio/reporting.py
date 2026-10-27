"""Create observed-data evidence tables, plots, and compact critical findings."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
P2 = ROOT.parent / "research_set50_factors/results/20261026T161657Z_64b58b98"


def main(out):
    out=Path(out); figs=out/"figures"; figs.mkdir(exist_ok=True)
    w=pd.read_csv(out/"windows.csv"); d=pd.read_csv(out/"daily_equity.csv")
    ev=w.query("role == 'evaluation' and scenario == 'official' and exit_rule == 'scheduled'").copy()
    ic=pd.read_csv(P2/"factor_summary.csv"); q=pd.read_csv(P2/"quantile_summary.csv")
    evidence=[]
    for factor,h in [("mom_20",5),("sma20_above_sma60",5),("reversal_1",1)]:
        i=ic.query("factor == @factor and horizon == @h and role == 'evaluation'").iloc[0]
        qq=q.query("factor == @factor and horizon == @h and role == 'evaluation'")
        top=qq.loc[qq["quantile"]==qq["quantile"].max(),"benchmark_relative"].iloc[0]
        evidence.append({"factor":factor,"horizon":h,"rank_ic":i.mean_rank_ic,"rank_ic_ci_lo":i.rank_hac_lo,"rank_ic_ci_hi":i.rank_hac_hi,"fdr_q":i.rank_fdr_q,"top_quantile_relative":top,
                         "decision":"exploratory primary" if factor != "reversal_1" else "tie-breaker only"})
    pd.DataFrame(evidence).to_csv(out/"factor_evidence.csv",index=False)
    audit=ev[["window","strategy","drawdown_pass","roundtrip_pass","exposure_pass","payoff_pass","nonnegative_return","nonnegative_excess","common_eligible","best_alpha_eligible"]]
    audit.to_csv(out/"eligibility_audit.csv",index=False)
    ev.assign(cost_thb=lambda x:x.commission_thb+x.vat_thb+x.slippage_thb)[["window","strategy","commission_thb","vat_thb","slippage_thb","cost_thb"]].to_csv(out/"cost_attribution.csv",index=False)
    rng=np.random.default_rng(20261027)
    ci=[]
    for s,g in ev.groupby("strategy"):
        a=g.excess_return.to_numpy(); boot=np.mean(rng.choice(a,size=(3000,len(a)),replace=True),axis=1)
        ci.append({"strategy":s,"mean_excess":a.mean(),"window_bootstrap_lo":np.quantile(boot,.025),"window_bootstrap_hi":np.quantile(boot,.975),"windows":len(a)})
    pd.DataFrame(ci).to_csv(out/"uncertainty.csv",index=False)
    scenarios=w.query("role == 'evaluation'").groupby(["strategy","scenario","exit_rule"]).agg(mean_net=("net_return","mean"),mean_excess=("excess_return","mean"),eligibility=("best_alpha_eligible","mean"),turnover=("turnover","mean"),roundtrips=("roundtrips","mean")).reset_index()
    scenarios.to_csv(out/"robustness.csv",index=False)
    # Ex-post regime diagnostic only; market direction is known after the window.
    ev["regime_ex_post"]=pd.cut(ev.benchmark_return,[-np.inf,-.02,.02,np.inf],labels=["down","sideways","up"])
    ev.groupby(["strategy","regime_ex_post"],observed=True).agg(windows=("net_return","size"),mean_excess=("excess_return","mean"),eligibility=("best_alpha_eligible","mean")).to_csv(out/"regimes_ex_post.csv")
    def save(name,title,xlabel="",ylabel=""):
        plt.title(title);plt.xlabel(xlabel);plt.ylabel(ylabel);plt.tight_layout();plt.savefig(figs/name,dpi=130);plt.close()
    sample=d.query("strategy == 'A' and scenario == 'official' and window == 'window_12'")
    if sample.empty: sample=d.query("strategy == 'A' and scenario == 'official'").iloc[:20]
    window_id=sample.window.iloc[0]
    b_return=ev[(ev.window==window_id)&(ev.strategy=="A")].benchmark_return.iloc[0]
    b_open=sample.benchmark_close.iloc[-1]/(1+b_return)
    plt.plot(sample.equity.to_numpy()/1e7-1,label="A portfolio");plt.plot(sample.benchmark_close.to_numpy()/b_open-1,label="SET50");plt.legend();save("equity.png","Example evaluation window equity vs SET50","session","return")
    piv=ev.pivot(index="window",columns="strategy",values="excess_return");piv.plot(figsize=(11,4));save("window_excess.png","Net excess return by window","window","return")
    for s in ["A","C","E"]:
        z=d.query("strategy == @s and scenario == 'official' and window == @window_id")
        if not z.empty: plt.plot(1-z.equity.to_numpy()/np.maximum.accumulate(np.r_[1e7,z.equity.to_numpy()])[1:],label=s)
    b_path=sample.benchmark_close.to_numpy()
    plt.plot(1-b_path/np.maximum.accumulate(np.r_[b_open,b_path])[1:],label="SET50",linestyle="--")
    plt.legend();save("drawdown.png","Example window drawdown","session","drawdown")
    for s in ["A","C","E"]:
        z=d.query("strategy == @s and scenario == 'official' and window == @window_id")
        if not z.empty: plt.plot(z.exposure.to_numpy(),label=s)
    plt.legend();save("exposure.png","Example window exposure","session","fraction")
    ev.boxplot(column="net_return",by="strategy");plt.suptitle("");save("return_distribution.png","Net return distribution","strategy","return")
    ev.groupby("strategy")[["commission_thb","vat_thb","slippage_thb"]].mean().plot.bar(stacked=True);save("costs.png","Mean modeled cost per window","strategy","THB")
    for s,g in ev.groupby("strategy"):plt.scatter(g.turnover,g.net_return,label=s,alpha=.6)
    plt.legend();save("turnover_performance.png","Turnover and net return","one-way traded value / initial capital","net return")
    ev.groupby("strategy")[["common_eligible","best_alpha_eligible"]].mean().plot.bar();save("eligibility.png","Eligibility rates","strategy","fraction")
    ev.groupby("strategy")[["net_return","excess_return"]].mean().loc[["A","B","C","D"]].plot.bar();save("weighting.png","A-D weighting and tie-breaker ablation","strategy","mean return")
    sens=pd.read_csv(out/"sensitivity.csv");sens.groupby(["parameter","value"]).excess_return.mean().plot.bar(figsize=(10,4));save("sensitivity.png","One-at-a-time sensitivity","parameter, value","mean excess")
    ev.groupby(["strategy","regime_ex_post"],observed=True).excess_return.mean().unstack().plot.bar();save("regimes.png","Ex-post market regimes","strategy","mean excess")
    comp=pd.read_csv(out/"comparison.csv").set_index("strategy")
    chosen=json.loads((out/"manifest.json").read_text())["development_selected_e_base"]
    lines=["# Phase 3 findings", "", f"Run: `{out.name}`. Development selected E base: **{chosen}**. All evaluation dates were previously exposed in prior research.","", "## Evaluation (24 windows)", "", "```text",comp[["mean_net","median_net","worst_net","mean_excess","common_pass","best_alpha_pass","mean_turnover","mean_roundtrips"]].round(4).to_string(),"```","", "## Interpretation", "", "The reversal tie-breaker does not establish a net edge: compare C with A and D with B under identical scheduled execution. E reduces turnover, but its lower natural FIFO lot completion can fail the five-round-trip gate. A positive average net return alone does not establish robust excess return.","", "Modeled one-tick cost is a sensitivity assumption applied to vendor-revised adjusted opens. It is not validated executable historical pricing. Large modeled slippage makes this limitation material. Participation caps and half-fill scenarios are conditional fill approximations, not IOC depth simulations.","", "Historical membership is today's permitted list, and adjustment vintages are unavailable. No independent untouched out-of-sample dates remain. Native practice data cover only 16 sessions and cannot establish a 20-session result. This research does not certify official eligibility.","", "## Recommendation", "", "**C — No defensible edge established.** New untouched history and executable price validation are needed before advancing to machine learning. The next practical work is to reconcile adjusted daily prices against native ticks and validate an order adapter on available sessions."]
    (ROOT/"docs/04_backtest_findings.md").write_text("\n".join(lines),encoding="utf-8")
    print("reporting complete",out)

if __name__=="__main__":
    import sys
    main(sys.argv[1])
