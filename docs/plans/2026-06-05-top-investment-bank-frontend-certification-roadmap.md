# Top Investment Bank Frontend Certification Roadmap

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this roadmap task-by-task.

> Historical snapshot. For current `/product-category-pnl` approval and owner-review counts, defer to `docs/audits/2026-06-06-top-investment-bank-certification-board.md` and the generated PnL packets. Current machine truth is `approval_action_item_count=15`, `closure_blocker_triage.blocker_count=15`, and `next_review_queue_item_count=4`; older 13 action-item counts below are retained as 2026-06-05 evidence only.

**Goal:** Move MOSS from audited flagship page-surface readiness to a stricter top investment-bank frontend certification standard.

**Architecture:** Keep every change page-scoped, evidence-first, and contract-preserving. Improve decision closure, mobile readouts, accessibility, and business-contract traceability without changing finance formulas, governance markers, backend services, schema, auth, scheduler, queue, cache, or global SDK layers.

**Tech Stack:** React, TypeScript, Vite, Vitest, browser verification, Ant Design, page-local CSS/CSS modules, existing MOSS design tokens, and project MCP evidence servers when available.

---

## Current State

Seven audited flagship routes are page-surface ready:

- `/cross-asset`
- `/ledger-pnl`
- `/macro-toolkit`
- `/stock-analysis`
- `/product-category-pnl`
- `/pnl-attribution`
- `/bond-analysis`

The current audited scope is strong, but full-system top investment-bank certification is not complete until the remaining gates below are closed with evidence.

## Certification Bar

A route can be called top investment-bank-grade only when it proves all of this:

1. The first screen answers trust, conclusion, supporting evidence, and next action.
2. Key displayed metrics keep source, date, unit, status, stale/fallback/no-data semantics visible.
3. Desktop and tablet preserve audit-grade raw grids.
4. Mobile shows a decision readout before dense raw tables.
5. Keyboard and assistive-technology workflows can reach the same decision state.
6. Targeted tests, live-route smoke, lint, typecheck, debt audit, build, and browser checks pass.
7. Business-contract claims are backed by MCP metric and lineage evidence.

## Gate G: Finish Mobile Table Decision Readouts

**Status:** In progress.

**Already complete:**

- `/bond-analysis` accounting DV01 and holdings readouts.
- `/pnl-attribution` product-category attribution and YTD readouts.
- `/product-category-pnl` formal table readout.
- `/product-category-pnl` attribution comparison and detail readouts.
- `/product-category-pnl` liability-side detail and currency matrix readouts.

### Task G1: Product Category Attribution Comparison Readout

**Status:** Complete. Evidence saved under `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/`.

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Steps:**

1. Add a failing test for `product-category-attribution-comparison-mobile-readout`.
2. Assert it renders before `product-category-attribution-comparison-table`.
3. Assert it summarizes monthly delta, largest effect, unexplained effect, closure error, and row state.
4. Implement a display-only readout using existing page payload fields.
5. Preserve the raw comparison table for reconciliation.
6. Run the product-category page tests.
7. Browser verify `/product-category-pnl` at `1440px`, `768px`, and `390px`.

**Completion evidence:**

- RED: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because `product-category-attribution-comparison-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 47 passed.
- Slice: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 86 passed.
- Browser evidence: `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/layout-verification.json`.

### Task G2: Product Category Attribution Detail Readout

**Status:** Complete. Evidence saved under `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/`.

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Steps:**

1. Add a failing test for `product-category-attribution-detail-mobile-readout`.
2. Assert it renders before `product-category-attribution-detail-table`.
3. Assert it summarizes selected category, current/prior date pair, current/prior business net income, scale, and yield.
4. Implement a display-only readout using existing page payload fields.
5. Preserve the raw detail table.
6. Run the product-category page tests.
7. Browser verify `/product-category-pnl` at `1440px`, `768px`, and `390px`.

**Completion evidence:**

- RED: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because `product-category-attribution-detail-mobile-readout` was missing.
- GREEN: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 47 passed.
- Slice: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 86 passed.
- Browser evidence: desktop/tablet keep the detail readout hidden; mobile `390px` shows it before `product-category-attribution-detail-table`, with no document-level horizontal overflow, no console warnings/errors, and no page errors.

### Task G3: Liability Matrix Readouts

**Status:** Complete for the normal matrix path. Evidence saved under `frontend/.codex-tmp/product-category-pnl-gate-g-liability/`. The fallback table readout remains a defensive branch; current model-derived liability detail rows also produce detail-matrix rows, so the residual is model-boundary review rather than synthetic production browser proof.

**Files:**

- Modify: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Modify: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Reuse: existing `product-category-attribution-mobile-readout` mobile styling in `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Update: `docs/audits/2026-06-05-gate-g-mobile-table-watchlist.md`

**Steps:**

1. Add tests for `product-category-liability-side-detail-matrix` mobile readout behavior.
2. Add tests for `product-category-liability-side-currency-matrix-*` mobile readout behavior.
3. Add a fallback readout for `product-category-liability-side-detail-table`.
4. Preserve all raw matrices and fallback tables.
5. Browser verify no horizontal overflow and readout-before-grid order.

**Completion evidence:**

- RED: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because the liability-side mobile readout anchors were missing.
- GREEN: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 49 passed.
- Slice: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 88 passed.
- Live-route slice: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- Browser evidence: `frontend/.codex-tmp/product-category-pnl-gate-g-liability/browser-verification.json`.

## Gate H: Accessibility 4/4

**Status:** Complete for the seven audited flagship routes under the automated frontend-surface gate. H1 keyboard entry, H2 route-owned focus traversal, and H3 control-context/non-color cue coverage are complete.

**Files:**

- Inspect/modify: `frontend/src/layouts/WorkbenchShell.tsx`
- Inspect/modify: `frontend/src/styles/workbenchInstitutionalConsole.css`
- Inspect/modify: seven audited route files under `frontend/src/features/`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`
- Test: relevant page tests under `frontend/src/test/`
- Test if available: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

**Steps:**

1. Audit keyboard order through shell navigation, filters, tabs, drill actions, and table controls.
2. Add or tighten visible focus states for custom controls.
3. Ensure ready, warning, stale, fallback, blocked, no-data, and temporary-exception states are not communicated by color alone.
4. Add accessible names or descriptions only where visible labels are insufficient.
5. Browser-walk the seven flagship routes and record keyboard evidence.

### Task H1: Shared Skip-To-Main Keyboard Entry

**Status:** Complete.

**Files:**

- Modified: `frontend/src/layouts/WorkbenchShell.tsx`
- Modified: `frontend/src/styles/global.css`
- Modified: `frontend/src/test/WorkbenchShell.test.tsx`
- Modified: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

**Completion evidence:**

- RED: `npm run test -- src/test/WorkbenchShell.test.tsx` failed only because the shell had no `Skip to main content` link and the main landmark had no accessible `Main content` name.
- GREEN: `npm run test -- src/test/WorkbenchShell.test.tsx`: 40 passed.
- Browser keyboard evidence: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-keyboard'`: 7 passed across `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Full a11y smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1`: 39 passed, including route axe coverage, shared keyboard entry, route-owned focus traversal, and control-level context evidence.
- Verification: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed; `npm run typecheck`, `npm run lint`, `npm run debt:audit`, and `npm run build` passed.

### Task H2: Route-Owned Business Control Focus Traversal

**Status:** Complete.

**Files:**

- Modified: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

**Completion evidence:**

- Browser route-focus smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-route-focus'`: 7 passed across `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- The test starts at `Skip to main content`, verifies focus lands on `#workbench-main-content`, then Tabs forward until focus reaches a route-owned business control such as report-date selectors, page tabs, refresh/drill buttons, or disclosure summaries.
- This proves keyboard users can move beyond shell chrome and the main landmark into the page's own decision/control surface for the seven audited flagship routes.

### Task H3: Control Context And Non-Color State Cues

**Status:** Complete.

**Files:**

- Modified: `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`
- Modified: `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`
- Modified: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Modified: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Modified: `frontend/src/test/PnlAttributionPage.test.tsx`
- Modified: `frontend/src/test/LedgerPnlPage.test.tsx`
- Modified: `frontend/src/test/LedgerPnlRoutesSmoke.test.tsx`

**Completion evidence:**

- RED: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-control-context'` failed because `/ledger-pnl` exposed internal slug names (`ledger-pnl-report-date`) to assistive technology and `/pnl-attribution` lens cards lacked explicit status text.
- GREEN: the same `@gate-h-control-context` smoke passed with 7 passed across `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Combined Gate H browser smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-(keyboard|route-focus|control-context)'`: 21 passed.
- Full a11y smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1`: 39 passed.
- Component regression: `npm run test -- src/test/PnlAttributionPage.test.tsx`: 6 passed; `npm run test -- src/test/LedgerPnlPage.test.tsx`: 49 passed; `npm run test -- src/test/LedgerPnlRoutesSmoke.test.tsx`: 3 passed.
- Standard checks: `npm run lint`, `npm run typecheck`, `npm run debt:audit`, and `npm run build`: passed.

**Gate H residual notes:**

- The automated gate now covers shared entry, route-owned control traversal, human-readable control names, visible focus indication, and non-color status cues for the seven audited routes.
- A manual assistive-technology walkthrough remains recommended before external release, but Gate H is no longer the blocker for the frontend-surface score.

## Gate I: MCP-Backed Business Contract Certification

**Status:** In progress. Direct Codex App tool discovery did not expose the project MCP tools, but the configured local read-only MCP stdio launchers were callable for `/ledger-pnl`. The first ledger slice collected metric-contract, lineage, catalog/date, direct-record blocker-routing, and preflight-candidate evidence; it remains `evidence-pending`, not `business-contract-certified`. `/pnl-attribution` now also has Gate I boundary evidence: direct governance-record validation is ready for audit review and catalog/date sampling covers all configured tables, but manual audit checks and business-owner approval are still open, so it is also `evidence-pending`. `/product-category-pnl` has stronger formal/governed readiness with catalog/date samples, direct-record readiness, a golden-sample boundary, and a strict pending business-owner approval checker; it remains `evidence-pending` because the checker reports `business_owner_approval_captured=false`, `closure_approved=false`, and 13 action items. `/bond-analysis` now has a Gate I boundary-gap artifact: the route is frontend-ready, but direct readiness, page-contract, golden-sample, governance, and approval evidence are missing, and `/bond-dashboard` evidence must not be reused as certification.

**Required evidence servers:**

- `moss-metric-contracts`: available through local stdio launcher for `/ledger-pnl`.
- `moss-lineage-evidence`: available through local stdio launcher for `/ledger-pnl`.
- `moss-data-catalog`: available through local stdio launcher for `/ledger-pnl`.
- `gitnexus`: configured locally but not directly exposed as an App tool and not used in the first Gate I slice.

**Current `/ledger-pnl` evidence artifact:**

- `docs/audits/2026-06-05-ledger-pnl-gate-i-mcp-evidence.json`
- `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`
- `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json`
- `docs/audits/2026-06-05-ledger-pnl-governance-closure-status.json`
- `scripts/emit_ledger_pnl_governance_record.py`, a default dry-run generator for the field-complete candidate record. It preflights the candidate, lists the target stream, and writes only when `--write` is explicitly supplied.
- `docs/pnl/ledger-pnl-business-owner-approval-template.md`, a pending business-owner approval template that keeps `formal_use_allowed=false` and `closure_approved=false`.
- `scripts/check_ledger_pnl_business_owner_approval.py`, a strict approval checker surfaced through page readiness; it currently reports `business_owner_approval_captured=false` and 11 approval action items.

**Current `/ledger-pnl` Gate I verdict:**

- `frontend-ready`: yes, based on earlier page-surface evidence.
- `business-contract-certified`: no.
- `Gate I status`: `evidence-pending`.
- Reason: `moss-lineage-evidence.get_page_governance_audit_evidence_packet` reports `manual_review_blocker_count=1`, blocker `direct_page_api_record_fields`, and `closure_approved=false`. Follow-up MCP blocker routing now shows `validation_status=missing_direct_records`, `direct_record_count=0`, `expanded_anchor_record_count=0`, P1 gap `missing_direct_and_expanded_records`, and remediation lane `create_direct_record_and_supporting_lineage`.
- Direct-record missing fields: `report_date`, `basis`, `source_surface`, `source_version`, `rule_version`, and `created_at`.
- Direct-record field-group status: the preflight candidate now satisfies `execution_identifier` with `cache_key=ledger_pnl.summary:2026-05-31:ALL`; the blocker remains at the written-record layer because no direct page/API governance record exists yet.
- Preflight candidate status: a candidate record populated from current `/api/ledger-pnl/summary` result_meta for `2026-05-31` fills the required fields, keeps `formal_use_allowed=false`, includes `cache_key=ledger_pnl.summary:2026-05-31:ALL`, and `preflight_page_governance_record` returns `validation_status=ready_for_audit_review`, `missing_required_fields=[]`, and `failed_required_field_groups=[]`. This is preflight-only field completeness; it does not write a record, prove page/API execution completeness, capture business-owner approval, or certify `/ledger-pnl`.
- Latest governed dry-run: `python scripts/emit_ledger_pnl_governance_record.py` returned `mode=dry-run`, `record_write_status=not_requested`, `existing_record_line=null`, `preflight.validation.validation_status=ready_for_audit_review`, `missing_required_fields=[]`, `failed_required_field_groups=[]`, and `evidence_scope.writes_governance_records=false` with `created_at=2026-06-05T13:47:58.221725Z`.
- Metric boundary: `MTR-LPN-001` through `MTR-LPN-003` remain candidate display metrics with `pending_confirmation=true` and no dedicated golden sample.
- Source/golden boundary status: `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json` records the ledger summary grain, natural key, `cache_key` execution identifier, configured source anchors, catalog-date limitations, current implementation/test evidence, and missing dedicated ledger summary golden sample.
- Approval gate status: the ledger approval template/checker is wired, but the template remains pending. Readiness now exposes `python scripts/check_ledger_pnl_business_owner_approval.py`, `python scripts/check_ledger_pnl_business_owner_approval.py --require-captured`, and `powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug ledger-pnl -RequireApprovalCaptured`.
- Catalog/date note: `ledger_import_batch` is present with sampled `as_of_date` values; `ledger_raw_row` is present without a date column; `qdb_general_ledger_workbook` is currently reported as `unknown_table`.
- Readiness refresh note: `python scripts/codex_page_readiness.py --page-slug ledger-pnl` returns `overall_status=static-pass`, `golden_sample_boundary=missing`, `business_owner_approval_status=pending; captured=false`, `catalog_date_evidence=null`, `governance_record_validation=null`, and `audit_review=null`; this is routing evidence, not closure.

**Current `/pnl-attribution` evidence artifact:**

- `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- `scripts/emit_pnl_attribution_governance_record.py`, a dry-run governance-record generator for the primary workbench API record; it locates the existing record line and writes only when `--write` is explicitly supplied.
- `docs/pnl/pnl-attribution-governance-audit-packet.md`, a ready-for-audit-review packet that keeps `formal_use_allowed=false` and `closure_approved=false`.
- `docs/pnl/pnl-attribution-sign-off-packet.md`, a business-owner handoff packet that does not capture approval.
- `docs/pnl/pnl-attribution-business-owner-approval-template.md`, a pending business-owner approval template.
- `scripts/check_pnl_attribution_business_owner_approval.py`, a strict approval checker surfaced through page readiness; it currently reports `business_owner_approval_captured=false` and 11 approval action items.

**Current `/pnl-attribution` Gate I verdict:**

- `frontend-ready`: yes, based on earlier page-surface evidence.
- `business-contract-certified`: no.
- `Gate I status`: `evidence-pending`.
- Reason: readiness reports `overall_status=static-pass`, catalog/date evidence sampled `5/5` configured tables, governance validation reports `direct_records_ready_for_audit_review`, `direct_record_count=1`, and `expanded_anchor_record_count=20`; however, audit review still requires page contract review, catalog/date review, lineage freshness review, UI/API payload review, live-smoke evidence review, and business-owner approval.
- Direct-record status: `python scripts/emit_pnl_attribution_governance_record.py` returns `mode=dry-run`, `record_write_status=not_requested`, `existing_record_line=5403`, `preflight.validation.validation_status=ready_for_audit_review`, `record_key.cache_key=pnl-attribution:volume-rate:2026-04-30:mom`, `basis=formal`, `source_surface=formal_attribution`, and `formal_use_allowed=false`.
- Golden-sample boundary: `GS-PNL-ATTR-WB-A` is `captured-awaiting-approval` and freezes only the primary `GET /api/pnl-attribution/volume-rate` workbench DTO for `MTR-PAT-001` through `MTR-PAT-006`; it does not certify advanced attribution, Campisi, full-page closure, `/api/pnl/overview`, or the executive analytical overlay `/ui/pnl/attribution`.
- Approval gate status: `python scripts/check_pnl_attribution_business_owner_approval.py` reports `approval_status=pending`, `business_owner_approval_captured=false`, `formal_use_allowed=false`, `closure_approved=false`, and 11 action items.
- Boundary note: the captured DTO sample asserts `result_meta.formal_use_allowed=true` for the fixture-backed primary API sample, while the page-level governance and closure workflow intentionally keeps `formal_use_allowed=false` until candidate closure and business-owner approval are captured. This difference must be reviewed rather than silently normalized.

**Current `/product-category-pnl` evidence artifact:**

- `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
- `docs/pnl/product-category-page-truth-contract.md`, the governed page truth contract.
- `docs/pnl/product-category-closure-checklist.md`, which still lists all ten closure units as `PARTIAL`.
- `docs/pnl/product-category-remaining-blockers.md`, the blocker triage.
- `tests/golden_samples/GS-PROD-CAT-PNL-A`, the formal/detail sample plus companion scenario probe.
- `frontend/.codex-tmp/product-category-pnl-gate-g-liability/browser-verification.json`, normal liability matrix browser evidence.
- `docs/pnl/product-category-pnl-business-owner-approval-template.md`, a pending business-owner approval template that keeps the approval decision explicit.
- `scripts/check_product_category_pnl_business_owner_approval.py`, a strict approval checker surfaced through page readiness; it currently reports `business_owner_approval_captured=false` and 13 approval action items.
- `docs/pnl/product-category-pnl-first-certification-packet.md`, the owner-review packet that packages `MTR-PCP-001` through `MTR-PCP-012` source-to-screen trace, the machine-visible golden approval mismatch, and the pending action items without approving closure.

**Current `/product-category-pnl` Gate I verdict:**

- `frontend-ready`: yes, based on earlier page-surface evidence.
- `business-contract-certified`: no.
- `Gate I status`: `evidence-pending`.
- Reason: readiness reports `overall_status=static-pass`, `approval_status=formal_or_governed`, `formal_use_allowed=true`, catalog/date evidence sampled `2/2` configured tables, governance validation reports `direct_records_ready_for_audit_review`, `direct_record_count=1`, and `expanded_anchor_record_count=20`; however, audit review still reports `closure_approved=false` and requires page contract review, catalog/date review, lineage freshness review, UI/API payload review, live-smoke evidence review, and business-owner approval.
- Golden-sample boundary: `GS-PROD-CAT-PNL-A` covers `GET /ui/pnl/product-category` for `report_date=2026-02-28`, `view=monthly`, and a companion scenario probe. It binds `MTR-PCP-001` through `MTR-PCP-012`; further product-category fields need a new approved matrix, dictionary row, sample assertion, and test bundle.
- Approval artifact mismatch: readiness now reports `golden_sample_approval_artifact_mismatch=true` because `golden_sample_boundary=approved`, but `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` still says `captured-awaiting-approval` with owner, approver, and approval date as `TBD`; treat this as a manual audit item before final certification wording.
- Approval gate status: `python scripts/check_product_category_pnl_business_owner_approval.py` reports `approval_status=pending`, `business_owner_approval_captured=false`, `formal_use_allowed=true`, `closure_approved=false`, and 13 action items covering owner identity, approval decision/date/signature, governance-record review, `GS-PROD-CAT-PNL-A` approval artifact reconciliation, closure-checklist review, liability fallback model-boundary evidence review, UI/API payload review, live-smoke review, verification rerun, and evidence-pending boundary acceptance.
- First-certification packet status: `python scripts/product_category_pnl_first_certification_packet.py` writes `docs/pnl/product-category-pnl-first-certification-packet.md` and reports `handoff_status=owner_actions_required`, `business_contract_certified=false`, `approval_action_item_count=13`, and `golden_sample_approval_artifact_mismatch=true`.
- Frontend residual: the fallback liability detail readout remains defensive; model evidence now shows current liability detail rows also produce detail-matrix rows, so reviewers should not treat synthetic fallback payloads as production browser proof.
- ID boundary: readiness and the product truth contract use `PAGE-PROD-CAT-001`; `docs/page_contracts.md` names `PAGE-PROD-CAT-PNL-001` and states it refers to the same governed surface. Keep both visible until the namespace distinction is normalized.

**Current `/bond-analysis` evidence artifact:**

- `docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json`
- `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json`, the browser surface evidence for desktop `1440px`, tablet `768px`, and mobile `390px`.
- `frontend/src/router/routes.tsx`, where `/bond-analysis` renders `BondAnalyticsView` and `/bond-dashboard` renders `BondDashboardPage`.
- `docs/page_contracts.md`, where `PAGE-BOND-001` names route `/bond-dashboard` and `GET /api/bond-dashboard/*`.
- `tests/golden_samples/GS-BOND-HEADLINE-A/approval.md`, where the sample is `captured-awaiting-approval` for `GET /api/bond-dashboard/headline-kpis?report_date=2026-03-31`.

**Current `/bond-analysis` Gate I verdict:**

- `frontend-ready`: yes, based on earlier page-surface evidence.
- `business-contract-certified`: no.
- `Gate I status`: `gate-i-gap`.
- Reason: `python scripts/codex_page_readiness.py --page-slug bond-analysis` is rejected as an unsupported slug; the readiness script supports `bond-dashboard` but not `bond-analysis`. There is no direct `/bond-analysis` Gate I readiness lane, golden-sample boundary, governance validation, or business-owner approval path in the current evidence.
- Non-reuse boundary: `PAGE-BOND-001`, `GS-BOND-HEADLINE-A`, and `MTR-BOND-001` through `MTR-BOND-004` are `/bond-dashboard` artifacts. They must not certify `/bond-analysis`, BondAnalyticsView, DV01, duration, yield/YTM, bp movement, PnL, KRD, credit-spread, or holdings metrics.
- Browser surface status: `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json` records status `200`, no fallback route, no permanent busy state, no document-level horizontal overflow, no console messages, no page errors, and accounting-DV01/holdings readout anchors before the raw grids across desktop, tablet, and mobile. This proves surface cleanliness only, not business-contract certification.
- Fixed-income convention boundary: future certification must preserve report date/result_meta semantics, DV01 scale and sign, duration in years, yield/YTM percent, bp movement, market value scale, accounting class and holdings grain, plus stale/fallback/no-data/temporary-exception/formal-candidate markers.

**Files:**

- Update with evidence: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update with evidence: `docs/page_contracts.md`
- Update with evidence only: `docs/metric_dictionary.md`
- Update with evidence only: `docs/golden_sample_catalog.md`

**Steps:**

1. Trace each certified metric from API response to adapter/model, state/selector, component, and chart/table. `/ledger-pnl` first slice completed this as a trace table in the scorecard, but did not certify the metrics.
2. Confirm unit, precision, report date, as-of date, stale/fallback behavior, and golden sample status.
3. Split each route status into `frontend-ready`, `business-contract-certified`, or `evidence-pending`.
4. Retire governance markers only when MCP evidence supports the change.

**Next Gate I action:**

1. Dry-run the governed candidate command: `python scripts/emit_ledger_pnl_governance_record.py`. It must return `mode=dry-run`, `preflight.validation.validation_status=ready_for_audit_review`, and `evidence_scope.writes_governance_records=false`.
2. Fill the direct record from auditable evidence; current preflight candidate has `report_date=2026-05-31`, `basis=ledger`, `source_surface=ledger_pnl.summary`, `source_version=sv_product_category_3353b116b9a6`, `rule_version=rv_ledger_pnl_v1`, `created_at=2026-06-05T12:01:14.993184Z`, `cache_key=ledger_pnl.summary:2026-05-31:ALL`, and `tables_used=["qdb_general_ledger_workbook"]`.
3. Keep `trace_id=tr_ledger_pnl_summary` as supporting trace context only; the accepted execution identifier for the candidate is the `cache_key`.
4. Only through an approved governance workflow, run `python scripts/emit_ledger_pnl_governance_record.py --write` to append or locate the written direct PAGE/API governance record, keeping `formal_use_allowed=false`.
5. Add supporting source-table/result-kind lineage for the configured ledger anchors where evidence exists.
6. Rerun `validate_page_governance_records`, then proceed to contract, catalog/date, lineage freshness, UI/API payload, live-smoke, and business-owner review only if the written record validates as `direct_records_ready_for_audit_review`.
7. Complete the ledger business-owner approval template only after governance-record review, no-dedicated-golden-sample boundary review, UI/API payload review, live-smoke evidence review, verification rerun, and candidate-boundary acceptance are all evidenced.
8. Keep `/ledger-pnl` out of `business-contract-certified` until direct record review and closure evidence support that status.

**Latest `/ledger-pnl` closure refresh:**

1. `docs/audits/2026-06-05-ledger-pnl-governance-closure-status.json` captures the current no-write state.
2. Dry-run preflight is field-complete, but `existing_record_line=null` and `record_write_status=not_requested`; therefore no written direct PAGE/API governance record is proven.
3. Readiness remains `static-pass`, but `catalog_date_evidence`, `governance_record_validation`, and `audit_review` are null in the readiness output.
4. Business-owner approval remains pending with 11 action items.
5. The next material closure step is still an authorized governance write or located written record plus supporting expanded lineage validation; do not start business certification language before that.

**Next `/pnl-attribution` Gate I action:**

1. Use `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json` as the boundary artifact for the next audit slice.
2. Rerun `python scripts/codex_page_readiness.py --page-slug pnl-attribution`; it must stay `static-pass` without implying closure.
3. Rerun `python scripts/emit_pnl_attribution_governance_record.py`; it must stay dry-run unless governance workflow explicitly authorizes a write.
4. Review current API payload and visible UI state against the page contract, metric dictionary, `GS-PNL-ATTR-WB-A`, and result_meta.
5. Review live smoke/browser evidence for stale, fallback, no-data, provenance, and candidate-boundary visibility.
6. Complete the business-owner approval template only after governance-record review, golden-sample boundary review, UI/API payload review, live-smoke evidence review, verification rerun, and candidate-boundary acceptance are all evidenced.
7. Keep `/pnl-attribution` out of `business-contract-certified` until manual review, business-owner approval, and `closure_approved=true` are supported by evidence.

**Next `/product-category-pnl` Gate I action:**

1. Use `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json` as the boundary artifact for the next audit slice.
2. Run `python scripts/check_product_category_pnl_business_owner_approval.py` and treat `approval_status=pending`, `business_owner_approval_captured=false`, and the 13 action items as blockers, not approval.
3. Use `docs/pnl/product-category-pnl-first-certification-packet.md` as the owner review packet, then review the machine-reported `golden_sample_approval_artifact_mismatch=true` status: readiness boundary is approved, while `GS-PROD-CAT-PNL-A/approval.md` still shows `captured-awaiting-approval`.
4. Review the liability fallback-table model-boundary evidence and keep synthetic branch data out of production browser proof.
5. Complete the manual audit checks returned by readiness: page contract, catalog/date sampling, lineage freshness, UI/API payload, live-smoke evidence, business-owner approval, verification rerun, and evidence-pending boundary acceptance.
6. Keep `/product-category-pnl` out of `business-contract-certified` until `closure_approved=true` and captured business-owner approval are supported by evidence.

**Next `/bond-analysis` Gate I action:**

1. Decide whether `/bond-analysis` needs its own page contract ID or an explicit documented alias separate from `PAGE-BOND-001`.
2. Add or wire a direct readiness slug for `bond-analysis` only after the contract boundary is explicit.
3. Collect route-specific metric-contract, lineage, catalog/date, and governance evidence for `/api/bond-analytics/*` surfaces used by BondAnalyticsView.
4. Define a direct golden-sample boundary if any BondAnalyticsView fixed-income decision metrics are to be certified.
5. Keep `/bond-analysis` out of `business-contract-certified` until direct route evidence, manual audit review, and business-owner approval exist.

**Current certification-ledger action:**

1. Use `docs/audits/2026-06-05-institutional-frontend-scorecard.md` `Certification Ledger` as the authoritative claim-control table for the seven-route scope.
2. Do not promote any route to `certified` unless the ledger shows closed Gate I evidence, golden-sample scope, governance record, manual audit review, and business-owner approval.
3. Keep `/cross-asset`, `/macro-toolkit`, and `/stock-analysis` as `frontend-only` until Gate I trace evidence is collected.
4. Keep `/ledger-pnl`, `/pnl-attribution`, and `/product-category-pnl` as `evidence-pending` until their named blockers close; for `/product-category-pnl`, the current approval checker still reports 13 action items and `business_owner_approval_captured=false`.
5. Keep `/bond-analysis` as `gate-i-gap` until direct route readiness, contract, golden-sample, governance, manual audit, and owner-approval evidence exist.

## Gate J: Expand Beyond Seven Flagship Routes

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Per-route steps:**

1. Baseline the route against `docs/frontend-institutional-standard.md`.
2. Identify the page's single primary business question.
3. Add first-screen decision-order tests.
4. Implement the smallest page-local readout or layout correction.
5. Browser verify desktop, tablet, and mobile.
6. Update the scorecard only with evidence.

## Verification Matrix

Run from `frontend/` after each implementation slice:

```powershell
npm run test -- <page-specific-tests>
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

Browser verification for each touched route:

- `1440px` desktop
- `768px` tablet
- `390px` mobile
- status `200`
- no fallback route
- no permanent loading
- no document-level horizontal overflow
- no blocking console errors
- screenshots and measurements saved under `frontend/.codex-tmp/`

## Do Not Claim Full Certification Until

1. Gate G decision-critical mobile tables are complete.
2. Gate H accessibility reaches `4/4` with evidence.
3. Gate I business-contract certification is separated from frontend readiness.
4. Non-audited business routes are scored or explicitly excluded.
5. Tests, lint, typecheck, debt audit, build, and browser evidence pass for the claimed scope.
