# Phase 03: Incremental Rebuild and Recovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `03-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 03-incremental-rebuild-and-recovery
**Areas discussed:** Invalidation scope, overlapping request coalescing, per-cutoff failure recovery, selected-cutoff page state

## Invalidation Scope

The user selected the recommended first option for every question in this area.

| Decision | Selected approach | Alternatives considered |
| --- | --- | --- |
| Formal refresh trigger | Trigger only after committed source transaction | trigger at request enqueue; trigger at both points |
| Manual-adjustment trigger | Only formal-result-changing approval/revocation/edit events | every draft edit; approval only |
| Multiple change range | Earliest affected cutoff through latest same-year cutoff | separate ranges; changed month only |
| Dispatch failure | Keep business change, fail visibly, use live fallback | roll back change; background log only |
| Affected date evidence | Earliest actual changed date from committed evidence | request report date; rebuild full year |
| Target-set timing | Freeze explicit list when task is dispatched | resolve at execution; expand on retry |
| Cross-year behavior | Same natural year only | cross-year propagation; metric-specific policy |
| Pending service mode | Mark stale immediately and use live fallback | keep old precompute; block the page |
| Non-month-end mapping | First available month-end on/after change date | reject; start from first month-end of year |
| Moved approved adjustment | Invalidate old chain now, new chain after re-approval | invalidate both now; both after re-approval |
| Merged evidence | Retain all event ids, dates, mappings, and reasons | earliest event only; latest event only |
| No available target | Audited no-target result, no empty task | long-lived waiting task; fail business change |
| Identical refresh | Audited no-change, no rebuild | always rebuild; manual-refresh-specific behavior |
| Metadata-only edit | Audit only, no rebuild | always rebuild; ignore the event |
| Removed cutoff | Stop serving but retain historical evidence | physical delete; continue serving |
| Triggering sources | Only governed inputs used by the formal page chain | any system data; adjustments only |
| Fingerprint scope | Cutoff-local cumulative fingerprint | annual global fingerprint; latest version only |
| Evidence ordering | Persist invalidation before dispatch | record after enqueue; record when running |
| Same totals, changed inputs | Rebuild because lineage/details changed | compare totals only; metadata-only update |
| Rolled-back source transaction | No precompute invalidation | mark partitions stale; retry precompute |

## Overlapping Request Coalescing

| Decision | Selected approach | Alternatives considered |
| --- | --- | --- |
| Events during running work | One durable pending-follow-up set | task per event; mutate running task |
| Events while queued | Keep queued task immutable, one successor | mutate queued target list; reject event |
| Overlapping ranges | Earliest merged range with all evidence retained | separate ranges; latest event only |
| Completion handoff | Remove fingerprint-current targets and dispatch residual only | dispatch full successor; discard successor |

## Per-Cutoff Failure Recovery

The user selected the recommended first option for the first three questions, then requested that the interview stop and implementation proceed. The remaining recovery behavior was resolved with the same recommended defaults.

| Decision | Selected/default approach | Alternatives considered |
| --- | --- | --- |
| Partial batch failure | Continue other cutoffs and keep successful partitions | stop batch; roll back batch |
| Automatic retry eligibility | Transient failures only; deterministic errors fail immediately | retry everything; retry nothing |
| Retry scope | Exact failed or stale cutoffs only | retry original batch; earliest failure through latest |
| Exhausted retries | Visible exact-cutoff failure, live fallback, independent manual retry | retry forever; mark full year failed |
| Persistence isolation | Atomic exact-cutoff replacement with source/fingerprint revalidation | multi-cutoff transaction; overwrite without recheck |
| Stale active work | Per-cutoff heartbeat and bounded stale release | year-level failure; indefinite active state |

## Selected-Cutoff Page State

This area was auto-resolved after the user explicitly asked to stop further questioning and begin handling the phase.

| Decision | Default approach | Alternatives considered |
| --- | --- | --- |
| Primary status scope | Exact selected cutoff | year-level headline; global latest task |
| Visible states | Current, stale, queued, running, failed, unavailable with serving mode | generic ready/busy/error only |
| Failure detail | Safe category and timestamp, no raw exception | raw backend error; no reason |
| Retry action | Selected failed/stale cutoff only when uncovered by active work | always-visible all-year retry; no manual retry |
| Page availability | Governed live fallback for affected cutoff; unaffected cutoffs remain current | serve stale precompute; block the page |

## the agent's Discretion

- Internal record/helper/task names.
- Page-local durable pending-work representation.
- Heartbeat field names and polling cadence within the existing bounded stale policy.
- Targeted test decomposition and implementation sequence.

## Deferred Ideas

- Phase 04 exact parity evidence matrix.
- Production scheduling that waits for future cutoffs.
- Shared queue/cache/schema/auth refactors.
- P1-10 frontend formal aggregation ownership.
