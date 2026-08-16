# 2026-07 Batch 3 Package Manifest

- scope: revised research/report-only Batch 3 stock-strategy validation
- live_candidate_generation_changed: no
- live_risk_exit_changed: no
- live_formula_version_changed: no
- data_readiness_status: blocked
- risk_budget_status: research_only
- hold_progress_exit_status: research_only
- entry_premium_status: research_only
- summary_go_no_go: no-go
- risk_budget_0p010_too_concentrated: true
- hold_progress_exit_recommendation: research_only/no-go
- hold_progress_portfolio_mode: horizon_diagnostic, diagnostic_only_not_comparable_to_path_mode_risk_report

## Included Source

- scripts/run_batch3_stock_strategy_research.py
- tests/test_batch3_stock_strategy_research.py

## Included Reports

- 2026-07-batch3-data-readiness-report.md
- 2026-07-batch3-risk-budget-robustness-report.md
- 2026-07-batch3-hold-progress-exit-simulation-report.md
- 2026-07-batch3-entry-premium-interaction-report.md
- 2026-07-batch3-summary.md
- 2026-07-batch3-test-log.md

## Included CSV

- docs/pnl/batch3_equity_*.csv
- docs/pnl/batch3_hold_progress_exit_positions.csv
- docs/pnl/batch3_hold_progress_exit_portfolio.csv

## Verification

- python -m pytest tests/test_batch3_stock_strategy_research.py -q -> 14 passed
- python -m ruff check scripts/run_batch3_stock_strategy_research.py tests/test_batch3_stock_strategy_research.py -> passed
- python -m pytest tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_walk_forward_threshold_scan.py tests/test_matched_baseline.py tests/test_batch3_stock_strategy_research.py -q -> 60 passed
- python -m pytest backend/tests/core_finance/test_strategy_policy.py -q -> 4 passed

## Revised Fixes

- Fixed the risk_budget_0.010 concentration key mismatch by using `risk_budget_rpt_0p01`.
- Marked risk_budget_0.010 too concentrated when max single-name weight exceeds 20% or max drawdown reaches 25%.
- Downgraded hold-progress exit recommendation to research_only/no-go unless position-level and portfolio-level conditions pass under path-mode consistency.
- Marked hold-progress portfolio comparison as horizon_diagnostic / diagnostic-only, not comparable to the path-mode risk-budget baseline.
- Promoted gate exposure fallback ratio above 10% to a hard data-readiness blocker.
- Added liquidity amount distribution, gate missing-date ranges, and adjustment-factor top-offender diagnostics.
- Added calendar-year and volatility-regime risk slices.
