# Balance Analysis FX Source Runbook

## Scope

This runbook is limited to the `zqtz / tyw` formal balance stream.
It does not authorize unrelated Phase 2 work, Agent MVP work, or broad frontend rollout.

## Governed Formal FX Contract

Current repo-executable normal path:

`Choice catalog-driven middle-rate discovery -> Choice live fetch -> AkShare fallback -> fail closed`

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
- Missing required formal middle-rates must fail closed.
- Non-middle-rate FX observations such as RMB indices or FX swap curves stay analytical-only and must not backflow into `fx_daily_mid`.

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

## Explicit Manual Override Path

The CSV/manual path is no longer the normal governed formal route.
It remains available only as an explicit override for controlled/manual replay.

Explicit override variables:

- `MOSS_FX_OFFICIAL_SOURCE_PATH`
- `MOSS_FX_MID_CSV_PATH`

If an explicit override path is configured, it must exist or the pipeline fails closed.
There is no silent data-root CSV fallback on the governed normal path.

## Standard Entrypoints

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
