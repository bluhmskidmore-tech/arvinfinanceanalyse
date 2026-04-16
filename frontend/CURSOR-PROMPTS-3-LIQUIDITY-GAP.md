# Prompt 3：流动性缺口 LiquidityGap

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「流动性缺口分析」页面，完全对齐 V1 的计算口径和功能。

注意：V3 已有 `CashflowProjectionPage`（现金流预测/久期缺口），那是不同的业务概念。流动性缺口是按期限桶展示资产/负债双向柱状图 + 累计缺口折线。

## V3 架构模式
同 Prompt 1。

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 流动性缺口分析 */
export type LiquidityGapBucket = {
  bucket_name: string;    // 期限桶名称，如 "隔夜", "7D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "5Y+"
  assets: number;         // 元（该桶资产总额）
  liabilities: number;    // 元（该桶负债总额，正数）
  gap: number;            // 元（assets - liabilities）
  cum_gap: number;        // 元（从第一个桶到当前桶的累计缺口）
  gap_ratio: number;      // 小数（gap / total_assets）
};

export type LiquidityGapResponse = {
  report_date: string;
  total_assets: number;   // 元（用于 GapRatio 分母）
  buckets: LiquidityGapBucket[];
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 参数 | 返回类型 | client.ts 方法名 |
|------|--------|------|----------|-----------------|
| 流动性缺口 | `GET /api/analysis/liquidity_gap` | `?report_date=YYYY-MM-DD` | `LiquidityGapResponse` | `getLiquidityGap(reportDate)` |

---

## 三、核心计算逻辑

### 图表数据转换
```typescript
const chartData = useMemo(() => {
  return (data?.buckets || []).map((b) => {
    const liabilitiesNeg = -Math.abs(b.liabilities || 0); // 负债取负值
    const cum = b.cum_gap || 0;
    return {
      bucket_name: b.bucket_name,
      assets: b.assets || 0,                    // 正值
      liabilities: liabilitiesNeg,               // 负值
      cum_gap_pos: cum >= 0 ? cum : null,        // 正累计缺口（蓝线）
      cum_gap_neg: cum < 0 ? cum : null,         // 负累计缺口（红线）
      gap: b.gap || 0,
    };
  });
}, [data]);
```

### 关键指标
```typescript
// 最小累计缺口（压力点）= 所有桶中 cum_gap 的最小值
const minCumGap = buckets.reduce((m, x) => Math.min(m, x.cum_gap), Infinity);

// 期末累计缺口 = 最后一个桶的 cum_gap
const endCumGap = buckets[buckets.length - 1]?.cum_gap;

// GapRatio = gap / total_assets（后端已算好，在每个 bucket 的 gap_ratio 字段）
```

### 金额格式化
```typescript
const formatYi = (v: number | null | undefined) => {
  if (v === null || v === undefined) return '-';
  return `${(v / 100000000).toFixed(2)} 亿元`;
};
```

---

## 四、页面布局

这是一个单页面，没有 Tab 切换。数据加载：`GET /api/analysis/liquidity_gap?report_date=`

布局从上到下：

1. **页面标题**
   - 标题：`流动性缺口分析（Liquidity Gap）`
   - 副标题：`数据日期：{report_date}`
   - 右上角徽章：`Liquidity Gap`

2. **概览 KPI 卡片**（3 列网格）
   - 总资产（用于 GapRatio 分母）：`formatYi(data.total_assets)`
   - 最小累计缺口（压力点）：`formatYi(minCumGap)`
     - 底部说明：`累计缺口跌破 0（红线）意味着出现期限错配的流动性风险`
   - 期末累计缺口：`formatYi(endCumGap)`

3. **双向柱状 + 累计缺口线图**（核心图表）
   - 标题：`期限桶资金池/资金坑 + 累计缺口`
   - echarts ComposedChart（柱状+折线混合图）
   - 高度 380px
   - 底部说明：`柱：资产为正、负债为负；线：累计缺口（跌破 0 自动红色）。Y轴单位：亿元`

4. **明细表格**
   - 标题：`期限桶明细`
   - 列：期限桶 | 资产(亿) | 负债(亿) | 缺口(亿) | 累计缺口(亿) | GapRatio(%)
   - 缺口 < 0 红色字体
   - 累计缺口 < 0 红色字体 + 红色背景
   - GapRatio 显示：`(gap_ratio * 100).toFixed(2)%`

---

## 五、图表配置（echarts）

### 双向柱状 + 累计缺口折线（核心图表）
```typescript
const option: EChartsOption = {
  tooltip: {
    trigger: 'axis',
    formatter: (params) => {
      // 负债显示绝对值
      // 格式：桶名\n资产：xx亿\n负债：xx亿\n缺口：xx亿\n累计缺口：xx亿
    }
  },
  legend: {
    data: ['Assets(+) 资产', 'Liabilities(-) 负债', 'CumGap(+) 累计缺口', 'CumGap(-) 累计缺口(风险)']
  },
  grid: { left: 60, right: 60 },
  xAxis: {
    type: 'category',
    data: chartData.map(d => d.bucket_name),
  },
  yAxis: {
    type: 'value',
    axisLabel: { formatter: (v) => (v / 1e8).toFixed(0) }  // 亿元
  },
  series: [
    {
      name: 'Assets(+) 资产',
      type: 'bar',
      data: chartData.map(d => d.assets),
      itemStyle: { color: '#60a5fa', borderRadius: [6, 6, 0, 0] },
    },
    {
      name: 'Liabilities(-) 负债',
      type: 'bar',
      data: chartData.map(d => d.liabilities),  // 负值
      itemStyle: { color: '#fb7185', borderRadius: [0, 0, 6, 6] },
    },
    {
      name: 'CumGap(+) 累计缺口',
      type: 'line',
      data: chartData.map(d => d.cum_gap_pos),  // 正值部分
      lineStyle: { color: '#1d4ed8', width: 2 },
      itemStyle: { color: '#1d4ed8' },
      symbol: 'none',
      connectNulls: false,
    },
    {
      name: 'CumGap(-) 累计缺口(风险)',
      type: 'line',
      data: chartData.map(d => d.cum_gap_neg),  // 负值部分（红色）
      lineStyle: { color: '#ef4444', width: 2 },
      itemStyle: { color: '#ef4444' },
      symbol: 'none',
      connectNulls: false,
    },
  ]
};
```

关键点：
- 资产柱子向上（正值），负债柱子向下（负值）
- 累计缺口用两条线：正值蓝色 `#1d4ed8`，负值红色 `#ef4444`
- Y 轴单位：亿元

---

## 六、业务口径说明

1. 流动性缺口 = 各期限桶的资产 - 负债
2. 累计缺口 = 从最短期限桶到当前桶的缺口累加
3. 累计缺口跌破 0 意味着出现期限错配的流动性风险
4. GapRatio = 单桶缺口 / 总资产
5. 最小累计缺口 = 所有桶中累计缺口的最小值，是流动性压力的极端点

---

## 七、路由和导航注册

routes.tsx:
```typescript
const LiquidityGapPage = lazy(() => import("../features/liquidity-gap/pages/LiquidityGapPage"));
if (section.path === "/liquidity-gap") {
  return { path: section.path.slice(1), element: routeElement(<LiquidityGapPage />) };
}
```

navigation.ts:
```typescript
{
  key: "liquidity-gap",
  label: "流动性缺口",
  path: "/liquidity-gap",
  icon: "risk",
  description: "期限桶流动性缺口分析",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接流动性缺口读链路。",
},
```
