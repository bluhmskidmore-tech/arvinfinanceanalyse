# 2026-07 Batch 3 A-Share Follow-Up Returnwork Package Test Log

- generated_at: 2026-07-05
- db_path: F:\MOSS-V3\data\moss.duckdb
- package_scope: Batch 3 A-share strategy optimization follow-up returnwork
- live_strategy_changes: none
- gitnexus_mcp: unavailable in this Codex tool surface; local inspection, native subagents, and targeted tests were used instead

## Generation

```powershell
python scripts/run_batch3_stock_strategy_research.py --db-path F:\MOSS-V3\data\moss.duckdb --output-dir docs/pnl --followup-only
```

Result summary:

```json
{
  "gate_fallback_split": "ready",
  "liquidity_canonical_rmb": "blocked",
  "adjustment_factor_repair": "blocked",
  "canonical_research_dataset": "schema_ready",
  "risk_budget_optimization": "blocked",
  "underwater_exit_overlay_optimization": "blocked",
  "a_share_trading_constraint": "blocked",
  "a_share_optimization_summary": "blocked"
}
```

## Canonical Dataset Verification

- canonical_strategy_paths.parquet: 20,634 rows x 39 columns
- canonical_strategy_trades.parquet: 826 rows x 32 columns
- canonical_data_quality_summary.csv: includes engine/canonical/within-horizon adjustment denominator scopes
- manifest status: `schema_ready / data_quality_blocked / promotion_blocked`
- adjustment repair report denominator scope source: `canonical_research_dataset`
- adjustment denominator tie-out: `engine_path_rows=20259`, `canonical_path_rows=20634`, `within_horizon_path_rows=15677`
- `exit_price_adjusted` missing in trades: 3 / 826, down from the prior 100% null issue
- `paths_gate_exposure_null_ratio`: 0.001212; affected rows are now explicitly flagged
- `raw_daily_amount`, `raw_volume`, `raw_close`, `amount_volume_close_ratio`, and `implied_amount_multiplier_diagnostic` are emitted in canonical paths

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
python -m pytest tests/test_adjusted_returns_backfill.py tests/test_batch3_stock_strategy_research.py -q
```

Result: `49 passed`.

```powershell
python -m pytest tests/test_adjusted_returns_backfill.py tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py -q
```

Result: `59 passed`.

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py tests/test_csi300_benchmark_backfill.py tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_adjusted_returns_backfill.py tests/test_matched_baseline.py tests/test_walk_forward_threshold_scan.py backend/tests/core_finance/test_strategy_policy.py tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer -q
```

Result: `110 passed`.

## Remaining No-Go Reasons

- `daily_amount_rmb_canonical` remains blocked until vendor/unit lineage confirms RMB conversion.
- Adjustment factor missing coverage remains above the 2% promotion threshold.
- Canonical dataset is schema-ready, but data quality and promotion are still blocked.
- A-share execution constraints remain research-only/incomplete until lot sizing, ST treatment, capacity, and delayed limit-down/halt/missing-open exits are modeled.
