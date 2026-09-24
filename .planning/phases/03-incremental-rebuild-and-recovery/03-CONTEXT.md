# Phase 03: Incremental Rebuild and Recovery - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Keep the existing `/pnl-by-business` exact-cutoff precompute partitions current after governed source or approved manual-adjustment changes. Phase 03 adds same-year cumulative invalidation, one coalesced follow-up behind active work, per-cutoff failure isolation, and independent recovery. It preserves the Phase 02 exact-cutoff read path and governed live fallback. It does not change PnL, ADB, balance, yield, FTP, VAT, FX, or classification formulas; add database schema; refactor shared queue/cache/auth infrastructure; or introduce production scheduling policy.

</domain>

<decisions>
## Implementation Decisions

### Invalidation scope and evidence
- **D-01:** Trigger invalidation only after the formal source transaction commits successfully. A failed and rolled-back source transaction records its own failure but does not make current precompute partitions stale.
- **D-02:** Manual adjustments trigger invalidation only when the formal result changes: approval, revocation of an approved adjustment, or editing an approved adjustment. Pending drafts and metadata-only edits remain audit events without rebuild work.
- **D-03:** Establish the affected start from committed change evidence, never from a guessed request date. If the earliest changed date is not month-end, map it to the first available month-end on or after that date and retain both dates in evidence.
- **D-04:** Propagate only within the same natural year. Build the explicit target list from real available month-ends at or after the affected cutoff; never manufacture missing cutoffs.
- **D-05:** When multiple committed changes overlap, use the earliest affected cutoff and merge through the latest available same-year cutoff while retaining every source/adjustment event id, original date, mapped cutoff, and trigger reason.
- **D-06:** Freeze a task's explicit target list when it is actually dispatched. A later event never mutates a queued or running task.
- **D-07:** Persist invalidation evidence before attempting queue dispatch. A dispatch failure keeps the business change committed, marks affected cutoffs stale/rebuild-required, serves governed live fallback, and remains independently retryable.
- **D-08:** Affected partitions stop serving precomputed data immediately after committed evidence marks them stale. Earlier cutoff-local partitions remain current when their own cumulative fingerprints still match.
- **D-09:** Use cutoff-local cumulative fingerprints over governed inputs and active adjustments, not a year-global version or output-total-only comparison. Detail, lineage, record-count, or diagnostic changes invalidate even when headline totals are unchanged.
- **D-10:** An identical committed input fingerprint is an audited no-change result. If no available month-end exists after the affected date, record an audited no-target result and do not create an empty or long-lived task.
- **D-11:** If an approved adjustment moves from an old report date to a new pending report date, invalidate the old cutoff chain immediately; invalidate the new chain only after re-approval.
- **D-12:** If a previously available cutoff loses current formal-source support, stop serving its old partition but retain the historical partition and governance evidence; physical deletion is outside this phase.
- **D-13:** Automatic invalidation is limited to governed inputs actually consumed by the `/pnl-by-business` formal calculation chain.

### Overlapping request coalescing
- **D-14:** While work is running, merge new automatic invalidations into one durable pending-follow-up set. Do not mutate the running task or emit one queue message per event.
- **D-15:** A queued-but-not-started task is also immutable. New events form at most one successor follow-up.
- **D-16:** Merge pending target ranges to the earliest affected cutoff through the latest available cutoff, retaining all contributing evidence.
- **D-17:** When active work finishes, recheck cutoff-local fingerprints, remove targets already made current, and freeze/dispatch only the residual stale set. If none remain, record an audited coalesced no-task outcome.

### Per-cutoff failure and recovery
- **D-18:** Batch execution is per-cutoff isolated: one cutoff failure does not stop later cutoffs or roll back already successful partitions. The run records a terminal result for every target.
- **D-19:** Only transient failures such as lock contention or temporary execution/storage faults receive bounded automatic retries. Deterministic date, source, cutoff, contract, or validation failures fail immediately and wait for correction.
- **D-20:** Automatic and manual retries target only failed or stale cutoffs. Current cutoffs are not recalculated; the existing explicit all-available operator action remains separate.
- **D-21:** After the retry limit, the exact cutoff remains visibly failed, continues through governed live fallback, exposes safe failure category and last-failure time, and allows an independent authorized manual retry. Other current cutoffs continue serving normally.
- **D-22:** Each cutoff persistence boundary is atomic. A retry must revalidate exact source cutoff and current fingerprints before replacing that partition.
- **D-23:** Record per-cutoff progress/heartbeat evidence so stale active work can be released without treating the whole year as failed. The planner may keep the existing bounded stale threshold unless research demonstrates a safer page-local value.

### Selected-cutoff page state
- **D-24:** Reuse the existing precompute status panel; no visual redesign. The primary state is always the currently selected exact cutoff, not an ambiguous year-level task.
- **D-25:** Distinguish `current/precomputed`, `stale/live_fallback`, `queued/live_fallback`, `running/live_fallback`, `failed/live_fallback`, and status-unavailable states without hiding the page's main result.
- **D-26:** Show exact cutoff, serving mode, safe failure category, last progress/failure time, and whether automatic retry is pending or exhausted. Do not expose raw backend exception text.
- **D-27:** Enable manual retry only for the selected failed or stale cutoff and only when no queued/running work already covers it. Keep explicit all-available rebuild as an operator action, not the page default.
- **D-28:** A status or dispatch error never substitutes stale precompute for governed live data and never blocks unaffected cutoff partitions.

### the agent's Discretion
- Internal helper, record, and task names.
- The exact page-local durable representation for invalidation and pending-follow-up evidence, provided no database schema or shared queue/cache refactor is introduced.
- The exact heartbeat field names and polling cadence, while preserving bounded stale detection and selected-cutoff truthfulness.
- Test decomposition and implementation order, with failing targeted contracts written before production changes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and acceptance
- `.planning/PROJECT.md` — v1.1 goal, business-correctness constraints, and excluded platform work.
- `.planning/REQUIREMENTS.md` — `INC-01`, `INC-02`, and `REC-01`.
- `.planning/ROADMAP.md` — Phase 03 goal and success criteria.
- `.planning/phases/02-exact-cutoff-historical-coverage/02-CONTEXT.md` — locked exact-cutoff, explicit scope, live-fallback, and no-formula-change decisions.
- `.planning/phases/02-exact-cutoff-historical-coverage/02-VERIFICATION.md` — Phase 02 evidence and the resilience items deferred into Phase 03.
- `AGENTS.md` — page-local scope, business display validation, GitNexus impact, MCP evidence, and no-shared-infrastructure constraints.

### Existing implementation
- `backend/app/services/pnl_service.py` — manual-adjustment state changes, dispatch lock, effective run records, stale detection, status payload, and current duplicate handling.
- `backend/app/tasks/pnl_materialize.py` — formal source commit, exact-cutoff precompute task, current batch lifecycle, and persistence dispatch.
- `backend/app/tasks/pnl_by_business_precompute.py` — exact-cutoff payload computation.
- `backend/app/repositories/pnl_repo.py` — available cutoff catalog, cutoff metadata, and exact partition replacement.
- `backend/app/api/routes/pnl.py` — authorized status, selected/all-available rebuild, manual-adjustment, and formal refresh routes.
- `frontend/src/api/contracts.ts` — current selected-cutoff status contract.
- `frontend/src/api/pnlClient.ts` — status and rebuild client boundary.
- `frontend/src/features/pnl/PnlByBusinessPage.tsx` — selected-cutoff status panel and retry interaction.
- `tests/test_pnl_api_contract.py` — primary backend contract and real DuckDB evidence anchor.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_available_pnl_by_business_precompute_cutoffs`: already produces sorted, real same-year month-end targets.
- `_queue_pnl_by_business_precompute_refresh`: already serializes dispatch decisions and records queued/dispatch-failure evidence; Phase 03 must make its overlap handling target-aware.
- `_effective_pnl_by_business_precompute_run_records`: already derives retry-pending and stale states; it can remain the selected-cutoff lifecycle read boundary.
- `_pnl_by_business_precompute_status_payload` and `PnlByBusinessPrecomputeStatusPanel`: already expose serving mode, retry policy, safe errors, source version, and exact selected cutoff.
- Exact partition replacement and source-cutoff guards from Phase 02 are the recovery write boundary and must not be weakened.

### Established Patterns
- Business changes commit independently from best-effort page-read-model refresh, while stale/live-fallback state remains explicit.
- Governance records are append-only lifecycle evidence and effective state is reduced by run id.
- Rebuild targets are canonical, explicit, year-bounded, and isolated by exact cutoff.
- Page queries remain available through governed live fallback whenever precompute is absent or stale.

### Integration Points
- Formal source materialization completion and approved manual-adjustment state changes emit cutoff-local invalidation evidence.
- The page-local dispatch coordinator coalesces pending ranges and launches one residual follow-up after active work.
- The worker records per-cutoff heartbeat/result evidence and continues across independent cutoff failures.
- The selected-cutoff status endpoint reduces invalidation, active run, terminal result, and current partition metadata into one truthful response.

</code_context>

<specifics>
## Specific Ideas

- Use the earliest committed changed date as the cumulative invalidation anchor.
- Keep queued and running jobs immutable; coalesce later events outside those job payloads.
- Preserve every merged trigger in audit evidence even when only one follow-up task is dispatched.
- Keep the page usable through governed live fallback rather than showing old precomputed data or blocking access.

</specifics>

<deferred>
## Deferred Ideas

- Full live-versus-precomputed parity and the cutoff evidence matrix remain Phase 04.
- Long-lived production scheduling that waits for future month-ends remains out of scope.
- Database schema, shared queue/scheduler/cache, authentication, and global frontend-state refactors remain out of scope.
- P1-10 frontend formal aggregation ownership remains a separate owner-decision track.

</deferred>

---

*Phase: 03-incremental-rebuild-and-recovery*
*Context gathered: 2026-07-17*
