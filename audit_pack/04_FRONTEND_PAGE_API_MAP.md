# 04 — 前端页面与接口调用映射（工作台）

数据来源：`frontend/src/router/routes.tsx`、`frontend/src/mocks/navigation.ts`、grep `frontend/src/api/*.ts`、`client.ts`。

## 顶层路由壳

| 路由文件 | 作用 |
|----------|------|
| `router/routes.tsx` | `/` → `WorkbenchShell`，子路由由 `buildWorkbenchChildRoutes()` 与别名 `Navigate` 组成 |
| `layouts/WorkbenchShell.tsx` | 侧栏导航、内容区、`DataModeRibbon` 等 |

别名示例：`macro-analysis`、`adb`、`pnl-by-business`、`bonds`、`liabilities` → 各 canonical 路径。

## 工作台页面一览（canonical path → 组件 → API 消费习惯）

以下为 **live** 且非占位（更细粒度字段/图表见源码与 Storybook/tests）。

| Path | Page 组件 | 主要数据来源（API） | Mock / 硬编码迹象 |
|------|-----------|---------------------|-------------------|
| `/`、`/dashboard` | `DashboardPage` | `client`：`/ui/home/overview`、`executive`、`pnl`、`bond-analytics`、`risk`（部分 guarded） | 壳层占位卡与就绪 pill |
| `/operations-analysis` | `OperationsAnalysisPage` | source preview、`macro-bond-linkage`、Fx formal、资产负债表 overview 跳转 | workload mocks 见 feature |
| `/decision-items` | `DecisionItemsPage` | `/ui/balance-analysis/decision-items` + status POST |
| `/balance-analysis` | `BalanceAnalysisPage` | `/ui/balance-analysis/*`、`/api/analysis/adb*`（日均对比）|
| `/balance-movement-analysis` | `BalanceMovementAnalysisPage` | **`balanceMovementClient`** → `/ui/balance-movement-analysis*` |
| `/liability-analytics` | `LiabilityAnalyticsPage` | **`/api/risk/buckets` 等**；若调用 `ApiClient` 新方法缺失会 **编译失败**（见 `08`）|
| `/pnl`、`/pnl-bridge` | `PnlPage`、`PnlBridgePage` | `/api/pnl/*` |
| `/pnl-attribution` | `PnlAttributionPage` | `/api/pnl-attribution/*`、`campisi/*` |
| `/product-category-pnl` | `ProductCategoryPnlPage` | `/ui/pnl/product-category*` |
| `/risk-tensor` | `RiskTensorPage` | `/api/risk/tensor*` |
| `/concentration-monitor` | `ConcentrationMonitorPage` | 信用利差 / 集中度（债券分析载荷）|
| `/cashflow-projection` | `CashflowProjectionPage` | `/api/cashflow-projection` |
| `/bond-analysis` | `BondAnalyticsView` | `/api/bond-analytics/*`（大量子面板）|
| `/bond-dashboard` | `BondDashboardPage` | `/api/bond-dashboard/*` |
| `/positions` | `PositionsPage` | `/api/positions/*` |
| `/average-balance` | `AverageBalancePage` | `/api/analysis/adb*` |
| `/ledger-pnl` | `LedgerPnlPage` | `/api/ledger-pnl/*` |
| `/bank-ledger-dashboard` | `LedgerDashboardPage` | `/api/ledger/*` |
| `/kpi` | `KpiPerformancePage` | **`kpiClient`** + `/api/kpi/*` |
| `/team-performance` | `TeamPerformancePage` | **统一客户端** |
| `/platform-config` | `PlatformConfigPage` | `/health`、`source` 状态等 |
| `/cross-asset`、`/cross-asset-drivers` | `CrossAssetPage` | **`marketDataClient`**、`macro`、`news` |
| `/market-data` | `MarketDataPage` | `marketDataClient`（Livermore、NCD、preview、日历等）|

**子路由**：`/product-category-pnl/audit` → `ProductCategoryAdjustmentAuditPage`。

## Placeholder（导航或路由仍占位）

| Path | 行为 |
|------|------|
| `/cube-query`、`/risk-overview`、`/reports`、`/news-events`（等） | `WorkbenchPlaceholderPage` |
| Hidden：`/agent`、`/source-preview` | 占位 + `navigationVisibility: hidden` |

## 组件与图表（横向）

| 类别 | 典型路径 |
|------|----------|
| 图表（ECharts） | `features/*/utils/*echarts*`, `**/charts/*`、`echarts-for-react` |
| 表格 | ag-grid：`features/**/*Grid*`、`components/*` |
| 经营 / 高管 | `features/executive-dashboard/components/*`、`adapters/executiveDashboardAdapter.ts` |
| 共性布局 | `components/page/PagePrimitives.tsx`、`GridContainer.tsx`、`DataModeRibbon.tsx` |

## API 门面分层（审计注意）

| 模块 | 文件 | 备注 |
|------|------|------|
| 巨型聚合 | `api/client.ts` | 五千行级；与工作台多数页面耦合 |
| 域客户端 | `api/kpiClient.ts`、`api/marketDataClient.ts`、`api/balanceMovementClient.ts`、`api/cubeClient.ts` | AGENTS 推荐扩展方向 |

## 「硬编码」与 Mock

- **`client.ts`** 内含大量开发与 fallback mock 金额（审计关键词：`mockLedger`、`campisi` 样板对象等）。
- **`frontend/src/mocks/*.ts`、`**/Mocks*.ts`、`*.test.tsx`**：`128000000` 类数值为测试夹具。
- **错误提示硬编码**：如余额变动页 **`请确认后端 7888`**，与测试中 `localhost:8000` 并存 → 端口叙事分裂。

## 接口未接通 / 契约漂移（静态证据摘录）

| 迹象 | 位置 / 说明 |
|------|-------------|
| `ApiClient` 缺少方法 | TS build：`LiabilityAnalyticsPage` → `getCockpitWarnings`、`getContributionSplit`（见 `08`）|
| Props 不匹配 | TS build：`GridContainer`、`DashboardBondHeadlineSection` |

## UI 复杂度与重复风险

- 多页面大量使用 **本地化 CSS Module + PagePrimitives**；`DEBT`/style audit 脚本在 `package.json` 中：`npm run debt:audit`。
- `balance-analysis`、`product-category-pnl`、`workbench` 等页面超千行：**维护性与一致性的热点**。

## 后端路径与前端代理

浏览器端请求通常为 **相对路径** `/api`、`/ui` → Vite 代理到后端；**不显式写死端口**的生产构建依赖部署侧反向代理或使用 `VITE_API_BASE_URL`。
