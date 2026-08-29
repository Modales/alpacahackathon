"""Regenerate the backtest equity chart as SVG (text) for the GitHub README."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot
import matplotlib.pyplot as plt

import config

setup_plot()
eq = pd.read_csv(config.BASE_DIR / "backtest_equity.csv")
trades = pd.read_csv(config.BASE_DIR / "backtest_trades.csv")

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                         gridspec_kw={"height_ratios": [3, 1]})
x = pd.to_datetime(eq["date"])
ax = axes[0]
ax.plot(x, eq["equity"], lw=1.8, color="#6C5CE7", label="APEX strategy")
eqmap = eq.set_index("date")["equity"]
for cond, c, m, lab in ((trades["pnl"] > 0, "#00B894", "^", "winning exit"),
                        (trades["pnl"] <= 0, "#D63031", "v", "losing exit")):
    t = trades[cond]
    pts = [(pd.to_datetime(d), eqmap.get(d)) for d in t["exit_date"]]
    pts = [(a, b) for a, b in pts if b == b]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], c=c, marker=m, s=26,
               zorder=5, label=lab)
ax.set_title("APEX backtest - equity curve (2024-06 -> 2026-08, next-open, 5bps)")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)
e = eq["equity"].astype(float)
dd = (e - e.cummax()) / e.cummax() * 100
axes[1].fill_between(x, dd, 0, color="#D63031", alpha=0.4)
axes[1].set_ylabel("drawdown %")
axes[1].grid(alpha=0.3)
fig.tight_layout()
out = config.BASE_DIR / "backtest_equity.svg"
fig.savefig(out, format="svg", bbox_inches="tight")
print(f"saved {out}")
