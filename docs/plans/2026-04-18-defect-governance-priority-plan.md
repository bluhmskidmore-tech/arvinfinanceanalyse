# Defect Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reconcile live/placeholder semantics and eliminate silent-failure paths before promoting any more consumer-facing surfaces.

**Architecture:** Keep the current governed formal-compute mainline intact and avoid widening scope just to make the UI look complete. First align frontend readiness with actual backend capability, then make backend/service failures observable instead of silently degrading to empty data, and only after that decide whether deferred surfaces should be promoted or kept reserved.

**Tech Stack:** FastAPI, Pydantic v2, React, TypeScript, Vitest, pytest, DuckDB, PostgreSQL governance streams

---

## Read This First

- `F:\MOSS-V3\AGENTS.md`
- `F:\MOSS-V3\prd-moss-agent-analytics-os.md`
- `F:\MOSS-V3\docs\CODEX_HANDOFF.md`
- `F:\MOSS-V3\docs\IMPLEMENTATION_PLAN.md`
- `F:\MOSS-V3\docs\CACHE_SPEC.md`
- `F:\MOSS-V3\docs\acceptance_tests.md`
- `F:\MOSS-V3\.omx\artifacts\claude-defect-classification-20260418-104535.md`

## Governance Assumptions

- This is a **governance-first** plan, not a feature-expansion plan.
- Do **not** implement full KPI CRUD / report generation in this plan unless the user explicitly re-authorizes that rollout.
- Prefer contract-down fixes over capability-up fixes:
  - Example: downgrade `/kpi` readiness to match actual backend behavior instead of rushing unfinished backend endpoints live.
- Formal compute formulas are **not** the target of this plan.

## Priority Checklist

### P0

- Stop claiming `/kpi` is a fully live read/write surface while the backend still returns reserved `503` for most KPI endpoints.
- Stop swallowing KPI/executive failures and turning them into indistinguishable “empty data” states.

### P1

- Stop returning `quality_flag="ok"` when `source_preview` read queries fail at the DuckDB layer.
- Add regression coverage so live vs reserved vs placeholder semantics cannot drift again without tests failing.

### P2

- After governance cleanup, decide whether to:
  - implement the full KPI write/fetch/report chain, or
  - keep KPI as a read-only / deferred surface for the current cutover.
- Keep `liability_analytics`, `cube_query`, and `agent` under explicit reserved/gated control unless a later cutover authorizes them.

## Definition Of Done For This Plan

- `/kpi` is no longer advertised as a fully live read/write surface unless its backend endpoints are actually live.
- KPI/executive failures are observable through logs and/or `result_meta` degradation, not silently converted into healthy empty states.
- `source_preview` backend read failures no longer produce `quality_flag="ok"` envelopes with empty payloads.
- Existing reserved surfaces remain explicitly reserved and continue to fail closed.

### Task 1: Reconcile KPI Rollout Contract With Reality

**Files:**
- Modify: `frontend/src/mocks/navigation.ts`
- Modify: `frontend/src/test/navigation.test.ts`
- Modify: `frontend/src/test/RouteRegistry.test.tsx`
- Modify: `frontend/src/features/kpi-performance/pages/KpiPerformancePage.tsx`
- Modify: `frontend/src/features/kpi-performance/components/MetricManageModal.tsx`
- Modify: `frontend/src/features/kpi-performance/components/BatchPasteModal.tsx`
- Test: `tests/test_kpi_api.py`

**Why this exists:**
- The frontend currently labels `/kpi` as `live` and claims “已接 /api/kpi 读写链路，与 V1 行为对齐”.
- The backend only ships `/api/kpi/owners` and `/api/kpi/values/summary`; the rest of the KPI write/report endpoints are still explicit reserved `503`.

**Step 1: Write the failing tests**

- Change `frontend/src/test/navigation.test.ts` so `/kpi` is no longer expected to be in the live primary navigation unless the backend write chain is live.
- Add or update a page-level test so KPI write/import/fetch/report actions render in a clearly disabled/deferred state when the backend endpoints are reserved.

**Step 2: Run tests to verify they fail**

Run:

```bash
npm --prefix frontend exec vitest run src/test/navigation.test.ts src/test/RouteRegistry.test.tsx
pytest -q tests/test_kpi_api.py
```

Expected:

- Frontend tests fail because `/kpi` is still marked `live`.
- Backend KPI route tests still pass, confirming the current backend truth is “read surfaces live, write/report surfaces reserved”.

**Step 3: Write the minimal implementation**

- In `frontend/src/mocks/navigation.ts`, downgrade KPI readiness from “full live read/write” to the lowest truthful state that matches current backend behavior.
- In the KPI page and its modals, disable or gate unsupported actions instead of letting users hit reserved endpoints blindly.
- Keep the route accessible only if its remaining read-only behavior is still useful; otherwise move it out of primary navigation.

**Step 4: Run tests to verify they pass**

Run:

```bash
npm --prefix frontend exec vitest run src/test/navigation.test.ts src/test/RouteRegistry.test.tsx
pytest -q tests/test_kpi_api.py
```

Expected:

- Frontend no longer claims false-live KPI readiness.
- Backend contract remains explicit and unchanged.

**Step 5: Commit**

Use a Lore-format commit describing why the KPI surface was downgraded or gated.

### Task 2: Make KPI And Executive Failures Observable Instead Of Silent

**Files:**
- Modify: `backend/app/services/kpi_service.py`
- Modify: `backend/app/services/executive_service.py`
- Modify: `backend/app/schemas/executive_dashboard.py` (only if existing payload/result-meta channels are insufficient)
- Test: `tests/test_kpi_service.py`
- Test: `tests/test_executive_service_contract.py`
- Test: `tests/test_executive_dashboard_endpoints.py`

**Why this exists:**
- `resolve_executive_kpi_metrics()` currently returns `[]` on repository/bootstrap/query failures.
- `executive_overview()` currently uses multiple `except ...: pass` branches, which can make broken dependencies look like “normal missing metrics”.

**Step 1: Write the failing tests**

- Add a failing backend test that distinguishes:
  - genuine no-data conditions
  - dependency/query failures
- Add a failing executive overview contract test asserting KPI-side failures degrade result quality explicitly instead of silently disappearing.

**Step 2: Run tests to verify they fail**

Run:

```bash
pytest -q tests/test_kpi_service.py tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py
```

Expected:

- Current implementation fails because it swallows errors and returns empty results without explicit degradation semantics.

**Step 3: Write the minimal implementation**

- In `kpi_service.py`, stop converting infrastructure/query failures into bare `[]`; raise a typed runtime error or return a distinguishable failure signal.
- In `executive_service.py`, catch that signal intentionally and surface it via the existing envelope/result-meta degradation path instead of `pass`.
- Prefer using existing `quality_flag` / `vendor_status` channels before inventing new payload fields.

**Step 4: Run tests to verify they pass**

Run:

```bash
pytest -q tests/test_kpi_service.py tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py
python scripts/backend_release_suite.py
```

Expected:

- KPI/executive degradation is observable.
- Canonical backend gate still passes.

**Step 5: Commit**

Use a Lore-format commit that records why silent KPI/executive degradation was unacceptable.

### Task 3: Stop `source_preview` From Reporting Backend Read Failures As Healthy Empty Results

**Files:**
- Modify: `backend/app/repositories/source_preview_repo_reads.py`
- Modify: `backend/app/services/source_preview_reads.py`
- Modify: `backend/app/api/routes/source_preview.py`
- Test: `tests/test_source_preview_flow.py`
- Test: `tests/test_source_preview_repo_split.py`

**Why this exists:**
- Current DuckDB read failures in `source_preview_repo_reads.py` collapse into empty pages/payloads.
- `source_preview_reads.py` then wraps those results with `quality_flag="ok"`, which misrepresents backend failure as healthy empty analytical output.

**Step 1: Write the failing tests**

- Add failing tests for:
  - DuckDB query error on source preview summary/history/rows/traces
  - service envelope not allowed to emit `quality_flag="ok"` for backend read failure
  - route-level behavior returning a truthful degraded/error response

**Step 2: Run tests to verify they fail**

Run:

```bash
pytest -q tests/test_source_preview_flow.py tests/test_source_preview_repo_split.py
```

Expected:

- Existing behavior fails the new expectations because backend read errors are currently flattened into empty successful responses.

**Step 3: Write the minimal implementation**

- Distinguish “DuckDB file/table genuinely absent” from “DuckDB query execution failed”.
- For execution failures, either:
  - raise a typed backend error and let the route return `503`, or
  - emit an explicitly degraded envelope with non-`ok` `quality_flag`.
- Do not change the successful empty-path semantics for genuinely absent preview data unless tests require it.

**Step 4: Run tests to verify they pass**

Run:

```bash
pytest -q tests/test_source_preview_flow.py tests/test_source_preview_repo_split.py
python scripts/backend_release_suite.py
```

Expected:

- Query failures are no longer misreported as healthy empties.
- Canonical backend gate still passes.

**Step 5: Commit**

Use a Lore-format commit describing why source preview error semantics had to fail truthfully.

## Deferred Decisions (Do Not Auto-Implement In This Plan)

1. **KPI capability decision**
   - Option A: Keep KPI as read-only/deferred for the current cutover.
   - Option B: Implement the missing backend metrics/value/report/fetch chain as a new authorized slice.

2. **Reserved surface promotion decision**
   - `liability_analytics`
   - `cube_query`
   - `agent`

These are explicit rollout decisions, not cleanup chores.

## Recommended Execution Order

1. Task 1 — KPI contract alignment
2. Task 2 — KPI/executive failure observability
3. Task 3 — source preview truthfulness

## Verification Bundle

Run after each task and once at the end:

```bash
pytest -q tests/test_kpi_api.py tests/test_kpi_service.py tests/test_executive_service_contract.py tests/test_source_preview_flow.py tests/test_source_preview_repo_split.py
python scripts/backend_release_suite.py
```

## Deliverable Summary

If this plan is executed correctly, the user-visible result should be:

- no fake-live KPI claims
- no silent KPI/executive empty-state masking
- no false-`ok` source preview envelopes on backend read failure
