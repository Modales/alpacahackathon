# APEX validation report

Data: 2024-06-03 -> 2026-08-28 (IEX feed, next-open execution, 5 bps slippage). Parameters fixed a priori; test windows strictly out-of-sample.


## 1. Walk-forward out-of-sample results

| variant | fold | window | return | Sharpe | maxDD | trades |
|---|---|---|---|---|---|---|---|
| apex_hybrid | 2025-01..2025-06 | 2025-01-02..2025-06-30 | +3.6% | 0.66 | -10.9% | 79 |
| apex_hybrid | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +18.3% | 1.92 | -6.5% | 97 |
| apex_hybrid | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +7.1% | 0.75 | -10.8% | 125 |
| core_momentum | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -2.7% | -0.59 | -10.1% | 48 |
| core_momentum | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +12.5% | 1.73 | -6.9% | 46 |
| core_momentum | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +9.1% | 1.08 | -7.9% | 65 |
| pullback_only | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -2.3% | -0.56 | -8.2% | 40 |
| pullback_only | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +4.2% | 0.96 | -4.2% | 80 |
| pullback_only | 2026-01..2026-08 | 2026-01-02..2026-08-28 | -0.9% | -0.13 | -5.2% | 93 |
| etf_rotation | 2025-01..2025-06 | 2025-01-02..2025-06-30 | +1.5% | 0.49 | -4.5% | 30 |
| etf_rotation | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +3.5% | 0.91 | -3.2% | 47 |
| etf_rotation | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +11.9% | 1.91 | -5.1% | 51 |
| tilted_pullback | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -3.1% | -0.48 | -12.8% | 80 |
| tilted_pullback | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +12.1% | 1.41 | -6.4% | 112 |
| tilted_pullback | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +7.9% | 0.86 | -9.3% | 123 |

## 2. Deployment gates

| variant | IS Sharpe | OOS Sharpe (mean) | gates | verdict |
|---|---|---|---|---|
| apex_hybrid | 0.26 | 1.11 | all pass | DEPLOY |
| core_momentum | 0.73 | 0.74 | every fold Sharpe > 0 | REJECT |
| pullback_only | 0.21 | 0.09 | OOS Sharpe >= 0.5 (mean), every fold Sharpe > 0, degradation < 50% | REJECT |
| etf_rotation | 0.39 | 1.10 | all pass | DEPLOY |
| tilted_pullback | -0.07 | 0.60 | every fold Sharpe > 0 | REJECT |

## 3. Parameter sensitivity (champion: apex_hybrid, full period)

| parameter | value | return | Sharpe | maxDD |
|---|---|---|---|---|
| RSI_ENTRY | 5.0 | +27.5% | 0.75 | -14.7% |
| RSI_ENTRY | 10.0 *(base)* | +32.5% | 0.86 | -14.4% |
| RSI_ENTRY | 15.0 | +30.2% | 0.80 | -14.7% |
| RSI_EXIT | 60.0 | +33.2% | 0.89 | -13.4% |
| RSI_EXIT | 70.0 *(base)* | +32.5% | 0.86 | -14.4% |
| RSI_EXIT | 80.0 | +30.2% | 0.80 | -15.0% |
| MOM_FAST | 10 | +35.6% | 0.92 | -10.7% |
| MOM_FAST | 21 *(base)* | +32.5% | 0.86 | -14.4% |
| MOM_FAST | 42 | +25.7% | 0.72 | -13.3% |
| MOM_SLOW | 42 | +25.4% | 0.72 | -13.3% |
| MOM_SLOW | 63 *(base)* | +32.5% | 0.86 | -14.4% |
| MOM_SLOW | 126 | +17.5% | 0.51 | -16.6% |
| TRAIL_ATR_MULT | 2.0 | +27.9% | 0.77 | -14.8% |
| TRAIL_ATR_MULT | 2.5 *(base)* | +32.5% | 0.86 | -14.4% |
| TRAIL_ATR_MULT | 3.0 | +34.7% | 0.89 | -14.6% |
| MOM_TOP_N | 6 | +32.6% | 0.93 | -11.8% |
| MOM_TOP_N | 8 *(base)* | +32.5% | 0.86 | -14.4% |
| MOM_TOP_N | 10 | +30.7% | 0.80 | -14.3% |

Sensitivity plateau: **PASS** (every run must keep Sharpe >= 0.3)

## Verdict

Champion **apex_hybrid** (hybrid core+pullback, base params): **CLEARED FOR LIVE DEPLOYMENT**
