# Phase 5: 经营分析页重构

> 前置依赖: Phase 0 + Phase 1 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 2 项
> Mockup: `.omx/mockups/business_analysis_hd.png`

## 目标

将现有 `OperationsAnalysisPage.tsx`（~681 行）增量重构为 mockup 所示的经营分析页面。

## 现状

**现有文件**: `src/features/workbench/pages/OperationsAnalysisPage.tsx`
**现有能力**: 月度 QDB GL 分析工作簿、场景、手工调整

**后端已有**:
- `/ui/qdb-gl-monthly-analysis*` — 月度 GL 分析
- `/ui/balance-analysis/*` — 余额分析（部分数据可复用）
- `/ui/home/*` — 高管看板聚合数据

## 实施要求

### 文件拆分结构
```
src/features/workbench/
├── pages/
│   └── OperationsAnalysisPage.tsx      # 增强为经营分析主页面
├── business-analysis/
│   ├── BusinessKpiRow.tsx              # 8 个经营 KPI
│   ├── BusinessConclusion.tsx          # 本期经营结论
│   ├── RevenueCostBridge.tsx           # 收益成本桥（瀑布图）
│   ├── QualityObservation.tsx          # 经营质量观察
│   ├── ContributionTable.tsx           # 资产/负债经营贡献
│   ├── AttentionItems.tsx             # 本期关注事项
│   ├── BusinessCalendar.tsx           # 近期经营日历
│   ├── MaturityConcentration.tsx      # 期限与集中度
│   └── ManagementOutput.tsx           # 管理输出
└── mocks/
    └── businessAnalysisMock.ts
```

### Mockup 对照

**顶部 KPI（8 张）**:
1. 市场资产 `3,525.0 亿`
2. 市场负债 `1,817.9 亿`
3. 静态资产收益率 `2.07%`
4. 静态负债成本 `1.77%`（当期加权）
5. 静态利差 `29.5 bp`
6. 净经营贡献 `40.65 亿`（静态年化口径）
7. 发行负债占比 `66.3%`（CD 占发行 81.8%）
8. 重大关注 `4 项`（缺口/滚续/集中度/集中度）

**本期经营结论** (`BusinessConclusion`):
- 管理语言摘要
- 关键词标签: 收益质量稳定, 负债结构偏短, 短端滚续压力, 预警
- 条列要点

**收益成本桥（静态年化口径）** (`RevenueCostBridge`):
- 瀑布图: 债券资产收益 → 同业资产收益 → (合计资产收益) → 发行负债成本 → 同业负债成本 → 净经营贡献
- 使用 `WaterfallChart` 组件
- 注释: 资产与负债利差主要来源于债券资产贡献

**经营质量观察** (`QualityObservation`):
- 指标列表，每项有状态标签 (`StatusPill`):
  - 资产/负债比 `1.94x` — 正常
  - 发行负债集中度 `81.8%` — 关注
  - 短期负债占比 `72.6%` — 预警
  - 1年内缺口/负债 `20.5%` — 关注
  - 异常资产占比 `0.21%` — 正常

**资产/负债经营贡献** (`ContributionTable`):
- Tab: 资产大类 | 负债大类
- 表格: 项目 | 余额(亿) | 占比 | 利率/收益 | 经营含义 | 经营含义
- 底行: 合计/加权

**本期关注事项** (`AttentionItems`):
- 红: 滚续负债
- 橙: 优化结构
- 黄: 提高收益质量
- 绿: 处置异常
- 每项有具体说明

**近期经营日历** (`BusinessCalendar`):
- 负债到期表（与资产负债分析共用数据但展示视角不同——强调经营影响）

**期限与集中度** (`MaturityConcentration`):
- 左: 缺口条图（7天→5年以上）
- 右: 集中度指标
  - 同业存单/发行负债 81.8%
  - 短期负债/总负债 72.6%
  - 异常资产/债券资产 0.21%
  - 浮盈/1年内缺口 18.4%

**管理输出** (`ManagementOutput`):
- 经营判断: 收益仍由债券票息主导，利差不厚但相对稳定
- 核心矛盾: 负债对发行类工具依赖度高，短端滚续压力偏大
- 当前优先级: 先管缺口和滚续，再谋进一步提升收益
- 下钻方向: 资产负债分析看缺口，债券分析看利差，市场数据看盘中变化

### 关键约束

- 面向**管理层/经营层**，不是交易员视角
- 不重复 Dashboard 的内容（Dashboard 是分流，这里是深度分析）
- 不伪造预算完成率、资本占用、风险预算使用率等无来源指标
- 后端如无专门经营分析 API，mock 数据基于 seed values + 余额分析数据计算

## 验证

```bash
npm run lint && npm run typecheck && npm run build
```

视觉对比 `business_analysis_hd.png`。
