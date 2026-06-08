# Top Investment Bank Standard Continuation Execution Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from seven-route frontend-surface readiness to evidence-backed top investment-bank certification for the exact route scope that can be proven.

**Architecture:** Treat the workbench as a governed decision system. Close one route at a time through business-contract evidence, source-to-screen traceability, approval gates, route-scope classification, and only then final institutional UX hardening.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright/browser checks, Ant Design, MOSS design tokens, local MCP stdio launchers, page contracts, metric dictionary, golden-sample catalog, governance evidence packets, Python readiness scripts, and PowerShell page verification wrappers.

---

## Current Assessment

The target has not been fully achieved yet.

Already proven:

- Seven flagship routes are frontend-surface ready: `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Gate H automated accessibility evidence is complete for the seven-route frontend surface.
- `/ledger-pnl` has Gate I MCP trace evidence and a field-complete governance-record preflight candidate.
- The `/ledger-pnl` candidate includes `cache_key=ledger_pnl.summary:2026-05-31:ALL` and preflights as `ready_for_audit_review`.

Still blocking the full top-standard claim:

- `/ledger-pnl` has no written direct page/API governance record in the real governance stream.
- `/ledger-pnl` has no completed manual audit review or business-owner approval.
- `MTR-LPN-001` through `MTR-LPN-003` remain candidate metrics with no dedicated summary golden sample.
- Gate I has not been repeated across the seven flagship routes.
- Gate J has not classified the remaining business routes or excluded them from the certification scope.

## Definition Of Done

Do not claim top investment-bank standard until all of this is true for the claimed route set:

1. Each page has a single primary business question and the first screen answers conclusion, trust, support, and next action.
2. Each displayed decision metric exposes source, date, unit, precision, status, stale/fallback/no-data behavior, and formal/candidate boundary.
3. Each decision metric is traced through API response -> adapter/model -> state/selector -> component -> chart/table.
4. MCP metric-contract, lineage, catalog/date, and governance evidence support the business claim, or the page remains `evidence-pending`.
5. Business-owner approval is captured by a checked template before closure.
6. Desktop, tablet, and mobile checks show no fallback route, no permanent loading, no document-level horizontal overflow, and no blocking console errors.
7. Non-audited routes are classified or explicitly excluded, so the final claim cannot silently overstate coverage.

## Task 1: Add `/ledger-pnl` Business-Owner Approval Gate

**Purpose:** Make the missing approval lane explicit and machine-checkable without approving the page.

**Files:**

- Create: `tests/test_ledger_pnl_business_owner_approval_status.py`
- Create: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Create: `scripts/check_ledger_pnl_business_owner_approval.py`
- Modify: `scripts/codex_page_readiness.py`
- Modify: `tests/test_codex_page_readiness_gate.py`

**Step 1: Write the failing checker tests**

Add tests modeled on `tests/test_pnl_attribution_business_owner_approval_status.py`.

Required pending-template assertions:

- `page_id`: `PAGE-LEDGER-PNL-001`
- `page_slug`: `ledger-pnl`
- `primary_api`: `/api/ledger-pnl/summary`
- `approval_status`: `pending`
- `business_owner_approval_captured`: `False`
- `formal_use_allowed`: `False`
- `closure_approved`: `False`
- `remaining_blockers` starts with `business_owner_approval`
- Required blockers include business-owner identity, decision, date, signature, governance review, no-dedicated-golden/candidate-boundary review, UI/API payload review, live smoke review, and verification rerun.

Run:

```powershell
python -m pytest tests/test_ledger_pnl_business_owner_approval_status.py -q
```

Expected: fail because the checker and template do not exist yet.

**Step 2: Create the pending approval template**

Create `docs/pnl/ledger-pnl-business-owner-approval-template.md`.

The template must say it is not an approval until completed and signed.

Required boundaries:

- Do not promote `MTR-LPN-001` through `MTR-LPN-003` to formal use.
- Do not replace formal PnL, product-category PnL, PnL bridge, or formal FI truth.
- The dedicated ledger summary golden sample is capture-ready only and does not approve the page for formal use.
- Keep `formal_use_allowed=false`.
- Keep `closure_approved=false`.

**Step 3: Implement the checker**

Create `scripts/check_ledger_pnl_business_owner_approval.py` by adapting the PnL attribution checker.

The output must include:

- `approval_field_status`
- `approval_action_items`
- `approval_action_item_count`
- `evidence_scope.approves_metric_or_page=false`
- `evidence_scope.writes_governance_records=false`
- `evidence_scope.proves_page_execution=false`
- `evidence_scope.captures_business_owner_approval=false` until fully completed.

Run:

```powershell
python -m pytest tests/test_ledger_pnl_business_owner_approval_status.py -q
```

Expected: pass.

**Step 4: Wire ledger approval into readiness**

Update `scripts/codex_page_readiness.py` so `ledger-pnl` exposes:

```powershell
python scripts/check_ledger_pnl_business_owner_approval.py
python scripts/check_ledger_pnl_business_owner_approval.py --require-captured
powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug ledger-pnl -RequireApprovalCaptured
```

Update all-page readiness expectations so pending approval pages include both `ledger-pnl` and `pnl-attribution`.

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

Expected: pass.

**Acceptance Criteria:**

- `/ledger-pnl` has an approval template and strict checker.
- Readiness reports surface the approval blockers.
- No formal-use, closure, metric, or governance status is promoted.

## Task 2: Governed `/ledger-pnl` Direct Record Workflow

**Purpose:** Move from candidate preflight to an auditable direct-record workflow while keeping writes explicit.

**Files:**

- Inspect: `scripts/emit_ledger_pnl_governance_record.py`
- Inspect: `tests/test_ledger_pnl_governance_record.py`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`

**Step 1: Re-run dry-run preflight**

Run:

```powershell
python scripts/emit_ledger_pnl_governance_record.py
```

Expected:

- `mode=dry-run`
- `record_write_status=not_requested`
- `preflight.validation.validation_status=ready_for_audit_review`
- `evidence_scope.writes_governance_records=false`

**Step 2: Keep real write as workflow-authorized only**

Do not run the real stream write unless the governance workflow authorizes it.

Allowed real command only after authorization:

```powershell
python scripts/emit_ledger_pnl_governance_record.py --write
```

**Step 3: Validate after any approved write**

After a real write, rerun local MCP validation through the existing launcher path and require:

- written direct page/API record found
- `direct_record_count >= 1`
- supporting expanded anchor lineage reviewed or explicitly blocked
- audit review status routed
- `closure_approved=false` until business-owner approval and manual review complete

**Acceptance Criteria:**

- Dry-run remains safe and repeatable.
- Real writes remain explicit.
- `/ledger-pnl` is not certified from preflight alone.

## Task 3: Close `/ledger-pnl` Supporting Lineage And Golden-Sample Boundary

**Purpose:** Resolve the evidence gap behind ledger summary cards without inventing approval.

**Files:**

- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-mcp-evidence.json`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`
- Inspect: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`
- Inspect/update only with evidence: `docs/metric_dictionary.md`
- Inspect/update only with evidence: `docs/golden_sample_catalog.md`
- Inspect/update only with evidence: `docs/page_contracts.md`

**Step 1: Reconfirm metric grain and keys**

Use the finance-data-quality workflow:

- grain: ledger summary per report date and currency basis
- natural key: `report_date`, `currency` or `ALL`, `source_surface`, `basis`
- execution identifier: `cache_key`

**Step 2: Reconcile source anchors**

Check the known anchors:

- `ledger_import_batch`
- `ledger_raw_row`
- `qdb_general_ledger_workbook`

Record whether each has date evidence, source version, rule version, and lineage support.

**Step 3: Preserve candidate wording**

If no dedicated golden sample approves ledger summary metrics, keep:

- `candidate_or_pending`
- `formal_use_allowed=false`
- `closure_approved=false`
- `evidence-pending`

**Acceptance Criteria:**

- Ledger source limitations are explicit.
- No candidate metric is promoted.
- Any `unknown_table` or missing-date finding is recorded as risk, not silently normalized.

## Task 4: Apply Gate I To `/pnl-attribution`

**Purpose:** Use the same evidence discipline on the next highest-value PnL page.

**Files:**

- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
- Inspect: `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
- Inspect: `frontend/src/test/PnlAttributionPage.test.tsx`
- Inspect: `scripts/emit_pnl_attribution_governance_record.py`
- Inspect: `scripts/check_pnl_attribution_business_owner_approval.py`
- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`

**Step 1: Collect trace and governance evidence**

Use local MCP launchers where available:

- metric contract trace bundle
- lineage evidence packet
- catalog/date evidence
- governance record validation
- audit review checklist

**Step 2: Split formal and candidate boundaries**

Do not collapse:

- product-category lens
- formal FI lens
- TPL hybrid exception
- Campisi decision-grade boundary

**Step 3: Run targeted verification**

Run:

```powershell
cd frontend
npm run test -- src/test/PnlAttributionPage.test.tsx
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run typecheck
npm run lint
npm run debt:audit
```

**Acceptance Criteria:**

- `/pnl-attribution` is either `business-contract-certified` with evidence or `evidence-pending` with exact blockers.
- Business-owner approval remains pending unless the completed template passes strict checker.

## Task 5: Scale Gate I Across Seven Flagship Routes

**Purpose:** Convert the flagship claim from visual readiness to business-contract-aware readiness.

**Routes:**

1. `/ledger-pnl`
2. `/pnl-attribution`
3. `/product-category-pnl`
4. `/bond-analysis`
5. `/cross-asset`
6. `/macro-toolkit`
7. `/stock-analysis`

**Per-route steps:**

1. Identify the primary business question.
2. List displayed decision metrics and status markers.
3. Trace API response -> adapter/model -> state/selector -> component -> chart/table.
4. Collect MCP metric-contract, lineage, catalog/date, and governance evidence where configured.
5. Classify as `business-contract-certified`, `evidence-pending`, or `frontend-only`.
6. Record unavailable MCP servers and fallback evidence.

**Acceptance Criteria:**

- Every flagship route has a Gate I status row.
- No route is certified from browser screenshots alone.
- Candidate and formal metrics remain visibly separated.

## Task 6: Gate J Route-Scope Classification

**Purpose:** Prevent the seven-route claim from becoming an unproven full-system claim.

**Candidate order:**

1. `/balance-movement-analysis`
2. `/balance-analysis`
3. `/risk-tensor`
4. `/kpi-performance`
5. Dashboard/workbench home decision surfaces

**Files:**

- Inspect: `docs/frontend-institutional-standard.md`
- Inspect/update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Inspect route-specific page/test files only as needed.

**Per-route steps:**

1. State the page's primary business question.
2. Score against the institutional standard.
3. Classify as `flagship-ready`, `releaseable-watch`, `evidence-pending`, or `out-of-scope`.
4. Apply only page-local corrections if the route is near closure.
5. Browser verify desktop `1440px`, tablet `768px`, and mobile `390px`.

**Acceptance Criteria:**

- Every named candidate route is scored or excluded.
- Final claim names the exact covered route set.
- Non-audited routes are not silently included.

## Task 7: Final Institutional UX Hardening

**Purpose:** Add the last visual and interaction layer after evidence gates stop moving.

**Scope:**

- typography density
- token alignment
- mobile decision readout order
- empty/stale/fallback/blocked/no-data states
- keyboard focus clarity
- status cues that are not color-only
- no overlap or truncation at `390px`, `768px`, and desktop

**Rules:**

- No decorative hero treatment.
- No marketing-style card stacks.
- No finance formula changes.
- No governance-marker retirement.
- No global design-system rebuild unless a page-local fix cannot solve the issue.

**Verification:**

Run route-specific tests first, then:

```powershell
cd frontend
npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx
npm run typecheck
npm run lint
npm run debt:audit
npm run build
```

Browser evidence must include:

- desktop `1440px`
- tablet `768px`
- mobile `390px`
- status `200`
- no fallback route
- no permanent busy state
- no document-level horizontal overflow
- no blocking console errors

## Task 8: Final Certification Packet

**Purpose:** Produce the artifact that can honestly answer whether MOSS has reached the target.

**Files:**

- Update: `docs/audits/2026-06-05-institutional-frontend-scorecard.md`
- Update: `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- Create if useful: `docs/audits/2026-06-05-top-investment-bank-certification-status.md`

**Packet must include:**

- certified route set
- frontend-ready route set
- evidence-pending route set
- out-of-scope route set
- MCP availability and fallback-risk notes
- golden-sample status per critical metric group
- business-owner approval status
- verification commands and results
- screenshot and measurement artifact paths
- remaining risks and next owner lane

**Final claim rule:**

Use this until Gate I and Gate J are closed:

```text
The seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.
```

Only use a top investment-bank certification claim for the exact route set where Gate I and Gate J are both closed with evidence.

## Next Execution Slice

Start with Task 1.

Expected first command:

```powershell
python -m pytest tests/test_ledger_pnl_business_owner_approval_status.py -q
```

Expected first result:

- fail because `scripts/check_ledger_pnl_business_owner_approval.py` and `docs/pnl/ledger-pnl-business-owner-approval-template.md` do not exist yet.

Then implement the checker/template, wire readiness, run the targeted tests, run `git diff --check`, and keep `/ledger-pnl` as `evidence-pending`.

## Non-Goals

- No database schema changes.
- No auth, permission, scheduler, queue, cache, or global SDK changes.
- No backend formula rewrite.
- No real governance-stream write without workflow authorization.
- No fake golden sample approval.
- No formal-use or closure promotion without evidence.
- No broad unrelated refactor.
