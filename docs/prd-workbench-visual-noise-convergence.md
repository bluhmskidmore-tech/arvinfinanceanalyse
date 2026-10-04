# PRD：工作台视觉降噪与治理信息分层收敛

- 状态：执行中（2026-08-27 owner 反馈"降噪后效果仍差"，经三方向概念稿比选后按方向 A 推进；owner 回复"继续"授权执行，方向选择为执行方专业判断，owner 可随时纠正）
- 日期：2026-08-27

## 0. 方向决策（2026-08-27 追加）

降噪（第 1-4 期）只解决"信息放错层"，不改变视觉语言本身。owner 对降噪后效果图仍不满意，据此追加**方向 A：精致深色终端**作为目标视觉：保持 Nocturne 深色体系与全部 token 语义不变，升级排版质感——关键数字放大分级（hero 结论数字 40px 级、KPI 主值 24-28px）、KPI 卡内嵌迷你趋势线、面板留白放宽（padding 16-24px）、主趋势图放大为区块级面积图。落地方式：新增 FR-6，以 `/bond-dashboard` 为样板页先行验证，验收后按同一 checklist 滚动到其余页面。

备选方向 B（浅色研究报告风）与 C（现代 SaaS 数据产品风）概念稿存档于 `output/ui-review/direction-*.png`。B 与 `DESIGN.md` 生效结论 1（全站深色默认）冲突，如 owner 改选 B 须先修订设计权威；C 为全站视觉重写，成本最高，未采纳。

### FR-6 样板页质感升级（方向 A，首批：/bond-dashboard）

1. 首屏结论区升级为大数字 hero：核心读数（组合规模）40px 级等宽字重展示，辅以结论句。
2. KPI 卡主值升至 24-28px，标签 11-12px muted；卡内嵌入迷你 sparkline（ECharts 或轻量 SVG，取色走 `nocturneTokens`）。
3. 面板 padding 放宽至 16-24px，区块间距 24px 级，行高放松；信息密度让位于层次。
4. 主趋势序列升级为区块级面积图（单色渐变填充，`nocturneChartTheme` 取色）。
5. 区块顺序不变（该页不在 §9 顺序锁清单内，但保持顺序以控制回归面）；数据、口径、API 契约零改动。

**验收标准：** 1440×900 真实截图对比概念稿方向一致；页面测试通过；`DESIGN.md` 字号/密度条款按"KPI 主值 20-24"放宽为样板页例外，验收通过后回写 `DESIGN.md`。
- 发起背景：owner 反馈"系统好丑，是不是技术栈有问题"；经 2026-08-27 六页截图走查确认，技术栈（React 18 + AntD 5 + ECharts 6 + AG Grid 35）为金融工作台主流组合且无需更换，观感问题全部来自呈现层执行，可在现有栈上修复。
- 证据：2026-08-27 运行系统 1440×900 截图六张（`/`、`/bond-dashboard`、`/positions`、`/market-data`、`/pnl`、`/balance-analysis`），存放于 `output/ui-review/`。

---

## 1. 问题定义

系统的设计权威 `DESIGN.md` 已经定义了完整的深色机构终端语言（Nocturne），且经营日报首页、正式损益页证明这套语言执行到位时观感是专业的。走查确认"丑"不是主题或组件库能力问题，而是四类呈现层违规，其中前两类直接违反 `DESIGN.md` §6"溯源标识分层"与第 12 节结论 17"常态收声、异常才亮"：

### P1 工程/治理文案直接暴露在业务叙述层（最严重）

两个来源：

1. **外壳级"临时例外"横幅。** `frontend/src/app/navigation.ts` 中 40 个路由有 18 个标记 `governanceStatus: "temporary-exception"`，`frontend/src/layouts/WorkbenchShell.tsx`（`workbench-governance-banner`）据此在页面主内容区顶部渲染整幅横幅，正文为面向开发者的契约治理表述（如"已接 /api/bond-dashboard 聚合读链路"），并固定追加一句"第一阶段仅在页面契约收口期间保留该路由可见；不要把它视为已完全治理的页面"。业务用户打开近半数页面，第一眼看到的是给工程师的备忘。
2. **页面内治理/契约脚注。** 至少四个页面在业务内容区内联渲染契约治理字符串：`positions`（"持仓列表指标边界 GAP-POS-LIST 尚未关闭：MTR-POS-001、MTR-POS-002 仍为 candidate, pending_confirmation=true, bound_sample_id=GS-POSITIONS-BONDS-LIST-A…"）、`ledger-pnl`、`bond-dashboard`、`product-category-pnl`。这些是 metric contract / golden sample 的内部标识，属于证据层。

### P2 子导航 chips 墙占据首屏

`WorkbenchShell.tsx`（`workbench-section-subnav`）把当前分组的全部页面平铺为按钮墙。组合工作台分组下有 17 个页面，渲染为两行 chips + "全部已开放页面"工程视角措辞，在该分组每个页面顶部重复出现，叠加 P1 横幅后，业务内容被压到首屏下半部。

### P3 次级页面色彩纪律失守

`/balance-analysis` 首屏同时出现紫色主按钮（导出 Workbook）、黄色警示胶囊（数据质量需复核）、红黄绿徽章墙（风险全景），违反 `DESIGN.md` §4 Color Consistency Lock 与结论 17。对照之下经营日报首页全页只有一个主强调色，说明这是执行差异而非规范缺失。

### P4 空态面板不收缩

`/market-data` 首屏右侧"关键利率 / 资金指标"面板仅一行数据、大片空白，违反 `DESIGN.md` §5"空态收缩"（0 条数据的分组收缩到消息框自身高度）。

---

## 2. 目标与非目标

### 2.1 目标

1. 把工程/治理信息从业务叙述层收进证据层，**不减弱状态可感知性**：五态（loading / 空 / 错 / stale / partial）与治理缺口仍必须可感知，但常态用安静形式（暗点、muted 短标签、抽屉），只有异常态用语义色发声（对齐 `DESIGN.md` 结论 17）。
2. 子导航收敛为低噪形式，首屏还给业务内容。
3. 次级页面色彩收敛到与经营日报首页同一纪律。
4. 空态面板按规范收缩。

完成标志：走查六页在 1440×900 下，首屏不再出现面向开发者的字符串（contract ID、sample ID、API 路径、布尔字段名），业务结论区内容占比明显提升，全页强调色唯一。

### 2.2 非目标

- 不更换或升级技术栈，不引入新 UI 库、新图表库。
- 不修改任何业务数据口径、指标计算、API 契约、`result_meta` 结构。
- 不删除治理机制本身：`readiness` / `governanceStatus` 字段、页面契约收口流程、审计流全部保留，改的只是呈现位置与形式。
- 不触碰 `DESIGN.md` §9 区块顺序锁（债券分析/组合工作台首页、经营日报首页）。
- 不做浅色回退，不新增第三套主题。
- 不做移动端适配。

---

## 3. 用户与场景

主用户为投资/交易、风控、经营与管理层（见 `DESIGN.md` §1）。核心场景："先看结论、再下钻证据"。当前实现把证据层信息前置到了结论位，本 PRD 的全部需求都是把这个顺序纠正回来。开发者/治理角色查看契约状态的需求继续满足，入口从"横幅平铺"改为"抽屉下钻"。

---

## 4. 需求明细

### FR-1 外壳治理横幅降级为状态胶囊 + 治理抽屉

**现状：** `WorkbenchShell.tsx` 对 `governanceStatus === "temporary-exception"` 的 18 个路由渲染整幅 `workbench-notice` 横幅。

**需求：**

1. 横幅整体移除，替换为页头工具条区域的一个安静状态胶囊（muted 文字 + 暗点，无语义色），文案统一为中文短语，例如"治理：契约收口中"。
2. 点击胶囊展开右侧抽屉或浮层（证据层），完整展示现有 `governanceBanner` / `readinessNote` 内容、readiness 状态与说明。现有文案不删改，只换容器。
3. 胶囊在常态下不使用琥珀/红等语义色；仅当路由处于真正的异常态（数据加载失败、正式链路降级兜底）时才允许语义色发声。
4. `navigation.ts` 的数据结构（`governanceStatus`、`governanceBanner`、`readinessNote`）保持不变，本需求纯呈现层。

**验收标准：**

- 18 个 temporary-exception 路由首屏不再出现横幅；DOM 中治理文案仍可通过抽屉访问（可测试）。
- 现有测试 `WorkbenchShell.test.tsx` 中横幅断言同步更新为胶囊 + 抽屉断言。
- `DESIGN.md` §6"五态齐备"走查通过：治理状态仍可感知。

### FR-2 页面内治理/契约脚注收进证据层

**现状：** `positions`、`ledger-pnl`、`bond-dashboard`、`product-category-pnl` 等页面在业务内容区内联渲染 contract ID / sample ID / 布尔字段等技术标识（本 PRD 走查所见清单，实施时按 P1 验收口径全量排查）。

**需求：**

1. 逐页把此类内容移入该页已有的证据链/明细区块（如 bond-dashboard 的 `EvidenceSection`），或页面级"治理说明"折叠区；页面无证据区块时收进 tooltip 或 FR-1 的治理抽屉。
2. 业务叙述位保留的最大限度是一个安静的状态点 + 一句中文业务语言说明（如"部分指标待业主确认"），不出现英文技术标识。
3. 涉及页面逐页排查，以"首屏无 contract/sample/字段名字符串"为完成标准，不预设固定页面清单。

**验收标准：**

- 每个改动页面 1440×900 截图对比：业务首屏无技术标识字符串。
- 对应页面测试（`PositionsView.test.tsx`、`LedgerPnlPage.test.tsx`、`BondDashboardPage.test.tsx` 等）断言更新且通过。
- 治理信息在证据层可达（折叠区/抽屉/tooltip 中断言存在）。

### FR-3 子导航 chips 墙收敛

**现状：** `workbench-section-subnav` 平铺当前分组全部页面，组合工作台 17 项渲染两行按钮墙，每页重复。

**需求：**

1. 子导航收敛为单行：当前页面高亮 + 同组页面收进下拉/overflow 菜单，或收敛为侧栏二级导航（方案由设计确认，PRD 不锁定实现形式，锁定"单行、不换行"的空间约束）。
2. "全部已开放页面"措辞删除，替换为分组名（如"组合工作台"）。
3. 保持键盘可达性与当前路由高亮，不破坏 `test:a11y-smoke`。

**验收标准：**

- 组合工作台任一页面首屏，子导航垂直占用 ≤ 单行高度（约 48px 级）。
- 全部 17 个组内页面仍可通过子导航到达（测试断言）。
- a11y smoke 通过。

### FR-4 次级页面色彩纪律修复（首批：/balance-analysis）

**现状：** 首屏紫色主按钮 + 黄色胶囊 + 红黄绿徽章墙并存。

**需求：**

1. 每页主强调色唯一（Nocturne `--dh-api-blue`），导出/刷新等次级操作降为 ghost/线框按钮。
2. "数据质量需复核"等提示按结论 17 处理：常态收声（muted），确有异常才用琥珀。
3. 风险全景徽章墙重新分级：同屏语义色徽章数量收敛，非异常项用中性色。
4. 完成 `/balance-analysis` 后，以同一 checklist 排查其余次级页面（`/positions`、`/liability-analytics` 等），逐页滚动收敛。

**验收标准：**

- 改动页 1440×900 截图对比：全页语义色仅出现在真实异常/涨跌语义处；主强调色唯一。
- 不改动任何数值、口径、导出功能行为（功能测试通过）。

### FR-5 空态面板收缩（首批：/market-data）

**现状：** "关键利率 / 资金指标"面板大片空白。

**需求：** 按 `DESIGN.md` §5：0 条或近 0 条数据的分组收缩到消息框自身高度（min-height ≤ 120px 级），居中一句话说明 + 原因；数据到达后恢复正常布局。

**验收标准：** 空态截图对比 + 有数据状态回归不受影响。

---

## 5. 设计约束（实施时必须遵守）

1. `DESIGN.md` 为唯一视觉权威；本 PRD 与其冲突时以 `DESIGN.md` 为准并回报。
2. 深色页语义色只用 Nocturne 去饱和色阶（`--dh-api-*` / `nocturneTokens`），盈亏着色走 `TONE_DH_CSS_VAR`。
3. 新增文案为简体中文业务语言，禁止中英混排技术微标签（`DESIGN.md` §7）；契约 ID 等英文标识只允许出现在证据层。
4. 抽屉/折叠等新交互用 `designTokens.motion`，尊重 `prefers-reduced-motion`。
5. 组件改动优先复用现有 primitives（`src/pageModel`、`workbenchShell.css` 体系），不新造平行组件。

---

## 6. 分期与优先级

按"单点改动收益最大"排序，每期独立可验收、可上线：

| 期 | 内容 | 改动面 | 预期收益 |
|---|---|---|---|
| 第 1 期 | FR-1 外壳横幅降级 + FR-3 chips 收敛 | 共享外壳 `WorkbenchShell.tsx` + CSS + 壳层测试，一次改动 | 18 个路由横幅消失、全部 6 分组子导航收敛，全站观感立即改善 |
| 第 2 期 | FR-2 页面治理脚注收敛 | 逐页（positions → ledger-pnl → bond-dashboard → product-category-pnl → 排查余量） | 首屏技术字符串清零 |
| 第 3 期 | FR-4 色彩纪律（balance-analysis 起） | 逐页局部 CSS/组件 | 次级页面与旗舰页面纪律一致 |
| 第 4 期 | FR-5 空态收缩（market-data 起） | 页面局部 | 版式事故清除 |

第 1 期是共享层改动（Tier 3，需按 `frontend/AGENTS.md` 做 GitNexus 影响分析并先行报告）；第 2-4 期为页面局部（Tier 1/2）。

---

## 7. 验证方式

- 每期改动前后 1440×900 基准截图对比（`DESIGN.md` §10 验收口径），截图归档到 `output/ui-review/`。
- 定向 Vitest：壳层 `WorkbenchShell.test.tsx`、逐页对应测试。
- `npm run lint`、`npm run typecheck`、`npm run debt:audit`（改动页面/共享层时）。
- `npm run test:a11y-smoke`（FR-1/FR-3 涉及导航与新交互）。
- 正式金融路径影响：**无**。全部需求为呈现层，不触碰 `backend/app/core_finance/`、API 契约与任何口径。

---

## 8. 风险与依赖

1. **治理可见性回退风险。** 收敛过度会违反 §6"五态齐备"。缓解：FR-1/FR-2 验收都含"治理信息在证据层可达"的正向断言，先加新入口再撤旧横幅。
2. **测试面较广。** 18 个路由 + 壳层测试对横幅/子导航有既有断言，第 1 期需同步更新；以 `data-testid` 稳定选择器减少连带修改。
3. **色彩分级需要产品判断。** FR-4 中"哪些徽章算真实异常"可能涉及口径判断（类似 `DESIGN.md` 结论 17 的 `--moss-color-warning-200` 分裂先例），遇到分歧上报 owner 决策，不自行猜测语义。
4. **横幅文案的治理承诺。** "临时例外"横幅承担"该路由未完全治理"的免责声明职能，收进抽屉后此声明仍在 DOM 且可达，但若审计/合规流程要求它"必须首屏可见"，需 owner 在开放问题 Q1 明确。

---

## 9. 影响面初步定位（供实现参考）

| 需求 | 主要文件 |
|---|---|
| FR-1 | `frontend/src/layouts/WorkbenchShell.tsx`（`workbench-governance-banner` 段）、`frontend/src/app/navigation.ts`（数据不动）、`frontend/src/styles/workbenchShell.css` 系、`frontend/src/test/WorkbenchShell.test.tsx` |
| FR-2 | `frontend/src/features/positions/components/PositionsView.tsx`、`frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`、`frontend/src/features/bond-dashboard/sections/EvidenceSection.tsx`、`frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx` 及对应测试 |
| FR-3 | `frontend/src/layouts/WorkbenchShell.tsx`（`workbench-section-subnav` 段）与壳层 CSS |
| FR-4 | `frontend/src/features/balance-analysis/` 页面局部样式与组件 |
| FR-5 | `frontend/src/features/market-data/` 相应面板组件 |

---

## 10. 开放问题（需 owner 决策）

- **Q1：**"临时例外"免责声明是否允许从首屏横幅降级为"胶囊 + 抽屉"？若治理流程要求首屏强可见，FR-1 改为保留单行细横幅（一行、muted、可折叠），其余不变。
- **Q2：** FR-3 子导航收敛形式选下拉 overflow 还是侧栏二级导航？前者改动小，后者信息架构更干净但动侧栏（当前侧栏已有六分组一级导航，二级展开会加长滚动）。建议先做下拉 overflow。
- **Q3：** FR-4 风险全景徽章的"真实异常"判定口径是否已有业务定义？若无，需要产品给出分级规则后再动色彩。
