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

本批只覆盖当前已完成“页面契约 + 指标字典”的面：

- `/ui/balance-analysis/overview`
- `/ui/balance-analysis/workbook`
- `/api/pnl/overview`
- `/api/pnl/data`
- `/api/pnl/bridge`
- `/api/risk/tensor`
- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

不纳入本批：

- `/` 驾驶舱聚合页
- `/api/bond-analytics/portfolio-headlines`
- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- Agent

原因：

- 驾驶舱聚合页混合了 live / excluded section，不适合作为第一批黄金样本主包
- `bond-analytics` 在 `golden_sample_plan.md` 中已被识别为重要样本来源，但当前 page contract 第一版尚未覆盖 bond analytics 专页，因此本目录将其延后，而不是伪装成当前首批已就绪样本
- excluded surface 当前就是 `503 fail-closed`

## 4. 样本落盘路径

建议路径：

```text
tests/golden_samples/
  GS-BAL-OVERVIEW-A/
  GS-BAL-WORKBOOK-A/
  GS-PNL-OVERVIEW-A/
  GS-PNL-DATA-A/
  GS-BRIDGE-A/
  GS-RISK-A/
  GS-EXEC-OVERVIEW-A/
  GS-EXEC-PNL-ATTR-A/
```

每个目录包含：

- `request.json`
- `response.json`
- `assertions.md`
- `approval.md`

## 5. Batch A 样本总表

| sample_id | surface | status | preferred_report_date | 证据来源 | 样本类型 |
| --- | --- | --- | --- | --- | --- |
| `GS-BAL-OVERVIEW-A` | `/ui/balance-analysis/overview` | `capture-ready` | `2025-12-31` | `tests/test_balance_analysis_api.py` | 正常样本 |
| `GS-BAL-WORKBOOK-A` | `/ui/balance-analysis/workbook` | `capture-ready` | `2025-12-31` | `tests/test_balance_analysis_api.py`、`tests/test_balance_analysis_workbook_contract.py` | 结构样本 |
| `GS-PNL-OVERVIEW-A` | `/api/pnl/overview` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 正常样本 |
| `GS-PNL-DATA-A` | `/api/pnl/data` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 明细样本 |
| `GS-BRIDGE-A` | `/api/pnl/bridge` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` | 正常样本 |
| `GS-RISK-A` | `/api/risk/tensor` | `capture-ready` | `2026-03-31` | `tests/test_risk_tensor_api.py`、`tests/test_risk_tensor_service.py` | 正常样本 |
| `GS-EXEC-OVERVIEW-A` | `/ui/home/overview` | `capture-ready` | `2026-02-28` | `tests/test_executive_service_contract.py` + `tests/test_executive_dashboard_endpoints.py` | overlay 样本 |
| `GS-EXEC-PNL-ATTR-A` | `/ui/pnl/attribution` | `capture-ready` | `2026-02-28` | `tests/test_executive_service_contract.py` + `tests/test_executive_dashboard_endpoints.py` | overlay 样本 |
| `GS-EXEC-SUMMARY-A` | `/ui/home/summary` | `capture-ready` | `2026-02-28` | `tests/test_executive_service_contract.py` + `tests/test_executive_dashboard_endpoints.py` | narrative 样本 |

## 5.1 已在计划中、但本批延后的样本

| sample_id | surface | status | 延后原因 |
| --- | --- | --- | --- |
| `GS-BOND-HEADLINE-A` | `/api/bond-analytics/portfolio-headlines` | `blocked-by-contract-gap` | 当前 `page_contracts.md` 第一版未覆盖 bond analytics 专页；为避免“有样本、无页面 owner contract”，本目录先不把它当作首批主包 |

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
  - `result_meta.rule_version == "rv_risk_tensor_formal_materialize_v1"`
  - `result_meta.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1"`
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
- 证据：
  - `tests/test_executive_service_contract.py::test_executive_overview_aum_uses_combined_formal_balance_scope`
  - `tests/test_executive_dashboard_endpoints.py` 已证明该 route 为 in-scope analytical envelope
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
  - `MTR-EXEC-003 == "+0.01%"`
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
  - `tests/test_executive_service_contract.py::test_executive_pnl_attribution_repo_aggregation_contract`
  - `tests/test_executive_dashboard_endpoints.py` 已证明 route 为 in-scope analytical envelope
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
  - `tests/test_executive_service_contract.py::test_executive_summary_uses_requested_report_date`
  - `tests/test_executive_dashboard_endpoints.py`
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

## 7. Batch B：异常样本候选

以下样本不是本轮主包，但建议紧接着做：

| sample_id | surface | status | preferred_report_date | 证据 | 目的 |
| --- | --- | --- | --- | --- | --- |
| `GS-BRIDGE-WARN-B` | `/api/pnl/bridge` | `capture-ready` | `2025-12-31` | `tests/test_pnl_api_contract.py` 中的 balance lineage fallback warnings | 锁住 `fallback_mode/quality/warnings` 语义 |
| `GS-RISK-WARN-B` | `/api/risk/tensor` | `capture-ready` | `2026-03-31` | `tests/test_risk_tensor_api.py::degraded snapshot` | 锁住 `quality_flag=warning` 和 warning 列表 |

## 8. 样本间对账矩阵

| 主样本 | 对账对象 | 对账目标 |
| --- | --- | --- |
| `GS-BAL-OVERVIEW-A` | `GS-BAL-WORKBOOK-A` | 总量与 governed workbook 主表一致 |
| `GS-PNL-OVERVIEW-A` | `GS-PNL-DATA-A` | overview 聚合值可由 data 复核 |
| `GS-PNL-OVERVIEW-A` | `GS-BRIDGE-A` | `total_pnl` 与 `actual_pnl` 方向一致 |
| `GS-RISK-A` | `GS-EXEC-OVERVIEW-A` | 管理层 DV01 与专业页 DV01 不自相矛盾 |
| `GS-EXEC-PNL-ATTR-A` | `GS-PNL-OVERVIEW-A` / `GS-BRIDGE-A` | analytical overlay 不得脱离 formal 主链解释范围 |

## 9. 当前结论

当前首批黄金样本里，已经可以直接落盘的有 6 个：

- `GS-BAL-OVERVIEW-A`
- `GS-BAL-WORKBOOK-A`
- `GS-PNL-OVERVIEW-A`
- `GS-PNL-DATA-A`
- `GS-BRIDGE-A`
- `GS-RISK-A`

因此下一步不需要再写更多“计划文档”，而是按这个目录开始真正落：

1. `capture-ready` 样本包
