"""Backtester for the APEX strategy.

Fetches daily bars from Alpaca, replays the exact strategy.py decision rules,
executes at next day's open with slippage, and reports performance vs SPY.

Usage:  python backtest.py [--start 2024-01-01] [--end 2026-08-28]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpaca_client
import config
import risk
import strategy

WARMUP = config.REGIME_SMA + 5


def fetch_all(symbols, start, end):
    """Return {symbol: DataFrame(o,h,l,c,v) indexed by date}."""
    out = {}
    for sym in symbols:
        bars = alpaca_client.get_bars(sym, "1Day", start=start, end=end)
        if not bars:
            print(f"  [warn] no bars for {sym}, dropped from universe")
            continue
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["t"]).dt.tz_convert("America/New_York").dt.date
        df = df.set_index("date")[["o", "h", "l", "c", "v"]].sort_index()
        out[sym] = df
        print(f"  {sym}: {len(df)} bars  {df.index[0]} -> {df.index[-1]}")
    return out


def run(data, start_cash=100_000.0):
    spy = data[config.REGIME_SYMBOL]
    dates = list(spy.index)
    closes = {s: df["c"] for s, df in data.items()}
    opens = {s: df["o"] for s, df in data.items()}

    cash = start_cash
    positions = {}  # sym -> {qty, entry_price, highest_close, atr_at_entry, sleeve}
    trades = []
    equity_curve = []
    slip = config.SLIPPAGE_BPS / 10_000.0

    # precompute bar-dict lists once (O(1) per-day slicing afterwards)
    bar_lists = {
        sym: [{"o": r.o, "h": r.h, "l": r.l, "c": r.c, "v": r.v}
              for r in df.itertuples()]
        for sym, df in data.items()
    }

    def bars_upto(sym, i):
        return bar_lists[sym][: i + 1]

    def open_position(sym, qty, px, exec_date, close_px, atr_val, sleeve):
        nonlocal cash
        cost = qty * px
        if qty <= 0 or cost > cash:
            return
        cash -= cost
        positions[sym] = {"qty": qty, "entry_price": px, "entry_date": str(exec_date),
                          "highest_close": close_px, "atr_at_entry": atr_val,
                          "sleeve": sleeve}

    def close_position(sym, px, exec_date, reason):
        nonlocal cash
        pos = positions.pop(sym)
        cash += pos["qty"] * px
        pnl = (px - pos["entry_price"]) * pos["qty"]
        trades.append({"symbol": sym, "sleeve": pos["sleeve"],
                       "exit_date": str(exec_date), "exit_price": round(px, 2),
                       "pnl": round(pnl, 2), "exit_reason": reason,
                       **{k: pos[k] for k in ("entry_date", "entry_price", "qty")}})

    for i in range(WARMUP, len(dates) - 1):
        d = dates[i]
        # --- build signal inputs from completed bars up to today ---
        bars_by_sym = {}
        for sym in data:
            if dates[i] in data[sym].index and i >= config.MOM_SLOW + 1:
                bars_by_sym[sym] = bars_upto(sym, i)
        spy_bars = bars_upto(config.REGIME_SYMBOL, i)
        on = strategy.regime_on(spy_bars)
        scores = strategy.rank_universe(bars_by_sym)
        core_set = strategy.core_targets(scores, on) if config.MODE != "pullback_only" else set()
        exec_date = dates[i + 1]

        # --- exits (evaluated at close, executed next open) ---
        for sym in list(positions):
            if sym not in bars_by_sym:
                continue
            ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
            pos = positions[sym]
            pos["highest_close"] = max(pos["highest_close"], ev["close"])
            stop = risk.trailing_stop(pos["highest_close"], pos["atr_at_entry"])
            reason = None
            if stop is not None and ev["close"] < stop:
                reason = f"trailing stop ({stop:.2f})"
            elif pos["sleeve"] == "core":
                if sym not in core_set:
                    reason = "core rotation" if on else "regime off"
            else:  # pullback sleeve
                if ev["rsi_exit"]:
                    reason = f"RSI2 {ev['rsi2']:.0f} >= {config.RSI_EXIT}"
                elif ev["mom_exit"]:
                    reason = "momentum decay"
            if reason:
                close_position(sym, opens[sym].loc[exec_date] * (1 - slip),
                               exec_date, reason)

        # --- entries ---
        equity = cash + sum(p["qty"] * closes[s].loc[d] for s, p in positions.items())
        pos_value = sum(p["qty"] * closes[s].loc[d] for s, p in positions.items())
        can_open, _why = risk.portfolio_guard(equity, pos_value, len(positions))
        if on and can_open:
            # core sleeve: hold every core target
            n_core = sum(1 for p in positions.values() if p["sleeve"] == "core")
            for sym in sorted(core_set, key=lambda s: -scores[s]):
                if sym in positions or n_core >= config.CORE_SLOTS:
                    continue
                ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
                qty = risk.position_size(equity, ev["close"], ev["atr"])
                px = opens[sym].loc[exec_date] * (1 + slip)
                before = len(positions)
                open_position(sym, qty, px, exec_date, ev["close"], ev["atr"], "core")
                if len(positions) > before:
                    n_core += 1
            # pullback sleeve: deepest RSI(2) dips in eligible leaders
            n_pb = sum(1 for p in positions.values() if p["sleeve"] == "pullback")
            cands = []
            for sym in (bars_by_sym if config.MODE != "core_only" else {}):
                if sym in positions or sym == config.REGIME_SYMBOL:
                    continue
                ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
                if ev["entry"]:
                    cands.append(ev)
            cands.sort(key=lambda e: e["rsi2"])  # deepest pullback first
            for ev in cands:
                if n_pb >= config.PULLBACK_SLOTS:
                    break
                qty = risk.position_size(equity, ev["close"], ev["atr"])
                px = opens[ev["symbol"]].loc[exec_date] * (1 + slip)
                before = len(positions)
                open_position(ev["symbol"], qty, px, exec_date, ev["close"],
                              ev["atr"], "pullback")
                if len(positions) > before:
                    n_pb += 1

        # --- mark to market ---
        equity = cash + sum(p["qty"] * closes[s].loc[d] for s, p in positions.items())
        equity_curve.append({"date": str(d), "equity": round(equity, 2),
                             "n_positions": len(positions), "regime_on": on})

    return pd.DataFrame(equity_curve), pd.DataFrame(trades)


def stats(eq, trades, start_cash=100_000.0):
    e = eq["equity"].astype(float)
    rets = e.pct_change().dropna()
    total = e.iloc[-1] / start_cash - 1
    years = len(e) / 252.0
    cagr = (e.iloc[-1] / start_cash) ** (1 / years) - 1 if years > 0 else np.nan
    sharpe = rets.mean() / rets.std() * math.sqrt(252) if rets.std() > 0 else 0
    downside = rets[rets < 0]
    sortino = rets.mean() / downside.std() * math.sqrt(252) if len(downside) and downside.std() > 0 else 0
    peak = e.cummax()
    maxdd = ((e - peak) / peak).min()
    out = {"total_return": f"{total:+.1%}", "CAGR": f"{cagr:+.1%}",
           "sharpe": f"{sharpe:.2f}", "sortino": f"{sortino:.2f}",
           "max_drawdown": f"{maxdd:.1%}", "final_equity": f"${e.iloc[-1]:,.0f}"}
    if len(trades):
        p = trades["pnl"].astype(float)
        wins = p[p > 0]
        out.update({
            "trades": len(p), "win_rate": f"{len(wins)/len(p):.0%}",
            "avg_win": f"${wins.mean():,.0f}" if len(wins) else "-",
            "avg_loss": f"${p[p<=0].mean():,.0f}" if len(p[p <= 0]) else "-",
            "profit_factor": f"{wins.sum()/abs(p[p<=0].sum()):.2f}" if len(p[p <= 0]) and p[p <= 0].sum() != 0 else "inf"})
    return out


def make_chart(eq, trades, bench, path):
    sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
    from daimon_runtime import setup_plot
    import matplotlib.pyplot as plt
    setup_plot()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    x = pd.to_datetime(eq["date"])
    ax = axes[0]
    ax.plot(x, eq["equity"], label="APEX strategy", lw=1.8, color="#6C5CE7")
    bx = pd.to_datetime(bench.index.astype(str))
    bv = bench["c"] / bench["c"].iloc[0] * eq["equity"].iloc[0]
    ax.plot(bx, bv, label="SPY buy & hold", lw=1.2, color="#B2BEC3")
    if len(trades):
        tw = trades[trades["pnl"] > 0]
        tl = trades[trades["pnl"] <= 0]
        eqmap = eq.set_index("date")["equity"]
        for t, c, m in ((tw, "#00B894", "^"), (tl, "#D63031", "v")):
            pts = [(pd.to_datetime(r["exit_date"]), eqmap.get(r["exit_date"], np.nan))
                   for _, r in t.iterrows()]
            pts = [(a, b) for a, b in pts if not np.isnan(b)]
            if pts:
                ax.scatter([p[0] for p in pts], [p[1] for p in pts],
                           c=c, marker=m, s=28, zorder=5,
                           label="winning exit" if m == "^" else "losing exit")
    ax.set_title("APEX backtest — equity curve vs SPY (paper-trading strategy validation)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    e = eq["equity"].astype(float)
    dd = (e - e.cummax()) / e.cummax() * 100
    axes[1].fill_between(x, dd, 0, color="#D63031", alpha=0.4)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    print(f"chart saved: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-06-01")
    ap.add_argument("--end", default="2026-08-28")
    ap.add_argument("--cash", type=float, default=100_000.0)
    args = ap.parse_args()

    print(f"Fetching bars {args.start} -> {args.end} ...")
    data = fetch_all(list(dict.fromkeys([config.REGIME_SYMBOL] + config.UNIVERSE)),
                     args.start, args.end)
    eq, trades = run(data, args.cash)
    eq.to_csv(config.BASE_DIR / "backtest_equity.csv", index=False)
    trades.to_csv(config.BASE_DIR / "backtest_trades.csv", index=False)

    s = stats(eq, trades, args.cash)
    print("\n===== APEX backtest results =====")
    for k, v in s.items():
        print(f"  {k:15s} {v}")

    spy = data[config.REGIME_SYMBOL]
    bench = spy.loc[spy.index >= pd.to_datetime(eq["date"].iloc[0]).date()]
    print(f"  SPY buy&hold   {bench['c'].iloc[-1]/bench['c'].iloc[0]-1:+.1%}")
    make_chart(eq, trades, bench, config.BASE_DIR / "backtest_equity.png")


if __name__ == "__main__":
    main()
