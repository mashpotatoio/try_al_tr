"""Pre-registered research execution with immutable run folders and provenance."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import traceback
import uuid
import numpy as np
import pandas as pd

from .data import ROOT, load_daily, source_hashes, verify_phase1_manifest, sha256
from .factors import make_factors
from .labels import make_labels
from .evaluation import evaluate, factor_correlations, regime_summary, spread_diagnostic, interaction_diagnostics, segment_diagnostics, factor_distribution, spread_summary
from .proxy import ranking_proxy, raw_tick_cost_sample

PACKAGE=Path(__file__).resolve().parent
CONFIG=PACKAGE/"configs/preregistered.json"
SCHEDULE=ROOT/"research_set50_baseline/experiments/20261025T163641Z_run-daily_7f6c0946/schedule.json"


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False,default=str)+"\n",encoding="utf-8")


def _git_commit():
    cmd=["git","--git-dir=.phase2_git_meta","--work-tree=.","rev-parse","HEAD"]
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else None


def _provenance(config):
    sources={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(PACKAGE.rglob("*.py"))}
    sources[CONFIG.relative_to(ROOT).as_posix()]=sha256(CONFIG)
    versions={}
    for name in ["numpy","pandas","matplotlib","nbformat","nbclient","scipy","statsmodels"]:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    return dict(created_utc=datetime.now(timezone.utc).isoformat(),git_commit=_git_commit(),
                config_sha256=sha256(CONFIG),source_sha256=sources,data_sha256=source_hashes(),
                schedule_sha256=sha256(SCHEDULE),python=sys.version,executable=sys.executable,
                versions=versions,config=config,
                adjustment_convention="Supplied revised daily OHLCV; adjustment vintages unavailable",
                benchmark_convention="SET50 price index adjusted-open to adjusted-open labels",
                execution_convention="Historical adjusted opens are not executable tick prices")


def _save(frame,path):
    frame.to_csv(path,index=False,float_format="%.12g")


def run():
    config=json.loads(CONFIG.read_text(encoding="utf-8"))
    if set(config["factor_directions"].values())!={1}:raise ValueError("Factors must be oriented in source implementation")
    folder=PACKAGE/"results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/"config.json",config)
    write_json(folder/"provenance.json",_provenance(config))
    write_json(folder/"status.json",{"status":"running"})
    warnings=[]
    try:
        integrity=verify_phase1_manifest();write_json(folder/"phase1_integrity.json",integrity)
        if integrity["changed"]:raise RuntimeError(f"Phase 1 inputs changed: {integrity['changed'][:5]}")
        symbols,calendar,daily,audit=load_daily();_save(audit,folder/"data_inventory.csv")
        factors,regimes,benchmark=make_factors(symbols,calendar,daily)
        if set(factors)!=set(config["factor_directions"]):raise RuntimeError("Preregistration/factor mismatch")
        labels,benchmark_labels,timeline=make_labels(symbols,calendar,daily,config["horizons"])
        _save(timeline,folder/"timeline.csv")
        schedule=json.loads(SCHEDULE.read_text(encoding="utf-8"));write_json(folder/"schedule.json",schedule)
        all_ic=[];all_sum=[];all_quant=[];all_qsum=[];all_status=[]
        for role in ["development","evaluation","tail"]:
            print("Evaluating",role,flush=True)
            ic,s,q,qs,status=evaluate(factors,labels,benchmark_labels,config,{role})
            all_ic.append(ic);all_sum.append(s);all_quant.append(q);all_qsum.append(qs);all_status.append(status)
            _save(s,folder/f"{role}_summary.csv")
        ic=pd.concat(all_ic,ignore_index=True);summary=pd.concat(all_sum,ignore_index=True)
        quant=pd.concat(all_quant,ignore_index=True);qsummary=pd.concat(all_qsum,ignore_index=True)
        statuses=pd.concat(all_status,ignore_index=True)
        for name,table in [("daily_ic",ic),("factor_summary",summary),("daily_quantiles",quant),
                           ("quantile_summary",qsummary),("observation_status",statuses)]:_save(table,folder/f"{name}.csv")
        spread=spread_diagnostic(quant);_save(spread,folder/"top_minus_bottom_diagnostic.csv")
        _save(spread_summary(spread,config),folder/"top_minus_bottom_summary.csv")
        _save(segment_diagnostics(ic,schedule),folder/"segment_ic.csv")
        _save(factor_distribution(factors,config),folder/"factor_distribution.csv")
        regime=regime_summary(ic,regimes);_save(regime,folder/"regime_summary.csv")
        development_dates=calendar[(calendar>=pd.Timestamp(config["development_first_signal"])) & (calendar<=pd.Timestamp(config["development_last_signal"]))]
        corr,rankcorr=factor_correlations(factors,development_dates)
        corr.to_csv(folder/"factor_correlation.csv");rankcorr.to_csv(folder/"factor_rank_correlation.csv")
        proxy,proxy_details=ranking_proxy(factors,daily,calendar,schedule,config)
        _save(proxy,folder/"ranking_proxy.csv");_save(proxy_details,folder/"ranking_proxy_details.csv")
        raw=raw_tick_cost_sample(factors,calendar,config);_save(raw,folder/"raw_tick_cost_reference.csv")
        interaction_daily,interaction_summary=interaction_diagnostics(factors,labels,regimes,config)
        _save(interaction_daily,folder/"interaction_daily.csv")
        _save(interaction_summary,folder/"interactions.csv")
        from .visualization import charts
        charts(folder/"figures",ic,summary,qsummary,rankcorr,regime,proxy,audit,config["rolling_ic_dates"])
        write_json(folder/"run_summary.json",dict(symbols=len(symbols),calendar_sessions=len(calendar),
                   first_date=str(calendar[0].date()),last_date=str(calendar[-1].date()),
                   factors=len(factors),horizons=config["horizons"],valid_ic_dates=len(ic),
                   development_ic_dates=int((ic.role=="development").sum()),evaluation_ic_dates=int((ic.role=="evaluation").sum()),
                   daily_rows=int(sum(len(d) for d in daily.values())),raw_tick_reference_rows=len(raw),
                   warnings=sorted(set(warnings)),phase1_integrity=integrity))
        write_json(folder/"status.json",{"status":"complete","completed_utc":datetime.now(timezone.utc).isoformat()})
        print("Completed",folder,flush=True)
        return folder
    except Exception:
        (folder/"failure.log").write_text(traceback.format_exc(),encoding="utf-8")
        write_json(folder/"status.json",{"status":"failed","error":traceback.format_exc().splitlines()[-1]})
        raise


def verify(folder:Path):
    """Independently rebuild summary means from saved date-level observations."""
    folder=Path(folder); ic=pd.read_csv(folder/"daily_ic.csv");summary=pd.read_csv(folder/"factor_summary.csv")
    mismatches=[]
    for row in summary.itertuples():
        g=ic[(ic.factor==row.factor)&(ic.horizon==row.horizon)&(ic.role==row.role)]
        if len(g)!=row.dates or abs(g.ic.mean()-row.mean_ic)>1e-9 or abs(g.rank_ic.mean()-row.mean_rank_ic)>1e-9:
            mismatches.append(f"{row.factor}/{row.horizon}/{row.role}")
    provenance=json.loads((folder/"provenance.json").read_text(encoding="utf-8"))
    data_changed=[name for name,expected in provenance["data_sha256"].items() if sha256(ROOT/name)!=expected]
    result=dict(status="pass" if not mismatches and not data_changed else "fail",summary_rows=len(summary),
                ic_rows=len(ic),mismatches=mismatches,data_changed=data_changed)
    write_json(folder/"verification.json",result)
    if result["status"]!="pass":raise RuntimeError(result)
    return result
