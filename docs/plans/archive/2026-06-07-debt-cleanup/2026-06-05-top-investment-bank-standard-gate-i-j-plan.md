# Top Investment Bank Standard Gate I/J Implementation Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `using-superpowers`, `executing-plans`, `finance-data-quality`, `karpathy-guidelines`, and `verification-before-completion` to implement this plan task-by-task.

**Goal:** Move MOSS from seven-route frontend-surface flagship readiness to a defensible top investment-bank standard by closing business-contract evidence and route-scope boundaries.

**Architecture:** Treat the current seven flagship pages as the reference surface, then add an evidence layer above them. Every route must be classified as `frontend-ready`, `business-contract-certified`, `evidence-pending`, or `out-of-scope`; metric and lineage claims require MCP or explicit fallback-risk documentation.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser smoke, page contracts, metric dictionary, golden-sample catalog, local MCP evidence servers, governance docs, and existing MOSS page-readiness scripts.

---

## Current Verdict

The system has **not yet fully achieved** the top investment-bank standard.

What is already strong:

- The seven audited flagship routes are page-surface ready under `docs/frontend-institutional-standard.md`.
- Gate H accessibility is now automated at `4/4` for the seven-route surface.
- Six routes are scored `28/28`; `/product-category-pnl` is `27/28` because liability fallback behavior still needs explicit model-boundary review.
- Lint, typecheck, debt audit, build, targeted page tests, and a11y/browser evidence have been recorded for the claimed frontend-surface scope.

What still blocks the full claim:

- Gate I business-contract certification is pending.
- The configured MCP evidence servers are not exposed in this Codex App session.
- Business/golden-sample approvals and governance marker retirement cannot be inferred from local code.
- Gate J has not yet scored or explicitly excluded the remaining non-audited business routes.

## RALPLAN-DR Summary

### Principles

1. Business correctness beats visual polish.
2. A page is not investment-bank-grade until its critical numbers can be traced from source to screen.
3. Governance uncertainty must stay visible, even when it hurts visual cleanliness.
4. Expand the claim by route, not by blanket system language.
5. Every promotion needs reproducible test and evidence artifacts.

### Decision Drivers

1. Evidence authority: MCP lineage/contract evidence outranks local inference.
2. Blast radius: start with one high-confidence route and template the certification workflow.
3. Claim discipline: separate frontend readiness from business-contract certification and business approval.

### Viable Options

**Option A: Gate I first on `/ledger-pnl`**

- Pros: already `28/28`, recently touched, strong page tests, narrow business surface, good certification template candidate.
- Cons: does not immediately expand visible product coverage.

**Option B: Gate I first on `/pnl-attribution`**

- Pros: high business value, explicit lens boundaries, approval blockers already visible.
- Cons: more mixed-source semantics and external approval risk.

**Option C: Gate J first on `/balance-movement-analysis`**

- Pros: expands route coverage and aligns with existing system score ledger candidate selection.
- Cons: would widen the claim before the certification mechanism is proven.

**Chosen path:** Option A, then Option B, then Gate J. First prove the business-contract certification workflow on `/ledger-pnl`, then apply it to `/pnl-attribution` and `/product-category-pnl`, then widen route scope.

## Acceptance Criteria

1. Each certified route has a trace table covering API response -> adapter/model -> state/selector -> component -> chart/table.
2. Each decision metric records unit, precision, report date, as-of date, stale/fallback behavior, null/zero handling, and golden-sample status.
3. MCP status is explicit: `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus` are either used or marked unavailable with fallback evidence and residual risk.
4. No governance marker, formal-use flag, business approval, or metric definition is changed without evidence authority.
5. Scorecard separates `frontend-ready`, `business-contract-certified`, `evidence-pending`, and `out-of-scope`.
6. Touched frontend pages keep passing targeted tests, live-route smoke, lint, typecheck, debt audit, build, and relevant browser/a11y smoke.

## Task 1: Gate I MCP Availability And Fallback Ledger

**Files:**

- Read: `docs/MCP_RUNBOOK.md`
- Read: `.mcp.json`
- Read: `.codex/config.toml`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Steps:**

1. Re-run tool discovery for project MCP servers and record the result.
2. Confirm local configuration for `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus`.
3. If exposed, collect route trace bundles and evidence packets.
4. If unavailable, record the exact unavailable state and use local docs/tests only as pre-certification evidence.
5. Update the audit wording so unavailable MCP evidence cannot be mistaken for certification.

**Verification:**

```powershell
Select-String -Path docs/audits/2026-06-05-institutional-frontend-scorecard.md -Pattern "MCP Status|business-contract"
Select-String -Path docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md -Pattern "Gate I"
```

## Task 2: `/ledger-pnl` Business Trace Certification Template

**Files:**

- Inspect: `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`
- Inspect: `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.css`
- Inspect: `frontend/src/test/LedgerPnlPage.test.tsx`
- Inspect: `frontend/src/test/LedgerPnlRoutesSmoke.test.tsx`
- Inspect: relevant ledger API/domain client files found via targeted search
- Read: `docs/page_contracts.md`
- Read: `docs/metric_dictionary.md`
- Read: `docs/golden_sample_catalog.md`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Identify displayed ledger decision metrics and controls from the page tests and component.
2. Trace each displayed value from API response through adapter/model to visible component.
3. Check unit, sign, precision, rounding, null versus zero, report date, as-of date, fallback, candidate/formal boundary, and stale semantics.
4. Confirm no frontend duplicate finance calculation has been introduced.
5. Add a ledger certification table to the audit with status per metric: `certified`, `pre-certified-local-only`, or `evidence-pending`.
6. Add the smallest test only if a trace gap reveals unguarded display behavior.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/LedgerPnlPage.test.tsx
npm run test -- src/test/LedgerPnlRoutesSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Task 3: Apply Gate I To `/pnl-attribution`

**Files:**

- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Inspect: `frontend/src/test/PnlAttributionPage.test.tsx`
- Inspect: relevant attribution API/domain client files found via targeted search
- Read: `docs/page_contracts.md`
- Read: `docs/metric_dictionary.md`
- Read: `docs/golden_sample_catalog.md`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Reuse the `/ledger-pnl` trace template.
2. Split product-category lens, formal FI lens, TPL hybrid exception, and Campisi boundary into explicit evidence rows.
3. Verify comparison mode, view period, quality flag, fallback text, and next action remain visible.
4. Preserve approval blockers instead of rewriting them.
5. Add tests only for concrete unguarded display semantics.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/PnlAttributionPage.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Task 4: Resolve `/product-category-pnl` Residual Branch Proof

**Files:**

- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Inspect: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Keep the implemented fallback liability detail readout.
2. Create or run a branch-specific browser fixture that reaches `product-category-liability-side-detail-table`, if existing test architecture supports it without changing business data.
3. If the branch cannot be reached safely, keep the `27/28` score and record the precise blocker.
4. Do not fabricate fallback payloads as production evidence.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

## Task 5: Gate J Route-Scope Expansion

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Files:**

- Read: `docs/frontend-institutional-standard.md`
- Read/update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Read/update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Inspect per-route feature files under `frontend/src/features/`
- Inspect relevant tests under `frontend/src/test/`

**Steps per route:**

1. State the route's single primary business question.
2. Score the route against the seven frontend dimensions.
3. Mark the route as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
4. If the route is close, add only the smallest first-screen or mobile-readout correction.
5. Add route-specific tests and browser evidence before promoting it.

**Verification per changed route:**

```powershell
cd frontend
npm run test -- <route-specific-test-file>
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Browser evidence must include desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, no fallback route, no permanent loading, no document-level horizontal overflow, no blocking console errors, and screenshots or measurements saved under `frontend/.codex-tmp/`.

## Task 6: Final Certification Report

**Files:**

- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Optional create: `docs/audits/2026-06-05-top-investment-bank-certification-status.md`

**Steps:**

1. Summarize which routes are frontend-ready.
2. Summarize which routes are business-contract-certified.
3. List which routes remain evidence-pending or explicitly excluded.
4. List MCP server availability and fallback evidence.
5. List commands and browser evidence run for the claimed scope.
6. Keep business-owner and golden-sample approval blockers explicit.

**Final claim rule:**

Do not say "MOSS has fully reached top investment-bank standard" unless Gate I certification and Gate J route-scope classification are both complete for the claimed scope. Until then, say: "the seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open."

## ADR

**Decision:** Certify business evidence before expanding the flagship claim further.

**Drivers:** The current visible UI quality is high, but top investment-bank trust depends on traceable numbers, lineage, governance, and scope discipline.

**Alternatives considered:** Expand Gate J first for more visible coverage; polish the remaining UI details first; wait for external business approvals before doing more engineering work.

**Why chosen:** Gate I creates the repeatable proof template. Without it, wider coverage risks becoming a visual claim without audit authority.

**Consequences:** The next round may produce documentation and tests before obvious visual changes. That is intentional: the remaining standard gap is trust infrastructure, not styling.

**Follow-ups:** After `/ledger-pnl` and `/pnl-attribution` Gate I slices, run Gate J on `/balance-movement-analysis`, then decide whether to promote, watch, or exclude each remaining route.
