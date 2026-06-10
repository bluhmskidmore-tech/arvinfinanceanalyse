# 市场数据页基线盘点（阶段 0）

**页面路径：** `/market-data`  
**主组件：** [`MarketDataPage.tsx`](../pages/MarketDataPage.tsx)（约 1875 行）  
**数据入口：** [`marketDataClient.ts`](../../../api/marketDataClient.ts) → `/ui/market-data/*`

## 区块清单（自上而下）

1. **PageDecisionHero**：标题「市场数据」、主业务问句、观察日、模式徽标、刷新宏观数据按钮。
2. **DataStatusStrip**：口径、目录条数、稳定回收比例（与 KPI 横带部分重叠）。
3. **筛选条**：日期、国债/国开、中票/城投、来源。
4. **刷新状态条**：轮询成功/失败提示。
5. **KpiBand 概览横带**：目录数、稳定回收、降级、稳定最新日、稳定缺口、外汇分组/序列数、联动报告日。
6. **LiveResultMetaStrip**：宏观读面元数据（有数据时）。
7. **核心观察区**：左侧 `RateQuoteTable`；右侧 **宏观深度 Tabs**（曲线 M8 / 信用利差 / 压力与情景）。
8. **Livermore**：`LivermoreStrategyPanel`（随观察日变化）。
9. **三列观察栅格**：`MoneyMarketTable`、`BondFuturesTable`、`NcdMatrix`。
10. **第二栅格**：`BondTradeDetail`、`CreditBondTradesTable`、`NewsAndCalendar`。
11. **条件块**（`MARKET_DATA_SHOW_*`）：宏观序列观察、外汇分析（当前默认关）。
12. **宏观-债市联动**：`Collapse` 默认收起；内为分析口径说明 + 异步区 + 表格与相关性。
13. **条件证据区**：目录与元数据面板（当前默认关）。

## 痛点（UX / 性能 / 代码）

| 类型 | 说明 |
|------|------|
| UX | ~~DataStatusStrip 与 KPI 横带重复目录/稳定回收~~ → **已处理（2026-06-10f）**：状态条仅保留利率口径；目录/稳定回收仅在折叠「读面运维指标」内展示。 |
| UX | 主业务问句偏长；可收敛为「先看清读面 ready 与口径边界」。 |
| 性能 | ~~宏观深度 Tabs 三栏均 `forceRender: true`~~ → **已处理（2026-06-10）**：按 `macroDepthTab` 条件渲染，仅挂载当前 Tab。 |
| 性能 | ~~联动 API 首屏即拉取~~ → **已处理（2026-06-10g）**：`getMacroBondLinkageAnalysis` 仅在信用利差/压力 Tab 或展开联动折叠块后启用；联动大块抽至 `MarketDataLinkageSection`。~~运维 KPI `forceRender`~~ → **已处理（2026-06-10f）**：展开后才挂载 `market-data-pipeline-kpi-strip`。 |
| 性能 | ~~窗口聚焦重复请求~~ → **已处理（2026-06-10）**：市场页 queries `refetchOnWindowFocus: false`；`staleTime` 由 `externalDataQueryOptions` 提供。 |
| UX | ~~Livermore 整段展开占首屏以下~~ → **已处理（2026-06-10）**：`market-data-livermore-collapse` 默认折叠 + 延迟 `getLivermoreStrategy`。 |
| 治理 | **Route B（2026-06-10）**：`GS-MKT-RATES-FRAGMENT-A` 冻结 formal rates 片段；来源筛选优先 catalog `vendor_name`；Playwright smoke。`GAP-MKT-DATA` 全页缺口仍在。 |
| 数据源 | **Route C（2026-06-10）**：挂载 `getFxFormalStatus`（`market-data-fx-formal-collapse`）；期货/成交仍 `source-pending` + 契约注记。 |
| 代码 | 单文件过大；大量 `style=`（审计约 130 处），与全仓 style 债务基线敏感。 |

## debt:audit（实施后快照）

- 全仓 `style=` 计数降至基线以下（约 **3219 / 3308**），`npm run debt:audit` 通过。
- `MarketDataPage.tsx` 单文件 `style=` 约 **39 / 130**（显著下降；新增子组件含少量 `style=` 如 ECharts 尺寸）。

## 后端依赖（只读、本次不改）

- `macro_vendor`：`/ui/market-data/rates`、`catalog`、`fx/*`
- `market_data_livermore`、`market_data_ncd_proxy` 等

---

*本文件随阶段 1–3 实施可追加「已处理」标注，不作为产品规格唯一来源。*
