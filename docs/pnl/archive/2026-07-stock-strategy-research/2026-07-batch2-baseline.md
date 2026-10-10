# 2026-07-04 Stock Strategy Optimization Batch 2 Baseline

## Task 0 Result

- Branch: `opt/2026-07-position-gate-batch2`
- Inspected database: `F:\MOSS-V3\data\moss.duckdb`
- Inspection time: 2026-07-04
- Scope: batch-2 portfolio backtest, diagnostics, and reports only.
- Out of scope: live candidate generation, live risk-exit trigger behavior, confluence field semantics, auth, frontend, shared infrastructure, and unrelated backend services.

## Evidence Surface

- The working database path above is the only DuckDB target inspected in this session. No second independent production DuckDB file was discoverable from local workspace context.
- Local GitNexus CLI was available earlier in this branch and reported the index up to date at commit `9ccb4dc`.
- Direct Codex App MCP discovery did not expose callable `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, or direct `gitnexus_*` MCP tools in this session, so Task 0 uses local schema, DuckDB facts, code search, and focused tests as evidence.

## DuckDB Readiness

| Table / source | Status | Coverage | Conclusion |
| --- | --- | --- | --- |
| `livermore_candidate_execution_history` | exists, populated | 5,532 rows; 316 signal dates from `2024-08-30` to `2026-06-22`; entry dates from `2024-09-02` to `2026-06-23` | Execution history is now populated for available candidate-history dates. |
| execution statuses | populated | `complete`: 4,283; `pending`: 1,184; `entry_blocked`: 65; `entry_executable=true`: 5,467; `false`: 65 | Reports can run but must handle pending rows. |
| execution adjusted-return columns | schema present, populated | `return_1d_net_adj`: 5,242; `return_5d_net_adj`: 4,799; `return_10d_net_adj`: 4,356; `return_20d_net_adj`: 3,540 | Dual-adjust execution returns are now available where adjustment factors and forward paths exist. |
| `stock_adjustment_factor` | exists, populated | 589,256 rows; 1,689 symbols; dates from `2024-08-30` to `2026-06-22` | Adjustment-factor backfill landed locally after chunked retry. |
| `livermore_candidate_history` | exists, populated | 5,532 rows; 316 dates from `2024-08-30` to `2026-06-22` | Candidate history is available. |
| candidate adjusted-return columns | schema present, populated | `return_1d_adj`: 5,259; `return_5d_adj`: 4,920; `return_10d_adj`: 4,470; `return_20d_adj`: 3,666 | Forward adjusted returns are available where adjustment factors and forward paths exist. |
| `livermore_stock_candidate_universe_history` | exists, populated | 1,192 rows; 231 dates from `2024-09-24` to `2026-06-15`; `return_1d_adj`: 1,127; `return_5d_adj`: 999; `return_10d_adj`: 1,022; `return_20d_adj`: 931 | Universe history exists and has adjusted-return coverage. |
| `choice_stock_daily_observation` | exists, populated | 3,116,524 rows; 5,589 symbols; dates from `2024-01-02` to `2026-06-26` | Daily stock bars are available for path-mode loading. |
| `livermore_position_snapshot` | exists, sparse | 6 rows; 6 snapshot dates from `2026-05-13` to `2026-06-22` | Enough for plumbing tests and blocked/partial diagnostics; too sparse for strong overheat conclusions. |

Formula-version observations:

- `livermore_candidate_history.formula_version`: `fv_livermore_candidate_forward_close_unadjusted_v1` for 5,532 rows.
- `livermore_candidate_execution_history.formula_version`: `fv_livermore_candidate_execution_dual_adjust_v2` with `price_adjustment_mode=adj_factor_ratio` for 5,532 rows.

## Gate Exposure Sources

| Source | Status | Coverage | Task 1 use |
| --- | --- | --- | --- |
| `fact_livermore_gate_supplement_daily` | exists, populated | 752 rows from `2023-05-15` to `2026-06-22`; `breadth_5d` and `limit_up_quality_ok` non-null for all rows | Can support replay of `evaluate_market_gate` with broad-index observations. |
| `fact_choice_macro_daily` broad index source | exists, populated | 3,741 rows from `2015-06-26` to `2026-06-26`; includes `series_id`, `trade_date`, `value_numeric`, `quality_flag` | Can provide `CA.CSI300` history for gate replay if series rows are present. |
| `livermore_candidate_history.signal_evidence_json` | exists, no exposure payload found | 0 rows with `$.market_gate.exposure`; 0 rows with `$.market_gate_exposure` | Not usable as persisted exposure source in the current local DB. |
| `livermore_monitor_append` | missing table | n/a | Not available locally as persisted exposure source. |
| `livermore_gate_supplement` / `livermore_gate_history` | missing tables | n/a | Not available locally as persisted exposure source. |

Task 1 should therefore default to `per_date_actual` via replay, with `source="replayed"` for dates covered by benchmark history and supplement inputs, and `source="missing"` where replay cannot be produced.

## Macro Composite History

- Existing macro-like tables: `fact_choice_macro_daily`, `phase1_macro_vendor_catalog`, `std_external_macro_daily`, `vw_external_legacy_choice_macro`, `vw_external_macro_daily`.
- No table matching the batch-2 macro-composite candidates was found: `livermore_macro_context_history`, `macro_composite_history`, `fact_macro_composite_daily`, or `macro_environment_history`.
- Policy macro multipliers exist in code through `POLICY.macro_multipliers`, but historical macro status is not landed locally.

Conclusion: Task 7 should produce a blocked report unless an alternate macro-status history source is supplied.

## Batch-One Regression Baseline

| Check | Result |
| --- | --- |
| `tests/test_market_data_livermore_candidate_history.py::test_livermore_macro_context_wrapper_uses_service_normalizer` | `1 passed` |
| Focused stock-strategy suite: `tests/test_portfolio_backtest.py backend/tests/core_finance/test_strategy_policy.py tests/test_adjusted_returns_backfill.py tests/test_matched_baseline.py tests/test_walk_forward_threshold_scan.py` | `44 passed` |
| Batch-2 focused diagnostics/regression suite: `tests/test_portfolio_backtest.py backend/tests/core_finance/test_strategy_policy.py tests/test_entry_premium_diagnostic.py tests/test_vol_target_overlay.py tests/test_macro_multiplier_diagnostic.py tests/test_overheat_holdings_diagnostic.py tests/test_stock_strategy_health_diagnostic.py tests/test_gate_state_flip_diagnostic.py tests/test_gate_exposure_series.py tests/test_portfolio_paths.py` | `79 passed` |

The initial focused suite pass count for this batch baseline is `44 passed`; the later batch-2 diagnostics/regression suite pass count is `79 passed`.

## Task 0 Conclusion

- Branch is active.
- Execution-history facts and adjustment factors are populated locally; adjusted returns are available where adjustment factors and forward paths exist.
- Gate exposure has a viable replay path through `fact_choice_macro_daily` plus `fact_livermore_gate_supplement_daily`; persisted candidate evidence does not currently carry exposure.
- Macro composite history is not available locally.
- The batch-one macro wrapper regression passes.
- The focused stock-strategy suite baseline is `44 passed`.
