# Yield-Curve / Curve-Effects Execution Split

## Current status

Codex-owned slice already completed in this worktree:

- [backend/app/tasks/yield_curve_materialize.py](/F:/MOSS-V3/backend/app/tasks/yield_curve_materialize.py)
- [tests/test_akshare_adapter_yield_curve.py](/F:/MOSS-V3/tests/test_akshare_adapter_yield_curve.py)
- [tests/test_yield_curve_materialize.py](/F:/MOSS-V3/tests/test_yield_curve_materialize.py)
- [tests/test_pnl_bridge_curve_effects.py](/F:/MOSS-V3/tests/test_pnl_bridge_curve_effects.py)

Local verification already run:

- `pytest tests/test_akshare_adapter_yield_curve.py tests/test_yield_curve_materialize.py tests/test_pnl_bridge_curve_effects.py -q`
- `pytest tests/test_akshare_adapter_yield_curve.py tests/test_yield_curve_materialize.py tests/test_yield_curve_repo.py tests/test_pnl_bridge_curve_effects.py tests/test_bond_analytics_curve_effects.py tests/test_pnl_api_contract.py::test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable tests/test_pnl_api_contract.py::test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows tests/test_pnl_api_contract.py::test_pnl_bridge_result_meta_merges_report_date_specific_balance_build_lineage -q`

## Split

### Codex owns

- `backend/app/tasks/yield_curve_materialize.py`
- `tests/test_yield_curve_materialize.py`
- `tests/test_pnl_bridge_curve_effects.py`
- the current `aaa_credit` fail-closed boundary for this stream

### Cursor owns

- `backend/app/repositories/akshare_adapter.py`
- `backend/app/repositories/yield_curve_repo.py`
- `backend/app/services/pnl_bridge_service.py`
- `backend/app/services/bond_analytics_service.py`
- `tests/test_yield_curve_repo.py`
- `tests/test_bond_analytics_curve_effects.py`
- if needed, targeted additions in `tests/test_pnl_api_contract.py`

Cursor should not revert or rewrite the Codex-owned files above.

## Cursor Prompt

```text
You are working in F:\MOSS-V3 on the authorized `yield-curve / curve-effects` stream only.

Read first:
- AGENTS.md
- docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md
- docs/plans/2026-04-12-cursor-yield-curve-execution-split.md

Hard constraints:
- Stay inside the 2026-04-12 scoped override only.
- No frontend changes.
- No broad Agent MVP work.
- No new effect scope beyond:
  - `roll_down` and `treasury_curve` in PnL Bridge
  - the already-landed bond-analytics `rate_effect`
- Do not touch or revert these Codex-owned files:
  - backend/app/tasks/yield_curve_materialize.py
  - tests/test_yield_curve_materialize.py
  - tests/test_pnl_bridge_curve_effects.py
  - tests/test_akshare_adapter_yield_curve.py

Your write scope:
- backend/app/repositories/akshare_adapter.py
- backend/app/repositories/yield_curve_repo.py
- backend/app/services/pnl_bridge_service.py
- backend/app/services/bond_analytics_service.py
- tests/test_yield_curve_repo.py
- tests/test_bond_analytics_curve_effects.py
- optionally targeted additions in tests/test_pnl_api_contract.py if absolutely needed

Goal:
Close out substrate/repo/service regression hardening for yield curves without changing API signatures or widening scope.

Required outcomes:
1. Make sure `YieldCurveRepository.fetch_curve_snapshot()` remains the governed snapshot-lineage surface and is explicitly validated for:
   - curve
   - vendor_name
   - vendor_version
   - source_version
   - rule_version
2. Harden `pnl_bridge_service.py` and `bond_analytics_service.py` so latest-fallback behavior is explicit, warning-bearing, and lineage-preserving.
3. Keep implementation precise: both services already consume curve snapshots. This is regression-hardening, not first-time wiring.
4. Do not introduce `aaa_credit`, `credit_spread`, or `fx_translation` into this round.

Test matrix you must satisfy:
- repo exact-date read
- repo latest-date read
- repo date-list read
- repo snapshot-lineage read
- explicit latest-fallback warnings in pnl_bridge_service
- explicit latest-fallback warnings in bond_analytics_service
- result_meta lineage merge for used curve snapshots in both services

Verification commands:
- pytest tests/test_yield_curve_repo.py tests/test_bond_analytics_curve_effects.py -q
- pytest tests/test_pnl_api_contract.py::test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable tests/test_pnl_api_contract.py::test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows tests/test_pnl_api_contract.py::test_pnl_bridge_result_meta_merges_report_date_specific_balance_build_lineage -q

Output back to me:
- changed files
- exact behavior changed
- tests run and results
- any residual risk or blocked edge case
```

## Recommended sequence

1. Cursor first on repo/service hardening inside its write scope.
2. Codex then re-runs the combined targeted test bundle and resolves any cross-file fallout.
