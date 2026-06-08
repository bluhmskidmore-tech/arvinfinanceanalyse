# Top Investment Bank Standard Owner-Signable Closure Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move MOSS from route-scope evidence coverage to the first owner-signable business certification lane while preserving honest certification boundaries.

**Architecture:** Treat top-investment-bank standard as a route-level operating certification pipeline: route contract, metric dictionary, golden sample, lineage/governance evidence, manual audit closure, owner approval, and institutional browser quality. Do not promote candidate, analytical, diagnostic, DTO-only, or frontend-only surfaces into formal business truth without direct approval evidence.

**Tech Stack:** Python readiness scripts, MOSS MCP fallback evidence, pytest, Markdown audit boards, PowerShell page gates, frontend Vitest, Playwright/a11y smoke, TypeScript typecheck, frontend debt audit, Vite build, route-scoped UI audit.

---

## Current Baseline

Fresh route-scope command:

```powershell
python scripts\codex_page_readiness.py --route-scope
```

Current machine baseline:

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
out_of_scope_count=0
unclassified_count=0
```

Truth:

- Route coverage has advanced: no visible navigation route is currently missing a seeded trace bundle.
- `/news-events` is now an analytical `evidence-pending` lane with seeded trace coverage.
- No route is `business-contract-certified`.
- The blocker is no longer basic page coverage. The blocker is owner-signable evidence closure.

Allowed claim:

```text
MOSS has route-scope evidence coverage across the current classified route set, plus institutional frontend surfaces. Full top-investment-bank business certification remains pending and route-scoped.
```

Forbidden claim:

```text
MOSS, or any individual route, is fully top-investment-bank business-certified.
```

## RALPLAN-DR Summary

### Principles

1. Evidence beats aesthetics: visual polish cannot certify a business metric.
2. One route, one approval lane: do not borrow adjacent route samples, contracts, or owner decisions.
3. Candidate means candidate: diagnostics, news events, DTO workbenches, and observational pages stay non-formal.
4. Human closure is mandatory: golden approval, manual audit closure, and business-owner approval must be real, non-placeholder evidence.
5. UI must support decisions: dense, calm, traceable, and audit-friendly beats decorative polish.

### Decision Drivers

1. First certified route requires the fewest remaining unknowns and strongest existing evidence.
2. The whole-system claim must stay honest while one route is prepared for owner signature.
3. UI effort should be spent only after metric/source/approval boundaries are explicit.

### Viable Options

| Option | Approach | Pros | Cons |
| --- | --- | --- | --- |
| A. Owner-signable first lane | Make `/product-category-pnl` the first owner-signable packet, then run institutional UI hardening on that lane. | Fastest path to a real certification candidate; blockers are already machine-counted; avoids broad churn. | Does not immediately certify the other 22 evidence-pending routes. |
| B. Evidence-pending breadth sprint | Add golden/manual/owner scaffolding to many candidate routes first. | Improves whole-board maturity. | Slower path to first real signable lane; higher false-certification risk. |
| C. UI-first flagship sprint | Polish the visible pages before owner packets. | Immediate visual lift. | Does not close business certification gates; risks confusing beauty with assurance. |

Decision: choose Option A, then use the same owner-signable pattern on `/pnl-attribution`, `/ledger-pnl`, `/bond-analysis`, and `/stock-analysis`.

## Target Standard

A route reaches top-investment-bank standard only when all gates below are true:

| Gate | Required proof |
| --- | --- |
| First-screen decision clarity | The first viewport states one primary business question, current date basis, evidence status, and conclusion. |
| Metric correctness | API response -> adapter/transformer -> state/selector -> component -> chart/table is traced and tested. |
| Semantic rigor | Units, precision, rounding, date basis, stale/fallback state, null-vs-zero, and scale are explicit. |
| Direct route contract | Route, page ID, primary API, source boundary, and formal/candidate status are route-specific. |
| Golden sample | Route-scoped sample exists with non-placeholder approval metadata. |
| Governance evidence | Source version, rule version, cache version, fallback/stale state, and review status are recorded. |
| Manual audit | Page contract, metric dictionary, UI/API payload, sample, live smoke, and lineage checks are reviewed. |
| Business-owner approval | Strict checker passes with real owner, approver, date, acceptance, and scope fields. |
| Browser quality | Desktop/tablet/mobile pass smoke, a11y, overflow, loading/error/stale-state, typecheck, debt audit, and build checks. |

## Institutional UI Standard

Use a data-dense drill-down workbench model. The UI should feel like a calm investment-bank desktop:

- Compact KPI hierarchy, not oversized marketing cards.
- Every displayed number exposes unit, date, source status, and stale/fallback state.
- Tables support scanning, comparison, drill-down, and exception review.
- Candidate/diagnostic/analytical pages visibly disclose non-formal status.
- No emoji icons, decorative chart chrome, horizontal overflow, or repeated inline layout blocks.
- Responsive checks cover 375px, 768px, 1024px, and 1440px.
- Motion is limited to state changes and interaction feedback; `prefers-reduced-motion` remains respected.

Design-system reference used for this plan:

```text
Pattern: Data-Dense + Drill-Down
Style: Data-Dense Dashboard
Typography: IBM Plex Sans family direction for finance/professional interfaces
Key effects: tooltips, row highlighting, smooth filter transitions
Avoid: ornate design, missing filtering
```

## Task 1: Freeze The Truth Board

**Files:**

- Modify: `docs/audits/2026-06-06-route-scope-classification.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Inspect: `scripts/codex_page_readiness.py`
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_project_mcp_servers.py`
- Test: `tests/test_native_dev_scripts.py`
- Test: `tests/test_native_dev_script_contents.py`

**Steps:**

1. Update both audit boards to the `39 / 39 / 0 / 23 / 0` route-scope baseline.
2. Confirm `/news-events` is `evidence-pending`, `formal_use_allowed=false`, no golden sample, no owner approval, and analytical event context only.
3. Remove any next-action language that says `/news-events` still needs seeding.
4. Run the route-scope command and focused tests.

**Acceptance criteria:**

- `visible_unseeded_route_count=0`.
- `not_started_count=0`.
- `business_contract_certified_count=0`.
- No board text implies `closure_approved`, `golden_sample_approved`, or owner approval.

## Task 2: Make `/product-category-pnl` Owner-Signable

This does not capture approval. It prepares a clean, signable packet for the human owner.

**Files:**

- Inspect: `docs/pnl/product-category-pnl-first-certification-packet.md`
- Inspect: `docs/pnl/product-category-pnl-owner-decision-packet.md`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Inspect: `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md`
- Run: `scripts/product_category_pnl_first_certification_packet.py`
- Run: `scripts/product_category_pnl_owner_decision_packet.py`
- Run: `scripts/check_product_category_pnl_business_owner_approval.py`
- Test: `tests/test_product_category_pnl_business_owner_approval_status.py`
- Test: `tests/test_product_category_pnl_first_certification_packet.py`
- Test: `tests/test_product_category_pnl_owner_decision_packet.py`

**Steps:**

1. Regenerate the first-certification packet and owner-decision packet.
2. Reconcile the blocker/action-item counts across packet, checker, and board.
3. Keep strict approval check as an expected blocker until real owner fields exist.
4. Ensure the packet separates product decisions, API/contract decisions, evidence gaps, and out-of-scope items.

**Acceptance criteria:**

- Non-strict checker reports pending with explicit action items.
- Strict checker fails until real owner approval exists.
- Packet says `business_contract_certified=false`.
- No placeholder owner, approver, date, or approval text is treated as captured.

## Task 3: Apply Owner-Signable Pattern To The Next Evidence Lanes

**Route order:**

1. `/pnl-attribution`
2. `/ledger-pnl`
3. `/bond-analysis`
4. `/stock-analysis`

**Steps per route:**

1. Regenerate the route owner evidence packet.
2. Run the route strict checker with `--require-captured`.
3. Confirm the failure is an expected approval blocker, not a broken script.
4. Update the certification board with current blocker counts and boundary language.
5. Run focused route tests.

**Boundary rules:**

- `/pnl-attribution` remains DTO/candidate only, not formal PnL.
- `/ledger-pnl` remains candidate until direct metric confirmation and owner closure.
- `/bond-analysis` must not borrow `/bond-dashboard` evidence.
- `/stock-analysis` must not become trading instruction, allocation advice, or formal stock metric truth.

## Task 4: Institutional UI Hardening On Evidence-Ready Lanes

Do this only after Task 2 has a clean owner-signable packet for `/product-category-pnl`.

**Priority route:**

1. `/product-category-pnl`

**Secondary routes:**

1. `/pnl-attribution`
2. `/ledger-pnl`
3. `/bond-analysis`
4. `/stock-analysis`

**UI steps:**

1. Capture desktop/tablet/mobile screenshots for the route.
2. Audit first-screen decision clarity, evidence status visibility, unit/date/source exposure, overflow, loading/empty/error/stale states, and keyboard focus.
3. Patch only page-local UI, adapters, or tests required by the route.
4. Run route frontend tests, a11y smoke, typecheck, debt audit, and build.

**Acceptance criteria:**

- The first screen answers the page's business question before any drill-down.
- Every business number visible in the first screen has unit/date/source/evidence status nearby.
- Candidate or non-formal pages visibly state their boundary.
- No horizontal overflow at 375px, 768px, 1024px, or 1440px.
- No repeated inline layout blocks are added.

## Task 5: Final Verification And Board Update

**Commands:**

```powershell
python scripts\codex_page_readiness.py --route-scope
python scripts\codex_page_readiness.py --all
python -m pytest tests\test_codex_page_readiness_gate.py tests\test_project_mcp_servers.py tests\test_native_dev_scripts.py tests\test_native_dev_script_contents.py -q
```

For any touched frontend route, also run the route-specific frontend tests plus:

```powershell
npm.cmd run typecheck
npm.cmd run debt:audit
npm.cmd run build
```

**Acceptance criteria:**

- `business_contract_certified_count=0` unless real golden/manual/owner approval exists.
- The first route becomes owner-signable, not owner-approved.
- Audit boards match machine route-scope output.
- Any strict checker failure is documented as an approval blocker, not ignored.

## Execution Log

### 2026-06-06 Owner-Packet Refresh

Product-category first lane:

- Regenerated `docs/pnl/product-category-pnl-owner-decision-packet.md`.
- Regenerated `docs/pnl/product-category-pnl-first-certification-packet.md`.
- Added an owner-readiness receipt to `docs/pnl/product-category-pnl-first-certification-packet.md` that separates machine-prepared evidence from human-required evidence and promotion blockers.
- Added a pre-signature verification rerun receipt to `docs/pnl/product-category-pnl-first-certification-packet.md` that lists the required rerun commands and records that the packet generator itself does not rerun the gate.
- Non-strict checker reports `approval_status=pending`, `approval_action_item_count=15`, `business_owner_approval_captured=false`, `closure_approved=false`, and `golden_sample_approval_artifact_mismatch=true`.
- Strict checker with `--require-captured` fails by design because real owner name, role, approval decision, approval date, signature, golden-sample reconciliation, checklist review, live-smoke review, and evidence-pending acceptance are not captured.
- Focused verification: product-category owner approval, first-certification packet, and owner-decision packet tests pass; the owner-readiness receipt tests assert `owner_signable=false`, `machine_evidence_ready=true`, `can_promote_certification=false`, and explicit human-required promotion blockers; the pre-signature rerun receipt tests assert `packet_generator_reruns_gate=false`, `approval_template_requires_rerun=true`, and `verification_commands_rerun_captured=false`.

Next evidence lanes:

| Route | Packet status | Strict checker status | Remaining owner action count | Boundary |
| --- | --- | --- | ---: | --- |
| `/pnl-attribution` | refreshed | expected strict failure | 11 | DTO/candidate only; not formal PnL |
| `/ledger-pnl` | refreshed | expected strict failure | 11 | candidate ledger summary only |
| `/bond-analysis` | refreshed | expected strict failure | 11 | candidate fixed-income action-attribution only |
| `/stock-analysis` | refreshed | expected strict failure | 11 | observational only; no trading instruction |

Focused verification for these four lanes: `55 passed` across owner evidence, business-owner approval status, and signoff packet tests.

This execution log does not approve any route, write governance records, close manual audit, approve a golden sample, or capture business-owner approval.

## ADR

**Decision:** Freeze the route-scope truth board, then make `/product-category-pnl` the first owner-signable lane, then apply the same packet and UI hardening pattern to the next evidence-pending routes.

**Drivers:** The route coverage gap is closed; owner/golden/manual closure is now the limiting factor; visual improvements matter most when they expose evidence rather than hide uncertainty.

**Alternatives considered:** breadth-first evidence scaffolding and UI-first flagship polish.

**Why chosen:** This gives the fastest honest path to a real top-investment-bank certification candidate without making false claims.

**Consequences:** The next visible improvement may look like governance and packet cleanup before dramatic UI changes. That is acceptable because trust is the product.

**Follow-ups:** Once a route has owner approval, add a certification promotion gate that requires direct golden approval, manual audit closure, and strict owner checker success in the same run.

## Stop Conditions

Stop and report instead of promoting a route if any of these remain true:

- `business_owner_approval_captured=false`
- `closure_approved=false`
- `golden_sample_approved=false`
- approval metadata is placeholder or mismatch
- route is candidate, DTO-only, diagnostic, analytical, or frontend-only
- governance write would be required
