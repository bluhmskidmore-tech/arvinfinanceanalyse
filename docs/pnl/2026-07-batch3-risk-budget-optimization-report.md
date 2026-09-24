# 2026-07 Batch 3 Risk-Budget Optimization Report

- status: blocked
- recommendation: blocked
- selected_walk_forward_risk_per_trade: None
- risk_0p010_candidate_allowed: False
- grid_execution_status: skipped_until_data_blockers_clear
- grid_skip_reason: full risk_per_trade x single_name_cap x downside_portfolio_exposure_cap grid is not executed while data blockers remain
- portfolio_exposure_cap_semantics: numeric cells are downside clamps on the existing gate exposure series; they do not lever exposure above the gate
- required_grid_cell_count: 140
- required_risk_per_trade_grid: [0.002, 0.003, 0.004, 0.005, 0.006, 0.0075, 0.01]
- required_single_name_cap_grid: [0.1, 0.125, 0.15, 0.2, 1.0]
- required_portfolio_exposure_cap_grid: ['existing_gate', 0.5, 0.75, 1.0]
- live_strategy_changes: none

## Blockers

- adjustment factor missing ratio > 2%
- liquidity canonical RMB amount is not verified

## Optimization Table

| risk_per_trade | single_name_cap | portfolio_exposure_cap | diagnostic_only | cumulative_return | maxDD | Sharpe | max_weight | utility | hard_fail |
|---:|---:|---|---|---:|---:|---:|---:|---:|---|

## Bootstrap And Walk-Forward

- daily_bootstrap: `{"status": "skipped_until_data_blockers_clear"}`
- month_cluster_bootstrap: `{"status": "skipped_until_data_blockers_clear"}`
- walk_forward: `{"status": "skipped_until_data_blockers_clear"}`

## Slices

| slice_type | slice_value | rows | fixed_return | risk_0p005_return | increment |
|---|---|---:|---:|---:|---:|

`risk_budget_0.010` is diagnostic only and is not allowed in the candidate list.
