# 首批黄金样本目录（v1 草案）

## 1. 目的

本文件把 [golden_sample_plan.md](</F:/MOSS-V3/docs/golden_sample_plan.md>) 的“计划”推进到“可执行目录”。

本文件回答 5 个问题：

1. 第一批样本具体抓哪些 surface
2. 每个样本用哪个 `report_date`
3. 每个样本当前是 `capture-ready` 还是仍有阻塞
4. 每个样本应该断言哪些指标 / 结构
5. 样本之间如何对账

## 2. 状态定义

### `capture-ready`

含义：

- 当前仓库已有稳定测试 seed 到具体 `report_date`
- endpoint 合同和主断言已明确
- 可以直接进入 `request.json / response.json / assertions.md / approval.md` 落盘

### `candidate-needs-probe`

含义：

- endpoint、页面契约、指标映射和上游证据已足够
- 但还缺一次显式抓取验证，才能冻结为正式样本

### `blocked-by-contract-gap`

含义：

- 当前路由或 outward contract 缺少关键冻结条件
- 在补合同前不应把它写成黄金样本

## 3. 第一批范围

本批覆盖 `tests/golden_samples/` 下 **23** 个目录所对应的主链与治理边界（其中 22 个为 capture-ready，1 个为 supporting-only；含 warning profile）；产品分类样本以 **truth contract** 与 **page contract `PAGE-PROD-CAT-PNL-001`** 为权威，不等同于“指标字典已全覆盖”。

- `/ui/balance-analysis/overview`
- `/ui/balance-analysis/workbook`
- `/api/pnl/overview`
- `/api/pnl/data`
- `/ui/pnl/product-category`（`GS-PROD-CAT-PNL-A`）
- `/api/pnl/bridge`（含 `GS-BRIDGE-WARN-B`）
- `/api/risk/tensor`（含 `GS-RISK-WARN-B`）
- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`
- `/api/ledger-pnl/summary`
- `/api/cashflow-projection` (`GS-CASHFLOW-PROJECTION-A`)
- `/api/bond-analytics/action-attribution`
- `/api/bond-analytics/credit-spread-migration` (`GS-CONCENTRATION-MONITOR-A`)
- `/ui/market-data/livermore`（`GS-STOCK-ANALYSIS-OBS-A`）
- `/ui/market-data/rates` formal fragment（`GS-MKT-RATES-FRAGMENT-A`；**非** full-page closure）
- `/api/analysis/adb` (`GS-AVERAGE-BALANCE-A`)

不纳入本批：

- `/` 驾驶舱聚合页
- `/api/bond-dashboard/headline-kpis`（`GS-BOND-HEADLINE-A` 已为 **capture-ready** 页面样本）
- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- Agent

原因：

- 驾驶舱聚合页混合了 live / excluded section，不适合作为第一批黄金样本主包
- `bond-analytics` 在 `golden_sample_plan.md` 中已被识别为重要样本来源；`docs/page_contracts.md` 已补入 `PAGE-BOND-001`，但 Headline / 风险卡的 `metric_id` 同源与样本目录仍未冻结，因此本目录继续将其延后，而不是伪装成当前首批已就绪样本
- excluded surface 当前就是 `503 fail-closed`

## 4. 样本落盘路径

建议路径：

```text
tests/golden_samples/
  GS-BAL-OVERVIEW-A/
  GS-BAL-WORKBOOK-A/
  GS-PNL-OVERVIEW-A/
  GS-PNL-DATA-A/
  GS-PNL-ATTR-WB-A/
  GS-BOND-HEADLINE-A/
  GS-BOND-ANALYSIS-ACTION-ATTR-A/
  GS-CONCENTRATION-MONITOR-A/
  GS-STOCK-ANALYSIS-OBS-A/
  GS-AVERAGE-BALANCE-A/
  GS-PROD-CAT-PNL-A/
  GS-BRIDGE-A/
  GS-BRIDGE-WARN-B/
  GS-RISK-A/
  GS-RISK-WARN-B/
  GS-EXEC-OVERVIEW-A/
  GS-EXEC-PNL-ATTR-A/
  GS-EXEC-SUMMARY-A/
  GS-LEDGER-PNL-SUMMARY-A/
  GS-CASHFLOW-PROJECTION-A/
  GS-PORTFOLIO-HOME-A/
```

每个目录包含：

- `request.json`
- `response.json`
- `assertions.md`
- `approval.md`

## 5. Batch A 样本总表

与 `tests/test_golden_samples_capture_ready.py` 中注册的 22 个 `sample_id` 对齐（含 `GS-PNL-ATTR-WB-A`、`GS-BRIDGE-WARN-B`、`GS-RISK-WARN-B`、`GS-BOND-HEADLINE-A`、`GS-BOND-ANALYSIS-ACTION-ATTR-A`、`GS-CONCENTRATION-MONITOR-A`、`GS-STOCK-ANALYSIS-OBS-A`、`GS-MKT-RATES-FRAGMENT-A`、`GS-AVERAGE-BALANCE-A`、`GS-AVERAGE-BALANCE-MONTHLY-A`、`GS-LEDGER-PNL-SUMMARY-A`、`GS-CASHFLOW-PROJECTION-A` 与 `GS-PROD-CAT-PNL-A`）。`GS-PORTFOLIO-HOME-A` 是 supporting-only 样本包，不进入 capture-ready 矩阵。

| sample_id | surface | status | preferred_report_date | 证据来源 | 样本类型 |
| --- | --- | --- | --- | --- | --- |
| `GS-BAL-OVERVIEW-A` | `/ui/balance-analysis/overview` | `capture-ready` | `2025-12-31` | `tests/test_balance_analysis_api.py` | 正常样本 |
| `GS-BAL-WORKBOOK-A` | `/ui/balance-analysis/workbook` | `capture-ready` | `2025-12-31` | `tests/test_balance_analysis_api.py`、`tests/test_balance_analysis_workbook_contract.py` | 结构样本 |
| `GS-PNL-OVERVIEW-A` | `/api/pnl/overview` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 正常样本 |
| `GS-PNL-DATA-A` | `/api/pnl/data` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 明细样本 |
| `GS-PNL-ATTR-WB-A` | `GET /api/pnl-attribution/volume-rate` | `capture-ready` | `2026-04-30` | `tests/test_pnl_attribution_workbench_contract.py` + `tests/test_golden_samples_capture_ready.py` | workbench primary API 样本 |
| `GS-BOND-HEADLINE-A` | `GET /api/bond-dashboard/headline-kpis` | `capture-ready` | `2026-03-31` | `tests/test_bond_dashboard_api_contract.py`、`tests/test_golden_samples_capture_ready.py` | bond-dashboard headline 页面样本 |
| `GS-BOND-ANALYSIS-ACTION-ATTR-A` | `GET /api/bond-analytics/action-attribution` | `capture-ready` | `2026-03-31` | `tests/test_golden_samples_capture_ready.py`、`tests/test_bond_analysis_business_owner_approval_status.py` | bond-analysis action-attribution 页面 DTO 样本 |
| `GS-CONCENTRATION-MONITOR-A` | `GET /api/bond-analytics/credit-spread-migration` | `capture-ready` | `2026-03-31` | `tests/test_golden_samples_capture_ready.py` | concentration-monitor candidate concentration DTO sample; not formal risk truth or certified concentration-limit approval |
| `GS-STOCK-ANALYSIS-OBS-A` | `GET /ui/market-data/livermore` | `capture-ready` | `2026-04-03` | `tests/test_golden_samples_capture_ready.py`、`tests/test_stock_analysis_business_owner_approval_status.py` | stock-analysis Livermore observational 页面 DTO 样本；非交易指令 |
| `GS-MKT-RATES-FRAGMENT-A` | `GET /ui/market-data/rates` | `capture-ready` | `2026-04-10` | `tests/test_golden_samples_capture_ready.py`、`frontend/src/features/market-data/lib/marketDataRatesFragmentGolden.test.ts` | PAGE-MKT-001 formal rates **fragment** only；不关闭 `GAP-MKT-DATA` |
| `GS-AVERAGE-BALANCE-A` | `GET /api/analysis/adb` | `capture-ready` | `2025-12-31` | `tests/test_golden_samples_capture_ready.py` | average-balance daily ADB candidate DTO sample; not formal balance truth, monthly ADB/NIM truth, manual audit, or owner approval |
| `GS-LEDGER-PNL-SUMMARY-A` | `GET /api/ledger-pnl/summary` | `capture-ready` | `2026-04-30` | `tests/test_ledger_pnl_service.py`、`tests/test_golden_samples_capture_ready.py` | ledger-pnl 页面级 summary DTO 样本 |
| `GS-CASHFLOW-PROJECTION-A` | `GET /api/cashflow-projection` | `capture-ready` | `2026-04-30` | `tests/test_cashflow_projection.py`, `tests/test_golden_samples_capture_ready.py` | cashflow-projection candidate liquidity projection DTO sample; not formal liquidity/risk/balance/PnL truth |
| `GS-PROD-CAT-PNL-A` | `GET /ui/pnl/product-category` | `capture-ready` | `2026-02-28` | `tests/test_product_category_pnl_flow.py`、`tests/test_golden_samples_capture_ready.py` | formal 明细/主表样本 |
| `GS-BRIDGE-A` | `/api/pnl/bridge` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 正常样本 |
| `GS-BRIDGE-WARN-B` | `/api/pnl/bridge` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py`（warning profile） | `warning-profile` 样本 |
| `GS-RISK-A` | `/api/risk/tensor` | `capture-ready` | `2026-03-31` | `tests/test_risk_tensor_api.py`、`tests/test_risk_tensor_service.py` | 正常样本 |
| `GS-RISK-WARN-B` | `/api/risk/tensor` | `capture-ready` | `2026-03-31` | `tests/test_risk_tensor_api.py`（degraded） | `warning-profile` 样本 |
| `GS-EXEC-OVERVIEW-A` | `/ui/home/overview` | `capture-ready` | `2026-02-28` | `tests/test_executive_release_contract.py` + `tests/test_executive_dashboard_endpoints.py` | overlay 样本 |
| `GS-EXEC-PNL-ATTR-A` | `/ui/pnl/attribution` | `capture-ready` | `2026-02-28` | `tests/test_executive_release_contract.py` + `tests/test_executive_dashboard_endpoints.py` | overlay 样本 |
| `GS-EXEC-SUMMARY-A` | `/ui/home/summary` | `capture-ready` | `2026-02-28` | `tests/test_executive_release_contract.py` + `tests/test_executive_dashboard_endpoints.py` | narrative 样本 |

## 5.1 Bond dashboard headline sample status

| sample_id | surface | status | 说明 |
| --- | --- | --- | --- |
| `GS-BOND-HEADLINE-A` | `GET /api/bond-dashboard/headline-kpis` | `capture-ready` | 冻结 bond-dashboard 首屏 headline DTO 真值、环比字段、空态行为与 candidate metadata；**不**自动批准 `GAP-BOND-DASH-HL` 的字典级 `MTR-*` 绑定 |

## 5.2 Wave 1 页面：`page_id` → `metric_id` → `sample_id` → 测试

与 `docs/metric_dictionary.md` §12.5 对齐；用于系统闭环 Wave 1 四条工作台路由（`/bond-dashboard`、`/positions`、`/market-data`、`/operations-analysis`）。`/market-data` 保持 mixed-source；**无** full-page capture-ready golden sample，但 `GS-MKT-RATES-FRAGMENT-A` 已冻结 `GET /ui/market-data/rates` formal rates 片段（`capture-ready pending approval`）。`/market-data` 的 **GAP-MKT-DATA**、NCD proxy、Livermore blocked、宏观联动警示等文档化边界见 `docs/page_contracts.md` §13.8.J 与 `docs/plans/market-workbench-cursor-prompts.md`（执行拆分，非权威定义）。

| 前端路由 | `page_id` | 可钉 `metric_id`（字典已批） | `sample_id` | 测试锚点 |
| --- | --- | --- | --- | --- |
| `/operations-analysis` | `PAGE-OPS-001` | `MTR-BAL-001`~`003`, `MTR-BAL-101`~`102`（overview 切片） | `GS-BAL-OVERVIEW-A` | `tests/test_balance_analysis_api.py`；`tests/test_golden_samples_capture_ready.py` |
| `/operations-analysis` | `PAGE-OPS-001` | `MTR-BAL-004`~`006`, `MTR-BAL-103`；筛选口径 `MTR-BAL-104`~`105`（summary 表） | —（无专包；不与 frozen JSON 逐项锁死） | `tests/test_balance_analysis_api.py`；`tests/test_balance_analysis_service.py` |
| `/operations-analysis` | `PAGE-OPS-001` | —（macro / FX / news / 运营条） | — | `frontend/src/test/OperationsAnalysisPage.test.tsx` |
| `/bond-dashboard` | `PAGE-BOND-001`（见 `page_contracts` §13.6） | —（Headline / 风险卡见字典 **GAP-BOND-DASH-***；字典级 metric 同源仍待单独批准） | `GS-BOND-HEADLINE-A` **capture-ready**（冻结 `GET /api/bond-dashboard/headline-kpis`；非 `MTR-*` 批准） | `frontend/src/test/BondDashboardPage.test.tsx` |
| `/bond-analysis` | `PAGE-BOND-ANALYSIS-001` | `MTR-BOND-ACT-001`~`MTR-BOND-ACT-006`（candidate；`formal_use_allowed=false`；pending owner approval） | `GS-BOND-ANALYSIS-ACTION-ATTR-A` **capture-ready pending approval**（冻结 `GET /api/bond-analytics/action-attribution` 页面 DTO；非公式/owner 审批） | `tests/test_golden_samples_capture_ready.py`；`tests/test_bond_analysis_business_owner_approval_status.py` |
| `/stock-analysis` | `GAP-STOCK-ANALYSIS-PAGE` | —（observational-only；无 `PAGE-STOCK-*` / `MTR-STOCK-*` approval；`formal_use_allowed=false`） | `GS-STOCK-ANALYSIS-OBS-A` **capture-ready pending approval**（冻结 `GET /ui/market-data/livermore` observation DTO；非交易指令/owner 审批） | `tests/test_golden_samples_capture_ready.py`；`tests/test_stock_analysis_business_owner_approval_status.py` |
| `/positions` | `PAGE-POS-001`（见 §13.7） | —（**GAP-POS-LIST**：`MTR-*` / 样本仍未钉死） | — | `tests/test_positions_api_contract.py`；`frontend/src/test/PositionsView.test.tsx` |
| `/market-data` | `PAGE-MKT-001`（见 §13.8） | —（mixed-source；无 full-page `metric_id` 黄金样本） | `GS-MKT-RATES-FRAGMENT-A` **capture-ready pending approval**（formal rates fragment only） | `tests/test_golden_samples_capture_ready.py`；`frontend/src/features/market-data/lib/marketDataRatesFragmentGolden.test.ts`；`frontend/src/test/MarketDataPage.test.tsx` |

## 6. 样本定义

### 6.1 `GS-BAL-OVERVIEW-A`

- surface：`GET /ui/balance-analysis/overview`
- request：

```json
{
  "report_date": "2025-12-31",
  "position_scope": "all",
  "currency_basis": "CNY"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_balance_analysis_api.py`
- 首批建议断言：
  - `result_meta.basis == "formal"`
  - `result_meta.formal_use_allowed == true`
  - `result_meta.result_kind == "balance-analysis.overview"`
  - `result_meta.source_version == "sv-fx-1__sv-t-1__sv-z-1"`
  - `result_meta.rule_version == "rv_balance_analysis_formal_materialize_v1"`
  - `result_meta.cache_version == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"`
  - `result.report_date == "2025-12-31"`
  - `MTR-BAL-001 == "792.00000000"`
  - `MTR-BAL-002 == "720.00000000"`
  - `MTR-BAL-003 == "50.40000000"`
  - `MTR-BAL-101 == 2`
  - `MTR-BAL-102 == 2`
- 对账：
  - 与 `GS-BAL-WORKBOOK-A` 的 workbook 主表汇总对账

### 6.2 `GS-BAL-WORKBOOK-A`

- surface：`GET /ui/balance-analysis/workbook`
- request：

```json
{
  "report_date": "2025-12-31",
  "position_scope": "all",
  "currency_basis": "CNY"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_balance_analysis_api.py`
  - `tests/test_balance_analysis_workbook_contract.py`
  - `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md §13`
- 首批建议断言：
  - `result_meta.result_kind == "balance-analysis.workbook"`
  - `tables[].key` 覆盖 `GOVERNED_WORKBOOK_SUPPORTED_TABLE_KEYS`
  - `advanced_attribution_bundle` 不得出现在 `tables[].key`
  - `operational_sections` 至少包含：
    - `decision_items`
    - `event_calendar`
    - `risk_alerts`
  - `decision_items`、`event_calendar`、`risk_alerts` 的 row schema 与现有 contract test 一致
- 对账：
  - 与 `GS-BAL-OVERVIEW-A` 的总量指标一致
- 备注：
  - 这是结构样本，不做“全 workbook 全值锁死”

### 6.3 `GS-PNL-OVERVIEW-A`

- surface：`GET /api/pnl/overview`
- request：

```json
{
  "report_date": "2025-12-31"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_pnl_api_contract.py::test_pnl_overview_returns_backend_owned_aggregation_and_report_date_build_lineage`
- 首批建议断言：
  - `result_meta.basis == "formal"`
  - `result_meta.result_kind == "pnl.overview"`
  - `result_meta.source_version == "fi-shared-v1__nonstd-shared-v1"`
  - `result_meta.vendor_version == "vv_none"`
  - `result_meta.rule_version == "rv_pnl_phase2_materialize_v1"`
  - `result_meta.cache_version == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"`
  - `MTR-PNL-101 == 1`
  - `MTR-PNL-102 == 1`
  - `MTR-PNL-001 == "12.50"`
  - `MTR-PNL-002 == "96.75"`
  - `MTR-PNL-003 == "1.75"`
  - `MTR-PNL-004 == "0.50"`
  - `MTR-PNL-005 == "111.50"`
- 对账：
  - 与 `GS-PNL-DATA-A` 的 row 聚合对账

### 6.4 `GS-PNL-DATA-A`

- surface：`GET /api/pnl/data`
- request：

```json
{
  "date": "2025-12-31"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_pnl_api_contract.py::test_pnl_data_returns_shared_date_with_two_explicit_lists_and_report_date_build_lineage`
- 首批建议断言：
  - `result_meta.basis == "formal"`
  - `result.report_date == "2025-12-31"`
  - `formal_fi_rows.length == 1`
  - `nonstd_bridge_rows.length == 1`
  - `formal_fi_rows[0].instrument_code == "240001.IB"`
  - `nonstd_bridge_rows[0].bond_code == "BOND-001"`
  - row 级字段中保留：
    - `MTR-PNL-001`
    - `MTR-PNL-002`
    - `MTR-PNL-003`
    - `MTR-PNL-004`
    - `MTR-PNL-005`
    - `MTR-PNL-103`
    - `MTR-PNL-104`
- 对账：
  - 聚合后必须能复核 `GS-PNL-OVERVIEW-A`

### 6.4.1 `GS-PROD-CAT-PNL-A`

- surface：`GET /ui/pnl/product-category`（query：`report_date`、`view` 等，见 `tests/golden_samples/GS-PROD-CAT-PNL-A/request.json`）
- 状态：`capture-ready`（`tests/test_golden_samples_capture_ready.py`）
- page / 真值链：`docs/pnl/product-category-page-truth-contract.md`；页面契约绑定：`docs/page_contracts.md` → `PAGE-PROD-CAT-PNL-001`
- 证据：
  - `tests/test_product_category_pnl_flow.py`
  - `tests/test_product_category_mapping_contract.py`
  - `tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md`
- 对账：
  - 与 `docs/pnl/product-category-golden-sample-a.md` 及 closure checklist 一致；不得用持仓侧分类重解样本行

### 6.5 `GS-BRIDGE-A`

- surface：`GET /api/pnl/bridge`
- request：

```json
{
  "report_date": "2025-12-31"
}
```

- 状态：`capture-ready`
- 样本类型：`warning-profile normal sample`
- 说明：
  - 当前最稳定的 bridge 样本并不是“全绿零 warning”，而是“bridge 可用，但缺 balance rows / curve 输入不完整时仍能返回受控结果”的真实样本。
- 证据：
  - `tests/test_pnl_api_contract.py::test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable`
  - `tests/test_pnl_api_contract.py::test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows`
- 首批建议断言：
  - `result_meta.basis == "formal"`
  - `result_meta.result_kind == "pnl.bridge"`
  - `result_meta.cache_version` 使用 bridge 组合 cache version
  - `result.report_date == "2025-12-31"`
  - `rows.length == 1`
  - `rows[0].instrument_code == "240001.IB"`
  - `MTR-BRG-003 == "12.50000000"`
  - `MTR-BRG-008 == "1.75000000"`
  - `MTR-BRG-009 == "-3.25000000"`
  - `MTR-BRG-010 == "0.50000000"`
  - `MTR-BRG-011 == "11.50000000"`
  - `MTR-BRG-012 == "11.50000000"`
  - `MTR-BRG-013 == "0.00000000"`
  - `summary.row_count == 1`
  - `warnings[0]` 必须保留当前 phase-3 partial delivery 提示
- 对账：
  - 与 `GS-PNL-OVERVIEW-A` 对 `actual_pnl` 方向对账
- 备注：
  - 审批时应明确这不是“全要素完备 bridge”，而是当前 governed bridge 的真实控制样本

### 6.6 `GS-RISK-A`

- surface：`GET /api/risk/tensor`
- request：

```json
{
  "report_date": "2026-03-31"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_risk_tensor_api.py`
  - `tests/test_risk_tensor_service.py::test_risk_tensor_service_returns_formal_envelope_with_lineage`
- 首批建议断言：
  - `result_meta.basis == "formal"`
  - `result_meta.result_kind == "risk.tensor"`
  - `result_meta.source_version == "sv_risk_tensor__sv_bond_snap_1"`
  - `result_meta.rule_version == "rv_risk_tensor_formal_materialize_v2"`
  - `result_meta.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2"`
  - `result_meta.quality_flag == "ok"`
  - `result.report_date == "2026-03-31"`
  - `MTR-RSK-101 == 3`
  - `MTR-RSK-020 == "429.00000000"`
  - `MTR-RSK-013 == "14.00000000"`
  - `MTR-RSK-014 == "14.00000000"`
  - `MTR-RSK-015 == "0.00000000"`
  - `MTR-RSK-016 == "0.00000000"`
  - `MTR-RSK-017 == "14.00000000"`
  - `MTR-RSK-018 == "14.00000000"`
  - `MTR-RSK-012 == "1.00000000"`
  - `MTR-RSK-001` 为 8 位小数字符串
  - `MTR-RSK-008 > 0`
  - `MTR-RSK-009 > 0`
- 对账：
  - 与 bond analytics 风险摘要 / headline 风险指标对账

### 6.7 `GS-EXEC-OVERVIEW-A`

- surface：`GET /ui/home/overview`
- request（建议）：

```json
{
  "report_date": "2026-02-28"
}
```

- 状态：`capture-ready`
- `caliber_label` 冻结字段：
  - `aum` 固定为 `本币资产口径`。
  - `yield` 固定为 `FI + 非标桥接`，标签为 `年度损益（不扣FTP）`，明细说明来自 `fact_formal_pnl_fi + fact_nonstd_pnl_bridge` 且不扣减 FTP。
  - `nim` / `dv01` 当前固定为 `null`。
  - 该形状与 `tests/test_executive_service_contract.py` 和 `backend/app/schemas/executive_dashboard.py` 的当前契约一致。
- 证据：
  - `tests/test_executive_release_contract.py::test_gs_exec_overview_release_contract`
  - `tests/test_executive_dashboard_endpoints.py` 已证明该 route 为 in-scope analytical envelope
  - `tests/test_executive_service_contract.py::test_executive_overview_aum_uses_combined_formal_balance_scope` 提供更宽的服务侧补充证据
  - `backend/app/api/routes/executive.py` 已证明 route 接受显式 `report_date`
- 说明：
  - 当前样本使用 deterministic stub-backed route capture，冻结 `report_date=2026-02-28` 的 analytical overlay 语义。
- 首批建议断言：
  - `result_meta.basis == "analytical"`
  - `result_meta.formal_use_allowed == false`
  - `result_meta.scenario_flag == false`
  - `result_meta.result_kind == "executive.overview"`
  - `result_meta.source_version == "sv_balance_union__sv_exec_dashboard_v1"`
  - `result_meta.rule_version == "rv_balance_union__rv_exec_dashboard_v1"`
  - `result_meta.cache_version == "cv_exec_dashboard_v1"`
  - `metrics` 至少包含：
    - `MTR-EXEC-001`
    - `MTR-EXEC-002`
    - `MTR-EXEC-003`
    - `MTR-EXEC-004`
  - `MTR-EXEC-001 == "3,572.76 亿"`
  - `MTR-EXEC-002 == "+4.69 亿"`
  - `MTR-EXEC-003 == "+1.00%"`
  - `MTR-EXEC-004 == "13,826,218"`

### 6.8 `GS-EXEC-PNL-ATTR-A`

- surface：`GET /ui/pnl/attribution`
- request（建议）：

```json
{
  "report_date": "2026-02-28"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_executive_release_contract.py::test_gs_exec_pnl_attr_release_contract`
  - `tests/test_executive_dashboard_endpoints.py` 已证明 route 为 in-scope analytical envelope
  - `tests/test_executive_service_contract.py::test_executive_pnl_attribution_repo_aggregation_contract` 提供更宽的服务侧补充证据
  - `backend/app/api/routes/executive.py` 已证明 route 接受显式 `report_date`
- 说明：
  - 当前样本使用 deterministic stub-backed route capture，冻结 `report_date=2026-02-28` 的 analytical composition 语义。
- 首批建议断言：
  - `result_meta.basis == "analytical"`
  - `result_meta.result_kind == "executive.pnl-attribution"`
  - `result_meta.source_version == "sv_exec_dashboard_v1__sv_pc_a__sv_pc_b__sv_pc_c"`
  - `result_meta.rule_version == "rv_exec_dashboard_v1__rv_pc_a__rv_pc_b__rv_pc_c"`
  - `result_meta.cache_version == "cv_exec_dashboard_v1"`
  - `segments` 至少包含：
    - `MTR-EXEC-102`
    - `MTR-EXEC-103`
    - `MTR-EXEC-104`
    - `MTR-EXEC-105`
    - `MTR-EXEC-106`
  - `total` 对应 `MTR-EXEC-101`
  - `MTR-EXEC-101 == "+1.75 亿"`

### 6.9 `GS-EXEC-SUMMARY-A`

- surface：`GET /ui/home/summary`
- request：

```json
{
  "report_date": "2026-02-28"
}
```

- 状态：`capture-ready`
- 证据：
  - `tests/test_executive_release_contract.py::test_gs_exec_summary_release_contract`
  - `tests/test_executive_dashboard_endpoints.py`
  - `tests/test_executive_service_contract.py::test_executive_summary_uses_requested_report_date` 提供更宽的服务侧补充证据
  - `backend/app/api/routes/executive.py` 现在接受显式 `report_date`
- 首批建议断言：
  - `result_meta.basis == "analytical"`
  - `result_meta.result_kind == "executive.summary"`
  - `result_meta.source_version == "sv_summary_requested"`
  - `result_meta.rule_version == "rv_summary_requested"`
  - `result.report_date == "2026-02-28"`
  - `result.title == "本周管理摘要"`
  - `result.points.length == 3`
  - `result.points[*].label` 包含：
    - `收益`
    - `风险`
    - `建议`

## 7. Batch B：异常 / warning profile 样本（已并入 12 目录）

`GS-BRIDGE-WARN-B` 与 `GS-RISK-WARN-B` 已作为 **第一方 capture-ready 包** 纳入 §5 总表与 `tests/test_golden_samples_capture_ready.py`，此处保留说明其意图：

| sample_id | surface | status | preferred_report_date | 证据 | 目的 |
| --- | --- | --- | --- | --- | --- |
| `GS-BRIDGE-WARN-B` | `/api/pnl/bridge` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` 中的 balance lineage fallback warnings | 锁住 `fallback_mode/quality/warnings` 语义 |
| `GS-RISK-WARN-B` | `/api/risk/tensor` | `capture-ready` | `2026-03-31` | `tests/test_risk_tensor_api.py`（degraded snapshot） | 锁住 `quality_flag=warning` 和 warning 列表 |

## 8. 样本间对账矩阵

| 主样本 | 对账对象 | 对账目标 |
| --- | --- | --- |
| `GS-BAL-OVERVIEW-A` | `GS-BAL-WORKBOOK-A` | 总量与 governed workbook 主表一致 |
| `GS-PNL-OVERVIEW-A` | `GS-PNL-DATA-A` | overview 聚合值可由 data 复核 |
| `GS-PNL-OVERVIEW-A` | `GS-BRIDGE-A` | `total_pnl` 与 `actual_pnl` 方向一致 |
| `GS-PNL-ATTR-WB-A` | `GS-PNL-OVERVIEW-A` / `GS-BRIDGE-A` | workbench volume-rate 只能解释归因主 API DTO，不替代 formal PnL truth 或 bridge truth |
| `GS-LEDGER-PNL-SUMMARY-A` | `GS-PNL-OVERVIEW-A` / `GS-PROD-CAT-PNL-A` / `GS-BRIDGE-A` | ledger summary DTO 只冻结 `/ledger-pnl` 候选展示口径；不得替代 formal PnL、product-category PnL 或 PnL bridge truth |
| `GS-BOND-ANALYSIS-ACTION-ATTR-A` | `GS-BOND-HEADLINE-A` | bond-analysis action-attribution DTO 只冻结 `/bond-analysis` 候选展示口径；不得替代 `/bond-dashboard` headline truth、固定收益公式批准或 owner approval |
| `GS-CONCENTRATION-MONITOR-A` | `GS-RISK-A` / `GS-BOND-HEADLINE-A` | concentration-monitor credit-spread-migration DTO 只冻结 `/concentration-monitor` 候选集中度展示口径；不得替代 formal risk truth、债券 headline truth、集中度限额突破批准或 owner approval |
| `GS-STOCK-ANALYSIS-OBS-A` | — | stock-analysis Livermore observation DTO 只冻结 `/stock-analysis` 观察口径；不得替代交易指令、执行批准、allocation advice、position-change command、formal stock-analysis truth 或 owner approval |
| `GS-RISK-A` | `GS-EXEC-OVERVIEW-A` | 管理层 DV01 与专业页 DV01 不自相矛盾 |
| `GS-EXEC-PNL-ATTR-A` | `GS-PNL-OVERVIEW-A` / `GS-BRIDGE-A` | analytical overlay 不得脱离 formal 主链解释范围 |

## 8.1 Supporting-only portfolio sample

`GS-PORTFOLIO-HOME-A` is registered for `PAGE-PORTFOLIO-HOME-001` and `/portfolio`.

Status:
- `supporting-only`
- not `capture-ready`
- not live API capture
- not page execution proof
- not page-level formal approval

Purpose:
- record the portfolio module-home evidence boundary at `decision_anchor_date=2026-05-31`
- keep `/portfolio` tied to downstream balance, bond dashboard, positions, PnL attribution, and risk tensor evidence
- document that risk tensor date evidence now includes the portfolio anchor `2026-05-31`, therefore the frontend date gate may observe `risk_closure_ready=true`
- preserve the boundary that the downstream `2026-05-31` risk tensor payload is still warning-quality evidence and does not upgrade the page to full decision-grade risk closure

This sample must not be used to approve standalone `MTR-*` metrics, live page execution, or full risk-tensor decision closure. It only supports same-day risk date evidence wording.

## 9. 当前结论

仓库中已有 **20** 个与 capture-ready 测试矩阵一致的样本目录（含产品分类、PnL attribution workbench、ledger summary、cashflow projection、average-balance daily ADB、bond-analysis action-attribution、concentration-monitor credit-spread-migration、stock-analysis observation 与两类 warning profile），另有 **1** 个 supporting-only 治理边界样本目录；治理重点转为：**契约/字典/冻结 JSON 一致性**。

因此下一步是维护与对账，而不是再扩张“计划-only”文档：

1. 按 `assertions.md` 与 page contract 持续校验 `capture-ready` 样本包
2. 未来若出现新的样本漂移，安排受控重抓或断言调整（需证据与审批）
