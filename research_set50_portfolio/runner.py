"""Run frozen 20-session portfolio experiments and write auditable records."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from research_set50_factors.data import load_daily, sha256
from .core import Account, signals, rank, weights, max_drawdown, eligibility

ROOT = Path(__file__).resolve().parent
PHASE2 = ROOT.parent / "research_set50_factors/results/20261026T161657Z_64b58b98"


def run_window(window, strategy, data, cfg, scenario="official", exit_rule="scheduled", params=None):
    symbols, calendar, frames, signal_cache = data
    par = {**cfg, **(params or {})}
    days = pd.DatetimeIndex(window["days"])
    if len(days) != 20 or any(d not in calendar for d in days):
        raise ValueError("Schedule must contain exactly 20 SET50 sessions")
    acct = Account(float(par["initial_cash"]))
    mark = {}
    daily, holding_rows = [], []
    previous_names = []
    requested_targets = []
    for i, day in enumerate(days):
        prior = calendar[calendar.get_loc(day)-1]
        rebalance = i % int(par["rebalance_every"]) == 0
        if strategy == "buy_hold":
            rebalance = i == 0
        if rebalance:
            cache_key = (prior, int(par["volatility_window"]))
            if cache_key not in signal_cache:
                signal_cache[cache_key] = signals(frames, symbols, prior, int(par["volatility_window"]))
            sig = signal_cache[cache_key]
            if strategy == "buy_hold":
                ranked = sorted(sig.index)  # fixed, transparent diversification baseline
            else:
                primary = "sma20_sma60" if strategy == "sma_trend" else par["primary"]
                ranked = rank(sig, primary, strategy in ("C", "D") or (strategy in ("E", "risk_only") and par.get("e_base") in ("C", "D")), par["tie_percentile_gap"])
            n = int(par["holdings"])
            names = ranked[:n]
            if exit_rule == "rank" and strategy != "buy_hold" and previous_names:
                retained=[s for s in previous_names if s in ranked[:n+4]]
                names=(retained+[s for s in ranked if s not in retained])[:n]
            if strategy == "E" and previous_names:
                keep = [s for s in previous_names if s in ranked[:int(par["hysteresis_exit_rank"])]]
                names = (keep + [s for s in ranked if s not in keep])[:n]
            if exit_rule == "trend_deterioration" and strategy != "buy_hold":
                names = [s for s in names if sig.loc[s, "mom20"] > 0]
            method = "inverse_vol" if strategy in ("B", "D") or (strategy in ("E", "risk_only") and par.get("e_base") in ("B", "D")) else "equal"
            risk_overlay = strategy in ("E", "risk_only")
            target = weights(names, sig, method, .75 if risk_overlay else float(par["target_exposure"]), .18 if risk_overlay else float(par["max_weight"]))
            previous_names = names
            requested_targets.append({"date": str(day.date()), "strategy": strategy, "target": target})
            opens = {s: frames[s].loc[day, "Open"] for s in set(target) | set(acct.shares)}
            # Prices for estimating current weights use completed prior close, never the future open.
            prior_prices = {s: float(frames[s].loc[prior, "Close"]) for s in opens}
            estimated_equity = acct.cash + sum(q * prior_prices[s] for s, q in acct.shares.items() if q and np.isfinite(prior_prices[s]))
            intents = []
            for sym in sorted(opens):
                old = acct.shares[sym]
                desired = int(estimated_equity * target.get(sym, 0) / prior_prices[sym] // 100) * 100 if np.isfinite(prior_prices[sym]) and prior_prices[sym] > 0 else old
                change = desired - old
                if strategy == "E" and i > 0 and abs(change * prior_prices[sym] / estimated_equity) < float(par["threshold_weight"]):
                    continue
                if change:
                    intents.append((sym, "sell" if change < 0 else "buy", abs(change)))
            # Sell first; preserve intended quantities independently of fills.
            for sym, side, qty in sorted(intents, key=lambda x: x[1] != "sell"):
                f = frames[sym]
                observed = f.loc[day]
                open_price = float(observed.Open) if bool(observed.valid) else float("nan")
                cap = int(float(sig.loc[sym, "prior_volume"]) * float(par["participation_rate"])) if sym in sig.index else 0
                acct.trade(day, sym, side, qty, open_price, cap,
                           commission=0 if scenario == "zero" else float(par["commission"]),
                           vat_rate=float(par["vat"]), ticks=0 if scenario == "zero" else (2 if scenario == "two_ticks" else int(par["slippage_ticks"])),
                           fill_fraction=.5 if scenario == "half_fills" else 1)
        for sym in symbols:
            close = frames[sym].loc[day, "Close"]
            if np.isfinite(close) and close > 0:
                mark[sym] = float(close)
        if any(s not in mark for s, q in acct.shares.items() if q):
            raise ValueError("No prior valid mark for held stock")
        equity = acct.equity(mark)
        invested = equity - acct.cash
        benchmark = float(frames["SET50"].loc[day, "Close"])
        daily.append({"date": str(day.date()), "strategy": strategy, "scenario": scenario, "window": window["period_id"],
                      "equity": equity, "cash": acct.cash, "exposure": invested/equity, "benchmark_close": benchmark,
                      "max_weight": max((q * mark[s] / equity for s,q in acct.shares.items() if q), default=0)})
        for s,q in acct.shares.items():
            if q:
                holding_rows.append({"date": str(day.date()), "strategy": strategy, "scenario": scenario,
                                     "window": window["period_id"], "symbol": s, "shares": q, "close": mark[s], "weight": q*mark[s]/equity})
    base_open = float(frames["SET50"].loc[days[0], "Open"])
    benchmark_path = [base_open] + [x["benchmark_close"] for x in daily]
    equity_path = [float(par["initial_cash"])] + [x["equity"] for x in daily]
    net = equity_path[-1]/equity_path[0]-1
    bench = benchmark_path[-1]/benchmark_path[0]-1
    pnl = [x["pnl"] for x in acct.trips]
    nonzero = [x for x in pnl if abs(x) > 1e-9]
    payoff = float(np.mean(nonzero)) if nonzero else 0.0
    wins = [x for x in nonzero if x > 0]; losses = [x for x in nonzero if x < 0]
    dd = max_drawdown(equity_path); bd = max_drawdown(benchmark_path)
    exposure = float(np.mean([x["exposure"] for x in daily]))
    checks = eligibility(dd, bd, len(acct.trips), exposure, payoff, net, net-bench)
    summary = {"window": window["period_id"], "role": window["role"], "strategy": strategy, "scenario": scenario, "exit_rule": exit_rule,
               "net_return": net, "gross_return_proxy": (equity_path[-1]+acct.fees+acct.vat+acct.slippage)/equity_path[0]-1,
               "benchmark_return": bench, "excess_return": net-bench, "max_drawdown": dd, "benchmark_max_drawdown": bd,
               "drawdown_ratio": dd/bd if bd > 0 else np.nan, "calmar": net/dd if dd > 0 else np.nan,
               "volatility_daily": float(pd.Series(equity_path).pct_change().dropna().std()),
               "max_weight": max(x["max_weight"] for x in daily), "orders": len(acct.orders),
               "filled_orders": sum(x["filled"]>0 for x in acct.orders), "roundtrips": len(acct.trips),
               "win_rate": len(wins)/len(nonzero) if nonzero else 0,
               "avg_win_thb": float(np.mean(wins)) if wins else 0, "avg_loss_thb": -float(np.mean(losses)) if losses else 0,
               "expected_payoff_thb": payoff, "average_holding_calendar_days": float(np.mean([x["holding_sessions_proxy"] for x in acct.trips])) if acct.trips else np.nan,
               "turnover": acct.turnover_value/float(par["initial_cash"]), "commission_thb": acct.fees,
               "vat_thb": acct.vat, "slippage_thb": acct.slippage,
               "average_exposure": exposure, **checks}
    for x in acct.orders:
        x.update(window=window["period_id"], strategy=strategy, scenario=scenario, exit_rule=exit_rule)
    for x in acct.trips:
        x.update(window=window["period_id"], strategy=strategy, scenario=scenario, exit_rule=exit_rule)
    return summary, daily, holding_rows, acct.orders, acct.trips, requested_targets


def main():
    cfg_path = ROOT / "configs/preregistered.json"
    cfg = json.loads(cfg_path.read_text())
    schedule = json.loads((PHASE2 / "schedule.json").read_text())
    syms, cal, frames, audit = load_daily()
    data = (syms, cal, frames, {})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runid = stamp + "_" + sha256(cfg_path)[:8]
    out = ROOT / "results" / runid
    out.mkdir(parents=True)
    (out / "config.json").write_bytes(cfg_path.read_bytes())
    manifest = {"experiment_id": runid, "utc": stamp, "seed": cfg["seed"], "git_commit": None,
                "git_note": "repository has no commits and .git is read-only", "config_sha256": sha256(cfg_path),
                "schedule_sha256": sha256(PHASE2 / "schedule.json"), "source_hashes": {p.name: sha256(p) for p in [ROOT/"core.py", ROOT/"runner.py", ROOT/"reporting.py"]}, "data_hashes": dict(zip(audit.symbol, audit.sha256)),
                "command": "python -m research_set50_portfolio.runner"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    records = []
    def execute(windows, strategies, scenario="official", rule="scheduled", params=None):
        for w in windows:
            for s in strategies:
                records.append(run_window(w,s,data,cfg,scenario,rule,params))
    dev = [w for w in schedule if w["role"] == "development"]
    eva = [w for w in schedule if w["role"] == "evaluation"]
    execute(dev, ["A","B","C","D"])
    d = pd.DataFrame([r[0] for r in records])
    selected = sorted(["A","B","C","D"], key=lambda s: (-d.loc[d.strategy==s,"best_alpha_eligible"].mean(), -d.loc[d.strategy==s,"excess_return"].median(), s))[0]
    manifest["development_selected_e_base"] = selected
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    execute(eva, ["buy_hold","A","B","C","D","risk_only","E","sma_trend"], params={"e_base":selected})
    execute(eva, [selected], scenario="zero")
    execute(eva, [selected], scenario="two_ticks")
    execute(eva, [selected], scenario="half_fills")
    for rule in ["rank","trend_deterioration"]:
        execute(eva, [selected], rule=rule)
    # Small predeclared sensitivity grid, changed one parameter at a time.
    sensitivity = []
    for key, vals in {"holdings":[5,8], "rebalance_every":[2], "target_exposure":[.7,.85], "max_weight":[.18], "volatility_window":[10,30]}.items():
        for val in vals:
            for w in eva:
                s = run_window(w,selected,data,cfg,params={key:val})[0]
                s.update(parameter=key, value=val)
                sensitivity.append(s)
    pd.DataFrame(sensitivity).to_csv(out / "sensitivity.csv",index=False)
    for idx,name in enumerate(["windows","daily_equity","holdings","orders","fifo_roundtrips","targets"]):
        rows = [x for r in records for x in (r[idx] if idx else [r[0]])]
        pd.DataFrame(rows).to_csv(out / f"{name}.csv",index=False)
    wdf = pd.read_csv(out / "windows.csv")
    ev = wdf[(wdf.role=="evaluation") & (wdf.scenario=="official") & (wdf.exit_rule=="scheduled")]
    agg = ev.groupby("strategy").agg(windows=("net_return","size"), mean_net=("net_return","mean"),median_net=("net_return","median"),worst_net=("net_return","min"),mean_excess=("excess_return","mean"),median_excess=("excess_return","median"),positive_excess=("nonnegative_excess","mean"),mean_drawdown=("max_drawdown","mean"),common_pass=("common_eligible","mean"),best_alpha_pass=("best_alpha_eligible","mean"),mean_turnover=("turnover","mean"),mean_exposure=("average_exposure","mean"),mean_roundtrips=("roundtrips","mean"),mean_payoff_thb=("expected_payoff_thb","mean"),median_payoff_thb=("expected_payoff_thb","median"),mean_commission=("commission_thb","mean"),mean_vat=("vat_thb","mean"),mean_slippage=("slippage_thb","mean"))
    agg.to_csv(out / "comparison.csv")
    print(out)
    print(agg.to_string())

if __name__ == "__main__":
    main()
