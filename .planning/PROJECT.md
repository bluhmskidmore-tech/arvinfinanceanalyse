# MOSS V3

## What This Is

MOSS V3 is a business analysis system for finance workflows. It turns governed data and formal finance outputs into page-level conclusions with explicit metric definitions, source lineage, report dates, and validation evidence.

## Core Value

Business metrics and governed pages can be released with traceable evidence, green gates, and explicit development security boundaries.

## Current State

- v1.0 Audit Remediation passed its milestone audit with 1 phase, 1 plan, and 6 of 6 requirements verified.
- The verified snapshot closes release-gate, page-contract, frontend finance-boundary, Dashboard fallback, development security-boundary, and CI evidence gaps.
- The v1.0 evidence does not certify unrelated later commits or current dirty-worktree changes; those changes need their own review and validation.

## Requirements

### Validated

- Release gates use explicit dev/test header trust and pass their targeted checks — v1.0.
- Live routes `/agent`, `/balance-movement-analysis`, and `/liability-analytics` have formal page contracts — v1.0.
- Frontend finance calculations remain guarded, with only the documented display-only DV01 label exception — v1.0.
- Dashboard first-screen placeholder deltas fall back to the governed read-chain label — v1.0.
- Macro refresh, agent-run ownership, GitNexus repository scope, and MCP launch boundaries have targeted controls — v1.0.
- CI and the backend release gate include the release-critical build, page-contract, finance-boundary, and MCP checks — v1.0.

### Active

No requirements are active at the milestone boundary. The next milestone must define a fresh, page-scoped requirement set before implementation.

### Out of Scope

- Full production JWT or SSO rollout — v1.0 hardened development-compatible boundaries only.
- Database schema changes — no audit-remediation blocker required them.
- Global frontend state or API-client refactors — page and workflow closure takes priority.
- Historical GSD reconstruction — only the current remediation evidence chain is maintained.

## Next Milestone Goals

- Define the next business-page milestone through `/gsd-new-milestone` before adding implementation scope.
- Start from one primary business question and close its loading, empty, partial, stale/fallback, and failure states end to end.
- The current candidate is the `/reports` workbench home, subject to requirement confirmation in the next milestone workflow.

## Context

- This is a brownfield Python and TypeScript system with formal metric, page-contract, lineage, data-catalog, and release-gate conventions.
- Business metric correctness, page-level closure, traceability, and minimal reviewable changes are the current priorities.
- Accepted non-blocking v1.0 debt includes existing frontend test warnings, an existing Vite chunking warning, production JWT/SSO remaining out of scope, and intentionally unreconstructed historical GSD artifacts.

## Constraints

- **Business correctness:** Do not guess metric definitions, units, dates, or lineage when evidence is missing.
- **Scope:** Fix one page or workflow at a time and avoid unrelated refactors.
- **Validation:** Use the narrowest relevant checks first and widen only when a shared boundary is crossed.
- **Architecture:** Do not modify schemas, auth frameworks, shared infrastructure, or app-wide state without direct root-cause evidence and explicit scope.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gate dev/test header trust behind `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1`. | Preserve development compatibility without implicit identity trust. | Good — verified in v1.0. |
| Give live routes formal page contracts instead of temporary exceptions. | Keep business questions, data chains, and state behavior auditable. | Good — verified in v1.0. |
| Allow only a file- and snippet-scoped display-only DV01 exception. | Keep formal finance calculations out of frontend code. | Good — verified in v1.0. |
| Resolve GitNexus MCP commands through the project launcher and constrain repository roots. | Prevent request-controlled command and path expansion. | Good — verified in v1.0. |
| Keep future work page-scoped and evidence-led. | Business closure is more valuable than broad platform refactoring. | Pending — apply to the next milestone. |

---
*Last updated: 2026-07-15 after v1.0 milestone review*
