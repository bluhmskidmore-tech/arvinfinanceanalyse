# 2026-07 Batch 3 Final Package Manifest

- package_name: 2026-07-05-stock-strategy-batch3-final-pro-pack.zip
- workspace: F:\MOSS-V3
- generated_at: 2026-07-05
- status: research_only / no-go
- live_strategy_changes: none

## Included Reports

- 2026-07-batch3-summary.md
- 2026-07-batch3-data-readiness-report.md
- 2026-07-batch3-gate-exposure-repair-report.md
- 2026-07-batch3-liquidity-unit-capacity-report.md
- 2026-07-batch3-adjustment-factor-gap-report.md
- 2026-07-batch3-risk-budget-robustness-report.md
- 2026-07-batch3-risk-budget-robustness-v2-report.md
- 2026-07-batch3-hold-progress-exit-simulation-report.md
- 2026-07-batch3-hold-progress-exit-path-mode-report.md
- 2026-07-batch3-entry-premium-interaction-report.md

## Included CSV Outputs

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

## Included Source And Tests

- scripts/run_batch3_stock_strategy_research.py
- tests/test_batch3_stock_strategy_research.py
- 2026-07-batch3-final-package-test-log.md

## Decision Summary

- Overall: no-go / research_only.
- Data readiness: blocked.
- Gate exposure: blocked until real per-date exposure fallback ratio is below 10%.
- Liquidity capacity: blocked until daily_amount unit is confirmed and capacity thresholds are meaningful.
- Risk-budget 0.005: research_only, not live-ready.
- Risk-budget 0.010: rejected_too_concentrated.
- Hold-progress exit: research_only; path-mode simulation did not produce a candidate rule.
- Entry-premium cap: diagnostic only; no hard live cap recommended.
