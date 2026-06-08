# Ledger PnL Top Investment Bank Standard Next Closure Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move `/ledger-pnl` from stale evidence wording to a dedicated capture-ready page-summary evidence lane while preserving candidate-only approval boundaries.

**Architecture:** Treat `/ledger-pnl` as a governed decision cockpit, not a visual-only dashboard. The next layer closes evidence wording, packet consistency, readiness summaries, and owner-review handoff without changing finance formulas, formal-use flags, governance records, database schema, auth, scheduler, cache, or shared SDK surfaces.

**Tech Stack:** Python readiness scripts, pytest, Markdown evidence packets, golden sample catalog, MOSS page contracts, route-scope certification board, PowerShell readiness wrapper, existing ledger PnL frontend and backend surfaces.

---

## Current Assessment

MOSS has not yet reached full top investment-bank business certification.

Current defensible claim:

- The frontend has strong institutional cockpit surfaces.
- The certification operating model exists.
- `/ledger-pnl` now has a dedicated sample directory: `tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A/`.

Current forbidden claim:

- Do not claim `/ledger-pnl`, or MOSS as a whole, is business-contract-certified.
- Do not claim `formal_use_allowed=true`.
- Do not claim business-owner approval, manual audit closure, golden approval, or governance write completion.

Latest targeted check:

```powershell
python -m pytest tests\test_ledger_pnl_business_owner_approval_status.py tests\test_ledger_pnl_owner_evidence_packet.py tests\test_ledger_pnl_signoff_packet.py tests\test_codex_page_readiness_gate.py -q
```

Observed result:

- `38` passed.
- `7` failed.

Failure meaning:

- The dedicated ledger sample exists, but old evidence wording still appears in scripts, docs, packets, and readiness summaries.
- `/product-category-pnl` blocker-count expectation says `16`, while current runtime reports `15`; this needs evidence review before changing the expected count.

## RALPLAN-DR Summary

### Principles

1. Certification is evidence closure, not screen polish.
2. Candidate boundaries must remain visible until humans approve.
3. One page must not borrow another page's golden sample or contract.
4. Generated packets prepare review; they never become approval.
5. Route-scope totals must stay honest even when a sub-lane improves.

### Decision Drivers

1. `/ledger-pnl` has a concrete Codex-actionable gap: evidence synchronization around `GS-LEDGER-PNL-SUMMARY-A`.
2. The next value step is clearing stale blocker language, not changing finance logic.
3. The route must remain `evidence-pending` until owner approval and governance review are real.

### Viable Options

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| A. Broad visual polish | Fast visible change | Does not reduce certification blockers | Reject for next round |
| B. Synchronize `/ledger-pnl` evidence lane | Directly advances certification readiness | Still leaves human approval pending | Choose now |
| C. Try to close `/product-category-pnl` first | Closest first certified route | Current blocker-count drift needs review and human approval | Parallel follow-up, not this lane |

## Task 1: Finish Ledger Approval Checker Rename

**Files:**

- Modify: `scripts/check_ledger_pnl_business_owner_approval.py`
- Test: `tests/test_ledger_pnl_business_owner_approval_status.py`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Replace the stale blocker key**

Change:

- `no_dedicated_golden_sample_review`
- `- No dedicated ledger summary golden sample reviewed`

To:

- `dedicated_golden_sample_review`
- `- Dedicated ledger summary golden sample reviewed`

Keep:

- required value `yes`
- current status `pending`
- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval_captured=false`

**Step 2: Verify approval checker**

Run:

```powershell
python -m pytest tests\test_ledger_pnl_business_owner_approval_status.py -q
```

Expected: pass.

**Acceptance Criteria:**

- The checker no longer says the dedicated sample is missing.
- The checker still blocks approval until a real owner completes the template.

## Task 2: Refresh Ledger Evidence Packets

**Files:**

- Modify: `docs/pnl/ledger-pnl-business-owner-approval-template.md`
- Generate: `docs/pnl/ledger-pnl-owner-evidence-packet.md`
- Modify or regenerate: `docs/pnl/ledger-pnl-sign-off-packet.md`
- Modify or regenerate: `docs/pnl/ledger-pnl-governance-audit-packet.md`
- Source script: `scripts/ledger_pnl_owner_evidence_packet.py`
- Test: `tests/test_ledger_pnl_owner_evidence_packet.py`
- Test: `tests/test_ledger_pnl_signoff_packet.py`

**Step 1: Align template wording**

The approval template must state:

- `GS-LEDGER-PNL-SUMMARY-A` is captured-awaiting-approval.
- It does not approve formal use.
- Evidence review asks whether the dedicated sample was reviewed.

**Step 2: Regenerate the owner packet**

Run:

```powershell
python scripts\ledger_pnl_owner_evidence_packet.py
```

Expected: packet writes Markdown and reports:

- `business_contract_certified=false`
- `approval_action_item_count=11`
- `governance_record_write_status=not_requested`
- `golden_sample_boundary=dedicated_summary_capture_ready_pending_approval`

**Step 3: Sync sign-off and audit packet wording**

Ensure both packets include:

- owner evidence packet path
- dedicated sample ID
- approval blockers from checker output
- candidate-only boundary
- no double bullet formatting such as `- - Dedicated...`

**Step 4: Verify packet consistency**

Run:

```powershell
python -m pytest tests\test_ledger_pnl_owner_evidence_packet.py tests\test_ledger_pnl_signoff_packet.py -q
```

Expected: pass.

**Acceptance Criteria:**

- Packets agree with the checker output.
- Packets no longer say the dedicated summary sample is missing.
- Packets do not approve, certify, or write governance records.

## Task 3: Update Readiness Gate And PowerShell Summary

**Files:**

- Inspect or modify: `scripts/codex_page_readiness.py`
- Inspect or modify: `scripts/codex-page-readiness.ps1`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Align all-page pending approval summary**

The batch readiness output must surface:

```text
Dedicated ledger summary golden sample reviewed: yes (pending)
```

It must not surface:

```text
No dedicated ledger summary golden sample reviewed
```

**Step 2: Align `/ledger-pnl` readiness residual gaps**

Expected route state after this round:

- `has_golden_samples=true`
- golden boundary is DTO/capture-ready only, not approved
- remaining blockers still include business-owner approval, governance review, live evidence review, verification rerun, and candidate boundary acceptance
- `business-contract-certified=0` at route scope

**Step 3: Verify readiness**

Run:

```powershell
python scripts\codex_page_readiness.py --page-slug ledger-pnl
python scripts\codex_page_readiness.py --route-scope
python -m pytest tests\test_codex_page_readiness_gate.py -q
```

Expected:

- `/ledger-pnl` static gate passes.
- route-scope still reports no certified route unless real owner/golden/manual audit evidence exists.

**Acceptance Criteria:**

- The machine-readable gate distinguishes capture-ready sample from approved sample.
- The route remains evidence-pending.

## Task 4: Update Catalog And Board

**Files:**

- Modify: `tests/golden_samples/README.md`
- Modify: `docs/golden_sample_catalog.md`
- Modify: `docs/page_contracts.md`
- Modify: `docs/audits/2026-06-06-top-investment-bank-certification-board.md`
- Modify: `docs/audits/2026-06-06-route-scope-classification.md`

**Step 1: Update golden sample inventory**

Record:

- total sample directories increases by one for `GS-LEDGER-PNL-SUMMARY-A`
- capture-ready count includes the new ledger summary sample
- approval status remains `captured-awaiting-approval`

**Step 2: Update certification board**

Ledger row should say:

- dedicated summary sample: capture-ready pending approval
- governance: dry-run ready or review-required, depending on current readiness output
- owner approval: pending
- formal use: false
- next blocker: owner/governance/manual review, not sample creation

**Step 3: Verify catalog and board wording**

Run:

```powershell
rg -n "missing_dedicated_summary_sample|No dedicated ledger summary golden sample|no_dedicated_golden_sample_review" docs scripts tests
python -m pytest tests\test_golden_samples_capture_ready.py tests\test_project_mcp_servers.py -q
```

Expected:

- no stale ledger blocker wording remains except archived historical audit files if intentionally preserved
- capture-ready tests pass
- MCP seeded bundle references `GS-LEDGER-PNL-SUMMARY-A`

**Acceptance Criteria:**

- Humans and scripts see the same ledger state.
- The board still forbids certification overclaim.

## Task 5: Investigate Product Category Blocker Count Drift

**Files:**

- Inspect: `scripts/check_product_category_pnl_business_owner_approval.py`
- Inspect: `docs/pnl/product-category-remaining-blockers.md`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Test: `tests/test_codex_page_readiness_gate.py`

**Step 1: Determine whether `15` is the new truth**

Run:

```powershell
python scripts\check_product_category_pnl_business_owner_approval.py
python scripts\codex_page_readiness.py --page-slug product-category-pnl
```

Compare runtime blocker list with docs.

**Step 2: Update only evidence-backed expectations**

If a blocker was truly resolved, update tests and board to `15`.

If a blocker disappeared by accident, fix the source script or packet to restore the missing blocker.

**Acceptance Criteria:**

- No blind test update.
- Product-category remains pending until real owner approval, closure review, and golden approval reconciliation exist.

## Task 6: Final Verification Before Claiming Progress

Run:

```powershell
python -m pytest tests\test_ledger_pnl_business_owner_approval_status.py tests\test_ledger_pnl_owner_evidence_packet.py tests\test_ledger_pnl_signoff_packet.py tests\test_golden_samples_capture_ready.py tests\test_project_mcp_servers.py -q
python -m pytest tests\test_codex_page_readiness_gate.py -q
python scripts\check_ledger_pnl_business_owner_approval.py
python scripts\check_ledger_pnl_business_owner_approval.py --require-captured
python scripts\codex_page_readiness.py --page-slug ledger-pnl
python scripts\codex_page_readiness.py --route-scope
```

Expected:

- targeted tests pass
- normal approval checker reports pending
- `--require-captured` fails because owner approval is not real
- `/ledger-pnl` no longer says the dedicated sample is missing
- route-scope still reports `business-contract-certified=0`

## Done Definition

This round is done when:

- `GS-LEDGER-PNL-SUMMARY-A` is referenced consistently as capture-ready pending approval.
- No active packet/checker/readiness summary uses stale missing-sample wording.
- `/ledger-pnl` remains evidence-pending with formal use blocked.
- The next blocker is human review and approval, not Codex-created sample artifacts.
- The final report explicitly says MOSS is closer to top investment-bank standard, but not fully certified.

## Next Round After This

After `/ledger-pnl` evidence wording is green:

1. Refresh `/product-category-pnl` owner decision packet and reconcile the `15` vs `16` blocker-count drift.
2. Run one full readiness gate for `/product-category-pnl` and keep `--require-captured` failing until signed.
3. Build direct Gate I contract lanes for `/bond-analysis` and `/stock-analysis`.
4. Apply page-local institutional UX final-layer work only after evidence state is machine-clean.
