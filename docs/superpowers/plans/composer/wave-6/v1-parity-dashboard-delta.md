# V1 → V3 驾驶舱 Delta 计划（2026-04-18）

依据 V1 `Dashboard.tsx` / `DashboardUI.tsx` / `PnLSummaryDashboard.tsx` 头部 80 行 + `Dashboard.tsx` 全文 API/区块检索；对照 V3 `DashboardPage.tsx` 与 `frontend/src/api/client.ts`（仅 grep，未通读）。

## 决策矩阵

| V1 模块 | V1 源行号 | V3 是否缺失 | V3 已有 client 方法 | 实施决定 | 原因 |
|---|---|---|---|---|---|
| 核心 KPI 六卡（总资/总负/净资/杠杆/久期缺口/LCR） | ~952–1048 | 是（粒度不同） | `getHomeSnapshot`（overview 卡片由 adapter 提供） | ⏭️ 跳过（已有等价） | V3 经营总览已由 `OverviewSection` + snapshot 覆盖，避免重复请求旧 `/api/dashboard/core_metrics` |
| CoreMetricsCards 扩展指标带 | ~1421+ | 是 | 无 `dashboard/core_metrics` 专用封装 | ⏭️ 跳过（端点缺） | V1 直连 `/api/dashboard/core_metrics`；client 未暴露同名读路径 |
| 余额变动分析（日/周/月 + 债券/同业资产/同业负债） | ~1050–1196 | 是 | 无 `daily-changes` / `dashboard/daily-changes-v2` | ⏭️ 跳过（端点缺） | V1 `/api/dashboard/daily-changes-v2`；client 无对应方法 |
| 市场监控（DR007/国债10Y/汇率/原油/PMI 等 chips） | ~1199–1289 | 是 | `getChoiceMacroLatest` | ✅ 实施 | 可用 Choice 宏观最新序列复刻「市场监控」薄切片 |
| 月末汇率趋势 / FX 历史 | ~1297–1419 | 是 | 无 `dashboard/exchange-rates/monthly`；`getFxAnalytical` 叙事不同 | ⏭️ 跳过（端点缺） | V1 `/api/dashboard/exchange-rates/*` 与 V3 FX 读面不一致，避免假对齐 |
| 资产负债趋势 + 结构 Donut | ~1433–1570 | 是 | 无 `dashboard/summary`、`dashboard/trend` | ⏭️ 跳过（端点缺） | V1 巨页核心；client 无 dashboard summary/trend |
| 流动性缺口期限桶图 | ~1573–1626 | 是 | 无 `dashboard` 流动性缺口专用读 | ⏭️ 跳过（端点缺） | V1 内嵌 summary 内字段；无独立 client 方法 |
| 对手方风险（资产端 Top5） | ~1629–1660 | 是 | `getPositionsCounterpartyBonds` | ✅ 实施 | 与 V1 叙事一致；需报告日区间（与持仓页同源参数） |
| 对手方风险（负债端 Top5） | ~1661–1695 | 是 | `getLiabilityCounterparty` | ✅ 实施 | 契约已为 `Numeric`，可直接 `formatNumeric` |
| 市场环境 / 中美利差曲线等 | ~1697–1854 | 部分 | `getChoiceMacroLatest`（+ V1 另用 `cn-us-treasury-yield`） | ⏭️ 跳过（端点缺） | 利差专链 `/api/dashboard/cn-us-treasury-yield` 未在 client 暴露；不与宏观条重复实施 |
| 损益摘要卡片（PnLSummaryDashboard） | `PnLSummaryDashboard.tsx` 全文 | 是（独立组件） | `getFormalPnlOverview` / snapshot 内 attribution | ⏭️ 跳过（已有等价） | V3 首页已有 `PnlAttributionSection`；非同一 API 形状 |
| 数据刷新（Wind / 持仓 import）/ DetailModal | ~405–421, ~1930+ | 是 | 无 `refresh_positions`、无 dashboard import 状态 | ⏭️ 跳过（端点缺） | V1 管理动作链；client 未暴露 |
| 资讯流 | V1 无独立 Choice 区块；矩阵 Gap 提及新闻 | — | `getChoiceNewsEvents` | ✅ 实施 | 补驾驶舱「市场资讯」薄切片，与 V1 市场监控心智相邻 |
| 债券组合头条 KPI | V1 摘要内嵌；矩阵 Gap | — | `getBondDashboardHeadlineKpis` | ✅ 实施 | 与债券驾驶舱 headline 同源，体量小、可报告日驱动 |

## 统计

- 候选模块：**12**
- ✅ 计划实施：**5**（本批次上限）
- ⏭️ 跳过：**7**（端点缺 5 + 已有等价 2）

## 待续（未在本批次实施）

- `DashboardMacroSpotSection` 若需中美利差专图：待后端/`client` 暴露 `cn-us-treasury-yield` 或等价只读封装后再做
- 资产负债趋势、余额变动、CoreMetrics、FX 月度专板：待 `dashboard/*` 正式读面进入 client 后再评估
