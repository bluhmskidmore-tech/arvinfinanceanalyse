---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: PnL Historical Cutoff Precompute Coverage
status: paused-pending-adoption-decision
stopped_at: Candidate audit line merged into integration branch codex/V1-merge-dateclosure; final merge-back to codex/V1 pending clean window
last_updated: "2026-07-20T09:00:00.000Z"
last_activity: 2026-07-20
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 3
  completed_plans: 1
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-15 for v1.1)

**Core value:** Business metrics and governed pages can be released with traceable evidence, green gates, and explicit development security boundaries.
**Current focus:** Mainline reconciliation (not Phase 03)

## Current Position

**Milestone:** v1.1 PnL Historical Cutoff Precompute Coverage
**Phase:** 03/04 — DEFERRED per 2026-07-19 forensic reconciliation (see `.planning/forensics/report-20260719-055254.md` and the Phase 03/04 status note in ROADMAP.md)
**Status:** Phase 03 is technically complete on side branch `codex/phase-03-incremental-rebuild` but is NOT adopted by current business and NOT merged into `codex/V1`. It is preserved as a historical-traceability capability candidate. Do not re-plan or re-execute Phase 03 as new work.
**Last Activity:** 2026-07-19
**Last Activity Description:** Round-3 Task 3 closed soft bridge quality-merge test gaps and reconciled planning STATE so completed Round-2/Round-3 meta work is no longer listed as next code focus.

### Completed (recent — do not re-open as next code work)

- **PnL bridge backend date/fallback metadata closure** — complete (Round-2): requested/resolved/as-of/fallback dates; merge latest_snapshot severity into final `quality_flag`.
- **Yield-curve result_meta date provenance** — complete (Round-3 Task 1).
- **PnL Bridge first-screen meta banner** — complete (Round-3 Task 2).
- **PnL bridge quality-merge test harden + STATE sync** — complete (Round-3 Task 3).

### Next actions (updated 2026-07-20 after isolated-worktree merge)

1. **DONE (staging):** candidate line `codex/balance-analysis-date-closure` merged --no-ff into integration branch `codex/V1-merge-dateclosure` (HEAD `feadfc932`, based on V1 tip `9f80fb999`; worktree `F:/MOSS-V3-worktrees/v1-merge-dateclosure`). 10 conflicts resolved: mainline naming/contract precedence, candidate semantic fixes preserved; one latent auto-merge double-division (sub-1% yield /100 twice) corrected to mainline `raw_scale="percent"` form.
2. **SUPERSEDED:** side branch `codex/pnl-bridge-date-closure` (`f70a536c1`) is NOT to be merged — mainline `5a25a4531` already landed equivalent bridge date metadata with the opposite PAGE-BRIDGE-001 ruling (curve trade dates are never promoted to `fallback_date`; `date_basis` stays empty). Keep the branch as reference only.
3. **PENDING:** merge-back `codex/V1-merge-dateclosure` into `codex/V1` at the next clean-worktree window; V1 has advanced past `9f80fb999`, so re-run merge-tree preflight for the delta before merging.
4. Worktree/branch cleanup only after an inventory; no bulk deletion.
5. Phase 03/04 adoption remains a business decision — not current code work.

## Performance Metrics

- Total plans completed: 2
- Tasks completed: 6
- Timeline: completed and verified 2026-05-11; final evidence snapshot recorded 2026-05-16; archived 2026-07-15
- Execution time and model mix: not recorded

## Accumulated Context

### Decisions

- Dev/test header trust requires an explicit environment switch.
- Live routes use formal page contracts instead of temporary exceptions.
- Frontend finance logic remains guarded; the DV01 exception is display-only and narrowly scoped.
- GitNexus repository roots and MCP launch commands remain project-controlled.

### Pending Todos

- Decide whether the business adopts the Phase 03/04 side-branch capability; until then keep INC-01/INC-02/REC-01/PAR-01/PAR-02 unchecked.
- Merge-back `codex/V1-merge-dateclosure` (`feadfc932`) into `codex/V1` after re-preflighting the post-`9f80fb999` delta.
- Operational note for the merge-back: monthly OA playwright smoke now hard-fails without a state server (candidate-line intent); curve partial-missing now reports `vendor_status=vendor_unavailable` (fail-visible).

### Blockers/Concerns

- The v1.0 audit certifies the historical remediation snapshot, not unrelated later commits or current dirty-worktree changes.
- Existing accepted frontend warnings and production JWT/SSO scope remain for future focused work.
- The shared worktree remains dirty; v1.1 commits must stage only page-scoped planning and implementation hunks.
- Planning-state drift risk: 72 registered worktrees and multiple long-lived branches; `codex/V1` is the single planning-state write point going forward.

## Session Continuity

**Last session:** 2026-07-20T09:00:00.000Z
**Stopped at:** Candidate audit line staged on `codex/V1-merge-dateclosure` (`feadfc932`); post-merge regression running; merge-back to `codex/V1` pending clean window + delta preflight
**Resume file:** .planning/forensics/report-20260719-055254.md
