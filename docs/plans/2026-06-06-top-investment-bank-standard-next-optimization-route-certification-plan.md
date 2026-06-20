# Top Investment Bank Standard Next Optimization Route Certification Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS closer to a top investment bank operating standard by closing route-scope evidence gaps, preparing the first owner-signable certification lane, and applying visual quality only where evidence supports it.

**Architecture:** Treat the standard as a route-level certification pipeline, not a frontend beauty score. Every route must preserve its formal, candidate, observational, diagnostic, or frontend-only boundary until direct golden approval, manual audit closure, and captured business-owner approval exist.

**Tech Stack:** Python readiness scripts, local MOSS MCP fallback script, pytest, Markdown audit boards, PowerShell page gates, frontend Vitest, Playwright/a11y smoke checks, TypeScript typecheck, frontend debt audit, Vite build.

---

## Supersession Note

This route-seeding plan has reached its coverage target: current route-scope output reports `seeded_trace_bundle_count=39`, `visible_unseeded_route_count=0`, `not_started_count=0`, and `business_contract_certified_count=0`. Continue from `docs/plans/2026-06-06-top-investment-bank-standard-owner-signable-closure-plan.md` for the next optimization round.

## Current Baseline

Fresh command:

```powershell
python scripts\codex_page_readiness.py --route-scope
```

Current route-scope counts:

```text
route_count=39
seeded_trace_bundle_count=37
visible_navigation_route_count=36
visible_unseeded_route_count=2
business_contract_certified_count=0
evidence_pending_count=21
gate_i_gap_count=0
frontend_ready_count=6
frontend_only_count=10
not_started_count=2
out_of_scope_count=0
unclassified_count=0
```

Remaining visible unseeded routes:

- `/platform-config`
- `/news-events`

Existing evidence facts:

- `/team-performance` is now seeded as `GAP-TEAM-PERFORMANCE-PAGE`, a candidate team-performance mapping lane for `/api/pnl/by-business-ytd` with product-category context; it remains `formal_use_allowed=false` and has no golden sample or owner approval.
- `/platform-config` has a real frontend page and tests: `frontend/src/features/platform-config/PlatformConfigPage.tsx`, `frontend/src/test/PlatformConfigPage.test.tsx`.
- `/news-events` has a real frontend page and tests: `frontend/src/features/news-events/NewsEventsPage.tsx`, `frontend/src/test/NewsEventsPage.test.tsx`.
- `docs/live_route_maturity.md` already marks these as temporary-exception routes with pending owner review.
- `docs/metric_dictionary.md` already contains candidate metric rows for `team-performance` and `platform-config`; `/news-events` must remain analytical event context, not a formal metric page.

Allowed claim:

```text
MOSS has institutional-grade frontend surfaces and route-scope evidence governance in progress. Full top-investment-bank business certification remains pending and route-scoped.
```

Forbidden claim:

```text
MOSS, or any route, is fully top-investment-bank business-certified.
```

## RALPLAN-DR Summary

### Principles

1. Evidence beats aesthetics: visual polish cannot certify a business metric.
2. One route, one boundary: do not borrow adjacent route evidence.
3. Candidate means candidate: do not promote temporary, diagnostic, observational, or mixed-source surfaces into formal use.
4. Certification requires human closure: golden approval, manual audit, and owner approval must be real, non-placeholder evidence.
5. Quality improvements must be page-scoped and reversible.

### Decision Drivers

1. Remove the remaining visible unseeded-route risk.
2. Preserve certification honesty while increasing owner-readiness.
3. Spend UI effort only on routes that already have enough evidence to benefit from visual hardening.

### Viable Options

| Option | Approach | Pros | Cons |
| --- | --- | --- | --- |
| A. Evidence-first lane closure | Seed the three remaining visible routes, then harden the first certification candidate. | Best governance discipline; reduces false-certification risk; measurable after every route. | Slower visual gratification. |
| B. UI-first polish sprint | Improve flagship pages visually before closing the unseeded routes. | Immediate visible improvement. | Does not close certification blockers; risks mistaking polish for readiness. |
| C. Single-route certification tunnel | Focus only on `/product-category-pnl` until owner packet is signable. | Shortest path to first formal candidate. | Leaves three visible routes unseeded and weakens whole-system credibility. |

Decision: choose Option A, with `/product-category-pnl` kept as the first certification candidate after the three-route seed gap is closed.

## Target Standard

A route reaches the top investment bank standard only when all gates below are satisfied:

| Gate | Required proof |
| --- | --- |
| First-screen decision clarity | Page answers one primary business question immediately. |
| Metric correctness | API response -> adapter/transformer -> state/selector -> component -> chart/table is traced and tested. |
| Semantic rigor | Units, precision, rounding, date basis, stale/fallback state, null-vs-zero, and scale are explicit. |
| Route contract | Route, page ID, API surface, and formal/candidate/observational boundary are route-specific. |
| Golden sample | Route-scoped sample and approval metadata are non-placeholder. |
| Governance evidence | Source version, rule version, cache version, fallback/stale state, and review status are recorded. |
| Manual audit | Page contract, metric dictionary, UI/API payload, sample, live smoke, and lineage checks are reviewed. |
| Business-owner approval | Strict checker passes with real owner, approver, date, acceptance, and scope fields. |
| Browser quality | Desktop/tablet/mobile pass smoke, a11y, overflow, loading/error/stale-state, typecheck, debt audit, and build checks. |

## Task 1: Seed `/team-performance` As A Candidate Evidence Lane

Status: completed in this pass. `/team-performance` is now `evidence-pending`, run-supported, and candidate-only.

**Files:**

- Modify: `scripts/codex_page_readiness.py`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Modify: `scripts/codex-page-smoke.ps1`
- Modify: `scripts/codex-verify-page.ps1`
- Modify: `tests/test_codex_page_readiness_gate.py`
- Modify: `tests/test_project_mcp_servers.py`
- Modify: `tests/test_native_dev_scripts.py`
- Modify: `tests/test_native_dev_script_contents.py`
- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`

**Step 1: Write failing readiness tests**

Add assertions that `/team-performance` is no longer `not-started`, has `page_id=GAP-TEAM-PERFORMANCE-PAGE`, remains `candidate_or_pending`, and keeps `formal_use_allowed=false`.

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py::test_route_scope_classification_keeps_certification_claim_route_scoped -q
python -m pytest tests\test_project_mcp_servers.py::test_metric_contracts_evidence_readiness_has_explicit_status_for_every_seeded_page -q
```

Expected before implementation: fail because `/team-performance` is still visible-navigation-only.

**Step 2: Add the candidate trace bundle**

Use the existing page and metric facts:

- route: `/team-performance`
- page ID: `GAP-TEAM-PERFORMANCE-PAGE`
- primary question: which mapped teams contribute to performance review, with pending/candidate attribution boundary visible.
- source endpoints: `GET /api/pnl/by-business-ytd`, `GET /ui/pnl/product-category`, date support from product-category endpoints, and page-local workbook mapping.
- metric boundary: keep `MTR-TEAM-001` as candidate only; exclude workbook-local score, department count, and text evidence cards from formal metrics.

Observed after implementation:

```text
seeded_trace_bundle_count=37
visible_unseeded_route_count=2
evidence_pending_count=21
business_contract_certified_count=0
```

**Step 3: Wire dry-run gates**

Add `team-performance` to the page smoke and verify scripts. Checklist language must say candidate team-performance evidence only, not approved KPI truth.

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug team-performance
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug team-performance -SkipBrowserSmoke
```

Expected: dry-run/checklist passes and does not imply certification.

**Step 4: Verify**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q
python -m pytest tests\test_project_mcp_servers.py -q -k "team or evidence_readiness or governance_gap_queue"
```

Expected: tests pass; no route is certified.

## Task 2: Seed `/platform-config` As A Diagnostic Evidence Lane

**Files:** same readiness, MCP, native-script, and board files as Task 1.

**Step 1: Write failing route tests**

Assert `/platform-config` has `page_id=GAP-PLATFORM-CONFIG-PAGE`, classification `evidence-pending` or diagnostic candidate, `formal_use_allowed=false`, no golden approval, no owner approval, and no business-certification claim.

Expected before implementation: fail.

**Step 2: Add diagnostic trace bundle**

Use the existing page and metric facts:

- route: `/platform-config`
- page ID: `GAP-PLATFORM-CONFIG-PAGE`
- primary question: what platform/source diagnostic state needs operator attention.
- source endpoints: `GET /health/ready`, `GET /health/live`, `GET /health`, `GET /ui/preview/source-foundation`.
- candidate metrics: `MTR-PLT-001` through `MTR-PLT-003`.
- excluded cards: environment text, liveness text, readiness text, and status labels must not become business data-quality approval.

Expected after implementation:

```text
seeded_trace_bundle_count=38
visible_unseeded_route_count=1
evidence_pending_count=22
business_contract_certified_count=0
```

**Step 3: Verify**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug platform-config
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug platform-config -SkipBrowserSmoke
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py -q -k "platform or evidence_readiness or governance_gap_queue"
```

Expected: pass; route remains diagnostic candidate only.

## Task 3: Seed `/news-events` As An Analytical Event Context Lane

**Files:** same readiness, MCP, native-script, and board files as Task 1.

**Step 1: Write failing route tests**

Assert `/news-events` has `page_id=GAP-NEWS-EVENTS-PAGE`, remains analytical/non-formal, has no golden approval, has no owner approval, and cannot be used as metric certification evidence.

Expected before implementation: fail.

**Step 2: Add analytical trace bundle**

Use the existing page and source facts:

- route: `/news-events`
- page ID: `GAP-NEWS-EVENTS-PAGE`
- primary question: which market/news events are available for analyst context and filtering.
- source endpoint: `GET /ui/news/choice-events/latest`.
- result kind: analytical event context only.
- metric boundary: do not create formal `MTR-NEWS-*` metrics unless a business owner defines units, freshness rules, and approval scope.

Expected after implementation:

```text
seeded_trace_bundle_count=39
visible_unseeded_route_count=0
not_started_count=0
business_contract_certified_count=0
```

**Step 3: Verify**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-smoke.ps1 -PageSlug news-events
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug news-events -SkipBrowserSmoke
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py -q -k "news or evidence_readiness or governance_gap_queue"
```

Expected: pass; route is analytical context only.

## Task 4: Promote `/product-category-pnl` To Owner-Signable Packet Readiness

This task does not capture approval. It prepares the cleanest packet for human approval.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Run: `scripts/product_category_pnl_first_certification_packet.py`
- Run: `scripts/product_category_pnl_owner_decision_packet.py`
- Run: `scripts/check_product_category_pnl_business_owner_approval.py`
- Test: `tests/test_product_category_pnl_business_owner_approval_status.py`
- Test: `tests/test_product_category_pnl_first_certification_packet.py`
- Test: `tests/test_product_category_pnl_owner_decision_packet.py`

**Step 1: Regenerate packets**

Run:

```powershell
python scripts\product_category_pnl_first_certification_packet.py
python scripts\product_category_pnl_owner_decision_packet.py
```

Expected: packet blocker counts match machine-readable blocker triage.

**Step 2: Confirm strict approval still blocks**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py
python scripts\check_product_category_pnl_business_owner_approval.py --require-captured
```

Expected: non-strict reports pending; strict checker fails until real approval exists.

**Step 3: Verify packet consistency**

Run:

```powershell
python -m pytest tests\test_product_category_pnl_business_owner_approval_status.py tests\test_product_category_pnl_first_certification_packet.py tests\test_product_category_pnl_owner_decision_packet.py -q
```

Expected: pass.

## Task 5: Apply The Institutional UI Quality Pass To Evidence-Ready Routes

Do this after the three unseeded routes are closed. Use `frontend-design`, `ui-ux-pro-max`, `audit`, `adapt`, `arrange`, `typeset`, `polish`, and `visual-verdict` only against visible evidence.

**Priority order:**

1. `/product-category-pnl`
2. `/pnl-attribution`
3. `/ledger-pnl`
4. `/bond-analysis`
5. `/stock-analysis`
6. `/team-performance`
7. `/platform-config`
8. `/news-events`

**UI acceptance criteria:**

- First screen states the business question and current evidence status.
- Candidate/diagnostic/analytical routes visibly say they are not formal certification truth.
- KPI cards disclose unit, date, source, stale/fallback status, and null/zero distinction where applicable.
- Tables and charts have no horizontal overflow at desktop, tablet, or mobile widths.
- Loading, empty, stale, fallback, and error states are visible and tested.
- No decorative complexity hides the decision.
- No repeated inline layout blocks are added.

**Verification:**

Run route-specific frontend tests for every touched page, then:

```powershell
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run build
```

Run Playwright/a11y smoke for touched routes when visible layout changes.

## Task 6: Produce The Final Certification Board Update

**Files:**

- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Create: `docs/audits/2026-06-06-top-investment-bank-next-optimization-evidence-note.md`

**Step 1: Rerun route-scope**

Run:

```powershell
python scripts\codex_page_readiness.py --route-scope
python scripts\codex_page_readiness.py --all
```

Expected after all route seeding:

```text
visible_unseeded_route_count=0
not_started_count=0
business_contract_certified_count=0
```

**Step 2: Rerun focused tests**

Run:

```powershell
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py tests\test_native_dev_scripts.py tests\test_native_dev_script_contents.py -q
```

Expected: pass.

**Step 3: Record the truth**

Final audit note must include:

- which routes moved out of `not-started`
- which routes remain `evidence-pending`, `frontend-ready`, or `frontend-only`
- why `business_contract_certified_count` remains `0`
- strict approval checkers that fail by design
- browser/frontend checks actually run
- any MCP fallback risk

## ADR

**Decision:** Close route-scope evidence coverage first, then harden `/product-category-pnl` as the first owner-signable candidate, then run UI polish on evidence-ready routes.

**Drivers:** visible unseeded routes weaken the institutional claim; certification honesty matters more than speed; visual quality is valuable only after evidence boundaries are explicit.

**Alternatives considered:** UI-first sprint and single-route certification tunnel.

**Why chosen:** Evidence-first closure gives the highest trust gain per change and keeps the system from overclaiming.

**Consequences:** The next visible improvement may be documentation and gate output before UI screenshots improve. This is acceptable because the blocker is certification closure, not just visual density.

**Follow-ups:** After visible unseeded routes reach zero, run a full visual/a11y sweep and prepare `/product-category-pnl` for human approval without modifying approval flags.

## Available Agent Types And Staffing Guidance

Use direct execution for one route at a time. Use native subagents only if splitting independent lanes improves throughput.

Recommended `$ralph` path:

- One executor owns readiness/MCP/script/test edits for the current route.
- One verifier reviews route-scope output and false-certification guardrails.
- One frontend reviewer runs visual/a11y checks only after route evidence is seeded.

Recommended `$team` path for parallel execution:

- `explore`: inspect route/page/API facts for each remaining route.
- `executor`: seed route bundles and script support.
- `test-engineer`: update and run focused readiness/native-script/MCP tests.
- `critic` or `verifier`: challenge certification language and ensure no approval flags were promoted.
- `frontend-design` reviewer: inspect screenshots and patch page-local UI only when evidence-backed.

Launch hints:

```text
$ralph execute docs/plans/2026-06-06-top-investment-bank-standard-next-optimization-route-certification-plan.md
$team execute route-seeding team-performance platform-config news-events
```

Team verification path:

1. Team proves `visible_unseeded_route_count=0`.
2. Team proves `business_contract_certified_count=0`.
3. Ralph independently reruns route-scope and focused tests before any completion claim.

## Stop Conditions

Stop only when:

- all visible routes have trace-bundle classification coverage, or
- a route requires real business-owner approval, or
- a destructive/write-governance action would be required.

Never set these without real human evidence:

```text
formal_use_allowed=true
closure_approved=true
business_owner_approval_captured=true
golden_sample_approved=true
business-contract-certified
```
