# Top Investment Bank Standard Next Round Optimization Implementation Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `using-superpowers`, `executing-plans`, `test-driven-development`, `karpathy-guidelines`, `finance-data-quality`, `frontend-design`, and `verification-before-completion` while executing this plan.

**Goal:** Move MOSS from seven-route frontend-surface flagship readiness to a defensible top investment-bank operating standard for the exact route set that can be proven.

**Architecture:** Treat MOSS as a governed decision workbench, not a beautified dashboard. Close certification route by route through source-to-screen metric traceability, explicit golden-sample boundaries, governance-record evidence, manual audit review, business-owner approval, route-scope classification, and final institutional UX hardening.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, local MCP stdio launchers, page contracts, metric dictionary, golden-sample catalog, governance packets, Python readiness scripts, and PowerShell page verification wrappers.

---

## Current Truth

MOSS has not fully reached the top investment-bank standard yet.

Allowed claim today:

> The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

Already proven:

- The audited flagship frontend surface is ready for `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Gate H automated accessibility evidence is complete for those seven routes.
- `python scripts/codex_page_readiness.py --all` currently reports `page_count=29`, `static_pass_count=29`, `run_supported_count=17`, `business_owner_approval_pending_count=3`, and `business_owner_approval_action_item_count=35`.
- `/product-category-pnl`, `/pnl-attribution`, and `/ledger-pnl` have machine-checkable approval blockers rather than hidden certification gaps.

Still blocking the final top-bank claim:

- `/product-category-pnl` has the strongest route evidence, but it remains `evidence-pending`: `closure_approved=false`, business-owner approval is not captured, `GS-PROD-CAT-PNL-A/approval.md` still says `captured-awaiting-approval` while readiness reports the golden boundary as approved, and `docs/pnl/product-category-closure-checklist.md` still has ten `PARTIAL` units. The product-category approval checker now directly reads the golden approval artifact and closure checklist artifact: `--require-captured` requires `Status: approved` plus non-placeholder owner, approver, and approval date, and `ready_for_owner_approval=true` with no `PARTIAL` or `NOT_TRUSTED` units. A completed owner template alone is not enough.
- `/pnl-attribution` has direct-record readiness, 5/5 catalog/date samples, and an owner evidence packet, but `formal_use_allowed=false`, `closure_approved=false`, `GS-PNL-ATTR-WB-A` is primary workbench DTO evidence only, and business-owner approval is pending.
- `/ledger-pnl` has a field-complete dry-run governance candidate plus sign-off, governance-audit, and owner-evidence packets. The approval checker now verifies those packet paths and artifact existence, but there is still no authorized written direct page/API governance record, no dedicated ledger summary golden sample, no manual audit closure, and no captured business-owner approval.
- `/bond-analysis` is frontend-ready and now has a direct route-specific Gate I gap lane: `GAP-BOND-ANALYSIS-PAGE`, `overall_status=static-pass`, `approval_status=gap_or_observational`, `formal_use_allowed=false`, no golden samples, and run-supported smoke/verification commands. It is still not certified because direct page contract closure, golden-sample boundary, governance validation, manual audit review, and business-owner approval remain missing; `/bond-dashboard` evidence still must not be reused.
- `/cross-asset`, `/macro-toolkit`, and `/stock-analysis` are still frontend-only under Gate I.
- Gate J has not classified the wider business route set, so the final claim cannot expand beyond the audited seven-route surface.

## Target Standard

A route can be called top investment-bank-grade only when all of this is true:

1. The first screen answers the primary business question, trust state, supporting evidence, and next action.
2. Every displayed decision metric exposes source, date, unit, precision, status, stale/fallback/no-data behavior, and formal/candidate boundary.
3. Every critical value is traced through API response -> adapter/model -> state/selector -> component -> chart/table.
4. MCP metric-contract, lineage, catalog/date, governance, or documented fallback-risk evidence supports the business claim.
5. Golden-sample scope is explicit and never overused to certify unapproved surfaces.
6. Business-owner approval is captured by a strict checker before route closure.
7. Desktop `1440px`, tablet `768px`, and mobile `390px` checks show no fallback route, no permanent loading, no document-level horizontal overflow, and no blocking console errors.
8. Non-audited routes are classified or explicitly excluded so the certification claim cannot silently expand.

## RALPLAN-DR Summary

### Principles

1. Business correctness outranks visual polish.
2. Claim only the route scope that evidence proves.
3. Preserve governance uncertainty until the correct evidence closes it.
4. Certify one high-value route deeply, then scale the workflow.
5. Keep visual hardening tied to decision quality, not decoration.

### Decision Drivers

1. Evidence authority: MCP evidence, golden samples, governance records, and business approval outrank local inference.
2. Auditability: every displayed number must be explainable from source to screen.
3. Claim discipline: frontend readiness, business-contract readiness, and signed business approval are separate states.

### Options Considered

**Option A: Certify `/product-category-pnl` first.**

- Pros: strongest current evidence, formal/governed status, direct-record readiness, 20 expanded anchors, and a strict approval checker already exist.
- Cons: cannot complete without resolving approval artifact mismatch and manual owner sign-off.

**Option B: Push `/ledger-pnl` governance write first.**

- Pros: directly attacks a known blocker.
- Cons: real governance writes require workflow authorization and should not be forced from this optimization lane.

**Option C: Run final visual polish first.**

- Pros: immediate perceived improvement.
- Cons: does not close the real certification blocker and could hide governance uncertainty.

**Chosen path:** Option A first, then `/pnl-attribution`, then `/ledger-pnl`, then Gate I scale-out, Gate J route-scope classification, and final institutional UX hardening.

## Task 1: Make `/product-category-pnl` Golden Approval Mismatch Machine-Checkable

**Status:** Complete. `scripts/codex_page_readiness.py` now reads `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` and exposes `golden_sample_approval_artifact_mismatch=true` without promoting approval status or blocking static readiness.

**Purpose:** Stop a hidden inconsistency from being mistaken for certification. Readiness currently reports `golden_sample_boundary=approved`, but `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` says `captured-awaiting-approval` with owner, approver, and approved-at fields as `TBD`.

**Files:**

- Modify: `scripts/codex_page_readiness.py`
- Modify: `tests/test_codex_page_readiness_gate.py`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Inspect/update: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
- Inspect/update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Inspect/update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Step 1: Write the failing readiness test**

Status: Complete. RED failed with `KeyError: 'golden_sample_approval_artifact_status'`.

Add a test proving `build_page_readiness_report("product-category-pnl")` exposes the approval artifact metadata:

- `golden_sample_approval_artifact_status="captured-awaiting-approval"`
- `golden_sample_approval_artifact_owner="TBD"`
- `golden_sample_approval_artifact_approver="TBD"`
- `golden_sample_approval_artifact_approved_at="TBD"`
- `golden_sample_approval_artifact_mismatch=true`

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

Expected: fail before implementation.

**Step 2: Implement a minimal approval artifact parser**

Status: Complete.

Add a small helper in `scripts/codex_page_readiness.py` that reads only the configured golden-sample `approval.md` fields for product-category PnL. Do not mark the sample approved. Do not edit `approval.md` unless signed evidence exists.

**Step 3: Surface mismatch without promoting or blocking static readiness**

Status: Complete. `overall_status` remains `static-pass`; the new payload fields expose the certification blocker.

Keep `overall_status=static-pass` if existing static gates pass, but expose the mismatch in the readiness payload and business-owner approval lane so certification cannot be claimed silently.

**Step 4: Update audit wording**

Status: Complete for the scorecard, product-category boundary JSON, and certification roadmap.

Update the scorecard and product-category boundary JSON to say the mismatch is machine-checkable and still blocks final certification.

**Acceptance Criteria:**

- Readiness payload exposes the approval artifact status and mismatch.
- `/product-category-pnl` remains `evidence-pending`.
- No metric definition, formal-use flag, golden-sample approval, governance record, or business-owner approval is promoted.

**Verification:**

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py -q
python -m pytest tests/test_product_category_pnl_business_owner_approval_status.py -q
python scripts/codex_page_readiness.py --page-slug product-category-pnl
python scripts/check_product_category_pnl_business_owner_approval.py
python -m json.tool docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json > $null
git diff --check scripts/codex_page_readiness.py tests/test_codex_page_readiness_gate.py docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json docs/audits/2026-06-05-institutional-frontend-scorecard.md docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md
```

## Task 2: Prepare `/product-category-pnl` First-Certification Packet

**Purpose:** Turn the strongest route into the first real certification candidate, while keeping every remaining blocker visible.

**Status:** In progress. `docs/pnl/product-category-pnl-first-certification-packet.md` now packages the `MTR-PCP-001` through `MTR-PCP-012` source-to-screen trace and owner action items. `scripts/check_product_category_pnl_business_owner_approval.py` now requires a completed owner template, a directly approved `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`, and a closure checklist with no `PARTIAL` or `NOT_TRUSTED` units before captured approval can pass. The current closure checklist artifact reports `ready_for_owner_approval=false`, `partial_count=10`, and `open_unit_count=10`. The page remains `evidence-pending`; the packet does not approve closure, write governance records, prove page execution, or capture business-owner approval.

**Files:**

- Inspect: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `docs/pnl/product-category-page-truth-contract.md`
- Inspect: `docs/metric_dictionary.md`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`

**Steps:**

1. Trace `MTR-PCP-001` through `MTR-PCP-012` from `/ui/pnl/product-category` response -> page model -> component -> readout/table.
2. Confirm unit, precision, date, stale/fallback/no-data, null-vs-zero, scenario-vs-formal, and result-meta visibility.
3. Keep the liability fallback branch as model-boundary evidence unless production selectors naturally reach it.
4. Keep all ten closure-checklist units as `PARTIAL` unless direct evidence closes each unit.
5. Prepare a business-owner packet listing exact remaining decisions, not a blank "please approve" request.

**Acceptance Criteria:**

- The route has a complete source-to-screen trace table for all approved product-category metric IDs. Status: complete for the first-certification owner packet.
- The remaining blockers are exact and owner-actionable.
- The page is not certified until `closure_approved=true`, the golden approval artifact is directly approved, the closure checklist has no `PARTIAL` or `NOT_TRUSTED` units, and the approval checker returns captured approval.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug product-category-pnl
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
python -m pytest tests/test_product_category_pnl_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx
npm run debt:audit
```

## Task 3: Close `/pnl-attribution` Boundary Without Overclaiming

**Purpose:** Keep `/pnl-attribution` moving from strong evidence-pending status toward certification while preserving its mixed-surface boundaries.

**Status:** Complete for the owner-facing evidence packet. `docs/pnl/pnl-attribution-owner-evidence-packet.md` now packages the candidate boundary, dry-run governance status, 5/5 catalog/date table list, DTO-only golden-sample boundary, and 11 business-owner action items. The approval template now validates this owner evidence packet path before captured approval. `/pnl-attribution` remains `evidence-pending`; the packet does not approve closure, write governance records, prove page execution, or capture business-owner approval.

**Files:**

- Inspect: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`
- Inspect: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Inspect: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- Inspect: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Inspect: `tests/golden_samples/GS-PNL-ATTR-WB-A/`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Inspect: `frontend/src/test/PnlAttributionPage.test.tsx`

**Steps:**

1. Re-run readiness, governance dry-run, and approval checker.
2. Record that `GS-PNL-ATTR-WB-A` covers the primary workbench DTO only.
3. Keep advanced attribution, Campisi, formal PnL overview, and executive overlay surfaces outside that golden-sample scope unless new evidence exists.
4. Keep `formal_use_allowed=false` and `closure_approved=false`.
5. Convert the 11 approval action items into an owner-facing evidence packet. Status: complete for `docs/pnl/pnl-attribution-owner-evidence-packet.md`.

**Acceptance Criteria:**

- `/pnl-attribution` remains honest: `evidence-pending` unless signed approval and manual audit closure exist.
- The primary workbench DTO boundary is not stretched into full-page certification.
- The next business-owner decision is crisp enough to action.

**Verification:**

```powershell
python scripts/codex_page_readiness.py --page-slug pnl-attribution
python scripts/emit_pnl_attribution_governance_record.py
python scripts/check_pnl_attribution_business_owner_approval.py
python -m pytest tests/test_pnl_attribution_governance_record.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py -q
cd frontend
npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx
npm run debt:audit
```

## Task 4: Keep `/ledger-pnl` Governance Closure Authorized And Auditable

**Purpose:** Advance ledger evidence without casually writing governance records or promoting candidate metrics.

**Status:** Complete for the owner-facing evidence lane. `docs/pnl/ledger-pnl-sign-off-packet.md`, `docs/pnl/ledger-pnl-governance-audit-packet.md`, and `docs/pnl/ledger-pnl-owner-evidence-packet.md` now exist; `scripts/check_ledger_pnl_business_owner_approval.py` validates the reviewed packet paths and verifies those artifacts exist before captured approval can pass. `/ledger-pnl` remains `evidence-pending`; the packets do not approve closure, write governance records, prove page execution, promote formal use, or capture business-owner approval.

**Files:**

- Inspect: `scripts/emit_ledger_pnl_governance_record.py`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json`
- Inspect: `docs/pnl/ledger-pnl-sign-off-packet.md`
- Inspect: `docs/pnl/ledger-pnl-governance-audit-packet.md`
- Inspect: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Inspect: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Inspect: `scripts/check_ledger_pnl_business_owner_approval.py`

**Steps:**

1. Re-run `python scripts/emit_ledger_pnl_governance_record.py` in dry-run mode.
2. Confirm `record_write_status=not_requested` and `preflight.validation.validation_status=ready_for_audit_review`.
3. Keep `python scripts/emit_ledger_pnl_governance_record.py --write` as workflow-authorized only.
4. Keep `MTR-LPN-001` through `MTR-LPN-003` as candidate metrics until dedicated summary golden sample and approval evidence exist.
5. Record source-anchor limitations such as missing written direct records, missing expanded lineage closure, or unknown table/date evidence as risks.
6. Keep the approval checker strict: reviewed packet fields must match the expected paths and the referenced sign-off, audit, and owner evidence packets must exist.

**Acceptance Criteria:**

- Ledger dry-run remains repeatable and safe.
- Ledger owner evidence is owner-actionable without implying approval.
- No governance write is performed without explicit workflow authority.
- `/ledger-pnl` remains `evidence-pending` until written record validation, manual review, golden-sample scope, and business-owner approval close.

**Verification:**

```powershell
python scripts/emit_ledger_pnl_governance_record.py
python scripts/ledger_pnl_owner_evidence_packet.py
python scripts/check_ledger_pnl_business_owner_approval.py
python scripts/codex_page_readiness.py --page-slug ledger-pnl
python scripts/codex_page_readiness.py --all
python -m pytest tests/test_ledger_pnl_governance_record.py tests/test_ledger_pnl_business_owner_approval_status.py tests/test_ledger_pnl_signoff_packet.py tests/test_ledger_pnl_owner_evidence_packet.py tests/test_codex_page_readiness_gate.py -q
```

## Task 5: Scale Gate I Across The Remaining Flagship Routes

**Purpose:** Convert the seven-route flagship claim from frontend-surface readiness to business-contract-aware status.

**Routes:**

1. `/cross-asset`
2. `/macro-toolkit`
3. `/stock-analysis`
4. `/bond-analysis`

`/bond-analysis` status: partially complete for machine-checkable gap routing. The next work is no longer adding a readiness slug; it is creating or mapping a direct page contract, defining the fixed-income golden-sample boundary, collecting direct `/api/bond-analytics/*` catalog/lineage/governance evidence, and preparing a manual audit plus business-owner approval lane without borrowing `/bond-dashboard` evidence.

**Per-route steps:**

1. State the page's primary business question.
2. List displayed decision metrics, evidence badges, stale/fallback/no-data states, and next actions.
3. Trace each critical value through API response -> adapter/model -> state/selector -> component -> chart/table.
4. Collect or route MCP metric-contract, lineage, catalog/date, and governance evidence where configured.
5. Classify the route as `business-contract-certified`, `evidence-pending`, `gate-i-gap`, or `frontend-only`.
6. Record unavailable MCP servers and fallback evidence explicitly.

**Acceptance Criteria:**

- Every flagship route has a Gate I status row.
- No route is certified from screenshots, component tests, or browser smoke alone.
- Formal, candidate, temporary-exception, supporting-only, stale, fallback, and no-data evidence remain visually and semantically separate.

## Task 6: Gate J Route-Scope Classification

**Purpose:** Prevent a seven-route claim from becoming accidental whole-system certification.

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Per-route steps:**

1. Score the route against `docs/frontend-institutional-standard.md`.
2. Classify as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
3. Apply only page-local corrections when a route is close to closure.
4. Browser verify desktop `1440px`, tablet `768px`, and mobile `390px` before promotion.

**Acceptance Criteria:**

- Every named candidate route is scored or explicitly excluded.
- The final claim names the exact covered route set.
- Non-audited routes are not silently included.

## Task 7: Final Institutional UX Hardening

**Purpose:** Add the last layer of top-bank feel after evidence gates stop drifting.

**Scope:**

- Typography density and hierarchy.
- Token alignment and palette balance.
- Compact first-screen decision strips.
- Mobile decision readout order before dense tables.
- Empty, stale, fallback, blocked, no-data, temporary-exception, and candidate states.
- Keyboard focus clarity and non-color state cues.
- No overlap, awkward truncation, or document-level horizontal overflow at `390px`, `768px`, and desktop.

**Rules:**

- Do not add decorative hero sections.
- Do not use marketing-style card stacks.
- Do not hide governance uncertainty to make the page cleaner.
- Do not change finance formulas.
- Do not rebuild global design-system layers unless a page-local fix cannot solve the issue.

**Verification for changed frontend routes:**

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

## Final Certification Packet

Create or update a final status packet only after Tasks 1 through 7 are complete.

The packet must state:

- Which routes are frontend-ready.
- Which routes are business-contract-certified.
- Which routes remain evidence-pending, gate-i-gap, frontend-only, or out-of-scope.
- Which golden samples are approved, pending, limited, or non-reusable.
- Which governance records are written, dry-run only, missing, or ready for audit review.
- Which business-owner approvals are captured or pending.
- Which commands and browser checks were run for the claimed scope.

Final claim rule:

Do not say "MOSS has fully reached top investment-bank standard" unless Gate I certification and Gate J route-scope classification are both complete for the exact claimed scope.

## ADR

**Decision:** Use `/product-category-pnl` as the first certification candidate because it has the strongest current evidence, but first make its golden-sample approval artifact mismatch machine-checkable.

**Drivers:** Strongest route evidence, highest chance of a real first certification, and lowest tolerance for hidden mismatch.

**Alternatives considered:** Ledger governance write first; PnL attribution first; visual polish first.

**Why chosen:** Product-category PnL is closest to true certification, while the golden approval mismatch is concrete, testable, and can be closed without changing business formulas or approvals.

**Consequences:** The next round may still end with `evidence-pending` if business-owner approval is not captured. That is acceptable and more honest than a false top-standard claim.

**Follow-ups:** After product-category mismatch evidence is wired, proceed to owner packet preparation, then repeat the closure workflow for `/pnl-attribution` and `/ledger-pnl`.
