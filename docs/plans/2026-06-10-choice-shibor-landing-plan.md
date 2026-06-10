# Choice SHIBOR Landing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Land the seven verified Choice SHIBOR funding series into DuckDB with scoped, auditable, repeatable writes.

**Architecture:** Reuse the existing Choice macro refresh stack instead of adding new tables. Add a narrow scoped-refresh path so the SHIBOR batch can be fetched and written without deleting unrelated Choice-managed macro rows. Keep `choice_market_snapshot` as the latest snapshot surface and `fact_choice_macro_daily` as the daily fact surface.

**Tech Stack:** Python, DuckDB, Choice EmQuantAPI, existing `backend.app.tasks.choice_macro` materialization task, existing Choice catalog JSON.

---

## Scope

Landing target: `choice_funding_shibor_latest` in `config/choice_macro_catalog.json`.

Series:

- `EMM00166252` `SHIBOR:ON`
- `EMM00166253` `SHIBOR:1W`
- `EMM00166254` `SHIBOR:2W`
- `EMM00167612` `SHIBOR:1M`
- `EMM00167613` `SHIBOR:3M`
- `EMM00167614` `SHIBOR:6M`
- `EMM00167708` `SHIBOR:1Y`

Do not land trading/order APIs. Do not promote LPR swap, OMO, M1/M2, social financing, or other funding candidates until their unit/date semantics are separately confirmed.

## Target Tables

Use existing schema in `backend/app/schema_registry/duckdb/11_choice_macro.sql`.

- `choice_market_snapshot`: latest SHIBOR point per series, including `source_version`, `vendor_version`, `rule_version`, `run_id`.
- `fact_choice_macro_daily`: daily fact row per `series_id + trade_date`; repeated runs replace the same date, but should preserve prior SHIBOR dates.
- `phase1_macro_vendor_catalog`: authoritative local catalog metadata for the seven series.
- `market_data_series_category`: business-facing category metadata; SHIBOR lands as `fallback`, `latest`, `single`.

## Recommended Approach

Do not run the existing full `refresh_choice_macro_snapshot` directly against production just to land SHIBOR. The current full-refresh delete scope includes all existing Choice-managed catalog series before reinserting the fetched snapshot. That is acceptable for the existing full macro refresh workflow, but too broad for a first SHIBOR landing.

Recommended: add scoped refresh support, then run only `choice_funding_shibor_latest`.

Scoped refresh contract after remediation:

- Scoped Choice refresh is a partial landing only. It skips Livermore gate supplement materialization and returns `gate_supplement_refresh = {"status": "skipped", "reason": "scoped_refresh"}`.
- Raw Choice payload archive is written only after the DuckDB transaction commits successfully. A fetch followed by a DuckDB write failure must leave no archive file, vendor snapshot manifest, vendor version registry record, or cache manifest for that failed run.
- Scoped payload validation rejects duplicate vendor points for the same `series_id` before any DuckDB rows, archive files, or governance manifests are written.
- If DuckDB commit succeeds but archive or governance append later fails, treat the run as failed and retry. The landed rows are not a completed SHIBOR landing until archive/governance manifests and cache build records complete successfully.

Scoped write semantics:

- Fetch only batches matching `batch_ids=["choice_funding_shibor_latest"]`.
- Delete from `choice_market_snapshot` where `series_id` is one of the seven SHIBOR ids, then insert the latest seven rows.
- Delete from `fact_choice_macro_daily` only where `(series_id, trade_date)` matches the fetched SHIBOR rows, then insert those rows. This makes the daily fact idempotent while allowing later daily history to accumulate.
- Delete and reinsert `phase1_macro_vendor_catalog` and `market_data_series_category` only for the seven SHIBOR ids.
- Preserve all non-SHIBOR Choice, Tushare, FX, public cross-asset, and other supplemental rows.

## Task 1: Add Scoped Refresh Contract

**Files:**

- Modify: `backend/app/tasks/choice_macro.py`
- Test: `tests/test_choice_macro_delivery.py`

**Step 1: Write the failing test**

Add a test that seeds an existing non-SHIBOR Choice row and then runs scoped SHIBOR refresh. The test must prove the old Choice row remains.

Expected assertions:

- `refresh_choice_macro_snapshot.fn(..., batch_ids=["choice_funding_shibor_latest"])` returns `status == "completed"`.
- `fact_choice_macro_daily` contains the original non-SHIBOR Choice row after refresh.
- `fact_choice_macro_daily` contains exactly seven SHIBOR rows for the fetched `trade_date`.
- `choice_market_snapshot` contains exactly seven SHIBOR snapshot rows for the target ids.
- `phase1_macro_vendor_catalog` has no duplicate `series_id`.
- `market_data_series_category` rows for SHIBOR have `category_key = "fallback"`, `fetch_mode = "latest"`, `fetch_granularity = "single"`.

**Step 2: Implement minimal parameters**

Extend the task signature conservatively:

```python
def refresh_choice_macro_snapshot(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    backfill_days: int = 0,
    batch_ids: list[str] | None = None,
    series_ids: list[str] | None = None,
) -> dict[str, object]:
```

Default behavior must stay unchanged when both new parameters are `None`.

**Step 3: Filter the registry and fetch plan**

After loading batches, derive a scoped batch list:

```python
def _filter_choice_macro_batches(
    batches: list[ChoiceMacroBatchConfig],
    *,
    batch_ids: list[str] | None,
    series_ids: list[str] | None,
) -> list[ChoiceMacroBatchConfig]:
    ...
```

Rules:

- If `batch_ids` is provided, keep only matching `batch.batch_id`.
- If `series_ids` is provided, keep only matching `series.series_id`.
- Preserve batch metadata: `fetch_mode`, `fetch_granularity`, `refresh_tier`, `policy_note`, `request_options`.
- Raise `ValueError` if the filter matches nothing.

**Step 4: Add scoped delete helper**

Keep `_delete_choice_managed_rows` unchanged for the full refresh path. Add a scoped helper for this landing path:

```python
def _delete_scoped_choice_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: list[str],
    fact_pairs: list[tuple[str, str]],
) -> None:
    ...
```

Delete rules:

- `choice_market_snapshot`: delete all rows for target `series_ids`.
- `fact_choice_macro_daily`: delete only fetched `(series_id, trade_date)` pairs.
- `phase1_macro_vendor_catalog`: delete rows for target `series_ids`.
- `market_data_series_category`: delete rows for target `series_ids`.

**Step 5: Preserve full refresh behavior**

In `refresh_choice_macro_snapshot`, use scoped delete only when `batch_ids` or `series_ids` is provided. Otherwise keep the existing full Choice-managed delete behavior.

**Step 6: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_choice_macro_delivery.py -q
```

Expected: all tests pass.

## Task 2: Dev DuckDB Landing Trial

**Files:**

- Use: `config/choice_macro_catalog.json`
- Use: `scripts/choice_funding_probe.py`
- Use: `backend/app/tasks/choice_macro.py`
- Output: `.codex-tmp/choice-shibor-dev.duckdb`
- Output: `.codex-tmp/choice-shibor-governance/`
- Output: `.codex-tmp/choice-shibor-archive/`

**Step 1: Run read-only live probe**

```powershell
python scripts/choice_funding_probe.py --as-of-date 2026-06-10 --chunk-size 30 --max-batches 1 --probe-mode latest --execute --output-path .codex-tmp/choice-funding-probe-latest-dev.json
```

Expected:

- `status = completed`
- `error_code = 0`
- `write_performed = false`
- all seven SHIBOR series have latest dates and non-null values

**Step 2: Run scoped refresh into dev DuckDB**

```powershell
$env:MOSS_CHOICE_MACRO_CATALOG_FILE = "F:\MOSS-V3\config\choice_macro_catalog.json"
$env:MOSS_OBJECT_STORE_MODE = "local"
$env:MOSS_LOCAL_ARCHIVE_PATH = "F:\MOSS-V3\.codex-tmp\choice-shibor-archive"
@'
from backend.app.governance.settings import get_settings
from backend.app.tasks.choice_macro import refresh_choice_macro_snapshot

get_settings.cache_clear()
payload = refresh_choice_macro_snapshot.fn(
    duckdb_path=r"F:\MOSS-V3\.codex-tmp\choice-shibor-dev.duckdb",
    governance_dir=r"F:\MOSS-V3\.codex-tmp\choice-shibor-governance",
    batch_ids=["choice_funding_shibor_latest"],
)
print(payload)
'@ | python -
```

Expected:

- `status = completed`
- `series_count = 7`
- `gate_supplement_refresh.status = skipped` and `gate_supplement_refresh.reason = scoped_refresh`
- no warnings except explicitly explainable Choice runtime warnings

**Step 3: Verify landed rows**

```powershell
@'
import duckdb

path = r"F:\MOSS-V3\.codex-tmp\choice-shibor-dev.duckdb"
ids = [
    "EMM00166252", "EMM00166253", "EMM00166254", "EMM00167612",
    "EMM00167613", "EMM00167614", "EMM00167708",
]
conn = duckdb.connect(path, read_only=True)
try:
    print(conn.execute("""
        select series_id, series_name, trade_date, value_numeric, unit, quality_flag
        from fact_choice_macro_daily
        where series_id in (?, ?, ?, ?, ?, ?, ?)
        order by series_id, trade_date
    """, ids).fetchall())
    print(conn.execute("""
        select series_id, trade_date, value_numeric, unit
        from choice_market_snapshot
        where series_id in (?, ?, ?, ?, ?, ?, ?)
        order by series_id
    """, ids).fetchall())
    print(conn.execute("""
        select series_id, batch_id, refresh_tier, fetch_mode, fetch_granularity
        from phase1_macro_vendor_catalog
        where series_id in (?, ?, ?, ?, ?, ?, ?)
        order by series_id
    """, ids).fetchall())
    print(conn.execute("""
        select series_id, category_key, source_surface, fetch_mode, fetch_granularity
        from market_data_series_category
        where series_id in (?, ?, ?, ?, ?, ?, ?)
        order by series_id
    """, ids).fetchall())
finally:
    conn.close()
'@ | python -
```

Expected:

- `fact_choice_macro_daily`: 7 SHIBOR rows for the latest observed `trade_date`; unit `%`; quality `ok`.
- `choice_market_snapshot`: 7 SHIBOR rows, latest date only.
- `phase1_macro_vendor_catalog`: 7 SHIBOR rows with `batch_id = choice_funding_shibor_latest`.
- `market_data_series_category`: 7 rows with `category_key = fallback`.

**Step 4: Verify idempotency**

Run the scoped refresh a second time against the same dev DuckDB, then rerun the row checks.

Expected:

- no duplicate `series_id + trade_date` rows in `fact_choice_macro_daily`;
- no duplicate `series_id` rows in `choice_market_snapshot`, `phase1_macro_vendor_catalog`, or `market_data_series_category`.

Use:

```sql
select series_id, trade_date, count(*)
from fact_choice_macro_daily
where series_id in (...)
group by series_id, trade_date
having count(*) > 1;

select series_id, count(*)
from choice_market_snapshot
where series_id in (...)
group by series_id
having count(*) > 1;
```

Both should return no rows.

## Task 3: Production Landing Runbook

**Files:**

- Use: production DuckDB path from `MOSS_DUCKDB_PATH`
- Use: production governance path from `MOSS_GOVERNANCE_PATH`
- Use: `config/choice_macro_catalog.json`

**Step 1: Snapshot current production state**

Before writing, record current counts and latest dates:

```sql
select count(*) from fact_choice_macro_daily;
select count(*) from choice_market_snapshot;
select count(*) from phase1_macro_vendor_catalog;
select count(*) from market_data_series_category;

select series_id, max(trade_date), count(*)
from fact_choice_macro_daily
where series_id in (...)
group by series_id;
```

Also create a filesystem copy of the DuckDB file before the write. This is the fastest rollback.

**Step 2: Run scoped production refresh**

Use the same Python call as the dev trial, but pass the production `duckdb_path` and `governance_dir`.

Expected:

- exactly 7 SHIBOR series landed;
- non-SHIBOR Choice row counts unchanged except for unrelated concurrent refreshes;
- governance streams receive `vendor_snapshot_manifest`, `vendor_version_registry`, and `cache_build_run`.
- Livermore gate supplement materialization is skipped because this is a scoped Choice refresh.
- If the task reports failure after DuckDB commit but before archive/governance completion, do not treat the landing as complete. Retry the same scoped refresh after checking the failed-run record and any partial archive/governance artifacts.

**Step 3: Post-write SQL checks**

Run:

```sql
select series_id, series_name, trade_date, value_numeric, unit, quality_flag
from fact_choice_macro_daily
where series_id in (...)
order by series_id, trade_date;

select series_id, trade_date, value_numeric, unit, source_version, vendor_version, rule_version, run_id
from choice_market_snapshot
where series_id in (...)
order by series_id;

select series_id, vendor_name, vendor_series_code, batch_id, refresh_tier, fetch_mode, fetch_granularity, request_options
from phase1_macro_vendor_catalog
where series_id in (...)
order by series_id;

select series_id, category_key, category_label, source_surface, batch_id
from market_data_series_category
where series_id in (...)
order by series_id;
```

Expected:

- `vendor_name = choice`
- `unit = %`
- `rule_version = rv_choice_macro_thin_slice_v1`
- `refresh_tier = fallback`
- `fetch_mode = latest`
- `fetch_granularity = single`
- `request_options = IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5`

## Task 4: API / UI Visibility Check

**Files:**

- Use: `backend/app/api/routes/macro_vendor.py`
- Use: `backend/app/services/macro_vendor_service.py`

**Step 1: Check latest Choice series API**

Call the existing read endpoint for Choice macro latest data after landing.

Expected:

- SHIBOR series are present.
- Response metadata includes `fact_choice_macro_daily` or `choice_market_snapshot` as source tables where applicable.
- `refresh_tier`, `fetch_mode`, and `policy_note` are surfaced if the service already exposes category metadata.

**Step 2: Check downstream consumers**

Only after the raw landing is correct, inspect pages/services that can benefit from SHIBOR:

- funding / NCD proxy
- market data rates
- macro toolkit
- PnL / Campisi context where macro rows are informational

Do not wire SHIBOR into formal business calculations until the consuming metric contract explicitly approves it.

## Task 5: Rollback

Preferred rollback: restore the pre-run DuckDB file copy.

Scoped SQL rollback if file restore is not practical:

```sql
delete from choice_market_snapshot where series_id in (...);
delete from fact_choice_macro_daily where series_id in (...);
delete from phase1_macro_vendor_catalog where series_id in (...);
delete from market_data_series_category where series_id in (...);
```

Then invalidate relevant API/page caches if the running app has already served the new rows.

## Validation Checklist

- Read-only Choice probe returns `error_code = 0`.
- Scoped refresh lands exactly seven SHIBOR series.
- No duplicate facts by `series_id + trade_date`.
- No duplicate catalog/category/snapshot rows by `series_id`.
- Duplicate vendor points are rejected before any scoped write, archive, or governance manifest.
- Existing non-SHIBOR Choice rows remain untouched in scoped mode.
- Scoped refresh reports Livermore gate supplement as skipped.
- Raw payload archive is present only for runs that pass the DuckDB commit boundary.
- Governance manifest and run records are written.
- No production write is attempted before dev DuckDB trial passes.
- No trading/order APIs are called.

## Alternative: Full Macro Refresh

There is a no-code path: run the existing `/ui/macro/choice-series/refresh` or `refresh_choice_macro_snapshot` full refresh after the catalog promotion. This would include SHIBOR automatically because `choice_funding_shibor_latest` is non-isolated.

I do not recommend this for the first SHIBOR landing unless the operator intentionally wants a full Choice macro refresh. The delete/reinsert scope is broader than SHIBOR and can change unrelated macro rows.
