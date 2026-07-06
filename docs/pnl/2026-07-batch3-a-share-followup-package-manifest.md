# 2026-07 Batch 3 A-Share Follow-Up Returnwork Package Manifest

- package_name: 2026-07-05-stock-strategy-batch3-a-share-followup-returnwork-pack.zip
- workspace: F:\MOSS-V3
- generated_at: 2026-07-05
- status: blocked / research_only
- live_strategy_changes: none
- package_path_policy: ZIP entries preserve repo-relative paths

## Reports

- docs/pnl/2026-07-batch3-gate-fallback-split-report.md
- docs/pnl/2026-07-batch3-liquidity-canonical-rmb-report.md
- docs/pnl/2026-07-batch3-adjustment-factor-repair-report.md
- docs/pnl/2026-07-batch3-risk-budget-optimization-report.md
- docs/pnl/2026-07-batch3-underwater-exit-overlay-optimization-report.md
- docs/pnl/2026-07-batch3-a-share-trading-constraint-report.md
- docs/pnl/2026-07-batch3-a-share-optimization-summary.md

## Canonical Research Artifacts

- data/research/2026-07-batch3/canonical_strategy_paths.parquet
- data/research/2026-07-batch3/canonical_strategy_trades.parquet
- data/research/2026-07-batch3/canonical_data_quality_summary.csv
- data/research/2026-07-batch3/canonical_dataset_manifest.json

## Source And Tests

- scripts/run_batch3_stock_strategy_research.py
- scripts/backfill_csi300_benchmark_from_backup.py
- scripts/backfill_stock_adjustment_factor.py
- scripts/backfill_adjusted_returns.py
- tests/test_batch3_stock_strategy_research.py
- tests/test_csi300_benchmark_backfill.py
- tests/test_adjusted_returns_backfill.py
- docs/pnl/2026-07-batch3-a-share-followup-package-test-log.md

## Decision Summary

- Overall: no-go / research_only.
- Paper trading: NO.
- Live strategy change: NO.
- Gate split: path simulation gate is ready; `trading_day_exposure_fallback_ratio=0`, while `calendar_gate_fallback_ratio=0.342229` remains a pipeline warning.
- Liquidity: blocked. `daily_amount_rmb_canonical` is not verified by vendor/unit lineage; raw amount, volume, close, and implied ratio diagnostics are now emitted.
- Adjustment factor: blocked. Denominator scopes now report `engine_path_rows`, `canonical_path_rows`, and `within_horizon_path_rows`.
- Canonical dataset: `schema_ready / data_quality_blocked / promotion_blocked`; it is a research dataset, not a go signal.
- Risk budget: optimization remains skipped while blockers exist; the required full grid is declared as `risk_per_trade x single_name_cap x downside_portfolio_exposure_cap`, where numeric exposure cells clamp the existing gate series rather than levering exposure above it.
- Underwater exit overlay: `day5_underwater_exit` and `day3_underwater_reduce_half` remain frozen prior research leads only.
- A-share constraints: `research_only_incomplete`; 100-share lot sizing, ST handling, capacity, and limit-down delayed exits are not fully integrated.
- Adjustment-factor backfill: non-dry-run writes now require `--target-backup-path` or `--governance-lock`; partial vendor responses only replace returned keys and preserve existing rows.
