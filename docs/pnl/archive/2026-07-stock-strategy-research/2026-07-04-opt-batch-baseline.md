# 2026-07-04 Stock Strategy Optimization Baseline

## Task 0 Result

- Branch: `opt/2026-07-validity-batch`
- Workspace state: dirty before branch creation; existing unrelated user/repo changes were preserved.
- Baseline status: non-green. This records the actual repository state before Task 1 policy refactoring.

## Verification Baseline

| Command | Result |
| --- | --- |
| `python -m pytest -q backend/tests/core_finance tests` | failed: `124 failed, 5284 passed, 6 skipped in 4425.80s (1:13:45)` |
| `cd frontend && npm run typecheck` | passed |
| `cd frontend && npm test` | failed: `40 failed, 2868 passed (2908)` across `9 failed \| 285 passed` files |

### Backend Failure Clusters

The failing backend baseline is broad and mostly outside the stock strategy slice. Representative clusters:

- Bond analytics exact-output and formal-lineage tests, including `tests/test_bond_analytics_service_real_data.py` and `tests/test_bond_dashboard_headlines_contract.py`.
- Route/auth boundary inventory drift, including `tests/test_boundary_surface_inventory.py`.
- Calculation P1 owner decision packet/snapshot drift.
- Portfolio-home owner intake, evidence, closure, and system-audit guard suites.
- Risk tensor and yield curve repository regressions.
- One stock-adjacent wrapper test: `tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer`.

### Frontend Failure Clusters

Representative frontend failures:

- `src/test/CrossAssetPage.test.tsx`: 28 failures, mostly data-testid/layout contract drift.
- `src/test/StartupPerformanceGuards.test.ts`: 5 failures.
- Stock analysis CSS/class guard failures:
  - `src/test/StockAnalysisPageSizeGuard.test.ts`
  - `src/test/StockAnalysisPageCopy.test.ts`
  - `src/test/StockAnalysisCycleRuleSummary.test.tsx`
  - `src/test/StockAnalysisDeepZoneHeader.test.tsx`
  - `src/test/theme.test.ts`
- `src/test/BondAnalyticsClient.test.ts` and `src/test/ContributionSection.test.tsx`.

## DuckDB Schema Registry Baseline

Current `backend/app/schema_registry/duckdb/` numbered files include:

- `21_choice_stock.sql`
- `22_livermore_position_snapshot.sql`
- `23_livermore_gate_supplement.sql`
- `24_cffex_member_rank.sql`
- `25_pnl_by_business_precompute.sql`
- `27_choice_stock_factor_snapshot.sql`
- `28_livermore_candidate_history.sql`
- `29_commodity_futures_daily.sql`

Number `26` is currently unused, but the highest occupied number is `29`. For new migrations in this batch, prefer the next highest unused number after `29` unless the project explicitly chooses to fill the gap.

## Script CLI Convention

Existing Livermore scripts use explicit `--db-path` style arguments and local path resolution:

- `scripts/export_livermore_pretrade_check.py`
  - Public function takes `duckdb_path`.
  - CLI parser exposes an explicit database path argument.
  - Runtime opens DuckDB read-only for export with `duckdb.connect(str(resolved_path), read_only=True)`.
- `scripts/run_livermore_daily_pretrade_refresh.py`
  - Public function takes `duckdb_path`.
  - CLI parser follows the same explicit database path pattern.
  - Inspection/read paths resolve the supplied path before connecting.

New backfill/validation scripts should follow the same pattern: explicit `--db-path`, path normalization, and read-only connections wherever mutation is not required.

## Task 1 Read-Only Inventory

Subagents performed read-only inventory only; no files were edited.

### Market States And Macro Multipliers

- `backend/app/core_finance/mean_reversion_candidates.py`
  - `FORMULA_VERSION = "rv_mean_reversion_candidates_v2"`
  - `ACTIVE_MARKET_STATES = frozenset({"WARM"})`
- `backend/app/core_finance/hybrid_fusion_candidates.py`
  - `FORMULA_VERSION = "rv_hybrid_fusion_candidates_v3"`
  - active states are `{"WARM", "HOT"}`
- `backend/app/services/livermore_signal_confluence_service.py`
  - entry observation states are `{"WARM", "HOT"}`
  - macro multipliers: `supportive=1.0`, `neutral=0.5`, `restrictive=0.0`, `unknown=0.0`

### Market Gate Exposure Mirror

`backend/app/core_finance/livermore_strategy.py` derives exposure as `round(passed_conditions / 4, 4)` for normal states, with special states returning `0.0`.

Possible observed/mirrored exposure values:

- `NO_DATA`: `0.0`
- `STALE`: `0.0`
- `PENDING_DATA`: `0.0`
- `OFF`: `0.0` or `0.25`
- `WARM`: `0.25`, `0.5`, or `0.75`
- `HOT`: `0.75`
- `OVERHEAT`: `1.0`

Task 1 should avoid converting this into a misleading single-value map for states that can have multiple exposures.

### Stock Candidate Constants

- `FORMULA_VERSION = "rv_livermore_stock_candidates_bundle_v7"`
- `MIN_HISTORY = 120`
- `EMA_WINDOW = 10`
- `MAX_RANKED = 6`
- `MAX_BREAKOUT_EXTENSION_NORM = 0.35`
- `GAP_NORM_MIN = 0.0`
- `ABNORMAL_TURNOVER_MIN_V7 = 1.2`
- `ABNORMAL_TURNOVER_MAX_V7 = 2.0`
- `CROWDED_LEADER_TURNOVER_BLOCK = 2.0`
- fundamental overlay top fractions: default `0.5`, WARM `1 / 3`
- current stock policies:
  - `default`: active `WARM/HOT/OVERHEAT`, close strength `0.95`, gap max `0.45`, turnover `[1.2, 2.0)`
  - `exp3b`: active `WARM/HOT`, close strength `0.99`, gap max `0.35`, turnover `[1.2, 2.4]`, close-strength-first
  - `exp3c_shadow`: active `WARM/HOT`, close strength `0.99`, gap max `0.35`, turnover `[1.0, 2.4]`
  - `v6_compat`: active `WARM/HOT/OVERHEAT`, close strength `0.95`, gap max `0.45`, turnover `[1.0, 3.5]`

The plan's FOMO "exemption" is implemented as a rank-1 crowded-leader block: `sector_rank == 1 and abnormal_turnover >= 2.0`.

### Risk Exit Constants

- `FORMULA_VERSION = "rv_livermore_risk_exit_ema10_volume_v2"`
- `MIN_HISTORY = 21`
- `EMA_WINDOW = 10`
- `VOLUME_MA_WINDOW = 20`
- `VOLUME_CONFIRMATION_RATIO = 1.3`
- trigger remains `price_below_ema and volume_confirmed`
- reason string remains `2d_below_ema10_with_volume`

### Costs And Monitoring Thresholds

- `backend/app/tasks/livermore_candidate_history_materialize.py`
  - `FORMULA_VERSION = "fv_livermore_candidate_forward_close_unadjusted_v1"`
  - `EXECUTION_FORMULA_VERSION = "fv_livermore_candidate_execution_next_open_unadjusted_v1"`
  - `BUY_COST_RATE = 0.0008`
  - `SELL_COST_RATE = 0.0013`
  - `SLIPPAGE_RATE = 0.0010`
  - net execution drag is `buy + sell + 2 * slippage = 0.0041`
- `scripts/stock_strategy_health_diagnostic.py`
  - `FACTOR_SCREEN_PRIMARY_COVERAGE_THRESHOLD = 0.8`
  - `FACTOR_SCREEN_PARTIAL_COVERAGE_THRESHOLD = 0.5`
  - `FACTOR_SCREEN_FRESHNESS_THRESHOLD_DAYS = 3`

## Proceeding Note

The full repository baseline is non-green before Task 1. The stock-strategy-targeted subset was green before this plan, but Task 0's mandated all-repo commands expose unrelated existing failures. Subsequent tasks should use their dedicated narrow verification commands and keep this baseline document as the comparison point.
