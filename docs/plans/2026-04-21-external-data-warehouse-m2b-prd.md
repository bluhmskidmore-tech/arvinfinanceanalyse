# External Data Warehouse — M2b PRD (std/vw + ETL + access port + legacy catalog)

**Status:** delivered (M2b)  
**Date:** 2026-04-22  
**Parent:** `.omx/specs/deep-interview-external-data-warehouse.md`, decisions in `deep-interview-external-data-warehouse-decisions.md`

## Scope (M2b)

- **D2:** Physical `std_external_macro_daily` + contract view `vw_external_macro_daily` (DuckDB `15_external_std_macro.sql`, migration v14).
- **IS3/IS5:** Read-only `vw_external_legacy_*` over existing Choice/Akshare/FX/macro fact tables without schema changes (`16_external_vw_legacy.sql`, migration v15).
- **ETL:** `ExternalStdMacroEtlService` — raw Tushare JSON `rows` → `std_external_macro_daily` (idempotent on `(series_id, trade_date, ingest_batch_id)`).
- **Ingest:** Optional `TushareMacroIngestService(etl_service=...)` to std-load after raw archive; `access_path` set to `select * from vw_external_macro_daily where series_id = '…'`.
- **HTTP (D4 M2):** `GET /api/external-data/series/{series_id}/data` and `.../data/recent` — implementation uses catalog `view_name` / `std` **allowlist** (no arbitrary SQL).
- **Catalog seed:** `legacy_catalog_seed` (4 umbrella series) + `register_tushare_m2a_catalog_descriptors`; task `run_external_data_catalog_seed_once()`.

## Out of scope (M2c+)

- Choice macro data migration into `std_external_macro_daily` (D6), dual-write, or decommission of `fact_choice_macro_daily` writes.
- `macro_vendor_service`, `choice_adapter`, `choice_macro` / `fx_mid_*` / `yield_curve_*` tasks (unchanged).

## Acceptance

- Migrations 14–15 registered; `manifest.json` lists `15_` / `16_` files.
- New tests: `test_external_std_macro_etl_service`, `test_external_data_query_service`, `test_external_data_api_m2b`, `test_legacy_catalog_seed`.
- `ruff check` clean on touched modules; pytest from `backend/` per project convention.

## Smoke

With API on port **7888** (e.g. `scripts/dev-api.ps1`), after seed + ingest (if applicable):

`curl "http://127.0.0.1:7888/api/external-data/series/tushare.macro.cn_cpi.monthly/data?limit=5"`

(Expect 200 if catalog + std rows exist; otherwise 404 until ingest.)
