"""Read source files without modifying them; audit exact coverage and defects."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / "marketInfo"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_daily() -> tuple[list[str], pd.DatetimeIndex, dict[str, pd.DataFrame], pd.DataFrame]:
    """Return currently permitted symbols, common benchmark calendar, aligned frames, audit rows."""
    symbols = sorted(pd.read_csv(MARKET / "symbolSET50/Symbol_SET50.csv")["Symbol"].tolist())
    raw = {}
    audit = []
    for symbol in [*symbols, "SET50"]:
        path = MARKET / "daily_history" / f"{symbol}.csv"
        frame = pd.read_csv(path, parse_dates=["Date"])
        duplicate_dates = int(frame.Date.duplicated().sum())
        if duplicate_dates:
            raise ValueError(f"Duplicate dates: {symbol}")
        frame = frame.set_index("Date").sort_index()
        prices = frame[["Open", "High", "Low", "Close"]]
        finite = pd.Series(np.isfinite(prices).all(axis=1) & np.isfinite(frame.Volume), index=frame.index)
        valid = finite & (prices > 0).all(axis=1) & (frame.Volume >= 0)
        ohlc = (frame.High >= prices.max(axis=1)) & (frame.Low <= prices.min(axis=1))
        frame["valid"] = valid & ohlc
        if symbol == "SET50":
            frame["close_valid"] = np.isfinite(frame.Close) & (frame.Close > 0)
        raw[symbol] = frame
    calendar = pd.DatetimeIndex(raw["SET50"].index)
    aligned = {}
    for symbol, original in raw.items():
        frame = original.reindex(calendar)
        aligned[symbol] = frame
        missing = int(frame.Open.isna().sum())
        zero_volume = int((frame.Volume == 0).sum())
        audit.append({"symbol": symbol, "rows": len(original), "first": str(original.index.min().date()),
                      "last": str(original.index.max().date()), "missing_calendar_sessions": missing,
                      "duplicate_dates": 0, "invalid_ohlc_rows": int((~original.valid).sum()),
                      "zero_volume_rows": zero_volume, "sha256": sha256(MARKET / "daily_history" / f"{symbol}.csv")})
    return symbols, calendar, aligned, pd.DataFrame(audit)


def source_hashes() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(MARKET.rglob("*.csv"))}


def verify_phase1_manifest() -> dict[str, object]:
    manifest = json.loads((ROOT / "phase1_prephase2_sha256.json").read_text(encoding="utf-8"))
    changed = []
    for name, expected in manifest.items():
        if name in {".gitignore", "phase1_prephase2_sha256.json"}:
            continue  # Git exclusions changed, and a manifest cannot hash its own final bytes.
        path = ROOT / name
        if not path.exists() or sha256(path) != expected:
            changed.append(name)
    return {"files_checked": len(manifest) - 2, "changed": changed}
