# 前端整体审美合规方案（交 Codex 执行）

> 状态：已批准（2026-10-02，D-A 至 D-G 全部同意）；DESIGN.md 已按批准结果修订 · 起草 Claude · 执行与提交 Codex · 阶段结果交用户确认
>
> 文档分工：
> - **规则与数值**只在 [DESIGN.md](../DESIGN.md)：§1.1 审美逻辑、§3 字体、§4.2 强调与装饰、§5 间距、§5.3 骨架、§5.4 数据组件、§6 状态、§10.1 合规门槛、§10.2 样式架构、§10.3 桌面预备。本文与 DESIGN.md 不一致时，以 DESIGN.md 为准。
> - **需求、目标与验收口径**见 [PRD](prd-frontend-aesthetic-compliance.md)。
> - **本文只管执行**：阶段顺序、实现位置、范围与退出条件。本文是 [design-global-unification-proposal.md](design-global-unification-proposal.md) Phase 3/4 的执行细则。
>
> 分级按 [frontend/AGENTS.md](../frontend/AGENTS.md)：S/T/C/D 类属 Tier 1（纯视觉）；A 类架构与 P5 桌面预备属 Tier 2–3。一旦触及业务显示即升级。

## 1. 目标

把 MOSS 前端收敛成**一个**专业金融工作台的观感：
- 全站同一骨架；
- 层级靠字号与留白，不靠粗体和色块；
- 数字能对齐比较；
- 颜色只表达语义；
- 状态清楚但不抢戏。

“合规”的判定：DESIGN §10.1 门槛全部通过，且 §5 的截图复核全部为“是”。

**不变量（任何阶段都不碰）**：
- 业务逻辑、指标含义与数据口径、接口、权限、关键操作流程；
- [页面顺序锁](frontend-design-page-rules.md)；
- 既有颜色语义（涨、跌、警示、强调各自的含义不变）。

## 2. 现状基线（2026-10-02，1440×900，mock 数据，21 个路由）

- 数据：`.tmp/visual-audit-20261002/baseline.log`、`baseline/metrics.json`
- 首屏截图：`baseline/*-fold.png`
- 探针：`aesthetic-audit.mjs`（只读）
- 逐页数字见附录 A。

最影响整体观感的五个问题：

| # | 问题 | 证据 | 根因位置 |
|---|---|---|---|
| 1 | **骨架有四种，像四个产品** | 浮框式 9 页（主区与终端条各是一张浮卡），通栏式 6 页，混合 2 页，自带顶栏 4 页。页面标题左边线从 200 到 421px 不等，多数在 230–272px；同一页内面包屑、子导航、标题三条左边线最多差 23px | `layouts/WorkbenchShell.tsx:434-444` 按路由加外壳修饰类，`:929` 是 minimal 开关；`styles/workbenchShell.css:666` 默认主区本身就是卡片（边框、阴影、渐变底、圆角），只有 `:1000` 的 cockpit 分支去掉了框 |
| 2 | **框套框** | 二层及以上框：余额变动 63、债券分析 37、产品分类 35、团队绩效 28；浮框页在此之上再多一层 | 页面局部 CSS：KPI 小卡、面板内子面板、表格外框 |
| 3 | **粗体过量** | 首屏粗体字占比：风险张量 69%、总账 64%、组合 62%、宏观 53%、KPI 50%，只有持仓和市场总览 ≤14%。700 字重尚未收口：发布展示页 10%、总账 7.7% 的字符仍是 700，来源主要是 `<strong>` 的默认字重 | R2 只把 700/800 降到 600，没有限制 600 的用途；微软雅黑没有 Semibold，600 一律渲染成 Bold；DESIGN.md 原条文还鼓励大字号和按钮 600 |
| 4 | **颜色与标签噪声** | 强调紫元素：组合 75、余额变动 65、产品分类 43、宏观 43。彩色标签：团队绩效 46、资产负债 21、组合 15、风险总览 12。8 页常态挂“已就绪/已接入/已同步”徽标；12 页的卡片、按钮或标题条上有装饰阴影或渐变 | 页面局部 CSS 把强调色用于描边和标签底；状态做成了徽标 |
| 5 | **小字与表格不统一** | 11px 字符占比：余额变动 86%、债券分析 48%、发布展示 48%、市场数据 40%。表头有 11/500、11/600、12/500、12/600 四种，行高 24–69px，单元格字号有 11、12、12.48、13、16 五种。非等宽数字：总账 62、余额变动 30、团队绩效 25、股票 22；首页 64 个数字仍是等宽代码字体 | R7 只落在共享 DataTable，页面局部表格没跟进；字号没有锁定字号阶 |

其他问题：
- 组合页“模拟数据/MOCK”出现 25 次，DESIGN §6 上限是 2 次。
- 发布展示页有 5 个全大写英文眉标。
- 市场总览的 MOCK 横幅遮挡导航文字（既有问题）。

21 页的 JS 错误均为 0，1440 宽下横向溢出均为 0。

## 3. 规则编号与实现位置

规则原文与数值见 DESIGN.md。下表只给编号（报告和提交信息沿用）、出处和实现位置。页面只消费公共变量与组件，页面 CSS 不复制全局组件皮肤。

### 3.1 骨架 S · DESIGN §5.3

| 编号 | 规则 | 实现位置与要点 | 阶段 |
|---|---|---|---|
| S1 | 单一外壳：通栏终端条 + 无框主区 | `styles/workbenchShell.css:666` 的默认主区改为无框，删除浮框分支（现在只有 `:1000` 的 cockpit 分支无框）。`layouts/WorkbenchShell.tsx:434-444` 的按路由修饰类和 `:929` 的 minimal 开关随 A2 收口。终端条 scope 清单（`styles/workbenchDeferredChrome.css:1288` 起）与 `tokens.css` 同构，两处按 `theme.test.ts` 的 parity 断言同步删除。总账终端条的渐变在 `styles/workbenchInstitutionalConsole.css` | P1 样板页 / P2 全量 |
| S2 | 单一 gutter，一条左边线 | 新增 `--moss-page-gutter`（`--moss-space-4`，992px 以下 `--moss-space-3`），面包屑、子导航分组标签、页面标题和一级区块都用它。`geom.mjs` 可打印左边线的祖先链 | P1 / P2 |
| S3 | 页面顺序与原语 | `components/page/PagePrimitives.tsx` 的 `PageHeader`、`DataStatusStrip`、`PageFilterTray`、`AnalysisGrid`、`EvidencePanel`、`PageStateSurface`；KPI 带用 `components/layout/KpiStrip` | P1 / P3 |
| S4 | 容器深度 ≤1 | 页面局部 CSS 中的 KPI 小卡、面板内子面板和表格外框，改为细线、留白或表格行线 | P1 / P3 |
| S5 | 自带顶部的 4 页 | 首页、市场总览、股票分析、发布展示只对齐顶栏高度、字号、底线和左边线；首页受 DESIGN §9.2 约束 | P3 ③ |

### 3.2 字体 T · DESIGN §3

| 编号 | 规则 | 实现位置与要点 | 阶段 |
|---|---|---|---|
| T1 | 六档字号阶 | `designSystem.fontSize` 已有 11/12/13/14/20/24；16/18/30 不用于工作台页（首页沿用 09-26 基准的除外）。现存的非阶字号有 10、11.5、12.5、12.48、13.5、14.5、18.5、21.5、22.5、28、30、32、36 等，逐批收口。长文阅读用 14/400、行高 1.7 | P1 / P3 |
| T2 | 字重预算 | 全局 `strong, b { font-weight: 500 }`；`theme/theme.ts:71` 中 Button 的 `fontWeight: 600` 改为 500；需要 600 的角色（KPI 主值、合计行）在组件里显式声明 | P1 |
| T3 | 等宽数字与对齐 | `body` 级 `font-variant-numeric: tabular-nums`；数字列右对齐；首页的等宽代码字体数字改用 `fontFamily.tabular`（D-D，只改字体族） | P1 / P3 ③ |
| T4 | 中文可读性 | 11px 字符 ≤15%；删除全大写英文眉标（发布展示有 5 个） | P3 |
| T5 | 字体随包 | 自托管 Noto Sans SC 400/500/600（可用可变字重版），建议放在 `public/fonts/noto-sans-sc/`；按 unicode-range 分片、`font-display: swap`，回退字体用 `size-adjust` 等度量对齐。放到 `designSystem.fontFamily.sans` 与 `--moss-font-sans` 的首位，两处同步；附 OFL 许可文件。现有唯一的 `@font-face` 是 `styles/marketOverviewShell.css` 中的 Cascadia Mono，可参照它的放置方式 | P1 |

### 3.3 颜色与强调 C · DESIGN §4.2、§6

| 编号 | 规则 | 实现位置与要点 | 阶段 |
|---|---|---|---|
| C1 | 强调色只表达交互 | 页面局部 CSS 中用强调色做的描边、标签底、KPI 色条和眉标文字改为中性色。最多的几页：组合 75、余额变动 65、产品分类 43、宏观 43 | P1 / P3 |
| C2 | 语义色与彩色标签 | 标签统一用 `components/StatusPill`；表格内状态改为彩色文字或圆点。最多的几页：团队绩效 46、资产负债 21 | P1 / P3 |
| C3 | 状态降噪 | 删除 8 页的常态徽标；组合页“模拟数据/MOCK”从 25 处收为 ≤2；KPI 内不写“模拟数据”，缺值用 muted 的 `EM_DASH`；修复 `components/DataModeRibbon.tsx` 在市场总览遮挡导航 | P1 / P3 |
| C4 | 无装饰阴影、渐变和发光 | 12 页的卡片、按钮、页签和标题条上的阴影与渐变；白名单见 DESIGN §4.2 | P1 / P3 |

### 3.4 组件 D · DESIGN §5.4

| 编号 | 组件 | 实现位置与要点 | 阶段 |
|---|---|---|---|
| D1 | 表格 | `components/layout/DataTable` 新增 `--moss-table-row-h`（32）和 `--moss-table-row-h-compact`（28），ag-grid 主题与页面手写表格对齐到同一组变量。不改 `density.tableRowNormal`，它是 AntD `controlHeight`（36）。现在表头有 4 种样式，行高 24–69px | P1 / P3 |
| D2 | KPI 带 | `components/layout/KpiStrip` + `components/KpiCard`；其余 5 套 KPI 实现按 A4 迁移 | P1 / P3 |
| D3 | 图表 | 沿用 `nocturneChartTheme`（29 个文件引用），只改主题，不逐图修改 | P1 |
| D4 | 控件与按钮 | 沿用 R6，用 `controls.mjs` 检查；R6 残余见 `controls-r1b.txt` | P1 |
| D5 | 导航 | 左轨当前项去掉整框描边，改为淡底加 ink 字；子导航沿用 R8 的文字页签，不用胶囊或卡片 | P1 |
| D6 | 空、加载、错误态 | `PageStateSurface`（`PagePrimitives.tsx`）与 `components/layout/StateSurface` | P1 / P3 |

### 3.5 架构 A · DESIGN §10.2

审美反复走样，根因在架构：页面可以随意覆盖外壳和公共组件，同一件事又有多套实现。现状（`frontend/src`）：
- 170 个 CSS 文件里有 857 处 `:has()`、2339 处 `!important`。
- 外壳按路由分出 10 种修饰类（`workbench-shell-grid--*`）。
- KPI 组件有 7 套：
  - `components/KpiCard.tsx`
  - `components/layout/KpiStrip.tsx`
  - `features/average-balance/components/AdbKpiStrip.tsx`
  - `features/bond-analytics/components/BondKpiRow.tsx`
  - `features/cross-asset/components/CrossAssetKpiBand.tsx`
  - `features/macro-observation/components/MacroObservationKpiBand.tsx`
  - `features/workbench/shared/InstitutionalKpiTile.tsx`
- 设计变量分散在 `styles/tokens.css` 和 `theme/` 下的 5 个文件里（designSystem、displayTokens、theme、themeScopes、tokens），靠手工互抄和 parity 测试维持一致。

只改样式与布局架构。React、Vite、AntD、ag-grid、ECharts、数据层和业务组件都不动。

| 编号 | 内容 | 实现要点 | 阶段 |
|---|---|---|---|
| A1 | 分层 | 页面 CSS 只留布局。外壳与全局样式里按页面写的 `:has([data-moss-theme-scope=…])` 补丁，迁回组件或删除。`!important` 只留给第三方覆盖，并在审计配置中登记 | P3 每批 / P4 |
| A2 | 外壳由路由声明驱动 | 路由元信息加 `layout` 字段（如 `workbench`、`immersive`）；`WorkbenchShell` 只读这个字段，删除按路由名的修饰类和终端条 scope 清单 | P2 |
| A3 | 变量单一来源 | 用一份 TS 定义生成 CSS 变量、AntD theme、ECharts 主题和 ag-grid 主题；feature 目录不再自建设计变量 | P2 |
| A4 | 一个角色一套组件 | KPI、表格皮肤（DataTable、ag-grid、页面手写表格）、页面原语（`PageSurfacePanel` 与 `PageV2*` 并存）各收敛为一套；页面迁移完成后删除旧实现 | P3 每批 / P4 |
| A5 | 用检查守住 | 扩展 `style:audit`/`debt:audit`，页面 CSS 中的以下情况计为违规：原始色值、字号阶以外的字号、`!important`、按页面写的 `:has()`。存量设基线，新增违规阻断，基线逐批下调 | P0 建基线 |

## 4. 执行顺序

每个阶段单独提交，可以独立回滚。

**P0 规则核对与工具**
- 内容：
  - DESIGN.md 已由 Claude 按批准结果修订（2026-10-02）。P0 不改规则，只核对 DESIGN.md 与代码注释、审计脚本的引用是否一致：`scripts/audit_font_size_floor.mjs` 的 11px 下限，`scripts/audit_visual_tokens.mjs` 的 Shape Lock 与 §4 禁色，测试注释引用的 §7、§11.2。发现冲突先报告；不要改章节编号，外部文档按编号引用这些章节。
  - FR-6：把 `.tmp/visual-audit-20261002/aesthetic-audit.mjs` 提升为 `frontend/scripts/visual-compliance-audit.mjs`，支持 1440×900 和 1280×720 两种视口。
    - 门槛按 DESIGN §10.1 写入 `frontend/scripts/visual-compliance.thresholds.json`，按路由登记例外，写明原因和批准人。
    - 违规时输出选择器清单；超过门槛时退出码非 0。
    - 应用根节点的底色不计为框。
  - 在 frontend/AGENTS.md 的证据工具中登记该脚本（DESIGN §10.1 要求不另立命令体系）。
  - 在 docs/frontend-design-page-rules.md 的经营日报条目中记录 D-D：数字字体族改为比例字体加等宽数字，字号与留白不变。
  - 按 A5 扩展审计规则，记录存量基线。
- 范围：新增脚本、审计规则，以及 frontend/AGENTS.md 和页面规则文档中的登记。
- 退出条件：在 21 页上复现附录 A 的基线，审计规则输出存量基线数字。

**P1 样板阶段：公共层 + 样板页**
- 内容：
  - 公共层：
    - 把 T1–T3、表格变量和 gutter 写入 `tokens.css`、`designSystem.ts`、`theme.ts`（三处同步，单一来源在 P2 做）；接入 T5 字体。
    - 按 D1–D6 修改公共组件：`components/layout/` 的 DataTable、KpiStrip、SectionHead、StateSurface；`components/` 的 KpiCard、StatusPill、FilterBar；`PagePrimitives.tsx` 的 PageHeader；以及按钮与左轨。
    - 修复 MOCK 横幅（`components/DataModeRibbon.tsx`）在市场总览遮挡导航的问题。
  - 样板页 `/ledger-pnl` 按全部规则精修。
    - 它覆盖页头、原生筛选、锚点页签、KPI 带、多张表格、标签、折叠证据和状态面。
    - S1/S2 先通过现有的路由外壳分支只对本页生效。
    - DESIGN §9 只锁顺序，“换肤和降噪”在允许范围内。
- 范围：`styles/`、`theme/`、`components/`、`public/fonts/`，以及样板页的呈现层。
- 退出条件：
  - 样板页通过 DESIGN §10.1 全部门槛。
  - 其余 20 页无回归：JS 错误 0、溢出 0、控件达标。
  - 交给用户：同视口前后截图和指标对比。**用户确认后才进入 P2。**

**P2 外壳与变量架构**
- 内容：
  - S1/S2 改为所有路由的默认；删除浮框分支和按路由补丁；同步 `theme.test.ts`/`themeScopes.ts`。
  - 按 A2 改为由路由元信息 `layout` 驱动，删除按路由名的修饰类；按 A3 把设计变量改为单一来源生成。
- 范围：`layouts/WorkbenchShell.tsx`、`styles/workbenchShell.css`、`styles/workbenchDeferredChrome.css`、`styles/tokens.css`、`theme/`，以及路由定义（只加 `layout` 字段）。
- 退出条件：
  - 全部路由通过 S1/S2。
  - A3 改造前后，各路由解析出的变量值逐项一致。
  - 组合、总账、余额变动三页在 1280、1024、720 宽下检查无问题。

**P3 逐批推广**（批内按问题严重度排序）
- ① 组合/债券域：`/portfolio` `/balance-movement-analysis` `/bond-analysis` `/balance-analysis` `/risk-overview` `/risk-tensor` `/positions` `/average-balance`
- ② 损益/绩效域：`/product-category-pnl` `/team-performance` `/kpi` `/pnl-by-business`（含 insights）`/pnl-attribution`
- ③ 市场/宏观/展示：`/macro-toolkit` `/market-data` `/cross-asset` `/stock-analysis` `/market-overview` `/publication-showcase` `/`
  - 首页只改字体族、字重和颜色，不动字号、留白和顺序，除非用户另行批准。
- ④ `routes.tsx` 中其余路由：先用探针扫一遍，再按同一规则收口。
- 每批同时按 A1 把页面 CSS 收回到只管布局，按 A4 把该批页面的 KPI、表格和面板换成统一组件。
- 范围：各页局部样式；按 A4 换组件时涉及页面的呈现层，不动数据获取和业务计算。
- 每批的退出条件：该批路由门槛全部通过、截图复核完成、相关页面测试通过。

**P4 收尾**
- 内容：
  - 清理已失效的 `:has()` 路由补丁、无引用的旧组件和死代码（统一提案 Phase 4、A4）。
  - 下调 debt 与 A5 审计基线。
  - DESIGN.md 补登最终的例外清单。
  - 制作全站缩略图墙的前后对比。
- 范围：全局。
- 退出条件：DESIGN §10.1 全部通过，提交最终报告。

**P5 桌面客户端预备**（PRD FR-7；可与 P3 穿插，但单独提交）
- 内容：§8“现在做”的第 5 项。
- 范围：`api/` 的配置读取、导出与本地存储的调用点、`WorkbenchShell` 顶部、路由入口。不改接口、权限和业务流程。
- 退出条件：网页版行为不变（导出、本地偏好、深链接刷新）；Tier 2–3 测试与 typecheck 通过。

## 5. 验收

**自动检查**：门槛以 DESIGN §10.1 为唯一定义，检查脚本按 PRD FR-6 实现。每页在 1440×900 下检查全部项；在最小窗口 1280×720 下复查溢出、截断、左边线和控件四项。

探针是启发式统计：图表 canvas 内部不计，颜色按色相归类。门槛没通过时，以截图核实为准；确属合理的情况登记为例外，不要放宽门槛。

**截图复核**
- 用同视口、同一套 mock 数据做前后对比，并为 21 页做首屏缩略图墙（改前、改后各一张）。
- 每页先做 DESIGN §10.1 的三项目视检查（眯眼、灰度、与样板页并排），再回答五问：
  1. 首屏是否先回答了一个主要问题？
  2. 与样板页并排时，是否像同一个产品？
  3. 有没有抢戏的粗体、颜色或框？
  4. 数字能否直接对齐比较？
  5. 状态是否清楚但不吵？

**测试**（frontend/AGENTS.md Tier 1）
- P1、P2：跑主题和壳层测试以及受影响公共组件的测试，各跑一次 typecheck 和 `debt:audit`。
- P3：跑每页的相关测试。
- P4：跑 `debt:audit` 和 typecheck。
- 断言旧字号、字重或类名的测试，按新规则更新断言，不删除断言。

## 6. 决策（2026-10-02 用户已批准，全部同意）

| # | 决策 | 理由 |
|---|---|---|
| D-A | 字重：按钮由 600 改为 500；600 只给标题、KPI 主值与合计行 | Windows 下 600 一律渲染成粗体，这是粗体过量的主因 |
| D-B | 字号：工作台页统一用六档字号阶（标题 20、KPI 20、首屏结论数 24），取代原“标题 24–32、KPI 28–40”的起点范围；首页维持现状 | 1440 宽的密集工作台里，大字号会挤占数据空间 |
| D-C | 外壳：浮框式 9 页改为通栏无框 | 这是观感变化最大的一项，统一骨架的前提 |
| D-D | 首页数字从等宽代码字体改为比例字体加等宽数字，只改字体族 | 首页受 09-26 视觉基准锁约束，字号与留白不动 |
| D-E | 架构：纳入 §3.5 的 A1–A5，只改样式与布局架构，不动框架、数据层和业务 | 不改的话，页面会继续覆盖公共样式，收口之后还会走样 |
| D-F | 字体：随包 Noto Sans SC，不再依赖各机器的系统字体 | 网页和客户端显示一致，也解决 600 变粗体的问题；首次加载变大，靠分片缓解 |
| D-G | 执行 §8 的“现在做”清单（P5）；客户端技术选型等真正开做时再定 | 这些改动成本低，越晚改越贵 |

## 7. 交接状态与环境

- **已完成**：
  - 上一轮 R1–R9（字体族、字重、圆角、控件、子导航、表头）已由 Codex 验证：定向测试 420 个、壳层 82 个、发布 10 个全部通过，typecheck 通过，视觉复核 94 分。
  - 已以 build-real（manifest `dfdf10f8…`）发布到 5888 真实数据入口；业务数据对账尚未做。
  - 改前备份在 `.tmp/visual-audit-20261002/orig/`。
  - 2026-10-02：DESIGN.md 已按批准结果修订，PRD 已写好（Claude，仅文档）。
- **并入本方案的残项**：R6 残余（`controls-r1b.txt`）、`<strong>` 700、页面局部表格表头 11/600、首页 mono 数字。
- **工具**（`.tmp/visual-audit-20261002/`）：
  - `with-server.mjs`：临时在 5891 起服务，用法 `node with-server.mjs <script> args -- <script2> …`
  - `aesthetic-audit.mjs`、`controls.mjs`、`geom.mjs`、`rules.mjs`
  - `compose.mjs`：前后对比拼图
- **环境约束**：
  - 中文文件只用 Node fs 或编辑工具读写，不用 PowerShell 文本 cmdlet 或 shell 重定向；保持 UTF-8 无 BOM。
  - 工作树里有大量他人未提交的改动：不要 `git stash`、`checkout` 或 `reset`。DESIGN.md、frontend/AGENTS.md、docs/frontend-design-page-rules.md 都带有他人未提交的改动，要在其基础上编辑，不要回退。
  - 不要重启常驻 dev server，用 `with-server.mjs`。
  - vitest 与 Playwright 不要并发运行。
  - 带服务器的命令把输出重定向到文件，不要接 `| head`，否则会残留端口占用。
  - 5888 发布沿用 `package-real-build.mjs` + `switch-real-build.ps1`（同目录），发布前先经用户确认；回滚目标是 `runtime-switch.json` 中记录的上一版构建。

## 8. GUI 客户端预备

现状：
- 路由用 `createBrowserRouter`。
- API 地址是构建期变量 `VITE_API_BASE_URL`，在 `api/client.ts`、`api/agentRunStream.ts`、`api/agentLabRunStream.ts` 三处分别读取。
- 导出用 Blob/`download`（11 个文件），本地存储直接调 `localStorage`（5 个文件）。
- 中文字体靠系统自带；只有市场总览自带一个英文等宽字体。
- 还没有任何桌面端依赖。

**现在做**（成本低，越晚改越贵）：
1. 按窗口验收：最小窗口 1280×720 已纳入 DESIGN §10.1；另在 Windows 125%/150% 缩放下抽查。客户端窗口可以任意拉伸，不能只在 1440 下调好。
2. 字体随包（T5）。
3. 设计变量单一来源（A3）。将来客户端的原生部分（标题栏、启动页、托盘菜单）可以复用同一套颜色。
4. 外壳由路由声明驱动（A2）。客户端用独立窗口打开某一页时，可以直接复用 `layout` 字段。
5. P5 的具体内容（PRD FR-7）：
   - **运行时配置**：API 地址、数据模式等改为启动时读取的运行时配置，由网页部署或客户端注入，三处读取收成一处。
   - **平台服务**：导出/下载、本地存储、打印、剪贴板、打开外链统一走一个 `platform` 服务；网页版的实现保持现在的行为。
   - **路由**：保留 `createBrowserRouter`，支持配置 `basename`；客户端用自定义协议加载时，深链接刷新要可用。
   - **标题栏预留**：终端条按将来的窗口标题栏设计，留出拖拽区和窗口按钮的位置（Windows 在右侧，macOS 在左侧）。
   - **长时间运行**：路由切换时销毁图表与表格实例、停止轮询。验收标准：连续切换 50 次路由后，内存不持续增长。

**等真正开做客户端时再定**：
- 技术选型：
  - Electron 自带 Chromium，渲染和现在完全一致，但安装包较大。
  - Tauri 用系统 WebView，安装包小。Windows 上是 WebView2，同为 Chromium 内核；macOS 上是 Safari 内核，需要额外做一轮兼容回归。
  - 只做 Windows 的话，两者都可以。
- 原生能力：菜单、托盘、快捷键、多窗口、自动更新、离线提示。
- 安全：CSP；只开放白名单内的原生接口；登录凭据存进系统钥匙串或凭据管理器。

## 附录 A 逐页基线（2026-10-02）

骨架：A 浮框、B 通栏、C 混合、D 自带顶栏。“框”列为 ≥2 层/≥3 层的框数；A 类页面在此之外还多一层壳层框。

| 路由 | 骨架 | 粗体% 全页/首屏 | 框 ≥2/≥3 | 强调色元素 | 彩色标签 | 11px% | 非等宽数字 | 状态文案 | 其他 |
|---|---|---|---|---|---|---|---|---|---|
| `/` | D | 34/40 | 13/1 | 17 | 6 | 30 | 0（mono 64） | 样例2 演示1 待接入3 暂无5 | 卡片渐变 2 |
| `/positions` | A | 9.5/13 | 14/0 | 18 | 3 | 15 | 1 | 演示1 | |
| `/portfolio` | B | 58/62 | 19/7 | 75 | 15 | 1 | 6 | 模拟19 MOCK6 | 16px 字 27%；阴影 3 |
| `/market-overview` | D | 9.6/14 | 1/0 | 8 | 0 | 8 | 7 | — | MOCK 横幅遮挡导航 |
| `/ledger-pnl` | A | 44/64 | 16/5 | 12 | 4 | 34 | 62 | 演示1 | 700 字重 7.7% |
| `/balance-analysis` | B | 35/42 | 16/2 | 12 | 21 | 28 | 9 | 演示1 | 阴影 6 |
| `/bond-analysis` | B | 21/21 | 37/19 | 16 | 3 | 48 | 0 | — | 面板渐变 9；子导航与标题左边线差 18px |
| `/risk-overview` | B | 25/31 | 21/13 | 23 | 12 | 6 | 3 | 已接入1 暂无2 待接入3 | 发光圆点阴影 12、渐变 4；有 36px 字 |
| `/product-category-pnl` | B | 43/36 | 35/12 | 43 | 3 | 1 | 0 | 已就绪1 | 渐变 4、阴影 2；标题左边线 421 |
| `/stock-analysis` | D | 18/21 | 15/0 | 15 | 2 | 33 | 22（mono 11） | 已就绪5 Mock1 | |
| `/pnl-by-business` | A | 38/38 | 1/0 | 3 | 0 | 12 | 1 | Mock2 无数据1 | 有 10px 字 |
| `/balance-movement-analysis` | B | 31/49 | 63/24 | 65 | 4 | 86 | 30 | 已同步2 | 截断 22 处 |
| `/average-balance` | A | 24/22 | 16/0 | 12 | 2 | 10 | 3 | 演示1 暂无4 | |
| `/kpi` | A | 50/50 | 0/0 | 1 | 0 | 10 | 3 | — | 按钮阴影 1 |
| `/cross-asset` | C | 50/39 | 22/6 | 7 | 3 | 33 | 5（mono 9） | 待接入3 | 三条不同左边线 |
| `/pnl-attribution` | A | 18/23 | 3/0 | 2 | 1 | 13 | 0 | 演示1 已就绪2 | 页签阴影 2 |
| `/risk-tensor` | A | 48/69 | 16/10 | 1 | 0 | 4 | 10 | 待接入4 | |
| `/market-data` | C | 28/37 | 24/16 | 10 | 6 | 40 | 0 | 已接入1 | 标题条渐变 7 |
| `/macro-toolkit` | A | 50/53 | 14/2 | 43 | 4 | 32 | 6 | 已接入1 已就绪1 | 按钮阴影 3 |
| `/team-performance` | A | 39/28 | 28/17 | 32 | 46 | 17 | 25 | 演示1 | KPI 卡阴影 7；表格行高 69 |
| `/publication-showcase` | D | 28/28 | 4/0 | 15 | 3 | 48 | 0 | 已就绪1 | 700 字重 10%；全大写英文眉标 5 个 |

## 附录 B 给 Codex 的启动指令（可直接粘贴）

```text
请按 docs/frontend-aesthetic-compliance-plan.md 执行前端整体审美收口。
先读 DESIGN.md（重点 §1.1、§3、§4.2、§5、§5.3、§5.4、§6、§10.1–§10.3）、docs/prd-frontend-aesthetic-compliance.md 和 frontend/AGENTS.md，再读方案 §1–§8。
已批准的决策：D-A 至 D-G 全部同意（2026-10-02）。DESIGN.md 已按批准结果修订，规则与数值以 DESIGN.md 为准；不要再改规则或章节编号，发现规则与代码、脚本冲突时先报告。
从 P0 开始，按 P0→P5 推进，每个阶段单独提交。
每个阶段结束时贴出：探针汇总表（改前/改后）、关键截图路径、测试与 typecheck 结果。
P1 结束后停下：把样板页 /ledger-pnl 的同视口前后截图和指标对比交给用户确认，确认后再做 P2 及以后。发布到 5888 前也须经用户确认。
不改业务逻辑、指标口径、接口、权限和关键流程；不动 DESIGN.md §9 与 docs/frontend-design-page-rules.md 锁定的页面顺序；遵守方案 §7 的环境约束。
规则与页面实际冲突时，在阈值文件里登记例外并写明理由，不得自行放宽门槛。
```
