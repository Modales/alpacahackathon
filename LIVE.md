# APEX — live trading journal

Repo: https://github.com/Modales/alpacahackathon · Alpaca paper account · all times ET · updated 2026-09-04T04:43:06

## Account

| equity | P&L | cash | positions |
|---|---|---|---|
| $100,181.12 | +0.18% ($+181.12) | $40,671.05 | 6 |

## Open positions

| symbol | qty | avg entry | last | unrealized P&L |
|---|---|---|---|---|
| MSFT | 39 | $509.81 | $509.67 | -5.52 |
| XLE | 311 | $64.13 | $64.58 | +139.76 |
| XLE261009C00067500 | -1 | $0.88 | $1.01 | -13.00 |
| XLF260925P00056500 | -1 | $0.39 | $0.27 | +12.00 |
| XLV | 117 | $169.51 | $172.75 | +379.08 |
| XLV261002C00172000 | -1 | $2.04 | $5.35 | -331.00 |

## Order ledger

| time (ET) | symbol | side | qty | sleeve | reason |
|---|---|---|---|---|---|
| 2026-08-31T09:47:40-04:00 | XLE | buy | 311 | core | core momentum score +9.81% |
| 2026-08-31T09:47:42-04:00 | XLV | buy | 117 | core | core momentum score +8.07% |
| 2026-08-31T09:47:47-04:00 | MSFT | buy | 39 | core | core momentum score +6.07% |

## Equity history (agent snapshots)

- snapshots: 10 (2026-08-29 -> 2026-09-02)
- high: $100,018.70 · low: $99,818.48 · max drawdown: -0.18%

## Method

Strategy, validation gates and OOS results: see [README.md](README.md) and [validation_report.md](validation_report.md). Trades are executed by `agent.py` on a 09:47/15:47 ET schedule; every order carries its signal reason in the ledger above.
