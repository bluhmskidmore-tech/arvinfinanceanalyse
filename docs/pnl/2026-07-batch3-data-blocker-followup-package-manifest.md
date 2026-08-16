# 2026-07 Batch 3 Gate V3 Data Diagnostics Package Manifest

- package_name: 2026-07-05-stock-strategy-batch3-gate-v3-data-diagnostics-pack.zip
- workspace: F:\MOSS-V3
- generated_at: 2026-07-05
- status: research_only / no-go
- live_strategy_changes: none
- package_path_policy: ZIP entries preserve repo-relative paths
- package_entry_count: 43
- package_flat_entry_count: 0

## New Or Updated Reports

- docs/pnl/2026-07-batch3-summary.md
- docs/pnl/2026-07-batch3-csi300-benchmark-backfill-report.md
- docs/pnl/2026-07-adjusted-vs-unadjusted-report.md
- docs/pnl/2026-07-batch3-data-blocker-resolution-report.md
- docs/pnl/2026-07-batch3-post-data-fix-risk-budget-report.md
- docs/pnl/2026-07-batch3-post-data-fix-hold-progress-report.md
- docs/pnl/2026-07-batch3-gate-exposure-repair-v3-report.md
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
- docs/pnl/batch3_hold_progress_exit_path_mode_portfolio.csv

## Source And Tests

- scripts/run_batch3_stock_strategy_research.py
- scripts/backfill_csi300_benchmark_from_backup.py
- scripts/backfill_stock_adjustment_factor.py
- scripts/backfill_adjusted_returns.py
- tests/test_batch3_stock_strategy_research.py
- tests/test_csi300_benchmark_backfill.py
- tests/test_adjusted_returns_backfill.py
- docs/pnl/2026-07-batch3-data-blocker-followup-package-test-log.md

## Decision Summary

- Overall: no-go / research_only.
- Live strategy changes: none.
- Gate exposure: v3 is ready for strategy trading-day coverage. Trading-day fallback is 0.000000, true_trading_day_missing_count is 0, and calendar fallback 0.342229 is now classified as non-trading natural-date pipeline warning.
- CSI300 benchmark backfill: completed from local backup; inserted 306 `CA.CSI300` rows for 2024-09-25 through 2025-12-29 after making `F:\MOSS-V3\data\moss.pre-csi300-followup-20260705.duckdb`. Backup SHA-256 is recorded in the backfill report.
- Gate supplement: 418 window rows, but no exposure/state fields, so it remains an input table, not exposure history.
- Liquidity unit/capacity: blocked. Source lineage confirms pass-through `AMOUNT -> amount -> daily_amount`, but does not confirm canonical `daily_amount_rmb`; raw 20m/50m/100m/200m thresholds all have zero pass rows.
- Adjustment-factor gap: blocked. Local `stock_adjustment_factor` has 589,256 rows, 350 dates, and 1,689 codes, but all 61 missing path dates are absent from the table; missing ratio remains 0.175922 and clean subset share remains 0.112591. No forward-fill was applied.
- Adjusted returns: local backfill completed; candidate rows updated 5,493, universe rows 1,186, execution rows 5,493. This did not resolve path-level adj_factor gaps.
- Tushare adj_factor live fetch: attempted after dry-run but failed before writing with `api.waditu.com` connect timeout. The pre-attempt backup is `F:\MOSS-V3\data\moss.pre-adj-factor-followup-20260705.duckdb`.
- Risk-budget 0.003/0.005 post-data-fix study: still blocked until liquidity unit and adjustment coverage pass.
- Risk-budget 0.005 after trading-day gate repair remains research_only; bootstrap/liquidity/adjustment gates still fail.
- Hold-progress exit: research_only. Priority retest order is `day5_underwater_exit`, `day3_underwater_exit`, `day3_underwater_reduce_half`; none is a paper-trading rule while liquidity/adjustment blockers remain.
