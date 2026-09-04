"""APEX agent configuration.

Secrets come from environment variables or a local .env file (never
committed — see .gitignore). Copy .env.example to .env and fill in your
paper-trading keys.
"""
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent


def _load_dotenv():
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# --- Alpaca credentials / endpoints ---------------------------------------
API_KEY = os.environ.get("APCA_API_KEY_ID", "")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY", "")
TRADING_BASE = os.environ.get("APCA_TRADING_URL", "https://paper-api.alpaca.markets/v2")
DATA_BASE = os.environ.get("APCA_DATA_URL", "https://data.alpaca.markets")
DATA_FEED = os.environ.get("APCA_DATA_FEED", "iex")          # free tier = IEX
OPTIONS_FEED = os.environ.get("APCA_OPTIONS_FEED", "indicative")  # free tier

# --- Universe ---------------------------------------------------------------
REGIME_SYMBOL = "SPY"
UNIVERSE = [
    "SPY", "QQQ", "XLK", "XLF", "XLE", "XLV", "XLY", "XLI",
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AMD", "AVGO",
    "JPM", "TSLA",
]
ETF_UNIVERSE = ["SPY", "QQQ", "XLK", "XLF", "XLE", "XLV", "XLY", "XLI"]

# --- Strategy mode ------------------------------------------------------------
# "hybrid" (core + pullback) | "core_only" | "pullback_only"
# Chosen by walk-forward validation (see validate.py / validation_report.md).
MODE = os.environ.get("APEX_MODE", "hybrid")

# --- Strategy parameters -----------------------------------------------------
MOM_FAST = 21            # ~1 month momentum lookback (trading days)
MOM_SLOW = 63            # ~3 month momentum lookback
MOM_TOP_N = 8            # only top-N momentum names are eligible
RSI_PERIOD = 2           # 2-day RSI pullback trigger
RSI_ENTRY = 10.0         # buy when RSI(2) <= this on an eligible leader
RSI_EXIT = 70.0          # take profit when RSI(2) >= this
PULLBACK_NEED_MOM = True  # False = pure RSI(2) reversion, no momentum filter
ATR_PERIOD = 14

# --- Novel-alpha hypothesis flags (research lab; validated in round 3) -------
# FLOW_MOMENTUM won the round-3 tournament: OOS Sharpe 1.20 vs base 1.11, own
# 18-perturbation sensitivity plateau passed (worst 0.49). Now the live ranking.
# Set APEX_FLOW_MOMENTUM=false to revert to close-close momentum (apex_hybrid).
AUTOCORR_GATE = os.environ.get("APEX_AUTOCORR_GATE", "false").lower() == "true"
PERSIST_GATE = os.environ.get("APEX_PERSIST_GATE", "false").lower() == "true"
VOV_GATE = os.environ.get("APEX_VOV_GATE", "false").lower() == "true"
_flow_env = os.environ.get("APEX_FLOW_MOMENTUM", "true")
RANK_MODE = os.environ.get("APEX_RANK_MODE") or \
    ("flow" if _flow_env.lower() == "true" else "classic")
FLOW_MOMENTUM = RANK_MODE == "flow"  # back-compat for older tooling
TRAIL_ATR_MULT = 2.5     # trailing stop distance in ATRs
REGIME_SMA = 200         # SPY above SMA200 => risk-on

# --- Sleeve allocation ---------------------------------------------------------
CORE_SLOTS = 3           # max core momentum positions
PULLBACK_SLOTS = 3       # max pullback positions

# --- Risk parameters ---------------------------------------------------------
RISK_PER_TRADE = 0.01    # 1% of equity risked per position (2*ATR stop)
MAX_POSITIONS = 6        # = CORE_SLOTS + PULLBACK_SLOTS
MAX_POS_PCT = 0.20       # max 20% of equity in one name
MAX_GROSS_PCT = 0.95     # max 95% of equity invested overall
DAILY_DD_KILL = 0.025    # halt new entries if intraday equity -2.5%
SLIPPAGE_BPS = 5.0       # backtest slippage per side (basis points)

# --- Options overlay (wheel) --------------------------------------------------
# Hackathon track: Options Alpha Agents. Cash-secured puts replace pullback
# stock entries when a suitable contract exists; covered calls on 100+ share
# positions; short premium is bought back at 50% of credit.
OPTIONS_ENABLED = os.environ.get("APEX_OPTIONS", "true").lower() == "true"
OPT_TARGET_DELTA = 0.30      # |delta| target for short strikes
OPT_MIN_DTE = 21
OPT_MAX_DTE = 45
OPT_MIN_BID = 0.30           # minimum bid to sell (premium floor)
OPT_MAX_SPREAD_PCT = 0.25    # max (ask-bid)/mid
OPT_MAX_SHORTS = 3           # max concurrent short option positions
OPT_MAX_SECURED_PCT = 0.50   # total CSP secured notional <= 50% equity
OPT_PROFIT_TAKE = 0.50       # buy back at 50% of credit received

# --- Paths ----------------------------------------------------------------
STATE_DIR = BASE_DIR / "state"
STATE_FILE = STATE_DIR / "state.json"
TRADES_CSV = STATE_DIR / "trades.csv"
EQUITY_CSV = STATE_DIR / "equity.csv"
LOG_FILE = STATE_DIR / "agent.log"
CACHE_DIR = STATE_DIR / "cache"
