# Prompt 6：比较分析 ComparativeAnalysis

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「比较分析」页面，完全对齐 V1 的计算口径和功能。

## V3 架构模式
同 Prompt 1。

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 比较分析 */
export type ComparativePeriodType = "daily" | "monthly" | "quarterly";

export type ComparativeMetricItem = {
  label: string;              // 如 "总资产", "总负债", "净资产", "NIM"
  current: number;            // 当期值（元或小数）
  previous: number;           // 上期值
  change: number;             // 变化额 = current - previous
  change_pct: number | null;  // 变化百分比（百分数，如 5.2 = 5.2%）
};

export type ComparativeComparisonResponse = {
  report_date: string;
  period_type: ComparativePeriodType;
  current_label: string;      // 如 "2026-04-11"
  previous_label: string;     // 如 "2026-04-10" 或 "2026-03" 或 "2025Q4"
  metrics: ComparativeMetricItem[];
};

export type ComparativeScaleTrendItem = {
  date: string;               // YYYY-MM-DD 或 YYYY-MM
  total_assets: number;       // 元
  total_liabilities: number;  // 元
  assets_change: number;      // 元（环比变化额）
  liabilities_change: number; // 元
};

export type ComparativeScaleTrendResponse = {
  report_date: string;
  period_type: ComparativePeriodType;
  items: ComparativeScaleTrendItem[];
};

export type ComparativeYieldItem = {
  security_type: string;      // 券种名称
  avg_balance: number;        // 元（日均余额）
  balance_proportion: number; // 百分数（占比）
  annualized_yield: number;   // 百分数（年化收益率）
  pnl_contribution: number;   // 百分数（损益贡献占比）
  total_pnl: number;          // 元（损益金额）
};

export type ComparativeYieldResponse = {
  report_date: string;
  start_date: string;
  end_date: string;
  total_avg_balance: number;
  total_pnl: number;
  overall_annualized_yield: number; // 百分数
  items: ComparativeYieldItem[];
};

export type ComparativePnlComponent = {
  name: string;               // 如 "利息收入", "公允价值变动", "资本利得"
  amount: number;             // 元
  proportion: number;         // 百分数
};

export type ComparativePnlCompositionResponse = {
  report_date: string;
  total_pnl: number;
  components: ComparativePnlComponent[];
};

export type ComparativeStructureChangeItem = {
  category: string;           // 分类名称
  change: number;             // 元（变化额）
  change_pct: number | null;  // 百分数
};

export type ComparativeStructureChangeResponse = {
  report_date: string;
  period_type: ComparativePeriodType;
  asset_summary: {
    total_change: number;
    total_change_pct: number | null;
  };
  liability_summary: {
    total_change: number;
    total_change_pct: number | null;
  };
  asset_changes: ComparativeStructureChangeItem[];
  liability_changes: ComparativeStructureChangeItem[];
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 参数 | 返回类型 | client.ts 方法名 |
|------|--------|------|----------|-----------------|
| 环比/同比对比 | `GET /api/analysis/comparative/comparison` | `?report_date=&period_type=daily` | `ComparativeComparisonResponse` | `getComparativeComparison(reportDate, periodType)` |
| 规模走势 | `GET /api/analysis/comparative/scale_trend` | `?report_date=&period_type=daily&limit=30` | `ComparativeScaleTrendResponse` | `getComparativeScaleTrend(reportDate, periodType, limit)` |
| 收益归因 | `GET /api/analysis/comparative/yield` | `?report_date=&start_date=&end_date=` | `ComparativeYieldResponse` | `getComparativeYield(reportDate, startDate, endDate)` |
| 损益构成 | `GET /api/analysis/comparative/pnl_composition` | `?report_date=` | `ComparativePnlCompositionResponse` | `getComparativePnlComposition(reportDate)` |
| 结构变化 | `GET /api/analysis/comparative/structure_change` | `?report_date=&period_type=daily` | `ComparativeStructureChangeResponse` | `getComparativeStructureChange(reportDate, periodType)` |

---

## 三、核心计算逻辑

### 环比/同比卡片
```typescript
// 每个指标卡片显示：
// - 当期值
// - 上期值
// - 变化额（正绿负红，中国标准反转：金额增长=红色向上箭头，减少=绿色向下箭头）
// - 变化百分比
// 注意颜色约定：对于资产/负债规模，增长用红色↑，减少用绿色↓（中国标准）
// 对于 NIM/收益率，上升用绿色↑，下降用红色↓

const formatChange = (change: number, isPct: boolean) => {
  const sign = change >= 0 ? '+' : '';
  if (isPct) return `${sign}${change.toFixed(2)}%`;
  return `${sign}${(change / 1e8).toFixed(2)} 亿`;
};
```

### 损益构成饼图数据
```typescript
const PNL_COLORS = {
  '利息收入': '#22c55e',
  '公允价值变动': '#3b82f6',
  '资本利得': '#f59e0b',
  '其他': '#94a3b8',
};

const pnlPieData = components.map(c => ({
  name: c.name,
  value: Math.abs(c.amount),
  color: PNL_COLORS[c.name] || '#94a3b8',
}));
```

### 金额格式化
```typescript
const formatYi = (v: number) => `${(v / 1e8).toFixed(2)} 亿元`;
const formatYiShort = (v: number) => `${(v / 1e8).toFixed(2)}`;
const formatRate = (v: number | null) => v != null ? `${v.toFixed(2)}%` : '—';
const formatPct = (v: number | null) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—';
```

---

## 四、页面布局

单页面。顶部有期间类型切换器。数据加载：并行请求 5 个 API。

布局从上到下：

1. **页面标题 + 期间类型切换器**
   - 标题：`综合比较分析`
   - 切换器：日度 / 月度 / 季度（默认日度）
   - 切换后所有模块重新加载

2. **模块 1：环比/同比对比卡片**（4 列网格）
   - 数据源：`getComparativeComparison`
   - 每个卡片：
     - 指标名称（如"总资产"）
     - 当期值（大字体）
     - 上期值（小字体灰色）
     - 变化额 + 变化百分比 + 箭头图标
   - 标题行显示：`{current_label} vs {previous_label}`

3. **模块 2：规模走势图**（全宽 Card）
   - 数据源：`getComparativeScaleTrend`
   - echarts 双轴混合图：
     - 左 Y 轴：规模（亿元）— 面积图
     - 右 Y 轴：增减额（亿元）— 柱状图
   - series：
     - 总资产规模（面积图，蓝色 #3b82f6）
     - 总负债规模（面积图，红色 #ef4444）
     - 资产增减额（柱状图，蓝色半透明）
     - 负债增减额（柱状图，红色半透明）

4. **模块 3 + 4：收益归因 + 结构变化**（2 列网格）

   **左：收益归因**
   - 数据源：`getComparativeYield` + `getComparativePnlComposition`
   - 3 列 KPI：日均余额 | 总损益 | 年化收益率
   - 损益构成饼图（环形）
     - 颜色：利息收入=#22c55e, 公允价值变动=#3b82f6, 资本利得=#f59e0b
   - 券种收益率表格（Top 10）
     - 列：券种 | 日均(亿) | 占比 | 年化收益 | 贡献

   **右：结构变化**
   - 数据源：`getComparativeStructureChange`
   - 2 列 KPI：资产变化（蓝色背景）| 负债变化（红色背景）
   - 资产端变化横向柱状图
     - 正值蓝色，负值红色
   - 负债端变化横向柱状图
     - 正值红色，负值蓝色（负债增加是风险）

---

## 五、图表配置（echarts）

### 规模走势双轴图
```typescript
const option: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['总资产', '总负债', '资产增减', '负债增减'] },
  xAxis: { type: 'category', data: items.map(d => d.date) },
  yAxis: [
    { type: 'value', name: '规模(亿)', axisLabel: { formatter: v => (v/1e8).toFixed(0) } },
    { type: 'value', name: '增减(亿)', axisLabel: { formatter: v => (v/1e8).toFixed(0) } },
  ],
  series: [
    { name: '总资产', type: 'line', areaStyle: { opacity: 0.15 }, data: items.map(d => d.total_assets), itemStyle: { color: '#3b82f6' } },
    { name: '总负债', type: 'line', areaStyle: { opacity: 0.15 }, data: items.map(d => d.total_liabilities), itemStyle: { color: '#ef4444' } },
    { name: '资产增减', type: 'bar', yAxisIndex: 1, data: items.map(d => d.assets_change), itemStyle: { color: 'rgba(59,130,246,0.4)' } },
    { name: '负债增减', type: 'bar', yAxisIndex: 1, data: items.map(d => d.liabilities_change), itemStyle: { color: 'rgba(239,68,68,0.4)' } },
  ]
};
```

### 损益构成饼图
```typescript
const option: EChartsOption = {
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: pnlPieData.map(d => ({ name: d.name, value: d.value, itemStyle: { color: d.color } })),
    label: { formatter: '{b} {d}%' },
  }]
};
```

### 结构变化横向柱状图
```typescript
// 资产端：正值蓝色 #3b82f6，负值红色 #ef4444
// 负债端：正值红色 #ef4444，负值蓝色 #3b82f6
const option: EChartsOption = {
  yAxis: { type: 'category', data: categories },
  xAxis: { type: 'value', axisLabel: { formatter: v => (v/1e8).toFixed(1) + '亿' } },
  series: [{
    type: 'bar',
    data: changes.map(d => ({
      value: d.change,
      itemStyle: { color: d.change >= 0 ? positiveColor : negativeColor }
    })),
  }]
};
```

---

## 六、业务口径说明

1. 日度对比：当日 vs 前一日
2. 月度对比：当月 vs 上月（月度日均口径）
3. 季度对比：当季 vs 上季
4. 收益归因：按券种的年化收益率贡献 = (该券种日均 × 该券种年化收益率) / 总日均
5. 损益构成：利息收入 + 公允价值变动 + 资本利得 + 其他
6. 结构变化：各分类的规模变化额和变化百分比

---

## 七、路由和导航注册

routes.tsx:
```typescript
const ComparativeAnalysisPage = lazy(() => import("../features/comparative-analysis/pages/ComparativeAnalysisPage"));
if (section.path === "/comparative-analysis") {
  return { path: section.path.slice(1), element: routeElement(<ComparativeAnalysisPage />) };
}
```

navigation.ts:
```typescript
{
  key: "comparative-analysis",
  label: "比较分析",
  path: "/comparative-analysis",
  icon: "analysis",
  description: "环比/同比对比、规模走势、收益归因、结构变化",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接比较分析读链路。",
},
```
