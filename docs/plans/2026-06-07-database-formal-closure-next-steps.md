# Database Formal Closure Next Steps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the current healthy DuckDB state toward strict formal-date alignment and page-level closure without promoting candidate or pending data.

**Architecture:** Keep DuckDB as the read authority and use existing task/repository/service boundaries. Database writes, if needed, stay in `backend/app/tasks/`; API and readiness checks stay read-only. Owner signoff work remains evidence/status only until a real business owner fills the approval templates.

**Tech Stack:** DuckDB, Python scripts, pytest, existing MOSS readiness and approval checker scripts.

---

## Current Baseline

- `scripts/data_readiness_report.py --format markdown` reports `pass`.
- Core formal tables are on `2026-05-31`.
- `fact_formal_yield_curve_daily` is on `2026-05-29` and currently allowed as lagged observe status.
- `product_category_pnl_scenario_read_model` is intentionally empty and must stay non-formal.
- Owner approval is pending for six pages: `product-category-pnl`, `balance-analysis`, `ledger-pnl`, `pnl-attribution`, `bond-analysis`, `stock-analysis`.

## Task 1: Make Yield Curve Date Policy Explicit

**Files:**
- Inspect: `scripts/data_readiness_report.py`
- Inspect: `backend/app/tasks/yield_curve_materialize.py`
- Inspect: `backend/app/repositories/yield_curve_repo.py`
- Test: `tests/test_data_readiness_report.py`
- Test: `tests/test_yield_curve_materialize.py`

**Steps:**
1. Confirm whether `2026-05-30` and `2026-05-31` are expected non-business dates or missing data.
2. If they are non-business dates, add a documented calendar/lag explanation to readiness output.
3. If they are missing formal inputs, backfill through the existing yield curve task path only.
4. Re-run `python scripts/data_readiness_report.py --format markdown`.
5. Re-run targeted yield curve tests.

**Acceptance:**
- Either yield curve reaches `2026-05-31`, or readiness explains why `2026-05-29` is the valid latest curve date.
- No API/service layer writes to DuckDB.
- No candidate curve data is promoted.

## Task 2: Lock Daily Readiness as the Database Gate

**Files:**
- Modify only if needed: `scripts/data_readiness_report.py`
- Test: `tests/test_data_readiness_report.py`
- Optional docs: `docs/MCP_RUNBOOK.md`

**Steps:**
1. Ensure the report clearly separates `pass`, `observe`, and blocking failure.
2. Ensure empty scenario read model remains `observe`, not failure.
3. Ensure formal zero-row, future-date, non-ISO date, and missing metadata cases fail or report as designed.
4. Add or adjust the smallest targeted tests if any behavior is unclear.

**Acceptance:**
- Readiness report stays read-only.
- Blocking issue count remains `0` on current data.
- Scenario empty table is visible but not promoted.

## Task 3: Finish Owner Evidence for One Page at a Time

**Order:**
1. `balance-analysis`
2. `pnl-attribution`
3. `bond-analysis`
4. `product-category-pnl`
5. `ledger-pnl`
6. `stock-analysis`

**Files per page:**
- Approval checker under `scripts/check_<page>_business_owner_approval.py`
- Approval template and packets under `docs/pnl/`
- Readiness connection in `scripts/codex_page_readiness.py`
- Targeted tests under `tests/test_*business_owner_approval_status.py` and `tests/test_codex_page_readiness_gate.py`

**Steps:**
1. Verify the page has direct readiness/governance evidence.
2. Verify checker reports pending by default.
3. Verify `--require-captured` fails while owner fields are incomplete.
4. Verify readiness exposes approval commands and action item counts.
5. Do not mark approval captured unless the template is actually completed and signed.

**Acceptance:**
- Each page has visible owner pending status.
- `formal_use_allowed=true` may remain true where formal data is valid.
- `closure_approved=false` remains until real approval.

## Task 4: Produce Closure Dashboard Snapshot

**Files:**
- Prefer existing: `scripts/codex_page_readiness.py`
- Optional docs output: `docs/audits/`

**Steps:**
1. Run all-page readiness.
2. Extract counts for formal/governed, mixed/candidate, owner pending, and business-contract-certified.
3. Save a human-readable snapshot only if needed for review.

**Acceptance:**
- Stakeholders can see exactly which pages are formal-data-ready versus closure-approved.
- No page is reported business-contract-certified without owner approval.

## Do Not Touch

- DuckDB schema base.
- Auth and permission framework.
- Redis/Postgres infrastructure.
- Global SDK wrappers.
- Frontend display logic unless a specific page closure task requires it.
- Candidate or preview promotion rules.

## Verification Commands

Run after each implementation task:

```powershell
python scripts\data_readiness_report.py --format markdown
python scripts\codex_page_readiness.py --all
python -m pytest tests/test_data_readiness_report.py -q
python -m pytest tests/test_codex_page_readiness_gate.py -q
```

Run page-specific tests for whichever page is touched.

## Git Boundary

Do not commit automatically. Stage and commit only after the user explicitly asks.
