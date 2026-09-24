# 2026-07 Batch 3 Returnwork Package Test Log

- generated_at: 2026-07-05
- db_path: F:\MOSS-V3\data\moss.duckdb
- package_scope: Batch 3 final evaluation返工包
- live_strategy_changes: none
- gitnexus_mcp: unavailable in this Codex tool surface; local code inspection and tests were used instead

## Generation

```powershell
python scripts/run_batch3_stock_strategy_research.py --db-path F:\MOSS-V3\data\moss.duckdb --output-dir docs/pnl
```

Result summary:

```json
{
  "data_readiness": "blocked",
  "gate_exposure_repair_v2": "blocked",
  "liquidity_unit_capacity_v2": "blocked",
  "adjustment_factor_gap_v2": "blocked",
  "path_engine_tieout": "ready",
  "risk_budget_003_005_post_data_fix": "blocked",
  "hold_progress_exit_path_mode": "research_only",
  "summary": "research_only"
}
```

## Verification Commands

```powershell
python -m py_compile scripts/run_batch3_stock_strategy_research.py
```

Result: exit 0.

```powershell
python -m ruff check scripts/run_batch3_stock_strategy_research.py tests/test_batch3_stock_strategy_research.py
```

Result: `All checks passed!`

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py -q
```

Result: `21 passed`.

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_adjusted_returns_backfill.py tests/test_matched_baseline.py tests/test_walk_forward_threshold_scan.py -q
```

Result: `69 passed`.

```powershell
python -m pytest backend/tests/core_finance/test_strategy_policy.py -q
python -m pytest tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer -q
```

Result: `4 passed` and `1 passed`.

## Key Evidence

- Path-engine tie-out fixed: fixed_20d, risk_0.005, and risk_0.010 baseline cumulative return/maxDD/Sharpe all have zero delta versus `run_portfolio_backtest(mode="path")`.
- Gate exposure remains blocked: calendar fallback 0.822606; trading-day fallback 0.774869.
- Liquidity remains blocked: raw `daily_amount` has zero pass rows at 20m/50m/100m/200m; unit remains unverified.
- Adjustment-factor gap remains blocked: missing adjustment paths remain and clean subset is explicitly sample-biased.
- Hold-progress path-mode is research_only: `day3_underwater_reduce_half` is only a research lead, not a paper-trading candidate, because data gates fail.
- Risk-budget 0.003/0.005 post-data-fix report is intentionally blocked until data blockers are resolved.
