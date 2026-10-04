# 前端全量审计报告（2026-09-17）

审计对象：`frontend/`（React 18 + TS 5 + Vite 8 + Vitest 4，34 个业务域，1531 个源文件，523 个测试文件 / 5897 个用例）。
审计方式：机械化检查（typecheck / lint / Vitest 全量 / debt:audit / 编码完整性 / style 审计）+ 四路静态审计（架构与 API 层、指标正确性链路、UI 与设计系统、测试与代码健康度）。
本报告为只读审计，未修改任何代码。

## 总体结论

前端整体健康度高于一般水平：类型检查零错误、ESLint 零错误、债务基线 6/6 通过、编码完整性零损坏、生产构建有硬闸门杜绝 mock 静默上生产、深色页盈亏着色有测试级互锁、TODO 密度近零、生产代码 `any` 仅个位数。需要处理的问题集中在四类：两个高严重度的前端业务口径问题（可能显示错误数字）、一组前端越界承担的正式计算、两个真实深色页视觉违规、以及一条自知有洞的契约防线（3 个被 skip 冻结的前后端漂移）。

## 一、机械化检查结果

| 命令 | 结果 | 关键事实 |
| --- | --- | --- |
| `npm run typecheck` | 通过 | 零类型错误 |
| `npm run lint` | 通过 | 0 错误 / 1 警告：`PnlByBusinessPage.tsx:92` react-refresh 导出警告 |
| `npm run test` | 2 失败 | 5892 通过 / 2 失败 / 3 跳过；失败均为 stock-analysis 深层研究样式表行数超预算守卫（实测 2409 行 vs 基线 2260/2203），需人工判断收紧 CSS 还是上调基线 |
| `npm run debt:audit` | 通过 | 6/6 PASS，各项贴近但未超基线（如 ProductCategoryPnlPage.tsx 5072/5153 行、TSX style props 295/297，缓冲已很薄） |
| `audit_encoding_integrity.mjs` | 通过 | 4581 文件，U+FFFD 0/0 |
| `style:audit` / `style:inventory` | 通过（有警告） | 工作区新增 1 行 `style=`（MomentumAndVolatilityPanels.tsx）；tokens.css 有 12 个重复定义的 CSS 变量 |

## 二、高严重度问题（可能显示错误数字/错误业务状态）

1. **`balance-analysis/pages/balanceAnalysisPageModel.ts:1211-1213, 1411-1418`** — 前端自定义对账阈值（绝对差 ≤ 1 亿元或相对差 ≤ 0.05%）直接判定并展示"可核对（aligned）"业务状态。这既违反"正式金融计算不进前端"，1 亿元绝对容忍度的口径也定义不明，可能把大额对账差异显示为"可核对"。需业务确认口径后下沉后端。
2. **`risk-tensor/RiskTensorPage.tsx:277-297`**（驱动 2080、2093、2522、2559 行的发行人集中度与 30 日流动性缺口 KPI 卡）— `ratioPercentDisplay` 按数量级启发式猜测单位（abs≤1 当 ratio ×100，abs≤100 当百分数直接用）。边界数值会 100× 显示错误。两个字段的契约单位需业务确认并显式化。

## 三、中严重度问题（语义不一致/口径隐患）

- `balance-analysis/hooks/useBalanceAnalysisData.ts:49-52, 114-118` — 缺失值归一为 0 后参与过滤排序，"余额缺失"行被当作"真零余额"静默剔除，不以 EM_DASH 呈现。
- `balance-analysis/pages/balanceAnalysisPageModel.ts:2068` — 同一图表系列混用 `full_scope_gap_amount` 与 `gap_amount` 两种口径，无标注。
- `balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx:3688-3711` — 前端把后端期限桶重新聚合求和（含 share_pct 直接相加），后端新增桶键会静默漏计。
- `pnl-attribution/components/pnlAttributionViewModel.ts:391-396` — 前端用 Decimal 重算 Campisi 归因闭合和，财务勾稽口径应与后端对齐。
- `api/liabilityAdbClient.ts:180-181` — `normalizeNullableNumber` 对空串/垃圾串无防护：`Number("")` → 0，空串变真零，违反共享层语义；影响 NIM、日均余额等大量字段。
- `kpi-performance/pages/KpiPerformancePage.tsx:200-205` — 指标列表加载失败仅瞬时 toast 后呈现空态，与"确实无指标"不可区分（owners 侧有持久错误面，metrics 侧没有）。
- `positions/components/CustomerDetailModal.tsx:171-189` — `parseFloat(it.balance)` 无 NaN 守卫，缺失余额会以 "NaN 亿元" 进 ECharts tooltip；同一条余额在 tooltip/y 轴/表格三种精度。
- `workbench/module-home/moduleHomeModel.ts:1233-1284` — 前端自算跨源核对差（浮点减法显示"正式余额核对差异"），与 balance-analysis 域对账逻辑是两套独立实现。
- `workbench/dashboard-home/dashboardHomeFirstScreenView.ts:533-539` — 前端不信任后端 dv01 Numeric 的 unit/display 而自行 /1e4（共三处同口径 workaround），后端若修正契约会出现双重换算。属后端契约缺陷的前端补丁，需后端确认 dv01 unit/raw 语义。
- **契约隐患**：同名字段 `proportion` 在 pnl 端点是 0-1 ratio、在 adb 端点是百分数，当前前端处理正确但极易回归，建议在契约文档固化。

## 四、架构与 API 层

正面：39 个路由目标全部存在；全部 MockClient 仅经 mode 开关懒加载，生产构建未显式声明 `VITE_DATA_SOURCE` 直接 throw，零静默 mock 回退；contracts 层 15 个域契约文件职责清晰；pageModel 分层有显式规则注释。

问题（按严重度）：

- **高**：`product-category-pnl/pages/productCategoryPnlPageModel.ts:4701-4721` 前端推导"达标所需年化收益率/需提升 bp"（`ftp + (targetPnl/scale)*(365/days)*100`），是正式金融计算，违反边界，应移后端契约。
- **中**：`features/source-preview/` 实现完整但 `navigation.ts:340` 标为 placeholder，路由落到占位页，真实页面仅测试引用——事实孤儿页面；且 `OperationsAnalysisPage.tsx:369` 的 `actionTo: "/source-preview"` 会把用户带进占位页。需决策接入或下线。
- **低**：`api/client.ts:149-248` 内嵌约 100 行 mock 编排，组合边界偏厚，建议下沉为邻居文件；mock 载荷有 api/、mocks/、fixtures/ 三个出口；`useMockFallback` 派生逻辑在 dashboard-home 域内三处逐字重复；`routes.tsx:503-517` 的 `stock-analysis/risk` 与 `/portfolio` 复用同一组件，8 条历史重定向 alias（含中文路径）无退役计划；`features/prototype/` 是空死目录。
- **低**：域间 import 无边界声明（OperationsAnalysisPage 直接 import balance-analysis 与 product-category-pnl 的内部符号；macro-toolkit 被 14 个外部文件 import）。

## 五、UI 与设计系统

正面：token 单一来源（designSystem.ts + tokens.css 双镜像由 theme.test.ts 值级互锁）；主题 boundary 三分列机制严密；零 styled-components/emotion 分叉；无全局样式污染；`LabeledValue` 无私有重声明；纯图标按钮无可访问名为 0；`prefers-reduced-motion` 处理良好；无装饰性无限动效。

问题（按修复价值排序）：

| # | 事项 | 规模 |
| --- | --- | --- |
| 1 | `agent/AgentWorkbenchPage.css:10,18` 定义浅色 hex 红绿变量并 8 处消费——登记的深色 scope 直灌浅色高饱和红绿，真实视觉违规 | 2 变量 8 处 |
| 2 | `components/page/PagePrimitives.module.css:79-92` headerBadgePositive/Accent 硬编码浅色 hex，被两个深色页消费，构成页内主题翻转 | 3 个类，共享层 |
| 3 | 全部图表无文本替代：`components/charts/BaseChart.tsx` 无 aria-*/role，全 features 0 处 ECharts aria 配置——系统性可访问性缺口 | 1 个基础组件 |
| 4 | 深色 scope 上直接消费 `var(--ib-up/down/warn)` 共 312 处/32 文件 + bond-analytics 用 `TONE_CSS_VAR` 而非 `TONE_DH_CSS_VAR`——当前靠 boundary 映射兜住渲染正确，但违反明文规则，未登记 scope 上会失效 | 大，可 codemod |
| 5 | 约 40 个文件各自重复声明 formatYi/formatPct 等格式化助手（dashboard-home 两文件逐字重复；ledger-pnl/macro-toolkit/average-balance/product-category-pnl 未采用 pageModel） | ~40 文件 |
| 6 | 刻度外字号 232 条（其中 10 条低于 12px 数据行下限）、刻度外圆角 91 条违反 Shape Lock；共享层 `workbenchDeferredChrome.css` 占 9 处 | 中 |
| 7 | 渲染层字面量 `—`/`-`/`--` 缺失值违规约 20 处（清单见下）；另有 3 处把 `—` 当日期区间分隔符 | 小 |
| 8 | 内联 `style={{}}` 200 处/56 文件，bond-analytics 一家 79 处，重复模式 5 组可收进 module CSS | 中 |

缺失值字面量违规清单：`app/jobs/polling.ts:100`、`StockAnalysisPageImpl.tsx:1797,1818`、`SourcePreviewPage.tsx:91,553`、`useLedgerImportWorkflow.ts:40`（"--"）、`CorrelationAndRegimePanels.tsx:71`、`macroToolkitStrategyDisplaySupport.ts:248-249`、`stockAnalysisDeepResearchPanelsModel.ts:883`、`StockAnalysisStrategyReviewCards.tsx:395`、`StockAnalysisStrategyLensSection.tsx:137,159`、`PnlByBusinessPage.tsx:597,959`、`RiskOverviewPage.tsx:431`、`DashboardHomeOptionTwoLayout.tsx:82`；mock 层 `src/mocks/workbench.ts` 硬编码 `display:"—"` 绕过 formatter。

## 六、测试与代码健康度

正面：5897 用例中 5892 通过；零 snapshot、零 @ts-ignore、零 test.todo；契约测试质量高（mock-contract 逐字段校验、多个 ContractSync 测试直接 diff 后端 schema、adapter 测试锚定"前端不重算"红线）；生产代码显式 any 仅 4 处。

风险（按排序）：

1. **契约防线自知有洞**：`src/test/BalanceContractSync.test.ts` 有 3 个 `it.skip` 冻结的已知前后端漂移（identity_source 多声明 "system"；BalanceMovementPayload 缺 `unmapped_gl_accounts`；BalanceMovementDatesPayload 缺 `upstream_control_report_dates`）。后端若真实触发任一漂移会穿透所有 mock 绿测试。
2. **假绿面**：页面级测试几乎全部跑在与 demo 模式共享的同一批 mock 上；29 个 api 客户端（cashflowClient、positionsClient、productCategoryClient、executiveClient 等）无任何直接测试。
3. **密度失衡**：`average-balance` 22 个源文件仅 34 用例，全仓最差；`kpi-performance`（7 src/18 用例）、`bond-trading-desk`（5 src/19 用例）次之。
4. `agent/hooks/useAgentRunRestore.ts:121` 是全仓唯一一处 `exhaustive-deps` 抑制，恢复逻辑对依赖敏感，值得人工复核。
5. `src/test/` 已膨胀为 269 文件平铺目录，与 features 内联测试双轨并存，92 个文件无法从 import 推断归属。
6. 浅断言比例偏高：`toBeDefined/toBeTruthy` 共 186 处（DashboardHomePage.test.tsx 26、ProductCategoryPnlPage.test.tsx 21）；个别 CSS 契约测试逐字断言内联样式串，脆弱。
7. 依赖：antd 与 ag-grid 双表格栈并存（ag-grid 仅 5-6 文件，合并候选）；React 停留 18；`@assistant-ui/react@0.15.14` 等 4 个依赖精确锁死（0.x 锁死升级通道，需人工盯）。未联网核实 CVE。

## 七、建议处理顺序

1. 先解决两个高严重度显示正确性问题（balance 对账阈值、risk-tensor 单位猜测）——都需业务确认口径，不要自行猜定义。
2. 解冻或升级 BalanceContractSync 的 3 个 skip 漂移（契约防线收口）。
3. 修复两个真实深色页视觉违规（AgentWorkbenchPage hex、PagePrimitives headerBadge），改动极小。
4. 处置 stock-analysis CSS 超预算的两个失败守卫（收紧或上调基线，需决策）。
5. 把 product-category-pnl 的年化收益率达标计算下沉后端；对齐变动率/归因闭合和/盈亏占比三处前端口径。
6. 决策 source-preview 孤儿域去留；decision 后清理 prototype 空目录。
7. BaseChart 加 aria 文本替代（一处修复全站受益）。
8. 中期：格式化函数收编、`--ib-*` 深色消费 codemod、average-balance 补测试密度、29 个未测 api 客户端补传输契约测试。

## 验证局限

- 本审计为静态分析 + 机械检查，未做浏览器实测；"`--ib-*` 在深色页渲染正确"的结论来自 tokens.css 级联推导。
- 可访问性的键盘可达性、焦点管理、颜色对比度未覆盖。
- 标注"定义不明，需业务确认"的条目均未猜口径；§三、§四中"待对齐"条目需对照后端响应契约才能最终定性。
- 依赖风险未联网核实 CVE 库；测试用例数为正则粗统。
