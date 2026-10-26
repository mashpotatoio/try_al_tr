"""Open-to-open forward labels on the common trading-session calendar."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_labels(symbols: list[str], calendar: pd.DatetimeIndex, daily: dict[str, pd.DataFrame], horizons: list[int]) -> tuple[dict[int, pd.DataFrame], dict[int, pd.Series], pd.DataFrame]:
    opens = pd.DataFrame({s: daily[s].Open.where(daily[s].valid & (daily[s].Volume > 0)) for s in symbols}, index=calendar)
    index_open = daily["SET50"].Open.where(daily["SET50"].valid)
    labels, benchmark = {}, {}
    for h in horizons:
        # A label at t requires valid opens from t+1 through t+1+h, inclusive.
        entry, exit_ = opens.shift(-1), opens.shift(-(h+1))
        path = opens.notna().iloc[::-1].rolling(h+1, min_periods=h+1).sum().iloc[::-1].shift(-1).eq(h+1)
        labels[h] = (exit_/entry-1).where(path)
        bp = index_open.notna().iloc[::-1].rolling(h+1, min_periods=h+1).sum().iloc[::-1].shift(-1).eq(h+1)
        benchmark[h] = (index_open.shift(-(h+1))/index_open.shift(-1)-1).where(bp)
    timeline = pd.DataFrame({"signal_date":calendar, "latest_observation":calendar,
                             "earliest_entry":pd.Series(calendar, index=calendar).shift(-1).to_numpy()}, index=calendar)
    return labels, benchmark, timeline
