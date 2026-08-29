"""Dependency-free Alpaca REST client (trading + market data)."""
import json
import time
import urllib.parse
import urllib.request

import config


class AlpacaError(Exception):
    pass


def _request(base, method, path, params=None, body=None, retries=3):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {
        "APCA-API-KEY-ID": config.API_KEY,
        "APCA-API-SECRET-KEY": config.API_SECRET,
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            payload = e.read().decode(errors="replace")
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise AlpacaError(f"{method} {url} -> {e.code}: {payload}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise AlpacaError(f"{method} {url} -> {e}") from e


# --- Trading API ----------------------------------------------------------
def get_account():
    return _request(config.TRADING_BASE, "GET", "/account")


def get_clock():
    return _request(config.TRADING_BASE, "GET", "/clock")


def list_positions():
    return _request(config.TRADING_BASE, "GET", "/positions")


def get_position(symbol):
    try:
        return _request(config.TRADING_BASE, "GET", f"/positions/{symbol}")
    except AlpacaError as e:
        if "404" in str(e):
            return None
        raise


def list_orders(status="open"):
    return _request(config.TRADING_BASE, "GET", "/orders", params={"status": status, "limit": 100})


def submit_order(symbol, qty, side, order_type="market", time_in_force="day",
                 limit_price=None, stop_price=None):
    body = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }
    if limit_price is not None:
        body["limit_price"] = str(limit_price)
    if stop_price is not None:
        body["stop_price"] = str(stop_price)
    return _request(config.TRADING_BASE, "POST", "/orders", body=body)


def cancel_order(order_id):
    return _request(config.TRADING_BASE, "DELETE", f"/orders/{order_id}")


def close_position(symbol):
    return _request(config.TRADING_BASE, "DELETE", f"/positions/{symbol}")


# --- Market data API ------------------------------------------------------
def get_bars(symbol, timeframe="1Day", start=None, end=None, limit=10000):
    """Return list of daily bars oldest->newest: dict(o,h,l,c,v,t)."""
    bars = []
    page = None
    while True:
        params = {"timeframe": timeframe, "limit": limit, "feed": config.DATA_FEED,
                  "adjustment": "split"}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if page:
            params["page_token"] = page
        resp = _request(config.DATA_BASE, "GET", f"/v2/stocks/{symbol}/bars", params=params)
        chunk = resp.get("bars") or []
        bars.extend(chunk)
        page = resp.get("next_page_token")
        if not page or not chunk:
            break
    return bars


def get_latest_trade(symbol):
    return _request(config.DATA_BASE, "GET", f"/v2/stocks/{symbol}/trades/latest",
                    params={"feed": config.DATA_FEED})
