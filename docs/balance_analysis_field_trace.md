# Balance Analysis 字段追踪表

本文只追踪 `balance-analysis` 页面的 `overview / summary / workbook` 三条正式链路：

`fact_formal_zqtz_balance_daily / fact_formal_tyw_balance_daily -> backend repository/service/API -> frontend api client -> BalanceAnalysisPage`

不在这里重新定义业务口径；表中“计算”列只记录当前代码实际怎么做。

## 证据范围

| 证据 | 当前结论 |
| --- | --- |
| 后端路由 | `backend/app/api/routes/balance_analysis.py` 暴露 `/ui/balance-analysis/overview`、`/summary`、`/workbook`。 |
| 后端服务 | `backend/app/services/balance_analysis_service.py` 负责 envelope、result_meta、lineage 和 payload schema。 |
| 后端仓库 | `backend/app/repositories/balance_analysis_repo.py` 直接读取 formal fact 表。 |
| Workbook builder | `backend/app/core_finance/balance_analysis_workbook.py` 从 formal fact row 构造 cards、tables、operational sections。 |
| 前端类型 | `frontend/src/api/contracts.ts` 定义 outward payload 字段。 |
| 前端调用 | `frontend/src/api/client.ts` 和 `BalanceAnalysisPage.tsx` 发起 overview、summary、workbook 查询。 |
| 前端展示 | `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 与 `balanceAnalysisPageModel.ts`。 |
| 测试证据 | `tests/test_balance_analysis_api.py`、`tests/test_balance_analysis_workbook_contract.py`、`frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts`、`frontend/src/test/BalanceAnalysisPage.test.tsx`。 |
| MCP 情况 | 当前会话未暴露 `moss-metric-contracts`、`moss-lineage-evidence`、`moss-data-catalog` 工具；`gitnexus` npx 查询因需要执行联网第三方包被安全策略拒绝。本文使用本地代码和测试证据。 |

## 总链路

| 层 | 文件 / 函数 | 作用 |
| --- | --- | --- |
| Fact | `fact_formal_zqtz_balance_daily` | 债券投资 / 发行类余额 formal fact。金额字段主要是 `face_value_amount`、`market_value_amount`、`amortized_cost_amount`、`accrued_interest_amount`。 |
| Fact | `fact_formal_tyw_balance_daily` | 同业资产 / 同业负债 formal fact。金额字段主要是 `principal_amount`、`accrued_interest_amount`。 |
| Repository | `BalanceAnalysisRepository.fetch_formal_overview` | 聚合 overview 总数和金额。 |
| Repository | `BalanceAnalysisRepository.fetch_formal_summary_table` | 聚合 summary 分页表。 |
| Service | `balance_analysis_overview_envelope` / `balance_analysis_summary_envelope` / `balance_analysis_workbook_envelope` | 包装 result payload 和 `result_meta`。 |
| API | `/ui/balance-analysis/overview` / `/summary` / `/workbook` | 页面直接消费的 HTTP 面。 |
| Frontend client | `getBalanceAnalysisOverview` / `getBalanceAnalysisSummary` / `getBalanceAnalysisWorkbook` | 拼 query string: `report_date`、`position_scope`、`currency_basis`。 |
| Page | `BalanceAnalysisPage` | 首屏 formal snapshot、summary 表、workbook 面板和真实数据 stage 区块。 |

## Overview 字段追踪

| 页面显示 | API 字段 | 后端计算 | Fact 来源 | 单位 | 前端处理 |
| --- | --- | --- | --- | --- | --- |
| 报告日 | `result.report_date` | request `report_date` 原样返回；先检查该日期在 formal fact 中存在。 | 两张 fact 表的 `report_date`。 | 日期 | 用于页首、筛选、stage tags。 |
| 头寸范围 | `result.position_scope` | request `position_scope` 原样返回；非 `all` 时加 `position_scope = ?`。 | 两张 fact 表的 `position_scope`。 | 枚举 | `formatBalanceScopeLabel` 显示资产端 / 负债端 / 全头寸。 |
| 币种口径 | `result.currency_basis` | request `currency_basis` 原样返回；overview SQL 直接按该字段过滤。 | 两张 fact 表的 `currency_basis`。 | 枚举 | `formatCurrencyBasisLabel` 显示 CNY / 原币。 |
| 正式明细查询 | `detail_row_count` | `zqtz.count(*) + tyw.count(*)`。 | 两张 fact 表过滤后的行数。 | 笔数 | 首屏 hero 和 overview cards 显示。 |
| 正式汇总查询 | `summary_row_count` | 两端各自按业务键去重后相加。 | ZQTZ: `instrument_code / portfolio_name / cost_center / position_scope / currency_basis / invest_type_std / accounting_basis`；TYW: `position_id / counterparty_name / product_type / position_scope / currency_basis / invest_type_std / accounting_basis`。 | 行数 | 首屏 hero 和 overview cards 显示。 |
| 规模合计 | `total_market_value_amount` | ZQTZ `sum(market_value_amount)` + TYW `sum(principal_amount)`。 | `fact_formal_zqtz_balance_daily.market_value_amount`；`fact_formal_tyw_balance_daily.principal_amount`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |
| 摊余成本合计 | `total_amortized_cost_amount` | ZQTZ `sum(amortized_cost_amount)` + TYW `sum(principal_amount)`。 | `amortized_cost_amount`；`principal_amount`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |
| 应计利息合计 | `total_accrued_interest_amount` | ZQTZ `sum(accrued_interest_amount)` + TYW `sum(accrued_interest_amount)`。 | 两张 fact 表的 `accrued_interest_amount`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |
| Result Meta | `result_meta.*` | `build_formal_result_envelope_from_lineage` 结合 build lineage 和 overview rule_version。 | fact 的 `source_version / rule_version`，以及 governance build lineage。 | 元数据 | 折叠面板 `FormalResultMetaPanel` 展示 basis、quality、fallback、cache 等。 |

## Summary 字段追踪

`/ui/balance-analysis/summary` 返回分页表，不是 detail 明细。它在 repository 里先构造 `summary_rows` CTE，再分页。

| 页面列 | API 字段 | ZQTZ 来源 / 计算 | TYW 来源 / 计算 | 单位 | 前端处理 |
| --- | --- | --- | --- | --- | --- |
| 行键 | `row_key` | 拼接 `zqtz:` + `instrument_code / portfolio_name / cost_center / currency_basis / position_scope / invest_type_std / accounting_basis`。 | 拼接 `tyw:` + `position_id / currency_basis / position_scope / invest_type_std / accounting_basis`。 | 文本 | AgGrid `getRowId` 使用。 |
| 来源 | `source_family` | 固定 `zqtz`。 | 固定 `tyw`。 | 枚举 | 页面转大写显示。 |
| 标识 | `display_name` | `instrument_code`。 | `position_id`。 | 文本 | Summary 表展示。 |
| 组合 / 对手方 | `owner_name` | `portfolio_name`。 | `counterparty_name`。 | 文本 | Summary 表展示。 |
| 分类 | `category_name` | `cost_center`。 | `product_type`。 | 文本 | Summary 表展示。 |
| 头寸范围 | `position_scope` | group by fact 字段。 | group by fact 字段。 | 枚举 | Summary 表展示。 |
| 币种口径 | `currency_basis` | group by fact 字段。 | group by fact 字段。 | 枚举 | Summary 表展示。 |
| 会计口径 | `invest_type_std` / `accounting_basis` | group by fact 字段。 | group by fact 字段。 | 文本 | 前端组合为 `invest_type_std / accounting_basis`。 |
| 明细行数 | `detail_row_count` | `count(*)`。 | `count(*)`。 | 笔数 | `formatBalanceGridThousandsValue`。 |
| 规模 | `market_value_amount` | `sum(market_value_amount)`。 | `sum(principal_amount)`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |
| 摊余成本 | `amortized_cost_amount` | `sum(amortized_cost_amount)`。 | `sum(principal_amount)`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |
| 应计利息 | `accrued_interest_amount` | `sum(accrued_interest_amount)`。 | `sum(accrued_interest_amount)`。 | 元 | `formatBalanceAmountToYiFromYuan` 转亿元。 |

## Workbook Cards 字段追踪

Workbook payload 的 `cards[].value` 当前由 builder 转成“万元”口径，页面再用 `formatBalanceAmountToYiFromWan` 显示成“亿元”。

| 页面卡片 / key | API 字段 | 后端计算 | Fact 来源 | 单位 | 前端处理 |
| --- | --- | --- | --- | --- | --- |
| 债券资产 `bond_assets_excluding_issue` | `workbook.cards[key].value` | ZQTZ `position_scope == asset` 的 `face_value_amount` 求和，再 `/ 10000`。 | `fact_formal_zqtz_balance_daily.face_value_amount`。 | 万元 | Overview card 和 stage allocation 转亿元。 |
| 同业资产 `interbank_assets` | 同上 | TYW `position_scope == asset` 的 `principal_amount` 求和，再 `/ 10000`。 | `fact_formal_tyw_balance_daily.principal_amount`。 | 万元 | Overview card、stage contribution、stage allocation。 |
| 同业负债 `interbank_liabilities` | 同上 | TYW `position_scope == liability` 的 `principal_amount` 求和，再 `/ 10000`。 | `fact_formal_tyw_balance_daily.principal_amount`。 | 万元 | Overview card、stage contribution、stage allocation。 |
| 发行类负债 `issuance_liabilities` | 同上 | ZQTZ `position_scope == liability` 的 `face_value_amount` 求和，再 `/ 10000`。 | `fact_formal_zqtz_balance_daily.face_value_amount`。 | 万元 | Overview card、stage contribution、stage allocation。 |
| 净头寸 `net_position` | 同上 | `债券资产 + 同业资产 - 同业负债`，再 `/ 10000`。当前 card 计算不扣发行类负债；全口径缺口在 `maturity_gap.full_scope_gap_amount`。 | 上面三类字段。 | 万元 | Overview card 转亿元。 |

## Workbook Tables 字段追踪

| 页面面板 | workbook table key | 主要字段 | 后端计算 | Fact 来源 | 页面使用 |
| --- | --- | --- | --- | --- | --- |
| 债券业务种类 | `bond_business_types` | `bond_type`、`count`、`balance_amount`、`share`、`weighted_rate_pct`、`weighted_term_years`、`amortized_cost_amount`、`market_value_amount`、`floating_pnl_amount` | ZQTZ asset rows 按 `bond_type` 分组；金额多为 face / amortized / market 求和；share 除以资产债券总额；weighted 字段按 face value 加权；floating pnl = market - amortized。 | ZQTZ: `bond_type`、`face_value_amount`、`coupon_rate`、`maturity_date`、`amortized_cost_amount`、`market_value_amount`。 | 主 workbook 面板分布条；stage summary 取首位 bond_type 和 share。 |
| 期限缺口 | `maturity_gap` | `bucket`、`bond_assets_amount`、`interbank_assets_amount`、`asset_total_amount`、`issuance_amount`、`interbank_liabilities_amount`、`full_scope_liability_amount`、`gap_amount`、`full_scope_gap_amount`、`cumulative_gap_amount` | 按剩余期限 bucket 分组；asset_total = 债券资产 + 同业资产；full_scope_liability = 发行类 + 同业负债；gap = asset_total - 同业负债；full_scope_gap = asset_total - full_scope_liability；cumulative_gap 累加 gap。 | ZQTZ: `face_value_amount`、`maturity_date`、`coupon_rate`；TYW: `principal_amount`、`maturity_date`、`funding_cost_rate`。 | 主 workbook 期限缺口条；stage contribution/risk/bottom 取 `full_scope_gap_amount` 优先。 |
| 发行类分析 | `issuance_business_types` | `bond_type`、`count`、`balance_amount`、`share`、`weighted_rate_pct`、`weighted_term_years`、`interest_mode_*_count` | ZQTZ liability rows 按 `bond_type` 分组；金额为 face value 求和；利率/期限按 face value 加权；计息方式计数。 | ZQTZ: `position_scope`、`bond_type`、`face_value_amount`、`coupon_rate`、`maturity_date`、`interest_mode`。 | 主 workbook 面板；stage summary 取首位 issuance bucket 和 share。 |
| 评级分析 | `rating_analysis` | `rating`、`count`、`balance_amount`、`share`、`weighted_rate_pct`、`weighted_term_years` | ZQTZ asset rows 按 `rating` 分组。 | ZQTZ: `rating`、`face_value_amount`、`coupon_rate`、`maturity_date`。 | 主 workbook 评级块；decision/risk 可基于集中度生成信号。 |
| 利率分布 | `rate_distribution` | `bucket`、`bond_amount`、`interbank_asset_amount`、`interbank_liability_amount` 及 count | 按利率 bucket 分别统计债券 coupon、同业资产 funding cost、同业负债 funding cost。 | ZQTZ: `coupon_rate`、`face_value_amount`；TYW: `funding_cost_rate`、`principal_amount`。 | 二级 workbook 面板。 |
| 行业分布 | `industry_distribution` | `industry_name`、`count`、`balance_amount`、`share`、`weighted_rate_pct` | ZQTZ asset rows 按 `industry_name` 分组。 | ZQTZ: `industry_name`、`face_value_amount`、`coupon_rate`。 | 二级 workbook 面板。 |
| 对手方类型 | `counterparty_types` | `counterparty_type`、`asset_amount`、`liability_amount`、`net_position_amount`、weighted rate | TYW rows 按 `core_customer_type` 或 `counterparty_name` 分组；资产/负债分别求 principal；net = asset - liability。 | TYW: `core_customer_type`、`counterparty_name`、`position_scope`、`principal_amount`、`funding_cost_rate`。 | 二级 workbook 面板。 |
| 决策事项 | `decision_items` operational section | `title`、`action_label`、`severity`、`reason`、`source_section`、`rule_id`、`rule_version` | 由 maturity gap、rating concentration、issuance bucket 派生；不写回 formal fact。 | 间接来自 workbook tables。 | 右侧治理栏和首屏 Governed Signals；状态来自 decision status 流。 |
| 事件日历 | `event_calendar` operational section | `event_date`、`event_type`、`title`、`source`、`impact_hint`、`source_section` | 取未来到期的 ZQTZ/ TYW rows，最多 5 条，按日期排序。 | ZQTZ/ TYW: `maturity_date`、instrument/position id、position scope、bond/product type。 | 右侧栏、详情下钻、stage calendar。 |
| 风险预警 | `risk_alerts` operational section | `title`、`severity`、`reason`、`source_section`、`rule_id`、`rule_version` | 由负缺口、发行类余额、评级集中度派生。 | 间接来自 maturity/issuance/rating tables。 | 右侧栏、首屏 Governed Signals、stage risk/alerts。 |

## Stage 真实数据区块

Stage 区块不是新的后端口径，只是前端把已有 API payload 重新组织成可读面板。

| Stage 展示 | 输入 | 计算 / fallback | 单位 |
| --- | --- | --- | --- |
| 摘要文案 | `workbook.cards`、`workbook.tables`、`decisionRows`、`riskAlertRows` | 优先用 workbook cards/tables；如果 workbook 缺失但 detail summary 有资产/负债合计，则说明“来自 detail summary”；如果都缺失则显示无真实 stage 切片。 | 文案中的金额为亿元。 |
| 收益成本分配 | `workbook.cards` | 债券资产、同业资产为正；发行类负债、同业负债为负；万元转亿元。 | 亿元 |
| 贡献表 | `workbook.cards`、`maturity_gap` | 资产/负债行来自 cards；缺口行取 maturity gap 中绝对值最大的前 3 个 `full_scope_gap_amount`。 | 亿元 |
| 风险矩阵 | `maturity_gap`、risk alerts、decision rows、event calendar、overview tags | 最大全口径缺口决定期限缺口等级；其余行只汇总已有信号数量和首条信号。 | 文本 |
| 期限结构图 | `maturity_gap` | `asset_total_amount`、`full_scope_liability_amount`、`full_scope_gap_amount` 万元转亿元。 | 亿元 |
| 风险指标 | `workbook.cards`、`maturity_gap`、risk alerts、decision rows | 资产/全口径负债比、1 年内全口径缺口、发行类负债、预警条数、治理事项条数。 | 倍数 / 亿元 / 条数 |
| 日历 | `event_calendar` | 取最多 6 条，按 event_type 转展示等级。 | 文本 |

## 当前已知风险

| 风险 | 说明 |
| --- | --- |
| Workbook 主表读取 native rows | `balance_analysis_workbook_service._build_balance_workbook_payload` 当前为 workbook 主构造读取 `currency_basis="native"` 的 ZQTZ / TYW rows；`currency_basis="CNY"` 主要额外传给 currency split。前端仍按 workbook builder 输出的“万元”显示。 |
| `net_position` card 不是全口径净缺口 | card 计算是 `债券资产 + 同业资产 - 同业负债`，没有扣发行类负债。全口径缺口应看 `maturity_gap.full_scope_gap_amount`。 |
| operational sections 是派生信号 | `decision_items`、`event_calendar`、`risk_alerts` 来自 workbook builder 规则，不是 fact 表原字段。页面已把它们标为 governed signals，但不能当作新的 formal fact。 |
| MCP 证据缺口 | 本轮没有可用 MOSS MCP 工具，无法从外部 metric contract/catalog 再校验字段定义；本文以本地代码和测试为准。 |
