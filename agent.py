"""APEX live/paper trading agent — one evaluation cycle per invocation.

Designed to be driven by a scheduler (cron / Blueprint Automation) every
15-30 min. Idempotent: only acts once per new completed daily bar, manages
intraday trailing stops on every run while the market is open.

Usage:
  python agent.py            # run one cycle (submits orders when market open)
  python agent.py --dry-run  # print intended actions, submit nothing
  python agent.py --status   # account/positions/signal snapshot, no actions
"""
import argparse
import csv
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpaca_client as broker
import config
import options_overlay
import reconcile
import risk
import strategy

ET = dt.timezone(dt.timedelta(hours=-4), name="ET")  # paper clock is America/New_York
BAR_LOOKBACK_DAYS = 400


# ---------------------------------------------------------------- state ---
def load_state():
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text())
    return {"positions": {}, "last_bar_date": None,
            "day": None, "day_start_equity": None}


def save_state(state):
    config.STATE_DIR.mkdir(exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2))


def log(msg):
    config.STATE_DIR.mkdir(exist_ok=True)
    line = f"{dt.datetime.now(ET).isoformat(timespec='seconds')}  {msg}"
    print(line)
    with open(config.LOG_FILE, "a") as f:
        f.write(line + "\n")


def append_equity(account, n_positions):
    config.STATE_DIR.mkdir(exist_ok=True)
    new = not config.EQUITY_CSV.exists()
    with open(config.EQUITY_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "equity", "cash", "positions_value", "n_positions"])
        w.writerow([dt.datetime.now(ET).isoformat(timespec="seconds"),
                    account["equity"], account["cash"],
                    account["long_market_value"], n_positions])


def record_trade(row):
    config.STATE_DIR.mkdir(exist_ok=True)
    new = not config.TRADES_CSV.exists()
    with open(config.TRADES_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "side", "qty",
                                          "sleeve", "reason", "order_id"])
        if new:
            w.writeheader()
        w.writerow(row)


# ----------------------------------------------------------------- data ---
def fetch_bars(symbols):
    end = dt.datetime.now(ET).date().isoformat()
    start = (dt.datetime.now(ET).date() - dt.timedelta(days=BAR_LOOKBACK_DAYS)).isoformat()
    out = {}
    for sym in symbols:
        bars = broker.get_bars(sym, "1Day", start=start, end=end)
        if bars:
            out[sym] = bars
    return out


def latest_bar_date(bars_by_sym):
    dates = [b[-1]["t"][:10] for b in bars_by_sym.values() if b]
    return max(dates) if dates else None


# ----------------------------------------------------------------- main ---
def run_cycle(dry_run=False):
    clock = broker.get_clock()
    account = broker.get_account()
    positions = {p["symbol"]: p for p in broker.list_positions()
                 if p.get("asset_class") != "us_option"}  # equity engine: stocks only
    open_orders = broker.list_orders("open")
    pending_syms = {o["symbol"] for o in open_orders}
    state = load_state()
    try:
        reconcile.reconcile(account, positions, log)
    except Exception as e:
        log(f"reconcile warn: {e}")

    equity = float(account["equity"])
    cash = float(account["cash"])
    today = dt.datetime.now(ET).date().isoformat()
    market_open = clock["is_open"]

    # day rollover for the kill switch
    if state.get("day") != today:
        state["day"] = today
        state["day_start_equity"] = equity
        log(f"new trading day, start equity ${equity:,.2f}")

    halted = risk.kill_switch_triggered(state.get("day_start_equity"), equity)
    if halted:
        log(f"KILL SWITCH: equity ${equity:,.2f} is -{config.DAILY_DD_KILL:.1%} "
            f"past day start -> entries blocked today")

    symbols = list(dict.fromkeys([config.REGIME_SYMBOL] + config.UNIVERSE))
    bars_by_sym = fetch_bars(symbols)
    if config.REGIME_SYMBOL not in bars_by_sym:
        log("ERROR: no regime bars, aborting cycle")
        return
    bar_date = latest_bar_date(bars_by_sym)
    new_bar = bar_date is not None and bar_date != state.get("last_bar_date")

    on = strategy.regime_on(bars_by_sym[config.REGIME_SYMBOL])
    scores = strategy.rank_universe(bars_by_sym)
    core_set = strategy.core_targets(scores, on)

    log(f"cycle: open={market_open} equity=${equity:,.2f} cash=${cash:,.2f} "
        f"positions={len(positions)} regime={'ON' if on else 'OFF'} "
        f"bar={bar_date} new_bar={new_bar} halted={halted}")
    log(f"core targets: {sorted(core_set) if core_set else '[]'}")

    actions = []

    # ---- sync state with broker positions (adopt unknowns) ---------------
    for sym, p in positions.items():
        if sym not in state["positions"]:
            ev = strategy.evaluate_symbol(sym, bars_by_sym.get(sym, []), scores) \
                if sym in bars_by_sym else None
            state["positions"][sym] = {
                "sleeve": "pullback",
                "highest_close": ev["close"] if ev and ev["close"] else float(p["current_price"]),
                "atr_at_entry": ev["atr"] if ev else None,
                "entry_date": today, "qty": p["qty"]}
            log(f"adopted unmanaged position {sym} ({p['qty']} sh)")

    # ---- exits ------------------------------------------------------------
    for sym in list(state["positions"]):
        if sym not in positions:  # closed externally
            del state["positions"][sym]
            continue
        if sym not in bars_by_sym:
            continue
        st = state["positions"][sym]
        ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
        st["highest_close"] = max(st.get("highest_close") or 0, ev["close"])
        stop = risk.trailing_stop(st["highest_close"], st.get("atr_at_entry"))

        reason = None
        # intraday stop check (every run while market open)
        if market_open and stop is not None:
            try:
                last = float(broker.get_latest_trade(sym)["trade"]["p"])
                if last < stop:
                    reason = f"intraday stop hit (last {last:.2f} < {stop:.2f})"
            except Exception as e:
                log(f"warn: latest trade {sym}: {e}")
        # daily-signal exits (once per new bar)
        if reason is None and new_bar:
            if stop is not None and ev["close"] < stop:
                reason = f"trailing stop (close {ev['close']:.2f} < {stop:.2f})"
            elif st["sleeve"] == "core" and sym not in core_set:
                reason = "core rotation" if on else "regime off"
            elif st["sleeve"] == "pullback":
                if ev["rsi_exit"]:
                    reason = f"RSI2 {ev['rsi2']:.0f} >= {config.RSI_EXIT} take-profit"
                elif ev["mom_exit"]:
                    reason = "momentum decay"
        if reason and sym not in pending_syms:
            qty = positions[sym]["qty"]
            actions.append({"symbol": sym, "side": "sell", "qty": qty,
                            "sleeve": st["sleeve"], "reason": reason})
            if not dry_run and market_open:
                o = broker.submit_order(sym, qty, "sell")
                record_trade({"timestamp": dt.datetime.now(ET).isoformat(timespec="seconds"),
                              "symbol": sym, "side": "sell", "qty": qty,
                              "sleeve": st["sleeve"], "reason": reason,
                              "order_id": o.get("id", "")})
                log(f"ORDER sell {qty} {sym} — {reason}")
                st["_closing"] = True

    # ---- entries (once per new bar) ---------------------------------------
    if new_bar and on and not halted:
        n_core = sum(1 for s in state["positions"].values()
                     if s["sleeve"] == "core" and not s.get("_closing"))
        n_pb = sum(1 for s in state["positions"].values()
                   if s["sleeve"] == "pullback" and not s.get("_closing"))

        def try_buy(sym, ev, sleeve, why):
            nonlocal cash
            held = sym in positions or sym in pending_syms
            acted = any(a["symbol"] == sym and a["side"] == "buy" for a in actions)
            if held or acted or sym not in bars_by_sym:
                return False
            qty = risk.position_size(equity, ev["close"], ev["atr"])
            if qty <= 0 or qty * ev["close"] > cash:
                return False
            actions.append({"symbol": sym, "side": "buy", "qty": qty,
                            "sleeve": sleeve, "reason": why})
            if not dry_run and market_open:
                o = broker.submit_order(sym, qty, "buy")
                record_trade({"timestamp": dt.datetime.now(ET).isoformat(timespec="seconds"),
                              "symbol": sym, "side": "buy", "qty": qty,
                              "sleeve": sleeve, "reason": why, "order_id": o.get("id", "")})
                log(f"ORDER buy {qty} {sym} @~{ev['close']:.2f} — {why}")
                cash -= qty * ev["close"]
                state["positions"][sym] = {
                    "sleeve": sleeve, "highest_close": ev["close"],
                    "atr_at_entry": ev["atr"], "entry_date": today, "qty": str(qty)}
            return True

        # core sleeve
        if config.MODE == "pullback_only":
            core_set = set()
        for sym in sorted(core_set, key=lambda s: -scores[s]):
            if n_core >= config.CORE_SLOTS:
                break
            if sym in state["positions"]:
                continue
            ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
            if try_buy(sym, ev, "core", f"core momentum score {scores[sym]:+.2%}"):
                n_core += 1
        # pullback sleeve
        cands = []
        acted = {a.get("symbol") or a.get("underlying") for a in actions}
        for sym in (bars_by_sym if config.MODE != "core_only" else {}):
            if sym == config.REGIME_SYMBOL or sym in state["positions"] \
                    or sym in acted:
                continue
            ev = strategy.evaluate_symbol(sym, bars_by_sym[sym], scores)
            if ev["entry"]:
                cands.append(ev)
        for ev in sorted(cands, key=lambda e: e["rsi2"]):
            if n_pb >= config.PULLBACK_SLOTS:
                break
            why = f"RSI2 {ev['rsi2']:.1f} <= {config.RSI_ENTRY}, score {ev['score']:+.2%}"
            filled = False
            if config.OPTIONS_ENABLED:
                try:
                    act = options_overlay.sell_cash_secured_put(
                        ev["symbol"], ev["close"], equity, cash, log,
                        dry_run=dry_run or not market_open)
                    if act:
                        act["reason"] = f"CSP wheel entry: {why}"
                        actions.append(act)
                        filled = True
                except Exception as e:
                    log(f"opts warn: CSP {ev['symbol']} failed ({e}), "
                        f"falling back to stock")
            if not filled and try_buy(ev["symbol"], ev, "pullback", why):
                filled = True
            if filled:
                n_pb += 1

    # ---- options overlay management -------------------------------------
    if config.OPTIONS_ENABLED:
        try:
            if market_open and not dry_run:
                options_overlay.manage_open_shorts(log)
            if new_bar:
                for act in options_overlay.sell_covered_calls(
                        log, dry_run=dry_run or not market_open):
                    actions.append(act)
        except Exception as e:
            log(f"opts warn: overlay management failed: {e}")

    if new_bar and market_open:
        state["last_bar_date"] = bar_date
    for s in state["positions"].values():
        s.pop("_closing", None)

    append_equity(account, len(positions))
    if not dry_run:
        save_state(state)

    if actions:
        log("actions: " + json.dumps(actions))
    else:
        log("no actions this cycle")
    if dry_run:
        print("\nDRY RUN — no orders submitted. Intended actions above.")


def status():
    account = broker.get_account()
    positions = broker.list_positions()
    clock = broker.get_clock()
    print(f"market open : {clock['is_open']}  (next open {clock['next_open']})")
    print(f"equity      : ${float(account['equity']):,.2f}")
    print(f"cash        : ${float(account['cash']):,.2f}")
    print(f"day P&L     : ${float(account['equity']) - float(account['last_equity']):+,.2f}")
    print(f"positions   : {len(positions)}")
    for p in positions:
        print(f"  {p['symbol']:6s} {p['qty']:>8s} sh  avg {float(p['avg_entry_price']):>10.2f}"
              f"  now {float(p['current_price']):>10.2f}  P&L {float(p['unrealized_pl']):+,.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    try:
        if args.status:
            status()
        else:
            run_cycle(dry_run=args.dry_run)
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
