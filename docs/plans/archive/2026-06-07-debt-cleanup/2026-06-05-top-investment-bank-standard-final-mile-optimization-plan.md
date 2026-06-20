# Top Investment Bank Standard Final Mile Optimization Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from seven-route flagship frontend readiness to an honestly certifiable top investment-bank operating standard for the exact route scope that evidence can prove.

**Architecture:** Treat MOSS as a governed decision system. Each route must close source-to-screen metric traceability, contract evidence, governance lineage, approval state, responsive/browser evidence, and final institutional UX polish before it can be included in the final claim.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, local MCP stdio evidence launchers, page contracts, metric dictionary, golden-sample catalog, governance packets, Python readiness scripts, PowerShell verification wrappers, and route-level audit artifacts.

---

## Current Truth

The target has not been fully achieved yet.

Proven so far:

- Seven audited routes are frontend-surface flagship ready: `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Gate H automated accessibility evidence is complete for those seven routes.
- `/ledger-pnl`, `/pnl-attribution`, and `/product-category-pnl` now have Gate I boundary evidence, but none should be called fully business-certified yet.

Still blocking the final top-standard claim:

- `/ledger-pnl` has no written direct PAGE/API governance record from the approved workflow, no expanded lineage closure, no dedicated ledger summary golden sample, and no captured business-owner approval.
- `/pnl-attribution` has direct-record readiness and catalog/date evidence, but `formal_use_allowed=false`, `closure_approved=false`, manual audit checks remain, and `GS-PNL-ATTR-WB-A` only covers the primary workbench DTO boundary.
- `/product-category-pnl` has the strongest evidence, but closure approval is still false, the golden-sample approval artifact still says awaiting approval, manual audit checks remain, and liability fallback behavior still needs model-boundary review.
- `/bond-analysis` is frontend-ready, but the readiness system currently supports `bond-dashboard`, not `bond-analysis`; `GS-BOND-HEADLINE-A` must not be borrowed to certify `/bond-analysis`.
- `/cross-asset`, `/macro-toolkit`, and `/stock-analysis` are still business-contract `not-started` in Gate I.
- Gate J has not classified the remaining business routes, so the final claim cannot expand beyond the seven audited routes.

Use only this claim until all blockers close:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

## Target Standard

A route can be called top investment-bank-grade only when all of this is true:

1. The first screen answers the primary business question, trust state, supporting evidence, and next action.
2. Every displayed decision metric exposes source, date, unit, precision, status, stale/fallback/no-data behavior, and formal/candidate boundary.
3. Every critical value is traced through API response -> adapter/model -> state/selector -> component -> chart/table.
4. MCP metric-contract, lineage, catalog/date, governance, or documented fallback-risk evidence supports the business claim.
5. Golden-sample scope is explicit and never overused to certify unapproved surfaces.
6. Business-owner approval is captured by a strict checker before closure.
7. Desktop `1440px`, tablet `768px`, and mobile `390px` checks show no fallback route, no permanent loading, no document-level horizontal overflow, and no blocking console errors.
8. Non-audited routes are classified or explicitly excluded so the certification claim cannot silently expand.

## RALPLAN-DR Summary

### Principles

1. Business correctness outranks visual polish.
2. Claim only the route scope that is proven.
3. Keep formal, candidate, supporting-only, temporary-exception, stale, fallback, and no-data states visible.
4. Close one route deeply before scaling the status wording.
5. Make every promotion reversible, testable, and evidence-backed.

### Decision Drivers

1. Evidence authority: MCP contracts, lineage records, golden samples, and business-owner approval outrank local inference.
2. Auditability: every number on screen must be explainable from source to UI.
3. Claim discipline: frontend readiness, business-contract certification, and business approval are separate states.

### Viable Options

**Option A: Evidence-first Gate I closure.**

- Pros: Directly closes the real blocker to a top-bank claim.
- Cons: Slower visible change; some steps need business/governance authorization.

**Option B: Final visual polish first.**

- Pros: Makes the product feel sharper immediately.
- Cons: Does not certify business correctness or reduce audit risk.

**Option C: Gate J route classification first.**

- Pros: Prevents overclaiming whole-system readiness.
- Cons: Leaves high-value PnL pages still pending certification.

**Chosen path:** Option A first, then Gate J route classification, then final UX hardening.

## Task 1: Finish `/bond-analysis` Gate I Boundary Gap

**Purpose:** Stop `/bond-analysis` from being incorrectly certified through `/bond-dashboard` evidence.

**Files:**

- Create: `docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Inspect: `frontend/src/router/routes.tsx`
- Inspect: `frontend/src/features/bond-analytics/`
- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Inspect: `docs/golden_sample_catalog.md`

**Steps:**

1. Record that `/bond-analysis` route exists and renders `BondAnalyticsView`.
2. Record existing browser surface evidence from `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json`.
3. Record that `scripts/codex_page_readiness.py --page-slug bond-analysis` is unsupported today.
4. Record that `PAGE-BOND-001` and `GS-BOND-HEADLINE-A` apply to `/bond-dashboard`, not `/bond-analysis`.
5. Preserve fixed-income conventions: DV01, duration, yield percent, bp, market value, accounting class, report date, stale/fallback/result_meta status.
6. Mark `/bond-analysis` as `frontend-ready` plus `gate-i-gap` or `evidence-pending`, never certified.

**Acceptance Criteria:**

- The scorecard no longer shows `/bond-analysis` Gate I as simply `not-started`.
- The gap artifact explicitly prevents `/bond-dashboard` evidence from being reused.
- No bond metric IDs, golden samples, formal-use flags, or approvals are promoted.

**Verification:**

```powershell
python -m json.tool docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json > $null
python -m pytest tests/test_codex_page_readiness_gate.py -q
git diff --check docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json docs/audits/2026-06-05-institutional-frontend-scorecard.md docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md
```

## Task 2: Turn The Scorecard Into A Certification Ledger

**Purpose:** Separate "looks flagship-ready" from "business certified" on every route.

**Files:**

- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Steps:**

1. Add status columns for frontend surface, Gate I evidence, golden-sample scope, governance record, manual audit review, business-owner approval, and final claim status.
2. Keep the seven-route frontend score as-is where browser evidence supports it.
3. Mark certification status independently as `certified`, `evidence-pending`, `gate-i-gap`, `frontend-only`, or `excluded`.
4. Add a short "allowed claim" line and a "forbidden claim" line.

**Acceptance Criteria:**

- A reader cannot confuse visual readiness with business certification.
- Every route has one unambiguous next blocker.
- The final claim remains narrower than the evidence.

**Verification:**

```powershell
Select-String -Path docs/audits/2026-06-05-institutional-frontend-scorecard.md -Pattern "allowed claim|forbidden claim|evidence-pending|gate-i-gap"
git diff --check docs/audits/2026-06-05-institutional-frontend-scorecard.md docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md
```

## Task 3: Certify The Strongest Route First

**Purpose:** Use `/product-category-pnl` as the first candidate for true business-contract closure because it has the strongest current evidence.

**Files:**

- Inspect: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`

**Steps:**

1. Reconcile readiness status against `GS-PROD-CAT-PNL-A/approval.md`.
2. Resolve or explicitly document the mismatch between `formal_use_allowed=true` readiness and `captured-awaiting-approval` approval artifact wording.
3. Close the ten `PARTIAL` closure-checklist units only with evidence.
4. Review the fallback liability detail model boundary or keep the blocker visible.
5. Do not alter formulas, metric IDs, or formal-use semantics without authority.

**Acceptance Criteria:**

- `/product-category-pnl` either becomes the first certified route with approval evidence, or remains `evidence-pending` with exact blockers.
- No approval mismatch remains hidden.
- Detail metrics `MTR-PCP-004` through `MTR-PCP-012` stay within their documented approved boundary.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug product-category-pnl
python -m pytest tests/test_codex_page_readiness_gate.py -q
python -m pytest tests/test_project_mcp_servers.py::test_metric_contracts_page_trace_bundle_accepts_aliases_and_rejects_unknown_pages tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records -q
```

## Task 4: Close `/pnl-attribution` Approval And Boundary Lane

**Purpose:** Keep strong existing evidence while preventing overclaiming advanced, Campisi, or full-page certification.

**Files:**

- Inspect: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- Inspect: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Inspect: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- Inspect: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Inspect: `tests/golden_samples/GS-PNL-ATTR-WB-A/`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`

**Steps:**

1. Re-run the readiness, governance dry-run, and approval checker.
2. Keep `formal_use_allowed=false` and `closure_approved=false` until signed evidence exists.
3. Split primary workbench DTO evidence from advanced, Campisi, formal PnL overview, and executive overlay surfaces.
4. Create a business-owner action packet if the current 11 action items remain open.

**Acceptance Criteria:**

- The page status remains honest: no certification without approval.
- The golden-sample boundary remains limited to the primary DTO.
- The next business-owner decision is crisp enough for sign-off.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug pnl-attribution
python scripts/emit_pnl_attribution_governance_record.py
python scripts/check_pnl_attribution_business_owner_approval.py
python -m pytest tests/test_pnl_attribution_governance_record.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
```

## Task 5: Close `/ledger-pnl` Governance Only When Authorized

**Purpose:** Keep ledger moving without writing governance records casually.

**Files:**

- Inspect: `scripts/emit_ledger_pnl_governance_record.py`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-governance-closure-status.json`
- Inspect: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json`

**Steps:**

1. Re-run dry-run and confirm `record_write_status=not_requested`.
2. Keep `python scripts/emit_ledger_pnl_governance_record.py --write` as workflow-authorized only.
3. If an authorized write happens later, validate direct and expanded records before changing status.
4. Keep `MTR-LPN-001` through `MTR-LPN-003` as candidate until golden sample and approval evidence exist.

**Acceptance Criteria:**

- Dry-run remains repeatable.
- Written-record closure is not faked from preflight.
- Ledger certification remains blocked until governance, manual review, and approval close.

**Verification:**

```powershell
python scripts/emit_ledger_pnl_governance_record.py
python scripts/check_ledger_pnl_business_owner_approval.py
python -m pytest tests/test_ledger_pnl_governance_record.py tests/test_ledger_pnl_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
```

## Task 6: Gate I Scale-Out For Remaining Flagship Routes

**Purpose:** Move `/cross-asset`, `/macro-toolkit`, and `/stock-analysis` from frontend-only evidence to contract-aware status.

**Files:**

- Inspect: `frontend/src/features/cross-asset/`
- Inspect: `frontend/src/features/macro-toolkit/`
- Inspect: `frontend/src/features/stock-analysis/`
- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Steps per route:**

1. Identify the primary business question.
2. List displayed decision metrics and status markers.
3. Trace API response -> adapter/model -> state/selector -> component -> chart/table.
4. Check unit, precision, date, stale/fallback/no-data, null-vs-zero, and candidate/formal boundary.
5. Collect MCP evidence where configured; record unavailable servers or missing contracts explicitly.
6. Classify as `certified`, `evidence-pending`, `gate-i-gap`, or `frontend-only`.

**Acceptance Criteria:**

- No remaining flagship route stays `not-started` without explanation.
- No visual-only route is called business certified.
- Contract gaps become named work items.

## Task 7: Gate J Whole-System Scope Control

**Purpose:** Prevent the final claim from silently covering routes that were never audited.

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard and workbench-home decision surfaces

**Files:**

- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Inspect per route: `frontend/src/router/routes.tsx`
- Inspect per route: relevant `frontend/src/features/` subtree
- Inspect per route: relevant tests under `frontend/src/test/`

**Steps per route:**

1. State the primary business question.
2. Score business trust, first-screen closure, hierarchy, responsive resilience, accessibility, token alignment, and runtime cleanliness.
3. Classify as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
4. Browser verify only when the route is near inclusion.

**Acceptance Criteria:**

- The final certification scope is explicit.
- Excluded routes are named, not silently ignored.
- The system-level claim cannot be misread as all-route approval.

## Task 8: Final Institutional UX Hardening

**Purpose:** Use design polish only after evidence status is stable.

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
- Do not hide governance, stale, fallback, no-data, temporary-exception, formal-use, or approval markers.
- Do not change finance formulas.
- Do not rebuild global design infrastructure for a page-local issue.

**Verification:**

```powershell
cd frontend
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Browser evidence for changed routes must include:

- Desktop `1440px`
- Tablet `768px`
- Mobile `390px`
- Status `200`
- No fallback route
- No permanent busy state
- No document-level horizontal overflow
- No blocking console errors

## Task 9: Final Certification Packet

**Purpose:** Produce the final answer to whether MOSS meets the target.

**Files:**

- Create: `docs/audits/2026-06-05-top-investment-bank-standard-certification-packet.md`
- Modify: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Modify: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Packet must include:**

1. Exact certified route set.
2. Excluded or pending route set.
3. Per-route frontend evidence.
4. Per-route business-contract evidence.
5. Golden-sample and metric-dictionary boundaries.
6. Business-owner approval status.
7. Verification commands and outputs.
8. Residual risks and release caveats.

**Acceptance Criteria:**

- The packet can be reviewed by audit, desk owner, engineering, and risk without relying on chat history.
- Claims are narrower than or equal to evidence.
- Any missing approval or evidence is visible.

## Tooling That Raises The Bar

Use these deliberately in the next execution round:

- `moss-metric-contracts`: page contracts, metric definitions, units, and source-to-screen trace bundles.
- `moss-lineage-evidence`: governance records, manual review blockers, source lineage, fallback/stale status.
- `moss-data-catalog`: table presence, report dates, date-column evidence, stale data detection.
- `gitnexus`: cross-page impact and symbol/call-path lookup before touching shared business paths.
- Browser/Playwright: desktop/tablet/mobile runtime proof, console errors, overflow, focus traversal.
- `visual-verdict`: structured visual QA when comparing screenshots after a polish pass.
- `finance-data-quality`: grain, keys, null/zero, date, unit, stale, reconciliation, and aggregate checks.
- `fixed-income-analytics`: DV01, duration, yield, bp, curve, clean/dirty price, and sign convention checks for bond routes.
- `frontend-design`, `normalize`, `polish`, `typeset`, `audit`: final UI layer after business evidence stabilizes.

## Final Claim Rule

Do not say "MOSS has reached top investment-bank standard" until the certification packet proves the claimed route set.

Allowed current wording:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

Target wording after closure:

> The named certified route set meets MOSS top investment-bank standard for frontend decision surface, business-contract traceability, governance evidence, approval state, and responsive/browser operation; routes outside the named set remain pending or excluded.
