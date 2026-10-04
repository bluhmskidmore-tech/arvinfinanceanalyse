# 前端全量审计报告（2026-10-04）

审计对象：`frontend/`（React 18 + TS 5 + Vite 8 + Vitest 4，35 个业务域，58 条路由声明，563 个测试文件 / 6499 个用例，非测试源码 907 个文件约 54.2 万行）。

审计方式：机械化门禁（typecheck / lint / 全量 Vitest / debt:audit / 编码完整性 / style 审计）+ **21 条路由 × 双视口的浏览器实测**（`scripts/visual-compliance-audit.mjs`，mock 数据）+ 三路静态审计（业务口径、架构与测试、UI 与设计系统）。

本报告为只读审计，未修改任何业务代码。审计对象是当前**工作树**（含大量未提交改动），不是已提交版本。

## 总体结论

前端的工程底座仍然干净：类型检查零错误、ESLint 零错误、编码完整性零损坏、生产构建对 mock 有硬闸门。但相比 2026-09-17 的那次静态审计，门禁出现两处实质回退，且首次完成的浏览器实测暴露出设计合规仍是半成品。

三条最需要处理的结论：

1. **门禁回退**：`debt:audit` 从 6/6 通过变为 1/7 失败（`audit_frontend_style_architecture` 报出 27 个新增/升高的违规身份，集中在 bond-analytics 的 `!important` 覆盖）；全量测试从 2 个失败涨到 14 个失败文件 / 12 个失败用例，其中 7 个是真实代码或文案回归，2 个让"生产禁止 mock"这条硬闸门失去了有效测试证明。
2. **浏览器实测首次给出全量答案**：1440×900 下 21 条路由只有 `/ledger-pnl` 一条通过 DESIGN §10.1 全部门槛；1280×720 下 18 条不通过。与 2026-10-02 同口径基线对比，粗体占比已大幅改善（如 `/ledger-pnl` 44%→11.8%、`/portfolio` 58%→26.2%），但"框套框"（≥2 层容器）在余额变动、产品分类、团队绩效、风险总览、市场数据、风险张量 6 个页面上数字**完全未变**，说明 P2/P3 批次的容器收口尚未启动。
3. **前端越界承担正式金融计算并据此判定业务状态**仍是系统性问题，本次新增确认 5 处（pnl 对账、pnl-attribution 归因闭合、cross-asset ERP 判定、bond-dashboard 占比反推配平、kpi 限额色态），09-17 记录的两条高严重度问题（balance 对账阈值、risk-tensor 单位猜测）均未修复。

## 一、机械化门禁结果

| 命令 | 结果 | 关键事实 |
| --- | --- | --- |
| `npm run typecheck` | 通过 | 零类型错误 |
| `npm run lint` | 通过 | 0 错误 / 1 警告：`src/features/pnl/PnlByBusinessPage.tsx:39` react-refresh 导出警告 |
| `npm run test` | 失败 | 14 文件失败 / 12 用例失败 / 3 跳过 / 6484 通过，另 1 个未捕获错误；耗时约 17 分钟 |
| `npm run debt:audit` | **失败** | 1/7 失败：`audit_frontend_style_architecture` FAIL（27 个新增/升高违规身份）。其余 6 项通过 |
| `audit_encoding_integrity.mjs` | 通过 | 4812 文件，U+FFFD 0/0 |
| `style:audit`（对比 HEAD） | 有新增 | 工作树相对 HEAD 新增 `!important` 与 `:has()` 违规，集中在 `workbenchShell.css`、`workbenchDeferredChrome.css` |
| 浏览器实测 | 见 §五 | 21 路由 × 2 视口，JS 错误 0，横向溢出 0 |

与 09-17 的对比：当时 6/6 PASS、测试 2 失败；本次门禁状态变差，且差在**债务基线与测试**，不是类型或编码。

## 二、门禁回退的具体内容

### 2.1 debt:audit A5 样式架构（新增失败）

`audit_frontend_style_architecture.mjs` 报 `rawColor 539/552、fontScale 566/650、important 2230/2305、pageHas 662/663`，判定 27 个新增违规身份。可复核的新增条目主要来自 bond-analytics：`BondAnalyticsFilterActionStrip.module.css:93,99,176,177,185` 与 `BondAnalyticsViewContent.module.css:159,160,163,180,468,483` 对 antd 控件高度/字号做 `!important` 覆盖（该域 `!important` 总数已 75 处）。这是"用 `!important` 压组件库"的既有模式继续扩散，与 DESIGN 的共享层纪律相冲突。

### 2.2 全量测试 12 个失败用例的分类

环境/配置类（3 个文件，非业务回归）：`scripts/homeRuntimeAcceptance.test.mjs`、`scripts/startupBundleParsing.test.mjs`、`scripts/visual-compliance-audit.test.mjs` 全部报 `Cannot bundle Node.js built-in "node:test"`。根因是 `vitest.config.ts` 未设置 `include`，Vitest 用默认规则把 `scripts/*.test.mjs` 也纳入，而这些脚本是为 `node --test` 写的，在 jsdom 环境下无法加载 Node 内建模块。这是长期存在的配置缺陷，本次集中暴露。

测试桩失效类（2 个用例，需警惕）：`src/test/parseEnvMode.test.ts` 中"生产环境拒绝显式 mock 覆盖"（eager / deferred 两个客户端）失败，报 `expected [Function] to throw`。该用例用 `vi.stubEnv("PROD", true)` 打桩，而 `api/dataSourceMode.ts:7` 读的是 `import.meta.env.PROD`；同文件里"PROD 下 mode='real' 不触发 fail-fast"的用例反而通过，符合"`PROD` 桩未生效"的表现。**结论不是生产防护已失效，而是这条硬闸门目前没有有效测试证明**——按项目"不猜"的纪律，需要单独验证 `import.meta.env.PROD` 在测试环境能否被桩替换后再定性。

真实回归（7 个用例，按业务影响排序）：

- `src/test/LiveRouteReadiness.test.tsx` — `/positions` 的真实页面锚点 `positions-list-candidate-boundary` 已从 `PositionsView.tsx` 消失，路由就绪契约与源码脱钩。
- `src/test/CustomerDetailModal.test.tsx` — 持仓弹窗渲染值与断言不符（实际输出 `信用债/信用债/AAA`，断言期望 `信用债/credit/...`），是真实展示差异。
- `src/features/bond-analytics/lib/bondAnalyticsOverviewModel.test.ts` — 加载态 truth strip 的标签由"新鲜度"改为"更新时间"，测试未同步。
- `src/test/BondDashboardPage.test.tsx`、`src/test/LedgerPnlPage.test.tsx` — 首屏 `result_meta` 降级与非正式口径文案断言失败。
- `src/test/AdbDeepAnalysisSection.test.tsx`、`src/test/ProductCategoryAdjustmentAuditPage.test.tsx` — "最新快照降级""当前页面保留重试入口"等降级/错误面文案找不到，需确认是文案改动还是降级面被削弱。
- `src/test/StartupPerformanceGuards.test.ts` — 启动采样器源码锚点漂移（期望含 `/src/mocks/homeMarketTickerMockClient…`）。
- `src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx` — 导出用例 15 秒超时，与本次未捕获错误同文件，需人工复核是性能还是环境抖动。

历史未决：`src/test/StockAnalysisPageSizeGuard.test.ts` 报 2204 > 2203，即 09-17 记录的 stock-analysis 样式表行数预算问题仍未决策（收紧或上调基线）。

## 三、业务口径：前端越界计算与状态判定

按严重度列出本次确证的问题。带 `*` 的是 09-17 已记录、本次确认仍未修复。

### 高

- `features/pnl/pnlByBusinessPageModel.ts:399-421` — 前端自算 `preAdjustmentPnl`（利息+公允价值+资本利得）与 FTP 对账差，并以自有 `toleranceYuan = 0.01` 判定"已对平"。正式勾稽口径与容差都由前端定。
- `features/pnl-attribution/components/pnlAttributionViewModel.ts:61,390,420-444` — 前端求和效应、算 `coveragePct`，以 `VOLUME_RATE_CLOSURE_TOLERANCE_YUAN = 10_000` 判定"归因闭合 / 存在未解释差额"。
- `features/cross-asset/lib/crossAssetAnalytics.ts:609-610,658-659` — 前端自算 ERP =（1/PE×100）−10Y，并用镜像阈值 4.0 / 2.75 判定"股票偏便宜/偏贵"。代码注释承认阈值是后端常数的镜像，靠测试用例兜同步。
- `features/bond-dashboard/utils/format.ts:207-260`（及 :264-295 legacy 路径）— 后端占比缺失时，前端按市值反推并用**最大余数法强行配平到 100**，再把最大持仓调整为余数。产出的是"看起来来自后端的占比"，来源标注只写在 tooltip 降级路径。
- `features/workbench/components/kpiFormat.ts:70-80` — `value === null` 直接返回 `"ok"`，即**缺失值被渲染成"未超限"**；并以自有 0.8 / 1.0 判定"接近/突破限额"。
- `features/kpi-performance/components/MetricTable.tsx:65-69,97-105` — 前端自定 1 / 0.8 / 0.6 三档判定达标色态；后端已给 `backendSummary` 仍自行累加 weight 与 score（空串→0）。
- `* features/balance-analysis/pages/balanceAnalysisPageModel.ts:1211-1213,1411-1418` — 对账容忍阈值（绝对差 ≤ 1 亿元或相对差 ≤ 0.05%）仍由前端常量定义并判定"可核对"。本次仅新增了阈值披露文案（`statusDetail` 显示生效阈值），判定权未下沉。
- `* features/risk-tensor/RiskTensorPage.tsx:277-297` — `ratioPercentDisplay` 仍按数量级启发式猜单位（abs≤1 当 ratio ×100，abs≤100 当百分数直接用），驱动发行人集中度与 30 日流动性缺口两张 KPI 卡（:2169、:2182、:2645、:2682）。
- `* features/product-category-pnl/pages/model/productCategoryManagementMonitoringModel.ts:273-275` — "达标所需年化收益率 / 需提升 bp"（`ftp + (targetPnl/scale) × (365/days) × 100`）仍在前端推导，只是从 `productCategoryPnlPageModel.ts` 迁到了 `model/` 子目录。

### 中

- `features/balance-movement-analysis/hooks/useBalanceMovementViewModel.ts:299-302,319-337` — 前端自算变动率 %，并把后端期限分桶重新聚合求和（含 `share_pct` 直接相加），后端新增桶键会静默漏计。
- `features/balance-movement-analysis/lib/balanceMovementReconciliationModel.ts:146-153` — 跨行求和 `reconciliation_diff` 得"可比差异"，缺失项 `?? 0` 计入合计。
- `features/average-balance/components/adbComparisonMetrics.ts:14,21,24,53-66` — 偏离度派生、5% 预警阈值、合并其余分桶并重算偏离。
- `features/average-balance/components/AverageBalanceView.tsx:69-71,165-174` — 0.9999 硬编码判定"利率覆盖不足"，前端算同比 %。
- `features/cashflow-projection/pages/cashflowProjectionPageModel.ts:134,149,156` — 0.05 硬编码判定久期缺口正负与"接近平衡"。
- `features/cross-asset/lib/crossAssetDriversModel.ts:24-30,42-70,97-104` — 0.12 / 0.1 / 0.05 硬编码判定"偏多/偏空/中性"。
- `features/bond-analytics/lib/alignmentThresholds.ts:3-7` + `bondAnalyticsHomeCalculations.ts:105-110` — 0.5% / 1bp / 0.1pp 判定 baseline 与 candidate 是否"对齐"。
- `features/pnl-attribution/components/campisiAttributionPanelSupport.ts:130-133,169` — 后端无占比字段时前端按 `total_return` 派生 `contribution_pct`；`CampisiAttributionPanel.tsx:123` 自定重要性门槛 `max(|总回报|×0.5%, 100万)` 过滤"几乎无影响"的行。
- `features/product-category-pnl/pages/ProductCategoryComparisonCharts.ts:571` — `(current − prior) × 100` 产出"同比差（bp）"，假定后端是 ratio。
- `features/liability-analytics/pages/liabilityAnalyticsPageModel.ts:87`、`LiabilityAnalyticsPage.tsx:918` — nim ×10000→bp、yield ×100，均假定后端为 ratio。
- `features/concentration-monitor/concentrationFormat.ts:74-81` — 前端算限额使用率。

### 缺失值语义（中）

- `features/balance-analysis/hooks/useBalanceAnalysisData.ts:49-52` — `finiteNumber` 把 null/undefined/NaN 全归一为 0，缺失余额被当真零参与过滤排序。
- `features/pnl/PnlByBusinessFormalRowsTable.tsx:33,51`、`PnlByBusinessDriverOverviewPanel.tsx:16,20,33,132` — 缺失规模 `?? 0` 渲染为真零并参与过滤。
- `features/balance-movement-analysis/lib/balanceMovementBusinessModel.ts:183` — 缺失余额回退字符串 `"0"`。
- `* api/liabilityAdbClient.ts:180-181` — `normalizeNullableNumber` 仍是 `Number(value)`，空串→0，违反共享层语义，影响 NIM、日均余额等字段。
- `* features/positions/components/CustomerDetailModal.tsx:171,177` — `parseFloat(it.balance)` 无 NaN 守卫，缺失余额会以 "NaN 亿元" 进图。

### 单位与精度（中）

- `features/pnl/pnlByBusinessPageModel.ts:286,297-313` — 同一字段按数量级在元/万元间切换；万元可变位数与亿元固定 2 位并存。
- `features/pnl-attribution/components/CampisiAttributionPanel.tsx:43-47` — 同一列金额 <50 万显示"元"、否则"亿元"，单位与精度随行变化。
- `features/bond-analytics/components/BondAnalyticsCockpitPrimitives.tsx:34-38` — 轴刻度按 1e8 / 1e4 切单位且 ≥1e9 改 0 位小数，与正文 2 位不一致。
- `features/pnl/pnlByBusinessPageModel.ts:405,408` — 浮点元值直接相减作为正式对账数。

### 存疑（需业务确认口径，未猜定义）

- `features/pnl-attribution/components/AdvancedAttributionChart.tsx:85`、`PnLCompositionChart.tsx:29` — `unit === "pct" ? raw*100 : raw` 是否覆盖后端全部单位枚举。
- `features/cross-asset/lib/crossAssetAnalytics.ts:340-357` — 前端算分位并 10/30/70/90 分档，是否属正式风险分档。
- `features/workbench/dashboard-home/useMockHomeFirstScreenView.ts:5-22` — mock 首屏在生产包内懒加载，仅由 `client.mode !== "real"` 门控。

## 四、架构、API 层与测试健康度

正面：40 个懒加载路由目标全部解析到真实文件；生产构建对 mock 有硬闸门（`api/dataSourceMode.ts:14,21` 在 PROD 下对 mock 抛错，且 `VITE_DATA_SOURCE` 未显式设置时拒绝静默回退）；`src` 内零 `@ts-ignore`、零 `test.todo`、仅 6 处 `eslint-disable`（全是 react-refresh）且无 `exhaustive-deps` 抑制。

问题：

- **孤儿域**：`features/source-preview/` 完整实现但 `app/navigation.ts:348-359` 标为 `readiness: "placeholder"` + `navigationVisibility: "hidden"`，`routes.tsx:164` 把非 live 区段统一导向占位页；`SourcePreviewPage.tsx` 只被 `src/test/SourcePreviewPage.test.tsx:9` 引用。`features/publication-showcase/` 由 `publicationShowcaseGate.ts:17` 限制为 `DEV && VITE_DATA_SOURCE=mock`，生产必然渲染 404。`features/prototype/` 是空目录却占一个域位。
- **mock 与生产 client 同层**：`src/api/` 下 16 个 mock 模块与生产 client 并列，`macroToolkitMockClient.ts` 3350 行、`marketDataMockClient.ts` 2987 行、`bondAnalyticsMockClient.ts` 1344 行、`balanceMovementMockClient.ts` 952 行。零静态导入进生产路径（仅动态 import），但样例数据与生产代码同层，仍是泄漏面。
- **demo 载荷写进生产 client**：`api/agentClient.ts:91,150,163,179,224` 内联 `"Agent is running in demo mode."`、`model: "frontend-demo"`、`owner_user_id: "frontend-demo"` 等真实可达的 demo 分支。
- **契约防线仍有 3 个冻结漂移**：`src/test/BalanceContractSync.test.ts:376`（`identity_source` 多声明 `"system"`）、`:788`（`BalanceMovementPayload` 缺 `unmapped_gl_accounts`）、`:816`（`BalanceMovementDatesPayload` 缺 `upstream_control_report_dates`）仍是 `it.skip`。后端真实触发任一漂移会穿透全部 mock 绿测试。
- **测试密度失衡（高）**：`features/ledger-pnl` 28 个源文件仅 1 个内联测试文件 / 4 个用例；`bond-analytics` 56 源 / 8 测试；`average-balance` 22 源 / 1 测试；`agent` 31 源 / 2 测试。另有 7 个域（`cube-query`、`news-events`、`publication-showcase`、`agent-lab`、`source-preview`、`ledger-dashboard`、`kpi-performance`）只有平铺目录 `src/test/` 的测试、零内联测试。`src/api/` 下 56/75 个非测试模块无同层测试，其中 8 个（`bondAnalyticsNormalization.ts`、`marketDataMocks.ts`、`pnlMockClient.ts`、`workbenchDashboardApi.ts` 等）全仓零测试引用。
- **测试双轨与脆弱断言**：平铺 `src/test/` 286 文件 / 3473 用例与 features 内联测试并存；`src/test/ApiClientCompositionBoundary.test.ts:13-40` 读取 20 个源文件再做字符串断言；`src/components/layout/DataTable.test.tsx:81-652` 大量绑定 CSS 字面量。浅断言整体占比低（192 / 29892），集中在 `DashboardHomePage.test.tsx` 26 处、`ProductCategoryPnlPage.test.tsx` 21 处。

## 五、浏览器实测（本次新增，21 路由 × 1440×900 / 1280×720）

方法：本地 Vite mock 服务（`127.0.0.1:5891`，`VITE_DATA_SOURCE=mock`）上运行 `scripts/visual-compliance-audit.mjs --profile all`，判定按 DESIGN §10.1 门槛。全部门槛零 JS 错误、零横向溢出。

每格为"未通过的规则条数"：

| 路由 | 1440×900 | 1280×720 | | 路由 | 1440×900 | 1280×720 |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | 17 | 2 | | `/pnl-by-business` | 8 | 2 |
| `/positions` | 4 | 1 | | `/balance-movement-analysis` | 21 | 3 |
| `/portfolio` | 10 | 1 | | `/average-balance` | 8 | 2 |
| `/market-overview` | 1 | 1 | | `/kpi` | 9 | 2 |
| `/ledger-pnl` | **0** | **0** | | `/cross-asset` | 17 | 3 |
| `/balance-analysis` | 11 | 1 | | `/pnl-attribution` | 12 | 3 |
| `/bond-analysis` | 8 | **0** | | `/risk-tensor` | 12 | 1 |
| `/risk-overview` | 17 | 3 | | `/market-data` | 17 | 3 |
| `/product-category-pnl` | **22** | 2 | | `/macro-toolkit` | 15 | 2 |
| `/stock-analysis` | 12 | 3 | | `/team-performance` | 18 | 1 |
| | | | | `/publication-showcase` | 8 | **0** |

系统性问题（按受影响路由-视口数排序，共 42 个组合）：

- `controls.geometry` 32/42 —— 控件高度/圆角不达标最普遍，实测样例为表格内按钮高 40.3px（门槛 36px）。
- `skeleton.leftEdgeRange` 22/42 —— 同一首屏内面包屑/子导航/标题三条左边线不一致，最差差 194px。
- `containers.undocumentedDepth2` 18/42、`containers.depth2` 15/42（最差 63 个）、`containers.depth3` 11/42（最差 24 个）—— "框套框"未收口。
- `typography.boldPct` 18/42（门槛 15%，最差 48%）、`typography.foldBoldPct` 11/42（最差 56%）、`typography.sizes` 17/42（最差 52 处刻度外字号）、`typography.smallPct` 10/42（最差 86%）。
- `stability.truncation` 18/42（最差 32 处文本截断）。
- `decoration.radii` 10/42（Shape Lock 违规）、`decoration.shadows` 8/42、`decoration.gradients` 5/42。
- `tables.rowHeight` 9/42（实测 26px，门槛 28/32）、`tables.headerTypography` 9/42、`tables.cellTypography` 7/42（最差 217 个单元格）、`tables.numericAlignment` 3/42。
- `states.demo` 8/42 —— **mock 模式的产物**（每页挂"模拟数据"徽标，门槛上限 2），真实数据下不判定此项。

### 与 2026-10-02 基线的对比（同 mock 数据、1440×900）

| 路由 | 粗体% 基线 → 本次 | ≥2/≥3 层框 基线 → 本次 |
| --- | --- | --- |
| `/ledger-pnl` | 44 → 11.8 | 16/5 → 0/0 |
| `/portfolio` | 58 → 26.2 | 19/7 → 10/0 |
| `/risk-tensor` | 48 → 31.9 | 16/10 → 16/10 |
| `/balance-analysis` | 35 → 18.6 | 16/2 → 8/2 |
| `/product-category-pnl` | 43 → 40.1 | 35/12 → 35/12（未变） |
| `/balance-movement-analysis` | 31 → 25.3 | 63/24 → 63/24（未变） |
| `/team-performance` | 39 → 35.8 | 28/17 → 28/17（未变） |
| `/market-data` | 28 → 27.7 | 24/16 → 24/16（未变） |
| `/risk-overview` | 25 → 25.3 | 21/13 → 21/13（未变） |

读法：字重收口（R 轮）在多数页面生效，其中 `/ledger-pnl` 已达全部门槛；容器层级（框套框）在 6 个页面上完全没有推进，这是下一阶段的主要工作量所在。注意两套探针（10-02 的 `aesthetic-audit.mjs` 与本次的 `visual-compliance-audit.mjs`）统计口径同源但字段不完全一致，上表按最可比的字段对齐，趋势判断可靠、绝对值不作为门禁依据。

### 视觉与可访问性（静态部分）

- **深色页浅色块（高，本次复核后下调为"需按视图确认"）**：`agent` 确为已登记的 Nocturne scope（`theme/themeScopes.ts:11`、`tokens.css:487`，`AgentWorkbenchPage.tsx:1583` 显式声明），`AgentWorkbenchPage.css:10-56` 定义 44 个浅色 hex 变量（`--agent-hex-*`）并在本文件内被 `var()` 消费 106 处，另有 `#ffffff`、`#f8fbff`、`#fff7f6`、`#f0fbf5` 等浅色底（:155、:165、:289、:321、:342、:352、:450、:491、:621、:798、:863）。但本次在 `/agent` 首屏（1440×900，mock）实测未捕获到 ≥80×30 且亮度 >0.75 的浅色块，说明违规视图不在默认首屏，需要按具体 tab/视图复核才能定性。`agent-lab` 复用同一外壳，风险同源。
- **未重映射的浅色 token（中）**：`--moss-color-info-50`（`tokens.css:21`）、`--moss-color-neutral-50/100`（:65、:66）只有浅色定义、无深色重映射，被 18 个 feature CSS 文件共 232 处消费，其中 `AgentWorkbenchPage.css:200,259,297,418,481,772` 落在深色页上。
- **`--ib-*` 与 tone 变量误用（中）**：深色 scope 上直接消费 `var(--ib-up/down/warn)` 共 318 处 / 32 个非测试文件。`tokens.css:318-334` 只在 `.theme-dh-api` 下把它们重映射到 `--dh-api-*`，规范 Nocturne 块（`tokens.css:451+`）不做映射，因此当前靠 `ThemedRouteBoundary` 兜住；`BondAnalyticsAgentDrawer.tsx:40,48` 设了 scope 但没有 `.theme-dh-api`，antd Drawer 会 portal 到 body，`--ib-*` 会回落到 `:root` 的浅色值（需运行时复核）。bond-analytics 还在 `BondAnalyticsViewContent.module.css:308-320` 自抄了一份映射，属重复防线。生产代码中唯一用 `TONE_CSS_VAR`（浅色入口）的是 `features/bond-analytics/utils/formatters.ts:88`。
- **图表无障碍（高）**：`components/charts/BaseChart.tsx:50-73` 无 `role`、无 `aria-label`，全仓 0 处 ECharts `aria` 配置，canvas 图表无文本替代；`ChartCard.tsx:135` 只标注 `<figure>`。10 处 `<Modal>/<Drawer>` 中只有 3 处显式 `role="dialog"`/`aria-modal`（antd 可能自带，未运行时确认）。`prefers-reduced-motion` 覆盖 25 个 CSS 文件，而 16 个文件有 `animation`、35 个有 `transition`，未全覆盖。
- **缺失值字面量（中）**：渲染层 `—` 字面量 32 处（应统一 `EM_DASH`，已被 247 文件使用 1304 次）。代表：`PnlByBusinessFormalRowsTable.tsx:49,58`、`PnlByBusinessMonthlyBreakdownPanel.tsx:97`、`LedgerPnlAccountDetailSection.tsx:18`（`——`）、`SourcePreviewPage.tsx:91`；另有 3 处把 `—` 当日期区间分隔符（`ActionAttributionView.tsx:260`、`BenchmarkExcessView.tsx:288`、`LedgerPnlCandidateFinancialIndicatorsPanel.tsx:503`）。
- **09-17 已修复项**：`components/page/PagePrimitives.module.css:78-91` 的 `headerBadgePositive/Accent` 已改为 `var(--dh-api-muted, ...)` 透明底，不再硬编码浅色 hex，该项可关闭。
- ** formatter 重复（中）**：14 个文件自声明 `formatYi`、15 个自声明 `formatPct`（`dashboard-home` 一个域内两处逐字重复）；`agent-lab`、`prototype`、`publication-showcase`、`source-preview` 四个域完全未用共享 `src/utils/format.ts` 或 `src/pageModel`。内联 `style={{}}` 176 处，`SourcePreviewPage.tsx` 24 处最多。

## 六、建议处理顺序

1. 恢复门禁：`debt:audit` 的 27 个新增样式违规身份（bond-analytics `!important` 为主）与 7 个真实测试回归逐个定性；`LiveRouteReadiness` 与 `parseEnvMode` 两条要优先，前者是契约脱钩、后者是安全闸门的证明缺口。
2. 澄清 `parseEnvMode`：确认 `import.meta.env.PROD` 能否被 `vi.stubEnv` 替换，恢复"生产禁止 mock"这条硬闸门的有效测试证明。不要用放宽断言的方式消掉失败。
3. 解冻 `BalanceContractSync` 的 3 个 skip 漂移（契约防线收口）。
4. 业务口径下沉：优先处理 5 处新增的"前端算正式指标并判定业务状态"（pnl 对账、归因闭合、ERP 判定、bond-dashboard 占比反推、kpi 限额色态），以及 `kpiFormat.ts:70` 的"缺失即未超限"。每一处都需要先确认后端口径，不要前端自行定义。
5. 决策 `source-preview`（接入或下线）与 `publication-showcase`（保留为仅 dev 的展示页需明确登记）；清理 `prototype` 空目录。
6. 浏览器实测暴露的批量项按计划推进：先做 `controls.geometry`（32/42，改动集中、收益最大）与容器层级收口（6 个页面完全未动），再做字重与截断。
7. `BaseChart` 加 aria 文本替代（一处修复全站受益）；补 `ledger-pnl`、`bond-analytics`、`average-balance` 的测试密度。

## 七、验证局限

- 浏览器实测跑在 **mock 数据**下（与 2026-10-02 基线同口径），因此 `states.demo` 8/42 是模式产物而非真实违规；真实数据下的降级面、空态、报错面未覆盖。后端未启动（7888 未监听），本次未做真实数据链路的浏览器验证。
- `/agent` 的深色浅色块问题未在首屏复现，按具体视图复核前不能定性为已确认视觉违规；`BondAnalyticsAgentDrawer` 的 portal 回落同理，属运行时待确认。
- 静态审计的"前端越界计算"清单以代码证据为准，凡标注"存疑/需业务确认"的条目均未猜口径；数量级启发式、硬编码阈值是否属业务授权口径需对照后端响应契约最终定性。
- 可访问性只覆盖静态标记与统计，键盘可达性、焦点顺序、颜色对比度未实测。
- 依赖 CVE 未联网核实。
- 测试失败中 3 个 `scripts/*.test.mjs` 与 1 个未捕获错误与本次沙箱环境（Vitest 默认 include 命中 node:test 脚本、文件代理 shim 抛 `instanceof` 错误）相关，已单独标注，不计为业务回归；在干净环境复核前不作为项目缺陷结论。
