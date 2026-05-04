# Frontend Layout Contract (Opt-In)

本文档定义 MOSS 前端**可逐步接入**的页面版式契约。权威视觉与色板仍以根目录 [`DESIGN.md`](../DESIGN.md) 与 `frontend/src/theme/designSystem.ts` 为准；本契约描述**页面解剖、栅格、断点、状态面与禁区**，供迁移页面对照实施。

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

---

## 1. 原则

1. **业务真值优先**：不改指标定义、API 语义、adapter、selector、计算、日期/单位口径、路由与后端行为。
2. **先契约后重绘**：先冻结本契约与 opt-in 原语，再逐页迁移布局与呈现。
3. **锚页参照**：工作台壳层与 **Dashboard（锚页）** 已形成可迁移参考实现；扩散至其它业务页时仍以 **一页一工单、`debt:audit` 不恶化** 为准。
4. **在源头消灭重复布局**：禁止用「新的页面级 CSS 混乱」替代「内联混乱」；跨页重复应进入 primitives 或稳定的全局 class。
5. **每页可验证**：测试、`npm run debt:audit`（不恶化）、浏览器多断点检视；业务页另需指标链路未改的证据（见第 7 节）。

---

## 2. 页面解剖（默认顺序）

除非该页有**已文档化的例外**，迁移后的首屏应按下述**区块角色**组织（与具体业务组件名解耦；实现时可对应 RALPLAN 中的 primitive 名）。

| 顺序 | 区块 | 职责 |
|------|------|------|
| 1 | **决策首屏区（Page Decision Hero）** | 页标题、**首要业务问题**、观察/报告日、主结论摘要、紧凑操作区。必须让「这一页首先要回答什么」一眼可见。 |
| 2 | **数据状态带（Data Status Strip）** | 数据源模式、报告日/as-of、stale / fallback / mock、治理或血缘摘要（若契约提供）。**不得**掩盖缺数或降级。 |
| 3 | **筛选托盘（Filter Tray）** | 日期、组合、类别、基数、币种、模式等；高度尽量稳定，筛选区不得压过主结论。 |
| 4 | **KPI 横带（Kpi Band）** | 首屏 **3–6** 个核心 headline 指标为上限；数字 tabular、单位显式（与 [`DESIGN.md`](../DESIGN.md) 数据字体一致）。 |
| 5 | **分析栅格（Analysis Grid）** | 主表、主图、叙述面板；使用下方「栅格预设」。 |
| 6 | **证据/下钻区（Evidence Panel）** | 来源、定义、血缘、审计或下钻上下文；**业务指标页必备**（可折叠，不可永久隐藏）。 |
| 7 | **一致状态面** | 见第 4 节。 |

**与 DESIGN.md 的关系：** 若某页在 `DESIGN.md` 中锁定了**区块顺序**（如债券分析首页），该页须**同时满足** `DESIGN.md` 的顺序与密度要求；本契约提供通用解剖，不覆盖已锁定的产品级版式权威。

---

## 3. 栅格与断点

### 3.1 栅格预设

- **主内容：** Ant Design 24 栅格；与现有 `Row` / `Col` 用法一致。
- **允许的分析区布局：**
  - **单栏**：12+12 叠放或单 Col 24。
  - **双栏**：12 + 12（常见主表 + 侧栏）。
  - **三栏**：8 + 8 + 8（大桌面；与 `DESIGN.md` 三列区一致方向）。
- **KPI 横带：** 使用统一 gap（与 `designTokens.space` 一致），同一横带内卡片 padding 与 gap 一致。
- **表格区：** 遵守壳层与 `global.css` 中已有表格溢出/包含规则，不在域内另起冲突的 max-width 除非与壳冲突已文档化。

### 3.2 断点（与实现一致）

| 档位 | 参考宽度 | 行为 |
|------|----------|------|
| 大桌面 | ≥1280px | 允许三栏 8-8-8 等高密度布局 |
| 标准桌面 | 约 992–1279px | 优先改为 12+12 或单栏优先，保持字号可读 |
| 平板 | 约 768–991px | 以单栏 / 双栏为主，筛选托盘允许折行 |
| 移动 | <768px | 单栏栈叠；**禁止**为保住多列而将数据字号压到 `DESIGN.md` 可读底线以下 |

---

## 4. 状态面（必须显式）

以下状态须在业务页可被感知（文案/标签/占位符皆可，但不可用演示数冒充正式口径）：

| 状态 | 要求 |
|------|------|
| 无数据 | 明确空态，不展示伪造正式指标 |
| 加载中 | 骨架屏或等价，不闪烁错误结论 |
| 加载失败 | 错误信息与重试入口（若产品有约定） |
| 过期/陈旧 | stale 明示（契约字段存在时） |
| Fallback 日期 | 使用的 fallback as-of **必须可见** |
| Mock / 演示模式 | 若为 mock，必须标注 |
| 指标定义待定 | 「待业务确认」等，不得装作已定口径 |

动画仅用于状态切换与聚焦，遵循 `DESIGN.md` Motion 一节（minimal-functional）。

---

## 5. 样式与令牌

- **数值色板 / 间距 / 圆角 / 动效：** 仅取自 `frontend/src/theme/designSystem.ts` 及既有 `shellTokens`，不引入第二套语义色。
- **数据字体：** KPI 与表格数字使用 tabular + `tabular-nums`，与 DESIGN 一致。
- **重复样式：**
  - **跨页重复** → `PagePrimitiveStyles.ts`、稳定全局 class、`PagePrimitives.tsx` 的 opt-in 导出。
  - **仅单页重复** → 该 feature 下的局部样式模块（如 `*.module.css`）或页内常量，但不要复制粘贴大块 inline。

---

## 6. Opt-In 兼容（与现有 primitives）

当前已有（非穷举）：`PageHeader`、`PageSectionLead`、`PageFilterTray`、`PageSurfacePanel`、`PageV2Shell`、`PageV2SurfacePanel` 等。

- **契约 v2 primitives**（实现见 `frontend/src/components/page/PagePrimitives.tsx`：`PageDecisionHero`、`DataStatusStrip`、`KpiBand`、`KpiBandMetric`、`AnalysisGrid`、`EvidencePanel`、`PageStateSurface`）须以 **增量、显式引用** 方式接入。**筛选托盘**在实现层继续沿用既有 `PageFilterTray`，与契约「Filter Tray」角色同义。
- **未引用 v2 primitives 的页面默认行为不变**（包括视觉），避免静默改变线上观感。

---

## 7. 业务页迁移时的证据门禁

当触及指标展示链路（adapter、formatter、selector、数据获取路径或可见指标呈现）时：

1. **必须可陈述：** `API 响应 → adapter/transformer → state → selector/computed → 组件 → 表/图` 与迁移前等价，或由测试锁定。
2. **MCP 证据（与 `AGENTS.md` 对齐）：** 在决定实现形态前，应使用 `moss-metric-contracts`、`moss-lineage-evidence`、`moss-data-catalog`、`gitnexus`；若变更影响可见前端行为，应使用 `playwright` 做浏览器级核对。若某 MCP 不可用，须在 PR/记录中写明**哪项不可用、沿用的本地证据、残留风险**；不得在无证据时猜测指标定义、单位、日期或血缘。
3. **禁止猜测**指标定义、单位、日期语义与血缘。

---

## 8. 禁区（不因版式改动而触碰）

以下内容不在本契约实施范围内（除非单列工单）：

- 后端 API、数据库 schema、认证与权限底座、队列/调度/缓存基础、全局 SDK 封装、无关的基础设施重构。
- **禁止**无序扩张 `frontend/src/api/client.ts`（新端点放域内 client 模块）。
- **禁止在前端「补算」正式金融口径**（与 `AGENTS.md` / `CLAUDE.md` 一致）。
- 无关页面的文案/导航语义重组。

---

## 9. 迁移与验收清单（摘要）

每一迁移页结束前：

- [ ] 首屏回答一个主业务问题；主结论在决策首屏区可见。
- [ ] 状态面齐备（与该页数据契约一致）。
- [ ] `npm run debt:audit`（`frontend/`）不恶化。
- [ ] 针对性测试（adapter/formatter/selector/state 任一被触及则增补最小测试）。
- [ ] 桌面 / 平板 / 移动宽度浏览器检视通过。

---

## 10. 参考实现路径

执行顺序见：`.omx/plans/ralplan-frontend-layout-system-2026-05-03.md`（Phase 0–5）；**实施后状态**以此文件顶部 **Status** 为准。

上下文快照：`.omx/context/frontend-layout-system-plan-20260503T055355Z.md`。

**Phase 5 文档收口：** 迁移表与本节（§ 迁移状态 / 下一批候选）与 `RALPLAN` 同步更新时间以 git 履历为准。
