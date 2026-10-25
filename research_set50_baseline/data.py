"""Read-only data access, validation, and reproducibility manifests."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import uuid

import numpy as np
import pandas as pd

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
MARKET = ROOT / "marketInfo"


def write_json(path, obj):
    """Strict JSON: NaN is forbidden so undefined metrics must be explicit nulls."""
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, default=str), encoding="utf-8")


def config(path=None):
    c = json.loads(Path(path or PACKAGE / "config.json").read_text(encoding="utf-8"))
    if c["initial_cash"] != 10_000_000 or c["lot_size"] != 100:
        raise ValueError("This workflow requires 10M capital and 100-share lots")
    if c["commission"] != .00157 or c["vat"] != .07:
        raise ValueError("Cost settings must match the supplied native engine")
    if not 0 < c["target_exposure"] <= 1 or not 0 < c["max_weight"] <= 1:
        raise ValueError("Invalid sizing settings")
    if c["lookback"] < 2 or c["holdings"] < 1 or c["rebalance_sessions"] < 1:
        raise ValueError("Invalid strategy settings")
    return c


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def provenance(c):
    """Hash the precise supplied inputs and implementation, not mutable mtimes."""
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in sorted(MARKET.rglob("*.csv"))}
    sources = {str(p.relative_to(ROOT)): digest(p)
               for folder in [ROOT / "tradeSim", ROOT / "strategy", PACKAGE]
               for p in sorted(folder.glob("*.py"))}
    versions = {}
    for name in ["numpy", "pandas", "matplotlib", "rich"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed in active path"
    plotting_env=PACKAGE/"plotting_environment.json"
    return dict(config=c, source_sha256=sources, data_sha256=inputs,
                plotting_environment=json.loads(plotting_env.read_text()) if plotting_env.exists() else None,
                python=sys.version, executable=sys.executable, packages=versions,
                source_identity=hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
                seed=c["seed"], timezone="Asia/Bangkok", created_utc=datetime.now(timezone.utc).isoformat())


def new_experiment(kind, c):
    """Exclusive creation prevents overwriting previous runs, including failed ones."""
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + kind + "_" + uuid.uuid4().hex[:8]
    path = PACKAGE / "experiments" / name
    path.mkdir(parents=True, exist_ok=False)
    write_json(path / "manifest.json", provenance(c))
    write_json(path / "config.json", c)
    checkpoint = path / "source"
    checkpoint.mkdir()
    for p in PACKAGE.glob("*.py"):
        (checkpoint / p.name).write_bytes(p.read_bytes())
    write_json(path / "status.json", {"status": "running", "kind": kind})
    return path


def read_history():
    """Keep supplied adjusted closes; flag row defects without altering originals.

    OHLC-invalid stock rows cannot enter features/execution. Index close use is
    allowed independently of an invalid Open/High: the known anomaly has a valid
    Close. No claim is made that current adjusted files are point-in-time vintages.
    """
    universe = pd.read_csv(MARKET / "symbolSET50/Symbol_SET50.csv").Symbol.tolist()
    history = {}
    for s in universe + ["SET50"]:
        d = pd.read_csv(MARKET / "daily_history" / (s + ".csv"))
        d["Date"] = pd.to_datetime(d.Date, errors="raise")
        if d.Date.duplicated().any():
            raise ValueError(f"Ambiguous duplicate daily dates: {s}")
        d = d.set_index("Date").sort_index()
        q = d[["Open", "High", "Low", "Close"]]
        finite = np.isfinite(q).all(axis=1) & np.isfinite(d.Volume)
        d["feature_valid"] = (finite & (q > 0).all(axis=1) & (d.Volume >= 0)
            & (d.High >= q.max(axis=1)) & (d.Low <= q.min(axis=1)))
        if s == "SET50":
            d["feature_valid"] = np.isfinite(d.Close) & (d.Close > 0)
        history[s] = d
    return universe, history, history["SET50"].index


def ticks(day):
    """Globally chronological stable replay; identical prints are retained."""
    d = pd.read_csv(MARKET / "ticks" / f"{day}.csv")
    d["TradeDateTime"] = pd.to_datetime(d.TradeDateTime, errors="raise")
    if not (d.TradeDateTime.dt.strftime("%Y-%m-%d") == day).all():
        raise ValueError(f"Tick date disagrees with filename: {day}")
    if not (np.isfinite(d.LastPrice) & (d.LastPrice > 0) & np.isfinite(d.Volume) & (d.Volume >= 0)).all():
        raise ValueError(f"Invalid execution observations: {day}")
    return d.sort_values("TradeDateTime", kind="stable")


def native_days(c):
    return [p.stem for p in sorted((MARKET / "ticks").glob("*.csv"))
            if c["native_start"] <= p.stem <= c["native_end"]]


def validate(output):
    """Inventory every CSV; retain stress and distinguish defective fields."""
    universe, history, calendar = read_history()
    rows, extremes, overlap = [], [], []
    for p in sorted(MARKET.rglob("*.csv")):
        if p.parent.name == "symbolSET50":
            continue
        d = pd.read_csv(p)
        col = next(x for x in ["Date", "Timestamp", "TradeDateTime"] if x in d)
        t = pd.to_datetime(d[col], errors="coerce")
        prices = [x for x in ["Open", "High", "Low", "Close", "LastPrice"] if x in d]
        q = d[prices].apply(pd.to_numeric, errors="coerce")
        bad_price = (~np.isfinite(q) | (q <= 0)).any(axis=1)
        ohlc = pd.Series(False, index=d.index)
        if "High" in d:
            ohlc = (d.High < q.max(axis=1)) | (d.Low > q.min(axis=1))
        bad_volume = (~np.isfinite(d.Volume) | (d.Volume < 0)) if "Volume" in d else pd.Series(False,index=d.index)
        row = dict(file=str(p.relative_to(MARKET)), rows=len(d), start=str(t.min()), end=str(t.max()),
                   duplicate_rows=int(d.duplicated().sum()), invalid_time=int(t.isna().sum()),
                   chronological=bool(t.is_monotonic_increasing), invalid_price=int(bad_price.sum()),
                   invalid_ohlc=int(ohlc.sum()), invalid_volume=int(bad_volume.sum()))
        if p.parent.name == "daily_history":
            row["duplicate_timestamps"] = int(t.duplicated().sum())
            expected = calendar[(calendar >= t.min()) & (calendar <= t.max())]
            row["missing_sessions"] = len(expected.difference(pd.DatetimeIndex(t)))
            row["missing_dates"] = ";".join(x.strftime("%Y-%m-%d") for x in expected.difference(pd.DatetimeIndex(t)))
            returns = d.Close.pct_change(fill_method=None)
            for i in d.index[returns.abs() > .25]:
                extremes.append(dict(symbol=p.stem, date=d.loc[i,"Date"], return_fraction=float(returns.loc[i]),
                                     treatment="retained; no evidence of erroneous close; corporate-action provenance unavailable"))
        if p.parent.name == "ticks":
            row["symbols"] = d.ShareCode.nunique()
            ordered = d.assign(_time=t).sort_values("_time", kind="stable")
            for s, g in ordered.groupby("ShareCode"):
                day = pd.Timestamp(p.stem)
                h = history.get(s)
                if h is not None and day in h.index:
                    overlap.append(dict(date=p.stem, symbol=s, tick_close=float(g.LastPrice.iloc[-1]),
                                        history_close=float(h.loc[day,"Close"]),
                                        difference=float(g.LastPrice.iloc[-1]-h.loc[day,"Close"])))
        rows.append(row)
    pd.DataFrame(rows).to_csv(output / "data_inventory.csv", index=False)
    pd.DataFrame(overlap).to_csv(output / "tick_history_overlap.csv", index=False)
    write_json(output / "extreme_returns.json", extremes)
    benchmark = pd.read_csv(MARKET / "benchmark/SET50.csv")
    summary = dict(files=len(rows), permitted_stocks=len(universe), daily_sessions=len(calendar),
        tick_sessions=len(list((MARKET / "ticks").glob("*.csv"))),
        invalid_ohlc=sum(r["invalid_ohlc"] for r in rows),
        invalid_price=sum(r["invalid_price"] for r in rows), invalid_volume=sum(r["invalid_volume"] for r in rows),
        invalid_time=sum(r["invalid_time"] for r in rows),
        tick_close_mismatches=sum(abs(r["difference"])>1e-8 for r in overlap),
        benchmark_history_mismatches=sum(abs(float(history["SET50"].loc[pd.Timestamp(r.Date),"Close"])-r.Close)>1e-8 for r in benchmark.itertuples()),
        extreme_returns=extremes)
    write_json(output / "data_quality.json", summary)
    text = "# Data quality report\n\n" + json.dumps(summary, indent=2) + "\n\n"
    text += ("Complete coverage and defect counts are in data_inventory.csv. Original inputs are never edited. "
        "Naive exchange timestamps are interpreted as Asia/Bangkok. Tick duplicate rows are retained because there are no trade IDs. "
        "The calendar is inferred from supplied SET50 observations, not an independently certified exchange calendar. "
        "Missing stock bars imply unavailable observations, not proven suspensions.\n\n"
        "Daily history is capital-action adjusted according to docs/get_historical_data.md. No adjustment ledger, dividend series, "
        "historical universe, or as-published vintages exist. The two large stock moves remain; neither has an invalid OHLC row, "
        "but no external event provenance is supplied. SET50 on 2025-12-11 has Open 840.26 above High 839.88; "
        "its positive Close 828.42 remains usable for close-only benchmark calculations.\n\n"
        "Native execution uses raw ticks. Daily research trades supplied adjusted prices with no dividends or share conversion events; "
        "historical lot sizes and price-dependent tick costs are therefore approximations. "
        "The historical and scoring SET50 files are separate sources; their overlap is checked above. "
        "SET50 is treated as a price index, not SET50 TRI; CSV provenance is not independently certified.\n")
    (output / "DATA_QUALITY_REPORT.md").write_text(text, encoding="utf-8")
    return summary
