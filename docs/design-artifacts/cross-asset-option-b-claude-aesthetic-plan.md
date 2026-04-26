# 方案 B：跨资产页「类 Claude / 高阶低饱和」审美 — 可执行计划

## 0. 约束（必须全程遵守）

| 约束 | 说明 |
|------|------|
| **功能** | 不删不改 API 契约、`crossAsset*Model` 计算逻辑、路由与 `data-testid` 语义。 |
| **可观测性** | 加载/空/错误/治理横幅等行为与现网一致；仅改**视觉**与**可访问性无关**的版式。 |
| **AGENTS 纪律** | 不扩张 `api/client.ts`；页面改动以 **本域 CSS + 本页 TSX** 为主；改壳层需单 PR、可回滚。 |
| **基线** | 合并前：`npm test -- --run CrossAsset`（含 `CrossAssetPage`、`CrossAssetDrivers`）、`npm run debt:audit`。 |

## 1. 目标与非目标

### 1.1 目标（B）

在 **仍嵌于 Workbench** 的前提下，让 `/cross-asset` 的观感更接近「高阶、低饱和、克制、字阶清楚」的 Claude 系产品气质（非像素级抄 Claude）：

- **色**：主背景与卡片对比克制；绿/红用 **低饱和、偏灰** 的 semantic，避免「券商默认荧光」。
- **型**：字重与字号层级更清楚；**弱边框/弱阴影/大圆角**统一在一套本页 token 上。
- **空**：KPI 数量 **随数据变化** 时，栅格不「碎」（见阶段 2 的版式策略）。
- **壳**：在**可选**阶段减少 `main` 上「双层大卡片」感（大圆角灰底 + 内页再一层纸面），与债券分析页已有 **`bond-analysis` minimal main chrome** 模式对齐思路。

### 1.2 非目标

- 不动全局 `antd` 主题与全站 `designSystem.ts` 默认值（避免波及其他工作台）。
- 不替换业务组件库为全新设计系统。
- 不以「动效堆满」补偿审美（除非有明确可访问性要求）。

## 2. 根因简析（为何与静态稿/预期差一截）

1. **壳层 `main`**：`WorkbenchShell` 在多数路由下为 `Outlet` 外包一层 **padding 24、圆角 30、渐变底、细边框+阴影**（见 `main` 的 `style`）。跨资产页内再叠本页纸色与卡片，容易出现 **「盒中盒、灰底+纸底」** 的割裂。债券分析通过 `currentSection.key === "bond-analysis"` 走 **minimal shell** 去掉该层（见下节）。
2. **KPI 条数 ≠ 设计稿 8**：`resolveCrossAssetKpis` 可能返回 8/11+，4 列栅格最后一行**缺格**会显得「没排完」；需 **纯展示策略** 处理（不占业务逻辑）。

## 3. 分阶段与影响评估

### 阶段 1 — 仅本页 CSS / 本页 class（**默认先做，风险最低**）

| 项 | 改动面 | 影响 |
|----|--------|------|
| 收敛 `--ca-*` token | `CrossAssetDriversPage.css` | 无业务逻辑；仅视觉 |
| `__mini-kpi` / `__panel` / 表格 / 驱动格 | 同上 | 无 |
| 标题与正文字阶（`h2`、说明文字） | 同上，或极少量本页内 `className` | 无 |
| Sparkline/图表颜色 | 若须改 ECharts 主题，仅 `buildCrossAssetTrendOption` 的 **颜色数组** | 需子代理通读，不改序列数据 |

**回滚**：还原 `CrossAssetDriversPage.css`（与少量 TSX 的 class 名）。

### 阶段 2 — 本页结构展示策略（**不改数据，只改呈现**）

| 项 | 做法 | 影响 |
|----|------|------|
| KPI 栅格「最后一行不满」 | 用 **CSS `auto-fill` + `minmax`** 或 **占位 `grid-column` 空单元**（无数据，仅占位） | TSX 可能增加若干 `div`+class；**不**改 `resolveCrossAssetKpis` 返回值 |
| 「市场判断」大留白 | 面板内 `min-height` + `align-content` 或与右侧表格 **stretch 对齐** | 仅布局类名 |

**回滚**：删除占位节点或 class。

### 阶段 3 — 壳层「跨资产轻量主区」（**可选，影响面大，单独评审**）

| 项 | 做法 | 影响 |
|----|--------|------|
| 与 `bond-analysis` 类似 | 增加 `isCrossAssetImmersiveShell`（名可再议）当 `currentSection.key === "cross-asset"` 时：`main` **透明/无内边框/无大圆角**或 **padding 收紧**，与 `bond-analysis` 共用或抽取「minimal main chrome」集合 | **文件**：`frontend/src/layouts/WorkbenchShell.tsx`；**回归**：`WorkbenchShell` 相关用例、人工点选市场组内多路由 |
| 子导航/治理横幅 | 仍保留；只减轻 **最外层** 与页面内容的 **双重嵌套** 视觉 | 需各路由快照对比市场组其他页 |

**回滚**：还原 `WorkbenchShell` 中条件分支；建议独立 commit。

## 4. 子代理（Subagent）拆分与执行顺序

目标：**并行为主、依赖处串行**；每个子代理输入输出写清，避免改同一 hunk 冲突。

| 顺序 | 子代理 ID | 范围 | 输入 | 输出 | 依赖 |
|------|-----------|------|------|------|------|
| **4.1** | `CA-B-tokens` | 阶段 1 | 当前 `CrossAssetDriversPage.css` 中 `.cross-asset-drivers-page` 与 `__panel` 等 | 一版**低饱和** token 与类名微调 diff | 无 |
| **4.2** | `CA-B-kpi-grid` | 阶段 2 | `MiniKpiCard` 与 `__kpi-grid` DOM 结构 | 满行/对齐策略（CSS 为主，必要时 TSX 占位） | 可与 4.1 **并行**，合并前先 rebase |
| **4.3** | `CA-B-trend-colors` | 阶段 1 可选 | `crossAssetTrendChart.ts` | 仅**配色/线宽/网格**的 option 调整 | 不改序列；与 4.1 可并行 |
| **4.4** | `CA-B-shell` | 阶段 3 | `WorkbenchShell.tsx` 中 `isBondAnalysisMinimalShell` 附近 | 可复用条件或 `Set<sectionKey>`，**仅 cross-asset** 生效 | **必须**在 4.1–4.3 合入后单独 PR；需人工验收市场组多页 |
| **4.5** | `CA-B-qa` | 收尾 | 整分支 | `npm test` + `debt:audit` + 手动 `/cross-asset` 烟测 | 依赖全部合入后 |

在 Cursor 中执行方式（概念上）：

1. 先开对话/任务 **「4.1 CA-B-tokens」**，限定文件：`CrossAssetDriversPage.css`（及禁止改 `*.ts` 业务逻辑）。  
2. 并行开 **「4.3 CA-B-trend-colors」**，限定文件：`crossAssetTrendChart.ts`。  
3. 第二 wave 开 **「4.2 CA-B-kpi-grid」**（可能触及 `CrossAssetDriversPage.tsx` + css）。  
4. 评审后如需壳层，再开 **4.4**（单独 PR）。  
5. 最后 **4.5** 跑测试与审计。

> **防冲突规则**：4.1 与 4.2 同改一个 TSX 时，优先 **4.1 只 CSS** 落地，4.2 只动 TSX+CSS 的 KPI 区。

## 5. 验收清单（每阶段可独立签字）

- [ ] `/cross-asset` 在 mock / real 下数据与现网**一致**（数字、表行数、无新增报错）。  
- [ ] 所有现有 **testid** 仍能被测试找到（`CrossAssetPage.test.tsx` 等 **绿**）。  
- [ ] `npm run debt:audit` **通过且未意外放宽** baseline。  
- [ ] 市场组子导航在阶段 3（若做）下 **多路由切换** 无布局炸裂。  
- [ ] 键盘/读屏无破坏性（未引入不可聚焦伪按钮）。  

## 6. 建议的 Git 策略

- **阶段 1+2**：一个 feature 分支，**原子 commit**：`ca-ui: token + panel` → `ca-ui: kpi grid layout`。  
- **阶段 3**：**独立分支/PR**（`ca-shell: cross-asset-immersive-main`），方便业务方只 cherry-pick 视觉不碰壳。  

## 7. 与既有文档关系

- 与 `cross-asset-implementation-plan.md`（首版落地产物）**互补**：彼文档侧重「结构重组与纸色」；本文档（B）侧重 **审美层级与壳层关系**，并显式评估 **Shell 级**变更。

---

## 8. 阶段 3 执行记录（2026-04-26）

- **`WorkbenchShell.tsx`**：`currentSection.key === "cross-asset"` 时与 `bond-analysis` 共用 **`isMinimalMainChrome`**——`main` 去 padding/边框/圆角/渐变底、去 **市场组大 hero 卡**（`showWorkspaceHeroCard` 增加 `!isCrossAssetImmersiveMain`）。  
- **保留**：`workbench-section-subnav`（市场数据 / 跨资产 / 新闻）仍显示，与债券分析「藏子导航」不同。  
- **测试**：`WorkbenchShell.test.tsx` 增加 `uses transparent main surface for cross-asset and keeps market workbench subnav`。

---
*阶段 1–2 已在前序提交；阶段 3 已落地。*
