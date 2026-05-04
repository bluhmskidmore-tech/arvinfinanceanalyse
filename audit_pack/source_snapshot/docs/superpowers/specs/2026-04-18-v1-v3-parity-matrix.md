# MOSS-V1 → MOSS-V3 前端功能对齐矩阵（2026-04-18）

**方法**：V1 路由来自 `D:\MOSS-SYSTEM-V1\frontend\src\app\moduleRegistry.tsx` 的 `appRoutes`；每个页面对应源文件头部 ≤70 行归纳「核心能力」。V3 对照 `frontend/src/router/routes.tsx`、`frontend/src/mocks/navigation.ts` 及现有特性目录。**不**对照 V1 全文件实现细节。

**覆盖状态**：✅ 已完整对齐；⚠️ 已部分对齐；❌ V3 未实现（无等价路由或仅占位/明显缺模块）。

| V1 页面路径 | V1 页面名称 | V1 核心能力（≤5 点） | V3 对应路径 | V3 覆盖状态 | Gap 清单 | 优先级 |
|-------------|-------------|----------------------|-------------|-------------|----------|--------|
| `/` | 驾驶舱 | 多图表总览；核心 KPI 卡片；市场/新闻/杠杆等模块；`dashboard/` 模块化摘要 | `/` 或 `/dashboard` | ⚠️ | V3 为 executive-dashboard 组装页，与 V1 巨页驾驶舱模块集合不一致；部分指标依赖后端 snapshot 与 wave-2/4 计划 | P0 |
| `/positions` | 持仓透视 | 薄封装 `PositionsView`；正式持仓表与筛选 | `/positions` | ✅ | 与 V1 对齐正式链路；若缺字段以后端契约为准 | P2 |
| `/assets` | 资产深度分析（薄封装） | 与 `/bonds` 同页：债券组合概览、分组、久期桶、估值分布、风险载荷等 | `/bond-dashboard`（建议书签） | ⚠️ | V1 为单页 BondAnalytics；V3 拆为 bond-dashboard + bond-analysis；需书签/别名 `/assets`→目标页（批次 0） | P1 |
| `/bonds` | 债券资产分析 | 组合市值/币种变动、分组饼图、期限桶、重仓券、估值与风险桶 API 聚合 | `/bond-dashboard`（重定向） | ⚠️ | 重定向已存在；UI 信息架构与 V1 单页不同，需对照 KPI/图表逐项验收 | P0 |
| `/liabilities` | 负债结构分析 | 负债结构/期限桶、同业与发行分项；月度对手方与 NIM 等 KPI | `/liability-analytics`（重定向） | ⚠️ | V3 导航为 Compat/占位主导；完整 V1 模块需 wave-5 与后端 `liability_analytics` 消费面 | P0 |
| `/risk` | 风险监测 | 预警记录与规则 CRUD；严重度/状态流转；图表汇总 | 无专页；`/risk-tensor`、`/concentration-monitor` 部分指标 | ❌ | 无等价「告警规则引擎」UI 与写路径；仅有正式风险读面 | P0 |
| `/risk-alerts` | 风险监测（别名） | 同 `/risk` | 同上 | ❌ | 同上 | P0 |
| `/adb` | 日均管理 (ADB) | 日均资产负债汇总、趋势、对比、月度分解与收益率/NIM | `/average-balance`（重定向） | ✅ | 文案与正式资产负债「主真源」关系需在页面内说清；数值走 V3 Numeric 管线 | P2 |
| `/gap` | 流动性缺口 | `/api/analysis/liquidity_gap` 桶图表；累计缺口与比率 | `/cashflow-projection` 为近似入口 | ⚠️ | API 与叙事不同；缺专用 liquidity gap 页或需在现金流页嵌入同源缺口模块 | P0 |
| `/yield` | 收益管理 | 资产/负债收益率、NIM 历史、散点（久期-收益）、多图表与排名卡 | 无同构页；部分能力在 `PnL`/经营分析分散 | ❌ | 需独立「收益管理」表面或明确合并到 PnL 桥/经营分析 | P1 |
| `/pnl` | 损益分析（YieldAnalysis 的 pnl Tab） | 与收益管理同壳：日度 PnL 汇总、组合分解、过滤器与下钻表 | `/pnl` | ⚠️ | V3 为 formal PnL 事实读链路；与 V1 双 Tab 壳层交互不同 | P0 |
| `/product-category-pnl` | 产品类别损益 | 产品树、场景冲击、手工调整弹窗；多 API | `/product-category-pnl` | ✅ | 审计子路由 V3 已有 `/product-category-pnl/audit` | P2 |
| `/pnl-by-business` | 业务线损益明细 | `/api/pnl/by-business` + 年度汇总；业务类型饼/柱 | `/ledger-pnl`（重定向） | ⚠️ | 科目口径 ledger vs V1 业务线维度；需对照数据契约与图表 parity | P0 |
| `/financial` | 财务分析 | 资产负债 KPI、PnL 摘要、绩效归因条、KRD 桶、雷达等组合财务视图 | 无 | ❌ | 无对应路由与特性包 | P1 |
| `/comparative` | 比较分析 | 资产负债趋势、区间指标对比、图表对比叙事 | 无 | ❌ | 无对应路由；或可部分由多维查询/经营分析替代（未落地） | P2 |
| `/market` | 市场数据 | 货币市场/SHIBOR/LPR/国债/NCD 等序列；Choice 状态 | `/market-data` | ✅ | 批次 0 增加 `/market` 重定向即可对齐书签 | P2 |
| `/macro-analysis` | 宏观分析 | 多 Tab（M7–M16）：货币政策、曲线、信用利差、压力测试、情景等 `/api/macro/*` | `/market-data`（重定向） | ⚠️ | V3 市场数据页未必挂载全部宏观 Tab；跨资产与经营分析分散承载 | P0 |
| `/balance-analysis` | 余额变动/资产负债分析 | 薄封装 `BalanceAnalysisView` | `/balance-analysis` | ✅ | 与 V1 同 feature 命名；持续对齐 formal fact | P1 |
| `/pnl-attribution` | 损益归因 | 薄封装 `PnLAttributionView`：规模/利率、TPL 相关性、构成、Campisi 等 | `/pnl-attribution` | ✅ | 以后端 `/api/pnl-attribution` 为准继续补图表 parity | P1 |
| `/reconciliation` | 全局对账 | 薄封装 `ReconciliationView` | 无 | ❌ | V3 无 `features/reconciliation` 与路由 | P0 |
| `/agent` | Agent | DeepSeek 报告生成、历史、模板类型 | `/agent` | ⚠️ | V3 为 gated disabled stub；无 V1 级 LLM 报告流 | P1 |
| `/kpi` | 绩效考核 | Owner 列表、指标表、导入/抓取/重算、导出 CSV | `/kpi` | ✅ | 交互细节需 UAT 对照 | P2 |
| `/bond-analytics-advanced` | 债券高级分析 | 薄封装 `BondAnalyticsView` + 页头 | `/bond-analysis`（重定向） | ✅ | 与 V3 governed cockpit 对齐；模块 readiness 见债券页内 | P2 |
| `/management-report` | 管理报告 | 薄封装 `ManagementReportView` | 无 | ❌ | V3 无该特性与路由；报表中心导航为占位 | P1 |

**统计（去重说明）**：上表按 `appRoutes` **逐条路由**列出（`/risk` 与 `/risk-alerts` 两行能力重复）。若合并「风险监测」双路径则为 **22** 个业务表面；全表 **24** 行路由级条目。

**覆盖分布（路由级 24 行）**：✅ **8**；⚠️ **9**；❌ **7**。

**备注**：用户已添加 V1 常用路径 `Navigate`（`/macro-analysis`、`/adb`、`/pnl-by-business`、`/liabilities`、`/bonds`、`/bond-analytics-advanced` 等），本矩阵不重复要求重做，仅在 Gap 中记录与 V1 功能深度的差异。
