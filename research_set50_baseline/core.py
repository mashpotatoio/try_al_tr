"""Pure financial logic shared by tick execution and daily research.

Prices are THB/share, weights and returns are fractions, and fees are THB.
Keeping these functions independent of the engine makes mistakes testable.
"""
from bisect import bisect_right
from collections import defaultdict, deque
import math

import numpy as np
import pandas as pd


def tick_size(price):
    """SET common-share price ladder; exact boundaries enter the higher band."""
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Price must be finite and positive")
    return [0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.0, 2.0][
        bisect_right([2, 5, 10, 25, 100, 200, 400], price)]


def fill_price(price, side):
    """One adverse tick, matching native Market semantics (including boundaries)."""
    if side not in ("Buy", "Sell"):
        raise ValueError(side)
    return price + tick_size(price) * (1 if side == "Buy" else -1)


def costs(notional, config):
    """Return commission and VAT separately; VAT is charged on commission."""
    commission = notional * config["commission"]
    return commission, commission * config["vat"]


def rsi_wilder(close, period=14):
    """Return the latest RSI from completed closes, or None with too little history.

    The first gain/loss average uses a simple mean over ``period`` changes;
    later observations use Wilder's recursive smoothing. The caller controls
    the information cutoff, so a current unfinished daily bar is never read.
    """
    values = np.asarray(close, dtype=float)
    changes = np.diff(values)
    if len(changes) < period or not np.isfinite(changes).all():
        return None
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + float(gain)) / period
        avg_loss = ((period - 1) * avg_loss + float(loss)) / period
    if avg_gain == 0 and avg_loss == 0:
        return None
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    relative_strength = avg_gain / avg_loss
    return float(100 - 100 / (1 + relative_strength))


def lots(quantity, lot=100):
    """Round down, never up: rounding up can borrow cash or exceed holdings."""
    return int(max(0, quantity) // lot) * lot


def capped_weights(raw, exposure, cap):
    """Allocate proportional weights with iterative caps; infeasible mass is cash.

    Inputs are positive scores (1/volatility or 1). Output weights never sum
    above exposure. No leverage is introduced when n * cap < exposure.
    """
    if not 0 <= exposure <= 1 or not 0 < cap <= 1:
        raise ValueError("Invalid exposure/cap")
    if any(not math.isfinite(v) or v <= 0 for v in raw.values()):
        raise ValueError("Sizing scores must be finite and positive")
    remaining = min(exposure, len(raw) * cap)
    active = dict(sorted(raw.items()))
    result = {}
    while active:
        total = sum(active.values())
        proposed = {s: remaining * v / total for s, v in active.items()}
        bound = [s for s, w in proposed.items() if w > cap + 1e-12]
        if not bound:
            result.update(proposed)
            break
        for s in bound:
            result[s] = cap
            remaining -= cap
            del active[s]
    return result


def features(history, calendar, date, symbols, lookback):
    """Build aligned features strictly before date using lookback+1 closes.

    Reindex to the common SET50 session calendar rather than counting each
    stock's available rows: a suspension must not shorten a return interval.
    No current-day close, backfill, or filling of missing returns is allowed.
    """
    dates = calendar[calendar < pd.Timestamp(date)][-(lookback + 1):]
    if len(dates) < lookback + 1:
        return pd.DataFrame()
    index_close = history["SET50"].reindex(dates).Close
    if index_close.isna().any() or (index_close <= 0).any():
        return pd.DataFrame()
    benchmark = index_close.iloc[-1] / index_close.iloc[0] - 1
    rows = []
    for symbol in sorted(symbols):
        d = history[symbol].reindex(dates)
        c = d.Close
        if c.isna().any() or (c <= 0).any() or not d.feature_valid.all():
            continue
        if d.Volume.iloc[-1] <= 0:
            continue
        momentum = c.iloc[-1] / c.iloc[0] - 1
        vol = c.pct_change(fill_method=None).iloc[1:].std(ddof=1)
        if not math.isfinite(vol):
            continue
        rsi = rsi_wilder(c.to_numpy(dtype=float), 14)
        rows.append(dict(symbol=symbol, momentum=momentum,
                         relative_strength=momentum - benchmark, volatility=vol,
                         rsi14=rsi,
                         close=float(c.iloc[-1]), feature_start=str(dates[0].date()),
                         feature_end=str(dates[-1].date())))
    return pd.DataFrame(rows)


def select_targets(strategy, table, config):
    """Scores -> selected symbols -> feasible weights, without execution effects.

    Relative strength subtracts one identical index return and therefore does
    not add a distinct ranking signal. Relative-equal is the sizing control.
    """
    if table.empty:
        return {}, []
    score = "relative_strength" if strategy.startswith("relative") else "momentum"
    if strategy == "rsi_oversold":
        # RSI is a transparent contrarian baseline: lower oversold readings rank first.
        selected = table[table.rsi14.notna() & (table.rsi14 < config["rsi_threshold"])]
        selected = selected.sort_values(["rsi14", "symbol"], ascending=[True, True])
    else:
        selected = table.sort_values([score, "symbol"], ascending=[False, True])
    if strategy == "buy_hold":
        selected = table.sort_values("symbol")
    if strategy != "buy_hold":
        selected = selected.head(config["holdings"])
    raw = {r.symbol: (1 / max(r.volatility, config["volatility_floor"])
                      if strategy == "relative_vol" else 1.0)
           for r in selected.itertuples()}
    cap = 1.0 if strategy == "buy_hold" else config["max_weight"]
    return capped_weights(raw, config["target_exposure"], cap), selected.symbol.tolist()


def feasible_buy(wanted, price, cash, reserved, held, equity, cap, config):
    """Reduce a requested buy for fees, pending cash, and the position cap.

    price is already the anticipated fill, so slippage is not charged twice.
    Outstanding orders reserve worst-case cash outside the native engine.
    """
    fee = config["commission"] * (1 + config["vat"])
    affordable = max(0, cash - reserved) / (price * (1 + fee))
    room = max(0, equity * cap / price - held)
    return lots(min(wanted, affordable, room), config["lot_size"])


class Ledger:
    """Fill-driven cash and FIFO accounting, independent of order submissions.

    One buy order creates one original lot; partial fills extend that lot.
    A partially sold lot accumulates P&L but counts as a round-trip only once
    its original quantity has closed. Costs belong to their actual fills.
    """
    def __init__(self, cash, config):
        self.initial_cash = self.cash = float(cash)
        self.config = config
        self.positions = defaultdict(deque)
        self.fills = []
        self.round_trips = []
        self.pending = {}
        self.seen_fills = set()

    def quantity(self, symbol):
        return sum(x["remaining"] for x in self.positions[symbol])

    def quantities(self):
        return {s: self.quantity(s) for s in self.positions if self.quantity(s)}

    def reserve(self, order_id, symbol, side, quantity, limit):
        """Reserve worst-case buy cash or sell shares until fill/cancel/reject."""
        if quantity <= 0 or quantity % self.config["lot_size"]:
            raise ValueError("Invalid order quantity")
        amount = quantity * limit * (1 + self.config["commission"] * (1+self.config["vat"]))
        if side == "Buy" and amount > self.cash - self.reserved_cash() + 1e-7:
            raise ValueError("Insufficient unreserved cash")
        if side == "Sell":
            pending = sum(p["quantity"] for p in self.pending.values()
                          if p["symbol"] == symbol and p["side"] == "Sell")
            if quantity + pending > self.quantity(symbol):
                raise ValueError("Insufficient unreserved holdings")
        self.pending[order_id] = dict(symbol=symbol, side=side, quantity=quantity, limit=limit)

    def reserved_cash(self):
        rate = 1 + self.config["commission"] * (1 + self.config["vat"])
        return sum(p["quantity"] * p["limit"] * rate for p in self.pending.values() if p["side"] == "Buy")

    def cancel(self, order_id):
        """Cancel/reject releases only unfilled commitments; holdings do not move."""
        return self.pending.pop(order_id, None)

    def fill(self, order_id, symbol, side, quantity, price, timestamp, market_price=None, fill_id=None):
        """Apply a confirmed fill once. Returns False for duplicate fill IDs."""
        fill_id = fill_id or order_id
        if fill_id in self.seen_fills:
            return False
        if quantity <= 0 or quantity % self.config["lot_size"] or price <= 0:
            raise ValueError("Invalid fill")
        notional = quantity * price
        commission, vat = costs(notional, self.config)
        fee = commission + vat
        if side == "Buy":
            if notional + fee > self.cash + 1e-6:
                raise AssertionError("Fill would borrow cash")
            self.cash -= notional + fee
            existing = next((x for x in self.positions[symbol] if x["order_id"] == order_id), None)
            if existing:
                if existing["remaining"] != existing["original"]:
                    raise ValueError("Cannot extend a lot already partially sold")
                n = existing["original"] + quantity
                existing["unit_cost"] = (existing["unit_cost"] * existing["original"] + notional + fee) / n
                existing["original"] = existing["remaining"] = n
            else:
                self.positions[symbol].append(dict(order_id=order_id, symbol=symbol,
                    original=quantity, remaining=quantity, unit_cost=(notional+fee)/quantity,
                    realized_pnl=0.0, opened=str(timestamp)))
        elif side == "Sell":
            if quantity > self.quantity(symbol):
                raise AssertionError("Fill would short stock")
            self.cash += notional - fee
            remaining = quantity
            unit_proceeds = (notional - fee) / quantity
            while remaining:
                lot = self.positions[symbol][0]
                matched = min(remaining, lot["remaining"])
                lot["realized_pnl"] += matched * (unit_proceeds - lot["unit_cost"])
                lot["remaining"] -= matched
                remaining -= matched
                if not lot["remaining"]:
                    closed = dict(self.positions[symbol].popleft())
                    closed.update(closed=str(timestamp), close_order=order_id)
                    self.round_trips.append(closed)
        else:
            raise ValueError(side)
        if order_id in self.pending:
            self.pending[order_id]["quantity"] -= quantity
            if self.pending[order_id]["quantity"] <= 0:
                self.cancel(order_id)
        self.seen_fills.add(fill_id)
        self.fills.append(dict(order_id=order_id, fill_id=fill_id, symbol=symbol, side=side,
            quantity=quantity, price=price, timestamp=str(timestamp), notional=notional,
            commission=commission, vat=vat, market_price=market_price,
            slippage_thb=(abs(price-market_price)*quantity if market_price is not None else None)))
        return True

    def equity(self, marks):
        """Value only held stocks, requiring an explicit current or stale mark."""
        return self.cash + sum(n * marks[s] for s, n in self.quantities().items())


def maximum_drawdown(values):
    """Positive peak-to-trough fraction; undefined for missing/nonpositive equity."""
    a = np.asarray(values, dtype=float)
    if not len(a) or not np.isfinite(a).all() or (a <= 0).any():
        return None
    return float(np.max(1 - a / np.maximum.accumulate(a)))
