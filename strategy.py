"""APEX strategy: momentum rotation + RSI(2) pullback, regime filtered.

Pure functions over daily-bar lists so the backtester and the live agent
run the *exact same* decision code. Bar dicts: {o,h,l,c,v,t} oldest->newest.

Rules (long only):
  REGIME     risk-on iff SPY close > SMA(REGIME_SMA); risk-off blocks new
             entries and forces momentum exits.
  ELIGIBLE   momentum score = 0.5*ret(MOM_FAST) + 0.5*ret(MOM_SLOW);
             a name is eligible iff score > 0 and it ranks in top MOM_TOP_N.
  ENTRY      eligible AND RSI(2) <= RSI_ENTRY.
  EXIT       RSI(2) >= RSI_EXIT  (reversion complete)
             OR score <= 0 / falls out of top-N  (momentum decay)
             OR trailing stop: close < max_close_since_entry - TRAIL_ATR_MULT*ATR
"""
import config


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(closes, period=2):
    """Cutler's RSI (simple average of gains/losses) over `period` bars."""
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    avg_gain, avg_loss = gains / period, losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def atr(bars, period=14):
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period


def momentum_score(closes):
    if len(closes) < config.MOM_SLOW + 1:
        return None
    fast = closes[-1] / closes[-1 - config.MOM_FAST] - 1.0
    slow = closes[-1] / closes[-1 - config.MOM_SLOW] - 1.0
    return 0.5 * fast + 0.5 * slow


def regime_on(spy_bars):
    closes = [b["c"] for b in spy_bars]
    ma = sma(closes, config.REGIME_SMA)
    if ma is None:
        return True  # not enough history: do not block
    return closes[-1] > ma


def rank_universe(bars_by_symbol):
    """Return {symbol: score} sorted desc, None-score symbols excluded."""
    scores = {}
    for sym, bars in bars_by_symbol.items():
        s = momentum_score([b["c"] for b in bars])
        if s is not None:
            scores[sym] = s
    return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


def core_targets(scores, regime_is_on):
    """Core momentum sleeve: top CORE_SLOTS names with positive momentum."""
    if not regime_is_on:
        return set()
    out = []
    for sym, s in scores.items():
        if len(out) >= config.CORE_SLOTS:
            break
        if s > 0:
            out.append(sym)
    return set(out)


def eligible_symbols(scores):
    top = list(scores.items())[: config.MOM_TOP_N]
    return {sym for sym, s in top if s > 0}


def evaluate_symbol(sym, bars, scores):
    """Return dict with indicators + entry/exit flags for one symbol."""
    closes = [b["c"] for b in bars]
    r = rsi(closes, config.RSI_PERIOD)
    a = atr(bars, config.ATR_PERIOD)
    score = scores.get(sym)
    elig = score is not None and score > 0 and \
        sym in set(list(sorted(scores, key=scores.get, reverse=True))[: config.MOM_TOP_N])
    return {
        "symbol": sym,
        "close": closes[-1] if closes else None,
        "rsi2": r,
        "atr": a,
        "score": score,
        "eligible": elig,
        "entry": bool(elig and r is not None and r <= config.RSI_ENTRY),
        "rsi_exit": bool(r is not None and r >= config.RSI_EXIT),
        "mom_exit": bool(score is not None and (score <= 0 or not elig)),
    }
