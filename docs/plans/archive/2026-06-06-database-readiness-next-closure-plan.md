# Database Readiness Next Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clear the remaining DuckDB readiness blocker and start page-level formal closure with `product-category-pnl` as the first governed page.

**Architecture:** Keep DuckDB as the fact store and keep all writes in task-layer code. The next implementation first determines whether future `choice_news_event.received_at` values are parsing defects or vendor-future records, then either repairs through a governed task path or quarantines with explicit evidence. Page closure then proceeds on one page only, adding direct evidence records and the smallest backend/frontend smoke coverage.

**Tech Stack:** Python, DuckDB, FastAPI service/repository/task layers, MCP read-only helpers, Pytest, React/Vitest.

---

## Guardrails

- Do not change DuckDB schema.
- Do not promote candidate, preview, or scenario data into formal.
- Do not silently delete or rewrite news rows without root-cause evidence.
- Do not touch Postgres, Redis, scheduler, MinIO, auth, global SDK wrappers, or shared infrastructure.
- Preserve unrelated dirty worktree changes.
- For data writes, use only `backend/app/tasks/` or scripts that delegate to task-layer functions.

## Current State

- `scripts/data_readiness_report.py` exists and is exposed through `moss-data-quality`.
- Formal main chain is aligned to `2026-05-31`, with yield curve observed at `2026-05-29` because `2026-05-31` was a Sunday.
- Commodity non-ISO dates are normalized.
- `choice_news_event` read path already excludes future rows by default, but the readiness report still blocks on three future values:
  - `2026-07-28T00:00:00+08:00`
  - `2026-08-23T00:00:00+08:00`
  - `2026-09-01T00:00:00+08:00`

## Task 1: Trace Future News Date Root Cause

**Files:**
- Inspect: `backend/app/tasks/choice_news.py`
- Inspect: `backend/app/tasks/tushare_news_ingest.py`
- Inspect: `backend/app/repositories/news_warehouse_repo.py`
- Test: `tests/test_tushare_news_ingest.py`
- Test: `tests/test_choice_news_routes.py`
- Test: `tests/test_data_readiness_report.py`

**Step 1: Add a failing root-cause test**

Add tests that seed Tushare-like records with future `datetime`, `pubtime`, `date`, or `pub_date` values and assert the ingest layer reports them as future-date anomalies instead of treating the page as clean.

Run:

```powershell
python -m pytest tests/test_tushare_news_ingest.py -q
```

Expected: fail until the ingest classification exists.

**Step 2: Inspect real rows and payloads**

Read the three future rows from `data/moss.duckdb`, including `event_key`, `received_at`, `group_id`, `content_type`, `topic_code`, `payload_text`, and parsed `payload_json`.

Evidence to collect:

- Whether the future date is in the vendor payload.
- Whether the stored `received_at` came from `datetime`, `pubtime`, `date`, or `pub_date`.
- Whether the row source is Choice push/pull or Tushare backup ingest.

**Step 3: Classify closure path**

Use this rule:

- If the future date is caused by parsing or wrong field selection, fix normalization and repair the three rows through task-layer code.
- If the future date is vendor-provided and semantically real, add explicit quarantine evidence so readiness can downgrade this table issue to `observe`.
- If evidence is inconclusive, keep readiness blocked and document the unresolved source.

## Task 2: Add News Future-Date Guard

**Files:**
- Modify: `backend/app/tasks/tushare_news_ingest.py`
- Modify if needed: `backend/app/tasks/choice_news.py`
- Test: `tests/test_tushare_news_ingest.py`
- Test: `tests/test_choice_news_routes.py`

**Step 1: Write failing tests first**

Add tests proving future-dated inbound news records are not silently treated as normal latest records. Expected result depends on Task 1 classification:

- Parsing defect path: normalized `received_at` becomes the correct non-future timestamp.
- Vendor-future path: row remains stored but is marked/returned as quarantined or excluded with explicit evidence.

**Step 2: Implement the smallest guard**

For Tushare task paths, add a helper near `_normalize_received_at` that:

- Parses the chosen source date.
- Compares it to the current as-of date.
- Returns normalized date plus a future-date classification.
- Does not mutate unrelated rows.

For Choice task paths, apply the same principle around `_normalize_choice_news_received_at` only if Task 1 shows those rows came from Choice.

**Step 3: Verify route behavior remains transparent**

Run:

```powershell
python -m pytest tests/test_choice_news_routes.py tests/test_tushare_news_ingest.py -q
```

Expected: pass; latest API still excludes future rows by default and reports `excluded_future_rows`.

## Task 3: Repair Or Quarantine Existing Future Rows

**Files:**
- Create or modify only if needed: `backend/app/tasks/tushare_news_ingest.py`
- Create or modify only if needed: `scripts/repair_choice_news_future_dates.py`
- Test: `tests/test_tushare_news_ingest.py`
- Verify: `scripts/data_readiness_report.py`

**Step 1: Add an idempotent task-layer function**

Implement one of:

- `repair_existing_choice_news_future_dates(...)` for proven parse defects.
- `quarantine_existing_choice_news_future_dates(...)` for vendor-future rows.

Requirements:

- Idempotent.
- Bounded to `choice_news_event`.
- Emits counts and affected `event_key` values.
- Does not touch `fact_news_event` unless root-cause evidence proves the warehouse copy is wrong too.

**Step 2: Add a script wrapper only if real data needs execution**

If a real DuckDB update is needed, the script must delegate to the task function and should accept:

```powershell
--duckdb-path data/moss.duckdb
--as-of-date 2026-06-06
--run-id choice-news-future-date-closure:2026-06-06
```

**Step 3: Run readiness**

Run:

```powershell
python scripts/data_readiness_report.py --duckdb-path data/moss.duckdb --as-of-date 2026-06-06 --format markdown
```

Expected:

- `status: pass`, or
- `choice_news_event` is `observe` with explicit quarantine evidence and no hidden future-date success claim.

## Task 4: Tighten Readiness Reporting For Governed News Exceptions

**Files:**
- Modify: `scripts/data_readiness_report.py`
- Modify: `tests/test_data_readiness_report.py`
- Modify: `scripts/mcp/moss_project_mcp.py` only if the report payload contract changes.
- Modify: `tests/test_data_quality_mcp.py` only if the MCP payload contract changes.

**Step 1: Add failing report tests**

Add tests for the chosen outcome:

- Parse-repair path: future rows are no longer reported.
- Quarantine path: future rows with complete quarantine evidence become `observe`, while ungoverned future rows remain `block`.

**Step 2: Keep fail-closed behavior**

Confirm these still block:

- DuckDB unavailable.
- Core formal table empty.
- Future news row without quarantine evidence.
- Missing metadata on formal targets.

**Step 3: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_data_readiness_report.py tests/test_data_quality_mcp.py -q
```

Expected: pass.

## Task 5: Start `product-category-pnl` Direct Evidence Closure

**Files:**
- Inspect: `docs/pnl/product-category-page-truth-contract.md`
- Inspect: `docs/pnl/product-category-closure-checklist.md`
- Inspect: `backend/app/api/routes/product_category_pnl.py`
- Inspect: `backend/app/services/product_category_pnl_service.py`
- Inspect: `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- Test: `tests/test_product_category_pnl_flow.py`
- Test: `frontend/src/test/ProductCategoryPnlPage.test.tsx`
- Test: `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`

**Step 1: Identify direct record gap**

Use existing MCP/read-only helpers to check the page evidence readiness for:

- page id
- route `/product-category-pnl`
- primary API `/ui/pnl/product-category`
- report date `2026-05-31`
- `source_version`
- `rule_version`
- `cache_version`
- run id
- live smoke evidence
- owner approval status

**Step 2: Add minimal direct evidence record support**

Only if the evidence record is missing, add a script or governance-record helper that emits direct evidence for this page. Keep it separate from metric computation.

**Step 3: Freeze status visibility**

Add or update page/model tests proving the first screen visibly distinguishes:

- no data
- stale/vendor unavailable
- fallback mode
- formal pending or owner approval pending
- formal use allowed

Do not invent new formal metrics.

**Step 4: Run targeted page tests**

Run:

```powershell
python -m pytest tests/test_product_category_pnl_flow.py -q
cd frontend
npm test -- ProductCategoryPnlPage.test.tsx productCategoryPnlPageModel.test.ts --run
npm run debt:audit
```

Expected: pass with no frontend debt baseline growth.

## Task 6: Final Verification Packet

**Files:**
- Readiness: `scripts/data_readiness_report.py`
- Backend tests: relevant `tests/test_*.py`
- Frontend tests: relevant product-category tests

**Step 1: Run core targeted suite**

Run:

```powershell
python -m pytest tests/test_data_readiness_report.py tests/test_data_quality_mcp.py tests/test_choice_news_routes.py tests/test_tushare_news_ingest.py tests/test_product_category_pnl_flow.py -q
```

Expected: pass.

**Step 2: Run readiness markdown**

Run:

```powershell
python scripts/data_readiness_report.py --duckdb-path data/moss.duckdb --as-of-date 2026-06-06 --format markdown
```

Expected: no ungoverned blocking issues.

**Step 3: Record residual risks**

Report:

- Whether `choice_news_event` is repaired or quarantined.
- Whether readiness is `pass` or still `observe` for governed news exceptions.
- Whether `product-category-pnl` has direct evidence ready for audit review.
- Any remaining owner-approval wording or smoke gaps.
