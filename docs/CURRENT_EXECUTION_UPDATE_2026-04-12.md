# Current Execution Update (2026-04-12)

This document records the current user-authorized execution boundary for the `yield-curve / curve-effects` workstream.

## Scope

- This is a scoped override, not a repo-wide phase change.
- The repo default boundary remains `Phase 1` outside this named workstream.
- This round is **substrate closeout plus regression-hardening**, not first-time adapter/service wiring.
- Effect scope remains capped to `roll_down` and `treasury_curve` only.

## Active execution plan

### Tasks

1. Close out the existing yield-curve substrate already present in the repo:
   - keep `backend/app/repositories/akshare_adapter.py` framed as existing primary fetch plus Choice fallback
   - keep `backend/app/tasks/yield_curve_materialize.py` framed as existing worker-only materialization into `fact_formal_yield_curve_daily` / `yield_curve_daily`
   - keep `backend/app/services/pnl_bridge_service.py` and `backend/app/services/bond_analytics_service.py` framed as existing consumers that now need regression-hardening

2. Harden governed curve read behavior in `backend/app/repositories/yield_curve_repo.py`:
   - preserve exact-date reads via `fetch_curve()`
   - preserve latest-date reads via `fetch_latest_trade_date()`
   - preserve date inventory via `list_trade_dates()`
   - explicitly validate `fetch_curve_snapshot()` as the snapshot-lineage read surface returning `curve`, `vendor_name`, `vendor_version`, `source_version`, and `rule_version`

3. Lock snapshot-lineage propagation through the two current consumers only:
   - `backend/app/services/pnl_bridge_service.py`: exact-or-latest snapshot resolution, explicit latest-fallback warnings, and lineage merge into `result_meta`
   - `backend/app/services/bond_analytics_service.py`: exact-or-latest snapshot resolution, explicit latest-fallback warnings, and lineage merge into `result_meta`
   - curve lineage merge must remain limited to the snapshots actually used by `roll_down` / `treasury_curve`

4. Regression-harden materialization failure behavior:
   - AkShare success path for `treasury` and `cdb`
   - AkShare failure with Choice fallback success
   - dual-vendor failure with no silent empty writes and no partial-success framing
   - unsupported `curve_type` rejection remains explicit and fails closed

## Acceptance criteria

- The execution update does **not** describe `akshare_adapter` or `bond_analytics_service` as unimplemented, stubbed, or first-time wiring when the repo already contains fetch and consumer wiring.
- The round is described as substrate closeout plus regression-hardening.
- `YieldCurveRepository.fetch_curve_snapshot()` is explicitly called out as the governed snapshot-lineage read surface.
- Snapshot lineage explicitly covers:
  - `curve`
  - `vendor_name`
  - `vendor_version`
  - `source_version`
  - `rule_version`
- The plan explicitly states that snapshot lineage feeds warning behavior and `result_meta` merges in:
  - `backend/app/services/pnl_bridge_service.py`
  - `backend/app/services/bond_analytics_service.py`
- Latest-date fallback is allowed only when the warning is explicit in the service payload; no silent same-day substitution is authorized.
- Effect scope stays capped to `roll_down` and `treasury_curve`; this round does not authorize `credit_spread`, `fx_translation`, `aaa_credit`, or broader curve consumers.

## Test matrix

- AkShare success materialization for `treasury`
- AkShare success materialization for `cdb`
- AkShare failure with Choice fallback success for `treasury`
- AkShare failure with Choice fallback success for `cdb`
- Dual failure surfaces an error and performs no silent empty write to `fact_formal_yield_curve_daily`
- Unsupported `curve_type` is rejected explicitly
- Repository read: exact-date `fetch_curve()`
- Repository read: latest-date `fetch_latest_trade_date()`
- Repository read: date-list `list_trade_dates()`
- Repository read: snapshot-lineage `fetch_curve_snapshot()` returns `curve`, `vendor_name`, `vendor_version`, `source_version`, `rule_version`
- `pnl_bridge_service.py` emits explicit latest-fallback warnings when exact snapshot is missing and latest snapshot is used
- `bond_analytics_service.py` emits explicit latest-fallback warnings when exact snapshot is missing and latest snapshot is used
- `pnl_bridge_service.py` merges used curve snapshot lineage into `result_meta`
- `bond_analytics_service.py` merges used curve snapshot lineage into `result_meta`

## Risks

- Vendor payload drift in AkShare or Choice can break curve-point extraction without changing repository/service code.
- Latest-fallback behavior can hide data freshness problems unless warning assertions remain strict.
- Snapshot-lineage merge logic can drift between `pnl_bridge_service.py` and `bond_analytics_service.py` if hardened in only one place.
- Broadening the scope beyond `roll_down` / `treasury_curve` would create unauthorized Phase-2-style spillover.

## Stop conditions

- Stop after the above substrate closeout and regression-hardening work is planned and bounded.
- Stop if proposed work expands beyond `roll_down` / `treasury_curve`.
- Stop if a change would require API signature changes, frontend work, response-model expansion, or `aaa_credit` enablement.
- Stop if the implementation path starts treating latest fallback as silent substitution rather than explicit warning-bearing evidence.
