# 2026-07 Batch 3 Post-Data-Fix Risk-Budget Report

- status: blocked
- db_path: F:\MOSS-V3\data\moss.duckdb
- reason: Formal post-data-fix risk-budget study is blocked until gate, liquidity, and adjustment blockers are all resolved.
- risk_budget_candidates: ['0.003', '0.005']

## Required Comparisons

- fixed_20d
- risk_budget_0.003
- risk_budget_0.005
- exposure_matched_fixed_control

## Required Checks

- daily bootstrap
- month-cluster bootstrap
- walk-forward
- year/market-state/volatility/liquidity slices

## Current Blockers

- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%
- daily_amount upstream unit remains unconfirmed
- raw liquidity thresholds still have zero passing rows

No promotion conclusion is allowed while any blocker remains.
