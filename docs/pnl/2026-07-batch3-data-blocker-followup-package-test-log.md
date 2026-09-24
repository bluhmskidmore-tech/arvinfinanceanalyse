# 2026-07 Batch 3 Gate V3 Data Diagnostics Package Test Log

- generated_at: 2026-07-05
- db_path: F:\MOSS-V3\data\moss.duckdb
- package_scope: Batch 3 CSI300 gate follow-up evaluation returnwork
- live_strategy_changes: none
- gitnexus_mcp: unavailable in this Codex tool surface; local code inspection, read-only subagents, and targeted tests were used instead

## Data Backfills And Attempts

### CSI300 Benchmark Backfill

Target backup before write:

```powershell
F:\MOSS-V3\data\moss.pre-csi300-followup-20260705.duckdb
```

Backup metadata:

```json
{
  "size_bytes": 1082929152,
  "created_at": "2026-07-05T07:39:42",
  "last_write_time": "2026-07-05T04:18:22",
  "sha256": "5F3E6F589534CE9BE23F1A3327F46D41B81E41F28D4C5F6EA7FDB015BF16D355"
}
```

Command:

```powershell
python scripts/backfill_csi300_benchmark_from_backup.py --duckdb-path F:\MOSS-V3\data\moss.duckdb --backup-duckdb-path F:\MOSS-V3\data\moss.pre-stock-refresh-20260618T171201.duckdb --start-date 2024-09-25 --end-date 2026-06-23 --governance-dir F:\MOSS-V3\data\governance
```

Result:

```json
{
  "status": "completed",
  "inserted_count": 306,
  "inserted_min_date": "2024-09-25",
  "inserted_max_date": "2025-12-29",
  "conflict_count": 0
}
```

### Adjustment Factor Fetch Attempt

Dry-run:

```powershell
python scripts/backfill_stock_adjustment_factor.py --db-path F:\MOSS-V3\data\moss.duckdb --start-date 2024-09-25 --end-date 2026-06-23 --dry-run
```

Dry-run result: 1,689 codes, 314 selected dates, would call Tushare.

Target backup before attempted live fetch:

```powershell
F:\MOSS-V3\data\moss.pre-adj-factor-followup-20260705.duckdb
```

Backup metadata:

```json
{
  "size_bytes": 1082929152,
  "created_at": "2026-07-05T08:52:32",
  "last_write_time": "2026-07-05T07:39:54",
  "sha256": "C44D79F67C16AAE5651B8F34F1BD8B5F125BB979E0D6B51A5E89532339ED5D6F"
}
```

Live fetch command:

```powershell
python scripts/backfill_stock_adjustment_factor.py --db-path F:\MOSS-V3\data\moss.duckdb --start-date 2024-09-25 --end-date 2026-06-23
```

Result: failed before write with `HTTPConnectionPool(host='api.waditu.com', port=80)` connect timeout. The script fetches rows before opening the write transaction, so no partial adj_factor write was made by this failed attempt.

### Adjusted Returns Backfill

Command:

```powershell
python scripts/backfill_adjusted_returns.py --db-path F:\MOSS-V3\data\moss.duckdb --start-date 2024-09-25 --end-date 2026-06-23 --report-path docs/pnl/2026-07-adjusted-vs-unadjusted-report.md
```

Result:

```json
{
  "status": "completed",
  "candidate_updated_count": 5493,
  "universe_updated_count": 1186,
  "execution_updated_count": 5493,
  "report_path": "F:\\MOSS-V3\\docs\\pnl\\2026-07-adjusted-vs-unadjusted-report.md"
}
```

## Generation

```powershell
python scripts/run_batch3_stock_strategy_research.py --db-path F:\MOSS-V3\data\moss.duckdb --output-dir docs/pnl
```

Result summary:

```json
{
  "data_readiness": "blocked",
  "gate_exposure_repair_v3": "ready",
  "liquidity_unit_capacity_v2": "blocked",
  "adjustment_factor_gap_v2": "blocked",
  "data_blocker_resolution": "blocked",
  "path_engine_tieout": "ready",
  "risk_budget_003_005_post_data_fix": "blocked",
  "post_data_fix_risk_budget": "blocked",
  "post_data_fix_hold_progress": "blocked",
  "hold_progress_exit_path_mode": "research_only",
  "summary": "research_only"
}
```

## Verification Commands

```powershell
python -m py_compile scripts/run_batch3_stock_strategy_research.py scripts/backfill_csi300_benchmark_from_backup.py scripts/backfill_stock_adjustment_factor.py scripts/backfill_adjusted_returns.py tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py tests/test_adjusted_returns_backfill.py
```

Result: exit 0.

```powershell
python -m ruff check scripts/run_batch3_stock_strategy_research.py scripts/backfill_csi300_benchmark_from_backup.py scripts/backfill_stock_adjustment_factor.py scripts/backfill_adjusted_returns.py tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py tests/test_adjusted_returns_backfill.py
```

Result: `All checks passed!`

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py -q
```

Result: `43 passed`.

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_adjusted_returns_backfill.py tests/test_matched_baseline.py tests/test_walk_forward_threshold_scan.py backend/tests/core_finance/test_strategy_policy.py tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer -q
```

Result: `96 passed`.

## Package Verification

Package path:

```powershell
C:\Users\arvin\Desktop\2026-07-05-stock-strategy-batch3-gate-v3-data-diagnostics-pack.zip
```

Result:

```json
{
  "entry_count": 43,
  "flat_entry_count": 0
}
```

## Key Evidence

- Exact-zero logic remains covered: `fallback_ratio=0.0` and non-worse deltas `0.0` are accepted by recommendation gates.
- Gate v3: `calendar_gate_fallback_ratio=0.342229`, `trading_day_gate_fallback_ratio=0.000000`, `true_trading_day_missing_count=0`, `calendar_missing_classification=non_trading_dates_only`.
- Gate supplement: `fact_livermore_gate_supplement_daily` has 418 rows in the execution window, but only `breadth_5d` and `limit_up_quality_ok` are mappable inputs; no exposure/state fields exist.
- Liquidity remains blocked: raw `daily_amount` has zero pass rows at 20m/50m/100m/200m. Source lineage confirms pass-through storage but not canonical RMB conversion; `amount_over_volume_x_close_median=0.099737`.
- Adjustment-factor gap remains blocked: 3,564 missing path rows, missing ratio 0.175922, clean subset share 0.112591. Local adj_factor table has 589,256 rows but all 61 missing path dates are absent from that table.
- Path-mode portfolio CSV exists: docs/pnl/batch3_hold_progress_exit_path_mode_portfolio.csv, 21 data rows.
- Hold-progress path-mode is research_only: `day5_underwater_exit`, `day3_underwater_exit`, and `day3_underwater_reduce_half` are retest leads, not paper-trading candidates.
- No Batch 3 result is wired into live strategy behavior.
