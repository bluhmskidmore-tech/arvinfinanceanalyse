# Requirements: MOSS V3 Audit Remediation

**Defined:** 2026-05-11
**Core Value:** Business metrics and governed pages can be released with traceable evidence, green gates, and explicit development security boundaries.

## v1.0 Requirements

### Release Gates

- [x] **REQ-AUDIT-001**: Restore backend release gate correctness by making Balance Analysis current-user role behavior consistent with status writes and by trusting header identity only through an explicit dev/test switch.
- [x] **REQ-AUDIT-002**: Add formal page contracts for live routes `/agent`, `/balance-movement-analysis`, and `/liability-analytics` without downgrading them to temporary exceptions.
- [x] **REQ-AUDIT-003**: Keep formal finance calculations out of frontend code while allowing only the documented dashboard cockpit DV01 display-only label exception.
- [x] **REQ-AUDIT-004**: Preserve Dashboard first-screen metric provenance by treating placeholder delta labels as missing and falling back to the read-chain label.
- [x] **REQ-AUDIT-005**: Harden development-compatible security boundaries for auth header trust, macro refresh authorization, agent run ownership, GitNexus repo roots, and MCP command launch.
- [x] **REQ-AUDIT-006**: Add CI/release-gate coverage for frontend build, page-contract completeness, frontend finance boundary, and project MCP self-checks.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full production JWT or SSO rollout | The remediation target is development-compatible hardening, not an auth platform rebuild. |
| Database schema changes | The audit blockers are release gates, contracts, frontend semantics, security boundaries, and evidence. |
| Global frontend state or API client refactor | The current priority is page/workflow closure with minimal reviewable changes. |
| Historical GSD reconstruction | Only current audit findings and the current fix phase are documented. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-AUDIT-001 | Phase 01 | Complete |
| REQ-AUDIT-002 | Phase 01 | Complete |
| REQ-AUDIT-003 | Phase 01 | Complete |
| REQ-AUDIT-004 | Phase 01 | Complete |
| REQ-AUDIT-005 | Phase 01 | Complete |
| REQ-AUDIT-006 | Phase 01 | Complete |

**Coverage:**
- v1 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-05-11*
*Last updated: 2026-05-11 after audit remediation implementation*
