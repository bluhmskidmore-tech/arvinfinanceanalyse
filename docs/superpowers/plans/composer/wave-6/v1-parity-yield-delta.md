# V1 → V3 Delta：收益管理（YieldAnalysis）

| V1 模块 | V3 已实现位置 | V3 client 方法 | 实施决定 | 目标 V3 文件 |
| --- | --- | --- | --- | --- |
| `/api/analysis/yield_metrics` KPI（资产收益率、负债成本、市场负债成本、NIM） | `LiabilityAnalyticsPage` 内嵌于日常分析，经 `LiabilityNimStressPanel` 消费 | `getLiabilityYieldMetrics` | ✅ 实施（在 PnL 页增加独立「收益/NIM」视图，与 V1 收益管理入口对齐） | `frontend/src/features/pnl/PnlPage.tsx` |
| 历史曲线、散点、PnL 日度组合等（V1 大块图表） | 部分能力分散在负债/债券；**无**与 V1 完全一致的单一端点聚合 | **无**额外 `getYield*` / 历史序列 client | ⏭️ 跳过（端点缺或契约未暴露） | — |
| V1 `YieldByPeriodTable` 等子组件 | V3 未在本次范围复刻 | — | ⏭️ 跳过（端点缺） | — |

## 待续

- 若后端补齐与 V1 对齐的 `history` / `scatter` / 日度 PnL 组合等契约并在 `client.ts` 暴露，可再拆 feature 或扩展当前 Tab。
