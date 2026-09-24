# MOSS V3

## What This Is

MOSS V3 is a business analysis system for finance workflows. It turns governed data and formal finance outputs into page-level conclusions with explicit metric definitions, source lineage, report dates, and validation evidence.

## Core Value

Business metrics and governed pages can be released with traceable evidence, green gates, and explicit development security boundaries.

## Current Milestone: v1.1 PnL Historical Cutoff Precompute Coverage

**Goal:** Make every available 2026 month-end cutoff on `/pnl-by-business` fast and auditable without changing any governed PnL formula.

**Target features:**
- Materialize an independent precompute partition for every available 2026 month-end cutoff.
- Rebuild only the affected cutoff and subsequent cumulative cutoffs after a governed source or manual-adjustment change.
- Prove exact live-versus-precomputed parity for PnL, ADB, yield, FTP, currency grouping, and parent summaries.
- Keep per-cutoff failure isolation and the existing governed live fallback.

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

- [ ] Users can select any available 2026 month-end cutoff and see whether that exact cutoff is precomputed or using the governed live fallback.
- [ ] Operators can materialize all available month-end cutoffs without duplicate partitions or overlapping active jobs.
- [ ] A governed source or approved manual-adjustment change rebuilds the affected cutoff and all later cumulative cutoffs only.
- [ ] Live and precomputed payloads reconcile exactly for the page's governed business metrics and diagnostics.
- [ ] One cutoff's build failure remains visible and recoverable without invalidating other current cutoffs.

### Out of Scope

- Full production JWT or SSO rollout — v1.0 hardened development-compatible boundaries only.
- Database schema changes — no audit-remediation blocker required them.
- Global frontend state or API-client refactors — page and workflow closure takes priority.
- Historical GSD reconstruction — only the current remediation evidence chain is maintained.

## Next Milestone Goals

- Close historical month-end precompute coverage for `/pnl-by-business` before expanding leadership-analysis features.
- Preserve the page contract, governed formulas, and exact selected-cutoff semantics established in `d45ec9fb4`.
- Produce a cutoff coverage matrix, exact-parity evidence, and a measured latency baseline.

## Context

- This is a brownfield Python and TypeScript system with formal metric, page-contract, lineage, data-catalog, and release-gate conventions.
- Business metric correctness, page-level closure, traceability, and minimal reviewable changes are the current priorities.
- Runtime evidence at milestone start shows `2026-06-30` current/precomputed while `2026-05-31` is correctly served through live fallback; historical coverage is incomplete but numerically safe.
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

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Move invalidated requirements to Out of Scope with a reason.
2. Move verified requirements to Validated with phase evidence.
3. Add newly discovered requirements to Active.
4. Record decisions that constrain later phases.
5. Recheck that the project description and core value remain accurate.

**After each milestone:**
1. Review all requirement sections.
2. Reconfirm the core value.
3. Audit Out of Scope decisions.
4. Update context with current runtime and validation evidence.

---
*Last updated: 2026-07-15 after starting v1.1 historical cutoff precompute coverage*
