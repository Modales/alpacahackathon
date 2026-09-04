# APEX — One-Page Write-Up

**lablab.ai × Alpaca AI Trading Agents Hackathon · Options Alpha Agents track**
Account: `PA3IV1PROFPW` (fresh paper account, $100,000 start) · Repo: github.com/Modales/alpacahackathon

## AI logic

APEX is an autonomous, fully rule-based agent whose core differentiator is not a
strategy but a **research pipeline with deployment gates**. Hypotheses are
generated as explicit code, then must survive three pre-registered defenses
before trading: (1) walk-forward evaluation on three unseen windows
(2025-H1, 2025-H2, 2026-YTD) with parameters frozen *a priori*; (2) an
18-point single-parameter sensitivity plateau (Sharpe ≥ 0.3 everywhere); (3)
quantitative deployment gates (mean OOS Sharpe ≥ 0.5, every fold positive,
IS→OOS degradation < 50%, worst-fold maxDD < 20%, ≥ 15 trades). **16 variants
were tested; 10 were rejected and never touched capital** — including *accel*,
an in-sample star (IS Sharpe 0.98) that collapsed OOS (0.34).

The deployed strategy runs three sleeves on 18 liquid US names + sector ETFs:
a **core sleeve** holding top-3 names by flow-momentum score
(½·close-close momentum + ½·Σ log(close/open) over 63d — our round-3 finding
that intraday-flow momentum beats close-close OOS, 1.20 vs 1.11 Sharpe); a
**pullback sleeve** buying RSI(2) ≤ 10 dips in top-8 leaders with RSI(2) ≥ 70
exits; and an **options wheel** converting the same signals to theta — selling
Δ≈0.30 cash-secured puts (21–45 DTE, liquidity-filtered) on pullback dips and
covered calls on ≥100-share winners, every short with a resting GTC buy-back at
50% of credit. A SPY SMA(200) regime gate blocks entries risk-off.

## Risk gates

1% equity risk per trade vs a 2×ATR stop; 2.5×ATR trailing stops checked daily
**and intraday**; ≤20% notional per name; ≤6 equity positions; ≤3 short options;
≤95% gross exposure; −2.5% daily kill switch; broker-adoption of stray
positions after restarts; kill-switch + reconcile alarms in the log.

## Alpaca infrastructure implementation

Trading API (equities + options orders, account, clock) via a hand-rolled,
dependency-free REST client with retries; Market Data API (IEX daily bars;
OPRA option snapshots with greeks/IV on the indicative feed) for contract
selection by target delta; official `alpaca-mcp-server` verified end-to-end
(72 tools; account + positions pulled over MCP — transcript in
docs/mcp_verification.txt); official `alpaca-py` SDK independently reconciles
broker state every cycle; cron-scheduled idempotent cycles at 09:47 + 15:47 ET
with nightly re-validation; public live journal (LIVE.md) and single-file demo
app (dashboard.html) regenerated after every run.

**Evidence:** backtest 2024-06→2026-08 +38.4%, Sharpe 1.51, maxDD −10.8%;
live ledger + positions in LIVE.md; full OOS tables in validation_report.md.

*Paper trading only. Not investment advice.*
