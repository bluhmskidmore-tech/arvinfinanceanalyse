# 指标字典（第一版）

## 1. 目的

本文件是当前 MOSS 已纳入 cutover 范围内的 **第一版真实指标字典**。

目标不是穷举全仓字段，而是先把当前主链和消费面的核心指标钉住，避免继续出现：

- 同一指标在不同页面含义漂移
- 页面文案和后端字段脱节
- 改口径时无法快速判断影响范围

## 2. 当前纳入范围

本版只覆盖以下域：

- `balance-analysis`
- `formal PnL`
- `PnL bridge`
- `risk tensor`
- `executive-consumer v1`
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`

不覆盖：

- Agent
- `cube-query`
- `liability_analytics_compat`
- broad `executive.*` 其余路由
- preview / vendor / analytical-only 扩张面

## 3. 编制依据

本版指标字典基于当前仓库已存在的代码与文档，不额外发明新指标。

主要证据文件：

- `docs/calc_rules.md`
- `docs/data_contracts.md`
- `docs/CACHE_SPEC.md`
- `backend/app/schemas/pnl.py`
- `backend/app/schemas/pnl_bridge.py`
- `backend/app/schemas/balance_analysis.py`
- `backend/app/schemas/risk_tensor.py`
- `backend/app/schemas/executive_dashboard.py`
- `backend/app/services/executive_service.py`
- `frontend/src/features/pnl/PnlPage.tsx`
- `frontend/src/features/pnl/PnlBridgePage.tsx`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
- `tests/test_pnl_api_contract.py`
- `tests/test_balance_analysis_api.py`
- `tests/test_risk_tensor_api.py`
- `tests/test_executive_dashboard_endpoints.py`

## 4. 使用约定

### 4.1 指标 ID 规则

- `MTR-BAL-*`：balance-analysis
- `MTR-PNL-*`：formal PnL
- `MTR-BRG-*`：PnL bridge
- `MTR-RSK-*`：risk tensor
- `MTR-EXEC-*`：executive-consumer v1

### 4.2 指标类型

- `business`：业务/金融主指标
- `control`：行数、coverage、状态分布等控制指标
- `quality`：质量/风险提示类指标

### 4.3 时间语义

当前仓库尚未在这些域统一 `as_of_date` 字段。

因此本版先按如下解释：

- `report_date`：当前业务观察日 / 报告日
- `generated_at`：响应生成时间
- `as_of_date`：暂未统一为独立 outward 字段；页面层在下一轮 page contract 中补齐

### 4.4 fallback 语义

本版只记录当前已存在的 runtime 语义：

- `fallback_mode`
- `vendor_status`
- `quality_flag`

其中：

- formal 指标默认不应静默 fallback
- analytical / executive overlay 可存在受控 fallback，但必须由页面明确可见

## 5. 本版明确不纳入字典的内容

以下内容本轮不作为“指标条目”纳入：

- narrative 文本块
  - 例：`executive.summary` 中的 `narrative`
  - 例：`SummaryPoint` 的 `income/risk/action`
- 纯 UI 结构字段
  - `title`
  - `label`
  - `tone`
- 通用 provenance 元字段
  - `trace_id`
  - `source_version`
  - `rule_version`
  - `cache_version`

这些内容将分别归入页面契约或 result_meta 契约，不与业务指标混用。

## 6. Balance Analysis

### 6.1 业务主指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-BAL-001` | 总市值 | business | `formal` | `backend/app/schemas/balance_analysis.py -> overview.total_market_value_amount`；service: `balance_analysis_overview_envelope` | `/ui/balance-analysis/overview`、`BalanceAnalysisPage.tsx` | 金额；当前页面直接显示字符串值 | 以 `report_date` 为准；lineage 缺失时 fail-closed | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-002` | 总摊余成本 | business | `formal` | `overview.total_amortized_cost_amount` | 同上 | 金额 | 同上 | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-003` | 总应计利息 | business | `formal` | `overview.total_accrued_interest_amount` | 同上 | 金额 | 同上 | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-004` | 市值 | business | `formal` | `BalanceAnalysisDetailRow.market_value_amount` / `BalanceAnalysisTableRow.market_value_amount` / `BalanceAnalysisBasisBreakdownRow.market_value_amount` | 明细表、汇总表、basis breakdown | 金额；AG Grid numeric formatter | 受 `position_scope`、`currency_basis` 影响 | `tests/test_balance_analysis_service.py` |
| `MTR-BAL-005` | 摊余成本 | business | `formal` | `*.amortized_cost_amount` | 同上 | 金额；AG Grid numeric formatter | 同上 | `tests/test_balance_analysis_service.py` |
| `MTR-BAL-006` | 应计利息 | business | `formal` | `*.accrued_interest_amount` | 同上 | 金额；AG Grid numeric formatter | 同上 | `tests/test_balance_analysis_service.py` |

### 6.2 控制指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-BAL-101` | 明细行数 | control | `formal` | `overview.detail_row_count`；`BalanceAnalysisTableRow.detail_row_count` | 头部 KPI、表格 | 整数 | `report_date` 绑定 | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-102` | 汇总行数 | control | `formal` | `overview.summary_row_count` | 头部 KPI | 整数 | `report_date` 绑定 | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-103` | 汇总表行数 | control | `formal` | `BalanceAnalysisSummaryTablePayload.total_rows` | summary table 分页 | 整数 | 与分页参数 `limit/offset` 配套 | `tests/test_balance_analysis_api.py` |
| `MTR-BAL-104` | 头寸范围 | control | `formal` | `position_scope` request/response | 页面筛选、导出 | 枚举：`asset/liability/all` | 非 fallback 指标；直接决定统计口径 | `tests/test_balance_analysis_core.py` |
| `MTR-BAL-105` | 币种口径 | control | `formal` | `currency_basis` request/response | 页面筛选、导出 | 枚举：`native/CNY` | 非 fallback 指标；直接决定统计口径 | `tests/test_balance_analysis_core.py` |

### 6.3 维度/分类指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-BAL-201` | 投资类型标准分类 | business | `formal` | `invest_type_std`；规则见 `docs/calc_rules.md §2` | 明细/汇总/basis breakdown | 文本枚举：`H/A/T` | 不允许前端推导 | `tests/test_balance_analysis_core.py` |
| `MTR-BAL-202` | 会计分类 | business | `formal` | `accounting_basis`；规则见 `docs/calc_rules.md` | 明细/汇总/basis breakdown | 文本枚举：`AC/FVOCI/FVTPL` | 不允许前端推导 | `tests/test_balance_analysis_core.py` |
| `MTR-BAL-203` | source_family | control | `formal` | `zqtz/tyw/combined` | summary / basis breakdown / workbook | 文本枚举 | 仅表示来源族，不是业务口径 | `tests/test_balance_analysis_contracts.py` |

## 7. Formal PnL

### 7.1 业务主指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PNL-001` | 利息收入（514） | business | `formal` | `PnlFormalFiRow.interest_income_514`；`PnlOverviewPayload.interest_income_514`；规则见 `docs/calc_rules.md §3` | `/pnl` overview + 明细 | 金额；signed string | 以 `report_date` 为准 | `tests/test_pnl_formal_semantics_contract.py` |
| `MTR-PNL-002` | 公允价值变动（516） | business | `formal` | `fair_value_change_516`；516 规则见 `docs/calc_rules.md §4` | `/pnl` overview + 明细 | 金额；signed string | formal recognized 语义受会计分类限制 | `tests/test_pnl_formal_semantics_contract.py` |
| `MTR-PNL-003` | 资本利得（517） | business | `formal` | `capital_gain_517` | `/pnl` overview + 明细 | 金额；signed string | 仅在 formal realized/event 语义成立时进入 recognized total | `tests/test_pnl_formal_semantics_contract.py` |
| `MTR-PNL-004` | 手工调整 | business | `formal` | `manual_adjustment` | `/pnl` overview + 明细 | 金额；signed string | 仅批准 adjustment 可进入 formal total | `tests/test_pnl_formal_semantics_contract.py` |
| `MTR-PNL-005` | 正式总损益 | business | `formal` | `total_pnl` | `/pnl` overview + 明细 | 金额；signed string | `formal recognized total_pnl`，不等于 standardized total | `tests/test_pnl_formal_semantics_contract.py` |

### 7.2 控制指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PNL-101` | 正式 FI 行数 | control | `formal` | `PnlOverviewPayload.formal_fi_row_count` | `/pnl` overview | 整数 | 与 `report_date` 强绑定 | `tests/test_pnl_api_contract.py` |
| `MTR-PNL-102` | 非标桥接行数 | control | `formal` | `PnlOverviewPayload.nonstd_bridge_row_count` | `/pnl` overview | 整数 | 与 `report_date` 强绑定 | `tests/test_pnl_api_contract.py` |
| `MTR-PNL-103` | 投资类型标准分类 | business | `formal` | `PnlFormalFiRow.invest_type_std` | 明细表 | 文本枚举 | 不允许前端推导 | `tests/test_pnl_core_finance_contract.py` |
| `MTR-PNL-104` | 会计分类 | business | `formal` | `PnlFormalFiRow.accounting_basis` | 明细表 | 文本枚举 | 不允许前端推导 | `tests/test_pnl_formal_semantics_contract.py` |

## 8. PnL Bridge

### 8.1 业务主指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-BRG-001` | 期初脏价市值 | business | `formal` | `PnlBridgeRowSchema.beginning_dirty_mv` | `/pnl-bridge` 行级表 | 金额 | 当前 `report_date` 对 prior balance 的桥接起点 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-002` | 期末脏价市值 | business | `formal` | `ending_dirty_mv` | 行级表 | 金额 | 当前 `report_date` 终点 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-003` | Carry | business | `formal` | `carry` | 行级表、summary 图卡 | 金额 | governed bridge 分解项 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-004` | Roll-down | business | `formal` | `roll_down` | 行级表、summary 图卡 | 金额 | 曲线不可用时可退化，但必须显式 warning/fallback | `tests/test_pnl_bridge_curve_effects.py` |
| `MTR-BRG-005` | 国债曲线效应 | business | `formal` | `treasury_curve` | 行级表、summary 图卡 | 金额 | 受曲线可用性影响 | `tests/test_pnl_bridge_curve_effects.py` |
| `MTR-BRG-006` | 信用利差效应 | business | `formal` | `credit_spread` | 行级表、summary 图卡 | 金额 | 受 AAA credit / treasury 曲线可用性影响 | `tests/test_pnl_bridge_with_curve.py` |
| `MTR-BRG-007` | FX 折算效应 | business | `formal` | `fx_translation` | 行级表、summary 图卡 | 金额 | 有外币债且有 FX 时不应固定为 0 | `tests/test_pnl_bridge_fx_translation.py` |
| `MTR-BRG-008` | 已实现交易损益 | business | `formal` | `realized_trading` | 行级表、summary 图卡 | 金额 | governed bridge 分解项 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-009` | 未实现公允价值 | business | `formal` | `unrealized_fv` | 行级表、summary 图卡 | 金额 | governed bridge 分解项 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-010` | 手工调整 | business | `formal` | `manual_adjustment` | 行级表、summary 图卡 | 金额 | formal 认可的 adjustment | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-011` | 可解释损益 | business | `formal` | `explained_pnl` | `/pnl-bridge` summary + 表格 | 金额 | bridge 核心输出 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-012` | 实际损益 | business | `formal` | `actual_pnl` | 同上 | 金额 | bridge 对账目标值 | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-013` | 残差 | business | `formal` | `residual` | 同上 | 金额；signed | `actual - explained` | `tests/test_pnl_bridge_core.py` |
| `MTR-BRG-014` | 残差占比 | quality | `formal` | `residual_ratio` | 行级表 | 比率 | 用于解释质量判断 | `tests/test_pnl_bridge_core.py` |

### 8.2 控制 / 质量指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-BRG-101` | bridge 行数 | control | `formal` | `PnlBridgeSummarySchema.row_count` | `/pnl-bridge` 顶部 KPI | 整数 | `report_date` 绑定 | `tests/test_pnl_api_contract.py` |
| `MTR-BRG-102` | quality=ok 行数 | control | `formal` | `ok_count` | 顶部 KPI | 整数 | 质量分布指标 | `tests/test_pnl_api_contract.py` |
| `MTR-BRG-103` | quality=warning 行数 | control | `formal` | `warning_count` | 顶部 KPI | 整数 | 质量分布指标 | `tests/test_pnl_api_contract.py` |
| `MTR-BRG-104` | quality=error 行数 | control | `formal` | `error_count` | 顶部 KPI | 整数 | 质量分布指标 | `tests/test_pnl_api_contract.py` |
| `MTR-BRG-105` | Bridge 质量标记 | quality | `formal` | `summary.quality_flag`、`row.quality_flag` | 顶部 KPI、行级表 | 枚举：`ok/warning/error` | 当前页面已直接展示为质量标签 | `tests/test_pnl_api_contract.py` |

## 9. Risk Tensor

### 9.1 业务主指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-RSK-001` | 组合 DV01 | business | `formal` | `RiskTensorPayload.portfolio_dv01` | `/risk-tensor` | 数值字符串；signed tone | `report_date` 绑定 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-002` | KRD 1Y | business | `formal` | `krd_1y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-003` | KRD 3Y | business | `formal` | `krd_3y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-004` | KRD 5Y | business | `formal` | `krd_5y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-005` | KRD 7Y | business | `formal` | `krd_7y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-006` | KRD 10Y | business | `formal` | `krd_10y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-007` | KRD 30Y | business | `formal` | `krd_30y` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-008` | CS01 | business | `formal` | `cs01` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-009` | 组合凸性 | business | `formal` | `portfolio_convexity` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-010` | 修正久期 | business | `formal` | `portfolio_modified_duration` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-011` | 发行人集中度 HHI | business | `formal` | `issuer_concentration_hhi` | `/risk-tensor` | 数值字符串 | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-012` | 前五发行人占比 | business | `formal` | `issuer_top5_weight` | `/risk-tensor` | 比率型字符串 | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-013` | 30 天资产现金流 | business | `formal` | `asset_cashflow_30d` | `/risk-tensor` | 金额 | 当前页面未重点展示，但属于 outward contract | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-014` | 90 天资产现金流 | business | `formal` | `asset_cashflow_90d` | outward contract | 金额 | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-015` | 30 天负债现金流 | business | `formal` | `liability_cashflow_30d` | outward contract | 金额 | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-016` | 90 天负债现金流 | business | `formal` | `liability_cashflow_90d` | outward contract | 金额 | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-017` | 30 天流动性缺口 | business | `formal` | `liquidity_gap_30d` | `/risk-tensor` | 金额；signed tone | 受资产/负债现金流共同影响 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-018` | 90 天流动性缺口 | business | `formal` | `liquidity_gap_90d` | `/risk-tensor` | 金额；signed tone | 同上 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-019` | 30 天流动性缺口比例 | quality | `formal` | `liquidity_gap_30d_ratio` | `/risk-tensor` 雷达/摘要 | 比率型字符串 | 当前页面作为风险强度参考 | `tests/test_risk_tensor_liquidity.py` |
| `MTR-RSK-020` | 风险组合总市值 | business | `formal` | `total_market_value` | outward contract | 金额 | `report_date` 绑定 | `tests/test_risk_tensor_api.py` |

### 9.2 控制 / 质量指标

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-RSK-101` | 债券数量 | control | `formal` | `bond_count` | `/risk-tensor` | 整数 | `report_date` 绑定 | `tests/test_risk_tensor_api.py` |
| `MTR-RSK-102` | 风险质量标记 | quality | `formal` | `quality_flag` | `/risk-tensor` | 枚举字符串 | 当前页面直接展示 | `tests/test_risk_tensor_api.py` |

## 10. Executive Consumer V1

### 10.1 管理总览指标

说明：

- 本节只收录当前 `executive_overview` 里有明确后端来源和 `id` 的指标。
- `resolve_executive_kpi_metrics(...)` 动态补入的 KPI，不纳入本版第一批字典；待 KPI 域单独建表后再补。

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-EXEC-001` | 资产规模 | business | `analytical` | `backend/app/services/executive_service.py -> ExecutiveMetric(id=\"aum\")`；上游来自 formal balance overview | `/ui/home/overview` | 亿元字符串 | consumer overlay；当前是 analytical，不可冒充 formal result | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-002` | 年内收益 | business | `analytical` | `ExecutiveMetric(id=\"yield\")`；上游来自 `fact_formal_pnl_fi` 聚合 | `/ui/home/overview` | 亿元 signed string | consumer overlay；report_date 未显式传入时可能取 latest | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-003` | 净息差 | business | `analytical` | `ExecutiveMetric(id=\"nim\")`；上游来自 `compute_liability_yield_metrics` | `/ui/home/overview` | 百分比 signed string | 当前依赖 liability analytics 读面；不属于 formal 主链真值页 | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-004` | 组合 DV01（管理视图） | business | `analytical` | `ExecutiveMetric(id=\"dv01\")`；上游来自 bond analytics risk snapshot | `/ui/home/overview` | 整数字符串 | 是 `MTR-RSK-001` 的管理层 overlay，不是新的 formal 指标 | `tests/test_executive_dashboard_endpoints.py` |

### 10.2 收益归因段指标

说明：

- `executive_pnl_attribution` 当前返回的是 management-layer analytical composition。
- 这些段值有页面和服务稳定 `id`，应纳入字典。

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-EXEC-101` | 收益归因总额 | business | `analytical` | `PnlAttributionPayload.total` | `/ui/pnl/attribution` | 亿元 signed string | 当前为 overlay，不宣称 formal truth | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-102` | Carry 归因 | business | `analytical` | `AttributionSegment(id=\"carry\")` | `/ui/pnl/attribution` | 段值 + 条形图 | 同上 | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-103` | Roll-down 归因 | business | `analytical` | `AttributionSegment(id=\"roll\")` | `/ui/pnl/attribution` | 段值 + 条形图 | 同上 | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-104` | 信用利差归因 | business | `analytical` | `AttributionSegment(id=\"credit\")` | `/ui/pnl/attribution` | 段值 + 条形图 | 同上 | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-105` | 交易损益归因 | business | `analytical` | `AttributionSegment(id=\"trading\")` | `/ui/pnl/attribution` | 段值 + 条形图 | 同上 | `tests/test_executive_dashboard_endpoints.py` |
| `MTR-EXEC-106` | 其他归因 | business | `analytical` | `AttributionSegment(id=\"other\")` | `/ui/pnl/attribution` | 段值 + 条形图 | 同上 | `tests/test_executive_dashboard_endpoints.py` |

## 11. PnL Attribution Workbench

说明：

- 本节对应前端页面 `/pnl-attribution` 与后端 `/api/pnl-attribution/*`。
- 这是 **formal read models 驱动的归因工作台**，不是 executive analytical overlay，也不是 formal PnL 真值页的替代物。
- 当前页面已显式展示 `generated_at / quality_flag / fallback_mode`，advanced 视图也已显示各子接口的 provenance 摘要。

### 11.1 Volume / Rate

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PAT-001` | 当期损益 | business | `formal` | `VolumeRateAttributionPayload.total_current_pnl` | `/pnl-attribution` volume-rate | 金额，亿元展示 | 当前期间来自 `current_period`，页面同时显示 `generated_at / quality_flag / fallback_mode` | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-002` | 上期损益 | business | `formal` | `total_previous_pnl` | 同上 | 金额，亿元展示 | `has_previous_data=false` 时不展示对比卡 | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-003` | 当前收益率（百分比） | business | `formal` | `VolumeRateAttributionItem.current_yield_pct` | volume-rate 表格 | 百分比值；字段名已显式带 `_pct` | 不再允许按 ratio 推断 | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-004` | 上期收益率（百分比） | business | `formal` | `VolumeRateAttributionItem.previous_yield_pct` | volume-rate 表格 | 百分比值；字段名已显式带 `_pct` | 同上 | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-005` | 规模效应 | business | `formal` | `total_volume_effect` / `row.volume_effect` | volume-rate 图表与表格 | 金额，亿元展示 | 与 `current_period / previous_period` 配套解释 | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-006` | 利率效应 | business | `formal` | `total_rate_effect` / `row.rate_effect` | volume-rate 图表与表格 | 金额，亿元展示 | 当前仍保持字段名 `rate_effect`，页面按金额解释 | `tests/test_pnl_attribution_workbench_contract.py` |

### 11.2 TPL / Market

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PAT-101` | TPL 公允价值累计变动 | business | `formal` | `TPLMarketCorrelationPayload.total_tpl_fv_change` | `/pnl-attribution` tpl-market | 金额，亿元展示 | 观察区间来自 `start_period ~ end_period` | `frontend/src/test/TPLMarketChart.test.tsx` |
| `MTR-PAT-102` | 10Y 国债累计变动（BP） | business | `formal` | `TPLMarketCorrelationPayload.treasury_10y_total_change_bp` | tpl-market | BP 值；字段名已显式带 `_bp` | 不再允许按百分点差推断 | `tests/test_pnl_attribution_workbench_contract.py` |
| `MTR-PAT-103` | 相关系数 | quality | `formal` | `correlation_coefficient` | tpl-market | 小数三位 | 当前页作为解释性指标使用 | `frontend/src/test/TPLMarketChart.test.tsx` |

### 11.3 Composition

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PAT-201` | 总损益 | business | `formal` | `PnlCompositionPayload.total_pnl` | `/pnl-attribution` composition | 金额，亿元展示 | 当前页需与各分项可见闭环 | `frontend/src/test/PnlCompositionChart.test.tsx` |
| `MTR-PAT-202` | 利息收入 | business | `formal` | `total_interest_income` | composition | 金额 + 占比 | 同上 | `frontend/src/test/PnlCompositionChart.test.tsx` |
| `MTR-PAT-203` | 公允价值变动 | business | `formal` | `total_fair_value_change` | composition | 金额 + 占比 | 同上 | `frontend/src/test/PnlCompositionChart.test.tsx` |
| `MTR-PAT-204` | 投资收益 | business | `formal` | `total_capital_gain` | composition | 金额 + 占比 | 同上 | `frontend/src/test/PnlCompositionChart.test.tsx` |
| `MTR-PAT-205` | 其他收入 / 调整项 | business | `formal` | `total_other_income`、`item.other_income`、`trend_data.other_income` | composition 卡片、趋势、表格 | 金额 + 占比 | 当前页面已补齐可见，不再允许只进总损益不进分项 | `frontend/src/test/PnlCompositionChart.test.tsx` |

### 11.4 Advanced / Campisi

| metric_id | 指标名 | 类型 | basis | 权威来源 | 当前消费面 | 展示规则 | fallback / 时间说明 | 测试锚点 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `MTR-PAT-301` | 静态收益（年化） | business | `formal` | `AdvancedAttributionSummary.static_return_annualized` | `/pnl-attribution` advanced | 百分比；前端不得再次乘 12 | 当前页面直接消费 summary 字段 | `frontend/src/test/AdvancedAttributionChart.test.tsx` |
| `MTR-PAT-302` | 国债曲线效应 | business | `formal` | `AdvancedAttributionSummary.treasury_effect_total` / `SpreadAttributionPayload.total_treasury_effect` | advanced | 金额，亿元展示 | advanced strip 必须显示 provenance | `frontend/src/test/AdvancedAttributionChart.test.tsx` |
| `MTR-PAT-303` | KRD 桶收益率变动 | business | `formal` | `KRDAttributionBucket.yield_change` | advanced KRD 表格 | 当前页面按 BP 文义展示 | 字段名仍未显式带单位，属于后续缺口 | `frontend/src/test/AdvancedAttributionChart.test.tsx` |
| `MTR-PAT-304` | 当前视图元信息 | quality | `formal` | `result_meta.generated_at / quality_flag / fallback_mode` | volume-rate / tpl-market / composition / advanced | 页面顶部 strip 必显 | 当前页已落地 | `frontend/src/test/PnlAttributionPage.test.tsx` |

## 12. 当前缺口清单

本版已经能覆盖当前 in-scope 页面的核心指标，但仍存在以下缺口：

### 12.1 缺少统一 `as_of_date`

当前状态：

- KPI 域已有 `as_of_date`
- balance / pnl / bridge / risk / executive 这 5 个域尚未统一 outward `as_of_date`

处理方式：

- 本版先以 `report_date + generated_at` 替代说明
- 下一轮 page contract 统一 `requested_report_date / resolved_report_date / as_of_date`

### 12.2 缺少页面级绑定

当前状态：

- 本字典已经标出“当前消费面”
- 但除本轮新增的 `/pnl-attribution` 约束外，仍缺少更多页面级绑定

处理方式：

- 下一轮为剩余主链页面继续补 page contract

### 12.3 缺少黄金样本绑定

当前状态：

- 本版的测试锚点主要还是 contract / API test
- 还没有把这些指标挂到正式的 `golden sample` 包

处理方式：

- 下一轮按 `docs/golden_sample_plan.md` 绑定第一批样本包

## 13. 建议下一步

按当前顺序继续，不要跳步：

1. 用本文件里的指标集合，先给 6 到 7 个 in-scope 页面写页面契约
2. 为高风险指标补“页面展示规范”和“fallback 可见性”字段
3. 再选第一批黄金样本，把本文件中的 `metric_id` 挂进去

## 14. 版本说明

- 当前版本：`v1-draft`
- 日期：`2026-04-18`
- 性质：docs-only first pass
- 约束：仅反映当前仓库已落地指标，不代表未来所有页面或所有域已建字典
