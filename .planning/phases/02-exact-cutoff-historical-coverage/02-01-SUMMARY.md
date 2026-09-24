---
phase: 02-exact-cutoff-historical-coverage
plan: "01"
subsystem: api
tags: [pnl, duckdb, exact-cutoff, batch-precompute, governance]

requires: []
provides:
  - Repository-bounded all-available cutoff orchestration with canonical date and year validation
  - In-lock exact-source preflight and post-result cutoff validation before batch completion
  - Exact selected-cutoff status matching without legacy batch leakage
  - DuckDB partition idempotence, lock, authorization, and route-wiring contract evidence
affects: [pnl-by-business, historical-precompute, phase-03-runtime-resilience]

tech-stack:
  added: []
  patterns:
    - Validate repository source resolution before invoking a cutoff-specific persistence path
    - Match batch lifecycle records only through explicit target membership

key-files:
  created:
    - .planning/phases/02-exact-cutoff-historical-coverage/02-01-SUMMARY.md
  modified:
    - backend/app/tasks/pnl_materialize.py
    - backend/app/services/pnl_service.py
    - tests/test_pnl_api_contract.py

key-decisions:
  - "Keep the existing selected scope and authorization unchanged; the route already exposed the required default and enum."
  - "Preflight every batch cutoff against the repository inside the single writer lock, then retain returned-cutoff validation as a second defense."
  - "Treat canonical YYYY-MM-DD and years 2000 through 2100 as direct service and worker contracts."

patterns-established:
  - "Exact-cutoff fail-closed: do not enter the persistence path when repository resolution differs from the requested cutoff."
  - "Batch status isolation: explicit target_as_of_dates membership takes precedence, and legacy blank-date fallback applies only to records without targets."

requirements-completed: [COV-01, COV-02, COV-03]

duration: 1h 22m
completed: 2026-07-16
---

# Phase 02 Plan 01: Exact-Cutoff Historical Coverage Summary

**Authorized repository-bounded batch precompute now fails closed before any wrong-cutoff write and reports lifecycle status only for explicitly targeted cutoffs.**

## Performance

- **Duration:** 1h 22m
- **Started:** 2026-07-16T10:38:25-04:00
- **Completed:** 2026-07-16T12:00:37-04:00
- **Tasks:** 3
- **Files modified:** 3 production/test files plus this summary

## Accomplishments

- Preserved one writer-lock context for a de-duplicated, sorted batch while preflighting each requested cutoff against actual repository resolution before invoking persistence.
- Added a second fail-closed check that rejects a precompute result whose reported `as_of_date` differs from the requested cutoff.
- Prevented a sparse all-available batch from appearing as the latest cutoff when that cutoff is absent from `target_as_of_dates`, while retaining positive historical membership and legacy selected behavior.
- Enforced canonical `YYYY-MM-DD` parsing and the API year range at direct service and worker boundaries; compact and ISO-week date forms no longer normalize silently.
- Added real DuckDB evidence for exact-partition replacement, repeat idempotence, and cross-cutoff isolation, plus lock failure, auth, route default, sparse enumeration, and no-dispatch contracts.

## Task Commits

Each test or implementation boundary was committed atomically:

1. **Task 1: Expose exact-cutoff coverage gaps** - `3be46d21f` (test)
2. **Task 2: Fail closed on returned cutoff drift** - `5423fcc06` (fix)
3. **Task 2: Bound status and date contracts** - `a7e0dca03` (fix)
4. **Task 2 hardening: Require a pre-write cutoff guard** - `e7f4ee1f8` (test)
5. **Task 2 hardening: Preflight exact batch cutoffs** - `339363b4a` (fix)

**Plan metadata:** this summary is committed separately as the final documentation artifact.

## Files Created/Modified

- `backend/app/tasks/pnl_materialize.py` - Validates direct year/batch dates, preflights each repository cutoff inside the writer lock, and verifies each returned cutoff.
- `backend/app/services/pnl_service.py` - Applies direct year/date bounds, filters only canonical repository dates, and confines legacy status fallback to non-batch records.
- `tests/test_pnl_api_contract.py` - Covers sparse targets, invalid/empty requests, one-lock failure semantics, pre-write storage safety, real partition idempotence, exact status membership, authorization, and route wiring.
- `.planning/phases/02-exact-cutoff-historical-coverage/02-01-SUMMARY.md` - Records implementation, evidence, deviations, and residual Phase 03 risks.

## Decisions Made

- Kept `scope=selected` as the default and reused `pnl_by_business.adjustment:write`; the existing route implementation and runtime auth tests already satisfied Task 3, so no route edit was warranted.
- Put repository source resolution immediately before every batch precompute call under the existing writer lock. A post-return check alone was insufficient because persistence occurs before the result is returned.
- Left cross-scope job de-duplication, worker heartbeat, and actor time-limit policy unchanged because they belong to runtime resilience rather than exact-cutoff correctness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Baseline mismatch] Audited and strengthened an implementation already present in the plan base**

- **Found during:** Task 1 RED gate
- **Issue:** The base already contained `5b8afef88` (`feat(pnl): add exact-cutoff historical precompute`) and `97eb0c17f` (`fix(pnl): harden ytd precompute correctness`), so the plan's original missing-feature selector unexpectedly passed (`3 passed`).
- **Fix:** Preserved the mismatch as evidence and shifted to a focused correctness audit instead of manufacturing a failing baseline.
- **Files modified:** `tests/test_pnl_api_contract.py`
- **Verification:** Strengthened RED set produced 11 expected behavior failures and 10 passing characterization gates before production edits.
- **Committed in:** `3be46d21f`

**2. [Missing critical correctness] Blocked wrong-partition persistence before it can start**

- **Found during:** Task 2 review after the first returned-cutoff fix
- **Issue:** Comparing `result["as_of_date"]` after `precompute_pnl_by_business_payloads` returned could detect a wrong cutoff but not prevent that function from already replacing an earlier partition.
- **Fix:** Added an in-lock `PnlRepository.max_formal_or_nonstd_report_date_in_year(year, as_of_cap=cutoff)` preflight before each call, while retaining the returned-value check.
- **Files modified:** `backend/app/tasks/pnl_materialize.py`, `tests/test_pnl_api_contract.py`
- **Verification:** Natural RED proved the old path invoked precompute; GREEN proves zero precompute calls and an unchanged real DuckDB sentinel when June resolves to May.
- **Committed in:** `e7f4ee1f8`, `339363b4a`

**3. [Data-contract hardening] Rejected liberal ISO parsing and out-of-range direct calls**

- **Found during:** Task 2 boundary audit
- **Issue:** `date.fromisoformat` accepts compact and ISO-week forms, and direct service/worker calls were not constrained to the route's 2000-2100 year range.
- **Fix:** Added full canonical-date matching and direct year validation without changing governed metrics or the selected-scope return shape.
- **Files modified:** `backend/app/tasks/pnl_materialize.py`, `backend/app/services/pnl_service.py`, `tests/test_pnl_api_contract.py`
- **Verification:** Compact/week dates and years 1999/2101 fail before queue or precompute; leap-year month-end remains accepted.
- **Committed in:** `3be46d21f`, `5423fcc06`, `a7e0dca03`

---

**Total deviations:** 3 auto-fixed (1 baseline mismatch, 1 critical correctness gap, 1 data-contract hardening).
**Impact on plan:** All changes remain inside the page-local exact-cutoff workflow; no schema, formula, auth framework, shared queue, or Phase 03 runtime policy changed.

## Validation Evidence

- Initial plan selector before audit: `3 passed, 133 deselected` (baseline already implemented).
- Strengthened natural RED: `11 failed, 10 passed, 132 deselected` with failures limited to cutoff drift, status leakage, canonical dates, year bounds, and sparse enumeration.
- Pre-write guard RED: `1 failed, 152 deselected`; the old code did not raise before persistence.
- Focused high-risk GREEN: `21 passed, 132 deselected`.
- Exact plan selector GREEN: `9 passed, 144 deselected`.
- Write-route authorization contract: `48 passed`.
- Full PnL API contract: `153 passed in 368.71s`.
- Changed production modules Ruff check: passed.
- Full scoped Ruff command: 14 pre-existing findings only (13 `UP017` timezone aliases in the test file and one untouched route `I001`); excluding those known baseline rules yields `All checks passed!`.
- GitNexus symbol impacts for `_rebuild_pnl_by_business_precompute`, `request_pnl_by_business_precompute_rebuild`, and `pnl_by_business_precompute_status`: `LOW`, zero indexed upstream callers/processes.
- Isolated branch diff from `321a5847f`: only the two production modules and PnL contract test before this summary; no route, schema, formula, auth framework, or Phase 03 file changed.

## Issues Encountered

- GitNexus is indexed to the main worktree, not this isolated branch. `detect-changes` therefore either returned no staged changes or reported 118 unrelated main-worktree files at MEDIUM aggregate risk. Per-symbol impact checks were LOW, and the isolated `git diff 321a5847f..HEAD` was used as the authoritative scope check.
- The first full-file pytest attempt was stopped after prolonged progress so the pre-write correctness review could proceed. The final post-fix run completed cleanly with all 153 tests passing.
- Full tests created an untracked `fake-governance/.locks` artifact; it was verified inside the isolated worktree and removed after each run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- COV-01 through COV-03 have exact-cutoff task, status, authorization, and partition evidence.
- Phase 03 should evaluate cross-scope active-job de-duplication, heartbeat/progress evidence, and the one-hour actor time limit under large historical batches. These were intentionally recorded as runtime risks and not changed here.
- No blocker remains for the next planned runtime-resilience work.

## Self-Check: PASSED

- Summary file exists at the planned path.
- All five task/test commits exist on `codex/phase-02-exact-cutoff`.
- Final full contract and authorization suites are green.
- Branch diff is limited to the planned page-local workflow and this summary.

---
*Phase: 02-exact-cutoff-historical-coverage*
*Completed: 2026-07-16*
