---
phase: 03
slug: incremental-rebuild-and-recovery
status: complete
researched: 2026-07-17
requirements: [INC-01, INC-02, REC-01]
---

# Phase 03 Research: Incremental Rebuild and Recovery

## Scope

Phase 03 closes the `/pnl-by-business` incremental refresh and recovery loop without changing PnL formulas, DuckDB schema, shared queue/cache infrastructure, or application-wide state. The governing decisions are in `03-CONTEXT.md`.

## Existing implementation evidence

- `backend/app/services/pnl_service.py`
  - `_enqueue_pnl_by_business_precompute_refresh` derives the year from a manual-adjustment date but dispatches `as_of_date=None`; it does not freeze the affected same-year cumulative cutoff set.
  - `_queue_pnl_by_business_precompute_refresh` serializes dispatch decisions, but an existing queued record causes an early no-op and an existing running record can receive only one unmerged queued follow-up.
  - `_pnl_by_business_precompute_status_record` and `_pnl_by_business_precompute_status_payload` already resolve a selected cutoff and expose live fallback, failure category, retry attempt, and safe operator-facing errors.
- `backend/app/tasks/pnl_materialize.py`
  - The governed formal materialization transaction commits before the page precompute call, but the current follow-on refresh is limited to the current `report_date`.
  - `_rebuild_pnl_by_business_precompute` validates exact target cutoffs, holds one writer lock, and records batch lifecycle evidence. A single cutoff exception currently aborts the remaining target list.
  - The actor retry policy is global; phase behavior needs an explicit transient/permanent classification so only transient failures retry automatically.
- `frontend/src/features/pnl/PnlByBusinessPage.tsx`
  - `PnlByBusinessPrecomputeStatusPanel` already has the correct selected-cutoff query boundary and live-fallback/manual-retry affordance. Only additive exact-cutoff recovery evidence should be added if the backend contract requires it; no redesign is needed.
- `tests/test_pnl_api_contract.py`
  - Existing tests cover manual rebuild dispatch, exact-cutoff batch validation, one writer lock, drift rejection, lifecycle failure records, and status payload behavior. Extend this file with the smallest orchestration and recovery cases.

## Recommended implementation

### 1. Freeze same-year cumulative invalidation targets

Add a page-local helper in `pnl_service.py` that maps the earliest committed change date to the first available month-end cutoff on or after that date, then returns all available month-end cutoffs through the end of the same year. The list is sorted, deduplicated, and frozen before dispatch.

Use that helper from both committed sources:

1. governed formal-source materialization, after its transaction commits;
2. approved manual-adjustment state changes that alter the formal result.

Persist the requested earliest change date, frozen targets, and trigger reason in the queued governance record. An empty target set is an audited no-task event. Earlier cutoffs are never included.

Currentness remains fingerprint-based. Before a queued successor is handed to the worker, remove targets already current under their cutoff-local fingerprint. If all are current, append an audited no-change completion instead of dispatching work.

### 2. Coalesce one durable successor

Keep the current page-local dispatch lock. Treat running and queued records as immutable events; append a new event for the same queued successor `run_id` when its target list is widened.

Within the lock:

- no in-flight run: append one queued record and dispatch it;
- running only: append one queued successor and dispatch it once;
- running plus queued successor, or queued only: union the incoming targets into that successor, retaining the earliest-to-latest sorted range, and append a superseding queued event for the same `run_id`; do not dispatch another actor;
- manual `raise_on_duplicate=True`: preserve the current conflict contract instead of silently coalescing operator requests.

The worker must load the latest effective queued record for its `run_id` before freezing execution targets, so a widened durable successor is honored even when the original message carried a narrower list.

### 3. Isolate cutoff failures and exact-cutoff recovery

In `_rebuild_pnl_by_business_precompute`, keep one writer lock but catch failures per target cutoff. Continue with remaining targets and persist `cutoff_results` entries with explicit `completed` or `failed` state, safe failure category, and attempt evidence.

The batch lifecycle is:

- `completed` when every cutoff is current or rebuilt successfully;
- `partial_failed` when at least one cutoff failed and at least one completed/current cutoff remains usable;
- `failed` only when no target succeeded/current or the batch cannot start.

Automatic retry targets only failed/stale exact cutoffs and only transient categories (for example lock timeout or temporary worker/transport failure). Contract, cutoff-drift, and validation errors are permanent. Manual retry keeps `scope=selected` and the exact selected cutoff.

Status resolution must prefer the selected cutoff's result from `cutoff_results`, so one failed cutoff remains visible while unaffected current partitions continue serving precomputed results. Failed/stale selected cutoffs serve `live_fallback` until their fingerprint is current again.

### 4. Frontend contract

Keep the existing page layout. If additive fields are needed, extend `PnlByBusinessPrecomputeStatus` with selected-cutoff recovery state such as `cutoff_status`, `retryable`, or `retry_exhausted`; render them inside the current status panel. Never expose raw exception text.

## Threat model and abuse boundaries

- **T-03-01 target amplification:** reject cross-year, non-month-end, duplicate, or empty ungoverned targets; cap targets to the repository's available same-year cutoffs.
- **T-03-02 retry storm:** only transient failures auto-retry; one durable successor per year prevents duplicate queued fan-out.
- **T-03-03 stale overwrite:** worker reloads the effective queued record and verifies cutoff-local fingerprints/source cutoffs before write.
- **T-03-04 information disclosure:** status API returns categorized safe messages, never raw worker/database exception text.
- **T-03-05 operator misuse:** manual retry remains exact-cutoff and preserves duplicate/conflict behavior.

## Validation Architecture

### Test layers

1. Pure/helper tests: changed-date to frozen cutoff targets, same-year boundary, non-month-end mapping, dedupe/sort, no-target audit.
2. Dispatch tests: no in-flight dispatch; running creates one successor; overlap widens the same successor without a second send; operator duplicate remains a conflict.
3. Worker tests: per-cutoff failure isolation, later targets continue, mixed result record, transient-only retry target selection, permanent failure exhaustion.
4. Status/contract tests: failed selected cutoff reports live fallback and retry state; unaffected current cutoff remains precomputed; safe error text only; exact-cutoff manual retry.
5. Frontend checks only if the TypeScript contract/panel changes: targeted Vitest/component test, scoped lint/typecheck, and `npm run debt:audit`.

### Commands

- Fast backend loop: `pytest tests/test_pnl_api_contract.py -q -k "precompute or incremental or recovery or coalesce"`
- Complete page contract: `pytest tests/test_pnl_api_contract.py -q`
- Broader changed boundary: `pytest tests/test_pnl_by_business_precompute_ftp_parity.py -q`
- Frontend, if touched: targeted Vitest plus `npm run debt:audit` from `frontend/`.

### Evidence limitations

The project GitNexus, metric-contract, lineage-evidence, and data-catalog MCP tools were not exposed in this session. This research uses the local Phase 02 verification, repository code, and tests. Before editing symbols, attempt the required local GitNexus impact workflow; before commit, run change detection. If tooling remains unavailable, record the failure and obtain explicit approval before bypassing the mandated gate. No metric definition, formula, unit, or source lineage is inferred here.

## Planning boundaries

- Prefer two plans: backend incremental/coalescing first, recovery/status and UI contract second.
- Keep tests adjacent to each behavior change.
- Do not refactor shared queue/cache/auth infrastructure or alter formal PnL calculations.
- Use exact-path commits because the worktree contains unrelated staged and unstaged changes.
