# Yield-Curve Isolation Manifest

## Purpose

This document isolates the currently authorized `yield-curve / curve-effects` stream from the broader dirty worktree without reverting unrelated changes.

## In-Scope Changed Files

- `backend/app/core_finance/bond_analytics/common.py`
- `backend/app/core_finance/bond_analytics/read_models.py`
- `backend/app/core_finance/pnl_bridge.py`
- `backend/app/repositories/akshare_adapter.py`
- `backend/app/repositories/yield_curve_repo.py`
- `backend/app/schemas/yield_curve.py`
- `backend/app/tasks/yield_curve_materialize.py`
- `backend/app/services/pnl_bridge_service.py`
- `backend/app/services/bond_analytics_service.py`
- `tests/test_akshare_adapter_yield_curve.py`
- `tests/test_yield_curve_repo.py`
- `tests/test_yield_curve_materialize.py`
- `tests/test_pnl_bridge_with_curve.py`
- `tests/test_pnl_bridge_curve_effects.py`
- `tests/test_bond_analytics_curve_effects.py`
- `tests/test_pnl_api_contract.py`
- `tests/test_macro_vendor_preflight.py`
- `tests/test_bond_analytics_service_real_data.py`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md`
- `docs/plans/2026-04-12-cursor-yield-curve-execution-split.md`

## Out-of-Scope Changed Files

- `backend/app/agent/tools/analysis_view_tool.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes/agent.py`
- `backend/app/api/routes/balance_analysis.py`
- `docs/acceptance_tests.md`
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/pnl/PnlBridgePage.tsx`
- `frontend/src/features/pnl/PnlPage.tsx`
- `frontend/src/main.tsx`
- `frontend/src/router/routes.tsx`
- `frontend/src/test/setup.ts`
- `tests/test_agent_enabled_path_smoke.py`
- `tests/test_agent_intent_routing.py`
- `tests/test_balance_analysis_boundary_guards.py`
- `tests/test_balance_analysis_materialize_flow.py`
- `tests/test_snapshot_materialize_flow.py`
- `tests/test_worker_bootstrap.py`
- `backend/app/api/routes/cube_query.py`
- `backend/app/repositories/cube_query_repo.py`
- `backend/app/schemas/cube_query.py`
- `backend/app/services/cube_query_service.py`
- `docs/plans/2026-04-12-balance-analysis-gap-closure.md`
- `frontend/src/features/bond-analytics/utils/echartsRiskCharts.ts`
- `frontend/src/features/platform-config/`
- `frontend/src/features/team-performance/`
- `frontend/src/lib/agGridSetup.ts`
- `pytest-last.txt`
- `tests/test_cube_query_api.py`
- `tests/test_cube_query_service.py`
- `tmp-governance-review/`

## Verification

Verified in-scope subset:

```text
pytest tests/test_akshare_adapter_yield_curve.py tests/test_yield_curve_materialize.py tests/test_yield_curve_repo.py tests/test_pnl_bridge_with_curve.py tests/test_pnl_bridge_curve_effects.py tests/test_bond_analytics_curve_effects.py tests/test_pnl_api_contract.py::test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable tests/test_pnl_api_contract.py::test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows tests/test_pnl_api_contract.py::test_pnl_bridge_result_meta_merges_report_date_specific_balance_build_lineage -q
```

Result: `21 passed`

Patch artifact:
- `.omx/artifacts/yield-curve-authorized-stream.patch`

Patch validation:

```text
git am --signoff F:/MOSS-V3/.omx/artifacts/yield-curve-authorized-stream.patch
```

Result: patch applies cleanly in a temporary detached `HEAD` worktree.

## Notes

- This manifest is non-destructive. It does not revert, stage, stash, or rewrite unrelated work.
- The next safe operation is to use the in-scope file list as the only candidate set for staging/patch export/review.
