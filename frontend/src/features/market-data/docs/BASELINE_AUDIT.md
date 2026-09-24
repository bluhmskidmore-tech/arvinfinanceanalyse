# 市场数据页基线盘点（阶段 0）

**页面路径：** `/market-data`  
**主组件：** [`MarketDataPage.tsx`](../pages/MarketDataPage.tsx)
**数据入口：** [`marketDataClient.ts`](../../../api/marketDataClient.ts) → `/ui/market-data/*`
**布局版本：** `data-layout-rev=2026-06-15b`（2026-06-15 下半区闭环）

## 区块清单（自上而下）

1. **终端驾驶舱**（`market-data-terminal-cockpit`）：Hero 筛选、Tape、决策轨、证据轨。
2. **核心观察区**：左侧 `RateQuoteTable`；右侧 **宏观深度 Tabs**（曲线 / **信用利差** / 压力与情景）。
   - **信用利差 Tab**：双栏 `LinkageSpreadTenorTable`（3Y/5Y/10Y 卡片 + `market-data-macro-spread-slot-*`）+ 相关图。
3. **运维 KPI**：`MarketPipelineKpiStrip`（折叠展开后挂载）。
4. **下半区（lower deck）** — `market-data-lower-deck-section`：
   - **资金读数**：`MarketDataLiquidityDeck`（DR007 / 回购 / Shibor + NCD 矩阵）。
   - **Tushare 宏观补充**：`MarketDataTushareSupplementSection`（cn_m + eco_cal；新鲜度条 + runbook 提示）。
   - **资讯与日历**：`NewsAndCalendar`（Choice 头条 + 供给/招标日历，`market-data-lower-deck-panel`）。
5. **条件块**（`MARKET_DATA_SHOW_*`）：宏观序列观察、外汇分析（默认关）。
6. **Livermore**：默认折叠 + 延迟 `getLivermoreStrategy`。
7. **正式外汇**：`MarketDataFxFormalSection` 默认折叠。
8. **扩展终端**：国债期货 / 现券 / 信用成交（`source-pending`）；summary 显示「待契约 N」+ 契约注记。
9. **宏观-债市联动**：`Collapse` 默认收起；展开后为 KPI + 组合影响 + 相关性前十 + **`LinkageSpreadsAuditBridge`**（利差槽位审计，跳转信用利差 Tab；**不再重复**利差双栏+图）。

## 痛点（UX / 性能 / 代码）

| 类型 | 说明 |
|------|------|
| UX | ~~DataStatusStrip 与 KPI 横带重复~~ → **已处理（2026-06-10f）**。 |
| UX | ~~信用利差在折叠区与 Tab 重复~~ → **已处理（2026-06-15）**：折叠区改审计桥，完整读面仅在 Tab。 |
| UX | ~~下半区样式割裂~~ → **已处理（2026-06-15b）**：资金 / Tushare / 资讯统一 lower-deck 壳层与 supplementary 头图。 |
| 性能 | ~~宏观深度 Tabs 三栏均挂载~~ → **已处理**：按 `macroDepthTab` 条件渲染。 |
| 性能 | ~~联动 API 首屏即拉取~~ → **已处理**：懒加载 + `MarketDataLinkageSection` 抽离。 |
| 治理 | **Route B**：`GS-MKT-RATES-FRAGMENT-A`；`GAP-MKT-DATA` 全页缺口仍在。 |
| 治理 | **Tushare 运维（2026-06-15）**：`docs/tushare_supplement_refresh_runbook.md` + scheduler handoff 模板；operator `scripts/refresh_tushare_supplement.py`。 |
| 数据源 | **Route C**：`getFxFormalStatus` 已挂载；期货/成交仍 `source-pending`。 |
| 测试 | **Playwright（2026-06-15）**：`market-data-terminal-smoke` + `market-data-workflow-smoke`（利差 Tab、审计桥、币种筛选、下半区壳层）。 |

## debt:audit（2026-06-15 快照）

- `npm run debt:audit` 通过（无增长）。
- `MarketDataPage.tsx` 单文件 `style=` **1/1**（基线内）。

## 后端依赖（只读、本次不改）

- `macro_vendor`：`/ui/market-data/rates`、`catalog`、`fx/*`
- `market_data_livermore`、`market_data_ncd_proxy`、`market_data.tushare_supplement`（`std_tushare_money_supply_monthly`、`std_tushare_eco_cal_event`）
- 运维写入：`refresh_tushare_supplement` actor / `scripts/refresh_tushare_supplement.py`

---

*本文件随阶段实施追加「已处理」标注，不作为产品规格唯一来源；契约主文见 `docs/page_contracts.md` §PAGE-MKT-001。*
