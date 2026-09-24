# Average Balance Candidate Page Contract

## Purpose

This document defines the current review contract for `/average-balance` as a candidate analytical ADB page. It is not a formal page approval, not a replacement for `PAGE-BALANCE-001`, and not an owner approval.

## Page Identity

- Page ID: `PAGE-ADB-001`
- Contract binding: `PAGE-ADB-001`
- Page slug: `average-balance`
- Frontend route: `/average-balance`
- Primary API: `GET /api/analysis/adb`
- Supporting APIs:
  - `GET /api/analysis/adb/comparison`
  - `GET /api/analysis/adb/monthly`
  - `GET /api/analysis/adb/coverage`
  - `GET /ui/balance-analysis/dates`
- Current status: `candidate_or_pending`
- Formal use allowed: `formal_use_allowed=false`

## Primary Business Question

The page answers: for a selected date range, how do daily average asset and liability balances compare with ending spot balances, and what candidate explanatory categories drive the difference?

The page must show the ADB analytical boundary clearly and must not imply that interval ADB values are the formal balance truth.

## Metric Boundary

Daily sample-bound candidate metrics:

- `MTR-ADB-001`: interval daily average total assets, from `GET /api/analysis/adb` summary.
- `MTR-ADB-002`: interval daily average total liabilities, from `GET /api/analysis/adb` summary.

Monthly sample-bound candidate metric:

- `MTR-ADB-003`: YTD spread / monthly ADB-NIM view, from `GET /api/analysis/adb/monthly`; this metric has candidate sample coverage through `GS-AVERAGE-BALANCE-MONTHLY-A`.

`GS-AVERAGE-BALANCE-A` freezes only the daily ADB candidate DTO for `MTR-ADB-001` and `MTR-ADB-002`. `GS-AVERAGE-BALANCE-MONTHLY-A` freezes selected monthly ADB/NIM candidate DTO fields for `MTR-ADB-003`. Neither sample approves formal balance truth, manual audit closure, page closure, or business-owner approval.

## Denominator Semantics

The page must keep denominator semantics visible when they are present in result metadata or coverage output:

- `observed`: average over dates with observed source rows.
- `observed-days-scaled-to-calendar`: sparse-window analytical sample completion used by
  comparison and deep scale attribution; observed sums are scaled by
  `calendar_days / coverage_days` before applying the calendar-day denominator.
- `LOCF`: last-observation-carried-forward analytical fill, when explicitly provided by backend evidence.
- `calendar-zero`: calendar-day denominator where missing dates contribute zero, only when explicitly stated by backend evidence.

Frontend code must not infer, swap, or silently relabel these denominator modes. Missing or unavailable denominator metadata must be surfaced as pending or no-data evidence, not filled with demo values.

## Formal Truth Boundary

- Formal balance truth remains `PAGE-BALANCE-001` and `/balance-analysis`.
- `/average-balance` may use formal balance daily tables as source anchors, but that does not make the ADB interval result a formal balance value.
- Do not replace `/balance-analysis` totals, report-date controls, or closure evidence with `/average-balance` ADB output.
- Do not promote `MTR-ADB-001` through `MTR-ADB-003` to formal use until page contract approval, golden approval, direct lineage/governance records, live UI/API evidence, manual audit review, and business-owner approval are complete.

## Required Evidence Before Closure

- Direct page/API governance record for `PAGE-ADB-001` and `/api/analysis/adb`.
- Catalog/date evidence for:
  - `fact_formal_zqtz_balance_daily`
  - `fact_formal_tyw_balance_daily`
  - `zqtz_bond_daily_snapshot`
  - `tyw_interbank_daily_snapshot`
- Golden sample review for `GS-AVERAGE-BALANCE-A`, limited to the daily candidate DTO.
- Golden sample review for `GS-AVERAGE-BALANCE-MONTHLY-A`, limited to selected monthly ADB/NIM candidate DTO fields.
- Live smoke evidence for visible candidate, stale, fallback, no-data, denominator, date-range, and `result_meta` states.
- Completed owner evidence packet and signed business-owner approval template.

## Prohibitions

- Do not set `formal_use_allowed=true` for `/average-balance`.
- Do not use `GS-AVERAGE-BALANCE-A` or `GS-AVERAGE-BALANCE-MONTHLY-A` as metric approval, page approval, or business-owner approval.
- Do not hide candidate-only, stale, fallback, denominator, or no-data states.
- Do not backfill missing ADB, monthly, comparison, or coverage rows with static demo values.
- Do not treat written governance evidence as owner approval or live page execution proof.

## Comparison 端点 fail-visible（`GET /api/analysis/adb/comparison`）

`result_kind=adb.comparison`（`basis=analytical`，`formal_use_allowed=false`）。下列语义与 `frontend/src/api/contracts/cubeAdb.ts`、`tests/test_adb_analysis_api.py` 对齐；不构成 formal 提升，不扩展新口径。

### 有效余额与 coverage

- 仅 `market_value_is_valid=true` / `amount_is_valid=true` 且金额有限的行参与金额累计、`coverage_days` 与 LOCF 的 `end_date_seen` 判定。
- 无效行（含 `valid=false`、非有限数值）不参与上述任一口径。
- `coverage_days`：区间内资产侧（ZQTZ）与负债侧（ZQTZ+TYW）**有效余额**的不重复观测日**并集**；与共享 `GET /api/analysis/adb` 的观测日口径可不同。
- 显式标记有效的 **0 仍为有效余额**（可产出 `0.0` 总量，语义不同于 `null`）。

### 四个 total 字段（按侧 fail-visible）

| 字段 | 侧 | `null` 条件 |
| --- | --- | --- |
| `total_spot_assets` | 资产 | 该侧无任何有效余额行 |
| `total_avg_assets` | 资产 | 该侧无有效余额；或 `calendar_days_inclusive <= 1` 且未开 `simulated` |
| `total_spot_liabilities` | 负债 | 该侧无任何有效余额行 |
| `total_avg_liabilities` | 负债 | 同上 |

两侧可独立为 `null`（例如仅资产侧有数时负债 total 为 `null`，全局 reason 字段仍可为 `null`）。

### 不可用原因

- `avg_unavailable_reason`：`insufficient_window` \| `no_data` \| `null`
  - `insufficient_window`：`calendar_days_inclusive <= 1` 且未模拟（单日窗口区间日均不可得）
  - `no_data`：资产与负债两侧均无有效余额
  - `null`：至少一侧可用且非 `insufficient_window`
- `spot_unavailable_reason`：`no_data` \| `null`
  - `no_data`：两侧均无有效余额
  - `null`：至少一侧有有效余额

未知 reason 取值前端安全归一为 `null`（不伪造文案）。

### 稀疏窗口 sample fill

当 `0 < coverage_days < calendar_days_inclusive` 时，`sample_filled=true`、`sample_fill_method=observed_days_scaled_to_calendar`；**仅有效行**进入观测日合计，再按 `calendar_days / coverage_days` 放大后除以日历分母。

### 前端展示（不得前端补数）

- `null` → `EM_DASH`（`--`）；禁止用 0 顶替缺失。
- 偏离度（期末 vs 日均）、KPI 同比/增减：任一侧 total 为 `null` 时不计算（显示 `EM_DASH`），不触发 \|偏离\|>5% 预警。
- 不可用原因在区块头/KPI detail 披露一次；表格行内仅安静 `EM_DASH`。

## 深度分析端点（adb.insights）

`GET /api/analysis/adb/insights?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` 返回 `result_kind=adb.insights` 的分析信封（`basis=analytical`，`formal_use_allowed=false`），一次聚合四类深度分析块：规模变动归因（环比 qoq + 同比 yoy）、NIM 量价归因（仅 qoq，含 rate/mix/residual 分解）、日度波动与异常检测（std/cv/z-score/月末效应）、结构集中度与迁移（HHI/Top3/Top5/movers）。`insights` 字段为确定性规则引擎输出的结构化结论列表（severity/dimension/title/detail/evidence），并入页面"区间结论与警示"区展示。

本端点及 `MTR-ADB-004`~`MTR-ADB-007` 均为 candidate 状态，不构成 formal 提升；响应必须保持 `formal_use_allowed=false`。对比窗口（qoq/yoy）缺数时 fail-visible：窗口对象 `available=false`、`reason="no_data"`，对应分析块为 `null`，并生成 `comparison_unavailable` insight；本期无有效数值余额时所有分析块为 `null` 并生成 `current_unavailable` insight；区间过短（`D<=1`）时 `insufficient_window=true`、分析块全为 `null`。详细 TypeScript 契约与公式定义见 `docs/plans/2026-08-13-average-balance-deep-analysis-prd.md`。
