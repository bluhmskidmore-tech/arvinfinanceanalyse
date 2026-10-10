# 市场数据页新数据源接入（Route C）

**日期：** 2026-06-10
**页面：** `/market-data`（PAGE-MKT-001）
**状态：** 已实施

## 目标

在不动金融口径、不塞 demo 的前提下，把后端已具备的 **formal 外汇中间价状态** 接到市场页；期货/成交仍保持 `source-pending` 并明示契约缺口。

## 范围

### 做

1. `useMarketDataPageData` 挂载 `getFxFormalStatus()` → `GET /ui/market-data/fx/formal-status`。
2. `MarketDataFxFormalSection`：默认折叠，展开后展示 `result_meta` + 行级表格（货币对 / 中间价 / 沿用 / 状态）。
3. 运维 KPI 折叠区新增 `market-data-fx-formal-materialized`；证据轨新增 `FX formal` 行。
4. `source-pending` 摘要补充契约说明（期货 / 现券 / 信用成交）。
5. 布局版本 `data-layout-rev=2026-06-10e`。

### 不做

- 不接国债期货 / 现券 / 信用成交真实 API（无 outward contract）。
- 不把 `getFxAnalytical` 升格为 formal 展示。
- 不改数据库 schema；前端不补算中间价。

## 验收

- 默认无 `market-data-fx-formal-panel`；展开后可见 `market-data-fx-formal-table` 与 mock `USD/CNY`。
- 证据轨含 `FX formal: basis=formal`（mock 环境）。
- `source-pending` 契约注记可见。
- 回归：`MarketDataPage.test.tsx`、`marketDataPageModel.test.ts`、Playwright smoke。
