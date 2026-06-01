# V1 → V3 Delta：流动性缺口（LiquidityGap）

| V1 模块 | V3 已实现位置 | V3 client 方法 | 实施决定 | 目标 V3 文件 |
| --- | --- | --- | --- | --- |
| `/api/analysis/liquidity_gap` 分桶资产/负债/缺口/累计缺口柱状图 | **无** client 方法；`client.ts` 未暴露 `liquidity_gap` / `getLiquidity*` | **无** | ⏭️ 跳过（端点缺） | 原计划 `CashflowProjectionPage` 或 `features/liquidity-gap/` |
| 叙事：按期限桶看资产负债错配与累计缺口 | `CashflowProjectionPage`：`getCashflowProjection` + 适配器按月桶展示资产流入、负债流出、累计净现金流 | `getCashflowProjection`、`getBalanceAnalysisDates` | ⏭️ 跳过（已有等价） | `frontend/src/features/cashflow-projection/pages/CashflowProjectionPage.tsx` |

## 说明

- V1 专页的「缺口比例」「gap_ratio」等字段在 V3 现金流投影契约中未以同形暴露；当前 V3 页面已覆盖「期限维度现金流与累计净值」这一核心阅读路径，故不重复建页。
- 若未来后端提供与 V1 对齐的 `liquidity_gap` envelope，再在 `client` 契约主线登记后接表。

## 待续

- 待 `/api/analysis/liquidity_gap`（或等价 read model）进入 `contracts` + `client` 后补专表或 Tab。
