# Phase 02: Exact-Cutoff Historical Coverage - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning
**Source:** Approved v1.1 requirements plus runtime inspection

<domain>
## Phase Boundary

Provide independent, exact-cutoff precompute coverage for every available 2026 month-end on `/pnl-by-business`, together with a bounded authorized rebuild path and truthful selected-cutoff status. Do not change any governed PnL, ADB, balance, yield, FTP, VAT, FX, or classification formula.

</domain>

<decisions>
## Implementation Decisions

### Cutoff coverage
- Treat the repository's available union report dates for the selected year as the authoritative cutoff set; for the current 2026 dataset that set is `2026-01-31`, `2026-02-28`, `2026-03-31`, `2026-04-30`, `2026-05-31`, and `2026-06-30`.
- Preserve one independent `(year, as_of_date)` partition per cutoff and replace that exact partition idempotently on rerun.
- The current runtime gap is stale historical source fingerprints: January through May are v3 while June is v4. Phase 02 must rebuild all available cutoffs to the current fingerprint.

### Operator contract
- Preserve the existing selected-cutoff rebuild behavior as the default.
- Add an explicit year-bounded rebuild scope for all available cutoffs; do not overload a missing `as_of_date` with ambiguous semantics.
- Reuse the existing PnL write authorization and page-local task lifecycle. Do not change authentication, database schema, or shared queue/cache infrastructure.

### Selected-cutoff truthfulness
- Status resolution must continue to use the selected cutoff's exact effective `period_end`; it must not inherit a later cutoff's run or metadata.
- When the exact cutoff is absent or stale, report governed `live_fallback`; when its source and rule fingerprints are current, report `precomputed`.
- Existing page status presentation may be extended only as needed to expose year coverage; no visual redesign is in this phase.

### Testing and evidence
- Use test-driven development: add failing contract/task tests before production changes.
- Prove that one all-cutoff request targets the six sorted 2026 cutoffs and that rerunning replaces partitions rather than duplicating them.
- Keep Phase 03 incremental invalidation/coalescing and Phase 04 live-versus-precomputed parity matrix out of this phase.

### the agent's Discretion
- Exact internal helper and task names.
- Whether the year coverage summary is returned by the rebuild response, status response, or both, provided selected-cutoff truthfulness and bounded all-cutoff execution remain explicit.

</decisions>

<canonical_refs>
## Canonical References

### Scope and acceptance
- `.planning/ROADMAP.md` — Phase 02 goal and success criteria.
- `.planning/REQUIREMENTS.md` — COV-01, COV-02, and COV-03.
- `AGENTS.md` — page-local business correctness, impact, validation, and scope rules.

### Existing implementation
- `backend/app/tasks/pnl_by_business_precompute.py` — exact-cutoff payload materialization and partition replacement.
- `backend/app/tasks/pnl_materialize.py` — current single-cutoff read-model task lifecycle.
- `backend/app/services/pnl_service.py` — selected-cutoff status and controlled dispatch contract.
- `backend/app/api/routes/pnl.py` — authorized status and rebuild endpoints.
- `tests/test_pnl_api_contract.py` — backend contract and read-model tests.

</canonical_refs>

<specifics>
## Specific Ideas

- Use an explicit rebuild scope such as `selected` versus `all_available`.
- Keep the set bounded by actual available dates in the requested year; never manufacture missing calendar month-ends.
- A batch result should name every targeted cutoff and its outcome so a reviewer can see what the request covered.

</specifics>

<deferred>
## Deferred Ideas

- Automatic source/manual-adjustment propagation from an affected cutoff to later cutoffs belongs to Phase 03.
- Full metric parity and cutoff evidence matrix belong to Phase 04.

</deferred>

---

*Phase: 02-exact-cutoff-historical-coverage*
*Context gathered: 2026-07-15 from approved scope and runtime evidence*
