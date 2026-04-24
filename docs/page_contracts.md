# 页面契约（第一版）

## 0. Current-state pointer

- `Role`: governed page contracts
- `Not for`: repo-level current-state or boundary entrypoint selection
- `Current-state pointer`: `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`, then this file

## 1. 目的

本文件把当前已纳入 cutover 的消费面收敛成一组 **页面级契约**。

目标不是重复 API 文档，而是钉住：

- 页面为什么存在
- 页面必须回答什么业务问题
- 页面允许展示哪些 section
- 页面依赖哪些 endpoint / DTO
- 页面如何处理 loading / empty / stale / fallback / fail-closed
- 页面与指标字典、黄金样本和自动化测试的关系

## 2. 本版范围

本版只覆盖以下 9 个消费面：

1. 前端驾驶舱 `/`
2. 资产负债分析 `/balance-analysis`
3. 正式损益 `/pnl`
4. PnL Bridge `/pnl-bridge`
5. 风险张量 `/risk-tensor`
6. executive overview `/ui/home/overview`
7. executive summary `/ui/home/summary`
8. executive pnl attribution `/ui/pnl/attribution`
9. 产品分类损益（正式主链）`/product-category-pnl`

不覆盖：

- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- Agent
- `cube-query`
- `liability_analytics_compat`

## 3. 编制依据

- `AGENTS.md`
- `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`
- `docs/EXECUTIVE_CONSUMER_CUTOVER_V1.md`
- `docs/metric_dictionary.md`
- `docs/CACHE_SPEC.md`
- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/pnl/PnlPage.tsx`
- `frontend/src/features/pnl/PnlBridgePage.tsx`
- `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
- `tests/test_executive_dashboard_endpoints.py`
- `tests/test_balance_analysis_api.py`
- `tests/test_pnl_api_contract.py`
- `tests/test_risk_tensor_api.py`

## 4. 通用规则

### 4.1 所有 in-scope 页面都必须满足

- 通过受控 endpoint 获取数据，不在前端补正式金融计算。
- 任何正式或 analytical 结果都必须保留 `{ result_meta, result }` 的 envelope 语义。
- 页面展示的正式指标必须能映射到 `docs/metric_dictionary.md` 中的 `metric_id`。
- 页面如果使用 analytical overlay，必须显式保留 `basis=analytical` 的解释，不得伪装为 formal truth。

### 4.2 当前统一时间语义

当前这些域尚未统一 outward `as_of_date`。

因此本版先按以下方式约定：

- `requested_report_date`：页面传给后端的报告日
- `resolved_report_date`：后端真正返回数据所使用的报告日
- `generated_at`：由 `result_meta.generated_at` 提供
- `as_of_date`：下一轮再统一为独立页面合同字段

### 4.3 当前统一状态语义

- `404`
  - 代表请求的 `report_date` 不存在或该报告日无数据
- `503`
  - 代表 excluded surface、reserved surface、或 formal lineage / governed prerequisite 不可用
- `fallback_mode != none`
  - 页面必须有业务可见提示，不能只藏在 debug 面板
- `quality_flag != ok`
  - 页面必须有状态提示或 badge，不能当正常值静默展示

## 5. PAGE-DASH-001 驾驶舱

### A. 页面身份

- 页面 ID：`PAGE-DASH-001`
- 页面名称：`驾驶舱`
- 路由：
  - 前端：`/`
  - 后端依赖：
    - `/ui/home/overview`
    - `/ui/home/summary`
    - `/ui/pnl/attribution`
    - `/ui/risk/overview`
    - `/ui/home/contribution`
    - `/ui/home/alerts`
- 页面状态：
  - `active`
- 当前边界来源：
  - `CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`
  - `EXECUTIVE_CONSUMER_CUTOVER_V1.md`

### B. 页面目标

- 主要使用者：
  - 管理层
  - 业务负责人
  - 需要从总览进入专业页的研究/运营用户
- 页面要回答的业务问题：
  1. 当前管理层应先看哪些已晋升的关键经营指标。
  2. 当前有哪些可读的管理摘要与收益归因结果。
  3. 哪些风险/预警/贡献面当前仍未晋升，不能误读为 live governed page。
- 页面不负责回答的问题：
  - 不负责提供正式分析结论
  - 不负责替代 `/balance-analysis`、`/pnl`、`/risk-tensor` 的专业页
  - 不负责把 excluded executive surface 伪装成正常内容

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `overview` | 经营总览 | 先给出管理层的关键经营 KPI | `/ui/home/overview` |
| `summary` | 全局判断 | 给出本周管理摘要 | `/ui/home/summary` |
| `pnl_attribution` | 收益归因 | 给出管理层可读的归因段值 | `/ui/pnl/attribution` |
| `module_snapshot` | 模块快照 | 引导进入专业工作台 | 前端静态/组合 |

#### 可选 section

| section_key | 名称 | 启用条件 | 备注 |
| --- | --- | --- | --- |
| `risk_overview` | 风险概览 | 仅当 `/ui/risk/overview` 不返回 `503` 时 | 当前默认 excluded |
| `alerts` | 预警中心 | 仅当 `/ui/home/alerts` 不返回 `503` 时 | 当前默认 excluded |
| `contribution` | 团队/账户/策略贡献 | 仅当 `/ui/home/contribution` 不返回 `503` 时 | 当前默认 excluded |

#### 禁止 section

- 把 `/ui/risk/overview`、`/ui/home/alerts`、`/ui/home/contribution` 的失败状态渲染成伪正常数据
- 在驾驶舱中补算专业页正式指标

### D. 筛选与时间语义

- 页面主筛选：
  - 当前前端固定展示 placeholder filter，不形成统一 report_date 参数入口
- `requested_report_date`：
  - 当前 dashboard 页没有统一主动传参；由各 executive endpoint 默认行为决定
- `resolved_report_date`：
  - 依赖各 executive endpoint 的返回
- `as_of_date`：
  - 当前未统一
- `generated_at`：
  - 来自各 endpoint 的 `result_meta.generated_at`
- latest fallback 是否允许：
  - 允许，但必须被业务可见
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 总览 | `/ui/home/overview` | `OverviewPayload` | `analytical` | 当前已纳入 cutover |
| 摘要 | `/ui/home/summary` | `SummaryPayload` | `analytical` | 当前已纳入 cutover |
| 收益归因 | `/ui/pnl/attribution` | `PnlAttributionPayload` | `analytical` | 当前已纳入 cutover |
| 风险概览 | `/ui/risk/overview` | `RiskOverviewPayload` | `analytical` | 当前 excluded，默认 `503` |
| 贡献 | `/ui/home/contribution` | `ContributionPayload` | `analytical` | 当前 excluded，默认 `503` |
| 预警 | `/ui/home/alerts` | `AlertsPayload` | `analytical` | 当前 excluded，默认 `503` |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 资产规模 | `MTR-EXEC-001` | `overview.metrics[id=aum]` |
| 年内收益 | `MTR-EXEC-002` | `overview.metrics[id=yield]` |
| 净息差 | `MTR-EXEC-003` | `overview.metrics[id=nim]` |
| 组合 DV01（管理视图） | `MTR-EXEC-004` | `overview.metrics[id=dv01]` |
| 收益归因总额 | `MTR-EXEC-101` | `pnl_attribution.total` |
| Carry 归因 | `MTR-EXEC-102` | `pnl_attribution.segments[id=carry]` |
| Roll-down 归因 | `MTR-EXEC-103` | `pnl_attribution.segments[id=roll]` |
| 信用利差归因 | `MTR-EXEC-104` | `pnl_attribution.segments[id=credit]` |
| 交易损益归因 | `MTR-EXEC-105` | `pnl_attribution.segments[id=trading]` |
| 其他归因 | `MTR-EXEC-106` | `pnl_attribution.segments[id=other]` |

### G. 状态合同

- Loading：
  - dashboard 可逐块 loading，不要求全页阻塞
- Empty：
  - 已纳入 cutover 的 executive surface 不应以“空且正常”掩盖缺失；应回到 backend contract
- Stale / fallback：
  - 若已晋升 surface 出现 `fallback_mode != none` 或 `vendor_status != ok`，dashboard 必须可见
- Error / fail-closed：
  - excluded surface 返回 `503` 时，该 section 直接不显示，不得渲染为 live 正常卡片

### H. 对账与黄金样本

- 黄金样本：
  - `GS-EXEC-OVERVIEW-A`
  - `GS-EXEC-SUMMARY-A`
  - `GS-EXEC-PNL-ATTR-A`
- 对账对象：
  - overview ↔ upstream formal balance / formal pnl / bond analytics 风险快照
  - pnl attribution ↔ product category analytical composition

### I. 自动化测试

- 页面：
  - `frontend/src/test/DashboardPage.test.tsx`
- 后端：
  - `tests/test_executive_dashboard_endpoints.py`

## 6. PAGE-BALANCE-001 资产负债分析

### A. 页面身份

- 页面 ID：`PAGE-BALANCE-001`
- 页面名称：`资产负债分析`
- 路由：
  - 前端：`/balance-analysis`
  - 后端：
    - `/ui/balance-analysis/dates`
    - `/ui/balance-analysis/overview`
    - `/ui/balance-analysis`
    - `/ui/balance-analysis/workbook`
    - `/ui/balance-analysis/summary`
    - `/ui/balance-analysis/summary-by-basis`
    - `/ui/balance-analysis/decision-items`
    - `/ui/balance-analysis/current-user`
    - `/ui/balance-analysis/advanced-attribution`
    - `/ui/balance-analysis/refresh`
    - `/ui/balance-analysis/refresh-status`
- 页面状态：
  - `active`

### B. 页面目标

- 主要使用者：
  - 研究员
  - 管理层
  - 治理/运营用户
- 页面要回答的业务问题：
  1. 当前报告日的正式资产、负债和净头寸规模是多少。
  2. 这些规模按来源族、会计分类、投资类型、工作簿 section 如何拆分。
  3. 当前有哪些治理动作、事件日历和风险预警需要跟踪。
- 页面不负责回答的问题：
  - 不负责把 `advanced-attribution` 当成正式 workbook 已落地区块
  - 不负责把 ADB analytical preview 冒充 formal balance truth

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `filter_bar` | 报告日/头寸范围/币种筛选 | 确定当前口径 | page state + `/dates` |
| `overview` | 正式概览 | 展示总市值、总摊余成本、总应计利息、行数 | `/overview` |
| `detail` | 正式明细 | 展示 detail rows | `/ui/balance-analysis` |
| `workbook` | governed workbook | 展示已支持的 workbook tables / operational sections | `/workbook` |
| `decision_items` | 决策与治理 | 展示 decision items / status | `/decision-items` |
| `summary` | 汇总表与 basis breakdown | 汇总拆分 | `/summary`、`/summary-by-basis` |
| `result_meta` | provenance / evidence | 展示各 endpoint 的口径与 lineage | page meta panel |

#### 可选 section

| section_key | 名称 | 启用条件 | 备注 |
| --- | --- | --- | --- |
| `adb_preview` | ADB analytical preview | 当前报告日存在 ADB preview 数据时 | analytical preview，不是 formal truth |
| `advanced_attribution` | advanced attribution bundle | 请求时单独查询 | contract 存在，但不得并入正式 workbook 断言 |

#### 禁止 section

- 把 `advanced_attribution_bundle` 写成当前 governed workbook 已支持 section
- 在前端补算正式 balance 指标
- 把 snapshot / preview 直读结果写成 formal truth

### D. 筛选与时间语义

- 页面主筛选：
  - `report_date`
  - `position_scope`
  - `currency_basis`
- `requested_report_date`：
  - 当前页面选中的 `selectedReportDate`
- `resolved_report_date`：
  - 当前以后端成功返回的 `report_date` 为准
- `as_of_date`：
  - 当前未单列；临时视为 `report_date`
- `generated_at`：
  - 来自各 endpoint `result_meta.generated_at`
- latest fallback 是否允许：
  - 页面初始选取 `dates[0]` 作为默认报告日，但 formal 数据本身不应静默 fallback 到其他日期
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 日期列表 | `/ui/balance-analysis/dates` | `BalanceAnalysisDatesPayload` | `formal` | 页面初始化 |
| 正式概览 | `/ui/balance-analysis/overview` | overview payload | `formal` | 头部 KPI |
| 正式明细 | `/ui/balance-analysis` | `BalanceAnalysisPayload` | `formal` | detail rows |
| workbook | `/ui/balance-analysis/workbook` | `BalanceAnalysisWorkbookPayload` | `formal` | governed workbook |
| 决策项 | `/ui/balance-analysis/decision-items` | `BalanceAnalysisDecisionItemsPayload` | `formal` | 运营治理 |
| 汇总表 | `/ui/balance-analysis/summary` | `BalanceAnalysisSummaryTablePayload` | `formal` | 分页表 |
| basis breakdown | `/ui/balance-analysis/summary-by-basis` | `BalanceAnalysisBasisBreakdownPayload` | `formal` | basis 拆分 |
| refresh | `/ui/balance-analysis/refresh*` | action payload | action | 非 envelope 主读面 |
| advanced attribution | `/ui/balance-analysis/advanced-attribution` | bundle payload | `analytical/scenario` | 仅边界内附加合同 |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 总市值 | `MTR-BAL-001` | `overview.total_market_value_amount` |
| 总摊余成本 | `MTR-BAL-002` | `overview.total_amortized_cost_amount` |
| 总应计利息 | `MTR-BAL-003` | `overview.total_accrued_interest_amount` |
| 市值 | `MTR-BAL-004` | detail/summary/basis rows |
| 摊余成本 | `MTR-BAL-005` | detail/summary/basis rows |
| 应计利息 | `MTR-BAL-006` | detail/summary/basis rows |
| 明细行数 | `MTR-BAL-101` | `detail_row_count` |
| 汇总行数 | `MTR-BAL-102` | `summary_row_count` |
| 汇总表行数 | `MTR-BAL-103` | `summary.total_rows` |
| 头寸范围 | `MTR-BAL-104` | request/response `position_scope` |
| 币种口径 | `MTR-BAL-105` | request/response `currency_basis` |
| 投资类型标准分类 | `MTR-BAL-201` | `invest_type_std` |
| 会计分类 | `MTR-BAL-202` | `accounting_basis` |
| 来源族 | `MTR-BAL-203` | `source_family` |

### G. 状态合同

- Loading：
  - dates 成功前，详情与 workbook 不应提前查询
- Empty：
  - 若 `dates` 空，则页面进入无数据态
- Stale / fallback：
  - formal 页面若 `fallback_mode != none`，必须显示提示
- Error / fail-closed：
  - `404`：当前 `report_date` 无 balance-analysis 数据
  - `503`：lineage 不可解析、refresh runtime 问题、或 governed prerequisite 不满足

### H. 导出、下钻与证据

- 导出：
  - summary CSV
  - workbook xlsx
- 下钻：
  - workbook / summary / decision items
- 证据面板：
  - 必须展示 overview/detail/workbook/summary/decision items 的 `result_meta`

### I. 对账与黄金样本

- 黄金样本：
  - `GS-BAL-OVERVIEW-A`
  - `GS-BAL-WORKBOOK-A`
- 对账对象：
  - overview ↔ workbook
  - summary ↔ detail rows aggregation

### J. 自动化测试

- 前端：
  - `frontend/src/test/BalanceAnalysisPage.test.tsx`
- 后端：
  - `tests/test_balance_analysis_api.py`
  - `tests/test_balance_analysis_workbook_contract.py`
  - `tests/test_balance_analysis_service.py`

## 7. PAGE-PNL-001 正式损益

### A. 页面身份

- 页面 ID：`PAGE-PNL-001`
- 页面名称：`正式损益`
- 路由：
  - 前端：`/pnl`
  - 后端：
    - `/api/pnl/dates`
    - `/api/pnl/overview`
    - `/api/pnl/data`
    - `/api/pnl/refresh*`
- 页面状态：
  - `active`

### B. 页面目标

- 主要使用者：
  - 研究员
  - 财务/治理用户
- 页面要回答的业务问题：
  1. 当前报告日 formal PnL 的核心组成是多少。
  2. 当前 formal FI 与 nonstd bridge 各有多少行。
  3. 明细层面 514/516/517/manual adjustment/total_pnl 如何展开。
- 页面不负责回答的问题：
  - 不负责做 PnL bridge 对账解释
  - 不负责提供 executive analytical overlay narrative

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `dates` | 报告日选择 | 确定 report_date | `/api/pnl/dates` |
| `overview` | 正式损益汇总 | 展示核心指标与行数 | `/api/pnl/overview` |
| `formal_rows` | formal FI 明细 | 展示正式 FI 行 | `/api/pnl/data` |
| `nonstd_rows` | nonstd bridge 明细 | 展示非标桥接行 | `/api/pnl/data` |
| `result_meta` | provenance / evidence | 展示 dates/overview/data 的 envelope | meta panel |

#### 禁止 section

- 在页面端重做 516 符号逻辑
- 把 standardized total 当 formal total 解读

### D. 筛选与时间语义

- 页面主筛选：
  - `report_date`
  - `basis`（当前页面支持 `formal/analytical` 选择，但当前主字典只认 formal 主链）
- `requested_report_date`：
  - `selectedReportDate`
- `resolved_report_date`：
  - 后端返回 `report_date`
- `as_of_date`：
  - 当前未统一；临时按 `report_date`
- latest fallback 是否允许：
  - 页面默认使用 `report_dates[0]`
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 日期列表 | `/api/pnl/dates` | `PnlDatesPayload` | `formal/analytical` | 当前页面以 formal 为主 |
| 汇总 | `/api/pnl/overview` | `PnlOverviewPayload` | 同请求 basis | 核心 KPI |
| 明细 | `/api/pnl/data` | `PnlDataPayload` | 同请求 basis | formal FI + nonstd bridge |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 利息收入（514） | `MTR-PNL-001` | `overview.interest_income_514` / row |
| 公允价值变动（516） | `MTR-PNL-002` | `overview.fair_value_change_516` / row |
| 资本利得（517） | `MTR-PNL-003` | `overview.capital_gain_517` / row |
| 手工调整 | `MTR-PNL-004` | `overview.manual_adjustment` / row |
| 正式总损益 | `MTR-PNL-005` | `overview.total_pnl` / row |
| 正式 FI 行数 | `MTR-PNL-101` | `overview.formal_fi_row_count` |
| 非标桥接行数 | `MTR-PNL-102` | `overview.nonstd_bridge_row_count` |
| 投资类型标准分类 | `MTR-PNL-103` | row `invest_type_std` |
| 会计分类 | `MTR-PNL-104` | row `accounting_basis` |

### G. 状态合同

- Loading：
  - dates 未就绪时 overview/data 不查询
- Empty：
  - 当前选中 report_date 无数据时展示 empty 表
- Stale / fallback：
  - 若 basis 不是 formal，页面必须明示不是正式主链
- Error：
  - `404`：当前报告日无 PnL 数据
  - `503`：materialization / lineage / runtime 不可用

### H. 对账与黄金样本

- 黄金样本：
  - `GS-PNL-OVERVIEW-A`
  - `GS-PNL-DATA-A`
- 对账对象：
  - overview ↔ data rows aggregation

### I. 自动化测试

- 前端：
  - `frontend/src/test/PnlPage.test.tsx`
- 后端：
  - `tests/test_pnl_api_contract.py`
  - `tests/test_pnl_formal_semantics_contract.py`

## 8. PAGE-BRIDGE-001 PnL Bridge

### A. 页面身份

- 页面 ID：`PAGE-BRIDGE-001`
- 页面名称：`PnL Bridge`
- 路由：
  - 前端：`/pnl-bridge`
  - 后端：
    - `/api/pnl/dates`
    - `/api/pnl/bridge`
    - `/api/pnl/refresh*`
- 页面状态：
  - `active`

### B. 页面目标

- 主要使用者：
  - 研究员
  - 风险/归因用户
- 页面要回答的业务问题：
  1. 当前报告日的 actual pnl 与 explained pnl 是否能对上。
  2. bridge 各分解项对损益解释贡献是多少。
  3. 当前 bridge 的质量是 `ok / warning / error` 中哪一种。
- 页面不负责回答的问题：
  - 不负责替代 formal PnL 明细页
  - 不负责展示未纳入 governed bridge 的未来模块

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `dates` | 报告日选择 | 确定 report_date | `/api/pnl/dates` |
| `summary_kpis` | bridge 概览 | 展示 explained/actual/residual/quality | `/api/pnl/bridge` |
| `waterfall` | bridge 主图 | 展示各分解项 | `/api/pnl/bridge` |
| `detail_table` | 明细表 | 展示 instrument 级桥接 | `/api/pnl/bridge` |
| `result_meta` | provenance / evidence | 展示 dates/bridge meta | meta panel |

#### 禁止 section

- 把 bridge warning 静默为正常
- 把 future-only 归因 section 写成当前已晋升

### D. 筛选与时间语义

- 页面主筛选：
  - `report_date`
- `requested_report_date`：
  - `selectedReportDate`
- `resolved_report_date`：
  - 后端返回 `report_date`
- `as_of_date`：
  - 当前未统一；临时按 `report_date`
- latest fallback 是否允许：
  - 页面默认取 `report_dates[0]`
- latest fallback 是否必须可见：
  - 是，尤其是曲线 fallback / vendor stale

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 日期列表 | `/api/pnl/dates` | `PnlDatesPayload` | `formal` | 与 PnL 共享 |
| bridge | `/api/pnl/bridge` | `PnlBridgePayload` | `formal` | 页面主读面 |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 期初脏价市值 | `MTR-BRG-001` | row `beginning_dirty_mv` |
| 期末脏价市值 | `MTR-BRG-002` | row `ending_dirty_mv` |
| Carry | `MTR-BRG-003` | row / summary `carry` |
| Roll-down | `MTR-BRG-004` | row / summary `roll_down` |
| 国债曲线效应 | `MTR-BRG-005` | row / summary `treasury_curve` |
| 信用利差效应 | `MTR-BRG-006` | row / summary `credit_spread` |
| FX 折算效应 | `MTR-BRG-007` | row / summary `fx_translation` |
| 已实现交易损益 | `MTR-BRG-008` | row / summary `realized_trading` |
| 未实现公允价值 | `MTR-BRG-009` | row / summary `unrealized_fv` |
| 手工调整 | `MTR-BRG-010` | row / summary `manual_adjustment` |
| 可解释损益 | `MTR-BRG-011` | row / summary `explained_pnl` |
| 实际损益 | `MTR-BRG-012` | row / summary `actual_pnl` |
| 残差 | `MTR-BRG-013` | row / summary `residual` |
| 残差占比 | `MTR-BRG-014` | row `residual_ratio` |
| bridge 行数 | `MTR-BRG-101` | `summary.row_count` |
| ok 行数 | `MTR-BRG-102` | `summary.ok_count` |
| warning 行数 | `MTR-BRG-103` | `summary.warning_count` |
| error 行数 | `MTR-BRG-104` | `summary.error_count` |
| quality 标记 | `MTR-BRG-105` | `summary.quality_flag` |

### G. 状态合同

- Loading：
  - bridge 未返回前，不显示伪 waterfall
- Empty：
  - row_count=0 时显示 empty state
- Stale / fallback：
  - 若 curve fallback / vendor stale，则页面必须业务可见
- Error：
  - `404`：无 bridge 数据
  - `503`：curve / lineage / materialization prerequisite 不可用

### H. 对账与黄金样本

- 黄金样本：
  - `GS-BRIDGE-A`
- 对账对象：
  - formal PnL overview
  - balance-analysis 当前/上期 balance inputs

### I. 自动化测试

- 前端：
  - `frontend/src/test/PnlBridgePage.test.tsx`
- 后端：
  - `tests/test_pnl_api_contract.py`
  - `tests/test_pnl_bridge_core.py`
  - `tests/test_pnl_bridge_curve_effects.py`
  - `tests/test_pnl_bridge_fx_translation.py`

## 9. PAGE-RISK-001 风险张量

### A. 页面身份

- 页面 ID：`PAGE-RISK-001`
- 页面名称：`风险张量`
- 路由：
  - 前端：`/risk-tensor`
  - 后端：
    - `/api/risk/tensor/dates`
    - `/api/risk/tensor`
- 页面状态：
  - `active`

### B. 页面目标

- 主要使用者：
  - 风险用户
  - 研究员
- 页面要回答的业务问题：
  1. 当前报告日组合的 DV01/KRD/CS01/凸性是什么。
  2. 当前发行人集中度和流动性缺口是否异常。
  3. 当前风险质量标记是否正常。
- 页面不负责回答的问题：
  - 不负责替代 excluded 的 `/ui/risk/overview`
  - 不负责补算任何风险衍生指标

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `dates` | 报告日选择 | 确定 report_date | `/api/risk/tensor/dates` |
| `summary_kpis` | 风险摘要 | 展示 DV01、CS01、凸性、集中度、流动性缺口 | `/api/risk/tensor` |
| `krd_chart` | KRD 图 | 展示期限桶风险 | `/api/risk/tensor` |
| `radar` | 风险雷达 | 展示强弱对比 | `/api/risk/tensor` |
| `result_meta` | provenance / evidence | 展示 dates/tensor meta | meta panel |

#### 禁止 section

- 前端重算 KRD / DV01 / CS01 / convexity
- 把 excluded 的 `risk-overview` 内容移花接木进来

### D. 筛选与时间语义

- 页面主筛选：
  - `report_date`
- `requested_report_date`：
  - URL query `report_date` 或默认首个 dates
- `resolved_report_date`：
  - 后端返回的 `report_date`
- `as_of_date`：
  - 当前未统一；临时按 `report_date`
- latest fallback 是否允许：
  - 页面默认取 `dates[0]`
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 日期列表 | `/api/risk/tensor/dates` | dates payload | `formal` | 页面初始化 |
| 风险张量 | `/api/risk/tensor` | `RiskTensorPayload` | `formal` | 页面主读面 |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 组合 DV01 | `MTR-RSK-001` | `portfolio_dv01` |
| KRD 1Y | `MTR-RSK-002` | `krd_1y` |
| KRD 3Y | `MTR-RSK-003` | `krd_3y` |
| KRD 5Y | `MTR-RSK-004` | `krd_5y` |
| KRD 7Y | `MTR-RSK-005` | `krd_7y` |
| KRD 10Y | `MTR-RSK-006` | `krd_10y` |
| KRD 30Y | `MTR-RSK-007` | `krd_30y` |
| CS01 | `MTR-RSK-008` | `cs01` |
| 组合凸性 | `MTR-RSK-009` | `portfolio_convexity` |
| 修正久期 | `MTR-RSK-010` | `portfolio_modified_duration` |
| 发行人集中度 HHI | `MTR-RSK-011` | `issuer_concentration_hhi` |
| 前五发行人占比 | `MTR-RSK-012` | `issuer_top5_weight` |
| 30 天流动性缺口 | `MTR-RSK-017` | `liquidity_gap_30d` |
| 90 天流动性缺口 | `MTR-RSK-018` | `liquidity_gap_90d` |
| 30 天流动性缺口比例 | `MTR-RSK-019` | `liquidity_gap_30d_ratio` |
| 债券数量 | `MTR-RSK-101` | `bond_count` |
| 风险质量标记 | `MTR-RSK-102` | `quality_flag` |

### G. 状态合同

- Loading：
  - dates 成功前不查 tensor
- Empty：
  - `bond_count=0` 时进入 empty
- Stale / fallback：
  - 若 `quality_flag != ok` 必须在页面可见
- Error：
  - `404`：当前报告日无 tensor 数据
  - `503`：risk tensor governed prerequisite 缺失

### H. 对账与黄金样本

- 黄金样本：
  - `GS-RISK-A`
- 对账对象：
  - bond analytics risk summary
  - executive overview 管理视图中的 DV01

### I. 自动化测试

- 前端：
  - `frontend/src/test/RiskTensorPage.test.tsx`
- 后端：
  - `tests/test_risk_tensor_api.py`
  - `tests/test_risk_tensor_core.py`
  - `tests/test_risk_tensor_liquidity.py`

## 10. PAGE-EXEC-OVERVIEW-001 executive overview

### 页面身份

- 页面 ID：`PAGE-EXEC-OVERVIEW-001`
- 页面名称：`executive overview`
- 后端路由：`/ui/home/overview`
- 页面状态：`active`

### 页面目标

- 给管理层提供当前已晋升的四个核心经营指标摘要
- 明确这是 `analytical` consumer overlay，不是 formal source-of-truth 页

### 必有 section

- `metrics`
- `result_meta`

### 指标映射

- `MTR-EXEC-001`
- `MTR-EXEC-002`
- `MTR-EXEC-003`
- `MTR-EXEC-004`

### 状态合同

- `200`：返回 analytical envelope
- `422`：非法 `report_date`
- 不允许 silent downgrade 成 mock

### 自动化测试

- `tests/test_executive_dashboard_endpoints.py`

## 11. PAGE-EXEC-SUMMARY-001 executive summary

### 页面身份

- 页面 ID：`PAGE-EXEC-SUMMARY-001`
- 页面名称：`executive summary`
- 后端路由：`/ui/home/summary`
- 页面状态：`active`

### 页面目标

- 给管理层输出当前受控摘要 narrative 和 3 个摘要点
- 当前不纳入业务指标字典主表；属于 narrative contract

### 必有 section

- `narrative`
- `points`
- `result_meta`

### 禁止事项

- 把 narrative 当成 formal 指标
- 用 narrative 覆盖页面上游指标缺失事实

### 自动化测试

- `tests/test_executive_dashboard_endpoints.py`

## 12. PAGE-EXEC-PNL-ATTR-001 executive pnl attribution

### 页面身份

- 页面 ID：`PAGE-EXEC-PNL-ATTR-001`
- 页面名称：`executive pnl attribution`
- 后端路由：`/ui/pnl/attribution`
- 页面状态：`active`

### 页面目标

- 给管理层提供收益归因的简化段值视图
- 当前属于 analytical composition，不冒充 formal bridge

### 必有 section

- `total`
- `segments`
- `result_meta`

### 指标映射

- `MTR-EXEC-101`
- `MTR-EXEC-102`
- `MTR-EXEC-103`
- `MTR-EXEC-104`
- `MTR-EXEC-105`
- `MTR-EXEC-106`

### 状态合同

- `200`：返回 analytical envelope
- `422`：非法 `report_date`
- 当前即便上游缺失，也必须保持“显式 analytical overlay”语义，不得伪装 formal

### 自动化测试

- `tests/test_executive_dashboard_endpoints.py`

## 13. PAGE-PNL-ATTR-WB-001 PnL Attribution Workbench

### A. 页面身份

- 页面 ID：`PAGE-PNL-ATTR-WB-001`
- 页面名称：`损益归因分析工作台`
- 前端路由：`/pnl-attribution`
- 后端依赖：
  - `/api/pnl-attribution/volume-rate`
  - `/api/pnl-attribution/tpl-market`
  - `/api/pnl-attribution/composition`
  - `/api/pnl-attribution/summary`
  - `/api/pnl-attribution/advanced/carry-rolldown`
  - `/api/pnl-attribution/advanced/spread`
  - `/api/pnl-attribution/advanced/krd`
  - `/api/pnl-attribution/advanced/summary`
  - `/api/pnl-attribution/campisi/four-effects`
  - `/api/pnl-attribution/campisi/enhanced`
  - `/api/pnl-attribution/campisi/maturity-buckets`
- 页面状态：`active`

### B. 页面目标

- 主要使用者：
  - 研究员
  - 归因/风险用户
- 页面要回答的业务问题：
  1. 当前期间损益变动主要来自规模还是利率。
  2. TPL 公允价值与国债收益率变化是否同向解释。
  3. 当前损益构成和高级归因是否能在页面内自洽。
- 页面不负责回答的问题：
  - 不负责替代 `/pnl` 正式损益真值页
  - 不负责替代 executive analytical overlay `/ui/pnl/attribution`

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `tab_switcher` | 归因视图切换 | 决定当前读链路 | 页面 state |
| `current_view_meta` | 当前视图元信息 | 显示当前 tab 的 `generated_at / quality_flag / fallback_mode` | 当前 tab 主接口 |
| `volume_rate` | 规模 / 利率效应 | 展示两期间分解 | `/api/pnl-attribution/volume-rate` |
| `tpl_market` | TPL 市场相关性 | 展示 TPL 与 10Y 的关系 | `/api/pnl-attribution/tpl-market` |
| `composition` | 损益构成 | 展示利息、公允、投资收益、其他收入 | `/api/pnl-attribution/composition` |
| `advanced` | 高级归因 + Campisi | 展示 carry/spread/krd/campisi | advanced + campisi endpoints |

#### 必须可见的 provenance

- 当前 active tab 必须显示：
  - `generated_at`
  - `quality_flag`
  - `fallback_mode`
- advanced 视图还必须显示子模块 provenance strip：
  - `Carry / Roll-down`
  - `利差归因`
  - `KRD归因`
  - `高级摘要`
  - `Campisi 四效应`
  - `Campisi 六效应`
  - `Campisi 到期桶`

### D. 筛选与时间语义

- 页面主筛选：
  - 当前 tab
  - volume-rate 的 `compare_type`
  - 可选 `report_date`（当前页面仍未统一交互控件）
- `requested_report_date`：
  - 当前由页面 props / query builder 透传；缺省时使用各 endpoint 默认 latest 行为
- `resolved_report_date`：
  - 当前按各 payload 的 `report_date / current_period / start_period-end_period` 解释
- `as_of_date`：
  - 当前未统一为独立 outward 字段
- `generated_at`：
  - 来自当前 tab 主接口 `result_meta.generated_at`
- latest fallback 是否允许：
  - 允许，但页面必须显示 `fallback_mode`
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 规模/利率 | `/api/pnl-attribution/volume-rate` | `VolumeRateAttributionPayload` | `formal` | `current_yield_pct / previous_yield_pct` 为百分比值 |
| TPL 市场 | `/api/pnl-attribution/tpl-market` | `TPLMarketCorrelationPayload` | `formal` | `treasury_10y_total_change_bp` 为 BP |
| 损益构成 | `/api/pnl-attribution/composition` | `PnlCompositionPayload` | `formal` | `other_income` 必须可见 |
| 归因摘要 | `/api/pnl-attribution/summary` | `PnlAttributionAnalysisSummary` | `formal` | 当前仅做说明性 findings |
| 高级摘要 | `/api/pnl-attribution/advanced/summary` | `AdvancedAttributionSummary` | `formal` | `static_return_annualized` 已是年化值 |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 当前收益率（百分比） | `MTR-PAT-003` | `current_yield_pct` |
| 上期收益率（百分比） | `MTR-PAT-004` | `previous_yield_pct` |
| 累计 10Y 国债变动（BP） | `MTR-PAT-102` | `treasury_10y_total_change_bp` |
| 其他收入 / 调整项 | `MTR-PAT-205` | `total_other_income` / `other_income` |
| 静态收益（年化） | `MTR-PAT-301` | `static_return_annualized` |
| 当前视图元信息 | `MTR-PAT-304` | `generated_at / quality_flag / fallback_mode` |

### G. 状态合同

- Loading：
  - 当前 tab 切换时只阻塞当前视图，不要求整页 skeleton
- Empty：
  - 各 tab 可返回空结构，但必须保留 `result_meta`，不得无声回到 demo 解释
- Stale / fallback：
  - `quality_flag != ok` 或 `fallback_mode != none` 时必须出现在 `current_view_meta`
- Error：
  - API 失败时显示错误卡片，不在前端补算或静默替代

### H. 自动化测试

- 前端：
  - `frontend/src/test/PnlAttributionPage.test.tsx`
  - `frontend/src/test/PnlCompositionChart.test.tsx`
  - `frontend/src/test/AdvancedAttributionChart.test.tsx`
  - `frontend/src/test/TPLMarketChart.test.tsx`
  - `frontend/src/test/PnlAttributionSection.test.tsx`
- 后端：
  - `tests/test_pnl_attribution_api_contract.py`
  - `tests/test_pnl_attribution_workbench_contract.py`

## 13.5 PAGE-OPS-001 经营分析

### A. 页面身份

- 页面 ID：`PAGE-OPS-001`
- 页面名称：`经营分析`
- 前端路由：`/operations-analysis`
- 页面状态：`wave-1 temporary exception`

### B. 页面只回答一个问题

`今天的经营判断是否已有可信证据支撑；如果需要下钻，第一站应该进入哪个正式专题页？`

本页 wave 1 不承担完整经营驾驶舱，也不承担静态经营结论展示。

### C. wave 1 允许的首屏区块

- source preview 状态
- macro latest 状态
- formal FX status
- balance-analysis overview 速览
- pnl refresh operational status
- 一个只由 live query 状态推导出的 recommendation panel
- drilldown links

### D. wave 1 首屏禁止区块

- 硬编码 KPI 行
- `BusinessConclusion`
- `RevenueCostBridge`
- `QualityObservation`
- `BusinessContributionTable`
- mock `AlertList`
- mock `CalendarList`
- `TenorConcentrationPanel`
- `ManagementOutput`

### E. 页面依赖的最小 query 边界

- `getSourceFoundation`
- `getMacroFoundation`
- `getChoiceMacroLatest`
- `getFxFormalStatus`
- `getBalanceAnalysisDates`
- `getBalanceAnalysisOverview`
- `getChoiceNewsEvents` 仅可作为 advisory 信息
- `refreshFormalPnl` / `getFormalPnlImportStatus` 仅可作为 operational state

### F. 验证要求

- 首屏 recommendation 必须能追到：
  `API response -> page-local derivation -> component`
- 若 wave 1 未完成本页闭环，则下一轮 readiness pass 必须把本页从 `live` 降级
- 相关前端验证至少覆盖：
  - `frontend/src/test/OperationsAnalysisPage.test.tsx`
  - `frontend/src/test/navigation.test.ts`
  - `frontend/src/test/RouteRegistry.test.tsx`
  - `frontend/src/test/WorkbenchShell.test.tsx`

## 14. PAGE-PROD-CAT-PNL-001 产品分类损益（正式）

### A. 页面身份

- 页面 ID：`PAGE-PROD-CAT-PNL-001`（与 `docs/pnl/product-category-page-truth-contract.md` 中的 `PAGE-PROD-CAT-001` 指同一受治理表面；本文件为 page contract 命名空间下的绑定 ID）
- 页面名称：`产品分类损益`
- 路由：
  - 前端：`/product-category-pnl`（`frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`）
  - 后端主读面：
    - `GET /ui/pnl/product-category`
    - `GET /ui/pnl/product-category/dates`
    - `POST /ui/pnl/product-category/refresh`、相关 `refresh-status`
    - manual adjustments 与 export 见 truth contract
- 页面状态：
  - `active`（正式主链；closure 见 `docs/pnl/product-category-closure-checklist.md`）
- 权威真值与字段冻结：
  - `docs/pnl/product-category-page-truth-contract.md`
  - `docs/pnl/adr-product-category-truth-chain.md`

### B. 页面目标

- 主要使用者：财务/研究/治理需要按产品分类看 formal PnL 的用户。
- 页面要回答的业务问题（首要）：
  1. 在选定 `report_date` 与主屏视图（`monthly` / `ytd`）下，产品分类层面的损益总计、资产/负债/总计各为多少，主要由哪些分类行贡献。
- 页面不负责回答的问题（与 truth contract 一致）：
  - 持仓侧利率债/信用债/转债等研究分解
  - 属于 `/ledger-pnl` 的通用总账 PnL 问题
  - 分支口径经营结论或邻域代码推定的 ad hoc 分类

### C. 信息架构（最小 first-screen）

- 必有：报告日选择；主屏 `monthly`/`ytd` 视图；基线合计；场景对比态；分类行；`result_meta`/新鲜度；调整与审计入口（见 truth contract §8）。

### D. 筛选与时间语义

- `requested_report_date`：查询参数 `report_date`
- `resolved_report_date`：当前为 `result.report_date`
- `generated_at`：`result_meta.generated_at`
- `as_of_date`：当前未作为独立 outward 字段；视为显式合同缺口，不得隐式假设
- 禁止静默回落；退化必须可见（见 truth contract §10）

### E. Endpoint / DTO 与正式性边界

| 用途 | Endpoint | 说明 |
| --- | --- | --- |
| 明细/主表 | `GET /ui/pnl/product-category` | `result_meta.basis` 为 `formal` 或受治理 `scenario`；主链见 truth contract §6 |
| 日期 | `GET /ui/pnl/product-category/dates` | 初始化 report_date 列表 |
| 刷新/状态 | refresh 与 refresh-status | 运营态，非主读值真值面 |

- 默认解释：`formal`；`scenario_rate_pct` 等场景字段仅在显式场景载荷下成为主解释（truth contract §6、§9）。

### F. 指标与字段锚点

- 本页 `metric_id` 主表绑定**尚未**在 `docs/metric_dictionary.md` 中完备案；真值以 truth contract **field freeze** 为准，禁止在前端重算或推断：
  - 头表：`result.asset_total.business_net_income`、`result.liability_total.business_net_income`、`result.grand_total.business_net_income`
  - 行：`category_id`、`category_name`、`side`、`level`、`view`、`report_date`、`business_net_income`、`children` 等（truth contract §9）
- 对账等式见 truth contract §12（含 asset+liability 与 grand_total 一致性等）。

### G. 状态合同（stale / fallback / error）

- 须可见：`quality_flag`、`fallback_mode`、`vendor_status`、无数据、陈旧、加载失败、指标定义待确认等（truth contract §11）。
- `404` / `503` 等 HTTP 语义遵循仓库通用状态语义（与 `page_contracts` §4.3 一致）。

### H. 对账与黄金样本

- 黄金样本：`GS-PROD-CAT-PNL-A`（`tests/golden_samples/GS-PROD-CAT-PNL-A/`，断言见同目录 `assertions.md`）
- 不通过持仓分类或研究桶重解释样本行；与 `docs/pnl/product-category-golden-sample-a.md` 对账

### I. 自动化测试（锚点）

- 后端/流程：`tests/test_product_category_pnl_flow.py`、`tests/test_product_category_mapping_contract.py`
- 前端：`frontend/src/test/ProductCategoryPnlPage.test.tsx` 等（见 `product-category-closure-checklist.md`）
- capture-ready：`tests/test_golden_samples_capture_ready.py` 中 `GS-PROD-CAT-PNL-A`

## 15. 当前缺口

### 15.1 `as_of_date` 未统一

当前纳入本文件的页面/消费面仍未统一 outward `as_of_date`。

下一轮需要在 page contract 与 DTO 层统一：

- `requested_report_date`
- `resolved_report_date`
- `as_of_date`

### 15.2 fallback 可见性未统一落 UI

当前部分页面已有 `result_meta` 面板，但不是所有业务异常都会上浮成用户可见状态。

下一轮需要补：

- formal 页面 fallback banner 规范
- analytical overlay 的 stale / vendor unavailable 文案

### 15.3 黄金样本绑定未完全收敛

本文件已经给核心页面标了黄金样本方向，且部分样本包已经落地；下一步需要把 `page_id -> metric_id -> sample_id -> test file` 绑定继续收敛到一致状态。

## 16. 下一步建议

按最小顺序继续：

1. 用本文件和 `metric_dictionary.md` 继续补齐样本绑定关系
2. 给 formal 页面补统一的 fallback / stale 可见性规范
3. 再把 page contract existence / metric coverage 接入 docs-contract 测试
