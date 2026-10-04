# Frontend Layout Contract (Opt-In)

本文只用于新建页面或明确安排的布局迁移；局部样式修复不自动触发布局改造。视觉权威是 [DESIGN.md](../DESIGN.md)，任务分级、业务证据及验收命令统一使用 [frontend/AGENTS.md](../frontend/AGENTS.md)。已有页面按任务边界逐页接入，不以历史迁移名单判断当前状态。

## 1. 原则

每次只迁移一个页面/工作流，先确认要回答的业务问题和可观察验收条件。复用 `frontend/src/components/page/PagePrimitives.tsx` 及现有样式，跨页重复进入稳定原语，单页重复用局部样式；不为布局迁移改变指标定义、API 语义、adapter/selector 计算、日期/单位、路由或后端行为。

<a id="2-页面解剖默认顺序"></a>
## 2. 页面解剖（信息角色）

下表用于检查需要承载的信息，不要求每页七层或七张卡片。按主要任务选择、合并或省略不适用角色，可沿用等价组件；实际适用的[页面顺序锁](frontend-design-page-rules.md) 优先。

| 角色 | 主要内容 |
|---|---|
| Page Decision Hero | 首要问题、观察/报告日、有依据的结论和操作 |
| Data Status Strip | 来源模式、as-of、stale/fallback/mock |
| Filter Tray | 日期、组合、分类等实际筛选 |
| Kpi Band | 支撑主要问题的指标，单位明确、数字对齐 |
| Analysis Grid | 主表、主图及解释面板 |
| Evidence Panel | 业务指标页的来源/口径/血缘，可折叠 |
| Page State Surface | 对应数据状态及恢复操作 |

总览突出结论与变化，分析页让主图获得主要空间，查询页让筛选和主表易用；不为了凑角色添加空 hero、KPI 或状态卡。控件高度稳定。次要证据可折叠，不永久隐藏；重要风险、权限/使用限制与关键数据缺口仍在相关操作或结论旁可见。治理摘要仅在契约提供时呈现。

## 3. 栅格与断点

沿用 Ant Design 24 栅格或已有等价布局。主图配次要解释可用 16+8，主表可占 24；12+12 或 8+8+8 适合同等重要的比较，不是默认版式。同类 KPI 的 gap/padding 一致，表格沿用壳层与全局溢出规则。

| 宽度 | 默认行为 |
|---|---|
| ≥1280px | 按任务选择主辅栏或等分栏 |
| 992–1279px | 双栏或单栏优先 |
| 768–991px | 单/双栏，筛选允许折行 |
| <768px | 单栏栈叠 |

字号、内容不等高时的对齐和空态高度遵守 DESIGN §3/§5，不靠压缩字号维持列数。断点仅在任务涉及响应式时按影响范围验证。

## 4. 状态面（必须显式）

沿用 DESIGN §6 和前端 AGENTS 的指标状态要求。迁移不能隐藏无数据、加载失败、契约提供的 stale、fallback as-of、mock 模式或待确认定义；加载态不闪现错误结论。失败后的重试入口遵循现有产品约定。

## 5. 样式与令牌

使用 DESIGN 的 CSS/JS token 权威源及现有原语；跨页样式复用 `PagePrimitiveStyles.ts`、稳定全局 class 和 `PagePrimitives.tsx`，仅单页重复放 feature 样式模块。不另建色板或复制大块 inline。

## 6. Opt-In 兼容（与现有 primitives）

可复用 `PageDecisionHero`、`DataStatusStrip`、`KpiBand`、`KpiBandMetric`、`AnalysisGrid`、`EvidencePanel`、`PageStateSurface`；Filter Tray 角色沿用 `PageFilterTray`/`FilterBar` 或等价筛选区。v2 原语显式接入，未迁移页面维持现有行为与观感，不静默扩散全站改造。

## 7. 业务页迁移时的证据门禁

按 [frontend/AGENTS.md 的 Tier 1/2/3](../frontend/AGENTS.md#classify-the-change-first) 选择证据。纯布局不额外要求业务 MCP；触及指标链路时，说明受影响链路等价性或由测试锁定。数据目录仅在来源/可用性/日期有影响时使用，GitNexus 遵守根规则；工具不可用时记录本地替代证据及剩余风险。

## 8. 禁区（不因版式改动而触碰）

根 AGENTS 的受保护边界继续适用。布局任务不扩大为无关后端、基础设施、正式金融计算或其它页面的文案/导航重组；新端点仍放领域 client，不扩张 `src/api/client.ts`。

## 9. 迁移与验收清单（摘要）

按前端 AGENTS 完成定向验证和既有最终门禁，按 DESIGN §10.1 检查信息主次、阅读、图表和状态，并核对任务涉及的断点；不另要求每次跑所有宽度、所有 MCP 或业务测试。`style:audit` 是增量静态检查，不能独立证明设计合规；`style:inventory` 用于明确安排的样式盘点，不是每次页面修改的前置步骤。

## 10. 参考实现路径

以当前页面源码和 `PagePrimitives.tsx` 为准。[经营日报源码样板](frontend-design-page-rules.md#daily-home)展示经营概览、核心指标、归因与产品摘要如何分出主次；其它页面按自己的任务取用，不照搬顺序。只有追溯旧迁移过程时才读取下方记录及其中历史计划；历史验收输出不证明当前版本通过。

<details>
<summary>Phase 0–5 / Wave 2 历史迁移记录（非日常必读）</summary>

以下保留整理前的迁移记录。文中的“当前”“已完成”和名单均指原记录时期；接手时应定向核对目标页面，不能据此要求其它页面继续迁移。原检查命令和签收状态只属于历史批次，不覆盖上方现行分级规则。

**状态：** Phase 0–5 文档收口与 **Wave 2（经营分析 / 决策事项 / 跨资产驱动）代码迁移已完成**。**已挂载 v2 首屏 primitives（至少含 `PageDecisionHero`）的页面：**`DashboardPage`、`ProductCategoryPnlPage`、`MarketDataPage`、`BalanceAnalysisPage`、`OperationsAnalysisPage`、`DecisionItemsPage`、`CrossAssetDriversPage`。其余路由页仍为 **opt-in**，未挂载则保持 v1 行为与观感。

下一批认领前：用 `grep -r PageDecisionHero frontend/src` 与 `grep PageHeader frontend/src`（业务页应仅剩原语测试与 `PagePrimitives` 导出）刷新下表。

### 迁移状态 · 已实现（摘要）

| 页面 | Decision Hero | Data Status | Filter Tray（沿用 `PageFilterTray` / `FilterBar` 或等价筛选区） | Kpi Band | Analysis Grid（或等价主栅格 class） |
|------|---------------|-------------|------|----------|----------|
| 组合工作台 Dashboard | ✅ | ✅ | — | ✅ | ✅（`AnalysisGrid` + `dashboard-overview-command-grid`） |
| 产品分类损益 | ✅ | ✅ | FilterBar（既有） | — | （既有图表面板） |
| 市场数据 | ✅ | ✅ | FilterBar（既有） | ✅ | `.market-data-command-grid`（未换 `AnalysisGrid`，保留原有栅格样式） |
| 资产负债分析 | ✅ | （首屏刷新条等与既有等价，未强求 `DataStatusStrip`） | ✅ `PageFilterTray` | （首屏 KPI 沿用既有卡片） | （既有 workbook 栅格） |
| 经营分析 | ✅ | ✅ | ✅ `PageFilterTray`（占位筛选） | ✅ 首屏经营 KPI 带 | （既有 contribution / structure 栅格） |
| 决策事项 | ✅ | ✅ | ✅ 决策工作区内控件 | — | （既有表格与工作区面板） |
| 跨资产驱动 | ✅ | ✅（首屏条 + 「数据状态」`SectionCard`） | — | ✅ `cross-asset-kpi-band` | （既有 `cross-asset-drivers-page__flow`） |

### 迁移状态 · 下一批候选（认领时刷新）

认领下一页布局迁移时：**用 `grep -r PageDecisionHero` / `grep PageHeader`** 复核本文件表格；以下为历史 Wave 2 目标页，已完成并入上表。

### 已知例外与设计双线

- **`DESIGN.md` 单列锁顺序/密度的页面**（例如债券工作台相关首页）：迁移时须 **同时满足** 本契约与 `DESIGN.md`，不得单靠本文件覆盖产品版式权威。
- **观感「变化不明显」**：当前阶段主要为 **结构与类名收口**（`moss-page-v2-*`），**非**全盘换肤色；显性重绘须单独产品与工单。

### Phase 5 / Wave 2 验收

- [x] RALPLAN 状态与消费者描述对齐：`.omx/plans/ralplan-frontend-layout-system-2026-05-03.md`。
- [x] 本文件记录：**已迁移页 + 下一批候选占位 + 例外**。
- [x] **`npm run typecheck` / 定向 Vitest（本批相关页）/ `npm run debt:audit`**：`Wave 2` 合并前跑通并提供输出（或由合并 PR CI 兜底）。

历史计划：`.omx/plans/ralplan-frontend-layout-system-2026-05-03.md`；上下文快照：`.omx/context/frontend-layout-system-plan-20260503T055355Z.md`。记录更新时间以 git 履历为线索，当前实施状态以源码为准。

</details>
