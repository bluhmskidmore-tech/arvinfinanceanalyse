# Balance Analysis FX Source Runbook

## Scope

This runbook is limited to the `zqtz / tyw` formal balance stream.
It does not authorize unrelated Phase 2 work, Agent MVP work, or broad frontend rollout.

## Governed Formal FX Contract

Current repo-executable normal path:

`Choice catalog-driven middle-rate discovery -> Choice live fetch -> ChinaMoney/CFETS official history -> AkShare fallback -> fail closed`

Key rules:

- Repo-owned Choice catalog assets are the authority source for formal FX candidate discovery.
- Formal candidates are restricted to genuine `middle-rate` FX series only.
- Current first-wave formal candidate set is catalog-derived and normalizes to:
  - `AUD -> CNY`
  - `EUR -> CNY`
  - `USD -> CNY`
  - `CAD -> CNY`
  - `HKD -> CNY` (from reverse supplier orientation such as `人民币兑港元`)
- Persisted formal rows must normalize to `(trade_date, base_currency, quote_currency='CNY')`.
- Reverse supplier orientation must be inverted before persistence.
- ChinaMoney response values must be mapped by the returned `searchlist` pair names; response position alone is not authoritative.
- ChinaMoney `HKD/CNY` is already normalized and must not be inverted a second time merely because the Choice catalog candidate uses reverse orientation.
- Missing required formal middle-rates must fail closed.
- Non-middle-rate FX observations such as RMB indices or FX swap curves stay analytical-only and must not backflow into `fx_daily_mid`.

## CFETS FX Business Calendar

Formal carry-forward is governed by the CFETS/ChinaMoney annual interbank FX
currency holiday table, not by a generic weekend-only calendar.

Current executable calendar source:

- `backend/app/core_finance/fx_calendar.py`
- official notice:
  `https://www.chinamoney.com.cn/chinese/rdgz/20251218/3254567.html`
- cross-check surface:
  `https://www.shclearing.cn/qsywzq/whzq/`

The 2026 table was published by China Foreign Exchange Trade System and Shanghai
Clearing House on 2025-12-18. The attachment excludes weekends and lists
currency-specific holidays. Code therefore treats a date as non-business when
either side of the currency pair is on its CFETS holiday list, or when the date
falls on that currency's weekend convention.

Formal rule:

- same-date official middle rate is accepted;
- prior observed date is accepted only when the requested report date is a
  confirmed CFETS non-business day for the currency pair;
- ordinary weekday vendor misses still fail closed.

Residual operational rule: the CFETS notice says temporary 2026 currency-holiday
adjustments will be announced separately. Those notices must be ingested into the
calendar before relying on carry-forward for affected dates.

## Choice Authority Source

Current authority files:

- `config/choice_macro_catalog.json`
- generated from `config/choice_macro_commands_2026-04-09.txt`

Current known formal reference series include:

- `EMM00058129` -> `中间价:澳元兑人民币`
- `EMM00058125` -> `中间价:欧元兑人民币`
- `EMM00058124` -> `中间价:美元兑人民币`
- `EMM00058130` -> `中间价:加拿大元兑人民币`
- `EMM01588399` -> `中间价:人民币兑港元`

The catalog is the discovery surface. Code must not maintain a second hardcoded formal-series registry that bypasses catalog selection.

## ChinaMoney Official Fallback

When Choice is unavailable or incomplete, the formal task queries the China
Foreign Exchange Trade System history endpoint exposed by ChinaMoney. Candidate
membership still comes from the Choice catalog; the official response only
supplies the dated values for those governed pairs.

- Page: `https://www.chinamoney.com.cn/chinese/bkccpr/`
- History endpoint: `https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew`
- Persisted `source_name`: `CFETS`
- Persisted `vendor_name`: `chinamoney`
- Ordinary weekday gaps remain fail-closed; carry-forward remains subject to the CFETS calendar rule above.

## Explicit Manual Override Path

The CSV/manual path is no longer the normal governed formal route.
It remains available only as an explicit override for controlled/manual replay.

Explicit override variables:

- `MOSS_FX_OFFICIAL_SOURCE_PATH`
- `MOSS_FX_MID_CSV_PATH`

If an explicit override path is configured, it must exist or the pipeline fails closed.
There is no silent data-root CSV fallback on the governed normal path.

## Standard Entrypoints

Canonical full core-data refresh:

```bash
python scripts/run_global_data_refresh.py --report-date 2026-07-31
```

Plan-only preflight:

```bash
python scripts/run_global_data_refresh.py --report-date 2026-07-31 --dry-run
```

This entrypoint is report-date driven, serialized by a global operator lock,
stops at the first required failure, and ends with table/date and formal FX
completeness/lineage checks. It never auto-discovers an FX CSV; a manual replay
must pass `--fx-source-path` explicitly.

Formal balance pipeline:

```bash
python -m backend.app.tasks.formal_balance_pipeline \
  --report-date 2026-02-27 \
  --data-root F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/data_input \
  --duckdb-path F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/moss.duckdb \
  --governance-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/governance \
  --archive-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/archive
```

Historical backfill:

```bash
python -m backend.app.tasks.fx_mid_backfill \
  --start-date 2026-02-01 \
  --end-date 2026-02-29 \
  --duckdb-path F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/moss.duckdb \
  --governance-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/governance
```

Optional explicit manual override for the formal balance pipeline:

```bash
python -m backend.app.tasks.formal_balance_pipeline \
  --report-date 2026-02-27 \
  --data-root F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/data_input \
  --duckdb-path F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/moss.duckdb \
  --governance-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/governance \
  --archive-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/archive \
  --fx-source-path F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/data_input/fx/fx_daily_mid.csv
```

## Verification Checklist

After the pipeline completes, verify the governed read surfaces:

1. `/ui/balance-analysis/overview`
2. `/ui/balance-analysis`
3. `/ui/balance-analysis/workbook`
4. `/ui/market-data/fx/formal-status`
5. `/ui/market-data/fx/analytical`

Recommended regression command:

```bash
pytest -q tests/test_fx_mid_materialize.py tests/test_choice_fx_catalog_selection.py tests/test_akshare_adapter_fx.py tests/test_fx_mid_backfill.py tests/test_fx_mid_backfill_governance.py tests/test_fx_analytical_view_service.py tests/test_fx_analytical_view_api.py tests/test_balance_analysis_materialize_flow.py
```

## Blocker Statement

If a future delivery provides the real official source only as `xls`, `xlsx`, or `pdf`, that is a new concrete parser task.
Do not guess the raw format. Add the smallest parser that matches the supplied sample, lock it with tests, and keep the scope inside the FX materialization path.
