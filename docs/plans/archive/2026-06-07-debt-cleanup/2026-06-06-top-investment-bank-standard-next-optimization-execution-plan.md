# Top Investment Bank Standard Next Optimization Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from flagship frontend readiness plus evidence-pending lanes to the first defensible top investment-bank route certification, then scale the same standard across priority routes.

**Architecture:** Treat every page as a governed decision cockpit. The next optimization layer is not broader decoration; it is route-level trust closure: source-to-screen metric traceability, explicit candidate/formal boundaries, browser evidence, strict owner sign-off, and a recurring certification board.

**Tech Stack:** React, TypeScript, Vite, Vitest, Playwright, Ant Design, MOSS design tokens, page contracts, metric dictionary, golden samples, Python readiness scripts, approval checkers, local MCP evidence workflows, and route-scope audit documents.

---

## Current Verdict

As of 2026-06-06, the target is not fully achieved.

MOSS has strong institutional frontend surfaces and several governed certification lanes, but route-scope evidence still reports:

- `39` classified routes.
- `business-contract-certified=0`.
- `evidence-pending=12`.
- `gate-i-gap=2`.
- `frontend-ready=5`.
- `frontend-only=10`.
- `not-started=10`.

Allowed claim:

> MOSS has flagship-ready frontend surfaces and a governed route-certification operating model.

Forbidden claim:

> MOSS, or any individual route, is fully top investment-bank business-certified today.

Latest evidence update:

- `/product-category-pnl` has passed the full technical/live readiness gate, but remains blocked by human owner approval, golden-sample approval reconciliation, and manual-audit closure.
- `/pnl-attribution` has now passed its full technical readiness gate, including MCP contract tests, backend tests, frontend tests, browser a11y smoke, typecheck, debt audit, and production build. It still remains candidate-only and cannot be certified without business-owner approval and accepted DTO/workbench boundary.
- `/ledger-pnl` is the next route where Codex can materially move the state forward: it needs a dedicated page-level ledger summary golden-sample lane plus direct governance review evidence. The existing financial-indicator fixture is supporting evidence only, not a page summary golden sample.

## What "Top Investment-Bank Standard" Means

A page reaches the target only when it passes all four layers:

1. **Decision Surface:** first screen answers trust state, primary conclusion, evidence, blocker, and next action.
2. **Metric Truth:** key values expose source, report date, unit, precision, stale/fallback/no-data state, and formal/candidate boundary.
3. **Evidence Chain:** API response -> adapter/model -> selector/state -> component -> visible chart/table is traceable and tested.
4. **Certification Closure:** golden sample approval, manual audit closure, browser evidence, and strict business-owner approval are captured without placeholders.

Design direction:

- Quiet, dense, professional cockpit; no marketing hero treatment.
- IBM Plex Sans is the preferred finance-grade typography direction where it can be adopted through existing tokens.
- Use restrained dark institutional surfaces with amber/trust accents only where they improve hierarchy.
- Do not add purple-blue decorative gradients, ornamental blobs, or effects that hide uncertainty.
- Preserve all stale, fallback, no-data, candidate-only, pending-approval, and review-required states.

## RALPLAN-DR Summary

### Principles

1. Certification is evidence, not screenshot quality.
2. One fully closed route is worth more than many partially polished routes.
3. Business uncertainty must be visible, not smoothed away.
4. Generated packets prepare sign-off; they never become sign-off.
5. No route borrows another route's contract, golden sample, or governance record.

### Decision Drivers

1. `/product-category-pnl` is the closest first certification lane.
2. `/pnl-attribution` has crossed the technical readiness bar, but remains a candidate-only lane until owner approval and boundary acceptance are captured.
3. `/ledger-pnl` is the next Codex-actionable Gate I lane because the missing artifact is concrete: a dedicated summary golden sample and direct governance review path.
4. `/bond-analysis` and `/stock-analysis` still need direct route-specific contracts/gates before certification claims.
5. The biggest remaining gap is trust closure, not visual polish alone.

### Options

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| A. More broad UI polish | Fast visible improvement | Does not reduce certification blockers | Secondary |
| B. Close `/product-category-pnl` first | Creates the first defensible certification pattern | Final closure needs human owner/golden/manual audit action | Chosen |
| C. Run all priority routes in parallel | Broad progress | More partial lanes and higher overclaim risk | After first route pattern stabilizes |

## Task 1: Keep The Certification Board Honest

**Purpose:** Make the current state inspectable before any implementation continues.

**Files:**

- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Re-run route scope**

Run:

```powershell
python scripts/codex_page_readiness.py --route-scope
```

Expected: `business-contract-certified=0` unless direct golden approval, manual audit closure, and owner approval now exist.

**Step 2: Update board rows**

Record per priority route:

- frontend status
- page contract status
- metric dictionary status
- golden sample status
- governance/manual audit status
- owner approval status
- latest verification commands
- next blocker

**Step 3: Test the board gates**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

**Acceptance Criteria:**

- Board language separates frontend readiness from business certification.
- No `evidence-pending` route is described as certified.
- `/pnl-attribution` full technical pass may be cited, but only with `formal_use_allowed=false`, `business_owner_approval_captured=false`, and candidate DTO/workbench boundary intact.

## Task 2: Finish The First Certification Lane For `/product-category-pnl`

**Purpose:** Turn the strongest route into a signable certification candidate without faking approval.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-pnl-business-owner-approval-template.md`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Inspect: `scripts/check_product_category_pnl_business_owner_approval.py`

**Step 1: Re-prove page evidence**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug product-category-pnl -Run -CheckLive
```

Expected: route smoke, focused verification, frontend checks, typecheck, debt audit, and build pass.

**Step 2: Re-prove approval boundary**

Run:

```powershell
python scripts/check_product_category_pnl_business_owner_approval.py
python scripts/check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: normal mode reports pending; `--require-captured` fails until real owner approval exists.

**Step 3: Prepare owner packet**

Regenerate only evidence packets. Do not edit approval fields.

```powershell
python scripts/product_category_pnl_first_certification_packet.py
python scripts/product_category_pnl_owner_decision_packet.py
```

**Acceptance Criteria:**

- The owner can review one coherent packet set.
- `business_owner_approval_captured=false` remains until real sign-off.
- `closure_approved=false` remains until manual audit review is actually closed.
- `GS-PROD-CAT-PNL-A` remains pending until non-placeholder approval exists.

## Task 3: Preserve `/pnl-attribution` Candidate Boundary After Full Technical Pass

**Purpose:** Keep the newly refreshed technical pass from being overclaimed as business certification.

**Files:**

- Inspect: `scripts/codex-page-readiness.ps1`
- Inspect: `scripts/codex-verify-page.ps1`
- Inspect: `scripts/codex-page-smoke.ps1`
- Inspect: `docs/pnl/pnl-attribution-owner-evidence-packet.md`
- Inspect: `scripts/pnl_attribution_owner_evidence_packet.py`
- Inspect: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Test: `tests/test_pnl_attribution_owner_evidence_packet.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`

**Step 1: Re-run the full readiness gate when evidence needs refreshing**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug pnl-attribution -Run
```

Expected: smoke, MCP contracts, backend tests, frontend tests, a11y smoke, typecheck, debt audit, build, and final readiness gate pass.

**Step 2: Re-prove approval boundary**

Run:

```powershell
python scripts/check_pnl_attribution_business_owner_approval.py
python scripts/check_pnl_attribution_business_owner_approval.py --require-captured
```

Expected: normal mode reports pending; `--require-captured` fails until a real business owner signs the candidate-boundary approval.

**Step 3: Keep packets honest**

Run:

```powershell
python scripts/pnl_attribution_owner_evidence_packet.py
python -m pytest tests/test_pnl_attribution_owner_evidence_packet.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py -q
```

Expected: packet stays `evidence-pending`, `formal_use_allowed=false`, `business_owner_approval_captured=false`, and DTO/workbench scope remains explicit.

**Acceptance Criteria:**

- Full technical readiness is recorded without certifying business truth.
- `formal_use_allowed=false` and candidate DTO-only boundary stay intact.
- The next human action is clear: review and accept the candidate workbench boundary before approval.

## Task 4: Build Direct Gate I Lanes For The Next Routes

**Purpose:** Stop high-value pages from relying on borrowed or partial evidence.

**Routes:**

- `/ledger-pnl`
- `/bond-analysis`
- `/stock-analysis`

**Files:**

- Inspect: `docs/page_contracts.md`
- Inspect: `docs/metric_dictionary.md`
- Inspect: `docs/audits/2026-06-06-route-scope-classification.md`
- Inspect: `scripts/codex_page_readiness.py`
- Inspect relevant docs under `docs/pnl/`
- Inspect relevant frontend domains under `frontend/src/features/`

**Step 1: Re-run readiness**

Run:

```powershell
python scripts/codex_page_readiness.py --page-slug ledger-pnl
python scripts/codex_page_readiness.py --page-slug bond-analysis
python scripts/codex_page_readiness.py --page-slug stock-analysis
```

**Step 2: Define route-specific blockers**

Record exactly one primary blocker per route:

- `/ledger-pnl`: dedicated summary golden sample and direct governance validation.
- `/bond-analysis`: direct fixed-income route contract, metrics, golden sample, governance, and owner lane.
- `/stock-analysis`: observational-versus-formal contract boundary; no trading-instruction claim.

**Step 3: Build the `/ledger-pnl` dedicated summary golden-sample lane**

Before creating any sample file, write or extend tests to require:

- a new sample pack under `tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A/`
- `request.json`, `response.json`, `assertions.md`, and `approval.md`
- `approval.md` status of `captured-awaiting-approval`, not approved
- response captured from `/api/ledger-pnl/summary` or a deterministic fixture-backed equivalent
- explicit candidate boundary: `formal_use_allowed=false`
- no reuse of `GS-LEDGER-PNL-FIN-IND-202603-B` as page summary approval

Run:

```powershell
python -m pytest tests/test_golden_samples_capture_ready.py tests/test_ledger_pnl_owner_evidence_packet.py -q
```

Expected: tests fail first if the dedicated sample is missing, then pass after the capture-ready sample and packet references are added.

**Step 4: Refresh `/ledger-pnl` owner and governance evidence without approving it**

Run:

```powershell
python scripts/emit_ledger_pnl_governance_record.py
python scripts/ledger_pnl_owner_evidence_packet.py
python scripts/check_ledger_pnl_business_owner_approval.py
python scripts/check_ledger_pnl_business_owner_approval.py --require-captured
```

Expected: dry-run governance validation is ready for audit review; packet names the dedicated sample boundary; normal approval check remains pending; `--require-captured` fails until real owner approval exists.

Do not run:

```powershell
python scripts/emit_ledger_pnl_governance_record.py --write
```

unless a human explicitly authorizes a governance write.

**Step 5: Add packets/checkers only when justified**

Create an owner packet/checker only when the page has a direct page contract, metric dictionary evidence, catalog/date evidence, governance boundary, and golden sample boundary.

**Acceptance Criteria:**

- No route is certified from another route's evidence.
- `formal_use_allowed=false` remains for candidate-only or observational routes.
- Each route has a machine-visible next blocker.
- `/ledger-pnl` progresses from "missing dedicated summary sample" to "dedicated capture-ready sample awaiting owner approval" without changing approval truth.

## Task 5: Apply The Institutional UX Final Layer

**Purpose:** Lift already honest pages from dashboard quality to desk-grade operating cockpit quality.

**Files:**

- Inspect: `docs/frontend-institutional-standard.md`
- Inspect: `frontend/CLAUDE.md`
- Modify only page-local files under `frontend/src/features/<route>/`
- Modify tests under `frontend/src/test/` or page-local model tests

**Step 1: Score the first screen**

For each priority page, score:

- business trust
- first-screen closure
- visual hierarchy
- responsive resilience
- accessibility/keyboard
- token/design-system alignment
- runtime cleanliness

**Step 2: Patch only decision clarity issues**

Allowed changes:

- clearer trust strip
- better evidence/date/source/unit visibility
- denser but readable blocker/action layout
- mobile readout before raw tables
- visible focus and non-color status cues

Disallowed changes:

- hiding pending/stale/fallback states
- decorative hero treatment
- broad theme rewrite
- repeated inline layout styles
- frontend recalculation of official finance metrics

**Step 3: Verify per touched page**

Run targeted tests first:

```powershell
cd frontend
npm run test -- src/test/<TouchedPage>.test.tsx
npm run typecheck
npm run debt:audit
npm run build
cd ..
```

Run Playwright/browser checks when visible layout changed.

**Acceptance Criteria:**

- The first screen reads faster without losing evidence.
- Mobile, tablet, and desktop have no horizontal overflow.
- Keyboard/focus and status semantics remain clear.

## Task 6: Automate The Recurring Certification Operating Board

**Purpose:** Make the standard sustainable after the first route is closed.

**Files:**

- Inspect: `scripts/codex_page_readiness.py`
- Inspect: `tests/test_codex_page_readiness_gate.py`
- Modify as needed: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Modify as needed: `docs/audits/2026-06-06-route-scope-classification.md`

**Step 1: Keep route rows complete**

Every visible route should show:

- classification
- page contract
- metric dictionary
- golden sample
- direct governance
- manual audit
- owner approval
- required commands
- next blocker

**Step 2: Add claim boundaries**

The board must keep an allowed-claim and forbidden-claim section.

**Step 3: Re-run board verification**

Run:

```powershell
python scripts/codex_page_readiness.py --route-scope
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

**Acceptance Criteria:**

- Reviewers can see why each route is or is not certified.
- A future route cannot silently move from frontend-ready to business-certified.

## Execution Order

1. Keep certification board and route-scope numbers current.
2. Finish `/product-category-pnl` owner packet, live evidence, and strict approval boundary.
3. Preserve `/pnl-attribution` full technical pass while keeping candidate-only status explicit.
4. Move `/ledger-pnl` through the dedicated summary golden-sample and dry-run governance lane.
5. Build direct Gate I lanes for `/bond-analysis` and `/stock-analysis`.
6. Apply institutional UX final-layer patches only where evidence shows first-screen or responsive weakness.
7. Re-run route-scope and targeted tests after every lane.
8. Stop only when the board shows either a real certified route or an explicit human-approval blocker.

## ADR

**Decision:** Continue with evidence-first certification, using `/product-category-pnl` as the first route-level closure lane and `/pnl-attribution` as the next candidate-boundary stabilization lane.

**Drivers:** The product-category route has the strongest evidence chain and strict approval tooling. PnL attribution now has a full technical pass but still cannot be overclaimed because its business-owner approval and candidate DTO/workbench boundary are pending. Ledger PnL is the next actionable route because the missing evidence is specific and Codex-addressable without pretending to approve business truth.

**Alternatives considered:** More UI polish across all pages; parallel certification of every priority route; governance writes from automation.

**Why chosen:** Top investment-bank quality is trust, traceability, and signable closure. Visual excellence matters, but it must sit on top of correct business evidence.

**Consequences:** Codex can close technical, documentation, packet, browser, and test gaps. Codex cannot approve business truth, sign owner packets, promote golden samples, or close manual audits without real human evidence.

## Final Checklist

- [x] Separates frontend readiness from business certification.
- [x] Names current route-scope counts.
- [x] Gives concrete route order.
- [x] Includes files, commands, and expected outcomes.
- [x] Preserves candidate/formal boundaries.
- [x] Avoids formula, schema, auth, scheduler, cache, and global SDK scope.
