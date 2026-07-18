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

**Wave 1 工作扩展（页面契约见 §13.5–§13.8，与上列 1–9 条并列索引，不修改既有 9 页编号）：**

- `/bond-dashboard`（债券总览 / 债券分析驾驶舱）
- `/positions`（持仓与对手方下钻）
- `/market-data`（市场数据：宏观/利率/外汇/结构化 NCD 等，含多源与 preview）
- `/operations-analysis`（经营分析：证据链 + 正式余额入口，Wave 1 例外与计划并存）
- `/bond-trading-desk`（单券交易分析台，深钻路由，见 §13.9）

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
- `docs/DOCUMENT_AUTHORITY.md`（`market-data` / preview / `source_preview` 排除语义）
- `docs/EXECUTIVE_CONSUMER_CUTOVER_V1.md`
- `docs/metric_dictionary.md`
- `docs/CACHE_SPEC.md`
- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx`
- `frontend/src/features/positions/pages/PositionsPage.tsx` / `PositionsView.tsx`
- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx`
- `backend/app/api/routes/bond_dashboard.py`
- `backend/app/api/routes/positions.py`
- `backend/app/api/routes/macro_vendor.py` / `market_data_ncd_proxy.py` / `macro_bond_linkage.py`
- `tests/test_positions_api_contract.py`
- `tests/test_bond_dashboard_api_contract.py`
- `tests/test_result_meta_source_surface_followup.py`（`bond_analytics` surface 与 `bond_dashboard` dates）
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
    - `/ui/home/snapshot`
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
| `judgment` | 本日判断 | 基于首页快照和治理状态给出是否可判断 | `/ui/home/snapshot.result.verdict` |
| `governance` | 治理状态 | 显示报告日、快照、质量、读链路 | `/ui/home/snapshot.result_meta` + `domains_effective_date` |
| `overview_metrics` | 核心经营指标 | 先给出管理层的关键经营 KPI | `/ui/home/snapshot.result.overview.metrics` |
| `product_category_headline` | 经营贡献摘要 | 展示随 snapshot 下发的产品分类损益摘要 | `/ui/home/snapshot.result.product_category_*` |

#### 可选 section

| section_key | 名称 | 启用条件 | 备注 |
| --- | --- | --- | --- |
| `core_metrics` | 债券 / 同业核心指标 | 仅当补充读面报告日等于首页快照 `report_date` | `supplemental`，只能在下钻区展示 |
| `daily_changes` | 日 / 周 / 月变动 | 仅当补充读面报告日等于首页快照 `report_date` | `supplemental`，只能在下钻区展示 |
| `market_context` | 市场上下文 | 不作为报告日判断依据 | `supplemental`，只能在下钻区展示 |
| `research_calendar` | 关键事件日历 | 不作为报告日判断依据 | `supplemental`，只能在下钻区展示 |
| `macro_release_context` | 宏观发布与历史变动 | 使用独立自然日窗口，不作为报告日判断依据 | `supplemental`，只能在延迟加载的下钻区展示；未接入来源保持 `source_pending` |
| `risk_overview` | 风险概览 | 当前不启用 | `reserved`，不发 live 首页请求 |
| `alerts` | 预警中心 | 当前不启用 | `reserved`，不发 live 首页请求 |
| `contribution` | 团队/账户/策略贡献 | 当前不启用 | `reserved`，不发 live 首页请求 |

#### Snapshot MVP section 状态矩阵

本轮驾驶舱 MVP 使用统一 section 状态，避免把未治理读面伪装成首屏结论：

| section_key | 状态 | 首屏展示 | 业务规则 |
| --- | --- | --- | --- |
| `judgment` | `landed` | 是 | 来自 `/ui/home/snapshot` verdict；若 mock / warning / partial，则降级为复核判断。 |
| `governance` | `landed` | 是 | 来自 `/ui/home/snapshot.result_meta`、`domains_effective_date`、`domains_missing`。 |
| `overview_metrics` | `landed` / `blocked` | 是 | 仅使用 snapshot overview；为空时显示空态，不得用 `core_metrics` 顶替。 |
| `product_category_headline` | `landed` | 是 | 随 snapshot 下发；前端只展示，不重算。 |
| `core_metrics` | `supplemental` / `blocked` | 否 | 补充读面报告日必须等于首页快照 `report_date`；不一致则 `blocked`。 |
| `daily_changes` | `supplemental` / `blocked` | 否 | 补充读面报告日必须等于首页快照 `report_date`；不一致则 `blocked`。 |
| `market_context` | `supplemental` | 否 | 市场/宏观数据不绑定首页严格报告日，只能作为下钻上下文。 |
| `research_calendar` | `supplemental` | 否 | 自然日事件窗口，只能作为下钻上下文。 |
| `macro_release_context` | `supplemental` | 否 | 由 `/ui/home/macro-release-context` 提供自然日宏观发布与历史变动上下文；不参与首页主判断，`source_pending` 不得伪装成 0 或正常值。 |
| `risk_overview` | `reserved` | 否 | 当前边界为 reserved/excluded surface，不发 live 首页请求。 |
| `contribution` | `reserved` | 否 | 当前边界为 reserved/excluded surface，不发 live 首页请求。 |
| `alerts` | `reserved` | 否 | 当前边界为 reserved/excluded surface，不发 live 首页请求。 |
| 静态演示内容 | `demo` | 否 | 只能留在占位或演示区，不进入首屏判断。 |

#### 禁止 section

- 把 `/ui/risk/overview`、`/ui/home/alerts`、`/ui/home/contribution` 的失败状态渲染成伪正常数据
- 在驾驶舱中补算专业页正式指标

### D. 筛选与时间语义

- 页面主筛选：
  - `report_date` 日期选择器；默认不传参，由 `/ui/home/snapshot` 选择最新严格交集日期
- `requested_report_date`：
  - 用户手动选择时传给 `/ui/home/snapshot`
- `resolved_report_date`：
  - `/ui/home/snapshot.result.report_date`
- `as_of_date`：
  - 本轮先使用 `domains_effective_date` 显示各核心域有效日期
- `generated_at`：
  - 来自 `/ui/home/snapshot.result_meta.generated_at`
- `macro_release_context` 自然日窗口：
  - 使用独立的 `start_date` / `end_date` / `history_limit`，不复用 snapshot `report_date`，不参与首页主判断。
- latest fallback 是否允许：
  - strict 默认使用最新严格交集；手动开启 partial 才允许含缺域
- latest fallback 是否必须可见：
  - 是

### E. Endpoint / DTO 契约

| 用途 | Endpoint | Response DTO | basis | 备注 |
| --- | --- | --- | --- | --- |
| 首页统一快照 | `/ui/home/snapshot` | `HomeSnapshotPayload` | `analytical` | 本轮驾驶舱 MVP 的主入口；默认最新严格交集 |
| 总览 | `/ui/home/overview` | `OverviewPayload` | `analytical` | 当前已纳入 cutover |
| 摘要 | `/ui/home/summary` | `SummaryPayload` | `analytical` | 当前已纳入 cutover |
| 收益归因 | `/ui/pnl/attribution` | `PnlAttributionPayload` | `analytical` | 当前已纳入 cutover |
| 风险概览 | `/ui/risk/overview` | `RiskOverviewPayload` | `analytical` | 当前 excluded，默认 `503` |
| 宏观发布与历史变动 | `/ui/home/macro-release-context` | `HomeMacroReleaseContextEnvelope` | `analytical` | supporting API；`result_kind` = `home.macro_release_context`、`formal_use_allowed=false`、`source_surface=market_data`；不进入首屏主判断 |
| 贡献 | `/ui/home/contribution` | `ContributionPayload` | `analytical` | 当前 excluded，默认 `503` |
| 预警 | `/ui/home/alerts` | `AlertsPayload` | `analytical` | 当前 excluded，默认 `503` |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 资产规模 | `MTR-EXEC-001` | `overview.metrics[id=aum]` |
| 年度损益（不扣FTP） | `MTR-EXEC-002` | `overview.metrics[id=yield]` |
| 净息差 | `MTR-EXEC-003` | `overview.metrics[id=nim]` |
| 组合 DV01（管理视图） | `MTR-EXEC-004` | `overview.metrics[id=dv01]` |
| AC DV01（管理拆分） | `MTR-EXEC-004A` | `risk_overview.signals[id=dv01_ac]` |
| OCI DV01（管理拆分） | `MTR-EXEC-004B` | `risk_overview.signals[id=dv01_oci]` |
| TPL DV01（管理拆分） | `MTR-EXEC-004C` | `risk_overview.signals[id=dv01_tpl]` |
| 收益归因总额 | `MTR-EXEC-101` | `pnl_attribution.total` |
| Carry 归因 | `MTR-EXEC-102` | `pnl_attribution.segments[id=carry]` |
| Roll-down 归因 | `MTR-EXEC-103` | `pnl_attribution.segments[id=roll]` |
| 信用利差归因 | `MTR-EXEC-104` | `pnl_attribution.segments[id=credit]` |
| 交易损益归因 | `MTR-EXEC-105` | `pnl_attribution.segments[id=trading]` |
| 其他归因 | `MTR-EXEC-106` | `pnl_attribution.segments[id=other]` |

### G. 状态合同

- Loading：
  - snapshot 主链 loading 时首屏显示空态和治理 loading，不用补充接口造结论
- Empty：
  - `overview_metrics` 为空时显示空态；不得使用 `core_metrics` 或 demo 数字顶替首屏 KPI
- Stale / fallback：
  - 若已晋升 surface 出现 `fallback_mode != none` 或 `vendor_status != ok`，dashboard 必须可见
- Error / fail-closed：
  - excluded surface 返回 `503` 时，该 section 直接不显示，不得渲染为 live 正常卡片
  - `core_metrics` / `daily_changes` 与首页快照报告日不一致时必须阻断展示，只能提示报告日不一致

  - `macro_release_context` 的 `ready` / `partial` / `stale` / `fallback` / `source_pending` / `error` 与 `no-data` 必须可见；美国未接入指标保持 `source_pending`。
  - 禁止静态历史数值回退；自动接口失败或无可用证据时显示 `自动数据暂不可用`，不得恢复人工维护值。
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
  - `frontend/src/features/workbench/dashboard/dashboardHomeModel.test.ts`
- 后端：
  - `tests/test_executive_dashboard_endpoints.py`
  - `tests/test_home_snapshot_endpoint.py`

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
    - `/api/risk/scenario-stress`
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
  4. 当前组合久期覆盖了哪些利率风险适用资产，哪些市值被排除在久期分母外。
- 页面不负责回答的问题：
  - 不负责替代 excluded 的 `/ui/risk/overview`
  - 不负责补算任何风险衍生指标
  - 压力结果仅由独立 `scenario` endpoint 提供，不进入 formal Risk Tensor DTO

### C. 信息架构

#### 必有 section

| section_key | 名称 | 目的 | 数据来源 |
| --- | --- | --- | --- |
| `dates` | 报告日选择 | 确定 report_date | `/api/risk/tensor/dates` |
| `summary_kpis` | 风险摘要 | 展示 DV01、CS01、凸性、集中度、流动性缺口 | `/api/risk/tensor` |
| `duration_scope` | 久期口径披露 | 展示利率风险适用市值、DV01、久期，以及被排除的市值/行数 | `/api/risk/tensor` |
| `krd_chart` | KRD 图 | 展示期限桶风险 | `/api/risk/tensor` |
| `radar` | 风险雷达 | 展示强弱对比 | `/api/risk/tensor` |
| `scenario_stress` | 压力情景 | 展示独立 scenario 口径的利率、信用、流动性与 FX 输入缺口 | `/api/risk/scenario-stress` |
| `result_meta` | provenance / evidence | 展示 dates/tensor meta | meta panel |

#### 禁止 section

- 前端重算 KRD / DV01 / CS01 / convexity
- 前端为无到期日资产合成到期日或久期
- 用 `portfolio_dv01` 回填或伪装 `regulatory_dv01`
- 把 `prior_period_change`、`dv01_controls` 或会计分类 DV01 注入 formal Risk Tensor DTO
- 把 scenario 压力估算、限额判断或处置建议标记为 `formal`
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
| 压力情景 | `/api/risk/scenario-stress` | `RiskScenarioStressPayload` | `scenario` | `formal_use_allowed=false`，仅作人工复核覆盖层 |

### F. 指标映射

| 页面展示项 | `metric_id` | 来源字段 |
| --- | --- | --- |
| 组合 DV01 | `MTR-RSK-001` | `portfolio_dv01` |
| 监管口径 DV01 | `MTR-RSK-001R` | `regulatory_dv01` |
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
| 利率风险市值 | `MTR-RSK-021` | `rate_risk_market_value` |
| 利率风险 DV01 | `MTR-RSK-022` | `rate_risk_dv01` |
| 利率风险久期 | `MTR-RSK-023` | `rate_risk_modified_duration` |
| 债券数量 | `MTR-RSK-101` | `bond_count` |
| 风险质量标记 | `MTR-RSK-102` | `quality_flag` |
| 久期排除行数 | `MTR-RSK-103` | `duration_excluded_count` |
| 久期排除市值 | `MTR-RSK-104` | `duration_excluded_market_value` |

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
  - `GS-RISK-WARN-B`（warning-profile）
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
- `MTR-EXEC-004A/B/C` 为管理风险总览拆分项；`MTR-EXEC-004` 总量保持全量含 AC/OCI/TPL

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
- 路由：前端 `/operations-analysis`（`frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx`）
- 页面状态：`mixed-source`（当前首屏正式经营口径复用 product-category PnL headline；余额读面仅作为专题入口补充；`basis=analytical` 的 source/macro/news 与 FX 覆盖状态仍为证据/观察面；`WorkbenchShell` 对本路由保留 **temporary exception** 横幅）
- 经营分析 harness：见 `docs/operating_analysis_harness.md`；本页只执行 `operating_analysis_driver_taxonomy_v1` 的证据门，要求经营差异落入 `market` / `business_action` / `accounting_caliber` / `one_off` / `data_issue` / `driver_unclear` 之一，不能据此新建 `MTR-OPS-*` 或把 mixed-source 证据升格为 formal truth。
- 编制备注：`client.mode === "real"` 与 `"mock"` 分支影响 badge/演示语义；**不得**将 mock 与真实链路混读为同一正式结论。

### B. 页面目标

- 主要问题（业务）：**当前经营判断是否已有可追证的读链路支撑；若需要下钻，第一站应进哪个受治理专题页？**
- 明确 **不负责**：
  - 不替代 `balance-analysis` 工作簿/明细真值
  - 不替代 `pnl` / 产品分类损益正式页；本页只复用产品分类损益正式页已批准的 headline truth
  - 不把 `source_preview` / Choice news / macro `preview` 伪装为 formal compute 主链真值
  - 不承诺 Wave 1 文档中列为「禁止首屏」的组件已从代码中物理移除（见下 **Pending**）

### C. 信息架构（按 repo 实装 + Wave 1 目标态）

| 类别 | section_key / 组件 | 状态 | 备注 |
| --- | --- | --- | --- |
| 必有（代码已渲染） | `hero` / `PageHeader` + `operations-business-kpis` | live | Current implementation primary first-screen formal PnL evidence：前三张 KPI 卡来自 `GET /ui/pnl/product-category` 的资产端、负债端、合计经营净收入；其余卡片为日期、行数、source/macro/FX/news 证据状态 |
| 必有（代码已渲染） | `operations-conclusion-grid` 内含 `BusinessConclusion`、`RevenueCostBridge`（可测试 stub）、`QualityObservation` | **与 Wave 1 目标清单冲突** | 以代码为准作契约；收缩首屏需后续改动 |
| 必有（代码已渲染） | `operations-contribution-grid`（`BusinessContributionTable` + `AlertList` + `CalendarList` 等） | mixed | 表格为 product-category detail rows；`AlertList`/`CalendarList` 使用 `businessAnalysisWorkbenchMocks`，仍是静态示例 |
| 必有（代码已渲染） | `operations-structure-grid`（`TenorConcentrationPanel` + `ManagementOutput`） | mixed | 与 §13.5 历史「禁止区块」声明不一致；**Pending** 对齐或更新禁止清单 |
| 必有 | `recommendation` 推导 + `ManagementOutput` 行动卡片 | live | 推导见 `recommendation` `useMemo`（source 预览、product-category 日期/结果/行为空或失败时不得给出充分证据结论；FX 缺口只影响关注事项） |
| 必有 | 专题入口 `operations-entry-balance-section` 等 | live | Balance overview is supplemental topic-entry evidence；只作为 `/balance-analysis` 下钻入口，不替代首屏 product-category headline |
| 可选 / 运维 | 产品分类 PnL refresh/status | operational | 本页不承接刷新操作；刷新/调整入口归 `/product-category-pnl` truth contract |
| 可选 | `getChoiceNewsEvents` | **analytical-only** / advisory | `result_kind` 为 news vendor 流；仅作信息 |
| 禁止 | 将上述 advisory/preview、静态示例或 supplemental balance overview 混写为无 provenance 的「正式经营结论」 | — | UI 上须可区分来源（badge / meta / 失败态） |

### D. 时间语义

- `requested_report_date`：经营页自身无独立日期控件；product-category 与 balance 部分分别使用各自 dates endpoint 的 **首个** `report_dates[0]`（与页面「最新证据」策略一致，非用户逐日点选语义）。
- `resolved_report_date`：首屏经营口径以 `getProductCategoryPnl` 返回的 `result.report_date` 为准；balance 专题入口以 `getBalanceAnalysisOverview` 返回的 `result.report_date` 为准；其它 endpoint 各自带 `result_meta` / 载荷内日期字段。
- `as_of_date`：本页**未**统一为单一向外字段；各区块遵循上游契约（同 §4.1 缺口声明）。
- `generated_at`：来自各 `ApiEnvelope['result_meta'].generated_at`；多来源页须在运维/折叠区保留可核对条带（见实装中 Collapse/面板）。

### E. Endpoint / DTO 契约

| 用途 | Endpoint（前端 client 方法） | Response / DTO 要点 | `basis` / 形式 |
| --- | --- | --- | --- |
| Source 预览 | `getSourceFoundation()` → `GET /ui/preview/source-foundation` | `SourcePreviewPayload` + `result_meta` | 多为 **analytical/preview**；`formal_use_allowed: false` |
| 宏观看板目录 | `getMacroFoundation()` → `GET /ui/preview/macro-foundation` | macro catalog 系列 + `result_meta` | **analytical** |
| 宏观最新 | `getChoiceMacroLatest()` → `GET /ui/macro/choice-series/latest` | Choice macro latest points + `result_meta` | **analytical** + vendor |
| 正式汇率覆盖 | `getFxFormalStatus()` → `GET /ui/market-data/fx/formal-status` | `FxFormalStatusPayload`（rows/materialized/candidate/日期） | 正式行与缺失行表；**非**全页 formal truth |
| 新闻 | `getChoiceNewsEvents()` | 事件列表 + `result_meta` | **analytical** |
| 产品分类日期 | `client.getProductCategoryDates()` -> `GET /ui/pnl/product-category/dates` | `ProductCategoryDatesPayload` | `formal`（复用 product-category PnL 主链） |
| 产品分类 PnL | `client.getProductCategoryPnl()` -> `GET /ui/pnl/product-category` | `ProductCategoryPnlPayload`，headline + detail rows | `formal`（本页首屏经营口径） |
| 余额日期 | `getBalanceAnalysisDates()` | `BalanceAnalysisDatesPayload` | `formal`（与 balance-analysis 页同链） |
| 余额概览 | `getBalanceAnalysisOverview()` | `BalanceAnalysisOverviewPayload` | `formal`；supplemental topic-entry evidence |

### F. 指标映射（`metric_id`）

- 本页 does not create `MTR-OPS-*`。当前首屏正式经营净收入复用产品分类损益已批准的 `MTR-PCP-001`、`MTR-PCP-002`、`MTR-PCP-003` 与 `GS-PROD-CAT-PNL-A`；与正式余额重叠的专题入口展示项仍沿用 `PAGE-BALANCE-001` 在字典中的 `MTR-BAL-*`，以 `getBalanceAnalysisOverview` 字段为准；其余为 **analytical/preview/operational 展示**，仅字段路径，**无**独立字典行。

| 展示锚点 | `metric_id`（若可映射） | 来源 |
| --- | --- | --- |
| 资产端经营净收入 | `MTR-PCP-001` | `ProductCategoryPnlPayload.asset_total.business_net_income` |
| 负债端经营净收入 | `MTR-PCP-002` | `ProductCategoryPnlPayload.liability_total.business_net_income` |
| 合计经营净收入 | `MTR-PCP-003` | `ProductCategoryPnlPayload.grand_total.business_net_income` |
| product-category detail rows | 不新增 `metric_id` | detail rows 仍按 product-category truth contract / sample truth，不在本页升格 |
| 总市值/摊余/应计/行数 | `MTR-BAL-001`–`MTR-BAL-103`（与 balance 页一致部分） | `BalanceAnalysisOverviewPayload`；supplemental topic-entry evidence |
| Source/Macro/News/FX 卡计数 | 不适用（无 `metric_id`）；`GAP-OPS-MACRO-FX` | 各 `result` 列表长度或 envelope |

### G. 状态：loading / empty / stale / fallback / error

- **Loading**：`AsyncSection` 与多 `useQuery` 并存；product-category、balance 与 `source/macro` 可不同步完成。
- **Empty**：`recommendation` 在 `sourceSummaries`、product-category 日期、product-category payload 或 detail rows 为空时走证据链不完整分支；balance 无日期只影响专题入口。
- **Stale / fallback**：遵循各 `result_meta.fallback_mode`、`quality_flag`、`vendor_status`；`ManagementOutput` / KPI 行须能反映查询失败态（`buildStatusCardContent` 等）。
- **Error**：`isError` 时 recommendation 与卡片文案必须可见；禁止用静态 KPI 行掩盖。
- **Mock 模式**：`client.mode === "mock"` 时首屏仍须标注演示语义（badge）。

### H. 测试与黄金样本锚点

- 测试：`frontend/src/test/OperationsAnalysisPage.test.tsx`、`navigation.test.ts`、`RouteRegistry.test.tsx`、`WorkbenchShell.test.tsx`（与 §13.5 旧表一致）
- 黄金样本：本页**无**独立 GS；首屏 product-category headline 复用 `GS-PROD-CAT-PNL-A`；balance 专题入口对账见 `GS-BAL-OVERVIEW-A` / balance 相关样本。

### I. 显式待确认（Pending）

- Wave 1 书面「禁止首屏」列表与 **当前** `OperationsAnalysisPage.tsx` 实装（仍含 `BusinessConclusion`、`TenorConcentrationPanel`、mock `AlertList`/`CalendarList` 等）的收敛策略：删组件 vs 改文档权威。
- `requested_report_date` 与「默认最新 product-category / balance 日期」的人机交互是否应升级为可点选，并分别与 `PAGE-PROD-CAT-PNL-001`、`PAGE-BALANCE-001` 统一。

## 13.6 PAGE-BOND-001 债券总览（债券分析驾驶舱）

### A. 页面身份

- 页面 ID：`PAGE-BOND-001`
- 页面名称：`债券总览`（导航：`bond-dashboard`）
- 路由：前端 `/bond-dashboard`；后端 `GET /api/bond-dashboard/*`（`backend/app/api/routes/bond_dashboard.py`）
- 页面状态：`active`（`bond_analytics` formal read surface；`result_meta` 经 `formal_result_runtime` 与 `source_surface="bond_analytics"` 一致）
- 依证据：`backend/app/services/bond_dashboard_service.py`（`BOND_ANALYTICS_*` 缓存/规则版本与 envelope）

### B. 业务问题与不回答

- **须回答**：在选定 `report_date` 下，组合市值/久期/票息/风险概览、资产分布、行业与利差结构、期限与收益分布等**只读**结论是什么。
- **不回答**：不替代 `balance-analysis` 会计口径余额真值；不替代 `risk-tensor` 全量风险张量；不在前端重算正式指标（见 `test_no_finance_logic_in_frontend` 对 `bond-dashboard/` 的约束）。

### C. 必有 / 可选 / 禁止 section

- **必有（实装）**：`filter`（`bond-dashboard-report-date`）、`bond-dashboard-conclusion`（由 headline + risk 推导的文案，**analytical/derived UI**，非独立 API）、`HeadlineKpis`、`AssetStructurePie`、`CreditRatingBlocks`、`SpreadTable`、`YieldDistributionBar`、`PortfolioTable`、`MaturityStructureChart`、`IndustryTable`、`RiskIndicatorsPanel`
- **禁止**：无可用 `report_date` 时仍展示上一日业务图；静默忽略 `result_meta.quality_flag` / `fallback_mode`

### D. 时间语义

- `requested_report_date`：页面 `Select` 当前值；初始为 `getBondDashboardDates` 返回的 `report_dates[0]`（`BondDashboardPage.tsx`）。
- `resolved_report_date`：各分请求 URL 中传入的 `report_date` 与/或 `result.report_date`（headline/各 payload 内）。
- `as_of_date`：未列独立字段；**临时**以 `report_date` 为截面语义。
- `generated_at`：各分响应 `result_meta.generated_at`（`bond_dashboard.*` 各 `result_kind`）。

### E. Endpoint / DTO 表

| Endpoint | 用途 | DTO / payload 名（`frontend/src/api/contracts.ts`） |
| --- | --- | --- |
| `GET /api/bond-dashboard/dates` | 可选报告日 | `result.report_dates` + envelope |
| `GET /api/bond-dashboard/headline-kpis?report_date=` | 首屏 KPI 与期次对比 | `BondDashboardHeadlinePayload` |
| `GET /api/bond-dashboard/asset-structure?...` | 资产结构 | `AssetStructurePayload` |
| `GET /api/bond-dashboard/yield-distribution?...` | 收益分布 | `YieldDistributionPayload` |
| `GET /api/bond-dashboard/portfolio-comparison?...` | 组合对比 | `PortfolioComparisonPayload` |
| `GET /api/bond-dashboard/spread-analysis?...` | 利差 | `SpreadAnalysisPayload` |
| `GET /api/bond-dashboard/maturity-structure?...` | 期限 | `MaturityStructurePayload` |
| `GET /api/bond-dashboard/industry-distribution?...` | 行业 | `IndustryDistPayload` |
| `GET /api/bond-dashboard/risk-indicators?...` | 风险指示 | `RiskIndicatorsPayload` |

### F. 指标映射（`metric_id`）

- **不新增** `metric_id` 行；字典未与债券驾驶舱作独立绑定时，以「展示字段」表代替：

| 展示字段 / KPI | 来源 DTO 路径 | `metric_id` |
| --- | --- | --- |
| 总市值/久期/票息/浮盈/DV01/信用利差中值等 | `BondDashboardHeadlinePayload.kpis.*`、prev_kpis | 待字典绑定；未绑定时不自称 `MTR-*` |
| 信用占价比等 | `RiskIndicatorsPayload.credit_ratio` 等 | 同上 |
| 各图 tabular 数据 | `asset-structure` / `industry` / `spread` 等 items | 同上 |

- `weighted_ytm` 与 `weighted_duration` 统一在债券投资范围 `asset_class_std in ('rate', 'credit')` 内按市值加权计算，排除 `other` 分类；`weighted_duration` 指市值加权修正久期，不混入现金流页麦考利久期口径。

### G. 状态与错误

- **Loading**：`datesQuery` 与分块 `useQuery`；`report_date` 为空时不 enabled 子查询。
- **Empty**：`report_dates` 空 → `bond-dashboard-page-state` 提示「暂无可用报告日」；combobox 禁用。
- **Error**：`datesQuery` 错误 → 错误 `Alert`（`bond-dashboard-page-state`）。
- **Stale / fallback**：以后端 `result_meta` 为准；若 `quality_flag`/`fallback_mode` 异常，须向用户可感知（同 §4.2 总规则）。

### H. 测试与黄金样本

- 现有测试锚点：`frontend/src/test/BondDashboardPage.test.tsx`、`tests/test_bond_dashboard_api_contract.py`、`tests/test_bond_dashboard_headlines_contract.py`、`tests/test_bond_analytics_api.py`、`tests/test_result_meta_source_surface_followup.py`
- 黄金样本状态：`GS-BOND-HEADLINE-A` 现已作为 **capture-ready** 页面样本绑定到 `GET /api/bond-dashboard/headline-kpis`，样本目录位于 `tests/golden_samples/GS-BOND-HEADLINE-A/`，并已纳入 `tests/test_golden_samples_capture_ready.py`。该样本冻结的是 bond-dashboard 首屏 headline DTO 真值与空态行为；Headline / 风险卡与正式 `MTR-*` 的字典级绑定仍见 `docs/metric_dictionary.md` **GAP-BOND-DASH-***，本次样本冻结**不**自动批准新的字典级 metric 映射。

## 13.6.1 PAGE-BOND-ANALYSIS-001 债券分析工作台

### A. 页面身份

- 页面 ID：`PAGE-BOND-ANALYSIS-001`
- 页面名称：`债券分析`
- 路由：前端 `/bond-analysis`；别名 `/bond-analytics-advanced` 归并到该路由。
- 页面状态：`candidate`。本页展示 action-attribution、组合读面、风险监控和下钻复核入口；`formal_use_allowed=false` 的边界必须可见，不能借用 `PAGE-BOND-001` 或 `GS-BOND-HEADLINE-A` 认证本页。

### B. 业务问题与不回答

- **须回答**：在选定报告日和期间下，债券 action-attribution DTO、候选固定收益风险/收益读面、下钻入口和可用 `result_meta` 证据是什么。
- **不回答**：不批准固定收益公式，不替代 formal risk tensor、bond-dashboard headline、PnL 或人工审计闭环；不产生交易指令或 owner approval。

### C. 必有 / 禁止

- **必有**：`bond-analysis-overview`、`bond-analysis-toolbar`、action-attribution 读面、候选标签、`result_meta`/source/version/run_id 证据、owner approval pending 状态。
- **禁止**：把 `/bond-dashboard` headline 样本、`PAGE-BOND-001`、`GS-BOND-HEADLINE-A` 或 `MTR-BOND-001`~`MTR-BOND-004` 复用为 `/bond-analysis` certification。

### D. 时间语义

- `requested_report_date`：页面选择的 report date。
- `resolved_report_date`：以后端 action-attribution payload 内报告日和 `result_meta` 为准。
- `period_type`：当前样本冻结 `MoM`；其他期间需保持候选/待审边界。

### E. Endpoint / DTO 表

| Endpoint | 用途 | DTO/Schema | 口径 |
| --- | --- | --- | --- |
| `GET /api/bond-analytics/action-attribution` | action-attribution 页面 DTO 与候选归因读面 | `BondActionAttributionPayload` | candidate / `formal_use_allowed=false` |
| `GET /api/bond-analytics/dates` | 报告日选择 | `BondAnalyticsDatesPayload` | source metadata |
| `GET /api/bond-analytics/top-holdings` | 重仓券/深钻入口辅助读面 | `BondTopHoldingsPayload` | analytical / candidate |

### F. 指标映射

- `MTR-BOND-ACT-001`~`MTR-BOND-ACT-006` 仍为 `candidate`、`pending_confirmation=true`，并绑定 `GS-BOND-ANALYSIS-ACTION-ATTR-A` 的页面 DTO 样本边界。
- 本页不新增 fixed-income formula approval；不把 `DV01`、duration、KRD、credit-spread、holdings、yield 或 accounting-class 展示值晋升为正式指标。

### G. 状态

- **Loading / Empty / Error**：以页面 query 状态和后端 envelope 为准，空态不得隐藏候选边界。
- **Stale / fallback**：以后端 `result_meta.quality_flag`、`fallback_mode`、`tables_used`、`source_version` 和 warning 文案为准。

### H. 测试与黄金样本

- 黄金样本：`GS-BOND-ANALYSIS-ACTION-ATTR-A`，只冻结 `GET /api/bond-analytics/action-attribution` 页面 DTO；状态为 capture-ready pending approval。
- 测试锚点：`tests/test_golden_samples_capture_ready.py`、`tests/test_bond_analysis_business_owner_approval_status.py`、`frontend/src/test/BondAnalyticsView.test.tsx`、`tests/test_live_route_page_contract_completeness.py`。

## 13.7 PAGE-POS-001 持仓

### A. 页面身份

- 页面 ID：`PAGE-POS-001`
- 页面名称：`持仓`（`PositionsView`）
- 路由：前端 `/positions?report_date=` 可选；后端 `GET /api/positions/*`（`backend/app/api/routes/positions.py`）
- 页面状态：`active`（`positions_service` 使用 `build_formal_result_envelope` + `result_kind` 形如 `positions.bonds.*` / `positions.interbank.*` 等，见 `tests/test_positions_api_contract.py`）
- 报告日来源：页面**复用** `getBalanceAnalysisDates()` 的 `report_dates` 作为默认可选日（与 `bond-dashboard` 自有 dates 源不同，**双源**）

### B. 业务问题与不回答

- **须回答**：在选定范围与类型下，债券/同业持仓列表、对手方与行业评级分布、客户明细等快照是什么。
- **不回答**：不提供跨页 formal PnL 解释；不替代 `product-category-pnl`；不在前端重算规模指标。

### C. 必有 / 禁止

- **必有**：`positions-page`、tab（债券/同业）、`report_date` 选择、与 tab 关连的列表与分布卡片、对手机构/客户 drilldown（`CustomerDetailModal` 等，见 `tests/CustomerDetailModal.test.tsx`）
- **禁止**：`report_date` 未选时发列表请求；静默吞掉 422/空 envelope

### D. 时间语义

- `requested_report_date`：URL `report_date` 或用户选择，或 balance `report_dates[0]`
- `resolved_report_date`：服务端在 `sub_types`/`product_types` 等接口内 `_resolve_report_date`（`positions_service`）及列表 `report_date` 参数
- `as_of_date`：无统一 outward 字段
- 对手方/统计 `start_date`/`end_date`：由页面本地 range 与 `reportDate` 派生，**区间语义** 与单点 `report_date` 不同

### E. Endpoint / DTO 表

| Endpoint | 用途 | DTO/Schema |
| --- | --- | --- |
| `GET /api/positions/bonds/sub_types` | 债券子类型 | `SubTypesResponse` 类（envelope `positions.bonds.sub_types`） |
| `GET /api/positions/bonds` | 债券分页列表 | `BondPositionsPageResponse` |
| `GET /api/positions/counterparty/bonds` | 对手方债券 | `CounterpartyStatsResponse` |
| `GET /api/positions/interbank/product_types` | 同业产品类型 | `ProductTypesResponse` |
| `GET /api/positions/interbank` | 同业列表 | `InterbankPositionsPageResponse` |
| `GET /api/positions/counterparty/interbank/split` | 同业对手方拆分 | `InterbankCounterpartySplitResponse` |
| `GET /api/positions/stats/rating` | 评级分布 | `RatingStatsResponse` |
| `GET /api/positions/stats/industry` | 行业分布 | `IndustryStatsResponse` |
| `GET /api/positions/customer/details` | 客户明细 | `CustomerBondDetailsResponse` |
| `GET /api/positions/customer/trend` | 客户趋势 | `CustomerBalanceTrendResponse` |
| 余额日期（页面初始化） | `getBalanceAnalysisDates` → 既有 balance 契约 | 同 `PAGE-BALANCE-001` |

### F. 指标映射

- 不声明新 `metric_id`；表头金额/张数/评级等以 positions schema 与列为准。

### G. 状态

- **Loading/Empty/Error**：`useQuery` + `Spin`/表格空态；`retry: false` 与 balance dates 拉取失败级联
- **Stale / fallback**：以各 `result_meta` 与行内 lineage 为准

### H. 测试锚点

- `data-testid`：`positions-page`、`positions-page-title`；`RouteRegistry` 对 `/positions` 路由

## 13.9 PAGE-BOND-DESK-001 单券交易分析台

### A. 页面身份

- 页面 ID：`PAGE-BOND-DESK-001`
- 页面名称：`单券交易分析台`
- 路由：前端 `/bond-trading-desk?bond_code=&report_date=`；**导航默认 hidden**（由重仓券/持仓深钻进入，见 `navigation.ts` `navigationVisibility: "hidden"`）
- 页面状态：`active-read-compose`（只读拼装，无独立单券 formal endpoint）
- 设计锚点：`docs/superpowers/specs/2026-06-10-bond-trading-desk-design.md`

### B. 业务问题与不回答

- **须回答**：在选定 `bond_code` 与 `report_date` 下，本券在组合中的身份、市值/久期/YTM/权重/利差（若列表命中）及持仓变动（若命中）是什么；数据从哪条只读链路拼来。
- **不回答**：不提供买卖指令、约束红绿灯、盘口报价、相似券打分、情景压力数值；不在前端重算正式金融指标；不将组合级结论冒充单券交易建议。

### C. 必有 / 禁止 section

- **必有**：`bond-trading-desk-page`、`bond-trading-desk-identity`、`bond-trading-desk-conclusion`、`bond-trading-desk-metrics`、`bond-trading-desk-gaps`、`bond-trading-desk-decision-rail`、`report_date` 选择、`bond_code` 输入或 URL 同步
- **禁止**：无 `bond_code` 时假装有单券结论；静默隐藏 `api_pending` 模块；用 mock 盘口/约束表冒充正式读面

### D. 时间语义

- `requested_report_date`：URL `report_date` 或 `getBondAnalyticsDates` 默认首项
- `resolved_report_date`：各拼装请求 URL 中的 `report_date` 与各 payload 内 `report_date`
- `bond_code`：URL `bond_code`（必填）；与 `instrument_code` / `bond_code` 字段大小写无关 trim 后匹配

### E. Endpoint / DTO 表（拼装源，非单券专用）

| Endpoint | 用途 | DTO |
| --- | --- | --- |
| `GET /api/bond-analytics/dates` | 报告日 | `BondAnalyticsDatesPayload` |
| `GET /api/bond-analytics/top-holdings?top_n=`（≤500） | 重仓券命中 | `BondTopHoldingsPayload` / `BondTopHoldingItem` |
| `GET /api/positions/bonds?page_size=`（≤500） | 持仓列表命中 | `BondPositionItem` |
| `GET /api/credit-spread-analysis/detail` | 利差行命中 | `CreditSpreadDetailBondRow` |
| `GET /api/bond-analytics/position-changes` | 变动行命中 | `BondPositionChangesPayload` |

**缺口（须 UI 标注，不得前端补算）：** 单券 profile API、盘口、约束校验、相似券、情景压力、组合冲击专用 DTO。

### F. 指标映射

- 不新增 `metric_id`；展示字段仅透传上述 DTO 列（市值、YTM、修正久期、权重、信用利差等），未命中列显示「待返回」或空态文案。

### G. 状态

- **Loading**：dates 与拼装查询并行；`bond_code` 空时不 enabled 拼装查询
- **Empty**：`bond_code` 空 → 引导输入；拼装未命中 → `bond-trading-desk-empty` 说明查找范围（top-holdings + positions 前 500）
- **Error**：各 query 错误须在页面级 `Alert` 可见，不覆盖首屏为加载中
- **Stale / fallback**：以各 `result_meta` 为准；拼装源不一致时结论须注明 `coverageSource`

### H. 测试锚点

- `frontend/src/features/bond-trading-desk/lib/bondTradingDeskPageModel.test.ts`
- `frontend/src/test/BondTradingDeskPage.test.tsx`
- 深钻：`TopHoldingsView` 行链至 `/bond-trading-desk?bond_code=&report_date=`

## 13.8 PAGE-MKT-001 市场数据

### A. 页面身份

- 页面 ID：`PAGE-MKT-001`
- 页面名称：`市场数据`
- 路由：前端 `/market-data`；别名重定向见 `frontend/src/router/routes.tsx`（`/market`→`/market-data` 等，见 `RouteRegistry.test.tsx`）
- 页面状态：`mixed-source`（**formal 片段**：`GET /ui/market-data/rates`（`getMarketDataRates` / 前端 `formalRatesQuery`）驱动利率主表的 formal basis 片段；`RateQuoteTable` / `MoneyMarketTable` 在序列缺失时仅展示 `emptyReason`，不再补静态 demo 行情；`BondFuturesTable` / `BondTradeDetail` / `CreditBondTradesTable` 目前为故意保留的 `source-pending` 终端面板。**preview/analytical**：Choice 宏观目录/最新点、vendor、外汇分析 `getFxAnalytical`、结构化代理 `ncd-funding-proxy`、`api/macro-bond-linkage`、**Livermore**（`/ui/market-data/livermore/*`，门控/板块/候选/风险退出等，均为 analytical）。与 `DOCUMENT_AUTHORITY.md` 中 **market-data preview/vendor/analytical surface** 的排除/警示语义一致：页内须标注 `basis` 与 `formal_use_allowed` 语义，不得整页称 formal cutover 真值面）

### B. 业务问题与不回答

- **须回答**：当前可得的利率/货基/信用成交/新闻与汇率覆盖、**refresh tier** 与 `result_meta` 所表达的线路质量如何；`macro-bond-linkage` 在选定 `report_date` 下环境/组合摘要是什么。
- **不回答**：不作为 `Phase 2` 全量 formal market 权威；不替代 PnL/余额页；不将 Choice/预览混写为「已晋升正式」。

### C. 必有 section（实装侧锚点，含 analytical-only）

- `market-data-page-title`、**catalog/series 统计**（`market-data-*-count` 等，见 `MarketDataPage.test.tsx`）
- 利率/曲线：rate quote、money market、rate trend、NCD 矩阵、信用成交等 `data-testid` 以 `market-data-` 前缀
- 外汇：本页已挂载 `getFxAnalytical`（**analytical**）；`getFxFormalStatus` 见 §E「实现核对」（domain 具备，本页当前未独立 query）；概览 KPI 另与 `getMarketDataRates` 的 formal 片段协同展示
- `NewsAndCalendar` / 宏观联动（`getMacroBondLinkageAnalysis` 等，**analytical/专题**)
- 运维区：Choice refresh + `getChoiceMacroRefreshStatus`、refresh tier / policy 文案
- 折叠说明中声明 **未暴露** 的 V1 `api/macro` 决策端点不实现（见 `MarketDataPage` 中注释性描述）

### D. 时间语义

- `requested_report_date` / `linkageReportDate`：由页面内状态或 selector 选择（`MarketDataPage` 内 `useState`+macro bond linkage 查询）
- `resolved_report_date`：以各 API 结果字段（如 `MacroBondLinkagePayload` 内含 report、或 `ChoiceMacroLatestPoint.trade_date` 等）为准
- `generated_at`：各 `result_meta.generated_at`

### E. Endpoint / DTO 表

| Client 方法 / Endpoint | 用途 | 备注 |
| --- | --- | --- |
| `getMacroFoundation()` | `GET /ui/preview/macro-foundation` | catalog/preview，**analytical** |
| `getChoiceMacroLatest()` | `GET /ui/macro/choice-series/latest` | 最新点 + `recent_points` |
| `getFxFormalStatus()` | `GET /ui/market-data/fx/formal-status` | **formal 状态表**（domain client 具备；**本页当前未挂载 query**，见上「实现核对」） |
| `getFxAnalytical()` | `GET /ui/market-data/fx/analytical` | **analytical** |
| `getNcdFundingProxy()` | `GET /ui/market-data/ncd-funding-proxy` | 结构化代理 |
| `getMacroBondLinkageAnalysis` | `GET /api/macro-bond-linkage/analysis?report_date=` | 债券-宏观联动 **analytical** 读面 |
| `getChoiceMacroRefreshStatus` / refresh POST | vendor 运维 | 非主值 |

> **实现核对（仓库当前 `MarketDataPage.tsx`）**：本页已挂载查询的上表方法为 `getMacroFoundation`、`getChoiceMacroLatest`、`getFxFormalStatus`、`getFxAnalytical`、`getNcdFundingProxy`、`getMacroBondLinkageAnalysis`、`getChoiceMacroRefreshStatus`（及刷新 POST）、`getMarketDataRates`、`getLivermoreStrategy`（Livermore 展开后 `enabled`）。

### F. 指标映射

- 不添加 `metric_id`；NCD/利差等展示为 vendor + 合约字段。FX formal rows 不自动等同于 `MTR-BAL-105` 等汇率口径（跨页引用须在证据链中说明）。

### G. 状态

- 测试约定：`market-data-*` 系列 testid 对 catalog/stable/fallback/missing/result_meta 的可见性（`MarketDataPage.test.tsx`）
- **Error**：Async/polling 与 vendor 失败（含 `424` permission 等）须可感知

### H. 测试锚点

- `frontend/src/test/MarketDataPage.test.tsx`、`ApiClient.test.ts`（端点 URL 拼写）、`RouteRegistry.test.tsx`

### H.1 Hero filter strip（前端读面筛选，不触发新 API）

- **控件锚点**：`market-data-filter-strip`、`market-data-active-filter-summary`（`MarketDataHeroSection.tsx`）。
- **筛选维度**（均为**前端本地过滤**，不改变 `useQuery` 参数或后端请求）：
  - **国债 / 国开**（`curveFilter`）：过滤 `RateQuoteTable`、Market Tape、首屏终端 KPI；`both` 表示不过滤曲线品种。
  - **来源**（`sourceFilter`）：过滤利率主表、资金表、Tape、KPI；分类规则见下。
  - **中票 / 城投**（`creditSegment`）：仅过滤宏观深度「信用利差」Tab 的 `credit_spread` 联动槽位（`buildSpreadSlots`）；按 `MacroBondLinkageTopCorrelation.series_name` 是否包含「中票」或「城投」匹配；`both` 表示不过滤信用分段。
- **来源分类规则**（`classifyTerminalSource` / `matchesSourceFilter`，`marketDataTerminalModel.ts`）：
  - 优先读取 catalog `vendor_name`（`buildCatalogVendorNameMap(catalog)`，按 `series_id` 对齐）；当 `vendor_name=choice` 时归为 **Choice**。
  - 否则读取每行/API 点上的 `source_version` 与 `vendor_version`，拼接为小写字符串；若包含子串 `choice` → **Choice**；否则 → **内部**（含 `public_*`、`fred`、`boc` 等中性 lineage）。
  - 前端**不得**据此重算利率/利差数值，仅决定行是否展示。
- **Fragment golden**（`GS-MKT-RATES-FRAGMENT-A`）：冻结 `GET /ui/market-data/rates` formal 片段；不关闭 `GAP-MKT-DATA` 全页缺口。回归：`marketDataRatesFragmentGolden.test.ts`、`tests/test_golden_samples_capture_ready.py`。
- **生效摘要文案**：`buildMarketDataActiveFilterSummary` 将非默认筛选拼为 `国债 + Choice` 等形式；全部为默认时显示 `全部`。
- **Tab 联动**：当 `creditSegment` 为 `mtn` 或 `urban` 时，页面自动切换宏观深度 Tab 至 **信用利差**（`macroDepthTab=spreads`）；改回 `both` 时不强制回切曲线 Tab。
- **空态**：筛选后无匹配行时，利率/资金表展示 `market-data-*-filter-empty`，不补 demo 数。
- **回归锚点**：`frontend/src/features/market-data/lib/marketDataTerminalModel.test.ts`、`frontend/src/test/MarketDataPage.test.tsx`（`updates shell filter state locally…`）。

### H.2 首屏收口与延迟加载（Route A）

- **Livermore**：`market-data-livermore-collapse` 默认折叠；`getLivermoreStrategy` 仅在用户展开后 `enabled`（`useMarketDataPageData({ livermoreEnabled })`）。展开前 DOM 中不应出现 `market-data-livermore-panel` 正文。
- **宏观深度 Tab**：仅渲染当前 `macroDepthTab` 对应 panel（曲线 / 信用利差 / 压力与情景），非激活 Tab 的 `market-data-macro-tab-*` 不应挂载。
- **查询焦点**：市场页相关 `useQuery` 设置 `refetchOnWindowFocus: false`；`staleTime` 继续沿用 `externalDataQueryOptions`（稳定 date_slice 30 分钟，其余 5 分钟）。
- **壳层**：`WorkbenchShell` 在 `market-data` 路由隐藏市场工作台子导航网格（`isMarketDataTerminalMain`）。
- **布局版本**：`data-layout-rev=2026-06-10g`。
- **回归**：`MarketDataPage.test.tsx`（`defers macro-bond linkage…`、`keeps Livermore deferred…`、`renders only the active macro depth tab panel`）。

### H.4 新数据源接入（Route C）

- **正式外汇**：页面挂载 `getFxFormalStatus()` → `GET /ui/market-data/fx/formal-status`；`market-data-fx-formal-collapse` 默认折叠，展开后展示 `market-data-fx-formal-table`（仅后端行，前端不补算中间价）。
- **与 analytical 分离**：`getFxAnalytical` 仍为分析观察；正式外汇状态单独进入证据轨 `FX formal` 与运维 KPI `market-data-fx-formal-materialized`。
- **仍 source-pending**：国债期货 / 现券成交 / 信用成交无 outward contract；`market-data-source-pending-contract-note` 明示缺口，面板保持 `source-pending` 空态。
- **布局版本**：`data-layout-rev=2026-06-10g`（首屏状态条仅保留利率口径；运维 KPI 与联动 API 懒加载）。
- **回归**：`MarketDataPage.test.tsx`、`marketDataPageModel.test.ts`、`frontend/tests/playwright/market-data-terminal-smoke.spec.mjs`。

### H.3 Blocked formal-use visibility

- If the `/market-data` formal rates fragment returns `result_meta.basis=formal` but `formal_use_allowed=false`, the page must not present it as formal-ready.
- Required user-visible copy: `formal · blocked`, `禁止作为正式口径`, and first-screen status `分析/候选`.
- Current implementation anchors: `frontend/src/features/market-data/pages/marketDataPageModel.ts`, `frontend/src/features/market-data/pages/MarketDataPage.tsx`, `frontend/src/features/market-data/pages/MarketDataHeroSection.tsx`.
- Regression anchors: `frontend/src/test/MarketDataPage.test.tsx` and `frontend/src/features/market-data/pages/marketDataPageModel.test.ts`.
- This visibility rule does not add new `MTR-*` rows, approve full-page formal truth, or create a capture-ready golden sample; `GAP-MKT-DATA` remains in force.

### I. 显式待确认

- 与全仓 `Phase 2` cutover 声明对齐后，本页是否拆分为「formal 子面」+「preview 子应用」的导航或强提示（当前为 **同页 mixed-source**）。

### J. 实施边界与已知 GAP（文档事实，非业务指标定义）

- **`GAP-MKT-DATA`**（与 `docs/metric_dictionary.md` §12.5、`docs/golden_sample_catalog.md` §5.2 一致）：市场页**尚无**本字典可冻结的**全页** formal metric dictionary / capture-ready **golden sample**；当前仅能对 `GET /ui/market-data/rates` 对应的 formal rates 片段做测试与 lineage 核对，页面契约不替代指标字典主表。
- **显示边界**：`RateQuoteTable`、`MoneyMarketTable` 在序列缺失时展示 `emptyReason`，不再补静态 demo 行情；`BondFuturesTable`、`BondTradeDetail`、`CreditBondTradesTable` 为故意保留的 `source-pending` 面板，不渲染示例合约或成交流水（见 `docs/plans/market-workbench-cursor-prompts.md` Cursor 分工说明）。
- **NCD 读面**：`ncd-funding-proxy` 为 **Shibor/资金利率类 proxy**（默认文案与 `payload.proxy_label` 对齐，如 Tushare Shibor funding proxy），**不是**「实际同业存单期限 × 评级」全矩阵真值；页内 `NcdMatrix` 已声明 proxy 语义。
- **Livermore `risk_exit`**：后端 `unsupported_outputs` / `rule_readiness` / `data_gaps` 所描述的门禁为事实链依赖；实现侧依赖 **ACTIVE A 股持仓、成本/入场条、K 线历史等 supplement** 就绪后才会解除 blocked（以前端展示的后端返回为准，本文不展开公式）。
- **`/news-events`**：若按市场工作台方案开放为路由实页，定位为 **analytical `temporary-exception`** 读面，**不是** formal metric 主链页面（与 `AGENTS.md` 占位/临时例外语义一致）。

## 13.9 PAGE-MACRO-TOOLKIT-001 宏观工具

### A. 页面身份

- 页面 ID：`PAGE-MACRO-TOOLKIT-001`
- 页面名称：`宏观工具`
- 路由：前端 `/macro-toolkit`（`frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`）
- 页面状态：`candidate tooling surface`。本页是宏观分析与脚本工具入口，允许展示分析/候选/运维证据，但 **不** 是正式宏观指标页，也不创建正式投资信号。
- 页面边界锚点：`MacroToolkitContractBoundary` 必须在正常页与错误页可见，并展示 `formal_use_allowed=false` 时的 `非正式口径` 文案。

### B. 业务问题与不回答

- **须回答**：当前宏观工具的核心判断、证据覆盖、市场踩踏风险、M7-M16 功能结果、策略供数状态、脚本注册表与脚本运行结果是否可读、可追踪、可显式降级。
- **不回答**：
  - 不替代 `market-data` 的利率/宏观序列读面。
  - 不替代 `stock-analysis` 或任何正式投资决策页。
  - 不把脚本输出、样例策略、Choice/Tushare vendor 读面或刷新状态升格为 governed macro metric truth。

### C. 必有 section / 组件

| Section / component | 状态 | 备注 |
| --- | --- | --- |
| `macro-toolkit-tailwind-cockpit` | live | 首屏展示分析日期、投研观点、证据覆盖、能力闭环与合同边界 |
| `DataStatusStrip` + `MacroToolkitContractBoundary` | live | 显示 `result_meta.basis`、`quality_flag`、`result_kind`、`rule_version`、`formal_use_allowed=false` |
| 核心信号 / 市场踩踏风险 | live | 只展示后端宏观模块返回的分析结果；缺失时须显示空/失败态 |
| 指标矩阵 / 功能结果 | live | M7-M16 的输入证据、缺失输入和降级状态须可见 |
| 策略展示 / 策略供数闭环 | live | 显示真实链路、降级、样例数量、股票历史日期、因子快照日期与 source/version/run_id |
| CFFEX 席位状态 / 股票数据刷新 | operational | 显式触发的刷新动作；须由后端权限与审计测试约束 |
| 脚本注册表 / 脚本产物 / 运行结果 | operational | 只作为工具运行证据；不得作为正式指标或自动交易建议 |

### D. 时间语义

- `requested_report_date`：本页没有独立日期控件；核心分析由后端 `MacroToolkitAnalysisPayload.as_of_date` 与各源状态共同决定。
- `resolved_report_date`：以各返回 payload 内的 `as_of_date`、`latest_trade_date`、`reference_date`、`factor_snapshot.as_of_date` 为准；不同区块不得被合并成一个全页日期。
- `generated_at`：来自各 `ApiEnvelope.result_meta.generated_at`。
- 刷新动作产生的 `run_id`、`started_at`、`finished_at` 仅用于运维追踪，不构成页面主读数日期。

### E. Endpoint / DTO 表

| Client 方法 / Endpoint | 用途 | DTO/Schema | 口径 |
| --- | --- | --- | --- |
| `getMacroToolkitAnalysis({ detail: "core" })` -> `GET /ui/macro/toolkit/analysis?detail=core` | 首屏核心分析、风险、指标、能力结果、runtime 状态 | `MacroToolkitAnalysisPayload` | analytical / tooling |
| `getMacroToolkitAnalysis({ detail })` -> `GET /ui/macro/toolkit/analysis?detail=core\|full` | 核心/完整分析、风险、指标、能力结果、runtime 状态 | `MacroToolkitAnalysisPayload` | analytical / tooling |
| `getMacroToolkitAnalysis({ detail: "full", historyLimit })` -> `GET /ui/macro/toolkit/analysis?detail=full&history_limit=430` | 完整分析下的 Crisis Score 历史序列（`score_history`） | `MacroToolkitAnalysisPayload.capability_results[crisis_score_cn].result.score_history` | analytical / tooling |
| `getMacroToolkitStrategySummaries()` -> `GET /ui/macro/toolkit/analysis/strategy-summaries` | 策略摘要、真实/降级/样例供数状态 | `MacroToolkitStrategySummariesPayload` | analytical / candidate |
| `getMacroToolkitScripts()` -> `GET /ui/macro/toolkit/scripts` | 脚本注册表、源命中、产物列表 | `MacroToolkitPayload` | tooling |
| `runMacroToolkitScript()` -> `POST /ui/macro/toolkit/scripts/{name}/run` | 显式运行选中脚本 | `MacroToolkitRunResponse` | operational |
| `refreshMacroSourceBackfill()` -> `POST /ui/macro/toolkit/source-backfill/refresh` | Crisis Score / 宏观来源缺口补齐（按 alias 滚动回填） | `MacroToolkitSourceBackfillRefreshResponse` | operational / permission-gated |
| `refreshCffexMemberRank()` -> `POST /ui/macro/toolkit/cffex-member-rank/refresh` | 中金所席位数据刷新 | `MacroToolkitCffexRefreshResponse` | operational / permission-gated |
| `refreshChoiceStock()` -> `POST /ui/macro/toolkit/choice-stock/refresh` | 股票历史与因子快照刷新 | `MacroToolkitChoiceStockRefreshResponse` | operational / permission-gated |
| `getChoiceStockRefreshStatus()` -> `GET /ui/macro/toolkit/choice-stock/refresh-status` | 刷新任务状态 | `MacroToolkitChoiceStockRefreshResponse` | operational |

**分析 detail 语义**

- `detail=core`：首屏快速返回；`runtime_status.deferred_sections` 可能延后策略、完整能力结果与 `data_health` 细项。
- `detail=full`：返回完整能力结果（含 `crisis_score_cn` 组件、`score_history`）与 `data_health` 覆盖/修复项；`history_limit` 默认 430，仅对 full 生效。
- `data_health`：来源覆盖、能力结果 complete/degraded/unavailable 计数与 repair_items；不得在前端重算 Crisis Score。
- `source-backfill/refresh`：仅补齐缺失 alias，不改变 Crisis Score 公式权重。

### F. 指标映射

- 本页不新增 `MTR-MACRO-*`，不新增 `MTR-*`，也不绑定 golden sample。
- `coverage.hit_rate`、脚本数量、策略数量、真实链路数量、股票历史行数、因子快照行数等均为页面状态/运维证据，不能写入正式指标字典。
- 若未来要把某个宏观指标升格为正式指标，必须另行补 metric dictionary 行、单位/精度/null 规则、source lineage、sample 或明确 `pending_confirmation=true` 的 candidate 决策；本页合同不授权该升格。

### G. 状态规则

- **Loading**：核心分析可以先返回；`runtime_status.deferred_sections` 须让策略展示等延后区块可见。
- **Empty**：无脚本、无策略、无指标时必须显示空态，不得补静态假数据。
- **Stale / fallback**：遵循 `result_meta.quality_flag`、`fallback_mode`、各源最新日期与 warnings；供数闭环必须保留样例/降级/真实链路区分。
- **Error**：分析、脚本或策略读取失败时，错误页或区块必须同时显示合同边界和失败来源。
- **Permission**：刷新和运行入口必须依赖后端权限/授权测试；前端不单独声明授权成功。

### H. 测试与验证锚点

- 前端页面：`frontend/src/test/MacroToolkitPage.test.tsx`
- 导航成熟度：`frontend/src/test/navigation.test.ts`、`tests/test_live_route_page_contract_completeness.py`
- 后端/API/权限：`tests/test_macro_toolkit_scripts.py`
- 债务基线：`npm run debt:audit`
- 浏览器检查：打开 `/macro-toolkit`，核对 `非正式口径`、核心信号、市场踩踏风险、策略供数闭环、脚本注册表和运行结果可见。

### I. 显式待确认

- 是否未来拆分为「只读宏观观察页」与「运维脚本工具页」两个路由。
- 是否将某些宏观序列或策略状态按 candidate metric 登记；当前合同明确不登记。
- 是否允许脚本运行输出进入可下载报告或审计归档；当前仅作为页面运行证据显示。

## 13.10 PAGE-MACRO-OBS-001 宏观观察

### A. 页面身份

- 页面 ID：`PAGE-MACRO-OBS-001`
- 页面名称：`宏观观察`
- 路由：前端 `/macro-observation`（`frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`，`mode="observation"`）
- 页面状态：`candidate tooling surface`。本页只展示宏观分析与策略供数证据，不暴露脚本注册表、执行按钮或刷新动作。
- 页面边界锚点：`macro-observation-readonly-boundary` 必须在正常页和错误页可见，并明确标出 `read-only macro observation`。

### B. 业务问题与不回答

- **须回答**：宏观核心判断、证据覆盖、市场踩踏风险、功能结果、策略供数状态是否可读。
- **不回答**：
  - 不展示脚本注册表、运行结果或任何运行/刷新入口。
  - 不把脚本产物或运维状态升格为正式宏观指标 truth。

### C. 必有 section / 组件

| Section / component | 状态 | 备注 |
| --- | --- | --- |
| `macro-toolkit-tailwind-cockpit` | live | 首屏保留分析日期、投研观点、证据覆盖、能力闭环与合同边界 |
| `MacroToolkitContractBoundary` | live | 仍需展示 `formal_use_allowed=false` 和 result meta |
| `macro-observation-readonly-boundary` | live | 明确只读边界，说明刷新、脚本执行和运维注册表留在 `/macro-toolkit` |
| 核心信号 / 市场踩踏风险 | live | 只读分析证据，不暴露运维操作 |
| 指标矩阵 / 功能结果 | live | 保留分析结果，但不引出脚本工具尾段 |
| 策略展示 / 策略供数闭环 | live | 保留策略证据与供数状态，不展示股票刷新控件 |

### D. 时间语义

- 与 `PAGE-MACRO-TOOLKIT-001` 相同，核心分析和策略供数日期仍以返回 payload 内字段为准。
- 本页不引入独立操作日期或运行日期。

### E. Endpoint / DTO 表

| Client 方法 / Endpoint | 用途 | DTO/Schema | 口径 |
| --- | --- | --- | --- |
| `getMacroToolkitAnalysis()` -> `GET /ui/macro/toolkit/analysis?detail=core` | 核心分析、风险、指标、能力结果、runtime 状态 | `MacroToolkitAnalysisPayload` | analytical / tooling |
| `getMacroToolkitStrategySummaries()` -> `GET /ui/macro/toolkit/analysis/strategy-summaries` | 策略摘要、真实/降级/样例供数状态 | `MacroToolkitStrategySummariesPayload` | analytical / candidate |

### F. 指标映射

- 本页不新增 `MTR-MACRO-*`，不新增 `MTR-*`，也不绑定 golden sample。
- 只读观察页复用工具页的分析证据，但不继承运维动作。

### G. 状态规则

- **Loading**：核心分析和策略供数可先返回，脚本/运维段不渲染。
- **Empty**：无分析时仍保留只读边界。
- **Error**：分析失败时展示合同边界和只读边界。

### H. 测试与验证锚点

- 前端页面：`frontend/src/test/MacroToolkitPage.test.tsx`
- 路由：`frontend/src/test/RouteRegistry.test.tsx`
- 导航成熟度：`frontend/src/test/navigation.test.ts`、`tests/test_live_route_page_contract_completeness.py`
- 债务基线：`npm run debt:audit`

## 14.0 PAGE-LEDGER-PNL-001 Ledger PnL

### A. Page identity

- Page ID: `PAGE-LEDGER-PNL-001`
- Primary front-end route: `/ledger-pnl`
- Status: `active` ledger read surface
- Primary APIs:
  - `GET /api/ledger-pnl/dates`
  - `GET /api/ledger-pnl/data`
  - `GET /api/ledger-pnl/summary`
  - `GET /api/ledger-pnl/analysis`
  - `GET /api/ledger-pnl/monthly-analysis/dates`
  - `GET /api/ledger-pnl/monthly-analysis/workbook`
  - `GET /api/ledger-pnl/candidate-financial-indicators`
  - `GET /api/ledger-pnl/candidate-financial-indicators/period-comparison`
  - `GET /api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail`
  - `GET /api/ledger-pnl/formal-financial-indicators`
  - `GET /api/ledger-pnl/formal-indicator-rule-checks`

### B. Primary business question

- The page answers: what does the ledger/QDB analytical read chain show for the selected report date, and which formal financial indicators are still pending source confirmation?
- The page must keep ledger/QDB analytics separate from formal financial indicator truth.
- It must not present Excel sample values, QDB candidate values, or reconciliation probes as formal values unless a future contract explicitly returns `formal_use_allowed=true`.

### C. Data chain

- Frontend route `/ledger-pnl` consumes ledger PnL read APIs under `/api/ledger-pnl/*`.
- The Ledger page reads the existing analytical monthly workbook only through the Ledger-owned dates/workbook endpoints. They require `ledger_pnl:read`, preserve the source analytical envelope and `formal_use_allowed=false`, and do not expose QDB export, refresh, scenario, or manual-adjustment capabilities.
- `GET /api/ledger-pnl/analysis?date=YYYY-MM-DD&currency=CNX|CNY` returns a backend-computed candidate analysis snapshot for the selected accounting basis. It includes the core/other-`5*`/all bridge, CNX-versus-CNY comparison, ranked account contributors, and comparison with the previous available source report date.
- `GET /api/ledger-pnl/candidate-financial-indicators?report_month=YYYYMM&include_lineage=false&metric_id=` executes the active frozen `qdb-finance-2026-v1.0.1` rule pack against the configured monthly ledger/daily workbook pair. `v1.0.1` re-locks the current 202606 ledger SHA without changing formulas or metric IDs; immutable `v1.0.0` remains available for historical replay. For the exact pinned 202606 rule/source tuple, the payload also returns backend-owned `source_version_impact`: all 186 metrics are compared as canonical Decimal values, numeric changes are reported separately from serialization-only changes, and the evidence has `certification_effect=none`. It is an isolated candidate result and does not modify the formal source-contract endpoint.
- `GET /api/ledger-pnl/candidate-financial-indicators/period-comparison?report_month=YYYYMM` returns the fixed seven-item, backend-computed candidate comparison. It uses exact adjacent calendar months, keeps the complete 186-item replay status separate from the explicitly degraded ledger-only key-metric scope, and never accepts a client-supplied path, comparison month, metric list, or materiality threshold.
- `GET /api/ledger-pnl/formal-financial-indicators?report_month=202603` returns the frozen formal financial indicator source contract.
- `GET /api/ledger-pnl/formal-indicator-rule-checks?report_month=202603` checks the frozen contract without producing new formal metric values.
- Ledger data/summary/analysis routes delegate to `backend/app/services/ledger_pnl_service.py`; candidate financial-indicator routes delegate to their isolated candidate services and do not pass through that ledger fact service.
- The formal financial indicator source contract is built by `backend/app/core_finance/formal_financial_indicators.py`.
- Formal indicator rule checks are built by `backend/app/core_finance/formal_financial_indicator_rules.py` and remain non-formal evidence.

### D. Formal indicator source-contract boundary

| Source status | Page meaning | Display rule |
| --- | --- | --- |
| `formal_pending` | Excel sample has a formal indicator value, but governed production source is not connected | Show as pending; `value` must remain null |
| `candidate_qdb_aligned` | QDB analytical value aligns to the Excel sample within display precision | Show as candidate only; `value` must remain null |
| `needs_reconciliation` | QDB analytical value and Excel sample differ | Show reconciliation gap; `value` must remain null |

- Contract envelope: `result_meta.basis=ledger`, `result_meta.formal_use_allowed=false`.
- Contract values: every source-contract metric uses `value=null`; `system_value` is evidence only, not a formal displayed value.
- Page copy must distinguish `excel_value`, `system_value`, and `value`.

### E. Units, dates, and status

- `report_date` controls ledger data/detail/summary endpoints.
- `report_date` and `currency` also control the selected-basis conclusion, account ranking, and period comparison returned by the analysis endpoint. The previous period is the latest available source report date strictly before the requested date; there is no date fallback for the current period.
- `report_month` controls the formal financial indicator source contract.
- `currency` is an accounting basis, not an additive currency dimension: `CNX=综本`, `CNY=人民币账`.
- Omitted currency and legacy/invalid page query values normalize to `CNX`; the API accepts only `CNX` or `CNY`, and never adds the two overlapping bases.
- `as_of_date` for the source contract is the month-end `report_date` returned by the envelope.
- Stale/fallback/vendor degradation must remain visible through `result_meta`.
- No-data and missing-source states must be explicit; pending formal indicators must not be rendered as zero.
- Ledger data and summary payloads expose `data_status=ready|no_data`. When it is `no_data`, summary cards render `--` even if legacy money placeholders are serialized as zero; the real transport badge must say the API is read-only and the accounting result remains non-formal.

### F. Candidate analysis contract

- The analysis endpoint remains `result_meta.basis=ledger` and `result_meta.formal_use_allowed=false`; its payload uses `metric_status=candidate` and must never be described as formal PnL attribution.
- `core_pnl = sum(monthly_pnl where account prefix in {514, 516, 517})`.
- `all_pnl = sum(monthly_pnl where account prefix is 5*)`.
- `other_5_pnl = all_pnl - core_pnl`. This is an arithmetic remainder across other `5*` ledger accounts, not an approved attribution category.
- Every basis-comparison difference is `CNX - CNY`. CNX and CNY are overlapping accounting bases, so they must not be added; the difference must not be labelled FX PnL.
- `basis_availability.CNX` and `basis_availability.CNY` describe PnL analyzability only. Every basis-comparison row also returns per-metric `availability` and `evidence_rows`; missing metric amounts and differences are `null`, never serialized zero placeholders.
- Positive and negative contributors are ranked from unrounded `Decimal` amounts after grouping by account code within the selected basis. Display rounding must not change rank order.
- Period changes compare the requested source month-end with the previous available source month-end in the same accounting basis. Missing current or previous basis data is explicit and must not be displayed as a genuine zero.
- Bridge, comparison, contributor ranking, and period-change arithmetic are backend-owned. The frontend may format the returned money DTO and map status codes to copy, but must not recompute those amounts.
- The page functional-audit strip consumes the `/analysis` envelope and metadata for candidate status, source, date, basis, and evidence checks. The retired frontend explainability engine must not re-aggregate money DTOs or emit a second driver/ranking conclusion.
- The analysis payload and envelope are validated by strict backend Pydantic response models (`extra=forbid`) before the route response is emitted.
- These derived analysis fields do not create new `MTR-*` entries or change the pending status of `MTR-LPN-001` through `MTR-LPN-003`.

#### F.1 Candidate financial-indicator engine

- The only HTTP source selector is `report_month`; the service resolves `总账对账{YYYYMM}.xlsx` and `日均{YYYYMM}.xlsx` under `settings.product_category_source_dir`. Client-supplied filesystem paths are forbidden. All six parsed source periods must end on that requested month-end; a renamed or stale workbook fails closed with `source_period_mismatch`.
- The contract is fixed to `currency=CNX`, `basis=ledger`, `metric_status=candidate`, and `formal_use_allowed=false`. The page-level CNX/CNY selector never changes this engine's CNX calculation boundary.
- The versioned rule asset expands to 186 unique metric IDs: 57 scale outputs (19 definitions × point/YTD-average/month-average), 75 direct outputs, 19 manual inputs, and 35 derived outputs. All values and lineage amounts are decimal strings; raw source amounts remain yuan and displayed metric values remain 亿元.
- The backend, not React, owns account aggregation, weights, scale/direct/manual/derived evaluation, missing-account substitution, and dependency propagation. A missing referenced account is distinguishable from an observed zero and remains visible in status, reasons, validation, gap, and lineage evidence.
- Every evaluated response returns the fixed 12 controls covering six source periods, CNX-only consumption, ledger identity/duplicates, referenced-account coverage, four scale reconciliations, and independent non-interest reconciliation. Any failed error-severity control produces `calculation_status=error`; the page must block headline values and the metric catalog in that state.
- `include_lineage=false` is the default base read. The page requests `include_lineage=true` with one exact `metric_id` only after a user opens trace detail; frontend code must not reconstruct finance lineage.
- Source SHA-256, rule hash/version, request parameters, manual overrides/references (when supported), and engine-contract version participate in deterministic idempotency. The runtime loader pins approved asset and source hashes separately for immutable `qdb-finance-2026-v1.0.0` and active `qdb-finance-2026-v1.0.1`, rejecting structurally valid byte drift until another rule version is approved. A matched source lock does not grant formal use: validation warnings, manual inputs, account coverage, the formal contract, and owner approval remain independent gates. Locked-sample comparison is a separate visible trust signal and never silently substitutes source files.
- For 202606, both configured source files match the active `v1.0.1` source locks, so the page reports `source_alignment=matched`. This closes only the source-hash check: the known missing-account warning, manual inputs, formal contract, and owner approval remain unresolved, and `formal_use_allowed` stays false.
- Missing source files return `no_data` with explicit source gaps. Structural/security parsing failures return a redacted domain `error`. No-data, error, source mismatch, manual defaults, validation failures, and absent lock configuration must remain visibly distinct. An evaluated source without an approved locked hash is at least `warning`, emits a visible source-hash gap, and cannot be labelled `ready`.
- Every candidate response includes backend-owned `promotion_readiness` contract `promotion-readiness-v1`. Its six ordered checks cover the approved rule asset, source-period/hash evidence, all 12 controls, explicit manual inputs, referenced-account coverage, and frozen-formal-contract registration. The frontend renders the checklist unchanged inside the explicit `治理与补证` view and must not derive or overwrite its status from counts or gaps. The formal-contract check proves registration only; it does not prove that the contract release gate is open.
- The candidate panel separates `经营分析` from `治理与补证`. The pinned 202606 payload opens on analysis only when its source-version-impact status is `numerically_unchanged`; missing, incomplete, or digest-mismatched comparison evidence fails conservatively to the governance view. Analysis shows the backend conclusion, scale/income cards, metric catalog, and version impact; governance contains promotion readiness, dry-run revalidation, source/validation/gap evidence, and the owner worklist. Switching views never recalculates values or changes candidate state.
- `promotion_readiness.status=review_required` means only that the six technical checks have no blocker. It never changes `formal_use_allowed=false`, never substitutes for the frozen formal contract, and still requires finance/data-governance owner approval. `candidate_idempotency_key` binds the checklist to the exact candidate calculation, while `readiness_evidence_key` separately fingerprints the check states, evidence references, formal sample/source/release status, and readiness contract version.
- `promotion_readiness.evidence_pack` is the backend-authored, downloadable `candidate-promotion-evidence-v1` blocker handoff. Its `evidence_pack_key` fingerprints the complete canonical pack other than the key itself, including report/rule/source context, checks, formal registration state, owner requirements, required evidence and actions. The strict payload contract also binds those context fields back to the outer candidate result. It contains no candidate metric values, value-bearing validation samples, or formal values; every owner input remains `awaiting_owner_input` with `submitted_value=null`. Downloading it has `certification_effect=none` and cannot approve, register, or promote a metric.
- The frontend may serialize and download that exact nested object and may expose each check's `evidence_refs`. It must fail closed if the pack is absent or structurally inconsistent, and must not rebuild the pack, infer submitted values, or add an approval/write action.
- The frontend may also render `owner_requirements` as a read-only evidence worklist in the fixed category order source evidence, validation control, manual input, account coverage, formal contract, and business-owner review. Category filtering and clipboard copy operate only on the already-returned requirements; they must not mutate the evidence pack, submit owner values, call a write endpoint, or imply approval. Clipboard failure must direct the user back to the exact JSON download.
- `POST /api/ledger-pnl/candidate-financial-indicators/revalidate?report_month=YYYYMM` is a non-persisted dry run bound to both the current candidate idempotency key and evidence-pack key. The frontend may keep its receipt and candidate result in component memory only; refresh or explicit clear discards it. `evidence_received` means the submitted manual value was applied to a candidate recalculation but its evidence is still unverified. Neither `evidence_received` nor `verified` is approval, persistence, certification, or permission for formal use; every receipt remains `revalidation_effect=none`, `persisted=false`, and `formal_use_allowed=false`.
- The active `v1.0.1` contract resolves the current 202606 source-hash mismatch only by establishing a new pinned rule/source version; it does not recreate the absent historical `v1.0.0` ledger binary or grant formal approval. Canonical Decimal comparison proves that the 186 reference/current metric values are numerically unchanged (`numeric_changed_count=0`); eight raw string differences are trailing-zero serialization only. The evidence still cannot prove that the 11 missing account inputs are zero or approve the 19 manual defaults, so those gates remain blocked rather than being inferred from candidate values or delivery examples.

#### F.2 Candidate financial-indicator period comparison

- The comparison endpoint is isolated from the single-month candidate and revalidation contracts. A historical parse or replay failure cannot change the current candidate idempotency key, promotion evidence pack, or dry-run receipt.
- The response contract is `candidate-financial-indicator-period-comparison-v2`. In addition to the fixed seven rows it returns one backend-owned `net_interest_component_bridge`; clients that still require v1 must fail closed rather than silently dropping the bridge.
- The endpoint fixes seven metrics in contract order: three cumulative income metrics (`income.interest.net`, `income.noninterest.total`, `income.operating.mother_bank`) followed by four month-end point metrics for corporate/retail deposits and loans. All amounts and rates are Decimal strings; amount unit is 亿元 and a rate of `1` means `100%`.
- Point metrics compare the requested month-end with the exact preceding calendar month-end. Cumulative income metrics first recover natural-calendar-month values from three consecutive cumulative observations; January and February use year-reset rules. Missing periods, missing metrics, warning/manual/error status, and real zero remain distinct. A zero previous value permits a delta but returns `change_rate=null` with `rate_reason=zero_denominator`.
- Complete-scope availability requires the exact previous calendar month to replay under the same rule version/hash with all 186 metrics evaluated and no error result. The service never skips to an older month. For 202606, the complete 202605 replay is unavailable because `日均202605.xlsx` lacks the required `微贷` sheet; this missing structure is not converted to zero.
- The separately named `comparison_scope=ledger_only_key_metrics` parses the three main-ledger `综本` periods through the hardened XLSX boundary and evaluates them symmetrically under formula/rule authority `qdb-finance-2026-v1.0.1`. Historical source identity is governed separately by the immutable `qdb-ledger-comparison-source-locks-2026-v1.0.0` asset, limited to this ledger-only comparison and its component detail. Its byte SHA is pinned, its scope is fixed to CNX ending balances on `综本`, and its overlapping 202606 record must equal the v1.0.1 rule evidence. Any duplicate ledger observation or invalid lock asset fails closed. A month absent from the lock asset may produce only `quality_status=degraded_candidate`; a locked mismatch cannot enter the response and never falls back to another month or rule metadata.
- A row is comparable only when every required period has metric status `ok` and a non-null value. Warning, manual-default, missing-account, error, and missing-reference evidence makes the row `not_comparable` with null comparison values. The contract does not return materiality, anomaly, good/bad direction, ranking, or deterministic drivers; `driver_status=unclear` remains fixed.
- The net-interest bridge uses the frozen direct formula components in fixed order and weight: `+ income.interest.loan.total`, `- expense.interest.deposit.total`, `+ income.interest.investment`, and `+ income.interest.interbank_net`. These four values use only the three main-ledger periods; the missing 202605 `微贷` sheet continues to block complete 186-item replay but does not block this ledger-only bridge.
- For each component, the backend recovers the current and previous natural-month values and returns both the component's own change and its signed contribution to net-interest change. The unrounded Decimal contribution total must equal the seven-row `income.interest.net.delta_yi` exactly before `foot_status=passed` and `status=available` may be emitted. Any missing/null/non-`ok` component makes the whole bridge `not_evaluable`; a non-zero reconciliation is surfaced as a failed foot and cannot be displayed as a valid explanation. For 202606, the exact 202604/202605/202606 main-ledger hashes all match the comparison source-lock asset, so an otherwise valid bridge and detail use `standard_candidate`; this status proves source identity plus calculation foot only.
- The bridge is an accounting formula contribution schedule, not a causal attribution. It does not determine whether volume, rate, spread, tenor, product, or business action caused the movement; outer `driver_status=unclear`, candidate/formal boundaries, and certification effect remain unchanged.
- The component-detail endpoint is a lazy, read-only drill-through bound to the exact parent comparison by `report_month`, one of the fixed four bridge `metric_id` values, and `parent_idempotency_key`. A changed parent key returns `stale_parent`; the frontend must close or show the stale state and must not reuse rows from another month, metric, or parent calculation.
- Component detail expands the same frozen direct-rule terms against the three exact main-ledger `综本` periods. For every stable 11-digit CNX account it returns the matched rule term and effective component/net weights, cumulative ending balances in yuan, recovered natural-month values and deltas in 亿元, plus the source workbook name, SHA-256/lock status, sheet, row, account-code cell, and ending-balance cell. The frontend formats these backend-owned Decimal strings but performs no financial arithmetic.
- Account membership must be identical across all three periods. A missing or newly appearing account fails closed; it is never filled with zero. Account totals must independently reconcile current value, previous value, component delta, and signed net-interest contribution to the selected parent bridge row before `status=available` and `foot_status=passed` may expose any account rows. Failed/not-evaluable/stale results expose no explanatory rows or totals.
- The overlapping account `50206000001` follows the frozen rule algebra: it contributes to loan interest with effective weight `-1`, while the interbank component's `502*` and `50206*` terms offset to effective weight `0`. The interbank detail returns that row only as `excluded_offset`; it must not be counted twice or described as an interbank contribution.
- The missing historical `微贷` sheet remains a blocker for complete 186-item replay and the outer complete-scope status. It does not participate in this main-ledger component-detail calculation and therefore must not block an otherwise valid account drill-through. Unlocked historical ledger periods keep the detail at `quality_status=degraded_candidate`; all-locked periods may reach `standard_candidate`, but `formal_use_allowed=false`, `driver_status=unclear`, and `certification_effect=none` remain invariant and the result never becomes formal or certified evidence.
- The page exposes the drill-through only for bridge rows whose outer status is `available` with a passed foot, and renders explicit loading, load failure/retry, stale parent, not-evaluable, failed-foot, and available states. Source-account arithmetic evidence supports audit and follow-up analysis, but remains non-causal: volume, rate, spread, product, and business-owner explanations are still outside this contract.
- The comparison idempotency key binds the contract version, exact three months, complete source/hash evidence, rule hash, full-scope replay evidence, the complete seven-row response, and the complete bridge evidence. `metric_status=candidate`, `formal_use_allowed=false`, and `certification_effect=none` are invariant.
- React consumes backend `current_value_yi`, `previous_value_yi`, `delta_yi`, `change_rate`, component changes, signed contributions, and foot evidence without recomputation. It may format Decimal strings and enforce response-shape/cross-field identity only. The operating-analysis view leads with the comparable/not-comparable count and source warning, then shows the complete-scope gap, compact bridge, and seven-row table. It distinguishes natural-month from month-end comparison, shows unavailable values as `--`, preserves the existing lazy component drill-through, and cancels in-flight reads when the view is unmounted. Loading, transport failure, wrong-month/malformed contract, no-month, bridge-unavailable/failed, partial, and fully unavailable states are explicit.

### G. Candidate metric bindings

- Ledger summary cards have dictionary entries only as candidate display metrics; they remain `pending_confirmation=true` and must not be read as formal PnL, product-category PnL, or approved financial-indicator truth.
- `MTR-LPN-001` -> `LedgerPnlSummaryPayload.ledger_monthly_pnl_core`
- `MTR-LPN-002` -> `LedgerPnlSummaryPayload.ledger_monthly_pnl_all`
- `MTR-LPN-003` -> `LedgerPnlSummaryPayload.ledger_net_assets`
- The bound page is `PAGE-LEDGER-PNL-001`; `bound_sample_id=GS-LEDGER-PNL-SUMMARY-A` as a capture-ready candidate DTO sample. This sample does not approve formal use and `pending_confirmation=true` remains in force for `MTR-LPN-001` through `MTR-LPN-003`.

### H. Tests

- API/source contract: `tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py`.
- Ledger summary/detail: `tests/test_ledger_pnl_service.py`.
- Ledger candidate analysis arithmetic and envelope: `tests/test_ledger_pnl_analysis.py`; `tests/test_ledger_pnl_service.py`.
- Ledger route validation/permission: `tests/test_ledger_pnl_routes.py`.
- Candidate rule/parser/evaluator/service/schema and source-version impact: `tests/test_finance_metric_rule_contract.py`; `tests/test_finance_metric_rule_version_upgrade.py`; `tests/test_finance_metric_xlsx.py`; `tests/test_finance_metric_engine.py`; `tests/test_finance_metric_validations.py`; `tests/test_candidate_financial_indicator_schema.py`; `tests/test_candidate_financial_indicator_service.py`.
- Historical ledger comparison source locks and net-interest capture-ready replay: `tests/test_finance_metric_ledger_comparison_source_locks.py`; `tests/test_candidate_financial_indicator_period_comparison_service.py`; `tests/test_candidate_financial_indicator_component_detail_service.py`; `tests/test_ledger_pnl_net_interest_golden_sample.py`. The dedicated golden test has a non-skipping clean-CI path that executes the production parent/detail calculation chain with an aggregate-preserving synthetic fixture; the compact real capture retains only aggregate, locator and row-digest evidence, while local governed-workbook replay remains an optional additional check.
- Candidate period comparison core/parser/schema/service/route: `tests/test_finance_metric_period_comparison.py`; `tests/test_finance_metric_ledger_only.py`; `tests/test_candidate_financial_indicator_period_comparison_schema.py`; `tests/test_candidate_financial_indicator_period_comparison_service.py`; `tests/test_candidate_financial_indicator_period_comparison_route.py`.
- The frontend 202606 demo fixture keeps the governed 186-ID catalog and dependency topology but contains only deterministic synthetic amounts, hashes, account codes, evidence references, statuses, validations, and gaps. `scripts/capture_candidate_financial_indicator_frontend_fixture.py` uses an explicit output allowlist; `tests/test_candidate_financial_indicator_frontend_fixture.py` guards the synthetic contract, and the production build scans `dist` for captured finance markers. The demo fixture is not a source snapshot, golden sample, or formal approval.
- Accounting-basis URL/client behavior: `frontend/src/test/LedgerPnlCurrencyBasis.test.tsx`; `frontend/src/test/LedgerPnlMockClient.test.ts`.
- Candidate analysis panel and lazy trace behavior: `frontend/src/test/LedgerPnlCandidateFinancialIndicatorsPanel.test.tsx`; `frontend/src/test/LedgerPnlPage.test.tsx`.
- Candidate period-comparison client/model/component: `frontend/src/test/PnlCoreClientPeriodComparison.test.ts`; `frontend/src/test/LedgerPnlCandidatePeriodComparisonModel.test.ts`; `frontend/src/test/LedgerPnlCandidatePeriodComparison.test.tsx`.
- Analysis workbench states and rendering: `frontend/src/test/LedgerPnlAnalysisWorkbench.test.tsx`.
- Route/page-contract completeness: `tests/test_live_route_page_contract_completeness.py`.

## 14.0.1 PAGE-BANK-LEDGER-001 Bank Ledger Dashboard

### A. Page identity and decision boundary

- Page ID: `PAGE-BANK-LEDGER-001`; route: `/bank-ledger-dashboard`.
- Maturity remains `temporary-exception`; this is a candidate ledger read model with `formal_use_allowed=false`.
- The page does not provide formal balance, formal PnL, approved net exposure, alert truth, or business-owner approval.
- The three headline fields have no approved MTR-* binding. `GS-BANK-LEDGER-CLASSIFICATION-A` is a dedicated capture-ready DTO/classification sample with status `captured-awaiting-approval`; it is not metric or owner approval.

### B. Imported snapshot read chain

- `GET /api/ledger/dates`, `GET /api/ledger/dashboard`, `GET /api/ledger/positions`, and `GET /api/ledger/export/positions` read only imported `position_snapshot` batches.
- Runtime reads no longer consume `zqtz_bond_daily_snapshot` and do not read `position_snapshot_agg`.
- `POST /api/ledger/import` plus `GET /api/ledger/import-status` materialize direction and expose batch evidence; succeeded imports invalidate and refetch dates, dashboard, and positions.
- Dashboard data is `{as_of_date, classification_status, classification_rule_version, currency_breakdown}`. `alert_count is removed` because no governed alert source or rule exists.

### C. Currency and classification boundaries

- Currency is canonicalized as `upper(trim(currency))`; blank values are the independent `UNKNOWN` bucket. Buckets are stably sorted and never FX-converted or added across currencies.
- `rv_ledger_classification_v2` is a closed pair allowlist applied at import. `LIABILITY` requires `(发行类债券, 发行类债券)`. `ASSET` requires one of `(银行账户, 持有至到期类资产)`, `(银行账户, 可供出售类资产)`, `(银行账户, 交易性资产)`, `(交易账户, 交易性资产)`, or `(银行账户, 应收投资款项)`. Every other pair is materialized as `UNCLASSIFIED`.
- Runtime reads never recompute direction from category fields. The controlled `ledger_classification_backfill` task can attest only explicitly selected legacy batches after byte-identical source-hash replay proves every `(batch_id, row_no)` standard field, position key, and direction unchanged; live history batches 1-8 were applied on 2026-07-12 under plan digest `1c90458a94f56525d4ee360cd2e7cad6fe79f035508b89355f0fd795fa6f065c`, with a completed receipt and unchanged immutable evidence.
- A current-rule bucket reports `classification_total_row_count`, `unclassified_row_count`, `unclassified_face_amount`, and row-based `classification_coverage_pct`. Asset, liability, and net use only materialized `ASSET`/`LIABILITY`; `UNCLASSIFIED` never contributes.
- `classification_status` is `ready|legacy_unassessed|invalid_materialization`. A legacy-rule batch is `legacy_unassessed`; a current-rule batch containing any direction outside `ASSET|LIABILITY|UNCLASSIFIED` is `invalid_materialization`. Both non-ready states fail closed: all three financial amounts and all assessable quality fields are null (except total row count), with no read-time reclassification.
- Positions and export accept normalized `currency` and `UNCLASSIFIED` direction filters. The row keeps batch ID, row number, position key, both classification fields, source/rule versions, and raw-row evidence through the imported lineage.
- Within each current-rule currency bucket, `net_face_exposure = asset_face_amount - liability_face_amount`; a missing classified side remains null in its headline while net treats only that missing side as zero.

### D. Date, freshness, and fallback semantics

- Exact `requested_as_of_date` uses the latest batch for that date.
- An exact miss uses a past-only fallback: the latest `as_of_date <= requested_as_of_date`, then the latest batch on that date. A request before the earliest snapshot returns no data and never falls forward.
- `requested_as_of_date` and `resolved_as_of_date` remain visible when different. `fallback` and `stale` remain explicit transport/read-model states, not formal freshness approval.

### E. Frontend and trace contract

- The selected currency and direction are URL state. Default currency is `CNY` when present, otherwise the first stable currency; `UNCLASSIFIED` survives query keys, client options, forward/back navigation, positions, and export filters.
- Exactly three KPI cards show only the selected currency and use `<CURRENCY>/1亿`; a separate classification-quality panel shows coverage and unclassified rows/amount and drills into `UNCLASSIFIED` positions.
- Legacy and invalid-materialization batches explicitly explain the failure, render all financial KPI values as `--`, hide UNCLASSIFIED drill evidence, and suppress cached UNCLASSIFIED rows. Net copy states that unclassified rows are excluded for ready batches.
- Metadata preserves `source_version`, `rule_version`, `batch_id`, `stale`, `fallback`, and `no_data`; trace preserves requested/resolved dates, normalized filters, batch ID, position key, and row number.
- No frontend fallback may fabricate amounts, dates, alerts, positions, classifications, quality coverage, or trace evidence.

### F. Formal-truth exclusions and exit conditions

- `PAGE-BALANCE-001` remains formal balance truth; `PAGE-PNL-001` and `PAGE-LEDGER-PNL-001` retain their separate PnL contracts.
- Do not promote these fields to MTR-* rows without metric ownership, dedicated golden evidence, lineage audit, manual review, and owner approval.
- The route remains `temporary-exception`: the historical backfill for live history batches 1-8 was applied with a completed receipt and dedicated golden evidence is now captured, but golden approval, owner approval, authorized real-page UAT, and UNKNOWN remediation remain incomplete; rule attestation and `captured-awaiting-approval` evidence do not release `formal_use_allowed=false`.
- Backfill apply requires explicit repeated batch IDs and source directory, the exact dry-run plan digest, a byte-identical pre-existing backup that is neither the target nor its hard link, an exclusively created prepared/completed receipt, fixed global-writer then Ledger-import lock order, frozen source fingerprints rechecked before the transaction, one all-or-none transaction, and unchanged immutable evidence including `position_snapshot_agg` when present. It changes only the three rule-version columns and never auto-corrects direction.
- The historical alias `GAP-BANK-LEDGER-DASHBOARD-PAGE` remains accepted for trace lookup only.

### G. Verification surfaces

- Backend: `tests/test_ledger_analytics_api.py`, `tests/test_ledger_import_flow.py`, `tests/test_golden_samples_capture_ready.py` (`GS-BANK-LEDGER-CLASSIFICATION-A`).
- Frontend: `frontend/src/test/LedgerDashboardPage.test.tsx`, `frontend/src/test/LedgerDashboardPageModel.test.ts`, `frontend/src/test/LedgerImportClient.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Governance/MCP: `tests/test_governance_doc_contract.py`, `tests/test_project_mcp_servers.py`.
- Owner review: `docs/ledger/bank-ledger-classification-owner-evidence-packet.md`, `docs/ledger/bank-ledger-classification-business-owner-approval-template.md`.
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
- `as_of_date`：按 2026-05-11 decision 1B 不作为独立 outward 字段；不得用 `report_date` 或 `generated_at` 替代
- 禁止静默回落；退化必须可见（见 truth contract §10）

### E. Endpoint / DTO 与正式性边界

| 用途 | Endpoint | 说明 |
| --- | --- | --- |
| 明细/主表 | `GET /ui/pnl/product-category` | `result_meta.basis` 为 `formal` 或受治理 `scenario`；主链见 truth contract §6 |
| 日期 | `GET /ui/pnl/product-category/dates` | 初始化 report_date 列表 |
| 刷新/状态 | refresh 与 refresh-status | 运营态，非主读值真值面 |

- 默认解释：`formal`；`scenario_rate_pct` 等场景字段仅在显式场景载荷下成为主解释（truth contract §6、§9）。

### F. 指标与字段锚点

- P0 headline `metric_id` 主表绑定已经在 `docs/metric_dictionary.md` 中批准；decision 3C 已方向性批准 detail metric 扩展，但 detail 字段在矩阵/编号/字典行/测试落地前仍以 truth contract **field freeze** 为准，禁止在前端重算或推断：
  - 头表：`MTR-PCP-001` -> `result.asset_total.business_net_income`；`MTR-PCP-002` -> `result.liability_total.business_net_income`；`MTR-PCP-003` -> `result.grand_total.business_net_income`
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

### F.1 Decision 3C active detail metric clarification

- 2026-06-04 update: decision 3C detail metrics are active as `MTR-PCP-004`~`MTR-PCP-012`, bound only to `result.rows[].cnx_scale`, `result.rows[].cny_scale`, `result.rows[].foreign_scale`, `result.rows[].cny_ftp`, `result.rows[].foreign_ftp`, `result.rows[].cny_net`, `result.rows[].foreign_net`, `result.rows[].business_net_income`, and `result.rows[].weighted_yield`.
- Active detail ids: `MTR-PCP-004`, `MTR-PCP-005`, `MTR-PCP-006`, `MTR-PCP-007`, `MTR-PCP-008`, `MTR-PCP-009`, `MTR-PCP-010`, `MTR-PCP-011`, `MTR-PCP-012`.
- Row dimensions such as `category_id`, `side`, `view`, and `report_date` remain dimensions, not metrics.
- Scenario payloads remain analytical companion probes unless a future decision explicitly promotes them.

## 14.1 PAGE-AGENT-001 Agent Workbench

### A. Page identity

- Page ID: `PAGE-AGENT-001`
- Primary front-end route: `/agent`
- Status: `active`
- Primary APIs:
  - `POST /api/agent/runs`
  - `GET /api/agent/runs/{run_id}`
  - `POST /api/agent/query` for local/synchronous compatibility paths

### B. Primary business question

- The page answers: what can the governed MOSS agent read, explain, and trace for the current user and selected context?
- It must preserve the boundary between analytical/read-only agent output and formal business metrics.
- It must not present an agent answer as a formal financial result unless `result_meta.formal_use_allowed` explicitly allows it.

### C. Data chain

- Frontend route `frontend/src/features/agent/AgentWorkbenchPage.tsx` builds an `AgentQueryRequest`.
- Managed runs call `POST /api/agent/runs`, then poll `GET /api/agent/runs/{run_id}`.
- Local compatibility calls use `POST /api/agent/query`.
- Backend route `backend/app/api/routes/agent.py` delegates to `backend/app/services/agent_run_service.py` and `backend/app/services/agent_service.py`.
- Responses are `AgentEnvelope` payloads with `answer`, `cards`, `evidence`, `result_meta`, `next_drill`, and optional `suggested_actions`.

### D. Units, dates, and status

- Units are not computed in the page. Numeric cards must display the unit supplied by the returned envelope or the originating governed intent.
- Dates use the request context and the backend `result_meta.generated_at`; page context dates remain filters, not independent truth.
- Empty state: no answer/cards means show an empty conversation state, not synthetic financial numbers.
- Failure state: disabled provider, rejected request, failed run, or forbidden run ownership must be visible to the user.
- Stale/fallback state: `quality_flag != ok`, `fallback_mode != none`, or vendor degradation must remain visible through evidence/result metadata.

### E. Tests

- Frontend: `frontend/src/test/AgentWorkbenchPage.test.tsx`, `frontend/src/test/AgentPlaceholderPage.test.tsx`, `frontend/src/test/RouteRegistry.test.tsx`.
- Backend: `tests/test_agent_api_contract.py`, `tests/test_agent_enabled_path_smoke.py`, `tests/test_agent_runs_api.py`, `tests/test_agent_intent_routing.py`.

## 14.2 PAGE-BAL-MOVE-001 Balance Movement Analysis

### A. Page identity

- Page ID: `PAGE-BAL-MOVE-001`
- Primary front-end route: `/balance-movement-analysis`
- Status: `active`
- Primary APIs:
  - `GET /ui/balance-movement-analysis/dates`
  - `GET /ui/balance-movement-analysis`
  - `POST /ui/balance-movement-analysis/refresh`

### B. Primary business question

- The page answers: what changed in asset, liability, and net balance between reporting periods, and which accounting or business dimensions explain the movement?
- It must separate accounting basis movement, business category movement, structure migration, maturity structure, and concentration views.
- It must not replace `PAGE-BALANCE-001` formal balance truth; it explains movement for selected report dates and currency basis.

### C. Data chain

- Frontend page `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx` reads dates through `client.getBalanceMovementDates`.
- The selected `report_date` and `currency_basis` call `client.getBalanceMovementAnalysis`.
- Domain client `frontend/src/api/balanceMovementClient.ts` maps the UI route to the `/ui/balance-movement-analysis*` endpoints.
- Backend route `backend/app/api/routes/accounting_asset_movement.py` returns the governed balance movement envelope and refresh entrypoint.

### D. Units, dates, and status

- Amount fields are displayed in yuan-derived units as provided by the backend model; page-level summaries convert to visible business units only for presentation.
- `requested_report_date` is the selected route/query value. `resolved_report_date` is the backend result date returned by the detail payload.
- `currency_basis` must stay visible when it affects amounts.
- Empty state: no report dates or no rows must show an explicit no-data state.
- Failure state: date load/detail load/refresh failure must show a user-visible error and must not backfill with demo rows.
- Stale/fallback state: `result_meta.quality_flag`, `fallback_mode`, source/version, and refresh status remain part of the governance line.

### E. Metric bindings

| Page display item | `metric_id` | Source field |
| --- | --- | --- |
| Previous balance total | `MTR-BMV-001` | `summary.previous_balance_total` |
| Current balance total | `MTR-BMV-002` | `summary.current_balance_total` |
| Balance change total | `MTR-BMV-003` | `summary.balance_change_total` |
| Reconciliation diff total | `MTR-BMV-004` | `summary.reconciliation_diff_total` |

### F. Tests

- Frontend: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`, `frontend/src/test/RouteRegistry.test.tsx`.
- Backend: `tests/test_accounting_asset_movement_api.py`, `tests/test_result_meta_on_all_ui_endpoints.py`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.3 PAGE-LIAB-ANALYTICS-001 Liability Analytics

### A. Page identity

- Page ID: `PAGE-LIAB-ANALYTICS-001`
- Primary front-end route: `/liability-analytics`
- Status: `active`
- Primary APIs:
  - `GET /ui/liability/risk-buckets`
  - `GET /ui/liability/yield-metrics`
  - `GET /ui/liability/yield-by-period`
  - `GET /ui/liability/counterparty`
  - `GET /ui/liability/business-context`
  - `GET /ui/liability/cockpit-warnings`
  - `GET /ui/liability/contribution-split`

### B. Primary business question

- The page answers: how are funding liabilities structured, concentrated, and priced, and what pressure do they place on NIM, liquidity, and near-term maturity risk?
- It combines daily liability analysis with monthly average-balance views.
- It must not treat reserved compatibility endpoints as formal truth, and it must surface any synthetic or derived section boundary.

### C. Data chain

- Frontend page `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` initializes report dates from balance-analysis dates.
- Daily view calls liability risk, yield, counterparty, knowledge, warning, and contribution endpoints.
- Monthly view calls liabilities monthly and liability average-balance monthly endpoints through the API client.
- Backend route `backend/app/api/routes/liability_analytics.py` delegates to liability analytics and liability knowledge services.
- Frontend adapters in `frontend/src/features/liability-analytics/adapters/` shape counterparty and section-state view models.

### D. Units, dates, and status

- Amounts are displayed as yuan-derived business units such as yi yuan after explicit frontend presentation conversion; source numeric fields remain backend-provided values.
- Yield, liability cost, market liability cost, NIM, and spread values must preserve percent/bp semantics from backend numeric payloads.
- `requested_report_date` is the selected report date. Monthly mode uses selected year/month and average daily balance semantics.
- Empty state: missing report dates, missing liability rows, or missing monthly rows must show no-data states.
- Failure state: date load, daily core query, monthly query, and knowledge-query failures must be visible and retryable where supported.
- Stale/fallback state: quality/fallback/vendor metadata and synthetic section notes must remain visible; the page may explain derived sections but may not hide pending metric definitions.

### E. Metric bindings

These bindings are analytical compatibility bindings, not formal balance/PnL truth. The page must keep result metadata visible and must not hide synthetic or derived section boundaries.

| Page display item | `metric_id` | Source field |
| --- | --- | --- |
| Daily liability total | `MTR-LIAB-001` | `counterparty.total_value` / `risk_buckets.liabilities_structure[].amount` |
| Daily liability cost | `MTR-LIAB-002` | `yield_metrics.kpi.liability_cost` |
| Daily NIM | `MTR-LIAB-003` | `yield_metrics.kpi.nim` |
| One-year maturity pressure | `MTR-LIAB-004` | `risk_buckets.liabilities_term_buckets[]` <= 1Y bucket |
| Top counterparty share | `MTR-LIAB-005` | `counterparty.top_10[0].value / counterparty.total_value` |
| Monthly average total liabilities | `MTR-LIAB-006` | `liabilities_monthly.months[].avg_total_liabilities` |
| Monthly average liability cost | `MTR-LIAB-007` | `liabilities_monthly.months[].avg_liability_cost` |

### F. Tests

- Frontend: `frontend/src/test/LiabilityAnalyticsPage.test.tsx`, `frontend/src/test/RouteRegistry.test.tsx`, `frontend/src/features/liability-analytics/adapters/liabilityAdapter.test.ts`.
- Backend: `tests/test_result_meta_on_all_ui_endpoints.py` and liability analytics route/service tests where present.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.4 PAGE-CUBE-QUERY-001 Cube Query

### A. Page identity

- Page ID: `PAGE-CUBE-QUERY-001`
- Primary front-end route: `/cube-query`
- Status: `active candidate query surface`
- Primary APIs:
  - `POST /api/cube/query`
  - `GET /api/cube/dimensions/{fact_table}`

### B. Primary business question

- The page answers: for an allowed fact table, what grouped rows result from the selected dimensions, measures, filters, and drill path?
- It is a query tool surface. It must not create a new page-level KPI, metric definition, or formal business conclusion outside the returned `result_meta`.
- Formal semantics apply only to backend-approved fact tables and response metadata; unsupported tables, dimensions, or measures must fail closed with visible errors.

### C. Data chain

- Frontend page `frontend/src/features/cube-query/pages/CubeQueryPage.tsx` builds a `CubeQueryRequest`.
- Frontend client `frontend/src/api/cubeClient.ts` sends `POST /api/cube/query`.
- Backend route `backend/app/api/routes/cube_query.py` delegates query execution to the analytical bridge and dimensions lookup to `CubeQueryService`.
- The response is `CubeQueryResult` with rows, columns, summary, drill path, and `result_meta`.

### D. Units, dates, and status

- Units and date semantics come from the selected fact table and backend query response; the frontend must not reinterpret measure units.
- Empty result sets must be rendered as query results or explicit no-data states, not as demo rows.
- Invalid table, dimension, measure, filter, or unavailable storage states must surface as user-visible query errors.
- The page must keep result metadata visible enough for operators to distinguish formal, analytical, stale, fallback, and quality states.

### E. Metric bindings

- None. This page is a candidate query surface and has no standalone `MTR-*` binding.
- Any formal-use claim is scoped to the `result_meta` returned for the specific query.

### F. Tests

- Frontend: `frontend/src/test/CubeQueryPage.test.tsx`, `frontend/src/test/RouteRegistry.test.tsx`.
- Backend: `tests/test_cube_query_api.py`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.5 PAGE-PORTFOLIO-HOME-001 Portfolio Workbench Home

### A. Page identity

- Page ID: `PAGE-PORTFOLIO-HOME-001`
- Primary front-end route: `/portfolio`
- Status: `active module home`
- Primary frontend files:
  - `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
  - `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
  - `frontend/src/features/workbench/module-home/usePortfolioHomeQueries.ts`
- Primary downstream pages:
  - `/balance-analysis`
  - `/bond-dashboard`
  - `/positions`
  - `/pnl-attribution`

### B. Primary business question

- The page answers: what portfolio-scale, risk, structure, and PnL evidence is ready enough to decide the next drilldown?
- It is a module home and navigation summary, not a standalone formal metric page.
- It must not replace the formal truth on `/balance-analysis`, `/bond-dashboard`, `/positions`, or `/pnl-attribution`.

### C. Data chain

- `usePortfolioHomeQueries` loads existing balance, bond dashboard, risk, structure, portfolio comparison, basis, and PnL attribution read surfaces.
- `buildModuleHomeView(... kind="portfolio")` maps those query envelopes into KPI cards, source statuses, briefings, distribution panels, and detail panels.
- The page only displays returned fields and presentation conversions such as yuan to yi yuan; it does not create official finance calculations.

### D. Units, dates, and status

- Amounts follow the originating endpoint semantics and may be rendered in yi yuan only as presentation.
- Dates are inherited from each endpoint result or result metadata; mixed dates must remain visible through source status and panel metadata.
- Empty state: missing query data must remain a muted or warning status, not a synthetic portfolio total.
- Failure state: failed child queries must remain visible at source or panel level.
- Stale/fallback state: quality, fallback, and source metadata from child endpoints must not be hidden by the module home.

### E. Metric bindings

- None. This module home has no standalone `MTR-*` binding.
- Formal-use claims remain scoped to each downstream page and API result metadata.

### F. Tests

- Frontend: `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.6 PAGE-MARKET-HOME-001 Market Workbench Home

### A. Page identity

- Page ID: `PAGE-MARKET-HOME-001`
- Primary front-end route: `/market-overview`
- Status: `active module home`
- Primary frontend files:
  - `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
  - `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
  - `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts`
- Primary downstream pages:
  - `/market-data`
  - `/cross-asset`
  - `/macro-toolkit`
  - `/stock-analysis`
  - `/news-events`

### B. Primary business question

- The page answers: which market data, macro, cross-asset, stock observation, or event context should be opened first today?
- It is a market entry surface and must not promote observational or vendor-readiness signals into formal operating metrics.
- Old `/market` bookmarks may redirect to `/market-data`; `/market-overview` remains the module home route.

### C. Data chain

- `useMarketHomeQueries` loads Choice macro latest data, market rate series, market catalog, and macro toolkit **full** analysis with `historyLimit: 430` (Crisis Score 历史窗口)。
- `buildModuleHomeView(... kind="market")` maps query envelopes into market KPI cards, rate tables, macro/toolkit panels, `MarketCrisisExplainBand`（Crisis Score 解释带）、`MarketDeskIntelStrip`（含 `yield_curve_shape` 形态标签）与 source statuses。
- The page references market data result metadata and child-page readiness instead of defining a new market metric contract.
- 商品旁证 / 影子评估不在市场首页完整展开；仅保留研究说明链接至 `/macro-toolkit#macro-toolkit-crisis-detail`。

### D. Units, dates, and status

- Rate, FX, spread, and macro units come from the originating market or macro payload and their local formatters.
- Trade dates and as-of dates must stay tied to the source row or result metadata.
- Empty state: no rates, no catalog, or no macro toolkit result must show a missing/partial status.
- Failure state: failed market or macro queries must be visible and must not be replaced by demo market values.
- Stale/fallback state: vendor, fallback, catalog, and source-version status must remain visible.

### E. Metric bindings

- None. This module home has no standalone `MTR-*` binding.
- Formal-use claims remain scoped to `/market-data` or the specific returned `result_meta`.

### F. Tests

- Frontend: `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.6.1 PAGE-CROSS-ASSET-001 Cross-Asset Drivers

### A. Page identity and question

- Page ID: `PAGE-CROSS-ASSET-001`
- Primary front-end route: `/cross-asset`
- Status: `active analytical page`
- The first screen answers which governed cross-asset transmission evidence is usable today; it must not promote retained, stale, fallback, or source-blocked observations into a transmission conclusion.

### B. Metric and direction boundaries

- `financial_conditions` binds only `EMM01843735` (中国金融条件指数). It is a zero-centered `z-score`; it must not be replaced by a market index, converted into a percentage return, normalized to first-value `100`, or included in asset-level volatility/correlation calculations.
- `csi300` binds only `CA.CSI300` (沪深300指数收盘点位). Its display unit is `point`; it is the broad-equity input for market regime, equity evidence, trend summaries, and stock analysis.
- Raw KPI changes may be described only as `rising` / `falling` / `neutral`. `supportive` / `restrictive` is reserved for governed transmission-axis output and must not be inferred from the sign of a raw KPI change.
- `EMM01843735` and `CA.CSI300` remain separate even when their report dates differ; freshness never makes them substitutes.

### C. First-screen source gate

- `source-blocked` is a blocking first-screen state alongside permission failure, loading failure, and no data.
- When blocked, hero, regime, dominant driver, bond judgment, stock judgment, trust badge, and action rail must show `来源受限` / `待确认`; retained rows may remain visible only as auditable raw evidence.
- When `source-blocked`, the first-screen correlation, transmission, and investment-judgment lower grid must be replaced by the blocking notice, and retained Choice rows in the evidence matrix must show low credibility.
- A blocked page must not simultaneously emit `dual-source` / `双源就绪`.

### D. Tests

- KPI semantics: `frontend/src/features/cross-asset/lib/crossAssetKpiModel.test.ts`.
- Asset analytics: `frontend/src/features/cross-asset/lib/crossAssetAnalytics.test.ts`.
- First-screen contract: `frontend/src/test/crossAssetDriversPageModel.test.ts`.
- Page integration: `frontend/src/test/CrossAssetPage.test.tsx`.

## 14.7 PAGE-RISK-HOME-001 Risk Workbench Home

### A. Page identity

- Page ID: `PAGE-RISK-HOME-001`
- Primary front-end route: `/risk-overview`
- Status: `active module home`
- Primary frontend files:
  - `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
  - `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
- Primary downstream pages:
  - `/risk-tensor`
  - `/concentration-monitor`
  - `/cashflow-projection`

### B. Primary business question

- The page answers: which risk-tensor, concentration, or cashflow area needs the next review?
- It is a risk module home and must not replace `PAGE-RISK-001` formal risk tensor truth.
- It must not estimate regulatory DV01, liquidity pressure, or concentration limits in the frontend.

### C. Data chain

- The module home loads risk tensor dates, selected risk tensor payload, and cashflow projection payload through the shared API client.
- `buildModuleHomeView(... kind="risk")` maps returned tensor and cashflow fields into KPI cards, detail panels, and drilldown status.
- Concentration remains a downstream drilldown status unless its route supplies explicit data to this module home.

### D. Units, dates, and status

- DV01/CS01 values must preserve the backend risk tensor field semantics and visible units.
- Report date comes from risk tensor date/result payload; cashflow may carry its own report date.
- Empty state: no tensor date, no tensor payload, or no cashflow payload must remain visible.
- Failure state: risk query failures must show warning/error status and must not be replaced with frontend estimates.
- Stale/fallback state: degraded tensor inputs, maturity gaps, fallback dates, and quality flags must remain visible.

### E. Metric bindings

- None. This module home has no standalone `MTR-*` binding.
- Formal risk metrics remain bound to `PAGE-RISK-001`.

### F. Tests

- Frontend: `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.8 PAGE-PERFORMANCE-HOME-001 Performance Workbench Home

### A. Page identity

- Page ID: `PAGE-PERFORMANCE-HOME-001`
- Primary front-end route: `/performance`
- Status: `active module home`
- Primary frontend files:
  - `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
  - `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
- Primary downstream pages:
  - `/kpi`
  - `/team-performance`
  - `/pnl-by-business`
  - `/product-category-pnl`

### B. Primary business question

- The page answers: which KPI, team contribution, business PnL, or product PnL surface should support the current performance review?
- It is a performance entry surface and must not rebuild KPI scoring or team allocation formulas.
- It must not treat temporary-exception downstream pages as formal KPI truth.

### C. Data chain

- The module home loads KPI owners, KPI period summary, and business PnL YTD payloads where available.
- `buildModuleHomeView(... kind="performance")` maps returned summaries into KPI cards, source statuses, briefings, and drilldown rows.
- Team performance and product-category details remain governed by their own pages and result metadata.

### D. Units, dates, and status

- KPI period labels, PnL units, and report dates must come from the originating payloads.
- Empty state: missing KPI owner, KPI summary, or business PnL must remain visible.
- Failure state: failed KPI/PnL queries must not be hidden behind static performance copy.
- Stale/fallback state: downstream quality, fallback, and temporary-exception boundaries must remain visible before any performance conclusion.

### E. Metric bindings

- None. This module home has no standalone `MTR-*` binding.
- Formal KPI, team, and PnL semantics belong to the downstream pages and source contracts.

### F. Tests

- Frontend: `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

## 14.8.1 PAGE-PNL-BY-BUSINESS-001 Business Type PnL

### A. Page identity

- Page ID: `PAGE-PNL-BY-BUSINESS-001`
- Primary front-end route: `/pnl-by-business`
- Status: `active analytical page with approved derived-insights overlay`
- Primary frontend files:
  - `frontend/src/features/pnl/PnlByBusinessPage.tsx`
  - `frontend/src/features/pnl/PnlByBusinessManagementChangePanel.tsx`
  - `frontend/src/features/pnl/pnlByBusinessPageModel.ts`
  - `frontend/src/api/pnlClient.ts`
- Primary backend/API files:
  - `backend/app/api/routes/pnl.py`
  - `backend/app/services/pnl_service.py`
  - `backend/app/repositories/pnl_repo.py`

### B. Primary business question

- The page answers: 哪类业务贡献/拖累最大，FTP 后是否仍有效，下一步该下钻哪里，数据能不能用于决策？
- The primary analysis view is YTD/月报 ZQTZ 管理披露分类, not formal primary.
- Formal primary is a reconciliation evidence view only; it must not be mixed with monthly/YTD business conclusions.
- The page must not replace `/product-category-pnl`, `/ledger-pnl`, `/pnl`, or `/pnl-bridge`.

### C. Data chain

- Monthly analysis uses `GET /api/pnl/by-business-monthly`.
- YTD analysis uses `GET /api/pnl/by-business-ytd`.
- Approved structure analysis uses `GET /api/pnl/by-business-insights?year=...&as_of_date=...`. The endpoint composes the governed current-period YTD result, prior-year same-period YTD result, and rolling 12 natural-month results in the backend; the browser consumes the returned metrics and must not recompute their formulas. The legacy `GET /api/pnl/by-business-candidate-insights` route remains compatibility-only and always returns `formal_use_allowed=false`.
- The approved structure endpoint returns: YTD CNY-equivalent parent-row average-balance HHI and Top-3 share; per-business negative-FTP month share and longest natural-month streak with missing months excluded from the denominator and interrupting the streak; current-YTD versus prior-year-same-period YTD average-balance share drift; and the backend-owned scale–FTP-after-return relative quadrant. The untraced-FI trend is returned as a separate reconciliation diagnostic and must not be mixed into leadership business conclusions. Its DTO exposes `available` and `availability_reason`; a storage/read failure is `source_unavailable`, while a successfully read window with no formal-FI observations is `no_observations`. Neither state may be represented as a successful empty or zero trend.
- YTD row-level `avg_balance`, annualized yield, FTP cost, and FTP-after-PnL come from `GET /api/pnl/by-business-ytd`; the front end must not recalculate them.
- YTD `summary` is backend-owned and covers parent business rows only. Amount, balance, and asset-count fields aggregate the non-overlapping parent rows; annualized yield and FTP fields are recalculated by the governed backend formula from the aggregate PnL, aggregate ADB, calendar days, and returned FTP rate. `proportion` is classified parent PnL divided by source total PnL. Detail/“其中项” rows are excluded, and the front end must not re-aggregate the rows.
- `GET /api/analysis/adb/comparison` is supplemental cross-source evidence for category/rollup coverage and ADB-vs-current drivers, not a required source for the YTD row fields. If it is unavailable or returns a different interval, the page may use the YTD row `avg_balance` for this page only, but must visibly downgrade the cross-source ADB conclusion.
- Formal reconciliation uses `GET /api/pnl/by-business`.
- Manual adjustment audit/actions use `/api/pnl/by-business/manual-adjustments*`; they are displayed as audit/reconciliation controls and must not create a new official metric definition.
- Page-read-model observability uses `GET /api/pnl/by-business/precompute-status?year=...&as_of_date=...`; permission-gated operator recovery uses `POST /api/pnl/by-business/precompute-rebuild?year=...&as_of_date=...`. Status/currentness is resolved against the page's selected cutoff, never the latest date for the year by implication. `queued` also covers an automatic retry wait; only retry exhaustion or a stale in-flight run is exposed as `failed`. Polling while work is in flight reads lifecycle/metadata only and defers the full source-fingerprint verification until the run is terminal. These endpoints report/operate the existing monthly and analysis precompute only and do not define or recalculate a metric in the front end.
- `/api/pnl/by-business-analysis?dimension=currency` uses the governed original-asset currency from the matched formal balance fact (`currency_code`) when available. This includes FI USD bonds such as non-financial enterprise bonds. Instrument code `J1` is only the fallback USD rule when governed original-currency evidence is absent; `JM`, `J4`, and other codes without such evidence fall back to `CNY`. This dimension changes grouping only; PnL, ADB, current balance, FTP cost, and FTP-after-PnL remain CNY-equivalent amounts.
- Monthly and YTD reconciliation diagnostics are backend-owned. For each period, `source_total_pnl = classified_parent_total_pnl + unallocated_pnl + reconciliation_delta`; the front end may format these values but must not derive or rebalance them.
- Monthly management comparison is backend-owned in `/api/pnl/by-business-monthly.result.management_change`. Within the requested `year`, it compares the `as_of_date` month with the exact preceding calendar month; it never skips to an older available month and never fills a missing month or business row with zero. January returns `previous_month_outside_request_scope` rather than claiming that the preceding December source is absent. Amount deltas are current minus previous in yuan, while yield deltas are returned in bp.
- `unallocated_items` contains source rows that did not hit a parent business rule, while `unallocated_breakdown` is the backend aggregation of the same evidence. `unallocated_evidence_complete=true` means the monthly bucket returned both reconciliation totals and its governed unallocated evidence; false or missing must remain `待核对`, never be treated as a closed zero difference.
- The front-end model may derive presentation-only insight labels from returned payload fields, but must not recalculate official PnL, balance, FTP cost, or formal yield formulas.

### D. Required sections

| section_key | Purpose | Data source |
| --- | --- | --- |
| `decision_hero` | State the selected view, report date, and current business question | page model + `result_meta` |
| `data_status` | Keep `quality_flag`, fallback, vendor status, trace, and generated time visible | active endpoint `result_meta` |
| `precompute_status` | Show queued/running/completed/failed lifecycle, serving mode, cutoff, generation time, source/rule evidence, and controlled rebuild; hide it in the formal-primary reconciliation tab | precompute status/rebuild endpoints + `cache_build_run` governance stream |
| `analysis_strip` | Put the leadership summary before the long analysis body; summarize contribution, drag, FTP/ADB status, formal reconciliation warning, and next drilldown without repeating the KPI band | page model derived from active payload fields |
| `structure_efficiency` | In YTD only, show approved concentration, persistent-negative-FTP, same-period share-drift, and scale–FTP-after-return conclusions; use the selected cutoff exactly and fail closed to `待复核` for a non-formal, fallback, date-mismatched, stale/error, or vendor-unusable envelope | `/api/pnl/by-business-insights` + page-local presentation model |
| `management_change` | In YTD, show backend-computed latest-month versus previous-calendar-month changes in ADB, PnL, FTP net PnL, FTP-after annualized yield, and parent-business drivers before the long table | `/api/pnl/by-business-monthly.result.management_change` |
| `main_table` | Show monthly/YTD/formal detail table with explicit units; the YTD footer consumes the backend-owned parent `summary` | active payload rows + YTD `summary` |
| `selected_business_trend` | In YTD, show the selected row's monthly ADB/current balance, PnL/FTP-after-PnL, and returned yield/FTP fields immediately after the table; match by stable `row_key`, use YTD `period_start_date`/`period_end_date` as the expected boundary, preserve every missing bucket or row as `null`, and perform presentation-only yuan-to-`亿元`/`万元` conversion | `/api/pnl/by-business-ytd` period boundary + `/api/pnl/by-business-monthly` items |
| `driver_overview` | In YTD, rank contribution, drag, yield, and ADB-vs-current-balance drivers after the selected-business decision chain | YTD rows + optional ADB comparison cross-check |
| `monthly_breakdown` | In monthly/YTD, allow monthly reconciliation against published monthly buckets | monthly payload |
| `drilldown` | In YTD, show FTP bridge, bond-bucket, instrument, and multidimensional drilldowns | `/api/pnl/by-business-analysis` |
| `evidence` | Show source, lineage, and result metadata below the decision summary | `result_meta` |

### E. Units, dates, and status

- Amount columns displayed in the page are in `万元` unless the table header explicitly says `亿元`.
- ADB and current balance displays are `亿元`.
- Insights `avg_balance` / `total_avg_balance` fields are serialized in yuan and must be divided by `100,000,000` for `亿元` display; `null` remains `--`, never numeric zero.
- Reconciliation and unallocated payload amounts are serialized in `元` and displayed in `万元`; row counts and coverage days are not currency values.
- Yield fields are displayed as `%`; formal primary `yield_pct` comes from the backend formal query and is not recomputed in the page model.
- `management_change` amount deltas are serialized in yuan and displayed as `亿元` for ADB or `万元` for PnL fields. `annualized_yield_delta_bp` and `ftp_net_annualized_yield_delta_bp` are already bp and must not be multiplied again in the front end.
- `comparison_status=data_quality_warning` means the exact two calendar-month buckets were compared but at least one has sample filling/incomplete date coverage, unallocated rows, a non-zero reconciliation difference, or incomplete unallocated evidence. `coverage_warning_months` and `reconciliation_warning_months` distinguish those causes. A non-month-end bucket returns `period_incomplete` and no comparison values; January returns `previous_month_outside_request_scope`. Missing-month and row-level missing reasons must remain unavailable/null and must not be converted to zero.
- If either compared month has `coverage_days=0`, PnL component deltas may remain comparable, but ADB, current balance, annualized yield, FTP cost, FTP net PnL, and FTP-after annualized deltas must be `null`; absence of balance observations is not a real zero balance.
- If a background monthly refresh fails while a cached `management_change` remains available, the page may keep the cached values visible only with an explicit stale/refresh-failed warning that says the result may exclude newer supplements or manual adjustments.
- A current source/rule fingerprint match is required before the status surface may say `预计算已就绪`. If the precompute is missing or stale, monthly/analysis endpoints keep the governed real-time calculation path and the page must say `当前使用实时计算`; a failed run must show its error and preserve the permission-gated rebuild action. Queued/running jobs are polled, and a completed current run invalidates the page queries once so the precomputed payload becomes visible.
- When `management_change` is shown in YTD, the evidence disclosure must include the monthly endpoint `result_meta` alongside the active YTD metadata so its trace, quality, fallback, generation time, and analytical/non-formal status remain auditable.
- Monthly view date semantics use the selected report month/bucket from `/api/pnl/by-business-monthly`.
- YTD view date semantics use selected `year` and `as_of_date` from `/api/pnl/by-business-ytd`.
- Formal primary view uses the selected single `report_date` from `/api/pnl/by-business`.
- Empty, loading, error, stale, fallback, and warning states must remain visible in the first screen status strip or state surfaces.
- The YTD structure panel may form a leadership conclusion only when the insights envelope has `basis=formal`, `formal_use_allowed=true`, `result_kind=pnl.by_business_insights`, `result_version=v2`, `vendor_status=ok`, `fallback_mode=none`, no fallback date, and both resolved/result dates equal the selected cutoff. `quality_flag=warning` remains usable only with a visible warning; `missing`, `stale`, `error`, `vendor_stale`, and `vendor_unavailable` must fail closed. The panel must not appear in monthly or formal-primary reconciliation views.
- V2 nested evidence is part of the same gate: baseline requested/resolved dates must match with `baseline_fallback_mode=none`; `component_evidence` must contain exact current-YTD, baseline-YTD, and every `monthly_YYYY` year implied by the rolling window. `current_ytd` and the current-year monthly component must bind to `result.as_of_date`; `baseline_ytd` must bind to `baseline_requested_report_date`; a prior-year monthly component must bind to that calendar year's `12-31`. Every component must have exact requested/resolved dates, `fallback_mode=none`, `vendor_status=ok`, and quality `ok|warning`. Missing, duplicate, extra, malformed, or correctly self-equal but wrong-cutoff evidence fails closed even if the outer metadata appears usable.
- A formal insights envelope may be constructed only when every required component has `formal_source_admitted=true` and `admission_reason=null`. The expected upstream contract is an `analytical` wrapper with `formal_use_allowed=false`, the correct YTD/monthly `result_kind`, `source_surface=formal_pnl`, complete trace/source/rule/cache evidence, and the governed formal FI, non-standard bridge, daily-balance, and classification table anchors. Any `data_input/*` refresh-bundle source, missing formal anchor, lineage gap, unexpected basis/result kind, date mismatch, fallback, unusable quality, or unusable vendor status rejects formal admission; the legacy candidate endpoint may still expose the rejected evidence as non-formal.
- If `reconciliation_diagnostics.available=false`, the endpoint raises the outer `quality_flag` to at least `warning` and the detail page displays the reason explicitly. Because `MTR-PNLBIZ-006` is diagnostic-only, this warning does not by itself invalidate independently admitted 001~005/007 business-analysis facts.
- Negative-FTP share/streak may render only when `eligible=true` and `status=eligible`; `insufficient_observations` must display a sample-insufficient state, not a zero or a non-warning conclusion. Share drift may render only when `available=true`; otherwise its `availability_reason` remains visible and rows may not be interpreted.
- The detail-page link must carry the active `year` and exact `as_of_date`; the detail page validates those query parameters and must not silently reset the selected cutoff to today.
- YTD `缺日均` confidence may only count parent rows with actual business activity; zero-PnL/zero-asset parent rows must not block FTP analysis.
- ZQTZ parent rows whose ADB can be resolved through existing rollup children must not be counted as missing ADB.
- A failed supplemental ADB comparison must not be interpreted as missing YTD daily averages. Positive YTD `avg_balance` values may support page analysis when the returned FTP fields are complete; a YTD zero denominator remains pending confirmation when the independent ADB comparison is unavailable.
- `coverage_days` is the count of distinct governed balance dates in the returned period; `expected_days` is the inclusive calendar-day count. `sample_filled=true` and `sample_fill_method=observed_days_scaled_to_calendar` identify an observed-day average carried as a calendar-period estimate, not complete daily coverage.

### F. Metric status and boundaries

- Approved derived-analysis bindings are `MTR-PNLBIZ-001` through `MTR-PNLBIZ-005` and `MTR-PNLBIZ-007`, owned by `组合管理/固收业务分析` and approved by `财务管理/资产负债管理`. They are served by `GET /api/pnl/by-business-insights` and are formal for the stated descriptive business-analysis purpose only.
- `MTR-PNLBIZ-006` is an approved diagnostic-only untraced-FI trend. It remains structurally separated from concentration, FTP, share-drift, and quadrant conclusions.
- These bindings do not redefine the underlying monthly/YTD PnL, ADB, FX, FTP cost, or FTP-after-PnL facts; do not approve a regulatory concentration limit or FTP rate caliber; and do not replace product-category, ledger, formal-PnL, or bridge truth.
- Business PnL rows reuse formal/monthly/YTD payload fields from the PnL service and remain page-level analytical display, not product-category truth.
- `MTR-PNLBIZ-007` uses x = YTD CNY-equivalent parent-row average-balance share and y = returned FTP-after annualized yield; the backend splits both axes at the eligible-row median only when at least six rows qualify. The label is descriptive relative positioning and must not output or imply allocation, increase, reduction, or exit advice.
- `ftp_net_annualized_yield_delta_bp` may be labelled `FTP后年化变化`; it must not be presented as a newly approved independent `生息资产利差` metric.
- Product-category truth remains governed by `PAGE-PROD-CAT-PNL-001`.
- Ledger-account PnL truth/candidate display remains governed by `PAGE-LEDGER-PNL-001`.
- Formal PnL overview truth remains governed by `PAGE-PNL-001`; PnL bridge truth remains governed by `PAGE-BRIDGE-001`.
- The formal primary tab is `仅对账`; it is source evidence for tracing `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, and `fact_formal_zqtz_balance_daily`, not the page's primary business contribution analysis.
- Monthly/YTD analytical `result_meta.quality_flag` is `warning` when balance coverage is incomplete, any unallocated row exists (including net-zero groups), or `reconciliation_delta` is non-zero. A non-zero unallocated amount must not be silently assigned to A/T without a governed rule.

### G. Known data-quality risks

- Formal primary may return `quality_flag=warning` when `summary.untraced_pnl_row_count > 0`.
- Current 2026-05-31 local evidence shows 148 formal FI rows untraced by balance join; page evidence surfaces the main zero-balance groups such as `T`, `A`, and `H` from existing rows where `balance_row_count = 0`.
- Owner-approved trace rule: strict match is attempted first; if it misses, `cost_center` may be relaxed only when report date, instrument code, portfolio, currency basis, and `position_scope = asset` still match a ZQTZ balance row.
- Formal summary may include `untraced_breakdown` as reconciliation-only evidence for remaining rows, using balance-evidence buckets such as `position_absent_before_maturity`, `matured_before_or_on_report_date`, and `never_seen_in_zqtz_asset_balance`; these buckets are not official business contribution metrics.
- Supporting read-only diagnostic: `docs/pnl/pnl-by-business-formal-untraced-diagnostic-2026-05-31.md`.
- Owner triage packet: `docs/pnl/pnl-by-business-formal-untraced-detail-packet-2026-05-31.md`.
- Untraced formal rows must be treated as reconciliation follow-up, not as a reason to mix formal primary rows into monthly/YTD conclusions.
- FTP rate remains the current page behavior until a metric contract explicitly formalizes it.

### H. Tests

- Frontend page/model: `frontend/src/features/pnl/pnlByBusinessPageModel.test.ts`.
- Approved insights selector/panel: `frontend/src/features/pnl/pnlByBusinessInsightsModel.test.ts`, `frontend/src/features/pnl/PnlByBusinessInsightsLeadershipPanel.test.tsx`.
- Insights page/client: `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.test.tsx`, `frontend/src/features/pnl-business-insights/CapitalEfficiencyQuadrantPanel.test.tsx`, `frontend/src/test/PnlBusinessInsightsClient.test.ts`.
- Selected-business monthly trend selector: `frontend/src/features/pnl/pnlByBusinessMonthlyTrend.test.ts`.
- Route smoke: `frontend/src/test/PnlRoutesSmoke.test.tsx`.
- PnL domain client: `frontend/src/test/PnlBusinessClientPrecompute.test.ts`.
- API contract: `tests/test_pnl_api_contract.py`.
- Approved-insights API/formulas: `tests/test_pnl_by_business_insights_contract.py`, `tests/test_pnl_by_business_candidate_insights_contract.py`.
- Mutation authorization: `tests/test_write_route_auth_contract.py`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

### I. Governed insights detail route

#### I.1 Page identity

- Governing Page ID: `PAGE-PNL-BY-BUSINESS-001`
- Governed detail route: `/pnl-by-business-insights`
- Status: `active governed formal-analysis detail page`
- This route is a dedicated presentation surface under the existing page contract; it does not create a second page identity or metric definition.
- Primary frontend files:
  - `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx`
  - `frontend/src/features/pnl-business-insights/CapitalEfficiencyQuadrantPanel.tsx`
  - `frontend/src/features/pnl-business-insights/UntracedReconciliationTrendPanel.tsx`
  - `frontend/src/api/pnlClient.ts`

#### I.2 Primary business question

- The page answers: 业务结构是否集中、哪些业务持续未覆盖 FTP、日均份额同比如何变化、规模与 FTP 后收益处于什么相对位置？
- It is a descriptive formal-analysis detail page, not a concentration-limit, FTP-rate, allocation, performance-assessment, or source-fact certification page.

#### I.3 Data chain

- The page reads only `GET /api/pnl/by-business-insights?year=...&as_of_date=...`.
- It must not call the legacy candidate endpoint or rebuild metrics from YTD/monthly rows in the browser.
- Formal display requires the approved v2 envelope, exact cutoff, complete component evidence, no fallback, usable vendor/quality state, and admitted formal sources.
- `GS-PNL-BUSINESS-INSIGHTS-A` is formula/DTO evidence, not independent source-fact truth.

#### I.4 Required sections

| section_key | Purpose | Data source |
| --- | --- | --- |
| `decision_hero` | Show the exact cutoff and primary business question | query parameters |
| `data_status` | Show formal status, quality, cutoff, fallback, and trace | `result_meta` |
| `concentration` | Show `MTR-PNLBIZ-001` and `MTR-PNLBIZ-002` | formal endpoint |
| `negative_ftp_persistence` | Show `MTR-PNLBIZ-003` and `MTR-PNLBIZ-004`, including insufficient-observation state | formal endpoint |
| `share_drift` | Show `MTR-PNLBIZ-005` and any unavailable reason | formal endpoint |
| `scale_yield_quadrant` | Show descriptive `MTR-PNLBIZ-007` only when eligible | formal endpoint |
| `reconciliation_diagnostics` | Show `MTR-PNLBIZ-006` in a separately labelled non-business-conclusion section | formal endpoint |

#### I.5 Units, dates, and status

- `001`/`002`/`003`/`006` use `%`; `004` uses `月`; `005` uses signed `pp`; `007` uses a quadrant label plus `%`.
- The selected `year` and canonical `as_of_date` must reach the formal endpoint unchanged.
- Non-formal, fallback, stale, error, missing, vendor-unusable, date-mismatched, malformed-v2, or incomplete-component evidence fails closed to `待复核`.
- A warning remains usable only when it is visible.
- Null, insufficient observations, source unavailable, and no observations must not become zero.

#### I.6 Metric status and boundaries

- `MTR-PNLBIZ-001` through `005` and `007` are approved formal `business_analysis` metrics for descriptive analysis only.
- `MTR-PNLBIZ-006` is also approved/formal, but its `metric_kind` is `diagnostic_only`; it must remain structurally separated from business conclusions.
- This route reuses the definitions and golden sample bound to `PAGE-PNL-BY-BUSINESS-001`; it creates no new `MTR-*` identifiers.
- No metric creates a concentration limit, changes the FTP caliber, or authorizes 增配、压降、退出, or performance conclusions.

#### I.7 Evidence boundary and known risks

- Golden approval proves formula, DTO, units, thresholds, null behavior, and diagnostic separation only.
- Underlying PnL, balance, FX, and lineage facts remain subject to independent reconciliation.
- A live exact-cutoff read of `GET /api/pnl/by-business-insights?year=2026&as_of_date=2026-06-30` was captured on `2026-07-16` through `scripts/emit_pnl_by_business_insights_governance_record.py`; the governance stream now reports `direct_page_or_api_records_present` and `direct_records_ready_for_audit_review` for `PAGE-PNL-BY-BUSINESS-001`.
- This direct record preserves the real trace/source/rule/cache versions, exact requested/resolved/as-of date, no-fallback state, and admitted current/baseline/monthly component evidence. It does not turn the golden sample into independent source-fact truth or prove page-execution completeness.
- Audit review remains open with `closure_approved=false`; the written record is evidence for review, not a new page identity, a new metric approval, source-fact certification, or permission to mix diagnostic-only `MTR-PNLBIZ-006` into business conclusions.
- Diagnostic unavailability must expose `available=false` and `availability_reason`; an unavailable empty series is not zero.

#### I.8 Tests

- Frontend page: `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.test.tsx`.
- Frontend client: `frontend/src/test/PnlBusinessInsightsClient.test.ts`.
- Route/readiness: `frontend/src/test/LiveRouteReadiness.test.tsx`, `frontend/src/test/routes.test.tsx`.
- API/formulas: `tests/test_pnl_by_business_insights_contract.py`, `tests/test_pnl_by_business_candidate_insights_contract.py`.
- Golden sample: `tests/test_golden_samples_capture_ready.py`.
- Governance: `tests/test_live_route_page_contract_completeness.py`, `tests/test_governance_doc_contract.py`.

## 14.9 PAGE-REPORTS-HOME-001 Reports And Data Home

### A. Page identity

- Page ID: `PAGE-REPORTS-HOME-001`
- Primary front-end route: `/reports`
- Status: `active module home`
- Primary frontend files:
  - `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
  - `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
- Primary downstream pages:
  - `/platform-config`
  - `/cube-query`
  - `/reports`

### B. Primary business question

- The page answers: are data health, source status, self-service query, and report-planning surfaces ready to support delivery?
- It is a governance/reporting entry surface and must not fabricate report data when a backend report interface is absent.
- It must keep planned or unimplemented report capabilities visibly marked as planned/pending.

### C. Data chain

- The module home loads health status, source foundation preview, and cube dimensions where available.
- `buildModuleHomeView(... kind="governance")` maps those payloads into data health KPIs, source rows, cube capability rows, and report planning notes.
- Cube query semantics remain scoped to `PAGE-CUBE-QUERY-001`; platform health remains diagnostics rather than business metric approval.

### D. Units, dates, and status

- Health and source status fields are displayed as returned by their diagnostic endpoints.
- Cube dimensions have no amount units; fact-table units are only known after a specific cube query.
- Empty state: missing source, health, or cube capability must show explicit missing/planned status.
- Failure state: failed health/source/cube reads must remain visible.
- Stale/fallback state: diagnostics or source preview metadata must not be converted into formal data-quality approval.

### E. Metric bindings

- None. This module home has no standalone `MTR-*` binding.
- Formal-use claims remain scoped to specific downstream query results and result metadata.

### F. Tests

- Frontend: `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`.
- Contract gate: `tests/test_live_route_page_contract_completeness.py`.

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
