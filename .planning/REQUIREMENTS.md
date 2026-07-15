# Requirements: MOSS V3 v1.1 PnL Historical Cutoff Precompute Coverage

**Defined:** 2026-07-15
**Core Value:** Business metrics and governed pages can be released with traceable evidence, green gates, and explicit development security boundaries.

## v1.1 Requirements

### Cutoff Coverage

- [ ] **COV-01**: A user selecting any available 2026 month-end cutoff can receive a precompute partition resolved to that exact cutoff.
- [ ] **COV-02**: A user can see the exact selected cutoff's current/precomputed or governed live-fallback status without inheriting a later cutoff's state.
- [ ] **COV-03**: An authorized operator can request one bounded build that covers every available month-end cutoff in the selected year without creating duplicate partitions.

### Incremental Rebuild

- [ ] **INC-01**: A governed source or approved manual-adjustment change at a cutoff queues rebuilds for that cutoff and all later cumulative cutoffs while leaving earlier current partitions untouched.
- [ ] **INC-02**: Overlapping automatic refresh requests coalesce so each affected cutoff has at most one queued follow-up behind a running build.

### Exact Parity

- [ ] **PAR-01**: Monthly and analysis payloads produced by the precomputed path match the governed live path exactly for PnL, ADB, current balance, yield, FTP, currency grouping, parent summaries, and reconciliation diagnostics.
- [ ] **PAR-02**: Validation produces an auditable cutoff coverage/parity matrix with source version, rule version, record count, and measured elapsed time for every tested cutoff.

### Recovery

- [ ] **REC-01**: A failed or stale cutoff build remains visible and independently recoverable while other current cutoff partitions continue serving normally.

## Future Requirements

### Leadership Analysis

- **LEAD-01**: Leadership users receive expanded narrative attribution and anomaly explanations after historical compute coverage is closed.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changes to governed PnL, ADB, yield, FTP, VAT, FX, or classification formulas | This milestone changes compute coverage and evidence only. |
| Database schema changes | The existing `(year, as_of_date)` partition boundary already supports multiple cutoffs. |
| Shared queue, scheduler, cache, or authentication framework refactors | Page-local orchestration is sufficient and keeps blast radius reviewable. |
| Precomputing non-month-end dates | The page's management and reporting workflow is month-end based. |
| Automatic production scheduling policy | First close deterministic build, invalidation, parity, and recovery behavior. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COV-01 | Phase 02 | Pending |
| COV-02 | Phase 02 | Pending |
| COV-03 | Phase 02 | Pending |
| INC-01 | Phase 03 | Pending |
| INC-02 | Phase 03 | Pending |
| PAR-01 | Phase 04 | Pending |
| PAR-02 | Phase 04 | Pending |
| REC-01 | Phase 03 | Pending |

**Coverage:**
- v1.1 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-07-15*
*Last updated: 2026-07-15 after roadmap creation*
