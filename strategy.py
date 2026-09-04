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


# ---------------------------------------------------------------------------
# Novel-alpha hypothesis signals (research lab — see validation_report.md)
# ---------------------------------------------------------------------------

def lag1_autocorr(closes, window=20):
    """Lag-1 autocorrelation of daily returns over `window` bars.
    Negative => dips statistically predict bounces (mean-reverting
    microstructure); positive => trending microstructure."""
    if len(closes) < window + 2:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(-window, 0)]
    mu = sum(rets) / len(rets)
    num = sum((rets[i] - mu) * (rets[i - 1] - mu) for i in range(1, len(rets)))
    den = sum((r - mu) ** 2 for r in rets)
    return num / den if den > 0 else None


def persistence_z(closes, window=40):
    """Sign-change z-score of daily returns vs a random-walk null.
    Under H0 (random walk) sign changes ~ Binomial(n-1, 0.5).
    z > 0 => anti-persistent (choppy, mean-reverting);
    z < 0 => persistent (trending)."""
    if len(closes) < window + 1:
        return None
    signs = [1 if closes[i] > closes[i - 1] else 0 for i in range(-window, 0)]
    n = len(signs) - 1
    if n < 10:
        return None
    changes = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])
    mu, var = n * 0.5, n * 0.25
    return (changes - mu) / (var ** 0.5)


def vol_of_vol_pct(closes, short=5, long=20, hist=252):
    """Percentile of current vol-of-vol within its own 1y history.
    Vol-of-vol = stdev of rolling `short`-day realized vol over `long` days.
    High VoV => unstable panic structure => deeper overshoots, bigger bounces."""
    if len(closes) < hist + long + short + 2:
        return None
    import math as _m
    n = len(closes)

    def rvol(end_idx):  # realized vol of `short` returns ending at end_idx (<0)
        i0 = n + end_idx - short + 1
        if i0 < 1:
            return None
        rs = [closes[i] / closes[i - 1] - 1.0 for i in range(i0, n + end_idx + 1)]
        mu = sum(rs) / len(rs)
        return _m.sqrt(sum((r - mu) ** 2 for r in rs) / len(rs))

    def vov(end_idx):  # stdev of the last `long` rvols ending at end_idx
        vs = [rvol(end_idx - j) for j in range(long - 1, -1, -1)]
        if any(v is None for v in vs):
            return None
        mu = sum(vs) / len(vs)
        return _m.sqrt(sum((v - mu) ** 2 for v in vs) / len(vs))

    cur = vov(-1)
    if cur is None:
        return None
    hist_vals = []
    for end in range(-hist, 0, short):  # sampled every `short` days
        v = vov(end)
        if v is not None:
            hist_vals.append(v)
    if len(hist_vals) < 20:
        return None
    return sum(1 for v in hist_vals if v <= cur) / len(hist_vals)


def intraday_flow_score(bars):
    """Momentum of intraday moves (close/open) vs overnight gaps.
    Institutional accumulation shows up intraday; gap-driven moves carry
    reversal risk. Score = log-sum of intraday returns over MOM_SLOW days,
    blended 50/50 with the classic close-close score."""
    if len(bars) < config.MOM_SLOW + 1:
        return None
    import math as _m
    flow = 0.0
    for i in range(-config.MOM_SLOW, 0):
        if bars[i]["o"] > 0:
            flow += _m.log(bars[i]["c"] / bars[i]["o"])
    classic = momentum_score([b["c"] for b in bars])
    if classic is None:
        return None
    return 0.5 * classic + 0.5 * flow


def rank_universe_flow(bars_by_symbol):
    """rank_universe variant using intraday-flow momentum."""
    scores = {}
    for sym, bars in bars_by_symbol.items():
        s = intraday_flow_score(bars)
        if s is not None:
            scores[sym] = s
    return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


# --- round 4: ranking hypotheses ---------------------------------------------

def accel_score(bars):
    """Momentum + acceleration: base score plus 0.5x the change in the fast
    momentum leg over the last MOM_FAST bars (second-derivative boost)."""
    closes = [b["c"] for b in bars]
    if len(closes) < config.MOM_SLOW + config.MOM_FAST + 1:
        return None
    base = momentum_score(closes)
    r_now = closes[-1] / closes[-1 - config.MOM_FAST] - 1.0
    r_prev = closes[-1 - config.MOM_FAST] / closes[-1 - 2 * config.MOM_FAST] - 1.0
    return base + 0.5 * (r_now - r_prev)


def riskadj_score(bars):
    """Vol-normalized momentum: base score divided by 21d realized vol.
    Rewards smooth accumulation over violent chops at equal return."""
    closes = [b["c"] for b in bars]
    if len(closes) < config.MOM_SLOW + 1:
        return None
    base = momentum_score(closes)
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(-config.MOM_FAST, 0)]
    mu = sum(rets) / len(rets)
    vol = (sum((r - mu) ** 2 for r in rets) / len(rets)) ** 0.5
    return base / vol if vol > 0 else None


def gap_pen_score(bars):
    """Gap-share penalty: base score x (1 - gap_share), where gap_share is the
    overnight |move| share of total |move| over MOM_SLOW days. Gap-dominated
    momentum is lower quality than intraday-driven momentum."""
    closes = [b["c"] for b in bars]
    if len(bars) < config.MOM_SLOW + 1:
        return None
    base = momentum_score(closes)
    gap = tot = 0.0
    for i in range(-config.MOM_SLOW, 0):
        o, c, pc = bars[i]["o"], bars[i]["c"], bars[i - 1]["c"]
        if o > 0 and pc > 0:
            gap += abs(o / pc - 1.0)
            tot += abs(o / pc - 1.0) + abs(c / o - 1.0)
    if tot <= 0:
        return None
    return base * (1.0 - gap / tot)


_RANKERS = {"classic": None, "flow": intraday_flow_score, "accel": accel_score,
            "riskadj": riskadj_score, "gappen": gap_pen_score}


def rank_universe_mode(bars_by_symbol):
    """Rank the universe with the scoring function selected by RANK_MODE."""
    fn = _RANKERS.get(getattr(config, "RANK_MODE", "classic"))
    if fn is None:
        return rank_universe(bars_by_symbol)
    scores = {}
    for sym, bars in bars_by_symbol.items():
        s = fn(bars)
        if s is not None:
            scores[sym] = s
    return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


def evaluate_symbol(sym, bars, scores):
    """Return dict with indicators + entry/exit flags for one symbol."""
    closes = [b["c"] for b in bars]
    r = rsi(closes, config.RSI_PERIOD)
    a = atr(bars, config.ATR_PERIOD)
    score = scores.get(sym)
    elig = score is not None and score > 0 and \
        sym in set(list(sorted(scores, key=scores.get, reverse=True))[: config.MOM_TOP_N])
    if not config.PULLBACK_NEED_MOM:
        elig = score is not None  # pure reversion: only need data, not rank

    entry = bool(elig and r is not None and r <= config.RSI_ENTRY)
    extras = {}
    if entry and config.AUTOCORR_GATE:
        rho = lag1_autocorr(closes)
        extras["autocorr"] = rho
        if rho is None or rho >= 0:
            entry = False
    if entry and config.PERSIST_GATE:
        z = persistence_z(closes)
        extras["persist_z"] = z
        if z is None or z <= 0:
            entry = False
    if entry and config.VOV_GATE:
        pct = vol_of_vol_pct(closes)
        extras["vov_pct"] = pct
        if pct is None or pct <= 2.0 / 3.0:
            entry = False
    return {
        "symbol": sym,
        "close": closes[-1] if closes else None,
        "rsi2": r,
        "atr": a,
        "score": score,
        "eligible": elig,
        "entry": entry,
        "rsi_exit": bool(r is not None and r >= config.RSI_EXIT),
        "mom_exit": bool(score is not None and (score <= 0 or not elig)),
        **extras,
    }
