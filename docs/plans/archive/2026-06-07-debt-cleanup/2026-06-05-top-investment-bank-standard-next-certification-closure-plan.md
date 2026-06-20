# Top Investment Bank Standard Next Certification Closure Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from flagship frontend-surface readiness to a defensible top investment-bank operating standard for the exact route set that can be proven.

**Architecture:** Treat MOSS as a governed decision workbench, not a styling project. Close one route at a time through source-to-screen traceability, business-contract evidence, golden-sample boundaries, manual review gates, business-owner approval, route-scope classification, and only then final institutional UX hardening.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, local MCP evidence launchers, page contracts, metric dictionary, golden-sample catalog, governance packets, Python readiness scripts, and PowerShell page verification wrappers.

---

## Current Truth

MOSS has not yet fully reached the top investment-bank standard.

Already achieved:

- The seven audited flagship routes are frontend-surface ready: `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Gate H automated accessibility evidence is complete for those seven routes.
- `/ledger-pnl` has a repeatable Gate I evidence lane: MCP trace evidence, direct-record blocker routing, a field-complete dry-run governance candidate, source/golden boundary documentation, and a strict pending business-owner approval checker.
- `/pnl-attribution` has stronger current Gate I readiness than the scorecard says: static readiness passes, catalog/date evidence samples 5/5 configured tables, one direct governance record is ready for audit review, and 20 expanded anchor records are present.

Still blocking a full top-standard claim:

- `/ledger-pnl` is still `evidence-pending`: no written direct PAGE/API governance record from the approved workflow, no supporting expanded lineage closure, no completed manual audit review, no dedicated summary golden sample, and no captured business-owner approval.
- `/pnl-attribution` is not certified: `formal_use_allowed=false`, `closure_approved=false`, `GS-PNL-ATTR-WB-A` is page DTO evidence only, advanced/Campisi surfaces are outside that sample, and business-owner approval remains pending with 11 action items.
- Gate I has not been repeated across the seven-route flagship surface.
- Gate J has not classified or excluded the remaining non-audited business routes.

Until those are closed, use this claim only:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

## Target Standard

A route can be called top investment-bank-grade only when all of this is true:

1. The first screen answers the primary business question, trust state, supporting evidence, and next action.
2. Every displayed decision metric exposes source, date, unit, precision, status, stale/fallback/no-data behavior, and formal/candidate boundary.
3. Every critical value is traced through API response -> adapter/model -> state/selector -> component -> chart/table.
4. MCP metric-contract, lineage, catalog/date, governance, or recorded fallback-risk evidence supports the business claim.
5. Golden-sample scope is explicit and never overused to certify unapproved surfaces.
6. Business-owner approval is captured by a strict checker before closure.
7. Desktop `1440px`, tablet `768px`, and mobile `390px` checks show no fallback route, no permanent loading, no document-level horizontal overflow, and no blocking console errors.
8. Non-audited routes are classified or explicitly excluded so the claim cannot silently expand.

## RALPLAN-DR Summary

### Principles

1. Business correctness outranks visual polish.
2. Only claim the route scope that is proven.
3. Keep governance uncertainty visible until evidence closes it.
4. Certify one route deeply, then scale the workflow.
5. Make every promotion reversible, testable, and reviewable.

### Decision Drivers

1. Evidence authority: MCP evidence, golden samples, and business approvals outrank local inference.
2. Auditability: every displayed number must be explainable from source to screen.
3. Claim discipline: frontend readiness, business-contract certification, and business approval are separate statuses.

### Options Considered

**Option A: Close `/pnl-attribution` Gate I boundary next.**

- Pros: fastest route to a second high-value evidence-backed page; current readiness already has direct record and catalog/date evidence.
- Cons: still cannot certify without manual review and business-owner approval.

**Option B: Finish `/ledger-pnl` real governance write next.**

- Pros: directly attacks the first Gate I blocker.
- Cons: real governance stream write needs workflow authorization and cannot be done casually in this plan lane.

**Option C: Start visual polish immediately.**

- Pros: visible quality improves quickly.
- Cons: does not close the actual top-standard blocker, which is evidence and approval.

**Chosen path:** Option A first, then ledger governance closure when authorized, then Gate I scale-out, Gate J classification, and final UX hardening.

## Task 1: `/pnl-attribution` Gate I Certification Boundary Package

**Purpose:** Update the evidence model so `/pnl-attribution` is no longer shown as `not-started`; it should become `evidence-pending` with exact blockers.

**Files:**

- Create: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Steps:**

1. Record current readiness evidence from `python scripts/codex_page_readiness.py --page-slug pnl-attribution`.
2. Record dry-run governance details from `python scripts/emit_pnl_attribution_governance_record.py`.
3. Record approval status from `python scripts/check_pnl_attribution_business_owner_approval.py`.
4. Capture the exact boundary of `GS-PNL-ATTR-WB-A`: page DTO and `/api/pnl-attribution/volume-rate` only, not full-page, advanced, Campisi, formal PnL overview, or executive overlay certification.
5. Keep `formal_use_allowed=false`, `closure_approved=false`, and business-owner approval pending.
6. Update the scorecard row from `not-started` to `evidence-pending` with blockers.

**Acceptance Criteria:**

- `/pnl-attribution` has a machine-readable Gate I boundary artifact.
- The scorecard accurately reflects strong evidence collection without calling the page certified.
- No metric definition, formal-use flag, golden-sample scope, or approval status is promoted.

**Verification:**

```powershell
python -m json.tool docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json > $null
python -m pytest tests/test_pnl_attribution_governance_record.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
python scripts/codex_page_readiness.py --page-slug pnl-attribution
git diff --check docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json docs/audits/2026-06-05-institutional-frontend-scorecard.md docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md
```

## Task 2: `/ledger-pnl` Governance Closure Lane

**Purpose:** Keep `/ledger-pnl` moving from preflight candidate to auditable direct-record closure without unauthorized writes.

**Files:**

- Inspect: `scripts/emit_ledger_pnl_governance_record.py`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json`
- Modify only with evidence: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Re-run `python scripts/emit_ledger_pnl_governance_record.py` in dry-run mode.
2. Confirm `mode=dry-run`, `record_write_status=not_requested`, `preflight.validation.validation_status=ready_for_audit_review`, and `evidence_scope.writes_governance_records=false`.
3. Keep `python scripts/emit_ledger_pnl_governance_record.py --write` as workflow-authorized only.
4. After any approved write, rerun direct record validation and record whether direct and expanded anchor records exist.
5. Keep candidate metrics `MTR-LPN-001` through `MTR-LPN-003` pending until dedicated summary golden-sample and business-owner review exist.

**Acceptance Criteria:**

- Ledger dry-run remains safe and repeatable.
- Real governance write is not performed from this plan without authorization.
- `/ledger-pnl` remains `evidence-pending` unless written-record validation, manual review, and business approval all close.

**Verification:**

```powershell
python scripts/emit_ledger_pnl_governance_record.py
python scripts/check_ledger_pnl_business_owner_approval.py
python -m pytest tests/test_ledger_pnl_governance_record.py tests/test_ledger_pnl_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
```

## Task 3: Scale Gate I Across Seven Flagship Routes

**Purpose:** Convert the seven-route claim from frontend-surface readiness to business-contract-aware readiness.

**Route order:**

1. `/pnl-attribution`
2. `/ledger-pnl`
3. `/product-category-pnl`
4. `/bond-analysis`
5. `/cross-asset`
6. `/macro-toolkit`
7. `/stock-analysis`

**Per-route steps:**

1. Identify the primary business question.
2. List displayed decision metrics and status markers.
3. Trace API response -> adapter/model -> state/selector -> component -> chart/table.
4. Confirm unit, precision, date, stale/fallback/no-data semantics, null-vs-zero handling, and golden-sample status.
5. Collect MCP metric-contract, lineage, catalog/date, and governance evidence where configured.
6. Classify the route as `business-contract-certified`, `evidence-pending`, or `frontend-only`.
7. Record unavailable MCP servers and fallback evidence explicitly.

**Acceptance Criteria:**

- Every flagship route has a Gate I status row.
- No route is certified from screenshots, component tests, or browser smoke alone.
- Formal, candidate, temporary-exception, and supporting-only evidence remain separated.

## Task 4: Gate J Route-Scope Classification

**Purpose:** Prevent a seven-route frontend claim from being mistaken for whole-system certification.

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Files:**

- Read: `docs/frontend-institutional-standard.md`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Inspect per route: relevant files under `frontend/src/features/` and `frontend/src/test/`

**Per-route steps:**

1. State the single primary business question.
2. Score the route against business trust, first-screen closure, hierarchy, responsive resilience, accessibility, token alignment, and runtime cleanliness.
3. Classify as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
4. Apply only page-local corrections when a route is near closure.
5. Browser verify desktop `1440px`, tablet `768px`, and mobile `390px`.

**Acceptance Criteria:**

- Every named candidate route is scored or explicitly excluded.
- The final claim names the exact covered route set.
- Non-audited routes are not silently included.

## Task 5: Final Institutional UX Hardening

**Purpose:** Add the last visual and interaction layer after evidence gates stop moving.

**Scope:**

- Typography density and hierarchy.
- Token alignment and palette balance.
- Mobile decision readout order.
- Empty, stale, fallback, blocked, no-data, and candidate states.
- Keyboard focus clarity.
- Status cues that are not color-only.
- No overlap or text truncation at `390px`, `768px`, and desktop.

**Rules:**

- Do not add decorative hero sections.
- Do not use marketing-style card stacks.
- Do not change finance formulas.
- Do not hide governance, stale, fallback, no-data, temporary-exception, formal-use, or approval markers.
- Do not rebuild the global design system unless a page-local fix cannot solve the issue.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Browser evidence for every changed route must include:

- desktop `1440px`
- tablet `768px`
- mobile `390px`
- status `200`
- no fallback route
- no permanent busy state
- no document-level horizontal overflow
- no blocking console errors

## Task 6: Final Certification Packet

**Purpose:** Produce the artifact that honestly answers whether MOSS has reached the target.

**Files:**

- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Optional create: `docs/audits/2026-06-05-top-investment-bank-certification-status.md`

**Packet must include:**

- Certified route set.
- Frontend-ready route set.
- Evidence-pending route set.
- Out-of-scope route set.
- MCP availability and fallback-risk notes.
- Golden-sample status per critical metric group.
- Business-owner approval status.
- Verification commands and results.
- Screenshot and measurement artifact paths.
- Remaining risks and next owner lane.

**Final claim rule:**

Only use a top investment-bank certification claim for the exact route set where Gate I and Gate J are both closed with evidence. Until then, keep the current truthful wording:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

## Immediate Next Execution Slice

Start with Task 1.

Expected output:

1. `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
2. Updated `/pnl-attribution` business-contract status in `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
3. Updated Gate I next-action text in `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
4. Verification results from JSON parsing, targeted Python tests, page readiness, and `git diff --check`

Do not begin visual polish before this slice, because the current limiting factor is evidence closure, not surface styling.
