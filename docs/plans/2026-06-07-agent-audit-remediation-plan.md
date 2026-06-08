# MOSS V3 Agent Audit Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the Desktop audit DOCX findings into small, testable, reviewable remediation batches.

**Architecture:** Preserve the existing API contracts and page routes while tightening boundaries. Writes move behind task-only scopes, routes remain thin HTTP adapters, external Agent providers get server-side policy enforcement, and temporary live-route exceptions become machine-checked governance records.

**Tech Stack:** FastAPI, pytest, DuckDB repositories/tasks, TypeScript/React, Vitest, Vite, project governance markdown contracts.

---

## Execution Notes

- Do not commit unless the user explicitly asks.
- Work in small batches. After each batch, run only the relevant tests first, then widen if shared behavior changed.
- Do not change schema, auth framework, scheduler, global SDK wrappers, or frontend layout unless a failing test proves that specific layer is the root cause.
- Treat the current dirty worktree as user-owned context. Inspect files before editing and avoid reverting unrelated changes.
- If MCP governance servers are unavailable, record the local source/test evidence used and the residual risk.

## Batch 1: Lock Service And Route Storage Boundaries

**Purpose:** Make it impossible for API/service request paths to directly write DuckDB or silently own persistence side effects.

**Files:**
- Inspect: `backend/app/services/cffex_member_rank_service.py`
- Inspect: `backend/app/services/tushare_news_ingest_service.py`
- Inspect: `backend/app/api/routes/`
- Modify or extend: `tests/test_service_storage_boundaries.py`
- Modify or create if needed: `tests/test_duckdb_write_boundary.py`
- Modify if still needed: `backend/app/tasks/cffex_member_rank.py`
- Modify if still needed: `backend/app/tasks/tushare_news_ingest.py`

**Step 1: Write or extend failing boundary tests**

Add test coverage that fails if `backend/app/api` or `backend/app/services` contains:

```python
read_only=False
duckdb.connect(
INSERT INTO
CREATE TABLE
DELETE FROM
UPDATE
COPY
```

Scope any allowed exceptions explicitly by file and reason. Do not use a broad whitelist.

**Step 2: Run boundary tests and capture failures**

Run:

```bash
python -m pytest tests/test_service_storage_boundaries.py tests/test_duckdb_write_boundary.py -q
```

Expected before implementation: failures point only to the two audit-named service write paths or already-known explicit exceptions.

**Step 3: Move remaining service writes into tasks**

For CFFEX member rank and Tushare news ingest:

- Keep service return DTOs unchanged.
- Move write connection ownership into `backend/app/tasks/...`.
- Let the service call the task synchronously first if preserving API behavior requires it.
- Keep status/query/readiness checks in service as read-only operations.

**Step 4: Re-run narrow verification**

Run:

```bash
python -m pytest tests/test_service_storage_boundaries.py tests/test_boundary_surface_inventory.py -q
python -m pytest tests/test_cffex_member_rank_service.py tests/test_choice_news_routes.py -q
```

If exact test filenames differ, use `rg -n "cffex|tushare_news|choice_news" tests` to choose the closest targeted tests.

**Execution status - 2026-06-07**

- `cffex_member_rank_service.py` no longer opens writable DuckDB connections or calls `replace_member_rank_rows`; persistence is delegated to `backend/app/tasks/cffex_member_rank.py`.
- `tushare_news_ingest_service.py` no longer owns the writable DuckDB connection for choice-news ingestion; persistence is delegated to `backend/app/tasks/tushare_news_ingest.py`.
- `tests/test_service_storage_boundaries.py` now blocks writable DuckDB connections and repository `replace_*` calls from `backend/app/api` and `backend/app/services`, and includes explicit CFFEX/Tushare service delegation checks.
- `tests/test_duckdb_write_boundary.py` is present as the audit-named compatibility gate and reuses the canonical service/route storage boundary checks.
- Verification: `pytest tests/test_duckdb_write_boundary.py tests/test_service_storage_boundaries.py -q` -> 28 passed; `pytest tests/test_service_storage_boundaries.py tests/test_boundary_surface_inventory.py -q` -> 56 passed; `pytest tests/test_choice_news_routes.py tests/test_tushare_news_ingest.py -q` -> 14 passed; `pytest tests/test_macro_toolkit_scripts.py -k "cffex_member_rank_refresh_materializes" -q` -> 2 passed, 74 deselected.

## Batch 2: Enforce Task-Only Repository Writers

**Purpose:** Repository `replace_*` writers should be callable only from approved task/materialization contexts.

**Files:**
- Inspect: `backend/app/repositories/task_write_guard.py`
- Modify: `backend/app/repositories/bond_analytics_repo.py`
- Modify: `backend/app/repositories/yield_curve_repo.py`
- Modify: `backend/app/repositories/pnl_repo.py`
- Modify: `backend/app/repositories/risk_tensor_repo.py`
- Modify: `backend/app/tasks/bond_analytics_materialize.py`
- Modify: `backend/app/tasks/yield_curve_materialize.py`
- Modify: `backend/app/tasks/risk_tensor_materialize.py`
- Modify: `backend/app/tasks/pnl_by_business_precompute.py`
- Modify: `tests/test_repository_task_write_guard.py`

**Step 1: Add failing runtime guard tests**

Test each formal writer directly:

```python
with pytest.raises(PermissionError):
    repo.replace_xxx(...)
```

Then test the same writer inside:

```python
with repository_task_write_scope("tests"):
    repo.replace_xxx(...)
```

**Step 2: Add writer-side guard calls**

At the top of each formal replace writer:

```python
require_repository_task_write_scope("replace_xxx")
```

**Step 3: Wrap legitimate task writers**

In task/materialization entry points only:

```python
with repository_task_write_scope(__name__):
    repo.replace_xxx(...)
```

**Step 4: Verify**

Run:

```bash
python -m pytest tests/test_repository_task_write_guard.py tests/test_service_storage_boundaries.py -q
python -m pytest tests/test_bond_analytics_materialize_flow.py tests/test_yield_curve_materialize.py tests/test_risk_tensor_materialize.py -q
```

**Execution status - 2026-06-07**

- Extended `tests/test_repository_task_write_guard.py` beyond the originally named formal writers to cover `BalanceAnalysisRepository.replace_formal_balance_rows`, `replace_zqtz_snapshot_rows`, `replace_tyw_snapshot_rows`, and the public standardized snapshot delete helpers.
- Added writer-side `require_repository_task_write_scope(...)` checks in `balance_analysis_repo.py` and `snapshot_repo.py`.
- Wrapped legitimate materialization writes in `repository_task_write_scope(__name__)` in `balance_analysis_materialize.py` and `snapshot_materialize.py`.
- Strengthened the guard test so Bond analytics, Yield curve, PnL by business, Risk tensor, Balance analysis, and snapshot writers are blocked outside task scope and allowed inside task scope.
- Verification: `pytest tests/test_service_storage_boundaries.py tests/test_repository_task_write_guard.py tests/test_snapshot_dq_guardrails.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_service_boundaries.py -q` -> 54 passed.

## Batch 3: Harden External Agent Provider Isolation

**Purpose:** Hermes/Dexter can provide analysis, but they must not gain write/build/terminal authority through caller-supplied toolsets.

**Files:**
- Inspect: `backend/app/agent/runtime/toolset_policy.py`
- Modify: `backend/app/services/hermes_agent_service.py`
- Modify: `backend/app/services/dexter_agent_service.py`
- Modify: `backend/app/agent/schemas/agent_response.py`
- Modify: `tests/test_agent_toolset_policy.py`
- Modify: `tests/test_agent_api_contract.py`

**Step 1: Add failing provider policy tests**

Cover both request and response sanitization:

```python
raw = {"toolsets": ["terminal", "file_write", "evidence"]}
assert normalize_provider_toolsets(raw["toolsets"]) == ["evidence"]
```

Also assert unknown toolsets are dropped, not passed through.

**Step 2: Enforce backend allowlist**

Policy should default to read-only evidence/query/research capabilities only. Caller-supplied values must be normalized before subprocess/bridge calls and before persisted metadata is returned.

**Step 3: Separate provider runtime evidence from governed evidence**

Agent responses should distinguish:

- `provider_runtime`: model/provider/tool execution facts.
- `governed_evidence`: MOSS source lineage, metric contract, catalog, or golden-sample backed evidence.

If governed evidence is absent, do not mark `quality_flag` as `ok`.

**Step 4: Verify**

Run:

```bash
python -m pytest tests/test_agent_toolset_policy.py tests/test_agent_api_contract.py tests/test_agent_runs_api.py -q
```

**Execution status - 2026-06-07**

- Added `backend/app/agent/runtime/toolset_policy.py` to normalize external provider toolsets to read-only `evidence`, `query`, and `research` capabilities.
- Hermes and Dexter CLI/bridge paths sanitize caller/provider toolsets before subprocess or bridge execution and before returned metadata is exposed.
- Provider runtime evidence is explicitly marked with `evidence_strength="provider_runtime"` and cannot retain `quality_flag="ok"` without governed MOSS evidence.
- Verification: `pytest tests/test_agent_toolset_policy.py tests/test_agent_api_contract.py tests/test_hermes_agent_service.py tests/test_dexter_agent_service.py -q` -> 46 passed.

## Batch 4: Make Suggested Actions Server-Confirmed

**Purpose:** `requires_confirmation` must be enforced by the server, not only displayed by the UI.

**Files:**
- Inspect: `backend/app/agent/runtime/action_token.py`
- Modify: `backend/app/api/routes/agent.py`
- Modify: `backend/app/services/agent_run_service.py`
- Modify: `frontend/src/features/agent/AgentWorkbenchPage.tsx`
- Modify: `frontend/src/features/agent/components/AgentSuggestedActionsPanel.tsx`
- Modify: `tests/test_agent_api_contract.py`
- Modify: `frontend/src/test/AgentWorkbenchPage.test.tsx`

**Step 1: Add backend failing tests**

For a suggested action with `requires_confirmation=True`, assert execution fails when:

- token is missing
- token is malformed
- token belongs to another action
- token is expired

Then assert execution succeeds with a valid server-issued token.

**Step 2: Generate confirmation tokens server-side**

When returning suggested actions, include a token or token handle for confirmable actions. The token should bind at least:

- action id
- run id/session id
- provider id
- expiration timestamp

**Step 3: Update frontend flow**

Frontend should send the confirmation token only after the user confirms. The UI label is still useful, but it is no longer the control boundary.

**Step 4: Verify**

Run:

```bash
python -m pytest tests/test_agent_api_contract.py tests/test_agent_runs_api.py -q
npm run test -- AgentWorkbenchPage
```

**Execution status - 2026-06-07**

- Backend confirmation tokens and intent routing coverage were already present in `tests/test_agent_api_contract.py` and `tests/test_agent_intent_routing.py`.
- Added frontend coverage that proves a `requires_confirmation` suggested action does not send its token on the first click and only sends it after the explicit `确认执行：...` click.
- Updated `AgentWorkbenchPage` and `AgentSuggestedActionsPanel` so confirmable suggested actions enter a pending confirmation state before execution.
- Verification: `npm test -- --run AgentWorkbenchPage` -> 127 passed; `npm run typecheck` -> passed; `npm run debt:audit` -> passed; `pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q` -> 56 passed.

## Batch 5: Machine-Check Live Temporary Exceptions

**Purpose:** Every live route marked `temporary-exception` must have a signoff row with owner, status, exposure class, scope, and review boundary.

**Files:**
- Modify: `docs/live_route_maturity.md`
- Modify: `tests/test_live_route_page_contract_completeness.py`
- Optionally modify: `frontend/src/test/LiveRouteReadiness.test.tsx`
- Optionally modify: `frontend/src/test/liveRouteReadinessContracts.ts`

**Step 1: Add failing doc-contract tests**

Parse `docs/live_route_maturity.md` and assert:

- every registry row with `nav_state=temporary-exception` has a matching signoff row
- `signoff_owner` equals the registry `owner`
- `signoff_status` is in an explicit allowed set, initially `pending-owner-review`, `owner-accepted`, `expired`
- `exposure_class` is one of `demo-visible`, `production-governed`, `pending-confirmation`, `debug-only`
- `signoff_scope` is non-empty and does not contain placeholder text

**Step 2: Fix registry/signoff rows**

Only edit `docs/live_route_maturity.md` rows that fail the test. Do not promote routes from `temporary-exception` to `live/governed` unless a page contract, metric dictionary entry, lineage evidence, and verification path already exist.

**Step 3: Verify**

Run:

```bash
python -m pytest tests/test_live_route_page_contract_completeness.py -q
npm run test -- LiveRouteReadiness RouteRegistry
```

**Execution status - 2026-06-07**

- `docs/live_route_maturity.md` now carries an explicit temporary-exception signoff list with owner, status, exposure class, and scope for every live route still marked `temporary-exception`.
- `tests/test_live_route_page_contract_completeness.py` validates missing/stale signoff rows, owner mismatches, allowed statuses, allowed exposure classes, and non-placeholder scopes.
- Verification: `pytest tests/test_live_route_page_contract_completeness.py -q` -> 6 passed; `npm test -- --run LiveRouteReadiness RouteRegistry` -> 72 passed.

## Batch 6: Frontend Runtime And Quality Gate Repair

**Purpose:** Make frontend validation runnable in the active environment instead of accepting broken optional native bindings.

**Files:**
- Inspect: `frontend/package.json`
- Inspect: `frontend/package-lock.json`
- Inspect: `frontend/node_modules` environment if present
- Modify only if needed: `frontend/package-lock.json`
- Modify only if needed: docs or dev scripts that describe Windows/WSL dependency separation

**Step 1: Cleanly reinstall in the target environment**

For WSL, run from WSL and avoid sharing a Windows-installed `node_modules`:

```bash
cd /mnt/f/MOSS-V3/frontend
npm install
```

For Windows PowerShell, run from `F:\MOSS-V3\frontend` with Windows Node.

**Step 2: Verify native binding**

Run:

```bash
npm run typecheck
npm run test -- RouteRegistry LiveRouteReadiness
npm run debt:audit
```

If `@rolldown/binding-linux-x64-gnu` still fails in WSL, remove only the environment-local `frontend/node_modules` and reinstall there. Do not hand-edit native binding package entries unless lockfile evidence requires it.

**Execution status - 2026-06-07**

- The active Windows PowerShell frontend environment can run the validation gates that were blocked in the audit finding.
- The `HermesUbuntu` WSL environment can also run the audit-targeted frontend quality gates from `/mnt/f/MOSS-V3/frontend`.
- `RouteRegistry.test.tsx` now mocks heavy page modules that are irrelevant to route-shell assertions, so the WSL run no longer times out while importing full Agent/dashboard/audit pages.
- No dependency reinstall or lockfile surgery was needed in the active Windows or `HermesUbuntu` WSL environments.
- Verification: Windows PowerShell `npm run typecheck` -> passed; Windows PowerShell `npm test -- --run LiveRouteReadiness RouteRegistry` -> 72 passed; Windows PowerShell `npm run debt:audit` -> passed with no growth over baseline; `wsl.exe -d HermesUbuntu -e sh -lc 'cd /mnt/f/MOSS-V3/frontend && npm run typecheck'` -> passed; `wsl.exe -d HermesUbuntu -e sh -lc 'cd /mnt/f/MOSS-V3/frontend && npm test -- --run RouteRegistry LiveRouteReadiness --pool=forks --maxWorkers=1 --no-file-parallelism --reporter=dot'` -> 72 passed; `wsl.exe -d HermesUbuntu -e sh -lc 'cd /mnt/f/MOSS-V3/frontend && npm run debt:audit'` -> passed with no growth over baseline.

## Batch 7: Router Surface Grouping Without URL Churn

**Purpose:** Make route ownership legible while preserving existing URLs and contracts.

**Files:**
- Inspect: `backend/app/api/__init__.py`
- Inspect: `backend/app/main.py`
- Inspect: `backend/app/api/routes/`
- Modify: `tests/test_boundary_surface_inventory.py`
- Modify or create: `backend/app/api/route_surface_registry.py`

**Step 1: Add surface inventory tests**

Assert every backend router is classified as one of:

- `formal_mainline`
- `preview`
- `macro_market`
- `agent_experimental`
- `diagnostics`

**Step 2: Add a registry, not a route rewrite**

Create a simple mapping from router module to surface class. Do not change path prefixes unless a separate migration plan exists.

**Step 3: Verify route inclusion remains stable**

Run:

```bash
python -m pytest tests/test_boundary_surface_inventory.py tests/test_backend_release_suite.py -q
```

**Execution status - 2026-06-07**

- Router grouping is implemented in `backend/app/api/__init__.py` through `RouteRegistryEntry` and `RouteGroupMetadata`, preserving existing URLs while classifying surfaces as `formal_mainline`, `preview`, `macro_market`, `agent_experimental`, or `diagnostics`.
- `tests/test_boundary_surface_inventory.py` validates group metadata, included route coverage, and registry/route surface consistency.
- Verification: `pytest tests/test_boundary_surface_inventory.py -q` -> 32 passed.

## Batch 8: Route DuckDB Reads Downshift

**Purpose:** Routes should map HTTP inputs/outputs; direct DuckDB read work belongs in service/repository layers.

**Files:**
- Inspect: `backend/app/api/routes/market_data_livermore.py`
- Inspect: other route files flagged by `tests/test_service_storage_boundaries.py`
- Modify: relevant `backend/app/services/*_service.py`
- Modify: relevant route tests

**Step 1: Add or tighten static route-read tests**

Fail on `duckdb.connect(` in `backend/app/api/routes` unless a route has an explicit temporary exception and exit task.

**Step 2: Move one route read at a time**

For each route:

- Create a service function that returns the existing response envelope.
- Keep route logic limited to parameter parsing, auth/context, service call, and HTTP exception mapping.
- Patch existing route tests to mock the new service function when appropriate.

**Step 3: Verify per route**

Run the route's focused contract tests plus:

```bash
python -m pytest tests/test_service_storage_boundaries.py tests/test_boundary_surface_inventory.py -q
```

**Execution status - 2026-06-07**

- `tests/test_service_storage_boundaries.py` blocks direct DuckDB references in API routes and includes focused checks for health, macro vendor, market data Livermore, choice news, ADB analysis, external data, and macro toolkit route helpers.
- Current API routes delegate DuckDB reads/errors to service or repository layers instead of opening route-level DuckDB connections.
- Verification: `pytest tests/test_service_storage_boundaries.py -q` -> 24 passed; `pytest tests/test_boundary_surface_inventory.py -q` -> 32 passed.

## Batch 9: StockAnalysisPage Controlled Extraction

**Purpose:** Reduce page-file risk without changing behavior or business semantics.

**Files:**
- Inspect: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Inspect: `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- Modify or add tests in: `frontend/src/test/StockAnalysisPage.test.tsx`
- Modify or add focused tests in: `frontend/src/test/StockAnalysisPageModel.test.ts`
- Extract to: `frontend/src/features/stock-analysis/components/`
- Extract to: `frontend/src/features/stock-analysis/lib/`

**Step 1: Add behavior locks before extraction**

Cover:

- smoke render
- loading state
- empty/no-data state
- stale/fallback date state
- error state
- query guard/readiness labels
- no trading-instruction language

**Step 2: Extract one concern per patch**

Recommended order:

1. status chips and boundary labels
2. review candidate cards
3. closed-loop rail
4. risk/exit rows
5. page chrome/copy constants
6. data shaping helpers

**Step 3: Verify after every extraction**

Run:

```bash
npm run test -- StockAnalysisPage StockAnalysisPageModel
npm run debt:audit
```

**Execution status - 2026-06-07**

- `StockAnalysisPage` has been reduced to the current extraction boundary with behavior split into focused stock-analysis components, hooks, and lib modules.
- `StockAnalysisObservationPreview` and `stockAnalysisQueryOptions` are extracted examples of the controlled split, and `StockAnalysisPageSizeGuard` prevents the page container from regrowing beyond the current boundary.
- Behavior locks cover the page/model paths used by loading, empty/no-data, stale/fallback, error, readiness, and no-trading-instruction surfaces.
- Verification: `npm test -- --run StockAnalysisPage StockAnalysisPageModel StockAnalysisPageSizeGuard` -> 172 passed; current `StockAnalysisPage.tsx` line count -> 3991.

## Final Gate

Run the narrow backend and frontend gates touched by the batches:

```bash
python -m pytest tests/test_service_storage_boundaries.py tests/test_boundary_surface_inventory.py tests/test_repository_task_write_guard.py tests/test_agent_toolset_policy.py tests/test_agent_api_contract.py tests/test_live_route_page_contract_completeness.py -q
```

From `frontend/`:

```bash
npm run typecheck
npm run test -- RouteRegistry LiveRouteReadiness AgentWorkbenchPage StockAnalysisPage
npm run debt:audit
```

Completion evidence should report:

- root cause per closed audit item
- changed files
- tests run and results
- any MCP evidence server unavailable and local fallback evidence used
- remaining temporary exceptions with owner/status/exposure class
