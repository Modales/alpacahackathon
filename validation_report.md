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
| pure_rsi2 | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -1.8% | -0.42 | -9.1% | 86 |
| pure_rsi2 | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +0.8% | 0.23 | -5.9% | 135 |
| pure_rsi2 | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +8.4% | 1.20 | -4.8% | 223 |
| fast_momentum | 2025-01..2025-06 | 2025-01-02..2025-06-30 | +3.2% | 0.65 | -8.7% | 68 |
| fast_momentum | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +14.9% | 1.84 | -6.6% | 95 |
| fast_momentum | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +6.5% | 0.74 | -10.2% | 123 |
| tight_stops | 2025-01..2025-06 | 2025-01-02..2025-06-30 | +1.0% | 0.21 | -14.4% | 77 |
| tight_stops | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +15.1% | 1.50 | -10.4% | 92 |
| tight_stops | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +10.6% | 0.93 | -12.8% | 125 |
| conservative | 2025-01..2025-06 | 2025-01-02..2025-06-30 | +1.2% | 0.42 | -6.5% | 80 |
| conservative | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +10.5% | 2.13 | -3.2% | 105 |
| conservative | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +3.0% | 0.58 | -5.6% | 132 |
| rho_gate | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -0.7% | -0.07 | -12.3% | 67 |
| rho_gate | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +14.6% | 1.74 | -7.8% | 81 |
| rho_gate | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +7.5% | 0.82 | -11.0% | 104 |
| persist_gate | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -0.9% | -0.12 | -10.7% | 65 |
| persist_gate | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +14.5% | 1.83 | -5.7% | 73 |
| persist_gate | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +7.0% | 0.82 | -9.8% | 91 |
| vov_gate | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -0.4% | -0.03 | -9.6% | 59 |
| vov_gate | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +13.0% | 1.67 | -8.7% | 63 |
| vov_gate | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +6.5% | 0.73 | -8.2% | 94 |
| flow_momentum | 2025-01..2025-06 | 2025-01-02..2025-06-30 | -0.1% | 0.05 | -11.8% | 68 |
| flow_momentum | 2025-07..2025-12 | 2025-07-01..2025-12-31 | +24.2% | 2.61 | -4.7% | 89 |
| flow_momentum | 2026-01..2026-08 | 2026-01-02..2026-08-28 | +9.4% | 0.94 | -10.4% | 132 |

## 2. Deployment gates

| variant | IS Sharpe | OOS Sharpe (mean) | gates | verdict |
|---|---|---|---|---|
| apex_hybrid | 0.26 | 1.11 | all pass | DEPLOY |
| core_momentum | 0.73 | 0.74 | every fold Sharpe > 0 | REJECT |
| pullback_only | 0.21 | 0.09 | OOS Sharpe >= 0.5 (mean), every fold Sharpe > 0, degradation < 50% | REJECT |
| etf_rotation | 0.39 | 1.10 | all pass | DEPLOY |
| tilted_pullback | -0.07 | 0.60 | every fold Sharpe > 0 | REJECT |
| pure_rsi2 | -0.24 | 0.34 | OOS Sharpe >= 0.5 (mean), every fold Sharpe > 0 | REJECT |
| fast_momentum | 0.20 | 1.08 | all pass | DEPLOY |
| tight_stops | 0.47 | 0.88 | all pass | DEPLOY |
| conservative | 0.15 | 1.04 | all pass | DEPLOY |
| rho_gate | 0.17 | 0.83 | every fold Sharpe > 0 | REJECT |
| persist_gate | 0.39 | 0.84 | every fold Sharpe > 0 | REJECT |
| vov_gate | 0.32 | 0.79 | every fold Sharpe > 0 | REJECT |
| flow_momentum | 0.42 | 1.20 | all pass | DEPLOY |

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

## 4. Round 3 — novel-alpha hypotheses + champion promotion

| hypothesis | IS Sharpe | OOS Sharpe | verdict |
|---|---|---|---|
| flow_momentum | 0.42 | 1.20 | DEPLOY -> promoted to live ranking |
| rho_gate | 0.17 | 0.83 | REJECT (2025-H1 fold Sharpe -0.07) |
| persist_gate | 0.39 | 0.84 | REJECT (2025-H1 fold Sharpe -0.12) |
| vov_gate | 0.32 | 0.79 | REJECT (2025-H1 fold Sharpe -0.03) |

flow_momentum post-promotion sensitivity (FLOW_MOMENTUM on, 18 perturbations,
full period): all profitable, Sharpe range 0.49-1.03, base +36.5% / Sharpe 0.98
vs apex_hybrid +32.5% / 0.86. Plateau PASS. Multiple-comparison caveat: 13
variants tested; live paper ledger is the final arbiter.
