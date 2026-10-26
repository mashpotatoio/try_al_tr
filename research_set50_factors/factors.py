"""Completed-session daily factors and point-in-time market regimes."""
from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_rsi(close: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """Wilder smoothing, seeded from the first n returns of each uninterrupted history."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    # EWM with adjust=False differs at initialization; explicit recursion is used.
    out = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    for symbol in close:
        values = close[symbol].to_numpy(dtype=float)
        result = np.full(len(values), np.nan)
        ag = al = np.nan
        for i in range(n, len(values)):
            if not np.isfinite(values[i-n:i+1]).all():
                ag = al = np.nan
                continue
            if np.isnan(ag):
                changes = np.diff(values[i-n:i+1])
                ag, al = np.maximum(changes, 0).mean(), np.maximum(-changes, 0).mean()
            else:
                change = values[i] - values[i-1]
                ag = ((n-1)*ag + max(change, 0))/n
                al = ((n-1)*al + max(-change, 0))/n
            if ag == al == 0:
                continue
            result[i] = 100 if al == 0 else 100 - 100/(1 + ag/al)
        out[symbol] = result
    return out


def make_factors(symbols: list[str], calendar: pd.DatetimeIndex, daily: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """All factor values at t use completed bars no later than t."""
    close = pd.DataFrame({s: daily[s].Close.where(daily[s].valid & (daily[s].Volume > 0)) for s in symbols}, index=calendar)
    high = pd.DataFrame({s: daily[s].High.where(daily[s].valid) for s in symbols}, index=calendar)
    low = pd.DataFrame({s: daily[s].Low.where(daily[s].valid) for s in symbols}, index=calendar)
    volume = pd.DataFrame({s: daily[s].Volume.where(daily[s].valid & (daily[s].Volume > 0)) for s in symbols}, index=calendar)
    benchmark = daily["SET50"].Close.where(daily["SET50"].close_valid)
    ret = close.pct_change(fill_method=None)
    bench_ret = benchmark.pct_change(fill_method=None)
    factors = {}
    for n in [3, 5, 10, 20]:
        mom = close / close.shift(n) - 1
        valid_path = close.notna().rolling(n+1, min_periods=n+1).sum().eq(n+1)
        mom = mom.where(valid_path)
        factors[f"mom_{n}"] = mom
        bm = (benchmark / benchmark.shift(n)-1).where(benchmark.notna().rolling(n+1, min_periods=n+1).sum().eq(n+1))
        factors[f"relative_{n}"] = mom.sub(bm, axis=0)
    for n in [1, 3, 5]:
        if n == 1:
            m = ret
        else:
            m = factors[f"mom_{n}"]
        factors[f"reversal_{n}"] = -m
    factors["rsi14_oversold"] = 100 - wilder_rsi(close, 14)
    sma20 = close.rolling(20, min_periods=20).mean()
    sma60 = close.rolling(60, min_periods=60).mean()
    factors["ma20_reversion"] = -(close/sma20-1)
    vol10 = ret.rolling(10, min_periods=10).std(ddof=1)
    vol20 = ret.rolling(20, min_periods=20).std(ddof=1)
    factors["low_vol_10"] = -vol10
    factors["low_vol_20"] = -vol20
    prev = close.shift(1)
    tr = pd.DataFrame(np.maximum.reduce([(high-low).to_numpy(), (high-prev).abs().to_numpy(), (low-prev).abs().to_numpy()]), index=calendar, columns=symbols)
    factors["low_atr14"] = -(tr.rolling(14, min_periods=14).mean()/close)
    factors["vol_normalized_mom5"] = factors["mom_5"] / vol20.where(vol20 > 0)
    factors["vol_normalized_mom20"] = factors["mom_20"] / vol20.where(vol20 > 0)
    avg20 = volume.shift(1).rolling(20, min_periods=20).mean()
    factors["volume_surprise"] = volume / avg20.where(avg20 > 0)
    factors["volume_5_20"] = volume.rolling(5, min_periods=5).mean() / volume.rolling(20, min_periods=20).mean()
    factors["price_volume_confirmation"] = factors["mom_5"] * factors["volume_surprise"]
    factors["log_trading_value20"] = np.log((close*volume).rolling(20, min_periods=20).mean().where(lambda x:x>0))
    factors["above_sma20"] = close/sma20-1
    factors["sma20_above_sma60"] = sma20/sma60-1
    factors["trend_strength5"] = sma20/sma20.shift(5)-1
    regimes = pd.DataFrame(index=calendar)
    regimes["benchmark_above_sma60"] = (benchmark > benchmark.rolling(60, min_periods=60).mean()).astype(object)
    regimes["benchmark_mom20_positive"] = (benchmark/benchmark.shift(20)-1 > 0).astype(object)
    bv = bench_ret.rolling(20, min_periods=20).std()
    regimes["benchmark_vol20_high_past_median"] = (bv > bv.shift(1).expanding(min_periods=40).median()).astype(object)
    regimes.loc[benchmark.rolling(60, min_periods=60).count()<60, "benchmark_above_sma60"] = np.nan
    regimes.loc[benchmark.rolling(21, min_periods=21).count()<21, "benchmark_mom20_positive"] = np.nan
    regimes.loc[bv.shift(1).expanding(min_periods=40).count()<40, "benchmark_vol20_high_past_median"] = np.nan
    for name, frame in factors.items():
        factors[name] = frame.replace([np.inf, -np.inf], np.nan)
    return factors, regimes, pd.DataFrame({"benchmark_close":benchmark, "benchmark_return":bench_ret}, index=calendar)
