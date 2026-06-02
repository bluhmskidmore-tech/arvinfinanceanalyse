# V1 → V3 负债结构（LiabilityAnalytics）Delta 计划

**依据**：V1 `D:\MOSS-SYSTEM-V1\frontend\src\pages\LiabilityAnalytics.tsx`（单文件内嵌全部模块）；V3 `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` 与子组件；`frontend/src/api/client.ts` 方法 grep。

| V1 模块 | V3 是否已实现 | V3 client 方法 | 实施决定 | 备注 |
|---|---|---|---|---|
| 日常 Tab：报告日选择 + 风险桶主数据 | 是 | `getBalanceAnalysisDates`、`getLiabilityRiskBuckets` | 保持 | 与 V1 `/api/risk/buckets` 等价读面 |
| 日常：NIM 压力测试（+50bps） | 是 | `getLiabilityYieldMetrics` | 保持 | `LiabilityNimStressPanel` |
| 日常：资金来源 Top10 柱 + 机构类型饼 | 是 | `getLiabilityCounterparty` | 本次增强 | 月度可增加与 V1 一致的 `counterparty_top10` 专用柱序列 |
| 日常：负债结构饼 + 期限柱 | 是 | `getLiabilityRiskBuckets` | 本次增强 | 月度结构卡可增加 V1 式副标题 |
| 日常：同业结构/期限 + 发行结构/期限 | 是 | 同上 | 保持 | `LiabilityStructureGrids` |
| 日常：客户维度明细表 | 是 | 同上 | 保持 | `LiabilityCustomerTable` |
| 月度：年份/月份选择 + 有效天数 | 是 | `getLiabilitiesMonthly` | 保持 |  |
| 月度：ADB 口径 NIM 压力卡 | 部分 | `getLiabilityAdbMonthly` | 本次增强 | 补 V1 级「预警/Δ」表达与视觉 |
| 月度：资金来源 Top10 + 机构类型 | 是 | 同上 | 本次增强 | Top10 序列与 V1 对齐（优先 `counterparty_top10`） |
| 月度：结构/期限/同业/发行四宫格 | 是 | 同上 | 保持 |  |
| 月度：客户明细表 | 是 | 同上 | 保持 |  |
| 月度：月内 KPI（总负债、付息率、环比等） | 否 | `getLiabilitiesMonthly`（字段已在契约） | **实施** | 契约含 `mom_change` / `avg_liability_cost` 等 |
| 月度：YTD 日均总负债与负债成本 | 否 | 同上 payload `ytd_*` | **实施** | 无新端点 |
| V1 骨架屏/全页错误壳 | 否 | — | 跳过 | 非功能 parity；V3 用 antd Spin/Alert 分段降级 |
| 其它 V1 未单列之装饰（Lucide 等） | — | — | 跳过 |  |

**统计**：V1 归纳模块约 **12** 项；V3 已实现约 **10** 项；未实现/部分约 **2** 项（月度 KPI+YTD、月度 NIM 卡细节）；本次在「不增 client、不改契约」下补齐 **5** 个可交付增量并评估导航 readiness。
