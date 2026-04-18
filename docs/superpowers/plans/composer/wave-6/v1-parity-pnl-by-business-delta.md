# V1 → V3 Delta：PnL by business（业务线损益）

| V1 模块 | V3 已实现位置 | V3 client 方法 | 实施决定 | 目标 V3 文件 |
| --- | --- | --- | --- | --- |
| `/api/pnl/by-business` 业务线汇总表、饼图、柱状图、YieldByPeriodTable | 无对等页面；Ledger PnL 为科目/币种口径，非业务线拆分 | **无**（`client.ts` 未暴露 `by-business` / `yearly-summary`） | ⏭️ 跳过（端点缺） | `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`（原计划） |
| `/api/pnl/yearly-summary` 年度各月累计 | 同上 | **无** | ⏭️ 跳过（端点缺） | 同上 |

## 待续

- 待后端在 `client.ts` 契约层增加只读方法（如 `getPnlByBusiness` / `getPnlYearlySummary`）且 **不违反**「禁止手写新增」流程由主线团队接入后，再在 `LedgerPnlPage` 增加「业务线视图」Tab。
