# Choice Macro Refresh Strategy Design (2026-04-11)

## Scope

- Workstream: external data plane / Choice macro thin slice
- In scope: catalog strategy, batch policy, governance metadata, refresh stability
- Out of scope: Choice live login chain, formal finance, frontend formal calculation, snapshot/source preview expansion

## Current Evidence Baseline

Based on:

- `data/choice_coverage_2026-04-11_post_cmd2_split_effective.json`
- `data/choice_empty_recovery_probe_2026-04-11.json`
- `data/choice_support_issue_list_2026-04-11.md`

Observed classification over `118` catalog series:

- `51` series are already stable on same-day date-slice and should stay in the main refresh lane.
- `48` series are retrievable only after switching to `IsLatest=1` and single-series fetch behavior.
- `19` series still return `10000009 / no data` after latest-single probes and must remain isolated until vendor confirmation arrives.

## Next-Version Strategy

### Lane 1: `stable_daily`

- `fetch_mode=date_slice`
- `fetch_granularity=batch`
- `refresh_tier=stable`
- request template: `IsLatest=0,StartDate=__RUN_DATE__,EndDate=__RUN_DATE__,Ispandas=1,RECVtimeout=5`

Use this lane only for the `51` series already proven on the same-day slice. This is the default main refresh path and should remain the only lane whose failures are treated as main-path regressions.

Representative families:

- 人民币中间价 / 人民币指数
- 中债国债收益率曲线
- 中债国开债收益率曲线
- 中债企业债 AAA / AA 部分期限点

### Lane 2: `fallback_latest_single`

- `fetch_mode=latest`
- `fetch_granularity=single`
- `refresh_tier=fallback`
- request template: `IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5`

Use this lane for the `48` sparse or low-frequency series. They should still participate in the default refresh, but only as a degraded lane executed independently from the stable lane so that one empty series does not poison the whole batch.

Representative families:

- GDP / 工业增加值 / CPI 等低频宏观指标
- 存贷款基准利率等长时间不变指标
- 地方政府债收益率历史停更曲线
- M0 / M1 / M2 / 社融 / 逆回购等通过 latest-single 已验证可取的序列

### Lane 3: `isolated_vendor_pending`

- `fetch_mode=latest`
- `fetch_granularity=single`
- `refresh_tier=isolated`
- request template: `IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5`

These `19` series must not enter the default refresh until Choice support confirms the correct interface or permission package:

- SHIBOR: `EMM00166252`, `EMM00166253`, `EMM00166254`
- 银行间同业拆借加权利率: `EMM00167612`, `EMM00167613`, `EMM00167614`, `EMM00167708`
- LPR IRS 曲线: `EMM01474568` to `EMM01474572`
- 美元兑人民币 C-Swap 曲线: `EMI01743799` to `EMI01743805`

## Governance Changes Landed

- `config/choice_macro_catalog.json` now expresses explicit batch strategy instead of relying on hardcoded `cmd2` behavior.
- `backend/app/tasks/choice_macro.py` resolves `__RUN_DATE__` dynamically and skips `refresh_tier=isolated` batches by default.
- The per-series DuckDB catalog metadata now persists `fetch_mode`, `fetch_granularity`, `refresh_tier`, and `policy_note`.

## Expected Outcome

- Main stable path is reduced to a deterministic `51`-series daily/date-slice lane.
- Low-frequency series remain available without destabilizing the main batch path.
- Vendor-pending series stay visible in governance artifacts but out of the default refresh path.

## Artifacts

- Machine-readable classification: `data/choice_refresh_strategy_2026-04-11.json`
- Updated runtime catalog: `config/choice_macro_catalog.json`
