# Top Investment Bank Standard Final Certification Lane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from flagship frontend readiness toward a defensible top investment-bank standard by completing one route-level business certification lane first, then scaling the same evidence model.

**Architecture:** Treat every page as a governed decision surface with separate gates for frontend quality, metric contract, source lineage, golden sample approval, manual audit review, live browser evidence, and business-owner sign-off. `/product-category-pnl` is the first certification candidate because it already has direct readiness evidence, strict approval checking, owner packets, and a known blocker ledger.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright, Ant Design, page contracts, metric dictionary, golden samples, Python readiness scripts, approval checkers, local MCP evidence launchers, and MOSS frontend design tokens.

---

## Current Verified State

Fresh checks on 2026-06-06 show:

- Route-scope ledger: `39` routes.
- `business-contract-certified=0`.
- `evidence-pending=12`.
- `gate-i-gap=2`.
- `frontend-ready=5`.
- `frontend-only=10`.
- `not-started=10`.
- `/product-category-pnl` is `static-pass`, but remains `evidence-pending`.
- `/product-category-pnl` has `business_owner_approval_captured=false`.
- `/product-category-pnl` has `closure_approved=false`.
- `GS-PROD-CAT-PNL-A/approval.md` remains `captured-awaiting-approval` with placeholder owner, approver, and approval date.
- Product-category closure checklist still has `10` units, all `PARTIAL`.
- Product-category blocker ledger has `16` blockers and `14` approval action items.

Allowed claim:

> MOSS has several flagship-ready frontend surfaces and a governed first certification lane. No route is yet business-contract-certified.

Forbidden claim:

> MOSS, or `/product-category-pnl`, has already reached full top investment-bank business certification.

## Target Standard

A route reaches the target only when all gates pass:

1. First screen answers trust state, primary business conclusion, supporting evidence, blocker, and next action.
2. Every critical metric exposes source, date, unit, precision, stale/fallback/no-data state, and formal/candidate boundary.
3. Critical values trace from API response to adapter/model, selector/state, component, and visible table/chart.
4. Page contract, metric dictionary, lineage, catalog/date evidence, and governance readiness are documented.
5. Golden sample approval is direct, non-placeholder, and scoped to the captured sample.
6. Manual audit review is closed.
7. Business-owner approval is captured by the strict checker.
8. Browser evidence passes desktop, tablet, and mobile without fallback route, permanent loading, horizontal overflow, or blocking console errors.
9. Route-scope classification prevents one page claim from becoming a whole-system claim.

## Non-Negotiable Boundaries

- Do not change finance formulas to make evidence pass.
- Do not promote `formal_use_allowed`, `closure_approved`, golden approval, or business-owner approval without real evidence.
- Do not run governance writes without explicit workflow authority.
- Do not borrow evidence across routes.
- Do not hide stale, fallback, no-data, pending approval, or temporary exception states for aesthetics.
- Do not touch schema, auth, scheduler, queue, cache, or global SDK layers in this lane.
- Do not commit unless explicitly requested.

## RALPLAN-DR Summary

### Principles

1. Certification is evidence, not appearance.
2. Close one route completely before broad rollout.
3. Preserve uncertainty visibly.
4. Keep business approval separate from Codex-generated artifacts.
5. Prefer narrow, reversible changes with direct verification.

### Decision Drivers

1. Highest leverage: `/product-category-pnl` is the closest route to certification.
2. Lowest trust risk: strict blockers prevent fake sign-off.
3. Fastest scale path: once one route has a complete certification lane, reuse the model for `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis`.

### Viable Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Continue visual polish across flagship pages | Quickly improves screenshots and perceived quality | Does not reduce certification blockers | Use only after evidence lanes are honest |
| B. Complete `/product-category-pnl` certification lane first | Creates the first defensible business route pattern | Final closure depends on real owner/golden/manual audit approval | Chosen critical path |
| C. Run all priority Gate I routes in parallel | Broad progress | More partial lanes, higher review risk | Use after first route pattern stabilizes |

## Task 1: Stabilize Product-Category Live Verification

**Purpose:** Separate real product-category route evidence from the currently unstable shared MCP contract verify run.

**Files:**

- Inspect: `scripts/codex-page-readiness.ps1`
- Inspect: `scripts/codex-page-smoke.ps1`
- Inspect: `scripts/codex-verify-page.ps1`
- Inspect: `tests/test_project_mcp_servers.py`
- Update if needed: `docs/pnl/product-category-closure-checklist.md`
- Update if needed: `docs/pnl/product-category-remaining-blockers.md`

**Step 1: Run product-category route smoke only**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl -CheckLive
```

Expected: route and API smoke pass, with no fallback route, permanent loading, or route mismatch.

**Step 2: Run page verify with a writable temp root**

Run:

```powershell
$env:CODEX_PYTEST_BASETEMP_ROOT='F:\MOSS-V3\.codex-tmp\pytest'
powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive
```

Expected: live route/API checks pass. If shared MCP tests still fail because of temp-dir cleanup or lingering subprocesses, record that as an environment/test-runner blocker, not a product-category UI failure.

**Step 3: Run the narrow product-category evidence pack**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_owner_decision_packet.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_business_owner_approval_status.py tests\test_golden_samples_capture_ready.py::test_product_category_companion_scenario_documents_promotion_gate tests\test_codex_page_readiness_gate.py -q
cd frontend
npm run test -- src/test/ProductCategoryAdjustmentAuditPage.test.tsx src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm run typecheck
npm run debt:audit
cd ..
```

Expected: focused product-category proof passes without promoting owner approval.

**Acceptance Criteria:**

- Product-category route evidence is fresh.
- Shared MCP verify instability is either fixed or explicitly isolated.
- No approval, closure, or golden status is promoted.

## Task 2: Close The Remaining Cursor-Safe Evidence Blocker

**Purpose:** Reduce residual risk that Codex can safely reduce without business decisions.

**Files:**

- Modify as needed: `docs/pnl/product-category-remaining-blockers.md`
- Modify as needed: `docs/pnl/product-category-closure-checklist.md`
- Modify as needed: `docs/pnl/product-category-page-truth-contract.md`
- Test as needed: `tests/test_product_category_pnl_business_owner_approval_status.py`

**Step 1: Handle Unit 10 process-wide golden/e2e unevenness**

Document that the process-wide full-repo golden/e2e gap is outside product-category route closure and must not block the route's own owner packet, while still remaining a system-wide improvement item.

**Step 2: Keep Units 2/3/5/6/8/9/10 partial where product, API, or broader matrix approval is still missing**

Do not move a unit to `CLOSED` unless every blocker in that unit is resolved or reclassified with evidence.

**Step 3: Re-run the strict approval checker**

Run:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: normal mode succeeds with pending approval; `--require-captured` fails until real owner evidence exists.

**Acceptance Criteria:**

- The blocker ledger is cleaner and more honest.
- Approval remains pending.
- The route is not overclaimed.

## Task 3: Package Human Owner Review

**Purpose:** Make the human sign-off step executable without Codex pretending to approve business truth.

**Files:**

- Generate: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Generate: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`

**Step 1: Regenerate packets**

Run:

```powershell
python scripts/product_category_pnl_first_certification_packet.py
python scripts/product_category_pnl_owner_decision_packet.py
```

**Step 2: Verify owner action items are explicit**

Confirm the packet still lists:

- owner name
- owner role
- approval decision
- approval date
- signature
- governance record review
- owner decision packet review
- golden sample reconciliation
- closure checklist review
- fallback branch boundary review
- UI/API payload review
- live smoke evidence review
- verification rerun
- evidence-pending boundary acceptance

**Step 3: Verify fake approval remains blocked**

Run:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: pending status remains until a real owner edits the approval template and golden artifact with non-placeholder values.

**Acceptance Criteria:**

- Owner can review one coherent packet set.
- Codex-generated artifacts do not capture approval.
- `business_owner_approval_captured=false` remains true until human sign-off.

## Task 4: Institutional UX Final Pass For Product-Category

**Purpose:** Bring the first certification candidate closer to the top investment-bank desk experience while preserving all evidence states.

**Files:**

- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Inspect: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Inspect: `docs/frontend-institutional-standard.md`

**Step 1: First-screen audit**

Verify the first screen shows, in order:

- trust state
- business conclusion
- evidence/date/source/unit state
- blocker or pending approval
- next action

**Step 2: Tighten scan quality**

Only change spacing, hierarchy, density, status labels, and responsive ordering when browser evidence shows a real scan or overflow issue.

**Step 3: Preserve uncertainty**

Keep fallback, stale, no-data, quality, vendor, pending approval, and `data-state-review-required` markers visible.

**Step 4: Run frontend proof**

Run:

```powershell
cd frontend
npm run test -- src/test/ProductCategoryPnlPage.test.tsx
npm run test -- src/test/ProductCategoryAdjustmentAuditPage.test.tsx
npm run typecheck
npm run debt:audit
npm run build
cd ..
```

**Acceptance Criteria:**

- UX improvements clarify decisions instead of adding ornament.
- Mobile/tablet/desktop have no horizontal overflow.
- Evidence-pending states remain visible.

## Task 5: Scale The Pattern To Priority Routes

**Purpose:** Use the product-category model to move other high-value routes without borrowing evidence.

**Routes:**

- `/pnl-attribution`: DTO-only golden sample boundary and candidate approval lane.
- `/ledger-pnl`: dry-run governance boundary and missing written direct-record/golden summary sample.
- `/bond-analysis`: direct Gate I lane, no borrowed `/bond-dashboard` evidence.
- `/stock-analysis`: observational versus formal metric boundary.

**Files:**

- Inspect: `scripts/codex_page_readiness.py`
- Inspect: `tests/test_codex_page_readiness_gate.py`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect relevant docs under `docs/pnl/`, `docs/page_contracts.md`, and `docs/metric_dictionary.md`

**Step 1: Re-run route readiness**

Run:

```powershell
python scripts/codex_page_readiness.py --page-slug pnl-attribution
python scripts/codex_page_readiness.py --page-slug ledger-pnl
python scripts/codex_page_readiness.py --page-slug bond-analysis
python scripts/codex_page_readiness.py --page-slug stock-analysis
python scripts/codex_page_readiness.py --route-scope
```

**Step 2: Record the next blocker per route**

Each route must have one explicit next blocker: golden sample, manual audit, governance record, owner approval, or direct Gate I lane.

**Step 3: Add owner packets/checkers only where evidence is strong enough**

Do not create approval lanes for pages that lack direct page contract, metric dictionary, lineage/catalog evidence, or golden sample boundary.

**Acceptance Criteria:**

- No route is certified from borrowed evidence.
- Route-scope report remains honest.
- The next blocker is machine-visible per priority route.

## Task 6: System-Level Operating Board

**Purpose:** Turn the standard into repeatable operations instead of one-off hero work.

**Files:**

- Modify or create as needed: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify or create as needed: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`

**Step 1: Build a route certification board**

Track per route:

- frontend score
- page contract
- metric dictionary
- golden sample status
- direct governance evidence
- manual audit status
- owner approval status
- required verification commands
- next blocker

**Step 2: Keep claim boundaries explicit**

The board must include an allowed-claim and forbidden-claim section.

**Acceptance Criteria:**

- The standard becomes inspectable.
- A future reviewer can tell exactly why a route is or is not certified.

## Execution Order

1. Stabilize product-category live verification.
2. Close or isolate the last cursor-safe evidence blocker.
3. Regenerate owner-facing packets.
4. Apply product-category UX final pass only where evidence shows a real issue.
5. Re-run focused frontend, Python, readiness, approval, and browser checks.
6. Scale the certification model route by route.
7. Maintain a system-level certification board.

## ADR

**Decision:** Use `/product-category-pnl` as the first route-level certification lane, then scale.

**Drivers:** It has the strongest current readiness evidence, strict approval checker, direct owner packet path, and known blocker ledger.

**Alternatives considered:** More global UI polish first; parallel Gate I work across all priority routes; direct governance writes.

**Why chosen:** It creates the first defensible business-certified route pattern while minimizing formula, governance-write, and false-approval risk.

**Consequences:** Full certification still depends on real business-owner approval, golden sample approval, manual audit closure, and live evidence review. Codex can prepare the evidence and close cursor-safe blockers, but cannot sign business truth.

**Follow-ups:** After product-category certification is actually captured, use the same checker, owner packet, readiness, browser evidence, and route-scope ledger pattern for `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis`.

## Available-Agent-Types Roster

- `explore`: narrow file/symbol lookup and route impact.
- `researcher`: official docs or version-sensitive framework guidance.
- `dependency-expert`: package or framework decisions if needed.
- `planner`: sequencing and risk flags.
- `architect`: boundary, interface, and tradeoff review.
- `executor`: focused implementation.
- `test-engineer` / `verifier`: tests, browser evidence, and completion proof.
- `critic` / `code-reviewer`: independent challenge before sign-off.

## Follow-Up Staffing Guidance

`$ralph` path:

- One owner loop should execute Tasks 1-4 in order.
- Use `verifier` for live/browser evidence if the shared MCP suite remains unstable.
- Use `critic` before any checklist status promotion.

`$team` path:

- Lane 1: `verifier` for live route and browser evidence.
- Lane 2: `executor` for cursor-safe docs/tests cleanup.
- Lane 3: `test-engineer` for focused Python/frontend gates.
- Lane 4: `critic` for claim-boundary and certification wording review.

Launch hints:

```text
$ralph execute docs/plans/2026-06-06-top-investment-bank-standard-final-certification-lane-plan.md
$team execute docs/plans/2026-06-06-top-investment-bank-standard-final-certification-lane-plan.md
```

Team verification path:

- Team proves product-category route smoke, focused tests, approval pending status, and no false promotion.
- Ralph then verifies route-scope classification and final owner packet consistency before reporting.

## Final Checklist

- [x] Plan has testable acceptance criteria.
- [x] Plan references specific files and commands.
- [x] Risks have mitigations.
- [x] No vague certification claim.
- [x] Plan saved to `docs/plans/`.
- [x] RALPLAN-DR summary included.
- [x] ADR included.
