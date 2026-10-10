# Home Macro Release Context Evidence

## Scope and boundary

- Evidence captured: `2026-07-17` for `PAGE-DASH-001` and the supporting API `/ui/home/macro-release-context`.
- The handoff filename retains the approved plan date `2026-07-16`; the evidence above records the actual refresh date.
- The read model remains `basis=analytical`, `formal_use_allowed=false`, `result_kind=home.macro_release_context`, and `source_surface=market_data`.
- This evidence supports Phase A automatic historical observations only. It does not approve formal metrics, database schema changes, or the `std_tushare_eco_cal_event` surface as release-calendar truth.

## MCP availability and fallback evidence

`codex mcp list` confirmed that `moss-metric-contracts`, `moss-lineage-evidence`, and `moss-data-catalog` are registered and enabled. The current Codex App session did not expose callable `moss-*` tools, so the required calls could not be executed in this session. This is recorded as a client/session tool-surface limitation, not a repository registration failure.

Fallback evidence used:

- local page contracts, schema registry, catalog seeds, and targeted tests;
- read-only DuckDB queries against `F:\MOSS-V3\data\moss.duckdb`;
- GitNexus CLI impact analysis against repository index `moss-v3-codex-v1`;
- `pytest tests/test_project_mcp_servers.py -q`: `201 passed`.

The fallback evidence does not grant metric promotion, formal approval, or source certification. Any binding that cannot be proven remains `source_pending`.

## Read-only catalog and observation checks

Representative queries used the canonical latest-batch pattern before choosing latest and previous observations:

```sql
select *
from std_external_macro_daily
where series_id = ?
qualify row_number() over (
  partition by series_id, trade_date
  order by created_at desc, ingest_batch_id desc
) = 1
order by trade_date desc;
```

Table and source availability was checked through `information_schema.tables`, distinct `series_id` values in `std_external_macro_daily`, and matching rows in `external_data_catalog`. No write statement was executed.

### Resolved China bindings

| Group / metric | Automatic table and series | Latest | Previous | Unit / cadence | Lineage evidence |
| --- | --- | --- | --- | --- | --- |
| China PMI / manufacturing PMI | `fact_choice_macro_daily` / `M0017126` | `2026-06-01 = 50.3` | `2026-05-01 = 50.0` | `index` / monthly | `source_version=backfill_macro_v1`; `vendor_version=vv_backfill_macro_nbs_pmi_release_20260710_204801316c86ecf8_e6c278bdb0d88252`; `rule_version=rv_backfill_macro_v1`; `run_id=backfill_macro_v1:20260713T031530Z` |
| China inflation / CPI YoY | `std_external_macro_daily` / `tushare.macro.cn_cpi.monthly` | `2026-05-01 = 1.2` | `2026-04-01 = 1.2` | `pct` / monthly | Tushare lineage below |
| China inflation / PPI YoY | `std_external_macro_daily` / `tushare.macro.cn_ppi.monthly` | `2026-05-01 = 3.9` | `2026-04-01 = 2.8` | `pct` / monthly | Tushare lineage below |
| China growth / GDP YoY | `std_external_macro_daily` / `tushare.macro.cn_gdp.quarterly` | `2025-12-31 = 5.0` | `2025-09-30 = 5.2` | `pct` / quarterly | Tushare lineage below |

For the checked Tushare observations, the latest evidence was `vendor_version=tushare|m2b.tushare_macro.v1`, `source_version=raw@2026-06-30T15:07:05+00:00`, `rule_version=m2b.external_std_macro_etl.v1`, and `ingest_batch_id=tushare-macro-20260630T150702Z-545cbdf9`.

`external_data_catalog` records CPI, PPI, and GDP with `vendor_name=tushare`, `source_family=tushare_macro`, `domain=macro`, cadence monthly or quarterly, `unit=pct`, `refresh_tier=on_demand`, and `catalog_version=m2a.tushare_macro.v1`.

### Duplicate-batch evidence

`std_external_macro_daily` preserves more than one ingest batch for the same `series_id + trade_date`. Examples include two batches for CPI on `2026-04-01`, two batches for PPI on `2026-03-01`, and four batches for several older monthly observations. Therefore, the page repository must select the newest `created_at/ingest_batch_id` for each observation period before it selects latest and previous values. Historical batches must not be deleted.

### Unresolved United States bindings

No automatic series or catalog binding was found for US ISM, US inflation, US employment, US growth, or FOMC in `std_external_macro_daily` or `external_data_catalog`. All five configured US groups remain `source_pending`; absence is not zero and cannot be filled from static history.

`std_tushare_eco_cal_event` exists in the current database, but it is not the governed observation-series binding for these metrics and is not accepted as Phase A history truth.

## GitNexus upstream impact gate

| Symbol | Risk | Direct / affected evidence | Decision |
| --- | --- | --- | --- |
| `run_tushare_macro_ingest_once` | LOW | 4 direct test callers; no affected process | Task 1 may edit within the tested boundary. |
| `TushareMacroIngestService.ingest_series` | LOW | 6 affected total; direct callers are `ingest_all_seed_series`, `_ingest_series_with_retry`, and one test; task entry is indirect | Task 1 may edit with targeted tests. |
| `backfill_macro_series` | HIGH | 17 direct test callers; no affected process | Reference-only; excluded from Tasks 0-2 edits. |
| `CANONICAL_TASK_MODULES` | LOW | 0 callers | Task 1 may add the explicit task module. |
| `_ensure_executive_read_allowed` | MEDIUM | 9 direct route callers; `home_snapshot` process affected | Not edited in Tasks 0-2. |
| `createRealHomeExecutiveClient` | LOW | 0 callers | Later frontend task only. |
| `createDeferredApiClient` | LOW | 4 test callers | Later frontend task only. |
| `useDashboardHomeBodyData` | LOW | 1 test caller | Later frontend task only. |
| `useDashboardHomeViewModel` | LOW | 1 test caller | Later frontend task only. |
| `mapToHomeBodyView` | LOW | 6 affected | Later frontend task only. |
| `buildHomeMacroBriefingModel` | MEDIUM | 13 affected | Later frontend task requires targeted adapter and view tests. |
| `ResearchCalendarSection` | LOW | 0 callers | Later frontend task only. |

`ExecutiveClientMethods` was not indexed as a standalone GitNexus symbol. Before its later edit, local type consumers and composition-boundary tests must substitute for the missing symbol result. No HIGH or CRITICAL symbol is edited in Tasks 0-2.

## Residual risks and required controls

- The current Tushare formal task does not yet guarantee materialization into `std_external_macro_daily`; Task 1 must close that gap before the new page read model is considered automatically refreshed.
- Duplicate batches require deterministic canonical selection; a raw `LIMIT 2` is invalid.
- GDP freshness needs a page-local conservative quarterly rule until a governed shared quarterly cadence exists.
- Future release dates remain Phase B. `release_date`, `observation_date`, and `previous_observation_date` must stay separate.
- API failure must surface `自动数据暂不可用`; static historical numeric fallback is prohibited.
