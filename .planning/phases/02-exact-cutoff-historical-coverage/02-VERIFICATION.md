---
phase: 02-exact-cutoff-historical-coverage
verified: "2026-07-17T00:10:01Z"
status: passed
score: "7/7 must-haves verified"
overrides_applied: 0
deferred:
  - truth: "Overlapping automatic refreshes are coalesced across selected and all-available scopes."
    addressed_in: "Phase 03"
    evidence: "Phase 03 success criterion 2 requires at most one queued follow-up for each affected cutoff when automatic refresh requests overlap."
  - truth: "Long-running batches expose heartbeat/progress, stale-run recovery, bounded actor behavior, and independent retry."
    addressed_in: "Phase 03"
    evidence: "Phase 03 goal requires per-cutoff recovery, and success criterion 3 requires failed or stale cutoffs to remain visible and independently retryable."
---

# Phase 02: Exact-Cutoff Historical Coverage Verification Report

**Phase Goal:** Give `/pnl-by-business` independent precompute coverage and truthful state resolution for every available 2026 month-end cutoff.
**Verified:** 2026-07-17T00:10:01Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | An authorized operator can submit one explicitly year-bounded `all_available` build. | ✓ VERIFIED | The route constrains `year`, exposes only `selected\|all_available`, checks write permission before service lookup, and dispatches one service request (`backend/app/api/routes/pnl.py:245-264`). The service validates the scope/year combination and sends one task carrying the complete target list (`backend/app/services/pnl_service.py:2008-2045`, `:2145-2250`). Route/auth contracts cover both authorization order and the default request path (`tests/test_pnl_api_contract.py:4186-4258`; `tests/test_write_route_auth_contract.py:31-108`). |
| 2 | Current 2026 coverage resolves exactly the six January-through-June month-ends in ascending order, while sparse inputs retain only real in-year month-ends. | ✓ VERIFIED | Repository dates are parsed canonically, constrained to the requested year, checked against the actual calendar month-end, de-duplicated, and sorted (`backend/app/services/pnl_service.py:2310-2347`). The parameterized golden contract asserts both the six-cutoff set and sparse January/March/June inputs, including response, queued event, and dispatched task (`tests/test_pnl_api_contract.py:3659-3754`). Independent spot-check: 2 passed. |
| 3 | Every target is materialized as an independent exact `(year, as_of_date)` partition; reruns replace rather than duplicate and do not disturb another cutoff. | ✓ VERIFIED | One writer lock encloses the batch (`backend/app/tasks/pnl_materialize.py:198-249`). Persistence starts a transaction, deletes only the exact partition, inserts its records, and commits or rolls back (`backend/app/repositories/pnl_repo.py:530-590`). The real DuckDB contract reruns January and preserves the June sentinel (`tests/test_pnl_api_contract.py:3927-3980`). Independent spot-check: 1 passed. |
| 4 | The batch refuses to write or report success if a target resolves to a different source cutoff. | ✓ VERIFIED | Before each precompute call, the worker verifies that the capped source resolver returns the requested cutoff; after the call it verifies the returned `as_of_date` again (`backend/app/tasks/pnl_materialize.py:209-239`). The pre-write test proves no precompute/persistence call occurs on drift, while the post-return test proves failure is recorded and cache invalidation is withheld (`tests/test_pnl_api_contract.py:3982-4087`). Independent spot-check: 2 passed. |
| 5 | A selected historical cutoff sees an in-flight/completed batch only when it is an explicit member, and never inherits a later cutoff's state. | ✓ VERIFIED | Status matching accepts exact `report_date` or explicit `target_as_of_dates` membership and rewrites only a copied response to the selected `period_end` (`backend/app/services/pnl_service.py:2050-2130`, `:2383-2435`). Tests cover historical membership, an unlisted latest cutoff returning idle, per-cutoff completion metadata, and a later run not leaking into the selected cutoff (`tests/test_pnl_api_contract.py:4089-4184`, `:4364-4428`). Independent spot-check: 2 passed across the two status contracts. |
| 6 | The page reports the exact selected cutoff and distinguishes current/precomputed service from governed live fallback. | ✓ VERIFIED | Status derives `is_current` from exact-cutoff metadata and maps it to `serving_mode=precomputed\|live_fallback` (`backend/app/services/pnl_service.py:2050-2130`, `:2442-2465`). The page keys and fetches status with `selectedYear` plus `selectedReportDate`, renders the returned cutoff and service mode, and passes the same selection through the client (`frontend/src/features/pnl/PnlByBusinessPage.tsx:111-157`, `:2029-2071`, `:2809-2827`; `frontend/src/api/pnlClient.ts:476-495`). Existing component/client contracts assert the selected date and fallback presentation (`frontend/src/test/PnlRoutesSmoke.test.tsx:1575-1634`; `frontend/src/test/PnlBusinessClientPrecompute.test.ts:5-58`). |
| 7 | Omitting `scope` preserves the existing selected-cutoff behavior and exact authorization boundary. | ✓ VERIFIED | The route's query default is `selected`, its write guard runs before `_pnl_service()`, and the service retains the single `as_of_date` path (`backend/app/api/routes/pnl.py:245-264`; `backend/app/services/pnl_service.py:2008-2045`). OpenAPI/default and route-wiring contracts passed independently (`tests/test_pnl_api_contract.py:4186-4258`). |

**Score:** 7/7 truths verified

### Deferred Items

These are intentionally later runtime-resilience requirements, not missing Phase 02 correctness controls.

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | Cross-scope active-job de-duplication/coalescing for overlapping automatic refreshes | Phase 03 | Roadmap Phase 03 success criterion 2: each affected cutoff has at most one queued follow-up behind its running build. |
| 2 | Worker heartbeat/progress, stale-run recovery, actor-time-limit behavior, and independent retry | Phase 03 | Roadmap Phase 03 goal is per-cutoff recovery; success criterion 3 explicitly covers visible failed/stale cutoffs and independent retry. |

Phase 04's live-versus-precomputed parity matrix is also explicitly future milestone scope; it is not a Phase 02 acceptance condition.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backend/app/api/routes/pnl.py` | Authorized status/rebuild HTTP contract with compatible default | ✓ VERIFIED | Substantive route, strict enum/default, exact permission ordering, and service wiring at lines 229-264. |
| `backend/app/services/pnl_service.py` | Target enumeration, one-batch queueing, exact selected state resolution | ✓ VERIFIED | Substantive logic at lines 2008-2465; no placeholder path. |
| `backend/app/tasks/pnl_materialize.py` | Normalized exact-cutoff batch execution and lifecycle records | ✓ VERIFIED | Canonical date validation, one lock, per-cutoff pre/post guards, aggregate completion/failure records at lines 151-328. |
| `backend/app/tasks/pnl_by_business_precompute.py` | Cutoff-specific payload computation | ✓ VERIFIED | Resolves and builds payloads against the supplied capped cutoff at lines 106-258. |
| `backend/app/repositories/pnl_repo.py` | Exact read/write partition boundary | ✓ VERIFIED | Exact precompute read at lines 104-187 and transactional replacement at lines 530-590. |
| `frontend/src/api/pnlClient.ts` and `frontend/src/features/pnl/PnlByBusinessPage.tsx` | Selected-date status reaches a visible page state | ✓ VERIFIED | Client sends year/date; page query key, panel, cutoff, and fallback/current presentation are wired. |
| Backend and frontend contract tests | Executable proof of target, idempotence, isolation, status, auth, and page wiring | ✓ VERIFIED | Focused contracts exist and are substantive; nine Phase 02 backend cases were independently spot-checked. |

The plan expresses must-haves in XML body text rather than YAML `must_haves.artifacts`/`key_links`, so `gsd-tools verify artifacts` and `verify key-links` correctly reported no frontmatter declarations. Artifact levels 1-4 and links were therefore verified manually from source and behavior tests.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Page selection | Status API | `selectedYear` + `selectedReportDate` → `getPnlByBusinessPrecomputeStatus` | ✓ WIRED | Query key and request both include the selected cutoff; response feeds the visible panel. |
| Rebuild route | Service | write guard → `request_pnl_by_business_precompute_rebuild` | ✓ WIRED | Authorization precedes service lookup; year/date/scope are passed unchanged. |
| Service | Repository target catalog | `list_union_report_dates()` → `_available_pnl_by_business_precompute_cutoffs` | ✓ WIRED | Produces the bounded canonical month-end list. |
| Service | Worker | one queued message containing `as_of_dates` | ✓ WIRED | Target list and target count are recorded in governance and dispatch payload. |
| Worker | Precompute | exact source preflight → `precompute_pnl_by_business_payloads(as_of_date=cutoff)` → returned-cutoff guard | ✓ WIRED | Prevents either resolver or return-value drift. |
| Precompute | Repository persistence | task-write scope → `replace_pnl_by_business_precompute` | ✓ WIRED | Writes only the exact target partition transactionally. |
| Selected status | Page | exact metadata/governance membership → `serving_mode` and selected `report_date` | ✓ WIRED | A later cutoff cannot substitute for the selection; page renders the exact response. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| Rebuild request | `year`, `scope`, optional `as_of_date` | Authorized HTTP query | Yes — becomes a validated bounded rebuild request | ✓ FLOWING |
| Target enumerator | `target_as_of_dates` | Formal/non-standard repository report dates | Yes — canonical, actual month-ends for the requested year | ✓ FLOWING |
| Queued batch | `as_of_dates`, `target_count`, `run_id` | Validated target list | Yes — one worker message and auditable governance event | ✓ FLOWING |
| Batch worker | `cutoff`, `resolved_cutoff`, `result.as_of_date` | Queued target and exact repository preflight | Yes — guarded cutoff-specific payload results | ✓ FLOWING |
| Exact partition | payload records keyed by `year` + `as_of_date` | Shared governed precompute calculation | Yes — transactional DuckDB rows isolated by cutoff | ✓ FLOWING |
| Selected read/status | `period_end`, exact metadata, matching batch record | Page-selected date | Yes — exact precomputed payload or governed live fallback plus truthful state | ✓ FLOWING |
| Visible panel | `report_date`, `is_current`, `serving_mode` | Status endpoint | Yes — selected cutoff and current/fallback state rendered to the user | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Six current-2026 cutoffs plus sparse actual-month-end filtering/one dispatch | `pytest tests/test_pnl_api_contract.py::test_request_pnl_by_business_precompute_rebuild_all_available_dispatches_exact_month_end_cutoffs -q` | 2 passed in 1.66s | ✓ PASS |
| Exact-partition rerun idempotence and cross-cutoff isolation | `pytest tests/test_pnl_api_contract.py::test_pnl_by_business_precompute_exact_cutoff_partitions_replace_idempotently_and_stay_isolated -q` | 1 passed in 2.15s | ✓ PASS |
| Pre-write and post-return cutoff drift guards | `pytest ...::test_rebuild_pnl_by_business_precompute_exact_cutoff_batch_rejects_resolved_cutoff_drift ...::test_rebuild_pnl_by_business_precompute_exact_cutoff_batch_rejects_returned_cutoff_drift -q` | 2 passed in 1.54s | ✓ PASS |
| Historical batch membership, later-cutoff non-leakage, OpenAPI default, and authorization-before-wiring | `pytest ...::test_pnl_by_business_precompute_batch_status_uses_selected_cutoff ...::test_pnl_by_business_precompute_rebuild_openapi_exposes_all_available_scope ...::test_pnl_by_business_precompute_routes_enforce_scopes_before_wiring_requests ...::test_pnl_by_business_precompute_status_uses_selected_cutoff -q` | 4 passed in 5.89s | ✓ PASS |

The full 155-test PnL contract suite was not rerun during this verification. The repaired review records `155 passed`, the security report records `48 passed` for write-route authorization, and scoped Ruff is recorded clean; this verifier independently exercised the nine highest-value Phase 02 cases above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| COV-01 | Phase 02 / 02-01 | Selecting any available 2026 month-end can use a partition resolved to that exact cutoff. | ✓ SATISFIED | Exact pre/post guards, exact transaction key, exact read path, and idempotence/isolation test. |
| COV-02 | Phase 02 / 02-01 | Exact selected cutoff reports current/precomputed or governed live fallback without later state. | ✓ SATISFIED | Explicit batch membership, selected response date, exact metadata, `serving_mode`, page wiring, and status contracts. |
| COV-03 | Phase 02 / 02-01 | Authorized bounded year build covers all available month-ends without duplicate partitions. | ✓ SATISFIED | Auth-first route, one batch message, calendar month-end enumerator, exact replace transaction, and golden/sparse/idempotence contracts. |

`REQUIREMENTS.md` now records COV-01, COV-02, and COV-03 as complete, consistent with the verified evidence above.

### Static and Safety Checks

- `gsd-tools verify schema-drift 02`: `drift_detected=false`, `blocking=false`.
- Scoped `git diff --check` for the currently modified repository/test files: clean.
- Scoped anti-pattern scan found no actionable TODO/FIXME/stub/debug path. Matches were legitimate SQL bind-variable names (`placeholders`) and empty exception subclasses.
- Current worktree was already dirty. The verifier did not alter implementation files, tests, the Git index, or commits.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | No actionable Phase 02 anti-pattern | — | None |

### Human Verification Required

None. The Phase 02 change is backend/API correctness, and the existing page's selected-cutoff status presentation is covered by direct client/component contracts and source wiring. No visual design change requires subjective review.

### Gaps Summary

No Phase 02 acceptance gaps were found. All three roadmap success criteria, COV-01/COV-02/COV-03, and the four plan must-haves are satisfied in the current code. Phase 03 runtime resilience and Phase 04 parity evidence remain explicitly later work and do not block this phase.

---

_Verified: 2026-07-17T00:10:01Z_
_Verifier: the agent (gsd-verifier)_
