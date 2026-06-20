# Top Investment Bank Standard Next Optimization Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `using-superpowers`, `executing-plans`, `finance-data-quality`, `frontend-design`, `karpathy-guidelines`, and `verification-before-completion` while executing this plan.

**Goal:** Move MOSS from seven-route frontend-surface flagship readiness to a defensible top investment-bank operating standard with business-contract evidence, route-scope closure, and final institutional UX hardening.

**Architecture:** Treat the visible workbench as a decision surface, not a decoration layer. Keep changes page-scoped and evidence-first. Promote a route only when its displayed numbers have source-to-screen traceability, its business status is explicit, and its desktop/tablet/mobile behavior has reproducible verification.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, local MCP evidence servers, page contracts, metric dictionary, golden-sample catalog, governance evidence packets, and existing readiness scripts.

---

## Current Truth

MOSS has not yet fully reached the top investment-bank standard.

What is already strong:

- The seven audited flagship routes are frontend-surface ready: `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Gate H automated accessibility evidence is complete for the seven-route surface.
- Standard frontend checks have passed in the recorded slices: targeted tests, live-route smoke, lint, typecheck, debt audit, build, and browser evidence.
- `/ledger-pnl` has MCP-backed Gate I trace evidence collected.

What still blocks the full claim:

- `/ledger-pnl` remains `evidence-pending`, not `business-contract-certified`, because lineage evidence reports `manual_review_blocker_count=1`, blocker `direct_page_api_record_fields`, and `closure_approved=false`.
- `MTR-LPN-001` through `MTR-LPN-003` remain candidate metrics with `pending_confirmation=true`.
- No dedicated golden sample currently approves `/ledger-pnl` summary metrics for formal use.
- Gate I evidence has not yet been repeated across the seven-route flagship surface.
- Gate J has not classified or excluded the remaining non-audited business routes.

## Standard To Hit

A route can be called top investment-bank-grade only when all of this is true:

1. The first screen answers trust, conclusion, support, and next action.
2. Each decision metric exposes source, date, unit, precision, status, stale/fallback/no-data behavior, and formal/candidate boundary.
3. The displayed value is traced through API response -> adapter/model -> state/selector -> component -> chart/table.
4. MCP evidence supports the business contract, or the route stays `evidence-pending` with residual risk recorded.
5. Desktop, tablet, and mobile have no fallback route, no permanent loading, no document-level horizontal overflow, and no blocking console errors.
6. Keyboard users can reach the same decision state and status cues are not color-only.
7. Business-owner approval, formal-use status, metric definitions, and governance markers are never changed without evidence authority.

## RALPLAN-DR Summary

### Principles

1. Business correctness outranks visual polish.
2. Claim only the scope that is proven.
3. Preserve governance uncertainty until evidence closes it.
4. Certify one route deeply, then scale the workflow.
5. Keep every change small, reviewable, and reversible.

### Decision Drivers

1. Evidence authority: MCP contracts, lineage, catalog/date evidence, and golden samples outrank local inference.
2. Auditability: every displayed number must be explainable from source to screen.
3. Route closure: the system-level claim requires both flagship-route certification and non-audited route classification.

### Options Considered

**Option A: Close Gate I before more visual work.**

- Best for trust and audit readiness.
- Slower to show visible improvements.

**Option B: Expand Gate J first.**

- Quickly clarifies broader route scope.
- Risky if the certification workflow is not proven first.

**Option C: Do a visual polish pass first.**

- Improves perceived quality.
- Does not close the top-standard blocker because business evidence remains unresolved.

**Chosen path:** Option A, then Gate I scaling, then Gate J, then a final visual/interaction polish pass.

## Execution Plan

### Task 1: Route `/ledger-pnl` Direct Governance Record Blocker

**Purpose:** Turn the current `direct_page_api_record_fields` blocker into concrete missing fields, failed groups, owners, and next actions.

**Files:**

- Read: `docs/MCP_RUNBOOK.md`
- Read: `tests/test_project_mcp_servers.py`
- Read: `scripts/mcp/moss_project_mcp.py`
- Read: `docs/audits/2026-06-05-ledger-pnl-gate-i-mcp-evidence.json`
- Create: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Steps:**

1. Call the local read-only MCP evidence flow for `/ledger-pnl`:
   - `get_page_governance_record_requirements`
   - `validate_page_governance_records`
   - `get_page_governance_record_blueprint`
   - `get_page_governance_gap_queue`
2. Save missing fields, failed required field groups, existing direct-record state, and recommended remediation lane.
3. Update the scorecard with exact blocker details.
4. Keep `/ledger-pnl` as `evidence-pending`.
5. Do not write governance records or approve formal use in this task.

**Acceptance Criteria:**

- The blocker is no longer described only as `direct_page_api_record_fields`; exact missing fields and failed groups are recorded.
- The next remediation lane is explicit: create direct record, complete existing record, repair primary page/API anchor, or manual audit review.
- No metric, formal-use, approval, or governance status is promoted.

**Verification:**

```powershell
Select-String -Path docs/audits/2026-06-05-institutional-frontend-scorecard.md -Pattern "direct_page_api_record_fields|missing required|failed required|evidence-pending"
git diff --check
```

### Task 2: Apply Gate I Template To `/pnl-attribution`

**Purpose:** Certify or explicitly block the highest-value PnL attribution page using the same evidence discipline.

**Files:**

- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Inspect: `frontend/src/test/PnlAttributionPage.test.tsx`
- Inspect: relevant PnL attribution API/domain client files
- Read/update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Create: `docs/audits/2026-06-05-pnl-attribution-gate-i-mcp-evidence.json`

**Steps:**

1. Collect metric-contract trace bundle, lineage packet, and catalog/date evidence.
2. Split evidence rows by product-category lens, formal FI lens, TPL hybrid exception, and Campisi boundary.
3. Trace displayed metrics through API -> client/model -> state -> component -> table/chart.
4. Preserve approval blockers and temporary exceptions.
5. Add tests only if a real display or boundary gap is uncovered.

**Acceptance Criteria:**

- `/pnl-attribution` status is either `business-contract-certified` with evidence or `evidence-pending` with exact blocker details.
- Comparison mode, view period, quality flag, fallback text, and next action remain visible.
- Product-category, formal FI, TPL, and Campisi boundaries are not collapsed into one ambiguous claim.

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

### Task 3: Scale Gate I Across The Seven Flagship Routes

**Purpose:** Make the flagship claim business-contract aware instead of only frontend-surface ready.

**Routes:**

1. `/ledger-pnl`
2. `/pnl-attribution`
3. `/product-category-pnl`
4. `/bond-analysis`
5. `/cross-asset`
6. `/macro-toolkit`
7. `/stock-analysis`

**Steps per route:**

1. Collect MCP metric-contract, lineage, and catalog/date evidence where configured.
2. Identify displayed decision metrics and status markers.
3. Fill a route trace table for API response -> adapter/model -> state/selector -> component -> chart/table.
4. Mark the route as `business-contract-certified`, `evidence-pending`, or `frontend-only`.
5. Record unavailable MCP servers and fallback evidence explicitly.

**Acceptance Criteria:**

- Every flagship route has a business-contract status row.
- No route is certified from visual evidence alone.
- Candidate metrics and formal metrics are visibly separated.

### Task 4: Close `/product-category-pnl` Residual Branch Boundary

**Purpose:** Resolve the one remaining liability fallback-boundary question without presenting synthetic payloads as production browser proof.

**Files:**

- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- Inspect: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Steps:**

1. Find whether model-derived rows can reach `product-category-liability-side-detail-table` without fabricating production evidence.
2. If current selectors make the fallback table naturally unreachable, record that as model-boundary evidence.
3. Keep synthetic branch payloads out of production browser proof.
4. Preserve raw tables and mobile readouts.

**Acceptance Criteria:**

- Either the branch is naturally browser-proven or the scorecard names the model-boundary reason it should not be production-browser-proven with synthetic data.
- No fake fallback payload is represented as production evidence.

### Task 5: Gate J Route-Scope Classification

**Purpose:** Prevent a seven-route claim from being mistaken for whole-system certification.

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Steps per route:**

1. State the single primary business question.
2. Score against `docs/frontend-institutional-standard.md`.
3. Classify as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
4. Apply only the smallest page-local correction when a route is near closure.
5. Browser verify desktop `1440px`, tablet `768px`, and mobile `390px`.

**Acceptance Criteria:**

- Every named candidate route is scored or explicitly excluded.
- The final system claim names the exact covered route set.
- No non-audited route is silently included in top-standard language.

### Task 6: Final Institutional UX Hardening

**Purpose:** Add the last layer of polish only after evidence gates stop drifting.

**Scope:**

- Typography density and hierarchy consistency.
- Token alignment and palette balance.
- Mobile decision readout order.
- Empty, stale, fallback, blocked, and no-data states.
- Keyboard focus and status cue clarity.
- Runtime cleanliness and page-level no-overlap checks.

**Steps:**

1. Run a route-by-route visual QA pass after Gate I/J updates.
2. Fix only issues that affect decision-making, trust, accessibility, or layout stability.
3. Avoid decorative hero, gradient, card-heavy, or marketing-style patterns.
4. Record screenshots and measurement JSON for changed pages.

**Acceptance Criteria:**

- First screen remains business-first, not decorative.
- Text does not overlap, truncate awkwardly, or obscure adjacent content at `390px`, `768px`, or desktop.
- The palette remains restrained but not one-note.
- Visual changes do not change metric definitions or status semantics.

### Task 7: Final Certification Packet

**Purpose:** Produce the artifact that answers whether MOSS has reached the top investment-bank standard.

**Files:**

- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
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
- Screenshots/measurement artifact paths.
- Remaining risks and next owner lane.

**Final Claim Rule:**

Only say MOSS has reached the top investment-bank standard for the exact route set where Gate I and Gate J are both closed. Until then, use this wording:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

## Verification Matrix

Run narrow checks after each changed route, then widen only when the change crosses shared contracts.

```powershell
cd frontend
npm run test -- <page-specific-test-file>
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run lint
npm run typecheck
npm run debt:audit
npm run build
```

For backend or MCP evidence changes:

```powershell
python -m pytest tests/test_project_mcp_servers.py -q
python -m pytest <targeted-business-tests> -q
```

Before any completion claim:

```powershell
git diff --check
```

## Non-Goals

- No database schema changes.
- No auth, permission, scheduler, queue, cache, or global SDK changes.
- No backend formula rewrite.
- No metric definition rewrite without MCP and golden-sample authority.
- No retirement of stale, fallback, no-data, temporary-exception, formal-use, or governance markers without evidence.
- No broad app-wide refactor.

## Next Immediate Slice

Task 1 evidence routing has produced:

1. `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`
2. An updated `/ledger-pnl` scorecard row with exact blocker details.
3. A clear remediation lane: create direct PAGE/API governance record plus supporting lineage, then preflight.
4. No false promotion from `evidence-pending` to `business-contract-certified`.
5. `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`, which shows current summary `result_meta` now includes `cache_key=ledger_pnl.summary:2026-05-31:ALL` and the candidate preflights as `ready_for_audit_review`.
6. `scripts/emit_ledger_pnl_governance_record.py`, which turns the field-complete candidate into a repeatable governance-record dry-run and explicit-write workflow.

Next execution should run the ledger governance generator in dry-run mode, route the explicit `--write` step through the approved governance workflow, create or locate the written direct PAGE/API governance record plus supporting lineage, then rerun validation and manual audit review. Keep `formal_use_allowed=false` until closure evidence and business-owner review support a later status change.
