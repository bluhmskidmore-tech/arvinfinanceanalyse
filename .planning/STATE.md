---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: PnL Historical Cutoff Precompute Coverage
status: paused-pending-adoption-decision
stopped_at: Merge-back complete — codex/V1-merge-dateclosure (aa9785aba) landed on codex/V1 as merge 5a3878beb; targeted regression green on the exact merge tree
last_updated: "2026-07-20T09:50:00.000Z"
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

### Next actions (updated 2026-07-20 after merge-back landed)

1. **DONE (staging):** candidate line `codex/balance-analysis-date-closure` merged --no-ff into integration branch `codex/V1-merge-dateclosure` (`feadfc932`, based on V1 tip `9f80fb999`; worktree `F:/MOSS-V3-worktrees/v1-merge-dateclosure`). 10 conflicts resolved: mainline naming/contract precedence, candidate semantic fixes preserved; one latent auto-merge double-division (sub-1% yield /100 twice) corrected to mainline `raw_scale="percent"` form.
2. **SUPERSEDED:** side branch `codex/pnl-bridge-date-closure` (`f70a536c1`) is NOT to be merged — mainline `5a25a4531` already landed equivalent bridge date metadata with the opposite PAGE-BRIDGE-001 ruling (curve trade dates are never promoted to `fallback_date`; `date_basis` stays empty). Keep the branch as reference only.
3. **DONE (merge-back):** `codex/V1-merge-dateclosure` (tip `aa9785aba`, includes the ADB preview test copy alignment) merged --no-ff into `codex/V1` as `5a3878beb` (tree `672aa867b`, matches merge-tree preflight; 27 files, zero overlap with dirty worktree files). Evidence: backend `tests/test_boundary_surface_inventory.py` + `tests/test_yield_curve_term_structure_api.py` + `tests/test_frontend_playwright_smoke_scaffold.py` = 47 passed on the pure merge tree (temp verify worktree); frontend 8 candidate-line test files = 216 passed on the identical frontend tree (integration worktree). Operational notes carried in: monthly OA playwright smoke hard-fails without a state server; curve partial-missing reports `vendor_status=vendor_unavailable` (fail-visible).
4. Integration branch/worktree `v1-merge-dateclosure` is now fully absorbed; it can be retired at the next worktree inventory (an uncommitted redundant `macro_toolkit.py` seam re-add from a parallel session remains there — content already on V1 via `ed7a8f544`; safe to discard, do not commit).
5. Worktree/branch cleanup only after an inventory; no bulk deletion.
6. Phase 03/04 adoption remains a business decision — not current code work.

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

- Push `codex/V1` to origin when explicitly requested (local is 35+ commits ahead; publishing withheld pending an explicit instruction).
- Future inventory pass for the remaining ~136 needs-confirm branches (recovery/meta-status/04-25 batches); no bulk deletion.

### Decisions recorded 2026-07-20

- **Phase 03/04 NOT adopted now** (owner direction in-session): monthly PnL cadence with no routine historical backtrace makes automatic cascade rebuild a low-frequency protection mechanism, not current work. `codex/phase-03-incremental-rebuild` stays reference-only; INC-01/INC-02/REC-01/PAR-01/PAR-02 stay unchecked; revisit only if the business rule changes.
- **Cleanup executed per inventory (no bulk deletion):** retired 4 completed worktrees (`v1-merge-dateclosure`, `gs-bal-workbook-a-recapture`, `lazy-dispatch-proxy-fn`, `pnl-bridge-date-closure`; the superseded `codex/pnl-bridge-date-closure` branch itself is kept as reference) and deleted 21 fully-merged branches (verified `rev-list --count codex/V1..branch == 0` each). `codex/phase-02-exact-cutoff` kept as the Phase 02 naming anchor.

### Landed 2026-07-20 (subagent fixes, reviewed and merged)

- **GS-BAL-WORKBOOK-A recapture** (`e7f163896`, merged `5f7396fa0`): 58 leaf values updated for the balance H-2 `currency_basis` remediation (USD rows now converted at 7.2 CNY mid; e.g. `bond_assets_excluding_issue` 0.01000000 -> 0.07200000); owner recapture record added to approval.md/assertions.md; full golden suite 33/33 green.
- **Lazy dispatch proxy attribute delegation** (`67c7ca151`): 9 actor proxies across pnl/balance/bond/accounting/macro/product-category/source-preview now delegate `__getattr__` to the lazily imported actor, restoring `.fn` access and monkeypatch compatibility; fixes the two pre-existing refresh-503 contract failures; 40 tests green pre-merge, 12 re-verified post-merge on codex/V1.

### Blockers/Concerns

- The v1.0 audit certifies the historical remediation snapshot, not unrelated later commits or current dirty-worktree changes.
- Existing accepted frontend warnings and production JWT/SSO scope remain for future focused work.
- The shared worktree remains dirty; v1.1 commits must stage only page-scoped planning and implementation hunks.
- Planning-state drift risk: 72 registered worktrees and multiple long-lived branches; `codex/V1` is the single planning-state write point going forward.

## Session Continuity

**Last session:** 2026-07-20T09:50:00.000Z
**Stopped at:** Merge-back landed — `codex/V1` = `5a3878beb` (merge of `aa9785aba`); targeted backend+frontend regression green on the exact merge tree; integration branch ready for retirement after inventory
**Resume file:** .planning/forensics/report-20260719-055254.md
