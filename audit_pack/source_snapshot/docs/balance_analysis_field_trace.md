# Balance Analysis Field Trace

本文只追 `balance-analysis` 页面当前正式链路中 `overview`、`summary`、`workbook` 三块字段从事实表到页面的流向。

## 1. 总链路

```text
zqtz_bond_daily_snapshot / tyw_interbank_daily_snapshot / fx_daily_mid
-> backend/app/tasks/balance_analysis_materialize.py
-> backend/app/core_finance/balance_analysis.py
-> fact_formal_zqtz_balance_daily / fact_formal_tyw_balance_daily
-> backend/app/repositories/balance_analysis_repo.py
-> backend/app/services/balance_analysis_service.py
-> backend/app/api/routes/balance_analysis.py
-> frontend/src/api/client.ts
-> frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx
```

关键边界：

- 对外页面不直接读 snapshot。
- 正式页面只通过 `fact_formal_zqtz_balance_daily` 和 `fact_formal_tyw_balance_daily` 读数。
- `currency_basis=CNY` 的金额必须已经在后端按正式 FX 折算；前端只展示，不临时换汇。
- `position_scope` 只能是 `asset / liability / all`，由后端正式规则生成和过滤。
- `advanced-attribution` 属于 analytical/scenario 边界，不是 governed workbook 的正式指标。

## 2. Overview 字段追踪

API：`GET /ui/balance-analysis/overview`

| 页面/API 字段 | fact 来源 | 后端计算位置 | API 载荷 | 前端展示 |
| --- | --- | --- | --- | --- |
| `report_date` | 查询参数 + fact `report_date` | `fetch_formal_overview()` 校验该日期存在 | `BalanceAnalysisOverviewPayload.report_date` | 页面主标题/筛选上下文 |
| `position_scope` | fact `position_scope` | `asset/liability` 时下推到两张 fact 表过滤；`all` 不额外过滤 | `BalanceAnalysisOverviewPayload.position_scope` | 页面范围标签 |
| `currency_basis` | fact `currency_basis` | 下推到两张 fact 表过滤 | `BalanceAnalysisOverviewPayload.currency_basis` | 页面币种口径标签 |
| `detail_row_count` | 两张 fact 表行数 | `count(*)` 后相加：ZQTZ + TYW | `detail_row_count` | cockpit 摘要/行数说明 |
| `summary_row_count` | 两张 fact 表聚合组数 | ZQTZ 按 `instrument_code/portfolio_name/cost_center/position_scope/currency_basis/invest_type_std/accounting_basis` 去重；TYW 按 `position_id/counterparty_name/product_type/position_scope/currency_basis/invest_type_std/accounting_basis` 去重；两边相加 | `summary_row_count` | cockpit 摘要/行数说明 |
| `total_market_value_amount` | ZQTZ `market_value_amount`；TYW `principal_amount` | `sum(zqtz.market_value_amount) + sum(tyw.principal_amount)` | `total_market_value_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `total_amortized_cost_amount` | ZQTZ `amortized_cost_amount`；TYW `principal_amount` | `sum(zqtz.amortized_cost_amount) + sum(tyw.principal_amount)` | `total_amortized_cost_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `total_accrued_interest_amount` | 两张 fact 的 `accrued_interest_amount` | `sum(zqtz.accrued_interest_amount) + sum(tyw.accrued_interest_amount)` | `total_accrued_interest_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `asset_total_market_value_amount` | `position_scope='asset'` 的 ZQTZ `market_value_amount` + TYW `principal_amount` | `position_scope=all` 时用 `case when position_scope = 'asset'` 拆分；单边 scope 时由 service/repo 补另一边为 0 | `asset_total_market_value_amount`，单位：元 | `position_scope=all` 时显示“资产端 · 市值”，转亿元 |
| `liability_total_market_value_amount` | `position_scope='liability'` 的 ZQTZ `market_value_amount` + TYW `principal_amount` | `position_scope=all` 时用 `case when position_scope = 'liability'` 拆分；单边 scope 时由 service/repo 补另一边为 0 | `liability_total_market_value_amount`，单位：元 | `position_scope=all` 时显示“负债端 · 市值”，转亿元 |
| `asset_total_amortized_cost_amount` | `position_scope='asset'` 的 ZQTZ `amortized_cost_amount` + TYW `principal_amount` | 同上 | `asset_total_amortized_cost_amount`，单位：元 | `position_scope=all` 时显示“资产端 · 摊余成本”，转亿元 |
| `liability_total_amortized_cost_amount` | `position_scope='liability'` 的 ZQTZ `amortized_cost_amount` + TYW `principal_amount` | 同上 | `liability_total_amortized_cost_amount`，单位：元 | `position_scope=all` 时显示“负债端 · 摊余成本”，转亿元 |
| `asset_total_accrued_interest_amount` | `position_scope='asset'` 的两张 fact `accrued_interest_amount` | 同上 | `asset_total_accrued_interest_amount`，单位：元 | `position_scope=all` 时显示“资产端 · 应计利息”，转亿元 |
| `liability_total_accrued_interest_amount` | `position_scope='liability'` 的两张 fact `accrued_interest_amount` | 同上 | `liability_total_accrued_interest_amount`，单位：元 | `position_scope=all` 时显示“负债端 · 应计利息”，转亿元 |
| `result_meta` | governance lineage + fact `source_version/rule_version` | `build_formal_result_envelope_from_lineage()` | `basis/formal_use_allowed/quality_flag/fallback_mode/source_version/rule_version/cache_version` | 页面 hero chip 和 Result Meta 面板 |

代码锚点：

- fact 汇总 SQL：`backend/app/repositories/balance_analysis_repo.py::fetch_formal_overview`
- service envelope：`backend/app/services/balance_analysis_service.py::balance_analysis_overview_envelope`
- API route：`backend/app/api/routes/balance_analysis.py::overview`
- 前端请求：`frontend/src/api/client.ts::getBalanceAnalysisOverview`
- 前端展示：`frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- 金额格式：`frontend/src/utils/format.ts::formatYuanAmountAsYiPlain`

## 3. Summary 字段追踪

API：`GET /ui/balance-analysis/summary`

| 页面/API 字段 | fact 来源 | 后端计算位置 | API 载荷 | 前端展示 |
| --- | --- | --- | --- | --- |
| `limit` / `offset` / `total_rows` | summary CTE 聚合结果 | `fetch_formal_summary_table()` 先 count，再分页 | `BalanceAnalysisSummaryTablePayload` | summary 表分页 |
| `row_key` | 聚合 key 拼接 | ZQTZ：`zqtz:{instrument_code}:{portfolio_name}:{cost_center}:{currency_basis}:{position_scope}:{invest_type_std}:{accounting_basis}`；TYW：`tyw:{position_id}:{currency_basis}:{position_scope}:{invest_type_std}:{accounting_basis}` | `rows[].row_key` | AG Grid row id |
| `source_family` | 固定来源标签 | ZQTZ 写 `zqtz`；TYW 写 `tyw` | `rows[].source_family` | 表格来源列/分组识别 |
| `display_name` | ZQTZ `instrument_code`；TYW `position_id` | summary CTE 直接映射 | `rows[].display_name` | 表格名称列 |
| `owner_name` | ZQTZ `portfolio_name`；TYW `counterparty_name` | summary CTE 直接映射 | `rows[].owner_name` | 表格归属/交易对手列 |
| `category_name` | ZQTZ `cost_center`；TYW `product_type` | summary CTE 直接映射 | `rows[].category_name` | 表格类别列 |
| `position_scope` | fact `position_scope` | 与 overview 同一过滤逻辑 | `rows[].position_scope` | 表格“头寸范围”列 |
| `currency_basis` | fact `currency_basis` | 与 overview 同一过滤逻辑 | `rows[].currency_basis` | 表格“币种口径”列 |
| `invest_type_std` | fact `invest_type_std` | materialize 阶段由 `core_finance` 正式映射为 H/A/T | `rows[].invest_type_std` | 表格投资分类列 |
| `accounting_basis` | fact `accounting_basis` | materialize 阶段由 H/A/T 映射为 AC/FVOCI/FVTPL | `rows[].accounting_basis` | 表格会计口径列 |
| `detail_row_count` | 聚合组内 fact 行数 | `count(*)` | `rows[].detail_row_count` | 表格明细行数列 |
| `market_value_amount` | ZQTZ `market_value_amount`；TYW `principal_amount` | summary CTE 聚合 | `rows[].market_value_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `amortized_cost_amount` | ZQTZ `amortized_cost_amount`；TYW `principal_amount` | summary CTE 聚合 | `rows[].amortized_cost_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `accrued_interest_amount` | 两张 fact 的 `accrued_interest_amount` | summary CTE 聚合 | `rows[].accrued_interest_amount`，单位：元 | `formatYuanAmountAsYiPlain()` 转亿元 |
| `result_meta` | governance lineage | service envelope | 与 overview 同类字段 | Result Meta 面板 |

代码锚点：

- summary CTE：`backend/app/repositories/balance_analysis_repo.py::_formal_summary_table_cte`
- 分页查询：`backend/app/repositories/balance_analysis_repo.py::fetch_formal_summary_table`
- service envelope：`backend/app/services/balance_analysis_service.py::balance_analysis_summary_envelope`
- API route：`backend/app/api/routes/balance_analysis.py::summary`
- 前端请求：`frontend/src/api/client.ts::getBalanceAnalysisSummary`
- 前端表格：`frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`

## 4. Workbook 字段追踪

API：`GET /ui/balance-analysis/workbook`

`workbook` 不是一张单表，它是后端把正式 fact 行组装成多块分析表和右侧行动区。

| 页面/API 字段 | fact 来源 | 后端计算位置 | API 载荷 | 前端展示 |
| --- | --- | --- | --- | --- |
| `report_date` / `position_scope` / `currency_basis` | 查询参数 + fact 可用日期 | service 先校验 report date，再按 scope 拉取 rows | `BalanceAnalysisWorkbookPayload` 顶层字段 | 页面 workbook 上下文 |
| `cards[].value` | ZQTZ 卡片使用 `face_value_amount`；TYW 卡片使用 `principal_amount`；发行类负债使用 ZQTZ `position_scope='liability'` 行的 `face_value_amount` | `_build_cards()` 汇总债券资产、同业资产、同业负债、发行类负债、净头寸 | `cards`，金额多数单位：万元 | `formatWanAmountAsYiPlain()` 转亿元 |
| `tables[].columns` | workbook builder 定义 | 各 section builder 生成列定义 | `tables[].columns` | 动态生成 AG Grid columns |
| `tables[].rows` | `zqtz_native_rows`、`tyw_native_rows`、`zqtz_currency_rows` | `build_balance_analysis_workbook_payload()` 调用 section builders；金额字段通常先 `_to_wanyuan()` | `tables[].rows` | 动态表格；金额列转亿元 |
| `operational_sections[].rows` | workbook 生成的 decision/risk/event 行 | `balance_analysis_workbook_envelope()` 原样返回 workbook 中的 operational sections，不叠加最新状态 | `workbook.operational_sections` | workbook 右侧行动项、事件日历、风险提醒的基础行 |
| `decision-items` 最新状态 | workbook 生成的 `decision_items` + decision status repo | `balance_analysis_decision_items_envelope()` 单独叠加 `latest_status` | `GET /ui/balance-analysis/decision-items` | 页面通过独立 query 展示/更新决策项状态 |
| `result_meta` | formal build lineage | `balance_analysis_workbook_envelope()` | 与 overview 同类字段 | Result Meta 面板 |

当前 governed workbook 已支持的 section key 以 `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md` 为准，核心包括：

- `bond_business_types`
- `maturity_gap`
- `issuance_business_types`
- `cashflow_calendar`
- `currency_split`
- `rating_analysis`
- `rate_distribution`
- `industry_distribution`
- `counterparty_types`
- `campisi_breakdown`
- `cross_analysis`
- `interest_modes`
- `issuer_concentration`
- `liquidity_layers`
- `regulatory_limits`
- `overdue_credit_quality`
- `vintage_analysis`
- `customer_attribute_analysis`
- `portfolio_comparison`
- `account_category_comparison`
- `ifrs9_classification`
- `ifrs9_position_scope`
- `ifrs9_source_family`
- `rule_reference`

代码锚点：

- service workbook rows：`backend/app/services/balance_analysis_workbook_service.py::_build_balance_workbook_payload`
- workbook builder：`backend/app/core_finance/balance_analysis_workbook.py::build_balance_analysis_workbook_payload`
- workbook cards：`backend/app/core_finance/balance_analysis_workbook.py::_build_cards`
- service envelope：`backend/app/services/balance_analysis_service.py::balance_analysis_workbook_envelope`
- API route：`backend/app/api/routes/balance_analysis.py::workbook`
- 前端请求：`frontend/src/api/client.ts::getBalanceAnalysisWorkbook`
- 前端动态列：`frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx::buildWorkbookGridColumnDefs`
- 前端 workbook cards：`frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- workbook 金额格式：`frontend/src/utils/format.ts::formatWanAmountAsYiPlain`

## 5. 验收口径

修这条链路时，最小验证应覆盖：

- `tests/test_balance_analysis_core.py`
  - H/A/T 与 accounting basis 映射
  - 发行类债券在资产范围排除
  - CNY 折算必须有 FX
- `tests/test_balance_analysis_repo_uses_formal_facts_only.py`
  - 对外 repo 查询不得直接读 snapshot
- `tests/test_balance_analysis_api.py`
  - overview / summary / summary-by-basis / workbook API 的正式 envelope 与字段聚合
- `frontend/src/test/BalanceAnalysisPage.test.tsx`
  - 页面卡片、summary 表、workbook 区、result meta、导出与刷新状态
