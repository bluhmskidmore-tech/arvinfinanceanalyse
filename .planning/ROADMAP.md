# Roadmap: MOSS V3 Audit Remediation

## Overview

This minimal GSD roadmap restores audit evidence for the current remediation effort only. It does not reconstruct historical milestones.

## v1.0 Audit Remediation

**Milestone Goal:** Move the system from "functionally mostly complete but release closure is unstable" to "verifiable, releasable, and traceable."
**Definition of Done:** Release gates are green, live routes have formal page contracts, frontend finance boundaries are explicit, dashboard first-screen metric fallbacks preserve provenance, security-sensitive development boundaries are hardened, CI includes the release-critical checks, and GSD evidence exists for this remediation phase.

## Phases

- [x] **Phase 01: Audit Remediation** - Close the current audit blockers and restore release evidence.

## Phase Details

### Phase 01: Audit Remediation
**Goal**: Resolve the audit blockers called out in the system-wide milestone audit and restore a minimal evidence chain for release review.
**Depends on**: Nothing.
**Requirements**: [REQ-AUDIT-001, REQ-AUDIT-002, REQ-AUDIT-003, REQ-AUDIT-004, REQ-AUDIT-005, REQ-AUDIT-006]
**Success Criteria** (what must be TRUE):
  1. Backend release suite uses explicit dev/test header trust and passes.
  2. Live routes `/agent`, `/balance-movement-analysis`, and `/liability-analytics` have formal `PAGE-*` contracts.
  3. Frontend finance-boundary guard allows only the documented display-only DV01 label exception.
  4. Dashboard home hero delta treats placeholder values as missing and falls back to the read-chain label.
  5. Macro refresh, agent run lookup, and GitNexus/MCP launch boundaries have targeted authorization/path tests.
  6. CI and backend release gate include build/page/finance/MCP coverage and GSD evidence is present.
**Plans**: 1 plan

Plans:
- [x] 01-01: Implement audit remediation plan and verification gates.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 01. Audit Remediation | 1/1 | Complete | 2026-05-11 |
