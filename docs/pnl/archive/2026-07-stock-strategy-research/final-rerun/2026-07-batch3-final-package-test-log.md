# 2026-07 Batch 3 Final Package Test Log

- generated_at: 2026-07-05
- db_path: F:\MOSS-V3\data\moss.duckdb
- package_scope: Batch 3 stock-strategy research reports only
- live_strategy_changes: none
- gitnexus_mcp: unavailable in this Codex tool surface; local code inspection and tests were used instead

## Generation

Command:

```powershell
python scripts/run_batch3_stock_strategy_research.py --db-path F:\MOSS-V3\data\moss.duckdb --output-dir docs/pnl
```

Result:

```json
{
  "data_readiness": "blocked",
  "gate_exposure_repair": "blocked",
  "liquidity_unit_capacity": "blocked",
  "risk_budget": "research_only",
  "risk_budget_robustness_v2": "research_only",
  "adjustment_factor_gap": "research_only",
  "hold_progress_exit": "research_only",
  "hold_progress_exit_path_mode": "research_only",
  "entry_premium": "research_only",
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

Result: `20 passed`.

```powershell
python -m pytest tests/test_batch3_stock_strategy_research.py tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_adjusted_returns_backfill.py tests/test_matched_baseline.py tests/test_walk_forward_threshold_scan.py -q
```

Result: `68 passed`.

```powershell
python -m pytest backend/tests/core_finance/test_strategy_policy.py -q
```

Result: `4 passed`.

```powershell
python -m pytest tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer -q
```

Result: `1 passed`.

## Key Evidence

- Gate exposure remains blocked: calendar-day fallback ratio 0.822606; trading-day fallback ratio 0.774869.
- Liquidity unit remains unverified: daily_amount max 17,572,905.892, zero rows pass 20m/50m/100m/200m RMB thresholds.
- Adjustment-factor gap remains material: 3,564 missing rows out of 20,259 path rows.
- Path-mode no-progress exits remain research_only: no rule is non-worse on both fixed_20d and risk_budget_0p005 return/drawdown.
- Risk-budget 0.005 remains research_only: daily and month-cluster bootstrap p10 increments are negative; walk-forward return underperforms fixed_20d.
- Risk-budget 0.010 remains rejected_too_concentrated.
