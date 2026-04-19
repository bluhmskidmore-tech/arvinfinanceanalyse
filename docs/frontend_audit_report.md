# 前端数字正确性审计与页面闭环排查报告

## 审计范围

- 受限于当前 cutover 边界，本次只审计当前允许消费面及其直接依赖链路：
  - `/` 驾驶舱
  - `/pnl-attribution`
- 排查层级：
  - 页面组件
  - 数据请求层 / API client
  - adapter / transformer / mapper
  - state / store
  - selector / computed
  - formatter
  - 图表 / 表格数据组装逻辑
- 明确未触碰：
  - 数据库 schema
  - 权限 / 认证
  - 队列 / 调度 / 缓存底座
  - SDK / 通用 service / 全局状态架构
  - 任何代码修复

## 前端目录与入口识别

### 前端目录

- 根目录：`frontend/`
- 应用入口：`frontend/src/main.tsx`
- App 入口：`frontend/src/app/App.tsx`
- Provider 入口：`frontend/src/app/providers.tsx`
- 路由入口：`frontend/src/router/routes.tsx`
- Shell / 导航：`frontend/src/layouts/WorkbenchShell.tsx`

### 主要页面路由 / 页面入口

- 驾驶舱 `/`
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
- 损益归因 `/pnl-attribution`
  - `frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx::PnlAttributionPage`
  - 主体视图：`frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx::PnlAttributionView`

### API 层入口

- API client 入口：`frontend/src/api/client.ts`
- 契约类型：`frontend/src/api/contracts.ts`

当前两页直接使用的主要接口：

- Dashboard
  - `getOverview -> /ui/home/overview`
  - `getSummary -> /ui/home/summary`
  - `getPnlAttribution -> /ui/pnl/attribution`
  - 同页还会请求：
    - `getRiskOverview -> /ui/risk/overview`
    - `getContribution -> /ui/home/contribution`
    - `getAlerts -> /ui/home/alerts`
- PnL Attribution
  - `getVolumeRateAttribution -> /api/pnl-attribution/volume-rate`
  - `getTplMarketCorrelation -> /api/pnl-attribution/tpl-market`
  - `getPnlCompositionBreakdown -> /api/pnl-attribution/composition`
  - `getPnlAttributionAnalysisSummary -> /api/pnl-attribution/summary`
  - `getPnlCarryRollDown -> /api/pnl-attribution/advanced/carry-rolldown`
  - `getPnlSpreadAttribution -> /api/pnl-attribution/advanced/spread`
  - `getPnlKrdAttribution -> /api/pnl-attribution/advanced/krd`
  - `getPnlAdvancedAttributionSummary -> /api/pnl-attribution/advanced/summary`
  - `getPnlCampisiAttribution -> /api/pnl-attribution/advanced/campisi`
  - `getPnlCampisiFourEffects -> /api/pnl-attribution/campisi/four-effects`
  - `getPnlCampisiEnhanced -> /api/pnl-attribution/campisi/enhanced`
  - `getPnlCampisiMaturityBuckets -> /api/pnl-attribution/campisi/maturity-buckets`

### state / store 入口

- 全局查询缓存：`frontend/src/app/providers.tsx::AppProviders`
  - `QueryClientProvider`
  - `ApiClientProvider`
- 本次审计未发现独立的 Redux / Zustand / 全局业务 store
- 当前两页主要是：
  - Dashboard：`useQuery` 直接拉取并渲染
  - PnL Attribution：`useState + useEffect + useCallback` 本地态

### formatter / selector / adapter 的主要位置

- 通用 formatter：
  - `frontend/src/utils/format.ts`
  - `frontend/src/features/bond-analytics/utils/formatters.ts`
  - `frontend/src/features/workbench/components/kpiFormat.ts`
- 当前两页的 page-local formatter / computed：
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::isUnavailableExecutiveSection`
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx::formatYi`
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx::formatMetaDateLabel`
  - `frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx::normalizeCampisiData`
  - `frontend/src/features/pnl-attribution/components/*.tsx` 内部大量 `formatYi` / `toFixed` / `Math.abs`
- 独立 adapter / transformer / mapper：
  - Dashboard 当前基本没有，API `result` 几乎直达组件
  - PnL Attribution 当前也没有 page-level adapter，图表组件直接消费 DTO

### 本仓库现有 lint / typecheck / test / build 命令

- 前端：
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`
- 后端 / 仓库已有测试入口：
  - `python scripts/backend_release_suite.py`
  - `python -m pytest -q`

## 页面与数据流理解

### 1. Dashboard `/`

数据流：

- `DashboardPage`
  - `useQuery`
  - `ApiClient`
  - `/ui/home/overview | /ui/home/summary | /ui/pnl/attribution | /ui/risk/overview | /ui/home/contribution | /ui/home/alerts`
  - `OverviewSection / SummarySection / PnlAttributionSection / RiskOverviewSection / ContributionSection / AlertsSection`

特点：

- 没有单独 adapter / selector / formatter 层
- 没有统一 `report_date` 状态
- 真实接口区块与演示模块同屏混排
- `result_meta` 只被拿来做“是否隐藏 excluded surface”，没有拿来做用户可见的 stale / fallback / as_of 展示

### 2. PnL Attribution `/pnl-attribution`

数据流：

- `PnlAttributionPage`
  - `PnlAttributionView`
  - `useState`
  - `ApiClient`
  - 多个 `/api/pnl-attribution/*` 接口
  - `VolumeRateAnalysisChart / TPLMarketChart / PnLCompositionChart / AdvancedAttributionChart / Campisi*`

特点：

- 没有统一 adapter 层
- 不同 tab 自己拉自己的 query
- 大量格式化和单位换算散落在各图表组件内部
- 同页元数据展示不完整，只显示 `generated_at / quality_flag / fallback_mode`
- 没有统一 page-level “当前报告日 / 数据口径 / fallback” 顶部锚点

## P0

### P0-1 默认就是 mock mode，未显式配置 `VITE_DATA_SOURCE=real` 时整站数字都会走假数据

- 问题描述
  - `ApiClient` 的 mode 默认回落到 `mock`，不是 `real`。
  - 如果环境变量没有显式设置为 `real`，Dashboard 和 PnL Attribution 全部会消费本地 mock payload。
  - 这会直接造成“数字错”或“与后端不一致”，而且问题根因不在业务计算，而在前端数据源选择。
- 影响页面
  - `/`
  - `/pnl-attribution`
- 怀疑根因
  - `parseEnvMode()` 只在 `VITE_DATA_SOURCE === "real"` 时切到真实接口；否则统一走 `mockClient`。
  - Shell 虽然会显示 `Mock Mode`，但这是页面右下角弱提示，不足以承担数字可信度告知。
- 证据文件和函数
  - `frontend/src/api/client.ts::parseEnvMode`
  - `frontend/src/api/client.ts::createApiClient`
  - `frontend/src/api/client.ts::mockClient`
  - `frontend/src/layouts/WorkbenchShell.tsx::WorkbenchShell`
- 建议修法
  - 在生产 / 预发构建中强制要求 `VITE_DATA_SOURCE=real`，未设置时直接 fail fast。
  - 把“当前数据源”提升到页面主信息区，不要只放固定角标。
  - 为 Dashboard 和 PnL Attribution 增加启动时数据源断言测试。

### P0-2 Dashboard 没有统一报告日锚点，同一首屏的不同数字可能来自不同日期、不同数据面

- 问题描述
  - Dashboard 前端没有 `report_date` state，也没有把日期透传给 `/ui/home/overview`、`/ui/home/summary`、`/ui/pnl/attribution`。
  - 后端 `executive_overview` 内部又分别按各自仓表的“最新可用日期”取数：
    - balance
    - pnl
    - liability
    - bond analytics
  - 结果是同一个首屏上并排的卡片天然可能不是同一天。
- 影响页面
  - `/`
- 怀疑根因
  - 页面层没有 authoritative `report_date`
  - 首页接口也没有统一“同一报告日快照”的 contract
  - 页面没有把 `generated_at / source_version / fallback_mode / as_of_date` 显示出来
- 证据文件和函数
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/api/client.ts::getOverview`
  - `frontend/src/api/client.ts::getSummary`
  - `frontend/src/api/client.ts::getPnlAttribution`
  - `backend/app/services/executive_service.py::executive_overview`
  - `backend/app/services/executive_service.py` 内：
    - `current_balance_report_date`
    - `current_pnl_report_date`
    - `liability_report_date`
    - `current_bond_report_date`
- 建议修法
  - 定义首页唯一的 `report_date`，所有首页 query 都必须绑定它。
  - 首屏显式展示 `report_date / generated_at / quality_flag / fallback_mode`。
  - 在没有统一日期前，不要让首页承担“管理结论页”的角色。

### P0-3 Dashboard 对 warning / vendor_unavailable / explicit miss 几乎不做用户可见展示，容易把缺数或零值当真数

- 问题描述
  - Dashboard 只拿 `result_meta.vendor_status` 去判断是否隐藏 excluded surface。
  - 对已经渲染出来的 overview / summary / attribution，本页不显示 `quality_flag`、`fallback_mode`、`generated_at`、`vendor_status`。
  - 特别是 `/ui/pnl/attribution` 在缺数据时会返回零值分段 payload，而首页仍按正常图卡渲染。
- 影响页面
  - `/`
- 怀疑根因
  - `AsyncSection` 只支持 `loading / error / empty`
  - 页面层没有“warning / stale / fallback / explicit miss”状态机
  - 首页没有接入已有的 metadata 展示思路
- 证据文件和函数
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/components/AsyncSection.tsx::AsyncSection`
  - `backend/app/services/executive_service.py::_pnl_attribution_explicit_miss_payload`
  - `backend/app/services/executive_service.py::executive_pnl_attribution`
  - `backend/app/services/executive_service.py::executive_overview`
- 建议修法
  - Dashboard 每个 live 模块都应接入 `result_meta` 展示。
  - 对 `vendor_unavailable / warning / latest_snapshot / explicit miss` 做独立 UI，而不是继续渲染图形。
  - 把“无数据、延迟数据、回退日期、定义待确认”提升到首屏可见层。

## P1

### P1-1 Dashboard 主动请求了当前 cutover 明确排除的接口，再靠 503 / vendor_status 事后隐藏

- 问题描述
  - 首页明知 `risk-overview`、`home/contribution`、`home/alerts` 不在当前允许面，仍然发请求。
  - 后端这些路由通过 `promoted=False` 强制 503；前端再靠 `isUnavailableExecutiveSection()` 把它们隐藏。
  - 这会让页面结构表现成“看起来像有这些模块，但又像没真正落地”，造成明显的业务表达不自然。
- 影响页面
  - `/`
- 怀疑根因
  - 页面装配没有严格遵守当前 cutover 范围
  - 页面以“先请求再隐藏”的方式管理边界，而不是“按边界决定是否装配”
- 证据文件和函数
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::isUnavailableExecutiveSection`
  - `backend/app/api/routes/executive.py::risk_overview`
  - `backend/app/api/routes/executive.py::contribution`
  - `backend/app/api/routes/executive.py::alerts`
- 建议修法
  - Dashboard 只装配当前真正 landed 的模块。
  - 被排除面要么完全不在首页出现，要么明确放到 reserved/placeholder 区，不走 live 请求。

### P1-2 Dashboard 混排真实 governed 区块与静态 demo 模块，是“页面看起来怪”的直接来源

- 问题描述
  - 首页真实接口区块之外，还硬编码混入：
    - 模块快照
    - 结构 teaser
    - 今日待办（演示数据）
    - 关键日历（演示数据）
  - 这些内容不是同一数据流，也不是同一业务问题的回答，首屏信息层级被打散。
- 影响页面
  - `/`
- 怀疑根因
  - Dashboard 同时承担了：
    - live 经营页
    - 导航页
    - 演示页
    - 占位页
  - `FixedIncomeDashboardHub` 里的内容没有被从 live 首屏剥离
- 证据文件和函数
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/features/workbench/dashboard/FixedIncomeDashboardHub.tsx::DashboardModuleSnapshot`
  - `frontend/src/features/workbench/dashboard/FixedIncomeDashboardHub.tsx::DashboardStructureMaturityTeaser`
  - `frontend/src/features/workbench/dashboard/FixedIncomeDashboardHub.tsx::DashboardTasksAndCalendar`
  - `frontend/src/features/workbench/dashboard/dashboardHubMock.ts`
- 建议修法
  - 首页首屏先只回答一个问题，例如“当前经营结果是否偏离目标、最需要下钻什么”。
  - demo 导航块、任务、日历下沉到单独导航页或 reserved 面板。
  - 首页不要再混入“演示数据”模块。

### P1-3 首页 `Summary` 是静态文案，不是任何 governed read model 的结果

- 问题描述
  - `/ui/home/summary` 返回的是硬编码 `narrative` 和 `points`。
  - 这部分看上去像管理结论，但没有和 overview / attribution 数字做可验证绑定。
  - 它会放大页面“像 PPT，不像业务系统”的感觉。
- 影响页面
  - `/`
- 怀疑根因
  - `executive_summary()` 当前只是静态 copy，借用了 overview 的 lineage，但没有真实摘要生成逻辑
- 证据文件和函数
  - `backend/app/services/executive_service.py::executive_summary`
  - `backend/app/schemas/executive_dashboard.py::SummaryPayload`
  - `frontend/src/features/executive-dashboard/components/SummarySection.tsx::SummarySection`
- 建议修法
  - 没有真实摘要引擎前，应显式标注“静态摘要 / 待接治理数据”。
  - 如果保留 live 模块，摘要至少要由首页已展示的真实指标自动生成，并绑定日期。

### P1-4 首页 `PnlAttributionSection` 把正负号信息在图形层抹平了，而且颜色语义前后打架

- 问题描述
  - 环形图把所有 segment 的值都做了 `Math.abs`，负值也按正面积渲染。
  - 同时该组件的环形图颜色语义和右侧条形颜色语义相反：
    - `chartToneColor.positive = 红`
    - `accentMap.positive = 绿`
  - 用户会看到同一分段在图里一种语义、在条里另一种语义。
- 影响页面
  - `/`
- 怀疑根因
  - 组件内局部定义了两套 tone map
  - 图表层没有保留 sign-aware encoding
- 证据文件和函数
  - `frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx::PnlAttributionSection`
  - `frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx::chartToneColor`
  - `frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx::accentMap`
- 建议修法
  - 统一正负颜色语义。
  - 不要对归因分段直接 `Math.abs` 后再画面积占比；如果需要构成图，必须额外说明是“绝对值占比”。
  - 文本值、图形值、色彩语义必须共用一套 adapter。

### P1-5 Executive 首页与归因工作台不是同一数据流，但前端命名和叙事过近，容易被误解为同一指标

- 问题描述
  - 首页 `PnlAttributionSection` 来自 `ProductCategoryPnlRepository.fetch_rows(..., "monthly")` 的 `business_net_income` 聚合。
  - 归因工作台则来自 formal FI、bond analytics、yield curve、Campisi 等多套正式读面。
  - 这两页都在讲“归因”，但口径、日期、数据源都不同，前端没有把差异说清楚。
- 影响页面
  - `/`
  - `/pnl-attribution`
- 怀疑根因
  - executive analytical surface 与 formal attribution workbench 各自生长，缺少统一命名和 page-level contract
- 证据文件和函数
  - `backend/app/services/executive_service.py::_build_pnl_attribution_from_repo`
  - `backend/app/services/executive_service.py::executive_pnl_attribution`
  - `backend/app/repositories/product_category_pnl_repo.py::fetch_rows`
  - `backend/app/services/pnl_attribution_service.py::volume_rate_attribution_envelope`
  - `backend/app/services/pnl_attribution_service.py::pnl_composition_envelope`
  - `frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx::PnlAttributionSection`
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx::PnlAttributionView`
- 建议修法
  - 如果允许不同口径并存，名称必须拆开，例如“经营贡献拆解” vs “正式损益归因”。
  - 如果不允许不同口径并存，就必须统一回同一 read model 和同一报告日。

### P1-6 Dashboard executive contract 把关键显示值定义为字符串，前端几乎失去数字一致性校验能力

- 问题描述
  - `ExecutiveMetric.value`、`delta`、`RiskSignal.value`、`PnlAttributionPayload.total` 都是字符串。
  - Dashboard 页面没有独立 adapter / formatter 层，API 返回什么字符串就直接渲染什么。
  - 这意味着前端无法校验：
    - 原始值和显示值是否一致
    - 单位是否统一
    - 精度 / rounding 是否正确
    - 同指标跨卡片 / 图表 / 表格是否共享同一 raw number
- 影响页面
  - `/`
- 怀疑根因
  - executive surface contract 以“展示字符串”而不是“typed numeric + unit metadata”设计
  - 前端数据流里缺失 adapter / selector / formatter 分层
- 证据文件和函数
  - `backend/app/schemas/executive_dashboard.py::ExecutiveMetric`
  - `backend/app/schemas/executive_dashboard.py::PnlAttributionPayload`
  - `frontend/src/api/contracts.ts::ExecutiveMetric`
  - `frontend/src/api/contracts.ts::PnlAttributionPayload`
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/features/executive-dashboard/components/OverviewSection.tsx::OverviewSection`
- 建议修法
  - executive contract 改成 `raw numeric + unit + display hint`
  - 前端接一个集中 adapter，把数字、单位、缺省值、四舍五入统一到一处

## P2

### P2-1 Composition 饼图按绝对值占比展示，负向分量会被视觉上伪装成正向构成

- 问题描述
  - `PnlCompositionChart` 构造饼图时，对 `total_interest_income / total_fair_value_change / total_capital_gain / total_other_income` 都做了 `Math.abs`。
  - 如果某个分量为负，饼图仍然会给它正面积，只靠 tooltip 文本保留符号。
  - 这会导致“构成占比图”和上方卡片的正负语义脱节。
- 影响页面
  - `/pnl-attribution`
- 怀疑根因
  - 组件默认把饼图理解成“绝对值结构”，但页面没有明确标注
- 证据文件和函数
  - `frontend/src/features/pnl-attribution/components/PnLCompositionChart.tsx::PnLCompositionChart`
- 建议修法
  - 如果保留饼图，明确写成“绝对值构成占比”。
  - 若强调经营方向，改用带正负轴的条形图或 waterfall，不要用 pie。

### P2-2 当前两页几乎没有 dedicated selector / computed / adapter 层，排查和回归保护都很脆

- 问题描述
  - Dashboard 和 PnL Attribution 都大量把业务格式化、单位转换、图表组装散落在组件内部。
  - 一旦后端 contract 微调，页面多个组件会各自以不同方式 broken。
- 影响页面
  - `/`
  - `/pnl-attribution`
- 怀疑根因
  - 当前实现更接近 demo/page assembly，而不是“可审计的业务系统消费层”
- 证据文件和函数
  - `frontend/src/features/workbench/pages/DashboardPage.tsx::DashboardPage`
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx::PnlAttributionView`
  - `frontend/src/features/pnl-attribution/components/*.tsx`
- 建议修法
  - 每页增加 page-local adapter / selector 文件，不必先做全局重构。
  - 把单位、null/0、warning/fallback、chart/table row model 统一从组件中收束出去。

## 口径不明确、不能靠代码猜

1. Dashboard 首屏的 authoritative `report_date` 应该是谁决定：
  - 统一由页面筛选器指定
  - 还是由后端生成“同一报告日首页快照”
2. 首页“经营贡献拆解”和归因工作台“损益归因”是否允许是两套不同口径：
  - 如果允许，前端必须拆名称、拆叙事、拆日期提示
  - 如果不允许，必须统一数据源和 contract
3. 首页 Overview 的“资产规模 / 年内收益 / NIM / DV01”是否允许混合来自不同业务域：
  - formal balance
  - formal pnl
  - liability compat
  - bond analytics
  - 如果允许混合，页面必须显式告诉用户每张卡的 as_of_date 和来源
4. Executive 面是否接受“展示字符串 contract”：
  - 如果不接受，contract 必须回到 typed number + unit
  - 如果接受，前端数字正确性将长期不可审计

## 建议优先修复页面

- 第一优先建议修 `/`

原因：

- 它同时承载了当前最明显的数字可信度问题：
  - mock mode 默认回退
  - 无统一报告日
  - 缺少 warning / fallback / stale 展示
  - 请求 excluded surface
  - 静态 summary 和 demo 模块混排
- 用户对系统可信度的第一印象主要来自首页，首页不闭环，后续工作台再正确也很难建立信任。