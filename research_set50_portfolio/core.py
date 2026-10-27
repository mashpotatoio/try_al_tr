"""Point-in-time ranking, target allocation, execution, and FIFO accounting."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import bisect
import math
import numpy as np
import pandas as pd

TICKS = [0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.0, 2.0]
BREAKS = [2, 5, 10, 25, 100, 200, 400]


def tick(price: float) -> float:
    return TICKS[bisect.bisect(BREAKS, price)]


def signals(history: dict[str, pd.DataFrame], symbols: list[str], decision_date, vol_window=20):
    """Only bars through decision_date are accessed. Returned scores are raw returns."""
    rows = []
    for sym in symbols:
        f = history[sym].loc[:decision_date]
        if len(f) < max(61, vol_window + 1):
            continue
        p = f.Close.astype(float)
        v = f.Volume.astype(float)
        tail = f.iloc[-61:]
        if not (tail.valid.eq(True).all() and np.isfinite(p.iloc[-1])):
            continue
        vol = p.pct_change().iloc[-vol_window:].std()
        prior_volume = v.iloc[-20:].mean()
        if not (np.isfinite(vol) and vol > 0 and prior_volume > 0):
            continue
        rows.append({"symbol": sym, "mom20": p.iloc[-1] / p.iloc[-21] - 1,
                     "sma20_sma60": p.iloc[-20:].mean() / p.iloc[-60:].mean() - 1,
                     "reversal1": 1 - p.iloc[-1] / p.iloc[-2], "vol": vol,
                     "prior_volume": prior_volume})
    return pd.DataFrame(rows).set_index("symbol") if rows else pd.DataFrame()


def rank(frame: pd.DataFrame, primary="mom20", tie=False, gap=0.05):
    """Reversal resolves only adjacent primary percentile ranks within gap."""
    if frame.empty:
        return []
    ordered = frame.sort_values([primary], ascending=False, kind="stable").copy()
    if not tie:
        return list(ordered.index)
    n = len(ordered)
    # Every member must remain within the threshold of the group's strongest score.
    scores = ordered[primary].to_numpy()
    span = max(float(np.nanmax(scores) - np.nanmin(scores)), 1e-12)
    groups, start = [], 0
    for i in range(1, n):
        if (scores[start] - scores[i]) / span > gap:
            groups.append(ordered.iloc[start:i])
            start = i
    groups.append(ordered.iloc[start:])
    return [s for g in groups for s in g.sort_values("reversal1", ascending=False, kind="stable").index]


def weights(names, frame, method, exposure, cap):
    if not names:
        return {}
    raw = np.ones(len(names)) if method == "equal" else 1 / np.maximum(frame.loc[names, "vol"].to_numpy(), 1e-4)
    # Iterative cap with redistribution; cash remains if cap prevents full exposure.
    out = np.zeros(len(names))
    remaining = list(range(len(names)))
    budget = min(exposure, 1.0)
    while remaining and budget > 1e-12:
        parts = budget * raw[remaining] / raw[remaining].sum()
        capped = [j for j, p in zip(remaining, parts) if p > cap]
        if not capped:
            for j, p in zip(remaining, parts):
                out[j] = p
            break
        for j in capped:
            out[j] = cap
            budget -= cap
            remaining.remove(j)
    return dict(zip(names, out))


@dataclass
class Account:
    cash: float = 10_000_000.0
    shares: dict = field(default_factory=lambda: defaultdict(int))
    lots: dict = field(default_factory=lambda: defaultdict(deque))
    orders: list = field(default_factory=list)
    trips: list = field(default_factory=list)
    fees: float = 0.0
    vat: float = 0.0
    slippage: float = 0.0
    turnover_value: float = 0.0

    def trade(self, date, sym, side, requested, open_price, cap_shares, commission=.00157, vat_rate=.07, ticks=1, fill_fraction=1):
        assert requested >= 0 and requested % 100 == 0
        event = {"date": str(date.date()), "symbol": sym, "side": side, "requested": requested,
                 "accepted": 0, "filled": 0, "status": "skipped", "open": open_price}
        self.orders.append(event)
        if not np.isfinite(open_price) or open_price <= 0:
            event["status"] = "missing_open"; return
        qty = min(requested, int(cap_shares // 100) * 100)
        if side == "sell":
            qty = min(qty, self.shares[sym])
        price = open_price + (1 if side == "buy" else -1) * ticks * tick(open_price)
        if price <= 0:
            event["status"] = "bad_price"; return
        if side == "buy":
            affordable = int(self.cash / (price * (1 + commission * (1 + vat_rate))) // 100) * 100
            qty = min(qty, affordable)
        event["accepted"] = qty
        qty = int(qty * fill_fraction // 100) * 100
        if qty <= 0:
            event["status"] = "no_fill"; return
        gross = qty * price
        fee = gross * commission
        tax = fee * vat_rate
        self.fees += fee; self.vat += tax
        self.slippage += qty * ticks * tick(open_price)
        self.turnover_value += qty * open_price
        if side == "buy":
            self.cash -= gross + fee + tax
            self.shares[sym] += qty
            self.lots[sym].append([qty, (gross + fee + tax) / qty, date, 0.0, qty])
        else:
            self.cash += gross - fee - tax
            self.shares[sym] -= qty
            remaining = qty
            while remaining:
                lot = self.lots[sym][0]
                matched = min(remaining, lot[0])
                lot[0] -= matched; remaining -= matched
                lot[3] += matched * ((gross - fee - tax) / qty - lot[1])
                if lot[0] == 0:
                    # Native engine counts a completed original FIFO lot, including partial sales.
                    self.trips.append({"symbol": sym, "buy_date": str(lot[2].date()),
                                       "sell_date": str(date.date()), "shares": lot[4],
                                       "pnl": lot[3],
                                       "holding_sessions_proxy": (date-lot[2]).days})
                    self.lots[sym].popleft()
        event.update(filled=qty, status="filled" if qty == requested else "partial",
                     price=price, commission=fee, vat=tax, slippage=qty * ticks * tick(open_price))
        assert self.cash >= -1e-6 and self.shares[sym] >= 0 and self.shares[sym] % 100 == 0

    def equity(self, prices):
        return self.cash + sum(q * prices[s] for s, q in self.shares.items() if q)


def max_drawdown(values):
    a = np.asarray(values, dtype=float)
    if len(a) == 0 or np.any(~np.isfinite(a)):
        return math.nan
    return float(np.max(1 - a / np.maximum.accumulate(a)))


def eligibility(port_dd, bench_dd, trips, exposure, payoff, net, excess):
    checks = {"drawdown_pass": bool(np.isfinite(port_dd) and np.isfinite(bench_dd) and bench_dd > 0 and port_dd < 1.5 * bench_dd and not math.isclose(port_dd, 1.5 * bench_dd, rel_tol=1e-12, abs_tol=1e-12)),
              "roundtrip_pass": trips >= 5, "exposure_pass": exposure >= .5,
              "payoff_pass": payoff > 0, "nonnegative_return": net >= 0, "nonnegative_excess": excess >= 0}
    checks["common_eligible"] = all(checks[k] for k in list(checks)[:4])
    checks["best_alpha_eligible"] = checks["common_eligible"] and checks["nonnegative_return"] and checks["nonnegative_excess"]
    return checks
