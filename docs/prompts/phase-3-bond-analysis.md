# Phase 3: 债券分析页重构

> 前置依赖: Phase 0 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 3 项
> Mockup: `.omx/mockups/bond_analysis_hd.png`

## 目标

将现有 `BondAnalyticsView` + 子组件增量重构为 mockup 所示的债市内部分析驾驶舱。

## 现状

**现有文件**:
- `src/features/bond-analytics/components/BondAnalyticsView.tsx`（~16 行，薄包装）
- `src/features/bond-analytics/components/BondAnalyticsDetailSection.tsx`
- `src/features/bond-analytics/components/CreditSpreadView.tsx`
- `src/features/bond-analytics/components/PortfolioHeadlinesView.tsx`（新增未提交）
- `src/features/bond-analytics/components/TopHoldingsView.tsx`（新增未提交）
- `src/features/bond-analytics/lib/bondAnalyticsModuleRegistry.ts` — 模块注册表
- `src/features/bond-analytics/lib/bondAnalyticsOverviewModel.ts` — 概览模型

**后端已有**:
- `/api/bond-analytics/*` — 收益拆解、基准超额、KRD、信用迁移、持仓headline、重仓、行为归因、刷新
- `/api/bond-dashboard/*` — 驾驶舱 KPI/结构/分布
- `/api/credit-spread-analysis/detail` — 信用利差分析

**已知差距**:
- 前端 client 未传 `asset_class`/`accounting_class`（收益拆解）
- 未传 `scenario_set`（KRD）、`spread_scenarios`（信用迁移）
- 模块有 `placeholder-blocked` 就绪态机制

## 实施要求

### 文件结构增强
```
src/features/bond-analytics/
├── components/
│   ├── BondAnalyticsView.tsx           # 保持薄包装
│   ├── BondKpiRow.tsx                  # 8 个债市 KPI（新增）
│   ├── MarketJudgment.tsx             # 市场判断摘要（新增）
│   ├── PortfolioSummary.tsx           # 组合摘要+资产结构饼图（新增/增强）
│   ├── YieldDurationChart.tsx         # 收益率与久期分布图（新增）
│   ├── CreditRatingDistribution.tsx   # 信用等级分布（新增）
│   ├── SpreadAnalysis.tsx             # 利差分析（中位数 bp）（增强 CreditSpreadView）
│   ├── TopHoldingsTable.tsx           # 重仓明细（增强 TopHoldingsView）
│   ├── PerformanceComparison.tsx      # 组合表现对比（年初至今）（新增）
│   ├── BondMaturityChart.tsx          # 期限结构（新增）
│   ├── CandidateActions.tsx           # 决策事项/候选动作（新增）
│   ├── RiskTrendChart.tsx             # 风险趋势（近12周）（新增）
│   └── BondEventCalendar.tsx          # 关键事件与日历（新增）
├── lib/                                # 保持现有
└── types/
    └── bondViewModels.ts              # 页面级 view model
```

### Mockup 对照

**顶部 KPI（8 张）**:
1. 债券持仓规模 `3,287.1 亿`（较上期 2.35%）
2. 浮动盈亏 `+68.48 亿`（较上期 12.73%）
3. 加权到期收益率 `2.38%`（较上期 0.05bp）
4. 加权久期 `3.92 年`（较上期 0.15年）
5. 平均票息 `2.65%`（较上期 0.03bp）
6. 信用利差中位数 `42.6 bp`（最新 8bp）
7. 逾期余额 `12.45 亿`（较上期 64%）
8. 异常预警 `3 个`（较上期 1项）

**组合摘要** — 一段文字 + 关键词标签（久期偏高, 信用以高等级为主, 策略以票息为主）

**债券资产结构** — 饼图: 政策性金融债 35.2%, 地方政府债 22.3%, 同业存单 17.9%, 信用债-企业 14.1%, 金融债 3.5%, 其他

**收益率与久期分布** — 双轴散点/柱图

**信用等级分布** — 大色块: AAA 1,682.4 亿 51.2%, AA+ 742.2 亿 22.6%, etc.

**利差分析（中位数 bp）** — 表格: 券种 | 当前 | 较上月 | 年初至今

**重仓明细（前10）** — 表格: 债券简称 | 面额 | 收益率 | 久期 | 评级 | 浮盈 | 浮盈/亏

**组合表现对比（年初至今）** — 表格: 组合名称 | 规模 | 收益率% | 初额较bp | 久期年 | 最大回撤%

**期限结构（亿元）** — 柱状图

**决策事项** — 动作列表 + 判断 + 操作建议

**风险趋势（近12周）** — 折线图: 净敞口/负债比 + 对手方集中度

**关键事件与日历** — 日期 + 事件 + 影响级别

### 关键约束

- 这是**债市内部分析**，不要混入跨资产内容
- "候选动作"不要叫"决策事项"（与资产负债分析的"决策事项"区分）
- 暴露后端支持但前端未传的筛选参数（`asset_class`, `accounting_class`, `scenario_set`）
- 现有模块注册表机制保留，在此基础上扩展

## 验证

```bash
npm run lint && npm run typecheck && npm run build
```

视觉对比 `bond_analysis_hd.png`。
