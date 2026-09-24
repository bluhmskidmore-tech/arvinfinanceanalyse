---
phase: "02"
slug: exact-cutoff-historical-coverage
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-16
---

# Phase 02 - Security

> Per-phase security contract for exact-cutoff historical PnL coverage.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| HTTP caller -> PnL routes | Authenticated status reads and operator-triggered rebuild requests enter the system. | User identity, permission scope, `year`, `as_of_date`, `scope` |
| Route/service -> repository target selection | The service converts an authorized request into a bounded set of formal source cutoffs. | Formal report dates and normalized target cutoffs |
| Queue/worker -> DuckDB writer | The batch worker validates exact source resolution and invokes cutoff-specific persistence under one writer lock. | Target cutoffs, computed payloads, source lineage |
| Worker -> governance status | Batch lifecycle records are exposed to readers only for exact target membership. | Run status, target dates, per-cutoff result metadata |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation and Evidence | Status |
|-----------|----------|-----------|-------------|-------------------------|--------|
| T-02-01 | Elevation of Privilege | PnL precompute status/rebuild routes | mitigate | Status requires `pnl:read`, while rebuild requires `pnl_by_business.adjustment:write` before service lookup: `backend/app/api/routes/pnl.py:19-25`, `backend/app/api/routes/pnl.py:229-264`, `backend/app/api/routes/pnl.py:427-433`. Runtime route proof: `tests/test_pnl_api_contract.py:4105-4190`; mutation denial contract: `tests/test_write_route_auth_contract.py:31-108`. | closed |
| T-02-02 | Tampering | Request and worker input boundaries | mitigate | Route and direct-call boundaries admit only `selected`/`all_available`, years 2000-2100, canonical calendar dates, same-year targets, actual month-ends, and valid parameter combinations: `backend/app/api/routes/pnl.py:245-264`, `backend/app/services/pnl_service.py:2008-2031`, `backend/app/services/pnl_service.py:2288-2307`, `backend/app/tasks/pnl_materialize.py:147-179`, `backend/app/tasks/pnl_materialize.py:302-327`. Tests: `tests/test_pnl_api_contract.py:3763-3826`. | closed |
| T-02-03 | Denial of Service / Tampering | `all_available` target enumeration | mitigate | Targets come only from distinct dates present in formal PnL fact tables, then are filtered to canonical month-ends in the requested year, de-duplicated, sorted, and rejected when empty. No calendar range is generated and only one bounded batch is dispatched: `backend/app/repositories/pnl_repo.py:71-93`, `backend/app/services/pnl_service.py:2024-2045`, `backend/app/services/pnl_service.py:2310-2329`. Tests: `tests/test_pnl_api_contract.py:3659-3751`. | closed |
| T-02-04 | Tampering / Race Condition | Batch worker and exact-partition persistence | mitigate | One writer lock encloses the whole batch. Every cutoff receives an in-lock exact-source preflight and returned-cutoff verification. Persistence is task-write scoped and transactionally replaces only `(year, as_of_date)`: `backend/app/tasks/pnl_materialize.py:166-249`, `backend/app/repositories/pnl_repo.py:530-590`. Lock, pre-write drift, idempotence, and partition-isolation tests: `tests/test_pnl_api_contract.py:3829-3995`. Phase 02 made no schema or shared-framework change. | closed |

---

## Verification Evidence

| Check | Result |
|-------|--------|
| Focused exact-cutoff security contracts | 21 passed, 132 deselected |
| Write-route authorization contracts | 48 passed |
| Registered threats | 4 total, 4 closed, 0 open |
| Summary threat flags | No unregistered threat flags |

The deferred Phase 03 items (cross-scope active-job de-duplication, worker heartbeat/progress, and actor time limits) are runtime-resilience follow-ups. They do not weaken a registered Phase 02 control and are not Phase 02 blockers.

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-16 | 4 | 4 | 0 | Codex (`gsd-security-auditor`) |

---

## Sign-Off

- [x] All threats have a disposition
- [x] Accepted risks are documented
- [x] `threats_open: 0` confirmed
- [x] `status: verified` confirmed

**Approval:** verified 2026-07-16
