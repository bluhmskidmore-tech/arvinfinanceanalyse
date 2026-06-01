# ZQTZ / TYW Formal Balance Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the formal `ZQTZ / TYW` asset-liability analysis pipeline from standardized snapshots into governed formal facts, then expose a read model and UI surface without violating the repo's finance-boundary rules.

**Architecture:** Reuse the repo's existing pattern: `snapshot tables -> core_finance derivation -> task/worker materialization -> repository/service/API envelopes -> workbench consumer`. Do not let `preview` tables, frontend code, or API handlers perform formal calculations. Keep `Scenario` and `Formal` isolated and attach `result_meta` to every outward-facing result.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, Dramatiq, React, TypeScript, TanStack Query, Ant Design

---

## Requirements Summary

- Current `zqtz / tyw` state is only `preview + standardized snapshot`.
- `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot` are canonical standardized storage, not formal facts.
- `formal compute`, `monthly average`, `FX conversion`, `issuance exclusion`, and `H/A/T derivation` are still the missing business-critical steps.
- Formal calculations must live only under `backend/app/core_finance/`.
- API and frontend may orchestrate or display only; they must not compute formal financial truth.

## Acceptance Criteria

1. `ZQTZ / TYW` formal balance facts can be materialized from `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot` without reading `phase1_*preview*` tables.
2. Formal derivation covers at least these rule families with explicit tests:
   - H/A/T -> AC / FVOCI / FVTPL
   - FX midpoint conversion and non-business-day carry-forward semantics
   - issuance-like exclusion
   - month-average basis rules
3. Materialized formal facts carry lineage fields and outward `result_meta`.
4. A governed API can return dates, detail rows, summary rows, and refresh status for the balance-analysis surface.
5. The first UI consumer reads only the governed API, not snapshot tables directly.

## Implementation Order

Do the work in this order:

1. Contracts and rule truth
2. `core_finance` derivation
3. task/worker materialization
4. read repository + service + API
5. workbench UI

Do not start step 5 until steps 1-4 are green.

### Task 1: Define the Formal Balance Contracts

**Files:**
- Modify: `docs/data_contracts.md`
- Modify: `docs/calc_rules.md`
- Modify: `docs/acceptance_tests.md`
- Modify: `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- Create: `backend/app/schemas/balance_analysis.py`

**Plan:**
1. Add the new formal fact/table contracts for `zqtz / tyw` balance analysis to `docs/data_contracts.md`.
2. Explicitly document which fields are standardized inputs and which are `formal-only derived later`.
3. Extend `docs/calc_rules.md` with the exact formal balance semantics for:
   - H/A/T derivation
   - FX conversion
   - issuance-like exclusion
   - month-average basis
   - result_meta requirements
4. Add file-level acceptance assertions in `docs/acceptance_tests.md`.
5. Define outward API payload schemas in `backend/app/schemas/balance_analysis.py`.

**Verification:**
- `pytest tests/test_result_meta_required.py -q`
- Add and run new contract tests:
  - `pytest tests/test_balance_analysis_contracts.py -q`

### Task 2: Build the Core Formal Derivation Layer

**Files:**
- Create: `backend/app/core_finance/balance_analysis.py`
- Modify: `backend/app/core_finance/__init__.py`
- Create: `tests/test_balance_analysis_core.py`

**Plan:**
1. Define canonical input dataclasses that read only from `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot`.
2. Add pure functions for:
   - H/A/T normalization
   - accounting basis derivation
   - FX midpoint application
   - issuance-like exclusion
   - average-balance / report-basis projection
3. Add pure formal output dataclasses for asset rows, liability rows, and totals.
4. Build one pure read-model assembly function that converts formal fact rows into a balance-analysis payload shape.
5. Keep this module side-effect free.

**Verification:**
- `pytest tests/test_balance_analysis_core.py -q`
- Add edge-case coverage for weekends/holidays, missing FX, and excluded issuance-like rows.

### Task 3: Materialize the Formal Facts Through Tasks Only

**Files:**
- Create: `backend/app/repositories/balance_analysis_repo.py`
- Create: `backend/app/tasks/balance_analysis_materialize.py`
- Modify: `backend/app/repositories/governance_repo.py`
- Create: `tests/test_balance_analysis_materialize_flow.py`
- Create: `tests/test_balance_analysis_no_preview_dependency.py`

**Plan:**
1. Add DuckDB DDL for the new formal fact tables and read-model cache tables.
2. Add repository helpers that:
   - read snapshot inputs
   - write formal fact rows
   - write summarized read-model rows
3. Add a task/worker-only materializer, following the same pattern as `pnl_materialize.py` and `product_category_pnl.py`.
4. Record governed lineage and build-run events in governance streams.
5. Explicitly fail if required formal inputs are missing, especially FX or snapshot prerequisites.

**Verification:**
- `pytest tests/test_balance_analysis_materialize_flow.py -q`
- `pytest tests/test_balance_analysis_no_preview_dependency.py -q`

### Task 4: Expose a Governed API Surface

**Files:**
- Create: `backend/app/services/balance_analysis_service.py`
- Create: `backend/app/api/routes/balance_analysis.py`
- Modify: `backend/app/api/__init__.py`
- Create: `tests/test_balance_analysis_api.py`
- Create: `tests/test_balance_analysis_service.py`

**Plan:**
1. Add service envelopes for:
   - available dates
   - detail payload
   - summary payload
   - refresh trigger
   - refresh status
2. Attach `result_meta` to every UI-facing response.
3. Keep API handlers limited to validation, service calls, and HTTP error mapping.
4. Block direct snapshot exposure from this route; serve only formal/read-model outputs.

**Verification:**
- `pytest tests/test_balance_analysis_service.py -q`
- `pytest tests/test_balance_analysis_api.py -q`
- `pytest tests/test_result_meta_on_all_ui_endpoints.py -q`

### Task 5: Add the Workbench Consumer

**Files:**
- Create: `frontend/src/features/balance-analysis/`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/router/routes.tsx`
- Modify: `frontend/src/layouts/WorkbenchShell.tsx`
- Create: `frontend/src/test/BalanceAnalysisPage.test.tsx`
- Create: `frontend/src/test/BalanceAnalysisApi.test.ts`

**Plan:**
1. Add typed client methods for the new balance-analysis endpoints.
2. Build a dedicated page that shows:
   - report-date selector
   - asset / liability totals
   - row drilldown
   - refresh status
   - result-meta visibility
3. Keep the page read-only in the first version.
4. Do not compute any formal fields in React.

**Verification:**
- `pnpm test -- --runInBand frontend/src/test/BalanceAnalysisApi.test.ts frontend/src/test/BalanceAnalysisPage.test.tsx`
- `pnpm typecheck`
- `pnpm lint`

### Task 6: Full Regression and Boundary Audit

**Files:**
- Modify: `tests/test_no_finance_logic_in_api.py`
- Modify: `tests/test_no_finance_logic_in_frontend.py`
- Create: `tests/test_balance_analysis_boundary_guards.py`

**Plan:**
1. Extend boundary tests so new balance-analysis routes cannot drift finance logic into API/frontend.
2. Add guard tests that reject preview-table dependency for formal paths.
3. Add regression tests to ensure formal and scenario semantics stay isolated.

**Verification:**
- `pytest tests/test_no_finance_logic_in_api.py -q`
- `pytest tests/test_no_finance_logic_in_frontend.py -q`
- `pytest tests/test_balance_analysis_boundary_guards.py -q`

## Risks and Mitigations

- **Risk:** Snapshot fields are still insufficient for formal derivation.
  - **Mitigation:** Finish Task 1 before any task code; mark missing inputs as explicit blockers, not silent defaults.
- **Risk:** Developers shortcut from snapshot directly to UI.
  - **Mitigation:** Add explicit no-preview/no-direct-snapshot-consumer tests in Tasks 3 and 6.
- **Risk:** FX and H/A/T rules get reimplemented in service or frontend layers.
  - **Mitigation:** Put all derivation in `backend/app/core_finance/balance_analysis.py` and add boundary tests.
- **Risk:** Workbench ships before formal facts are stable.
  - **Mitigation:** Keep Task 5 behind green gates from Tasks 1-4.

## Verification Steps

Run in this order:

1. `pytest tests/test_balance_analysis_contracts.py -q`
2. `pytest tests/test_balance_analysis_core.py -q`
3. `pytest tests/test_balance_analysis_materialize_flow.py -q`
4. `pytest tests/test_balance_analysis_service.py -q`
5. `pytest tests/test_balance_analysis_api.py -q`
6. `pytest tests/test_balance_analysis_boundary_guards.py -q`
7. `pytest tests/test_result_meta_required.py tests/test_result_meta_on_all_ui_endpoints.py -q`
8. `pnpm test -- --runInBand frontend/src/test/BalanceAnalysisApi.test.ts frontend/src/test/BalanceAnalysisPage.test.tsx`
9. `pnpm typecheck`
10. `pnpm lint`

## Recommendation

The first execution slice should stop at **Task 4**. That delivers the highest-value backend truth surface without prematurely spending time on UI. Once Task 4 is green, the UI work becomes a thin consumer instead of a second design exercise.
