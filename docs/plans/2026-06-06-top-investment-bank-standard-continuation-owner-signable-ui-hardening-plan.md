# Top Investment Bank Standard Continuation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from broad route evidence coverage toward a first owner-signable, audit-ready business route, then harden the matching UI to investment-bank desktop quality.

**Architecture:** Treat "top investment bank standard" as route-scoped certification readiness, not visual polish alone. A page is not certified until metric truth, source-to-screen trace, golden sample approval, manual audit closure, fresh browser evidence, and real business-owner approval all agree in the same lane.

**Tech Stack:** Markdown audit packets, Python readiness/checker scripts, pytest, PowerShell page gates, React/Vitest, Playwright/a11y smoke, TypeScript typecheck, frontend debt audit, Vite build.

---

## Current Truth

Current route-scope baseline from `python scripts\codex_page_readiness.py --route-scope`:

```text
route_count=39
seeded_trace_bundle_count=39
visible_navigation_route_count=36
visible_unseeded_route_count=0
business_contract_certified_count=0
evidence_pending_count=23
gate_i_gap_count=0
frontend_ready_count=6
frontend_only_count=10
not_started_count=0
```

This means route coverage is no longer the main gap. The main gap is certification closure:

- no route is `business-contract-certified`
- no owner approval is captured
- no golden sample approval should be promoted
- no manual closure should be promoted
- `/product-category-pnl` is the first and best certification candidate, but remains `evidence-pending`

Allowed claim:

```text
MOSS has route-scope evidence coverage across the classified route set and institutional-grade frontend candidates. Full top-investment-bank business certification is still pending and route-scoped.
```

Forbidden claim:

```text
MOSS, or any route, has already reached full top-investment-bank business certification.
```

## RALPLAN-DR Summary

### Principles

1. Business correctness outranks appearance.
2. A route can only certify its own direct contract, metrics, golden sample, lineage, manual audit, and owner approval.
3. Candidate, DTO-only, diagnostic, observational, and analytical pages must visibly stay non-formal.
4. UI hardening must expose evidence status, date basis, units, stale/fallback state, and owner blockers.
5. No code path should turn a template review field into certification without strict checker proof.

### Decision Drivers

1. Fastest honest path to a first certifiable lane.
2. Lowest false-certification risk.
3. Most reusable pattern for the remaining evidence-pending routes.

### Options

| Option | Approach | Why not enough by itself |
| --- | --- | --- |
| UI-first polish | Make pages look more premium first | Does not close owner/golden/manual-audit blockers |
| Breadth-first evidence | Add scaffolding to many routes | Slower path to first real signable route |
| Owner-signable first lane | Finish `/product-category-pnl` packet, then harden UI and replicate | Best path; preserves honest certification boundaries |

Decision: use owner-signable first lane as the primary path, with UI hardening only after the evidence packet is aligned.

## Target Standard

A route reaches the target only when all of these are true:

| Gate | Required proof |
| --- | --- |
| Page contract | direct page ID, route, primary API, formal/candidate boundary |
| Metric dictionary | metric IDs, units, precision, date basis, null/zero semantics |
| Source-to-screen trace | API response -> adapter/model -> selector/state -> component -> table/chart |
| Golden sample | route-scoped sample with non-placeholder owner, approver, and date |
| Governance evidence | source version, rule/cache lineage, stale/fallback status |
| Manual audit | checklist closed with evidence, not just reviewed text |
| Business owner approval | strict checker passes with real approval fields |
| Browser quality | desktop/tablet/mobile, a11y, overflow, loading/error/stale states, typecheck, debt audit, build |

## Institutional UI Standard

Use the `ui-ux-pro-max` design-system direction as a constraint, not as decoration:

- Pattern: `Data-Dense + Drill-Down`
- Style: `Data-Dense Dashboard`
- Best fit: financial analytics, enterprise reporting, operational dashboards
- Required feel: calm, compact, decision-first, traceable
- Avoid: ornate design, generic hero marketing, decorative chart chrome, emoji icons, unexplained numbers

Route UI rules:

- first viewport answers one business question
- key numbers show unit, date basis, source/evidence status, and stale/fallback state nearby
- tables support scanning, comparison, exception review, and drill-down
- candidate pages disclose non-formal status above the fold
- no horizontal overflow at 375px, 768px, 1024px, or 1440px
- no repeated inline layout blocks

## Task 1: Sync Product-Category Approval Template With Receipts

**Files:**

- Modify: `tests/test_product_category_pnl_business_owner_approval_status.py`
- Modify: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`

**Step 1: Add the failing template assertion**

Extend `test_product_category_pnl_approval_template_states_current_owner_decision_counts` to require the approval template to mention:

```text
Owner Readiness Receipt
Pre-Signature Verification Rerun Receipt
owner_signable=false
can_promote_certification=false
packet_generator_reruns_gate=false
verification_commands_rerun_captured=false
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive
```

Expected: the focused test fails before the documentation patch.

**Step 2: Patch the template**

Add a small section under `## Evidence Boundary` that states:

- the first-certification packet contains the owner readiness receipt
- the pre-signature verification rerun receipt must be reviewed
- setting review fields to `yes` does not bypass golden approval, manual checklist closure, owner decisions, or strict checker failure

**Step 3: Verify**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py::test_product_category_pnl_approval_template_states_current_owner_decision_counts -q
```

Expected: pass.

## Task 2: Confirm Owner-Signable Packet Is Internally Consistent

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Test: `tests/test_product_category_pnl_first_certification_packet.py`
- Test: `tests/test_product_category_pnl_owner_decision_packet.py`

**Steps:**

1. Regenerate the first-certification and owner-decision packets.
2. Confirm packet, checker, and board agree on `15` owner action items and `15` closure blockers.
3. Confirm the packet says `owner_signable=false` and `can_promote_certification=false`.
4. Confirm strict checker failure remains expected until real owner evidence exists.

**Verification:**

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected:

- pytest passes
- strict checker exits non-zero with `approval_status=pending`

## Task 3: Product-Category Institutional UI Hardening

**Files:**

- Inspect/modify only if needed: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Inspect/modify only if needed: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- Inspect/modify only if needed: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
- Inspect/modify only if needed: `frontend/src/test/ProductCategoryPnlPage.test.tsx`

**Steps:**

1. Capture desktop/tablet/mobile evidence for `/product-category-pnl`.
2. Check first-screen decision clarity: conclusion, report date, unit, evidence status, and owner blocker state.
3. Check every first-screen business number has unit/date/source status nearby.
4. Check loading, empty, error, stale/fallback, and keyboard focus states.
5. Patch only page-local UI or model/tests required to close gaps.

**Verification:**

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
npm.cmd run test:a11y-smoke -- --grep @product-category-pnl
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run build
```

Expected: all pass; no debt baseline growth.

## Task 4: Pre-Signature Evidence Refresh

**Files:**

- Inspect: `scripts/codex-page-readiness.ps1`
- Inspect: `scripts/check_product_category_pnl_business_owner_approval.py`
- Update only documentation evidence if rerun output changes.

**Steps:**

1. Rerun the full route gate before any owner review.
2. Rerun non-strict and strict owner checker.
3. Record the result as pre-signature evidence, not approval.

**Verification:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive
python scripts\check_product_category_pnl_business_owner_approval.py
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected:

- readiness gate passes
- non-strict checker reports pending
- strict checker fails until real human owner approval exists

## Task 5: Replicate Pattern To Next Four Lanes

**Route order:**

1. `/pnl-attribution`
2. `/ledger-pnl`
3. `/bond-analysis`
4. `/stock-analysis`

**Steps per route:**

1. Regenerate owner evidence packet.
2. Run strict checker.
3. Confirm failure is owner/golden/manual closure, not script breakage.
4. Update the certification board with blocker count and boundary language.
5. Run focused route tests.

**Non-negotiable boundaries:**

- `/pnl-attribution` stays DTO/candidate only.
- `/ledger-pnl` stays candidate until direct metric confirmation and owner closure.
- `/bond-analysis` must not borrow `/bond-dashboard` evidence.
- `/stock-analysis` must not become trading instruction, allocation advice, or formal stock metric truth.

## Task 6: Certification Promotion Gate After Real Approval

Do this only after real owner/golden/manual-audit evidence exists.

**Files:**

- Inspect/modify: `scripts/codex_page_readiness.py`
- Inspect/modify: `tests/test_codex_page_readiness_gate.py`
- Inspect/modify route-specific checker tests.

**Required logic:**

A route may become `business-contract-certified` only if the same route has:

- direct static readiness pass
- approved route-scoped golden sample
- closed manual audit checklist
- strict owner checker success
- no candidate/DTO/diagnostic/analytical boundary
- fresh route gate evidence

**Verification:**

```powershell
python scripts\codex_page_readiness.py --route-scope
python scripts\codex_page_readiness.py --all
python -m pytest tests\test_codex_page_readiness_gate.py -q
```

Expected before real approval:

```text
business_contract_certified_count=0
```

## Stop Conditions

Stop instead of promoting certification if any of these remain true:

- `business_owner_approval_captured=false`
- `closure_approved=false`
- `golden_sample_approved=false`
- `owner_signable=false`
- `can_promote_certification=false`
- approval metadata is placeholder or mismatched
- route is candidate, DTO-only, diagnostic, analytical, observational, or frontend-only

## Immediate Next Round

The next execution round should start with Task 1. It is narrow, low-risk, and directly improves owner-signable evidence quality without making a false certification claim.

## Execution Log

### 2026-06-06 Task 1-2 Owner Template And Packet Alignment

- Added a TDD assertion requiring `docs/pnl/product-category-pnl-business-owner-approval-template.md` to name the Owner Readiness Receipt, Pre-Signature Verification Rerun Receipt, `owner_signable=false`, `can_promote_certification=false`, `packet_generator_reruns_gate=false`, and `verification_commands_rerun_captured=false`.
- Confirmed RED first: the focused test failed because the approval template did not mention Owner Readiness Receipt.
- Updated the approval template evidence boundary to state that receipt review does not approve the page, does not remove human blockers, and does not bypass golden approval, manual checklist closure, owner decisions, or strict checker failure.
- Regenerated `docs/pnl/product-category-pnl-owner-decision-packet.md`; output remained `owner_decision_ready=false` with 5 decision items, 3 product decisions, and 2 API/contract blockers.
- Regenerated `docs/pnl/product-category-pnl-first-certification-packet.md`; output remained `business_contract_certified=false`, `approval_action_item_count=15`, `closure_blocker_triage.blocker_count=15`, and `golden_sample_approval_artifact_mismatch=true`.

Verification:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py::test_product_category_pnl_approval_template_states_current_owner_decision_counts -q
# 1 passed

python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
# 19 passed

python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
# expected failure: approval_status=pending, business_owner_approval_captured=false, approval_action_item_count=15
```

False-certification check:

```powershell
rg -n "business_contract_certified=true|closure_approved=true|business_owner_approval_captured=true|golden_sample_approved=true|can_promote_certification=true|owner_signable=true|verification_commands_rerun_captured=true" docs\pnl\product-category-pnl-business-owner-approval-template.md docs\pnl\product-category-pnl-first-certification-packet.md docs\pnl\product-category-pnl-owner-decision-packet.md docs\plans\2026-06-06-top-investment-bank-standard-continuation-owner-signable-ui-hardening-plan.md
# no matches
```

Next execution step: Task 3, product-category institutional UI hardening, starting with desktop/tablet/mobile capture and first-screen evidence-status audit.

### 2026-06-06 Task 3 First-Screen Certification Blocker Strip

- Added a product-category first-screen certification blocker strip inside the formal readiness band.
- The strip exposes the current certification boundary next to the headline business numbers:
  - `Owner approval pending`
  - `Golden sample awaiting approval`
  - `Manual audit partial units=10`
  - `Fresh pre-signature rerun required`
  - `Unit=亿元`
  - `Date basis=report_date`
  - `Source=formal read model`
- The UI change is page-local to `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx` and `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`.
- The change does not alter metric calculation, adapters, API clients, approval status, golden sample status, manual closure status, or route certification status.

TDD evidence:

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx -t "renders the page shell, summary, and table structure"
# RED first: failed because product-category-certification-blockers did not exist
# GREEN after page-local UI patch: 1 passed, 49 skipped
```

Focused frontend verification:

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
# 2 passed, 104 passed

npm.cmd run test:a11y-smoke -- --grep @product-category-pnl
# 1 passed

npm.cmd run typecheck
# passed

npm.cmd run debt:audit
# Frontend debt audit passed, no growth over baseline

npm.cmd run build
# production build passed
```

Certification boundary verification:

```powershell
rg -n "business_contract_certified=true|closure_approved=true|business_owner_approval_captured=true|golden_sample_approved=true|can_promote_certification=true|owner_signable=true|verification_commands_rerun_captured=true" docs\pnl\product-category-pnl-business-owner-approval-template.md docs\pnl\product-category-pnl-first-certification-packet.md docs\pnl\product-category-pnl-owner-decision-packet.md frontend\src\features\product-category-pnl\pages\ProductCategoryPnlPage.tsx frontend\src\test\ProductCategoryPnlPage.test.tsx
# no matches

python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
# expected failure: approval_status=pending, business_owner_approval_captured=false, approval_action_item_count=15
```

Remaining UI follow-up: capture desktop/tablet/mobile screenshots and run overflow checks at 375px, 768px, 1024px, and 1440px.

### 2026-06-06 Task 3 Owner-Signable First-Viewport Rerun

- Moved `ProductCategoryOwnerSignableStatus` above the product-category branch switcher so the non-signable certification boundary appears before users choose the product branch.
- Added a DOM-order assertion that `product-category-owner-signable-status` precedes `product-category-branch-product-category-pnl`.
- Tightened only the mobile owner-signable strip spacing under `720px`; no metric calculation, adapter, API client, approval status, golden sample status, manual closure status, or route certification status was changed.

TDD evidence:

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx -t "renders the page shell, summary, and table structure"
# RED first: expected DOM order failed because owner status was after the branch switcher
# GREEN after page-local order and mobile-density patch: 1 passed, 49 skipped
```

Focused frontend verification:

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
# 2 passed, 104 passed

npm.cmd run test:a11y-smoke -- --grep @product-category-pnl
# 1 passed

npm.cmd run typecheck
# passed

npm.cmd run debt:audit
# Frontend debt audit passed, no growth over baseline
```

Browser evidence:

```text
json: frontend\.codex-tmp\product-category-owner-signable-ui\product-category-owner-signable-rerun-responsive.json
mobile 375x844: ownerStatus.bottom=808.515625, inFirstViewport=true, ownerBeforeBranch=true, horizontalOverflow=false
tablet 768x1024: ownerStatus.bottom=463.640625, inFirstViewport=true, ownerBeforeBranch=true, horizontalOverflow=false
laptop 1024x768: ownerStatus.bottom=305.375, inFirstViewport=true, ownerBeforeBranch=true, horizontalOverflow=false
desktop 1440x900: ownerStatus.bottom=283.875, inFirstViewport=true, ownerBeforeBranch=true, horizontalOverflow=false
```

Screenshots:

```text
frontend\.codex-tmp\product-category-owner-signable-ui\product-category-owner-signable-mobile-375-rerun.png
frontend\.codex-tmp\product-category-owner-signable-ui\product-category-owner-signable-tablet-768-rerun.png
frontend\.codex-tmp\product-category-owner-signable-ui\product-category-owner-signable-laptop-1024-rerun.png
frontend\.codex-tmp\product-category-owner-signable-ui\product-category-owner-signable-desktop-1440-rerun.png
```

Residual browser/environment evidence:

- The browser run still reported two `502 Bad Gateway` console messages and one aborted request for `http://127.0.0.1:5888/ui/pnl/product-category/dates`.
- The page rendered and the four-viewport layout checks passed, but the 502 should be investigated separately before using this browser run as final live evidence.

Certification boundary verification:

```powershell
rg -n "business_contract_certified=true|closure_approved=true|business_owner_approval_captured=true|golden_sample_approved=true|can_promote_certification=true|owner_signable=true|verification_commands_rerun_captured=true" docs\pnl\product-category-pnl-business-owner-approval-template.md docs\pnl\product-category-pnl-first-certification-packet.md docs\pnl\product-category-pnl-owner-decision-packet.md frontend\src\features\product-category-pnl\pages\ProductCategoryPnlPage.tsx frontend\src\test\ProductCategoryPnlPage.test.tsx
# no matches

python scripts\codex_page_readiness.py --page-slug product-category-pnl
# overall_status=static-pass; business_owner_approval_captured=false; closure_approved=false; golden sample artifact still captured-awaiting-approval/mismatch=true

python scripts\codex_page_readiness.py --route-scope
# route_count=39; seeded_trace_bundle_count=39; visible_unseeded_route_count=0; business_contract_certified_count=0; evidence_pending_count=23

python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
# expected failure: approval_status=pending, business_owner_approval_captured=false, approval_action_item_count=15
```

Build status:

```powershell
npm.cmd run build
# failed outside this product-category patch:
# src/features/pnl/pnlByBusinessAdbMap.test.ts(4,46): Cannot find module './pnlByBusinessAdbMap'
# src/features/pnl/PnlByBusinessPage.tsx(1550,24): number | null is not assignable to number
```

This build failure is in the separate `/pnl-by-business` lane and was not repaired in this page-scoped round.

### 2026-06-07 Task 3 Live Evidence Rerun And Dates 502 Check

- Rechecked the prior browser residual risk for `http://127.0.0.1:5888/ui/pnl/product-category/dates`.
- Direct request through the active frontend/local gateway returned HTTP 200.
- Direct `127.0.0.1:8000` was not listening in this local setup, so `5888` is the active local browser target.
- Reran browser evidence for `/product-category-pnl`; the previous `502 Bad Gateway` symptom did not reproduce.
- No production code was changed for this symptom because the failure was not currently reproducible and all observed product-category API calls returned 200.

Browser evidence:

```text
json: frontend\.codex-tmp\product-category-live-evidence\product-category-live-evidence-20260607.json
screenshot: frontend\.codex-tmp\product-category-live-evidence\product-category-live-mobile-375-20260607.png
viewport: 375x844
ownerStatus.bottom=808.515625
ownerStatusInFirstViewport=true
ownerBeforeBranch=true
horizontalOverflow=false
tablePresent=true
consoleMessageCount=0
requestFailureCount=0
```

Observed product-category responses:

```text
/ui/pnl/product-category/dates -> 200 OK
/ui/pnl/product-category/manual-adjustments?report_date=2026-05-31 -> 200 OK
/ui/pnl/product-category/attribution?report_date=2026-05-31&compare=mom -> 200 OK
/ui/pnl/product-category?report_date=2026-05-31&view=monthly -> 200 OK
```

Verification:

```powershell
npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts
# initially blocked by missing optional native dependency @rolldown/binding-win32-x64-msvc
# after npm dependency hydration: 2 passed, 104 passed

npm.cmd run test:a11y-smoke -- --grep @product-category-pnl
# 1 passed

npm.cmd run typecheck
# passed

npm.cmd run build
# production build passed

python scripts\codex_page_readiness.py --page-slug product-category-pnl
# overall_status=static-pass; business_owner_approval_captured=false; closure_approved=false; approval_action_item_count=15

python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
# expected failure: approval_status=pending, business_owner_approval_captured=false, approval_action_item_count=15

python scripts\codex_page_readiness.py --route-scope
# route_count=39; seeded_trace_bundle_count=39; visible_unseeded_route_count=0; business_contract_certified_count=0; evidence_pending_count=23
```

Dependency environment note:

- `npm.cmd install` was used to restore the missing local optional Rolldown native binding needed by Vitest/Vite on Windows.
- The local `node_modules/@rolldown/binding-win32-x64-msvc` directory exists after hydration.
- The package manifest/lock already had unrelated working-tree differences; this live-evidence rerun should not be treated as a package-script feature change.
