# Backend Launch Foundations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the backend substrate gaps that currently block the frontend from running in governed `real` mode without shell demos, V1 compat payloads, or phase-boundary placeholders.

**Architecture:** Keep the existing layered direction `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`. First harden identity, governance authority, and async/task guarantees; then remove demo/compat fallback from the consumer-facing read surfaces; finally complete the still-placeholder formal analytics seams that the frontend already depends on.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.x, DuckDB, PostgreSQL, Redis, Dramatiq, pytest

---

## Read This First

- Current repo-level state lookup now enters through:
  - `F:\\MOSS-V3\\AGENTS.md`
  - `F:\\MOSS-V3\\docs\\DOCUMENT_AUTHORITY.md`
  - `F:\\MOSS-V3\\docs\\CURRENT_EFFECTIVE_ENTRYPOINT.md`
- The references below remain useful as background / planning context, not as the current repo-level entry sequence.

- `F:\MOSS-V3\AGENTS.md`
- `F:\MOSS-V3\prd-moss-agent-analytics-os.md`
- `F:\MOSS-V3\docs\CODEX_HANDOFF.md`
- `F:\MOSS-V3\docs\IMPLEMENTATION_PLAN.md`
- `F:\MOSS-V3\docs\calc_rules.md`
- `F:\MOSS-V3\docs\data_contracts.md`
- `F:\MOSS-V3\docs\CACHE_SPEC.md`
- `F:\MOSS-V3\docs\acceptance_tests.md`
- `F:\MOSS-V3\docs\CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`

## Scope Notes

- This is a **planning artifact only**. It does not by itself authorize code changes outside the current repo boundary.
- The plan is ordered by launch criticality, not by implementation convenience.
- Prefer deletion over addition, reuse existing repositories/services before introducing new abstractions, and keep commits Lore-compliant.
- Every task below assumes: write failing test first, then minimal implementation, then focused regression run, then commit.

## Definition Of Done For The Whole Plan

- Frontend can run in `real` mode for the targeted launch surfaces without shell-demo fallbacks.
- All targeted backend responses return governed envelopes with `result_meta`.
- No targeted route still depends on `auth_stub`, raw V1 payloads, or phase-boundary placeholder behavior.
- Queue/task execution, cache manifest/build-run state, and lineage authority are production-safe for the targeted paths.
- Regression tests cover auth, governance, PnL, executive dashboard, liability analytics, and bond analytics launch surfaces.

### Task 1: Replace Auth Stub With Governed Identity And Scope

**Files:**
- Create: `backend/app/security/auth_context.py`
- Create: `backend/app/repositories/user_scope_repo.py`
- Create: `backend/app/schemas/auth_context.py`
- Modify: `backend/app/security/auth_stub.py`
- Modify: `backend/app/api/routes/balance_analysis.py`
- Modify: `backend/app/api/routes/agent.py`
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/app/models/governance.py`
- Modify: `backend/app/postgres_migrations.py`
- Test: `tests/test_auth_context.py`
- Test: `tests/test_balance_analysis_auth_scope.py`
- Test: `tests/test_agent_api_contract.py`
- Test: `tests/test_agent_audit_log_contract.py`

**Why this exists:**
- `backend/app/security/auth_stub.py` still returns `phase1-dev-user`.
- Approval/status routes in `balance_analysis` already accept a user context, but it is not governed.
- Launch cannot rely on fallback identity for writes, approvals, or audit.

**API / table targets:**
- Preserve header-based identity bootstrap for development, but move it behind a real auth-context abstraction.
- Add governed user-role/scope storage in PostgreSQL.
- Make audit payloads store a real identity source instead of fallback-only semantics.

**Step 1: Write the failing tests**

```python
def test_get_auth_context_requires_real_identity_source_when_headers_present():
    ctx = get_auth_context(x_user_id="u_real", x_user_role="reviewer")
    assert ctx.user_id == "u_real"
    assert ctx.role == "reviewer"
    assert ctx.identity_source == "header"


def test_balance_analysis_decision_status_rejects_user_without_scope():
    response = client.post(
        "/ui/balance-analysis/decision-items/status",
        headers={"X-User-Id": "u_no_scope", "X-User-Role": "viewer"},
        json={...},
    )
    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_auth_context.py tests/test_balance_analysis_auth_scope.py -q
```

Expected:
- FAIL because only `auth_stub.py` exists
- FAIL because no governed scope check blocks the write path

**Step 3: Write the minimal implementation**

- Introduce `auth_context.py` as the canonical dependency used by routes.
- Keep `auth_stub.py` as a thin compatibility shim that imports the new code until all callers are migrated.
- Add a repository for `user_role_scope` lookup instead of scattering role checks in routes.
- Extend governance models/migrations with the minimum persisted scope table needed by launch flows.
- Update `balance_analysis.py` and `agent.py` to depend on the governed auth context layer.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_auth_context.py tests/test_balance_analysis_auth_scope.py tests/test_agent_api_contract.py tests/test_agent_audit_log_contract.py -q
```

Expected:
- PASS
- Audit records include governed identity metadata
- Unauthorized status updates fail closed

**Step 5: Commit**

```bash
git add backend/app/security/auth_context.py backend/app/repositories/user_scope_repo.py backend/app/schemas/auth_context.py backend/app/security/auth_stub.py backend/app/api/routes/balance_analysis.py backend/app/api/routes/agent.py backend/app/services/agent_service.py backend/app/models/governance.py backend/app/postgres_migrations.py tests/test_auth_context.py tests/test_balance_analysis_auth_scope.py tests/test_agent_api_contract.py tests/test_agent_audit_log_contract.py
git commit -m "Replace fallback auth with governed request identity" -m "Constraint: Launch write paths must stop depending on phase1 fallback users." -m "Rejected: Keep auth_stub as the runtime source of truth | would preserve fake identity semantics in production." -m "Confidence: medium" -m "Scope-risk: moderate" -m "Directive: Do not reintroduce direct route-level role checks without going through the auth context layer." -m "Tested: auth context and scoped write-path tests" -m "Not-tested: external SSO integration"
```

**Completion criteria:**
- No targeted write route depends directly on `auth_stub`.
- At least one governed scope source exists in PostgreSQL-backed storage.
- Audit payloads identify the real request principal.

### Task 2: Harden Governance Authority, Queue Behavior, And Build-Run Persistence

**Files:**
- Modify: `backend/app/repositories/governance_repo.py`
- Modify: `backend/app/models/governance.py`
- Modify: `backend/app/governance/settings.py`
- Modify: `backend/app/tasks/broker.py`
- Modify: `backend/app/tasks/worker_bootstrap.py`
- Modify: `backend/app/schemas/materialize.py`
- Modify: `backend/app/storage_bootstrap.py`
- Test: `tests/test_governance_logging.py`
- Test: `tests/test_worker_bootstrap.py`
- Test: `tests/test_materialize_flow.py`
- Test: `tests/test_duckdb_single_writer.py`
- Test: `tests/test_repository_healthchecks.py`
- Test: `tests/test_governance_sql_authority.py`

**Why this exists:**
- `GovernanceRepository` still defaults to `jsonl`.
- SQL authority only covers a narrow subset of streams.
- The task broker can fall back to `StubBroker`, which is useful for dev but not launch-safe.

**API / table targets:**
- Make `cache_build_run` and `cache_manifest` SQL-authoritative for launch flows.
- Add any missing persisted governance tables needed by PnL/executive/liability refresh paths.
- Fail fast in production if the broker is not a real Redis broker.

**Step 1: Write the failing tests**

```python
def test_governance_repo_reads_launch_streams_from_sql_authority():
    repo = GovernanceRepository(..., backend_mode="sql-authority")
    repo.append(CACHE_BUILD_RUN_STREAM, payload)
    assert repo.read_all(CACHE_BUILD_RUN_STREAM)[-1]["run_id"] == payload["run_id"]


def test_worker_bootstrap_rejects_stub_broker_in_production(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        get_broker()
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_governance_logging.py tests/test_worker_bootstrap.py tests/test_materialize_flow.py tests/test_governance_sql_authority.py -q
```

Expected:
- FAIL because launch streams are not fully SQL-authoritative
- FAIL because broker behavior is still permissive

**Step 3: Write the minimal implementation**

- Expand governance persistence so launch-critical streams are first-class SQL citizens.
- Tighten settings so production cannot silently use `StubBroker`.
- Ensure worker bootstrap verifies migrations and broker readiness before loading actors.
- Keep JSONL shadowing only where it still adds dev value and does not conflict with authority.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_governance_logging.py tests/test_worker_bootstrap.py tests/test_materialize_flow.py tests/test_duckdb_single_writer.py tests/test_repository_healthchecks.py tests/test_governance_sql_authority.py -q
```

Expected:
- PASS
- build-run and manifest writes are consistent
- production-mode bootstrap fails closed on invalid broker setup

**Step 5: Commit**

```bash
git add backend/app/repositories/governance_repo.py backend/app/models/governance.py backend/app/governance/settings.py backend/app/tasks/broker.py backend/app/tasks/worker_bootstrap.py backend/app/schemas/materialize.py backend/app/storage_bootstrap.py tests/test_governance_logging.py tests/test_worker_bootstrap.py tests/test_materialize_flow.py tests/test_duckdb_single_writer.py tests/test_repository_healthchecks.py tests/test_governance_sql_authority.py
git commit -m "Make launch governance and queue state authoritative" -m "Constraint: Launch refresh paths need durable build-run and manifest state." -m "Rejected: Keep jsonl as launch authority | weakens concurrency and recovery guarantees." -m "Confidence: medium" -m "Scope-risk: moderate" -m "Directive: New launch-critical task streams must be wired into the authority layer, not left as ad hoc jsonl." -m "Tested: governance repo, worker bootstrap, and materialize flow tests" -m "Not-tested: real multi-node worker deployment"
```

**Completion criteria:**
- Launch-critical task state reads from SQL authority.
- Production cannot start with stub broker behavior.
- Governance persistence is consistent across rerun/recovery paths.

### Task 3: Complete Formal PnL Cutover

**Files:**
- Modify: `backend/app/core_finance/pnl.py`
- Modify: `backend/app/tasks/pnl_materialize.py`
- Modify: `backend/app/services/pnl_service.py`
- Modify: `backend/app/services/pnl_bridge_service.py`
- Modify: `backend/app/repositories/pnl_repo.py`
- Modify: `backend/app/schemas/pnl.py`
- Modify: `backend/app/api/routes/pnl.py`
- Modify: `docs/calc_rules.md`
- Modify: `docs/acceptance_tests.md`
- Test: `tests/test_pnl_phase2_start_pack.py`
- Test: `tests/test_pnl_materialize_flow.py`
- Test: `tests/test_pnl_api_contract.py`
- Test: `tests/test_pnl_bridge_core.py`
- Test: `tests/test_pnl_bridge_service_boundaries.py`
- Test: `tests/test_pnl_formal_enabled_flow.py`
- Test: `tests/test_pnl_formal_semantics_contract.py`

**Why this exists:**
- `backend/app/core_finance/pnl.py` still declares formal semantics incomplete.
- `backend/app/tasks/pnl_materialize.py` still contains a phase-boundary gate that blocks formal emission.
- Launch dashboard and PnL pages cannot depend on half-cut formal semantics.

**API / table targets:**
- `GET /api/pnl/dates`
- `GET /api/pnl/data`
- `GET /api/pnl/overview`
- `GET /api/pnl/bridge`
- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`

**Step 1: Write the failing tests**

```python
def test_ac_and_fvoci_516_do_not_enter_formal_total():
    rows = normalize_fi_pnl_records([...])
    facts = build_formal_pnl_fi_fact_rows(rows)
    assert facts[0].total_pnl == Decimal("514_only")


def test_pnl_materialize_emits_formal_rows_when_formal_pnl_enabled(tmp_path):
    payload = run_pnl_materialize_sync(...)
    assert payload["formal_fi_rows"] > 0
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_pnl_phase2_start_pack.py tests/test_pnl_materialize_flow.py tests/test_pnl_formal_enabled_flow.py tests/test_pnl_formal_semantics_contract.py -q
```

Expected:
- FAIL because placeholder/gate behavior still exists

**Step 3: Write the minimal implementation**

- Remove `_PHASE2_PLACEHOLDER` semantics from the core formal path.
- Replace the materialize gate with governed config/contract checks.
- Ensure 514/516/517/adjustment semantics match `calc_rules.md`.
- Keep `services/` as orchestration only; formal math remains in `core_finance/`.
- Align PnL bridge consumers with the finalized formal facts instead of start-pack assumptions.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_pnl_phase2_start_pack.py tests/test_pnl_materialize_flow.py tests/test_pnl_api_contract.py tests/test_pnl_bridge_core.py tests/test_pnl_bridge_service_boundaries.py tests/test_pnl_formal_enabled_flow.py tests/test_pnl_formal_semantics_contract.py -q
```

Expected:
- PASS
- formal totals and bridge totals are consistent
- no repo-phase gate blocks formal emission for the launch path

**Step 5: Commit**

```bash
git add backend/app/core_finance/pnl.py backend/app/tasks/pnl_materialize.py backend/app/services/pnl_service.py backend/app/services/pnl_bridge_service.py backend/app/repositories/pnl_repo.py backend/app/schemas/pnl.py backend/app/api/routes/pnl.py docs/calc_rules.md docs/acceptance_tests.md tests/test_pnl_phase2_start_pack.py tests/test_pnl_materialize_flow.py tests/test_pnl_api_contract.py tests/test_pnl_bridge_core.py tests/test_pnl_bridge_service_boundaries.py tests/test_pnl_formal_enabled_flow.py tests/test_pnl_formal_semantics_contract.py
git commit -m "Cut over formal PnL from start-pack to governed semantics" -m "Constraint: Executive and PnL launch views need the same formal totals." -m "Rejected: Keep the phase gate and mask with service fallbacks | would preserve false-positive readiness." -m "Confidence: medium" -m "Scope-risk: broad" -m "Directive: Do not add new PnL semantics in services or routes; keep them in core_finance." -m "Tested: formal PnL materialize, API, and bridge tests" -m "Not-tested: full historical backfill across all legacy input files"
```

**Completion criteria:**
- No formal PnL launch path returns start-pack semantics as if they were complete.
- Materialize emits governed formal facts.
- API and bridge consumers agree on totals and lineage.

### Task 4: Remove Executive Dashboard Shell Demos

**Files:**
- Modify: `backend/app/services/executive_service.py`
- Modify: `backend/app/api/routes/executive.py`
- Modify: `backend/app/schemas/executive_dashboard.py`
- Modify: `backend/app/repositories/pnl_repo.py`
- Modify: `backend/app/repositories/bond_analytics_repo.py`
- Modify: `backend/app/repositories/formal_zqtz_balance_metrics_repo.py`
- Test: `tests/test_executive_service_contract.py`
- Test: `tests/test_executive_dashboard_endpoints.py`
- Test: `tests/test_executive_dashboard_schema_contract.py`
- Test: `tests/test_result_meta_on_all_ui_endpoints.py`
- Test: `tests/test_executive_no_shell_demo_fallback.py`

**Why this exists:**
- `executive_service.py` still returns shell-demo data when governed inputs are absent.
- Frontend dashboard can render, but not with launch-grade truth guarantees.

**API targets:**
- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`
- `/ui/risk/overview`
- `/ui/home/contribution`
- `/ui/home/alerts`

**Step 1: Write the failing tests**

```python
def test_executive_overview_returns_unavailable_not_shell_demo_when_inputs_missing():
    payload = executive_overview(report_date="2026-03-01")
    assert payload["result_meta"]["source_version"] != "sv_exec_dashboard_shell_demo_v1"
    assert "壳层演示" not in json.dumps(payload, ensure_ascii=False)
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py tests/test_executive_dashboard_schema_contract.py tests/test_executive_no_shell_demo_fallback.py -q
```

Expected:
- FAIL because shell-demo paths are still present

**Step 3: Write the minimal implementation**

- Replace shell-demo fallback with governed unavailable/warning states.
- Keep endpoint contracts stable so the frontend does not need a large rewrite.
- Use existing governed repositories rather than inventing a new executive abstraction unless unavoidable.
- Ensure alerts, risk, contribution, and pnl attribution all degrade explicitly and consistently.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py tests/test_executive_dashboard_schema_contract.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_executive_no_shell_demo_fallback.py -q
```

Expected:
- PASS
- no executive endpoint emits shell-demo lineage/version markers
- missing data yields explicit unavailable state instead of demo numbers

**Step 5: Commit**

```bash
git add backend/app/services/executive_service.py backend/app/api/routes/executive.py backend/app/schemas/executive_dashboard.py backend/app/repositories/pnl_repo.py backend/app/repositories/bond_analytics_repo.py backend/app/repositories/formal_zqtz_balance_metrics_repo.py tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py tests/test_executive_dashboard_schema_contract.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_executive_no_shell_demo_fallback.py
git commit -m "Replace executive shell demos with governed unavailable states" -m "Constraint: Dashboard launch cannot mix real facts with fabricated demo figures." -m "Rejected: Keep demo fallback behind result_meta warning only | still leaks fake numbers into launch surfaces." -m "Confidence: medium" -m "Scope-risk: moderate" -m "Directive: New executive cards must read governed repositories or return explicit unavailable states." -m "Tested: executive endpoint and schema contract tests" -m "Not-tested: visual frontend regressions"
```

**Completion criteria:**
- No executive endpoint returns demo values.
- All executive responses still renderable by the current frontend.
- Missing governed inputs are explicit and traceable.

### Task 5: Unify Liability Analytics Into Governed Envelopes

**Files:**
- Create: `backend/app/schemas/liability_analytics.py`
- Modify: `backend/app/api/routes/liability_analytics.py`
- Modify: `backend/app/services/liability_analytics_service.py`
- Modify: `backend/app/repositories/liability_analytics_repo.py`
- Modify: `docs/acceptance_tests.md`
- Test: `tests/test_liability_analytics_api.py`
- Test: `tests/test_liability_analytics_compat_contract.py`
- Test: `tests/test_liability_v1_field_mapping.py`
- Test: `tests/test_result_meta_required.py`
- Test: `tests/test_liability_analytics_envelope_contract.py`

**Why this exists:**
- Liability endpoints still expose V1-compat raw JSON instead of `ApiEnvelope`.
- Frontend contracts explicitly call this out as unfinished.

**API targets:**
- `/api/risk/buckets`
- `/api/analysis/yield_metrics`
- `/api/analysis/liabilities/counterparty`
- `/api/liabilities/monthly`

**Step 1: Write the failing tests**

```python
def test_liability_endpoints_return_governed_result_meta(client):
    response = client.get("/api/risk/buckets")
    body = response.json()
    assert "result_meta" in body
    assert body["result_meta"]["basis"] in {"formal", "analytical"}
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_liability_analytics_api.py tests/test_liability_analytics_compat_contract.py tests/test_liability_v1_field_mapping.py tests/test_liability_analytics_envelope_contract.py -q
```

Expected:
- FAIL because current routes still return bare payloads

**Step 3: Write the minimal implementation**

- Add explicit Pydantic schemas for liability read payloads.
- Wrap each route in a governed envelope with lineage, quality, and basis semantics.
- Preserve V1 field names inside `result` for consumer compatibility, but stop returning raw top-level JSON.
- Keep compatibility math in `core_finance/liability_analytics_compat.py` until a deeper formal rewrite is separately authorized.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_liability_analytics_api.py tests/test_liability_analytics_compat_contract.py tests/test_liability_v1_field_mapping.py tests/test_result_meta_required.py tests/test_liability_analytics_envelope_contract.py -q
```

Expected:
- PASS
- frontend-facing liability endpoints now conform to the common envelope contract

**Step 5: Commit**

```bash
git add backend/app/schemas/liability_analytics.py backend/app/api/routes/liability_analytics.py backend/app/services/liability_analytics_service.py backend/app/repositories/liability_analytics_repo.py docs/acceptance_tests.md tests/test_liability_analytics_api.py tests/test_liability_analytics_compat_contract.py tests/test_liability_v1_field_mapping.py tests/test_result_meta_required.py tests/test_liability_analytics_envelope_contract.py
git commit -m "Wrap liability analytics in governed API envelopes" -m "Constraint: Frontend launch cannot special-case raw V1 JSON for one analytics surface." -m "Rejected: Leave routes raw and patch only frontend typings | would preserve contract inconsistency." -m "Confidence: medium" -m "Scope-risk: moderate" -m "Directive: Keep V1 field compatibility inside result payloads, not in the transport contract." -m "Tested: liability API and envelope contract tests" -m "Not-tested: downstream frontend page adjustments"
```

**Completion criteria:**
- Liability endpoints return the same envelope shape as the other governed surfaces.
- V1 field compatibility is preserved inside `result`.
- The frontend no longer needs a liability-only transport exception.

### Task 6: Close Bond Analytics Phase 3 Gaps And Activate Advanced Attribution

**Files:**
- Modify: `backend/app/services/bond_analytics_service.py`
- Modify: `backend/app/services/advanced_attribution_service.py`
- Modify: `backend/app/core_finance/bond_analytics/engine.py`
- Modify: `backend/app/core_finance/bond_analytics/read_models.py`
- Modify: `backend/app/repositories/bond_analytics_repo.py`
- Modify: `backend/app/repositories/yield_curve_repo.py`
- Modify: `backend/app/tasks/bond_analytics_materialize.py`
- Modify: `backend/app/tasks/yield_curve_materialize.py`
- Modify: `backend/app/schemas/advanced_attribution.py`
- Test: `tests/test_bond_analytics_service.py`
- Test: `tests/test_bond_analytics_curve_effects.py`
- Test: `tests/test_bond_analytics_refresh_contract.py`
- Test: `tests/test_advanced_attribution_contract.py`
- Test: `tests/test_bond_dashboard_api_contract.py`
- Test: `tests/test_macro_bond_linkage.py`

**Why this exists:**
- Bond analytics still documents transaction-level trading and benchmark-side values as placeholders.
- `advanced_attribution_service.py` still returns `status="not_ready"` instead of a minimal real result set.

**API targets:**
- `/api/bond-analytics/return-decomposition`
- `/api/bond-analytics/benchmark-excess`
- `/api/bond-analytics/action-attribution`
- `/ui/balance-analysis/advanced-attribution`

**Step 1: Write the failing tests**

```python
def test_advanced_attribution_returns_real_summary_when_curves_and_bridge_exist():
    payload = advanced_attribution_bundle_envelope(...)
    assert payload["result"]["status"] != "not_ready"


def test_benchmark_excess_does_not_zero_benchmark_side_when_inputs_exist():
    payload = get_benchmark_excess(...)
    assert payload["result"]["benchmark_return"] != "0.00000000"
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_bond_analytics_service.py tests/test_bond_analytics_curve_effects.py tests/test_bond_analytics_refresh_contract.py tests/test_advanced_attribution_contract.py tests/test_bond_dashboard_api_contract.py -q
```

Expected:
- FAIL because placeholder/not_ready behavior is still active

**Step 3: Write the minimal implementation**

- Promote the currently available upstream summaries into a minimal advanced-attribution result instead of a pure `not_ready` contract.
- Replace benchmark/trading placeholder branches when the required inputs are present.
- Keep strict warnings for still-missing components rather than silently zeroing them.
- Reuse current yield-curve and bridge lineage instead of inventing a second attribution state channel.

**Step 4: Run focused verification**

Run:

```powershell
pytest tests/test_bond_analytics_service.py tests/test_bond_analytics_curve_effects.py tests/test_bond_analytics_refresh_contract.py tests/test_advanced_attribution_contract.py tests/test_bond_dashboard_api_contract.py tests/test_macro_bond_linkage.py -q
```

Expected:
- PASS
- advanced attribution produces a real, warning-aware analytical/scenario result
- bond analytics no longer advertises placeholder values where governed inputs exist

**Step 5: Commit**

```bash
git add backend/app/services/bond_analytics_service.py backend/app/services/advanced_attribution_service.py backend/app/core_finance/bond_analytics/engine.py backend/app/core_finance/bond_analytics/read_models.py backend/app/repositories/bond_analytics_repo.py backend/app/repositories/yield_curve_repo.py backend/app/tasks/bond_analytics_materialize.py backend/app/tasks/yield_curve_materialize.py backend/app/schemas/advanced_attribution.py tests/test_bond_analytics_service.py tests/test_bond_analytics_curve_effects.py tests/test_bond_analytics_refresh_contract.py tests/test_advanced_attribution_contract.py tests/test_bond_dashboard_api_contract.py tests/test_macro_bond_linkage.py
git commit -m "Turn bond analytics launch surfaces from placeholders into governed results" -m "Constraint: Frontend analysis pages already depend on these contracts in real mode." -m "Rejected: Keep not_ready contracts and patch in frontend copy | would preserve backend incompleteness behind UI gloss." -m "Confidence: medium" -m "Scope-risk: broad" -m "Directive: If an attribution component is still unavailable, return a warning-backed explicit gap, not a fabricated zero." -m "Tested: bond analytics, curve effects, and advanced attribution tests" -m "Not-tested: full production-sized market dataset"
```

**Completion criteria:**
- Advanced attribution is no longer a pure `not_ready` surface.
- Bond analytics returns real values when governed inputs exist.
- Remaining unavailable inputs are explicit warnings, not silent placeholders.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

## Verification Milestones

- After Task 2: queue/governance/auth substrate is launch-safe enough to trust downstream fixes.
- After Task 3: PnL and bridge numbers are stable enough for dashboard consumers.
- After Task 5: all targeted launch APIs share the same transport contract.
- After Task 6: the remaining analysis surfaces stop advertising placeholders as launch-ready behavior.

Plan complete and saved to `docs/plans/2026-04-15-backend-launch-foundations.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
