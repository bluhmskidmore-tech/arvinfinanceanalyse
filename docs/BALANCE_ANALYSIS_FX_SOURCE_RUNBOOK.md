# Balance Analysis FX Source Runbook

## Scope

This runbook is limited to the `zqtz / tyw` formal balance stream.
It does not authorize unrelated Phase 2 work, Agent MVP work, or broad frontend rollout.

## Official FX Drop Contract

Current repo-executable contract:

- Preferred drop path: `data_input/fx/fx_daily_mid.csv`
- Compatibility drop path: `data_input/fx_daily_mid.csv`
- Explicit override: `MOSS_FX_OFFICIAL_SOURCE_PATH`
- Legacy explicit override retained for compatibility: `MOSS_FX_MID_CSV_PATH`
- Required header row:
  `trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward`

Notes:

- The executable ingest contract for this stream is a normalized CSV landing file.
- `source_name` should reflect the official source family, for example `CFETS` or `SAFE`.
- When an explicit path is configured, the path must exist; the pipeline fails closed and does not silently fall back.
- The repo currently has no raw official non-CSV sample. In other words, there is no checked-in `xls`, `xlsx`, or `pdf` source specimen that proves a bounded parser contract. Because the raw official non-CSV sample is absent, the current runtime supports only the normalized CSV landing contract above.

## Standard Entrypoint

Use the stable task/module entrypoint instead of ad-hoc one-off scripts:

```bash
python -m backend.app.tasks.formal_balance_pipeline \
  --report-date 2026-02-27 \
  --data-root F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/data_input \
  --duckdb-path F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/moss.duckdb \
  --governance-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/governance \
  --archive-dir F:/MOSS-V3/tmp-governance/runtime-fx-discovery-20260412T073500Z/archive
```

Optional explicit FX override:

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

Recommended regression command:

```bash
pytest -q tests/test_agent_api_contract.py tests/test_agent_intent_routing.py tests/test_fx_mid_materialize.py tests/test_snapshot_materialize_flow.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_service.py tests/test_balance_analysis_api.py tests/test_balance_analysis_boundary_guards.py
```

## Blocker Statement

If a future delivery provides the real official source only as `xls`, `xlsx`, or `pdf`, that is a new concrete parser task.
Do not guess the raw format. Add the smallest parser that matches the supplied sample, lock it with tests, and keep the scope inside the FX materialization path.
