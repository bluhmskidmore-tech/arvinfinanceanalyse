# 2026-08-27 前端系统级优化计划（方向 A 全站落地）

- 状态：待 owner 确认分期与开放问题后分批施工
- 日期：2026-08-27
- 定位：本计划是 `docs/prd-workbench-visual-noise-convergence.md`（降噪 PRD，执行中）的**系统级承接与扩展**，不是替代。降噪 PRD 解决"信息放错层"与样板页质感；本计划回答"方向 A 如何变成全站制度"——共享层清账、原语收敛与退役、全部页面的滚动顺序与验收口径。凡降噪 PRD 已定义的需求（FR-1~FR-6），本计划只标注其当前状态并安排收尾，不重新发明。
- 技术栈不变：React 18 + Ant Design 5 + ECharts 6 + AG Grid 35。观感问题在呈现层执行，已由 2026-08-27 六页截图走查证实（`output/ui-review/`）。

---

## 0. 一段话结论

系统的共享层（Nocturne 主题体系、壳层、`components/layout` 视觉原语）已经达到机构终端应有的质量，且降噪 PRD 第 1 期（壳层横幅降级 + 子导航收敛）与 FR-6 样板页的 hero/KPI 两项**已在本地未提交改动中落地**（`WorkbenchShell.tsx` 治理胶囊 + 单行子导航、`bond-dashboard` 结论 hero + `KpiStrip size="hero"`，实况见 `output/ui-review/final-bond-dashboard.png`）。真正的系统性差距有四类：①两代页面原语并存（`components/page` 旧代 vs `components/layout` 新代），约 10 个页面私有 KPI 带/分区头未迁移；②约 9 个页面业务区仍内联契约技术标识（FR-2 未动工）；③次级页色彩纪律与空态收缩未按 checklist 滚动（FR-4/FR-5 未动工）；④方向 A 的质感升级目前只存在于一个样板页，缺少"全站 checklist + 滚动顺序 + 每批验收"的制度。本计划按 P0~P7 八期推进，每期独立可验收、可上线，全程不触碰口径、API、`result_meta` 与 §9 顺序锁。

---

## 1. 现状诊断

### 1.1 共享层盘点（结论：基座合格，欠清账）

**主题体系（合格，有零星尾工）。** `frontend/src/styles/tokens.css`（39.5KB）维护 37 个 canonical Nocturne scope 的三分列色板（页根 / 外壳 grid / ThemedRouteBoundary），`frontend/src/theme/themeScopes.ts` 字面量联合在编译期挡死拼写死 scope，`theme.test.ts` 做值级 parity 断言；`designSystem.ts` 提供 `nocturneTokens` 镜像给 canvas/ECharts。AntD `workbenchTheme` 已全量切 `nocturneTokens`（DESIGN.md 结论 9）。深色盈亏着色入口 `src/utils/tone.ts::TONE_DH_CSS_VAR` 已有明确纪律（结论 6）。尾工：`--moss-color-warning-200` 深色映射收敛在未提交第 23 组（`fix(theme)`）中，落库即闭合；约 57 个色板变量的页根重声明块仍需按结论 17 的"逐变量取值分布"方法论清理，不能一刀切。

**壳层（功能完备，欠登记收口与文案清账）。** `frontend/src/layouts/WorkbenchShell.tsx` 当前本地版本已实现：治理横幅降级为「治理 · 契约收口中」胶囊 + 点开详情（`workbench-governance-pill`，FR-1 的实现形态）；组内子导航单行内联上限 7 项 + 「更多」下拉（`SUBNAV_MAX_INLINE`，FR-3 的实现形态）。壳层变体清单大部分已提炼到 `workbenchShellSections.ts` 并被 `theme.test.ts` parity 锁定（结论 14），但 `institutionalConsoleShellSectionKeys`（cross-asset / ledger-pnl / product-category-pnl / pnl-attribution 四项）仍硬编码在组件文件内，未进登记模块。壳层文案有两处违反 DESIGN.md §7 的技术/英文微标签：组合工作台导流卡眉标 `Suggested Flow`（英文出现在业务叙述位）、终端条报告日 chip 缺省值渲染为「报告日 默认路由」（把路由概念暴露给业务用户）。

**视觉原语（新代成熟，两代并存）。** 新代 `frontend/src/components/layout/`：`SectionHead`（CSS counter 编号 + 外接编号域 + 开发期自检）、`KpiStrip`（`hero` 尺寸档、`spark` 迷你走势、格级状态、valueTone）、`SectionGrid`、`StateSurface`（五态 + 去重配额）、`DataTable`、`statusBridge`，边界注释完整，组件自包含 CSS module，页面失去写歪的能力——这是方向 A 全站滚动的正确底座。旧代 `frontend/src/components/page/`：`PagePrimitives`（`PageDecisionHero` / `DataStatusStrip` / `KpiBand` / `AnalysisGrid` / `EvidencePanel`）、`SectionLead`（`PageSectionLead`）、`FormalResultMetaPanel`、`DataQualityBanner`、`PageAsyncSection` / `PageDataSection`。其中 `FormalResultMetaPanel`（证据层元数据面板）、`DataQualityBanner`、`PageAsyncSection/PageDataSection`（懒加载占位背板）职责与新代不重叠，应保留；`PageSectionLead` 与 `PagePrimitives.KpiBand` 与新代职责重叠，属退役对象（见第 4 节）。

**护栏工具链（齐备）。** `npm run debt:audit` 已串联六个审计（frontend_debt / visual_tokens / font_size_floor / encoding_integrity / section_numbering / undeclared_css_vars）；`style:audit` 增量拦截非 token hex 与私有阴影；`test:a11y-smoke`（Playwright）覆盖导航可达性；`docs/frontend-layout-contract.md` 提供未锁序页面的默认解剖。

### 1.2 页面层盘点（结论：收敛进行中，进度不均）

**共享原语收敛（进行中，本地未提交）。** 约 40 个 feature 文件已改从 `components/layout` 导入。已删除私有分区头的页面：bond-dashboard（`BondDashboardKpiBand`/`BondDashboardSectionLead` 删除，未提交第 6 组）、balance-analysis（`BalanceSectionHead` → `balanceSectionNumbering.ts`）、bond-analytics（`SectionLead` 删除）、liability-analytics（`LiabilitySectionLead` 删除）、macro-observation（`MacroObservationSectionLead` → `macroObservationSectionHeadNumbering.ts`）、average-balance（`adbSectionHeadNumbering.ts`）。**这是在途工作，本计划不重复提出，只安排收尾与验收。**

**尚未迁移的私有实现（本计划第 4 节的收敛对象）。** 旧代 `PageSectionLead` 仍被 macro-toolkit（约 8 个 section 文件）、`MarketDataPage.tsx`、`PnlByBusinessPage.tsx` 消费；私有 KPI 带仍存在：`AdbKpiStrip`（average-balance，纯重复）、`MacroObservationKpiBand`（当初因缺 valueTone 保留，如今 `KpiStrip` 已支持）、`CrossAssetKpiBand`、`InstitutionalKpiTile`（workbench/shared）、`LiabilityMonthlySnapshotCards` 等（后两者需逐页核对是否真是 KPI 横带语义）。

**FR-2 残量（业务区内联契约标识，grep 初筛，实施时按"首屏无技术字符串"全量排查）。** `positions/components/PositionsView.tsx`（5 处，GAP-POS-LIST/MTR-POS-00x/GS-POSITIONS-* 直接渲染在当日结论下方，实况见 `output/ui-review/shell-after-positions.png`）、`ledger-pnl/pages/LedgerPnlPage.tsx`（3 处）、`product-category-pnl/pages/ProductCategoryFormalReadinessBand.tsx`（3 处）、`platform-config/PlatformConfigPage.tsx`（3 处）、`risk-tensor/RiskTensorPage.tsx`（1 处）、`news-events/NewsEventsPage.tsx`（1 处）、`stock-analysis/components/StockAnalysisBoundaryWorkbenches.tsx`（1 处）、`balance-analysis/pages/balanceAnalysisPageModel.ts`（2 处，需确认是否上首屏）。对照项：bond-dashboard 的 4 处全部在 `EvidenceSection`（证据层），是合规样板。

**FR-4/FR-5 残量。** balance-analysis 首屏：紫色主按钮（`balance-analysis-btn--primary` 导出 Workbook）+ 黄色质量胶囊 + 风险全景红黄绿徽章墙并存（`output/ui-review/balance-analysis.png`）；market-data 右侧「关键利率 / 资金指标」面板一行数据大片空白（`output/ui-review/market-data.png`）。注意：market-data 正被并行会话整页重构（未提交第 12 组，tape cockpit → 宏观序列终端，-4800 行），**FR-5 必须落在新版页面上，不要在旧实现上返工**。

**FR-6 样板页（部分落地）。** bond-dashboard 已实现：结论区 hero 大数字（复用 KPI 带持仓规模格）+ 结论句、`KpiStrip size="hero"`（主值 24-28px）。未实现：KPI 卡内嵌迷你 sparkline、区块级面积图（概念稿 `after-bond-dashboard.png` 中的「组合规模趋势」）。**根因是数据依赖而非前端欠账**：`frontend/src/api/contracts/bondDashboard.ts` 的 bundle 22 个 section 全部是单报告日截面，没有任何时序 section，前端无数据可画（`KpiStrip` 的 `spark` prop 明确禁止常数兜底序列）。此项需要 owner 决策（见第 8 节 Q5）。

### 1.3 与 DESIGN.md 的真实差距（按权威条款对账）

1. **§6 溯源标识分层**：外壳侧已闭合（治理胶囊），页面侧未闭合（1.2 节 FR-2 残量清单）。
2. **§4 Color Consistency Lock / 结论 17 常态收声**：balance-analysis 为代表的次级页未执行；旗舰页（经营日报首页）已执行到位，证明是执行差异不是规范缺失。
3. **§5 空态收缩**：`StateSurface` 原语已具备收缩能力，但存量页面手写空白面板未替换（market-data 为代表）。
4. **§7 文案语域**：壳层 `Suggested Flow`、「报告日 默认路由」两处；各页面滚动时需按 §7 通读自审。
5. **§3 字号 Scale**：DESIGN.md 目前写「KPI 主值 20–24」，而方向 A 样板页已用 24-28（`KpiStrip` hero 档）。按降噪 PRD FR-6 验收条款，样板页验收通过后**必须回写 DESIGN.md**，否则权威文件与实现漂移（见 Q4）。
6. **结论 18（`--ib-radius` 2px 残留）**：六个共享文件（`Skeletons.tsx`、`PageAsyncSection.css`、`PageDataSection.css`、`workbenchShell.css` 的 `.moss-page-v2-*`、`agGridInstitutional.css`、`dashboardCockpit.css`）在 loading/空态/重试界面仍渲染 2px 锐角，与 Nocturne 8px 制度不一致，常规走查看不到，需专门触发验收。
7. **两代原语并存**本身是对"数值单一来源"精神的偏离：同一"KPI 横带"语义存在 `KpiStrip`（新）、`PagePrimitives.KpiBand`（旧）、多个页面私有实现三层，必须给出退役表（第 4 节）。

### 1.4 在途工作定位（衔接，不重复，不推翻）

| 在途工作 | 状态 | 本计划的动作 |
|---|---|---|
| 降噪 PRD 第 1 期（FR-1 胶囊 + FR-3 子导航） | 已在本地实现，未提交、未走完验收 | P1 安排验收收尾（测试断言、a11y、截图、Q1/Q2 结论回写 PRD） |
| 降噪 PRD 第 2 期（FR-2 脚注收敛） | 未动工 | P2 按页执行 |
| 降噪 PRD 第 3 期（FR-4 色彩） | 未动工 | P4 按页执行，前置 Q3 |
| 降噪 PRD 第 4 期（FR-5 空态） | 未动工 | P5 按页执行，等 market-data 重构落库 |
| FR-6 样板页 | hero + KPI hero 档已落地；spark/面积图缺数据 | P3 收尾 + Q5 决策 |
| 共享原语收敛（SectionHead/KpiStrip 等） | 大范围进行中（未提交第 6 组及多页改动） | 视为进行中工作，P0 落库，P7 只做剩余页迁移与退役 |
| market-data 整页重构（未提交第 12 组） | 并行会话在途 | 不碰旧页；FR-5 与方向 A 滚动均落在新版上 |
| 未提交工作拆分手册（30 组） | `docs/plans/2026-08-27-uncommitted-work-split-plan.md` | P0 硬前置：与视觉相关的组先落库再施工 |

---

## 2. 目标视觉：方向 A 变成全站 checklist

方向 A（精致深色终端）在样板页的四项手法——hero 结论数字、KPI 主值升档、留白放宽、区块级主图——要变成**每页滚动时逐条打勾的验收清单**，而不是 bond-dashboard 的一次性装修。全站 checklist 如下（每页迁移工单必须逐条给出证据，不适用项写明原因）：

1. **首屏答题**：页面第一屏回答该页的首要业务问题；结论区在 KPI 之前（`frontend/AGENTS.md` 首条 + 布局契约解剖顺序）。§9 顺序锁页面维持锁定顺序，其余页面按 `docs/frontend-layout-contract.md` 解剖。
2. **结论 hero**：有单一核心读数的页面，首屏结论区用 40px 级等宽大数字 + 一句结论（P3 沉淀的共享原语，禁止逐页手写）。没有单一核心读数的页面（如列表工作台）不硬造 hero。
3. **KPI 横带**：统一 `KpiStrip`，首屏横带用 `size="hero"`（主值 24-28px，标签 11-12px muted）；非首屏横带用默认档。有历史序列的 KPI 传 `spark`，无序列不造假数据。
4. **留白与密度**：首屏面板 padding 16-24px、区块间距 24px 级；下钻区/表格区维持 compact 密度（12-15px），不把全页拉稀。
5. **主强调色唯一**：全页可交互强调只用 `--dh-api-blue`（Nocturne #9184d9），次级操作 ghost/线框；语义色只出现在真实异常与涨跌语义处，常态徽标收声为 muted/暗点（结论 17）。
6. **盈亏与利率色**：盈亏走 `TONE_DH_CSS_VAR`；市场利率序列变动读数按结论 20（上行=琥珀、下行/零值=muted），禁止涨绿跌红。
7. **无技术字符串**：首屏（1440×900 第一屏）不出现 contract ID、sample ID、API 路径、布尔字段名、中英混排微标签；此类内容收进证据层（`FormalResultMetaPanel`、EvidenceSection、治理胶囊详情、tooltip）。
8. **空态收缩**：0 条数据分组收缩到 ≤120px 消息框（`StateSurface`），懒加载占位带背板与真实高度（`PageAsyncSection` 模式），无零值假图。
9. **五态可感知**：loading / 空 / 错 / stale / partial 齐备且用 `statusBridge`/`StateSurface` 的统一形态；同一状态事实全页 ≤2 处。
10. **文案自审**：一页一语域（简体中文业务语言）、单行 ≤1 个 `·`（`SectionHead` meta 已内建配额）、无装饰性微元句、无 AI 味修辞。

其中 2/3/4 是方向 A 新增的质感条款，5-10 是 DESIGN.md 既有纪律——合在一张 checklist 里，是为了让每页只走查一次。

---

## 3. 信息架构

**一级导航（不动结构，只清文案）。** 六分组（经营日报 / 组合 / 市场 / 风险 / 绩效 / 报表与数据）+ 各组模块首页的架构已经成立且被 `workbenchShellSections.ts` + `theme.test.ts` 锁定，本计划不重组。P1 只清理壳层文案（1.1 节两处）与把 `institutionalConsoleShellSectionKeys` 迁入登记模块。

**子导航（维持现实现，留 Q2 决策口）。** 单行 ≤7 内联 + 「更多」下拉已落地，满足降噪 PRD "单行、不换行"的空间约束。侧栏二级导航方案仍是 Q2 的备选——若 owner 后续选择侧栏二级，属壳层 Tier 3 改动，另立工单，本计划不预支。

**首屏结论区（页面层制度）。** 每页首屏按「结论区（hero 或结论句）→ KPI 横带 → 分析栅格」组织；筛选托盘高度稳定、不压结论。§9 锁定页（债券分析/组合工作台首页、经营日报首页）顺序不动，方向 A 只作用于色板、字号、密度（与结论 19 的历次先例一致）。

**证据层分层（四级）。** ①壳层治理胶囊详情：路由级"临时例外"声明与 readiness 说明；②页面证据区块：`FormalResultMetaPanel`（result_meta、basis、quality_flag、时间戳语义）与 EvidenceSection 类区块承载 contract/sample ID、API 路径；③区块头 tooltip：口径/来源一句话说明（`SectionHead` meta 的 `title` 位）；④正文兜底：最多一个安静状态点 + 一句中文说明（如"部分指标待业主确认"）。FR-2 的全部迁移按此四级归位，不新造第五种容器。

---

## 4. 共享原语清单：收敛什么、不新造什么、退役什么

### 4.1 目标原语（唯一实现，全站收敛到它们）

| 语义 | 目标原语 | 状态 |
|---|---|---|
| 编号分区头 | `components/layout/SectionHead`（stack/外接双编号域） | 已成熟，约 40 文件在用 |
| KPI 横带 | `components/layout/KpiStrip`（default/hero 双档、spark、格级状态） | 已成熟 |
| 分区栅格 | `components/layout/SectionGrid` | 已成熟 |
| 五态面板 | `components/layout/StateSurface`（+ 去重配额） | 已成熟 |
| 简单数据表 | `components/layout/DataTable`（排序/固定列/虚拟滚动回退 AG Grid） | 已成熟 |
| 状态桥接 | `components/layout/statusBridge` | 已成熟 |
| 结论 hero | **P3 新增**（从 bond-dashboard 页面局部实现抽取进 `components/layout`） | 待沉淀 |
| 证据层元数据 | `components/page/FormalResultMetaPanel` | 保留，职责不重叠 |
| 懒加载占位背板 | `components/page/PageAsyncSection` / `PageDataSection` | 保留（需修 2px 圆角残留，见 1.3 条 6） |
| 数据质量横幅 | `components/page/DataQualityBanner` | 保留 |
| 治理胶囊 + 详情 | `WorkbenchShell` 内建（`workbench-governance-pill`） | 已落地 |
| 缺值/语气/格式 | `src/pageModel`（`EM_DASH`、`MetricTone`、`buildStateSurfaces`）+ `src/utils/format.ts` + `src/utils/tone.ts` | 已成熟 |

### 4.2 明确不新造

- 不新造第二个分区头、第二个 KPI 带、第二个空态面板、第二个证据面板；页面确有新形状时先证明"该形状在 ≥3 页重复"再进原语层（`frontend/AGENTS.md` 的 pageModel 扩展纪律同理）。
- 结论 hero 原语化之前，**不允许**其他页面复制 bond-dashboard 的 `__conclusion-hero` 页面局部 CSS——这正是当年 20 页各写一遍 KPI 带的复发路径。
- 不为方向 A 新造图表主题：ECharts 统一 `nocturneChartTheme`/`nocturneTokens`（结论 12），面积图/迷你线全部走既有取色。
- 不新造治理信息容器：FR-2 迁移只用 3.4 节四级既有容器。

### 4.3 退役表（迁移完成即删，删除动作计入对应页面工单）

| 退役对象 | 剩余消费方 | 承接原语 |
|---|---|---|
| `components/page/SectionLead`（`PageSectionLead`） | macro-toolkit 约 8 个 section 文件、`MarketDataPage.tsx`（第 12 组重构中）、`PnlByBusinessPage.tsx` | `SectionHead`（macro-toolkit 用外接编号域渐进迁移，机制已内建） |
| `PagePrimitives.KpiBand` / `KpiBandMetric` | 布局契约 v2 存量页 | `KpiStrip` |
| `AdbKpiStrip` | average-balance | `KpiStrip` |
| `MacroObservationKpiBand` | macro-observation（保留理由 valueTone 已被 KpiStrip 吸收） | `KpiStrip` |
| `CrossAssetKpiBand` | cross-asset | `KpiStrip` |
| `InstitutionalKpiTile` | workbench/shared 消费方 | `KpiStrip`（先核对是否 KPI 横带语义，不是则不硬迁） |
| `PageDecisionHero`（v2 契约 hero） | 布局契约 v2 存量页 | P3 结论 hero 原语（评估后二选一，避免双 hero 并存） |

退役次序服从页面滚动次序（第 5 节）：迁一页、删一处、`debt:audit` 基线只降不升；不搞一次性大爆炸替换。

---

## 5. 页面滚动顺序与批次验收

滚动原则：样板页 → 旗舰页 → 次级页；一页一工单一提交；每页按第 2 节 checklist 全量走查（含该页 FR-2/FR-4/FR-5 残量，一次进场做完，避免同页反复施工）。

**批次 A（样板收口）：** `/bond-dashboard`（P3 收尾）。
**批次 B（旗舰页，验收方向 A 制度）：** `/`（经营日报，§9.2 顺序锁，预期只有文案与常态收声微调）→ `/pnl`（正式损益，已开放主链路）→ `/balance-analysis`（叠加 FR-4 首批）→ `/positions`（叠加 FR-2 首批）→ `/product-category-pnl` → `/ledger-pnl`。
**批次 C（组合工作台次级页）：** `/liability-analytics` → `/average-balance`（含 AdbKpiStrip 退役）→ `/balance-movement-analysis` → `/bank-ledger-dashboard` → `/pnl-bridge` → `/pnl-attribution` → `/pnl-by-business`（含 PageSectionLead 退役）→ `/pnl-by-business-insights` → `/bond-analysis` → `/bond-trading-desk` → `/decision-items`。
**批次 D（市场工作台）：** `/market-data`（第 12 组落库后，叠加 FR-5 首批）→ `/market-overview` → `/macro-observation`（含 MacroObservationKpiBand 退役）→ `/macro-toolkit`（PageSectionLead 渐进迁移收尾）→ `/cross-asset`（含 CrossAssetKpiBand 退役）→ `/stock-analysis` → `/news-events`。
**批次 E（风险/绩效/报表）：** `/risk-overview` → `/risk-tensor` → `/concentration-monitor` → `/cashflow-projection`（久期缺口色语义红线，结论 4）→ `/performance` → `/kpi` → `/team-performance` → `/reports` → `/cube-query` → `/platform-config`。

**每批验收标准（批内每页逐页出证据）：**

1. 1440×900 真实截图（改前/改后）归档 `output/ui-review/`，命名带页面与日期。
2. 首屏无技术字符串（contract/sample ID、API 路径、布尔字段名、中英混排微标签），以截图 + DOM 断言双重证明。
3. 全页主强调色唯一；语义色仅真实异常与涨跌/利率语义。
4. 空态分组收缩 ≤120px 级；loading 占位不重排（专门触发 loading/空态/错误态截图，覆盖结论 18 的非常态界面）。
5. 该页 targeted Vitest 绿；`npm run debt:audit` 不恶化（原语退役页应下降）；lint/typecheck 绿。
6. 数值、口径、导出/交互行为零变化（既有功能测试通过；触及 adapter/selector 时按 Tier 2 补最小测试）。

---

## 6. 分期（每期独立可验收、可上线）

| 期 | 内容 | Tier | 依赖 | 验收出口 |
|---|---|---|---|---|
| **P0 前置收口** | 按 `docs/plans/2026-08-27-uncommitted-work-split-plan.md` 落库未提交工作；与本计划强相关：第 6 组（bond-dashboard 原语重构）、22（tailwind 移除）、23（theme 深色映射）、27（DESIGN 决策外迁）；第 12/25 组等并行会话收口后落库 | 按各组自定 | 并行会话收口 | 各组提交前验证命令绿；工作树可分辨新增改动 |
| **P1 壳层验收与清账** | ①FR-1/FR-3 验收收尾：`WorkbenchShell.test.tsx` 断言对齐胶囊+下拉、`test:a11y-smoke`、六分组代表页截图、Q1/Q2 结论回写降噪 PRD；②壳层文案清账：`Suggested Flow` 中文化、「报告日 默认路由」改为业务语义或隐藏；③`institutionalConsoleShellSectionKeys` 迁入 `workbenchShellSections.ts` | **Tier 3（共享壳层，GitNexus 影响分析先行，HIGH/CRITICAL 先警告）** | P0 | 18 个 temporary-exception 路由首屏无横幅、治理文案抽屉可达（DOM 断言）；子导航 ≤48px 高、17 项全可达；a11y 绿 |
| **P2 治理脚注收进证据层（=PRD 第 2 期 FR-2）** | 逐页迁移：positions → ledger-pnl → product-category-pnl → platform-config → risk-tensor → news-events → stock-analysis → balance-analysis（model 层 2 处确认）→ 全库 grep 复查收口 | Tier 2 逐页 | P1（治理胶囊作为兜底容器已就绪） | 每页首屏无技术字符串 + 证据层可达断言 + 页面测试更新 |
| **P3 样板页收尾与 hero 原语沉淀** | ①Q5 决策后处理 spark/面积图（有数据依赖）；②抽取结论 hero 进 `components/layout`（含与 `PageDecisionHero` 的归一决策）；③DESIGN.md §3 回写 KPI 双档字号 + hero 条款（Q4，owner 签字） | Tier 1/2；若加后端时序 section 则后端侧另立只读读模型工单（api/services/repo，非 core_finance） | P0 第 6 组 | 样板页 1440×900 与概念稿方向一致；`KpiStrip`/hero 原语测试绿；DESIGN.md 更新合入 |
| **P4 色彩纪律滚动（=PRD 第 3 期 FR-4）** | balance-analysis 首批（主按钮唯一、质量胶囊常态收声、风险全景徽章分级）；随批次 B-E 滚动到 positions、liability-analytics、cube-query、kpi、news-events、platform-config 等 | Tier 1 逐页 | **Q3（徽章"真实异常"口径）拍板** | 每页截图证明语义色仅真实异常/涨跌；功能行为零变化 |
| **P5 空态收缩滚动（=PRD 第 4 期 FR-5）** | market-data 首批（在第 12 组新版页面上）；随后全站空态走查，替换手写空白面板为 `StateSurface` 收缩模式；专项触发六个 2px 圆角残留文件的非常态界面并修复（结论 18） | Tier 1 逐页 | 第 12 组落库 | 空态截图对比 + 有数据回归不受影响 |
| **P6 旗舰页方向 A 滚动** | 批次 B 六页按第 2 节 checklist 逐页施工验收 | Tier 1/2 逐页 | P3（hero 原语就绪） | 第 5 节批次验收标准 |
| **P7 次级页滚动与原语退役** | 批次 C/D/E 逐页施工；按 4.3 退役表迁一页删一处；结项时 `PageSectionLead`、私有 KPI 带全部删除，debt 基线净下降 | Tier 1/2 逐页；涉及 `components/page` 删除时按 Tier 3 跑 GitNexus | P6 完成主体 | 退役表清零 + `debt:audit` 基线下降 + 全站 checklist 抽查 |

说明：P2/P4/P5 与 P6/P7 在页面粒度上合并进场（第 5 节"一次进场做完"），分期编号表达的是**验收口径与依赖**，不是同一页要施工五次。P1 是唯一的共享层改动期，之后全部是页面局部，符合"最小可审改动、一页一主题"。

---

## 7. 明确不做

1. 不换技术栈、不引入新 UI 库/图表库/CSS 框架（tailwind 移除组落库后不回头）。
2. 不做浅色回退，不新增第三套主题；IB 浅色仅存量例外，方向 B 已否决。
3. 不做移动端适配；断点行为维持布局契约 §3.2。
4. 不改业务口径、指标计算、API 契约、`result_meta` 结构；前端不重算正式指标。
5. 不删治理机制：`readiness`/`governanceStatus` 数据结构、页面契约收口流程、审计流全部保留，改的只是呈现容器。
6. 不碰 DESIGN.md §9 区块顺序锁两页的信息区块顺序。
7. 不扩散装饰性动效：全站唯一无限循环豁免仍是经营日报 hero 呼吸光（结论 3）；方向 A 的质感升级不含新增循环动效，交互动效走 `designTokens.motion` + reduced-motion。
8. 不做平台化重构：不重写壳层布局引擎、不做通用"页面生成器"、不为假想需求扩展原语 props。

---

## 8. 风险与需 owner 拍板的问题

**承接降噪 PRD 的未决问题（不假装已决策）：**

- **Q1（承接）**：「临时例外」免责声明从首屏横幅降级为"胶囊 + 抽屉"**已按此形态实现但未获追认**。若审计/合规要求首屏强可见，回退方案是单行 muted 细横幅。P1 验收前必须拿到结论——这是当前最大的返工风险，因为实现已先行。
- **Q2（承接）**：子导航现落地为"单行 + 更多下拉"。侧栏二级导航仍是备选；若 owner 改选，属另立 Tier 3 工单，不阻塞本计划其余部分。
- **Q3（承接）**：FR-4 风险全景徽章"真实异常"的判定口径需要产品分级规则。无规则前 P4 不动色彩语义，只做主按钮唯一化等无口径争议项。

**本计划新增的决策点：**

- **Q4（新增）**：DESIGN.md §3「KPI 主值 20–24」需按方向 A 回写为双档（default 20-24 / hero 24-28）并新增 hero 结论数字条款。设计权威变更需 owner 签字，建议随 P3 样板页验收一并批。
- **Q5（新增）**：FR-6 的 KPI 迷你趋势线与区块级面积图存在**真实数据依赖**——bond-dashboard bundle 无任何时序 section。选项 a：后端新增只读 headline 时序 section（api/services/repo 只读读模型，不触 core_finance，需要后端排期）；选项 b：样板页验收范围收窄为 hero + KPI 档 + 留白三项，时序视觉列为待数据项。两个选项都不造假数据。
- **Q6（新增）**：`PageDecisionHero`（布局契约 v2）与 P3 结论 hero 原语是否归一为一个实现。建议归一（避免双 hero），但涉及布局契约存量页回改量，P3 评估后给出成本再定。

**执行风险：**

1. **未提交基线漂移**：拆分手册记录并行会话仍在产出（第 30 组活动快照）。缓解：P0 严格执行"收口判定（两次 status 一致）"，本计划各期开工前重跑差集核对。
2. **治理可见性回退**：FR-2 收敛过度会违反 §6 五态齐备。缓解：每页验收含"证据层可达"正向断言，先加新容器再撤旧文案。
3. **测试断言连带面**：壳层与 18 个路由的既有断言在 P1/P2 需同步更新。缓解：优先用 `data-testid` 稳定选择器；`readiness 契约`（liveRouteReadinessContracts）锚点改名必须与页面同笔提交（第 11 组先例）。
4. **文件编码事故**：全部计划文档与页面文案为中文，严禁 PowerShell 文本管道读写（AGENTS.md 编码纪律）；`debt:audit` 内建 encoding_integrity 兜底。
5. **概念稿与实现混淆**：`output/ui-review/after-*.png` 与 `docs/design-drafts/moss-portfolio-v2-*.png` 是概念渲染图不是实现截图，验收对比一律以真实运行截图为准。

---

## 9. 验证方式

**每页/每期固定动作（从 `frontend/` 运行）：**

- 定向 Vitest：`npm run test -- <页面/原语 pattern>`；壳层期加 `WorkbenchShell`。
- `npm run lint`、`npm run typecheck`。
- `npm run debt:audit`（改动页面/原语/客户端时必跑；含编码完整性、字号地板、分区编号、未声明 CSS 变量审计）。
- `npm run style:audit`（增量拦截非 token hex / 私有阴影，方向 A 滚动期间每页必跑）。
- `npm run test:a11y-smoke`：P1（导航/抽屉交互）与任何触及焦点顺序/键盘可达的页面。
- 1440×900 真实截图改前/改后对比，归档 `output/ui-review/`；非常态界面（loading/空态/错误/2px 圆角残留面）专门触发截图。
- GitNexus：P1 壳层与 P7 `components/page` 删除前做上游影响分析（Tier 3），HIGH/CRITICAL 先警告再动；提交前跑变更检测；索引过期（`.gitnexus/meta.json` lastCommit ≠ HEAD）先 `npx gitnexus analyze --skip-agents-md`。

**正式金融路径影响：无。** 本计划全部工作为呈现层与前端结构层，不触碰 `backend/app/core_finance/`、API 契约、口径与 `result_meta`。唯一潜在例外：Q5 选项 a 的后端时序读模型，届时也仅新增 api/services/repositories 只读读链路，不进入 core_finance；该工单若立项，按后端规则单独走影响报告。

**分期上线口径：** 每期（P1-P7）与每页工单独立可合入、可回滚；任何一页验收不过只阻塞该页，不阻塞批次内其他页。

---

## 附录 A：本计划实际核读的关键证据

- 设计权威与规则：`DESIGN.md`（全文，含 12 节 20 条生效结论）、`frontend/AGENTS.md`、`frontend/CLAUDE.md`、`docs/frontend-layout-contract.md`、`docs/agent_codebase_map.md`
- 在途文档：`docs/prd-workbench-visual-noise-convergence.md`（全文）、`docs/plans/2026-08-27-uncommitted-work-split-plan.md`（全文）、`docs/plans/2026-08-27-audit-remediation-prd.md`（结构）
- 主题与壳层：`frontend/src/theme/designSystem.ts`（全文）、`frontend/src/theme/themeScopes.ts`、`frontend/src/styles/tokens.css`（结构）、`frontend/src/layouts/WorkbenchShell.tsx`（全文）、`frontend/src/layouts/workbenchShellSections.ts`、`frontend/src/router/routes.tsx`（全文）、`frontend/src/app/navigation.ts`（全文）
- 原语层：`frontend/src/components/layout/`（SectionHead/KpiStrip 全文 + index 全文 + 目录清单）、`frontend/src/components/page/`（目录 + FormalResultMetaPanel 头部 + SectionLead 消费方 grep）
- 页面抽样：`frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx`（hero/KpiStrip 用法）、`frontend/src/api/contracts/bondDashboard.ts`（bundle section 清单）、`frontend/src/features/balance-analysis/`（toolbar 主按钮与质量胶囊）、`frontend/src/features/average-balance/components/AdbKpiStrip.tsx`、契约标识 grep（features 全域）
- 截图证据：`output/ui-review/` 16 张（home / bond-dashboard 前后 / balance-analysis / market-data / positions / direction-a~c 概念稿 / shell-after 四张）、`docs/design-drafts/` 3 张
- 工具链：`frontend/package.json` scripts、`scripts/run_frontend_debt_audits.mjs` 审计清单
