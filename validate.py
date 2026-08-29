"""Anti-overfitting validation harness for APEX strategy variants.

Three defenses before anything is allowed to trade live:

1. Walk-forward OOS: each variant is evaluated on three unseen test windows
   with parameters fixed a priori (no fitting on test data).
2. Sensitivity plateau: champion parameters are perturbed one at a time; a
   real edge sits on a plateau, a curve-fit spike collapses when nudged.
3. Deployment gates: OOS Sharpe floor, IS->OOS degradation cap, drawdown cap,
   and minimum trade count. Fail any gate -> variant does not deploy.

Usage:  python validate.py            # full run, writes validation_report.md
        python validate.py --quick    # champion only, 2 folds (daily loop)
"""
import argparse
import copy
import datetime as dt
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest
import cache
import config

FULL_START = "2023-06-01"      # includes warmup for first test window
END = "2026-08-28"
TRADE_START = "2024-06-03"     # first day signals can fire (SMA200 warmup)

FOLDS = [("2025-01-02", "2025-06-30"),
         ("2025-07-01", "2025-12-31"),
         ("2026-01-02", "2026-08-28")]

# Deployment gates
GATE_OOS_SHARPE = 0.5
GATE_DEGRADATION = 0.50        # OOS Sharpe >= (1-0.5)*IS Sharpe
GATE_MAX_DD = 0.20
GATE_MIN_TRADES = 15
GATE_SENS_SHARPE = 0.3         # every sensitivity run must clear this

BASE = {k: getattr(config, k) for k in
        ("MODE", "MOM_FAST", "MOM_SLOW", "MOM_TOP_N", "RSI_ENTRY", "RSI_EXIT",
         "TRAIL_ATR_MULT", "CORE_SLOTS", "PULLBACK_SLOTS", "RISK_PER_TRADE",
         "MAX_POS_PCT", "REGIME_SMA")}

VARIANTS = {
    "apex_hybrid":      {},
    "core_momentum":    {"MODE": "core_only"},
    "pullback_only":    {"MODE": "pullback_only"},
    "etf_rotation":     {"MODE": "core_only", "_universe": "etf"},
    "tilted_pullback":  {"CORE_SLOTS": 2, "PULLBACK_SLOTS": 4, "RSI_ENTRY": 15.0},
}

SENS_GRID = {
    "RSI_ENTRY": [5.0, 10.0, 15.0],
    "RSI_EXIT": [60.0, 70.0, 80.0],
    "MOM_FAST": [10, 21, 42],
    "MOM_SLOW": [42, 63, 126],
    "TRAIL_ATR_MULT": [2.0, 2.5, 3.0],
    "MOM_TOP_N": [6, 8, 10],
}


def apply(overrides):
    for k, v in BASE.items():
        setattr(config, k, v)
    for k, v in overrides.items():
        if not k.startswith("_"):
            setattr(config, k, v)


def window_stats(eq, trades, w0, w1):
    e = eq.set_index("date")["equity"].astype(float).sort_index()
    w = e[(e.index >= w0) & (e.index <= w1)]
    if len(w) < 20:
        return None
    rets = w.pct_change().dropna()
    sharpe = rets.mean() / rets.std() * math.sqrt(252) if rets.std() > 0 else 0.0
    dd = ((w - w.cummax()) / w.cummax()).min()
    n_tr = len(trades[(trades["exit_date"] >= w0) & (trades["exit_date"] <= w1)]) \
        if len(trades) else 0
    return {"ret": w.iloc[-1] / w.iloc[0] - 1, "sharpe": sharpe,
            "maxdd": dd, "trades": n_tr}


def run_variant(name, overrides, data_all, etf_data):
    apply(overrides)
    data = etf_data if overrides.get("_universe") == "etf" else data_all
    eq, trades = backtest.run(data)
    return eq, trades


def fmt_pct(x):
    return f"{x:+.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    print("loading bars (cached) ...")
    symbols = list(dict.fromkeys([config.REGIME_SYMBOL] + config.UNIVERSE))
    raw = {s: cache.get_bars_cached(s, FULL_START, END) for s in symbols}
    data_all = {}
    for sym, df in raw.items():
        if df.empty:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["t"]).dt.tz_convert("America/New_York").dt.date
        data_all[sym] = df.set_index("date")[["o", "h", "l", "c", "v"]].sort_index()
    etf_syms = [config.REGIME_SYMBOL] + [s for s in config.ETF_UNIVERSE
                                         if s != config.REGIME_SYMBOL]
    etf_data = {s: data_all[s] for s in etf_syms if s in data_all}

    variants = {"apex_hybrid": {}} if args.quick else VARIANTS
    folds = FOLDS[-2:] if args.quick else FOLDS
    lines = ["# APEX validation report",
             f"\nData: {TRADE_START} -> {END} (IEX feed, next-open execution, "
             f"{config.SLIPPAGE_BPS:.0f} bps slippage). "
             f"Parameters fixed a priori; test windows strictly out-of-sample.\n"]

    # ---------------- walk-forward -------------------------------------
    lines.append("\n## 1. Walk-forward out-of-sample results\n")
    lines.append("| variant | fold | window | return | Sharpe | maxDD | trades |")
    lines.append("|---|---|---|---|---|---|---|")
    verdicts = {}
    for name, ov in variants.items():
        eq, trades = run_variant(name, ov, data_all, etf_data)
        is_stats = window_stats(eq, trades, TRADE_START, folds[0][0])
        fold_rows, oos_sharpes, oos_trades, worst_dd = [], [], 0, 0.0
        for w0, w1 in folds:
            st = window_stats(eq, trades, w0, w1)
            if st is None:
                continue
            oos_sharpes.append(st["sharpe"])
            oos_trades += st["trades"]
            worst_dd = min(worst_dd, st["maxdd"])
            fold_rows.append((w0, w1, st))
            lines.append(f"| {name} | {w0[:7]}..{w1[:7]} | {w0}..{w1} "
                         f"| {fmt_pct(st['ret'])} | {st['sharpe']:.2f} "
                         f"| {st['maxdd']:.1%} | {st['trades']} |")
        oos_mean = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0
        is_sharpe = is_stats["sharpe"] if is_stats else 0
        degrad_ok = is_sharpe <= 0 or oos_mean >= (1 - GATE_DEGRADATION) * is_sharpe
        gates = {
            "OOS Sharpe >= 0.5 (mean)": oos_mean >= GATE_OOS_SHARPE,
            "every fold Sharpe > 0": all(s > 0 for s in oos_sharpes),
            "degradation < 50%": degrad_ok,
            "maxDD < 20%": worst_dd > -GATE_MAX_DD,
            f"trades >= {GATE_MIN_TRADES}": oos_trades >= GATE_MIN_TRADES,
        }
        verdicts[name] = (all(gates.values()), oos_mean, is_sharpe, gates)

    lines.append("\n## 2. Deployment gates\n")
    lines.append("| variant | IS Sharpe | OOS Sharpe (mean) | gates | verdict |")
    lines.append("|---|---|---|---|---|")
    for name, (ok, oos_mean, is_sharpe, gates) in verdicts.items():
        g = ", ".join(k for k, v in gates.items() if not v) or "all pass"
        lines.append(f"| {name} | {is_sharpe:.2f} | {oos_mean:.2f} | {g} "
                     f"| {'DEPLOY' if ok else 'REJECT'} |")

    # ---------------- sensitivity --------------------------------------
    lines.append("\n## 3. Parameter sensitivity (champion: apex_hybrid, full period)\n")
    lines.append("| parameter | value | return | Sharpe | maxDD |")
    lines.append("|---|---|---|---|---|")
    sens_ok = True
    for param, values in SENS_GRID.items():
        for v in values:
            apply({"MODE": "hybrid", param: v})
            eq, trades = backtest.run(data_all)
            st = window_stats(eq, trades, TRADE_START, END)
            flag = "" if st["sharpe"] >= GATE_SENS_SHARPE else "  <-- FAILS gate"
            if st["sharpe"] < GATE_SENS_SHARPE:
                sens_ok = False
            mark = " *(base)*" if v == BASE.get(param) else ""
            lines.append(f"| {param} | {v}{mark} | {fmt_pct(st['ret'])} "
                         f"| {st['sharpe']:.2f} | {st['maxdd']:.1%} |{flag}")
    lines.append(f"\nSensitivity plateau: **{'PASS' if sens_ok else 'FAIL'}** "
                 f"(every run must keep Sharpe >= {GATE_SENS_SHARPE})")

    apply({})  # restore base params
    champion_ok = verdicts.get("apex_hybrid", (False,))[0] and sens_ok
    lines.append(f"\n## Verdict\n")
    lines.append(f"Champion **apex_hybrid** (hybrid core+pullback, base params): "
                 f"**{'CLEARED FOR LIVE DEPLOYMENT' if champion_ok else 'NOT CLEARED — do not deploy'}**")

    report = "\n".join(lines)
    (config.BASE_DIR / "validation_report.md").write_text(report)
    print(report)
    print(f"\nwritten: validation_report.md")


if __name__ == "__main__":
    main()
