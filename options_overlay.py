"""Options overlay — the "wheel" on top of APEX equity signals.

Hackathon track: Options Alpha Agents. Two income strategies, both fully
rule-based and keyed to the same signals as the equity engine:

1. Cash-secured puts (CSP): when the pullback sleeve fires (RSI2 <= entry on
   a top momentum name), sell 1 OTM put (~30 delta, 21-45 DTE) instead of
   buying shares, when a liquid contract exists. Assignment is welcome:
   shares are adopted by the equity engine (the wheel).
2. Covered calls (CC): any stock position >= 100 shares sells 1 OTM call per
   100 shares (~30 delta, 21-45 DTE).

Short premium is managed with a resting GTC buy-to-close at 50% of credit.
Everything is best-effort: any options failure is logged and never blocks
the equity engine.
"""
import datetime as dt

import alpaca_client as broker
import config
import risk


# ------------------------------------------------------------- data ------
def _snapshots(underlying, opt_type, min_strike=None, max_strike=None):
    today = dt.date.today()
    params = {
        "feed": config.OPTIONS_FEED,
        "type": opt_type,
        "expiration_date_gte": (today + dt.timedelta(days=config.OPT_MIN_DTE)).isoformat(),
        "expiration_date_lte": (today + dt.timedelta(days=config.OPT_MAX_DTE)).isoformat(),
        "limit": 250,
    }
    if min_strike is not None:
        params["strike_price_gte"] = f"{min_strike:.2f}"
    if max_strike is not None:
        params["strike_price_lte"] = f"{max_strike:.2f}"
    resp = broker._request(config.DATA_BASE, "GET",
                           f"/v1beta1/options/snapshots/{underlying}", params=params)
    return resp.get("snapshots") or {}


def pick_contract(underlying, opt_type, spot, target_delta):
    """Return {symbol, strike, delta, bid, ask, mid, dte} closest to
    +/-target_delta passing liquidity filters, or None."""
    snaps = _snapshots(underlying, opt_type)
    best = None
    for sym, s in snaps.items():
        g = s.get("greeks") or {}
        q = s.get("latestQuote") or {}
        delta = g.get("delta")
        bid, ask = q.get("bp"), q.get("ap")
        if delta is None or not bid or not ask or bid < config.OPT_MIN_BID:
            continue
        mid = (bid + ask) / 2
        if mid <= 0 or (ask - bid) / mid > config.OPT_MAX_SPREAD_PCT:
            continue
        want = -abs(target_delta) if opt_type == "put" else abs(target_delta)
        if abs(abs(delta) - abs(want)) > 0.15:
            continue  # hard band around target delta
        score = abs(delta - want)
        # contract symbol embeds expiration: ...YYMMDD...
        ymd = sym[len(underlying):][:6]
        dte = (dt.date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:6]))
               - dt.date.today()).days
        if not (config.OPT_MIN_DTE <= dte <= config.OPT_MAX_DTE):
            continue
        if best is None or score < best[0]:
            best = (score, {"symbol": sym, "delta": delta, "bid": bid,
                            "ask": ask, "mid": mid, "dte": dte,
                            "strike": float(sym.split("P" if opt_type == "put" else "C")[1]) / 1000})
    return best[1] if best else None


# --------------------------------------------------------- positions -----
def option_positions():
    return [p for p in broker.list_positions()
            if p.get("asset_class") == "us_option"]


def stock_positions():
    return [p for p in broker.list_positions()
            if p.get("asset_class") != "us_option"]


def _underlying_of(option_symbol):
    i = 0
    while i < len(option_symbol) and not option_symbol[i].isdigit():
        i += 1
    return option_symbol[:i]


# ------------------------------------------------------------ actions ----
def sell_cash_secured_put(underlying, spot, equity, cash, log, dry_run=False):
    """Sell 1 CSP ~30 delta. Returns action dict or None."""
    if len(option_positions()) >= config.OPT_MAX_SHORTS:
        log(f"opts: max short option positions reached, skip CSP {underlying}")
        return None
    secured_cap = equity * config.OPT_MAX_SECURED_PCT
    secured_now = sum(abs(float(p["qty"])) * float(p.get("current_price") or 0) * 100
                      for p in option_positions() if "P" in p["symbol"])
    contract = pick_contract(underlying, "put", spot, config.OPT_TARGET_DELTA)
    if not contract:
        log(f"opts: no suitable CSP contract for {underlying}")
        return None
    notional = contract["strike"] * 100
    if notional > equity * config.MAX_POS_PCT or \
            secured_now + notional > secured_cap or notional > cash:
        log(f"opts: CSP {underlying} secured ${notional:,.0f} exceeds caps")
        return None
    act = {"kind": "csp", "underlying": underlying, "contract": contract["symbol"],
           "strike": contract["strike"], "delta": contract["delta"],
           "credit": contract["bid"], "dte": contract["dte"], "qty": 1}
    if not dry_run:
        o = broker.submit_order(contract["symbol"], 1, "sell", time_in_force="day")
        act["order_id"] = o.get("id", "")
        log(f"ORDER sell-to-open CSP {contract['symbol']} "
            f"strike {contract['strike']:.0f} dte {contract['dte']} "
            f"delta {contract['delta']:.2f} credit ~{contract['bid']:.2f}")
        _place_profit_take(contract["symbol"], contract["bid"], log)
    return act


def sell_covered_calls(log, dry_run=False):
    """Sell CCs on stock positions >= 100 shares (1 per 100, cap slots)."""
    acts = []
    shorts = {_underlying_of(p["symbol"]) for p in option_positions()}
    pending = {o["symbol"] for o in broker.list_orders("open")}
    for p in stock_positions():
        sym = p["symbol"]
        shares = int(float(p["qty"]))
        lots = shares // 100
        if lots < 1 or sym in shorts:
            continue
        if len(option_positions()) + len(acts) >= config.OPT_MAX_SHORTS:
            break
        spot = float(p["current_price"])
        contract = pick_contract(sym, "call", spot, config.OPT_TARGET_DELTA)
        if not contract:
            log(f"opts: no suitable CC contract for {sym}")
            continue
        if contract["symbol"] in pending:
            continue
        qty = min(lots, 1)  # conservative: 1 contract per name
        act = {"kind": "cc", "underlying": sym, "contract": contract["symbol"],
               "strike": contract["strike"], "delta": contract["delta"],
               "credit": contract["bid"], "dte": contract["dte"], "qty": qty}
        acts.append(act)
        if not dry_run:
            o = broker.submit_order(contract["symbol"], qty, "sell", time_in_force="day")
            act["order_id"] = o.get("id", "")
            log(f"ORDER sell-to-open CC {contract['symbol']} x{qty} "
                f"strike {contract['strike']:.0f} dte {contract['dte']} "
                f"delta {contract['delta']:.2f} credit ~{contract['bid']:.2f}")
            _place_profit_take(contract["symbol"], contract["bid"], log, qty)
    return acts


def _place_profit_take(option_symbol, credit, log, qty=1):
    """Resting GTC buy-to-close at OPT_PROFIT_TAKE of the credit."""
    try:
        limit = round(max(credit * (1 - config.OPT_PROFIT_TAKE), 0.01), 2)
        broker.submit_order(option_symbol, qty, "buy", order_type="limit",
                            time_in_force="gtc", limit_price=limit)
        log(f"opts: profit-take resting bid {limit:.2f} on {option_symbol}")
    except Exception as e:
        log(f"opts warn: profit-take order failed for {option_symbol}: {e}")


def manage_open_shorts(log, dry_run=False):
    """Ensure every short option has a profit-take resting order."""
    pending = {o["symbol"] for o in broker.list_orders("open")}
    for p in option_positions():
        sym = p["symbol"]
        if sym in pending:
            continue
        try:
            entry = float(p["avg_entry_price"])
            qty = abs(int(float(p["qty"])))
            limit = round(max(entry * (1 - config.OPT_PROFIT_TAKE), 0.01), 2)
            if not dry_run:
                broker.submit_order(sym, qty, "buy", order_type="limit",
                                    time_in_force="gtc", limit_price=limit)
                log(f"opts: re-placed profit-take {limit:.2f} on {sym}")
        except Exception as e:
            log(f"opts warn: manage {sym}: {e}")
