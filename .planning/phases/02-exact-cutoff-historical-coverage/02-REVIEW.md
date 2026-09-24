---
phase: "02-exact-cutoff-historical-coverage"
reviewed: "2026-07-16T16:42:58Z"
depth: standard
diff_base: "0a7d78f2e"
diff_head: "f791b0499"
working_tree_overlay_reviewed: true
files_reviewed: 3
files_reviewed_list:
  - backend/app/services/pnl_service.py
  - backend/app/tasks/pnl_materialize.py
  - tests/test_pnl_api_contract.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-16T16:42:58Z  
**Depth:** standard  
**Files Reviewed:** 3  
**Status:** clean

## Summary

The exact diff from `0a7d78f2e` through `f791b0499`, plus the current Phase 02 working-tree repairs, was reviewed. The implementation correctly derives bounded repository-backed month-end targets, normalizes and de-duplicates the batch, holds one DuckDB writer lock, performs source-cutoff preflight before each write, keeps the returned-cutoff defense, preserves selected-scope behavior, prevents unrelated batch status leakage, and retains the existing route authorization.

All three findings from the initial review are resolved and independently verified. All reviewed files meet the Phase 02 quality standard; no security, metric-definition, unit, date-basis, production-correctness, or remaining test-reliability issue was found.

## Resolved Findings

### RES-WR-01: Post-return cutoff guard now has an independent negative regression

**Production guard:** `backend/app/tasks/pnl_materialize.py:230-239`  
**Regression test:** `tests/test_pnl_api_contract.py:4030-4086`  
**Resolution:** The new test makes preflight resolve exactly to `2026-06-30`, calls precompute with that cutoff, then returns `2026-05-31`. It verifies the returned-cutoff guard raises, lifecycle records are exactly `running` then `failed`, and runtime caches are not cleared. The existing prewrite sentinel test remains separate and unchanged.

### RES-IN-01: Scoped Ruff import-order check is clean

**File:** `backend/app/tasks/pnl_materialize.py:1-12`  
**Resolution:** The extra blank line after `import duckdb` was removed. The same scoped Ruff command now reports `All checks passed!`.

### RES-IN-02: Acceptance coverage pins both the six-date 2026 set and sparse inputs

**File:** `tests/test_pnl_api_contract.py:3659-3746`  
**Resolution:** The parameterized contract now contains a golden current-2026 case asserting all six ascending month-ends from January through June, plus the original sparse/invalid-input case asserting January, March, and June. Both cases verify the response, dispatched task payload, queued target list, and target count.

## Validation Evidence

- Three-finding regression selector: `4 passed, 151 deselected`.
- Phase 02 precompute selector: `11 passed, 144 deselected`.
- Full PnL contract suite (implementer-reported final): `155 passed`.
- Scoped Ruff for both production files: `All checks passed!`.
- `git diff --check` for the repaired task and contract test: clean.

## Audit Trail

- **Initial review - 2026-07-16T16:22:59Z:** status `issues_found`; 0 critical, 1 warning, and 2 info findings.
- **Repair re-review - 2026-07-16T16:42:58Z:** WR-01, IN-01, and IN-02 were reread against the current main-worktree overlay and passed targeted verification; status changed to `clean` with zero open findings.
- The reviewer changed only this report. Source and test repairs remain uncommitted working-tree changes owned by the implementing workflow.

## Deferred Phase 03 Runtime Risks

The existing one-hour actor limit, absence of per-cutoff heartbeat/progress events, retry/deduplication policy across scopes, and long-batch operational behavior remain Phase 03 runtime-resilience work. They are not counted as Phase 02 findings because this phase explicitly preserved those policies and the reviewed exact-cutoff correctness path is bounded and idempotent.

---

_Reviewed: 2026-07-16T16:42:58Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
