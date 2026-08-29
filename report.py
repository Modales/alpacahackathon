"""Generate the APEX live-performance report (paper account).

Reads state/equity.csv + state/trades.csv, pulls the account snapshot from
Alpaca, prints stats and renders report.png.

Usage:  python report.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
import alpaca_client as broker
import config


def main():
    account = broker.get_account()
    equity0 = 100_000.0
    eq = pd.DataFrame()
    if config.EQUITY_CSV.exists():
        eq = pd.read_csv(config.EQUITY_CSV)
        eq["equity"] = eq["equity"].astype(float)
        if len(eq):
            equity0 = eq["equity"].iloc[0]
    trades = pd.DataFrame()
    if config.TRADES_CSV.exists():
        trades = pd.read_csv(config.TRADES_CSV)

    cur = float(account["equity"])
    print("===== APEX live performance (paper) =====")
    print(f"  current equity  ${cur:,.2f}")
    print(f"  total P&L       ${cur - equity0:+,.2f}  ({cur / equity0 - 1:+.2%})")
    if len(eq) > 1:
        e = eq["equity"]
        peak = e.cummax()
        print(f"  max drawdown    {((e - peak) / peak).min():.2%}")
        print(f"  data points     {len(eq)}  ({eq['timestamp'].iloc[0]} -> {eq['timestamp'].iloc[-1]})")
    positions = broker.list_positions()
    print(f"  open positions  {len(positions)}")
    for p in positions:
        print(f"    {p['symbol']:6s} {p['qty']:>8s} sh  P&L {float(p['unrealized_pl']):+,.2f}")
    if len(trades):
        print(f"  orders logged   {len(trades)}  (see state/trades.csv)")

    # --- chart ---
    from daimon_runtime import setup_plot
    import matplotlib.pyplot as plt
    setup_plot()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    if len(eq) > 1:
        x = pd.to_datetime(eq["timestamp"])
        ax.plot(x, eq["equity"], lw=1.8, color="#6C5CE7", label="APEX live equity")
        ax.axhline(equity0, color="#B2BEC3", lw=1, ls="--", label=f"start ${equity0:,.0f}")
        for _, t in trades.iterrows():
            ts = pd.to_datetime(t["timestamp"])
            near = eq.iloc[(eq["timestamp"] - str(ts)).abs().argsort()[:1]] \
                if "timestamp" in eq else None
            y = float(near["equity"].iloc[0]) if near is not None and len(near) else None
            if y:
                ax.scatter([ts], [y], marker="^" if t["side"] == "buy" else "v",
                           c="#00B894" if t["side"] == "buy" else "#D63031", s=40, zorder=5)
        ax.legend(loc="upper left")
    else:
        ax.text(0.5, 0.5, "No live equity data yet — agent has not run",
                ha="center", va="center", transform=ax.transAxes)
    ax.set_title("APEX live paper-trading equity")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = config.BASE_DIR / "report.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    print(f"\nchart saved: {out}")


if __name__ == "__main__":
    main()
