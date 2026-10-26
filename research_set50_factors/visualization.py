"""Saved research diagnostics with explicit sample and return convention labels."""
from __future__ import annotations

from pathlib import Path
import sys
import numpy as np
import pandas as pd

VENDOR=Path(__file__).resolve().parent.parent/"research_set50_baseline"/"vendor"
sys.path.insert(0,str(VENDOR))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi":180,"savefig.dpi":180,"font.size":9,"axes.spines.top":False,"axes.spines.right":False,"grid.alpha":0.25})


def _save(fig,path,title):
    fig.suptitle(title,fontsize=11,fontweight="bold")
    fig.tight_layout(rect=[0,0,1,.95]); fig.savefig(path,bbox_inches="tight"); plt.close(fig)


def charts(out:Path, ic:pd.DataFrame, summary:pd.DataFrame, quant_summary:pd.DataFrame,
           corr:pd.DataFrame, regime:pd.DataFrame, proxy:pd.DataFrame, audit:pd.DataFrame,
           rolling_dates=60):
    out.mkdir(parents=True,exist_ok=True)
    convention="Adjusted daily open t+1 to open t+1+h; diagnostics, not executable returns"
    for role in ["development","evaluation"]:
        sub=summary[(summary.role==role)&(summary.horizon==5)].sort_values("mean_rank_ic")
        if sub.empty:continue
        for metric,filename in [("mean_ic","ic_comparison"),("mean_rank_ic","rank_ic_comparison")]:
            fig,ax=plt.subplots(figsize=(9,7));ax.barh(sub.factor,sub[metric],color=np.where(sub[metric]>=0,"#0d6b66","#a63d40"));ax.axvline(0,color="black",lw=.7);ax.set_xlabel(metric.replace("_"," "));ax.grid(axis="x")
            _save(fig,out/f"{role}_{filename}.png",f"{role.title()} | h=5 sessions | {convention}")
        mat=summary[summary.role==role].pivot(index="factor",columns="horizon",values="mean_rank_ic")
        fig,ax=plt.subplots(figsize=(7,8));lim=np.nanmax(np.abs(mat.to_numpy()));im=ax.imshow(mat,cmap="RdBu_r",vmin=-lim,vmax=lim,aspect="auto")
        ax.set_xticks(range(len(mat.columns)),mat.columns);ax.set_yticks(range(len(mat.index)),mat.index);ax.set_xlabel("Forward sessions");fig.colorbar(im,ax=ax,label="Mean Rank IC")
        _save(fig,out/f"{role}_horizon_heatmap.png",f"{role.title()} | all horizons | {convention}")
        fig,axes=plt.subplots(5,5,figsize=(16,11),sharex=True,sharey=True)
        for ax,(name,g) in zip(axes.flat,ic[(ic.role==role)&(ic.horizon==5)].groupby("factor")):
            g=g.sort_values("date");ax.plot(g.date,g.ic.rolling(rolling_dates,min_periods=20).mean(),lw=.8);ax.axhline(0,color="gray",lw=.5);ax.set_title(name,fontsize=8);ax.tick_params(axis="x",labelrotation=45)
        _save(fig,out/f"{role}_rolling_ic.png",f"{role.title()} | h=5, rolling {rolling_dates} dates | {convention}")
        fig,axes=plt.subplots(5,5,figsize=(16,11),sharex=True)
        for ax,(name,g) in zip(axes.flat,ic[(ic.role==role)&(ic.horizon==5)].groupby("factor")):
            g=g.sort_values("date");ax.plot(g.date,g.ic.cumsum(),lw=.8);ax.set_title(name,fontsize=8);ax.tick_params(axis="x",labelrotation=45)
        _save(fig,out/f"{role}_cumulative_ic.png",f"{role.title()} | h=5 cumulative IC, not equity | {convention}")
        for name,g in quant_summary[(quant_summary.role==role)&(quant_summary.horizon==5)].groupby("factor"):
            g=g.sort_values("quantile");fig,ax=plt.subplots(figsize=(5,3));ax.bar(g["quantile"],g.benchmark_relative*100,color="#236f7c");ax.axhline(0,color="black",lw=.6);ax.set_xticks(g["quantile"]);ax.set_xlabel("Factor quantile, low to high");ax.set_ylabel("Mean excess return, %")
            _save(fig,out/f"{role}_quantile_{name}.png",f"{role.title()} | {name}, h=5 | {convention}")
        rg=regime[(regime.role==role)&(regime.horizon==5)].copy()
        if len(rg):
            rg["group"]=rg.regime+"="+rg.state.astype(str)
            mat=rg.pivot(index="factor",columns="group",values="mean_rank_ic")
            fig,ax=plt.subplots(figsize=(11,8));lim=np.nanmax(np.abs(mat.to_numpy()));im=ax.imshow(mat,cmap="RdBu_r",vmin=-lim,vmax=lim,aspect="auto");ax.set_xticks(range(len(mat.columns)),mat.columns,rotation=45,ha="right");ax.set_yticks(range(len(mat.index)),mat.index);fig.colorbar(im,ax=ax,label="Mean Rank IC")
            _save(fig,out/f"{role}_regime.png",f"{role.title()} | h=5, decision-time regimes | {convention}")
        pg=proxy[proxy.role==role].groupby(["factor","frequency"]).total_one_way_turnover.mean().unstack()
        if len(pg):
            fig,ax=plt.subplots(figsize=(10,6));pg.plot(kind="bar",ax=ax,width=.8);ax.set_ylabel("Mean 20-session one-way turnover / initial capital");ax.grid(axis="y")
            _save(fig,out/f"{role}_turnover.png",f"{role.title()} | top-five proxy, adjusted-open notionals | not filled trades")
    fig,ax=plt.subplots(figsize=(10,8));lim=np.nanmax(np.abs(corr.to_numpy()));im=ax.imshow(corr,cmap="RdBu_r",vmin=-lim,vmax=lim);ax.set_xticks(range(len(corr)),corr.columns,rotation=90);ax.set_yticks(range(len(corr)),corr.index);fig.colorbar(im,ax=ax,label="Mean date-level rank correlation")
    _save(fig,out/"factor_correlation.png",f"Development | same-date factors | completed daily data, no forward return")
    fig,ax=plt.subplots(figsize=(9,6));a=audit.sort_values("rows");ax.barh(a.symbol,a.rows,color="#236f7c");ax.set_xlabel("Daily OHLCV sessions");ax.grid(axis="x")
    _save(fig,out/"data_coverage.png","Supplied daily data | 2023-09-21 to 2026-10-06 | symbol coverage")
