# Roadmap: MOSS V3

## Milestones

- [x] **v1.0 Audit Remediation** - Phase 01, 1/1 plan; completed and verified 2026-05-11, archived 2026-07-15. See [archived roadmap](milestones/v1.0-ROADMAP.md).
- [ ] **v1.1 PnL Historical Cutoff Precompute Coverage** - Phases 02-04; roadmap defined 2026-07-15.

## Current Milestone

### v1.1 PnL Historical Cutoff Precompute Coverage

**Milestone Goal:** Make every available 2026 month-end cutoff on `/pnl-by-business` fast and auditable without changing any governed PnL formula.

**Definition of Done:** Every available 2026 month-end has an independent exact-cutoff precompute partition; the page reports the selected cutoff's own precompute or governed live-fallback state; affected and later cumulative cutoffs rebuild without duplicate work; failures remain isolated and recoverable; and live-versus-precomputed parity is evidenced for every governed page metric and diagnostic.

## Phases

- [ ] **Phase 02: Exact-Cutoff Historical Coverage** - Materialize all available 2026 month-end partitions and expose exact selected-cutoff state.
- [ ] **Phase 03: Incremental Rebuild and Recovery** - Rebuild only affected cumulative cutoffs, coalesce overlap, and isolate failures.
- [ ] **Phase 04: Exact Parity and Audit Evidence** - Prove governed live-versus-precomputed equality and publish the cutoff evidence matrix.

## Phase Details

### Phase 02: Exact-Cutoff Historical Coverage

**Goal:** Give `/pnl-by-business` independent precompute coverage and truthful state resolution for every available 2026 month-end cutoff.

**Depends on:** Phase 01 (v1.0 complete).

**Requirements:** [COV-01, COV-02, COV-03]

**Success Criteria** (what must be TRUE):

1. An authorized operator can run one year-bounded build that creates exactly one independent partition for every available 2026 month-end, and rerunning it does not create duplicate partitions.
2. Selecting any available 2026 month-end on `/pnl-by-business` resolves data only for that exact cutoff and never inherits a later cutoff's partition or state.
3. The page identifies whether the exact selected cutoff is current/precomputed or is being served through the governed live fallback.

**Plans:** TBD

### Phase 03: Incremental Rebuild and Recovery

**Goal:** Keep historical partitions current with bounded cumulative invalidation, coalesced refresh work, and per-cutoff recovery.

**Depends on:** Phase 02.

**Requirements:** [INC-01, INC-02, REC-01]

**Success Criteria** (what must be TRUE):

1. A governed source or approved manual-adjustment change at a cutoff queues that cutoff and every later cumulative cutoff while earlier current partitions remain untouched and available.
2. When automatic refresh requests overlap, each affected cutoff has at most one queued follow-up behind its running build.
3. A failed or stale cutoff remains visibly identified and can be retried independently while other current cutoff partitions continue serving normally.

**Plans:** TBD

### Phase 04: Exact Parity and Audit Evidence

**Goal:** Demonstrate exact governed equivalence between live and precomputed page payloads and leave reviewable cutoff-level evidence.

**Depends on:** Phase 03.

**Requirements:** [PAR-01, PAR-02]

**Success Criteria** (what must be TRUE):

1. For every tested cutoff, monthly and analysis payloads from the precomputed path match the governed live path exactly for PnL, ADB, current balance, yield, FTP, currency grouping, parent summaries, and reconciliation diagnostics.
2. Reviewers can inspect a cutoff coverage/parity matrix that records parity outcome, source version, rule version, record count, and measured elapsed time for every tested cutoff.

**Plans:** TBD

## Progress

| Phase | Requirements | Plans Complete | Status | Completed |
|-------|--------------|----------------|--------|-----------|
| 02. Exact-Cutoff Historical Coverage | 3 | 0/TBD | Not started | - |
| 03. Incremental Rebuild and Recovery | 3 | 0/TBD | Not started | - |
| 04. Exact Parity and Audit Evidence | 2 | 0/TBD | Not started | - |
