# 2026-07 Batch 3 Risk-Budget 0.003 / 0.005 Post-Data-Fix Report

- status: blocked
- reason: Post-data-fix robustness cannot be run as a promotion study until gate, liquidity, and adjustment data blockers are resolved.
- risk_budget_candidates: ['0.003', '0.005']

## Blockers Before Promotion Study

- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%; promotion conclusions would be sample-biased
- daily_amount upstream unit remains unverified
- liquidity thresholds have no passing known rows under raw unit

This report is intentionally blocked. Run the 0.003/0.005 comparison only after gate exposure, liquidity unit, and adjustment factor blockers are resolved.
