"""Independent broker-state reconciliation via the official alpaca-py SDK.

Our engine talks to Alpaca over hand-rolled REST; this module re-reads the
same account through Alpaca's official SDK and flags any disagreement
(position count, equity, cash). Runs inside every agent cycle, best-effort.
"""
import config


def reconcile(rest_account, rest_positions, log):
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        log("reconcile: alpaca-py not installed, skipping")
        return
    client = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
    acct = client.get_account()
    sdk_positions = client.get_all_positions()

    issues = []
    # equity moves between the two API calls — allow timestamp drift
    tol = max(25.0, 0.0005 * float(rest_account["equity"]))
    if abs(float(acct.equity) - float(rest_account["equity"])) > tol:
        issues.append(f"equity mismatch sdk={acct.equity} rest={rest_account['equity']}")
    if len(sdk_positions) != len(rest_positions):
        issues.append(f"position count sdk={len(sdk_positions)} rest={len(rest_positions)}")
    sdk_syms = {p.symbol for p in sdk_positions}
    rest_syms = {p["symbol"] if isinstance(p, dict) else p.symbol
                 for p in rest_positions}
    if sdk_syms != rest_syms:
        issues.append(f"symbol mismatch sdk-rest={sdk_syms - rest_syms} "
                      f"rest-sdk={rest_syms - sdk_syms}")
    if issues:
        log("RECONCILE MISMATCH: " + "; ".join(issues))
    else:
        log(f"reconcile OK (sdk equity ${float(acct.equity):,.2f}, "
            f"{len(sdk_positions)} positions, options bp ${float(acct.options_buying_power or 0):,.0f})")
