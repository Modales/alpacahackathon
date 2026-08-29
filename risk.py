"""Risk engine: ATR position sizing + portfolio guards."""
import math

import config


def position_size(equity, price, atr_val):
    """Shares such that a 2*ATR adverse move loses ~RISK_PER_TRADE of equity,
    capped at MAX_POS_PCT of equity notional."""
    if atr_val is None or atr_val <= 0 or price <= 0:
        return 0
    risk_dollars = equity * config.RISK_PER_TRADE
    per_share_risk = 2.0 * atr_val
    shares = math.floor(risk_dollars / per_share_risk)
    cap_shares = math.floor(equity * config.MAX_POS_PCT / price)
    return max(0, min(shares, cap_shares))


def trailing_stop(highest_close_since_entry, atr_val):
    if atr_val is None:
        return None
    return highest_close_since_entry - config.TRAIL_ATR_MULT * atr_val


def portfolio_guard(equity, positions_value, n_positions):
    """Return (can_open_new, reason)."""
    if n_positions >= config.MAX_POSITIONS:
        return False, "max positions reached"
    if equity > 0 and positions_value / equity >= config.MAX_GROSS_PCT:
        return False, "gross exposure cap reached"
    return True, "ok"


def kill_switch_triggered(day_start_equity, current_equity):
    if day_start_equity and day_start_equity > 0:
        dd = current_equity / day_start_equity - 1.0
        return dd <= -config.DAILY_DD_KILL
    return False
