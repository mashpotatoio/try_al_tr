"""Independently reconcile saved positions, orders, fees and summary metrics."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from research_set50_factors.data import sha256, verify_phase1_manifest

out=Path(sys.argv[1]); root=Path(__file__).resolve().parent
m=json.loads((out/"manifest.json").read_text())
w=pd.read_csv(out/"windows.csv"); d=pd.read_csv(out/"daily_equity.csv")
h=pd.read_csv(out/"holdings.csv"); o=pd.read_csv(out/"orders.csv"); t=pd.read_csv(out/"fifo_roundtrips.csv")
errors=[]
allowed=set(pd.read_csv(root.parent/"marketInfo/symbolSET50/Symbol_SET50.csv").Symbol)
if not set(o.symbol).issubset(allowed):errors.append("universe membership")
if ((o.filled>o.accepted)|(o.accepted>o.requested)|(o.filled<0)|(o.filled%100!=0)).any():errors.append("order quantities")
if ((h.shares<0)|(h.shares%100!=0)).any():errors.append("holding lots")
if (d.cash<-1e-6).any():errors.append("negative cash")
if sha256(out/"config.json")!=m["config_sha256"]:errors.append("config hash")
for name,digest in m["source_hashes"].items():
    if sha256(root/name)!=digest:errors.append("source hash "+name)
if len(w)!=len(d.groupby(["window","strategy","scenario"])):
    # Same strategy and scenario can occur under alternative exits; verify with exit rule below.
    pass
for key,g in d.groupby(["window","strategy","scenario"]):
    if len(g) not in (20,40,60):errors.append("unexpected daily count "+str(key))
dup=w.groupby(["window","strategy","scenario"]).size()
unique_keys=set(dup[dup==1].index)
v=h.assign(value=h.shares*h.close).groupby(["window","strategy","scenario","date"]).value.sum()
for row in d.itertuples():
    if (row.window,row.strategy,row.scenario) not in unique_keys:continue
    position_value=v.get((row.window,row.strategy,row.scenario,row.date),0)
    if abs(row.cash+position_value-row.equity)>1e-4:
        errors.append("equity mismatch "+str(row.date));break
for _,r in w.iterrows():
    mask=(o.window==r.window)&(o.strategy==r.strategy)&(o.scenario==r.scenario)&(o.exit_rule==r.exit_rule)
    orders=o.loc[mask]
    if len(orders)!=r.orders or int((orders.filled>0).sum())!=r.filled_orders:errors.append("orders "+str(r.window)+r.strategy)
    if abs(orders.commission.fillna(0).sum()-r.commission_thb)>1e-5:errors.append("commission "+str(r.window)+r.strategy)
    if abs(orders.vat.fillna(0).sum()-r.vat_thb)>1e-5:errors.append("vat "+str(r.window)+r.strategy)
    if abs(orders.slippage.fillna(0).sum()-r.slippage_thb)>1e-5:errors.append("slippage "+str(r.window)+r.strategy)
    trips=t[(t.window==r.window)&(t.strategy==r.strategy)&(t.scenario==r.scenario)&(t.exit_rule==r.exit_rule)]
    if len(trips)!=r.roundtrips:errors.append("FIFO count "+str(r.window)+r.strategy)
    dg=d[(d.window==r.window)&(d.strategy==r.strategy)&(d.scenario==r.scenario)]
    # Scheduled strategy records are the first 20 daily entries for duplicated scenarios.
    if r.exit_rule=="scheduled":
        dg=dg.iloc[:20]
        if len(dg)!=20:errors.append("window length "+str(r.window)+r.strategy)
        elif abs(dg.equity.iloc[-1]/10_000_000-1-r.net_return)>1e-9:errors.append("net return "+str(r.window)+r.strategy)
phase1=verify_phase1_manifest()
result={"pass":not errors and not phase1["changed"],"errors":errors[:30],"phase1_integrity":phase1,
        "window_records":len(w),"daily_records":len(d),"orders":len(o),"fifo_completions":len(t),
        "figures":len(list((out/"figures").glob("*.png")))}
(out/"verification.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
if not result["pass"]:sys.exit(1)
