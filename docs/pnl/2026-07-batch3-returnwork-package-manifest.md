# 2026-07 Batch 3 Returnwork Package Manifest

- package_name: 2026-07-05-stock-strategy-batch3-returnwork-pro-pack.zip
- workspace: F:\MOSS-V3
- generated_at: 2026-07-05
- status: research_only / no-go
- live_strategy_changes: none
- package_path_policy: ZIP entries preserve repo-relative paths

## New Or Updated Reports

- docs/pnl/2026-07-batch3-summary.md
- docs/pnl/2026-07-batch3-gate-exposure-repair-v2-report.md
- docs/pnl/2026-07-batch3-liquidity-unit-capacity-v2-report.md
- docs/pnl/2026-07-batch3-adjustment-factor-gap-v2-report.md
- docs/pnl/2026-07-batch3-path-engine-tieout-report.md
- docs/pnl/2026-07-batch3-risk-budget-003-005-post-data-fix-report.md
- docs/pnl/2026-07-batch3-hold-progress-exit-path-mode-report.md
- docs/pnl/2026-07-batch3-risk-budget-robustness-v2-report.md

## Carry-Forward Reports

- docs/pnl/2026-07-batch3-data-readiness-report.md
- docs/pnl/2026-07-batch3-gate-exposure-repair-report.md
- docs/pnl/2026-07-batch3-liquidity-unit-capacity-report.md
- docs/pnl/2026-07-batch3-adjustment-factor-gap-report.md
- docs/pnl/2026-07-batch3-risk-budget-robustness-report.md
- docs/pnl/2026-07-batch3-hold-progress-exit-simulation-report.md
- docs/pnl/2026-07-batch3-entry-premium-interaction-report.md

## CSV Outputs

- docs/pnl/batch3_equity_fixed_20d_equal.csv
- docs/pnl/batch3_equity_fixed_20d_exposure_matched_to_risk_0p005.csv
- docs/pnl/batch3_equity_fixed_5d_equal.csv
- docs/pnl/batch3_equity_risk_budget_rpt_0p003.csv
- docs/pnl/batch3_equity_risk_budget_rpt_0p005.csv
- docs/pnl/batch3_equity_risk_budget_rpt_0p0075.csv
- docs/pnl/batch3_equity_risk_budget_rpt_0p01.csv
- docs/pnl/batch3_equity_vol_target_0p15_control.csv
- docs/pnl/batch3_equity_vol_target_0p2_control.csv
- docs/pnl/batch3_hold_progress_exit_positions.csv
- docs/pnl/batch3_hold_progress_exit_portfolio.csv
- docs/pnl/batch3_hold_progress_exit_path_mode_positions.csv

## Source And Tests

- scripts/run_batch3_stock_strategy_research.py
- tests/test_batch3_stock_strategy_research.py
- docs/pnl/2026-07-batch3-returnwork-package-test-log.md

## Decision Summary

- Overall: no-go / research_only.
- Path-engine tie-out: fixed.
- Gate exposure: blocked.
- Liquidity unit/capacity: blocked.
- Adjustment-factor gap: blocked.
- Risk-budget 0.003/0.005 post-data-fix study: blocked until data gates pass.
- Hold-progress exit: research_only; `day3_underwater_reduce_half` is only a low-priority research lead.
