# Prompt 2：日均管理 AverageBalance (ADB)

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「日均管理（ADB）」页面，完全对齐 V1 的计算口径和功能。

## V3 架构模式
同 Prompt 1（参考 `src/features/positions/components/PositionsView.tsx`）。

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 日均管理 ADB */
export type AdbCategoryItem = {
  category: string;
  spot_balance: number;       // 元（期末时点）
  avg_balance: number;        // 元（区间日均）
  proportion: number;         // 百分数，如 35.2
  weighted_rate?: number | null; // 百分数（年化），如 2.55
};

export type AdbComparisonResponse = {
  report_date: string;
  start_date: string;
  end_date: string;
  num_days: number;
  simulated: boolean;         // 仅1天时为 true，日均为稳态模拟
  total_spot_assets: number;
  total_avg_assets: number;
  total_spot_liabilities: number;
  total_avg_liabilities: number;
  asset_yield: number | null;       // 百分数（年化）
  liability_cost: number | null;    // 百分数
  net_interest_margin: number | null; // 百分数
  assets_breakdown: AdbCategoryItem[];
  liabilities_breakdown: AdbCategoryItem[];
};

export type AdbMonthlyBreakdownItem = {
  category: string;
  avg_balance: number;        // 元
  proportion?: number | null; // 百分数
  weighted_rate?: number | null; // 百分数
};

export type AdbMonthlyDataItem = {
  month: string;              // "2026-01"
  month_label: string;        // "2026年1月"
  num_days: number;
  avg_assets: number;
  avg_liabilities: number;
  asset_yield: number | null;       // 百分数
  liability_cost: number | null;    // 百分数
  net_interest_margin: number | null; // 百分数
  mom_change_assets: number | null;
  mom_change_pct_assets: number | null;
  mom_change_liabilities: number | null;
  mom_change_pct_liabilities: number | null;
  breakdown_assets: AdbMonthlyBreakdownItem[];
  breakdown_liabilities: AdbMonthlyBreakdownItem[];
};

export type AdbMonthlyResponse = {
  year: number;
  months: AdbMonthlyDataItem[];
  ytd_avg_assets: number;
  ytd_avg_liabilities: number;
  ytd_asset_yield: number | null;
  ytd_liability_cost: number | null;
  ytd_nim: number | null;
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 参数 | 返回类型 | client.ts 方法名 |
|------|--------|------|----------|-----------------|
| Spot vs ADB 对比 | `GET /api/analysis/adb/comparison` | `?start_date=&end_date=` | `AdbComparisonResponse` | `getAdbComparison(startDate, endDate)` |
| 月度统计 | `GET /api/analysis/adb/monthly` | `?year=2026` | `AdbMonthlyResponse` | `getAdbMonthly(year)` |

---

## 三、核心计算逻辑

### Spot vs ADB 偏离（核心功能 — 识别"窗口粉饰"）
```typescript
// 偏离度 = (Spot - ADB) / ADB × 100
// 当偏离度 > 5% 时标红提示"窗口粉饰"风险
const deviationAssets = totalAvgAssets > 0
  ? ((totalSpotAssets - totalAvgAssets) / totalAvgAssets) * 100
  : 0;
const deviationLiabilities = totalAvgLiabilities > 0
  ? ((totalSpotLiabilities - totalAvgLiabilities) / totalAvgLiabilities) * 100
  : 0;
```

### 区间选择器
```typescript
// 三个预设区间：7d / 30d / YTD
// 7d: end_date = reportDate, start_date = reportDate - 7天
// 30d: end_date = reportDate, start_date = reportDate - 30天
// YTD: end_date = reportDate, start_date = 当年1月1日
// 也支持自定义日期范围
```

### 金额格式化
```typescript
const formatYi = (v: number) => `${(v / 100000000).toFixed(2)} 亿元`;
const formatWan = (v: number) => `${(v / 10000).toFixed(2)} 万元`;
```

---

## 四、页面布局

### 两个 Tab：日均分析 / 月度统计

#### Tab 1：日均分析
数据加载：`GET /api/analysis/adb/comparison?start_date=&end_date=`

布局从上到下：

1. **区间选择器**（顶部工具栏）
   - 三个按钮：7D / 30D / YTD（默认 YTD）
   - 自定义日期范围输入
   - 右侧显示：`有效天数：{num_days} 天`
   - 如果 `simulated === true`，显示提示：`当前区间仅1天，日均为稳态模拟，便于演示图表逻辑`

2. **概览 KPI 卡片**（6 列网格）
   - Spot 总资产 | ADB 总资产 | 偏离度(资产)
   - Spot 总负债 | ADB 总负债 | 偏离度(负债)
   - 偏离度 > 5% 时红色字体 + 警告图标
   - 口径说明：`Spot=期末（end_date）时点规模；Avg=区间日均规模`

3. **Spot vs ADB 偏离对比图**（echarts 分组柱状图）
   - X 轴：分类名称（资产端各分类 + 负债端各分类）
   - 两组柱子：Spot（蓝色 #3b82f6）vs ADB（橙色 #f97316）
   - 偏离度标注在柱子上方

4. **收益率/NIM 卡片**（3 列网格）
   - 资产收益率(年化) | 负债付息率(年化) | NIM(年化)
   - 值已经是百分数格式（如 2.55），直接显示 `2.55%`
   - NIM < 0 红色

5. **资产端分类明细表**
   - 列：分类 | Spot(亿) | 日均(亿) | 占比(%) | 收益率(%)
   - 数据源：`assets_breakdown`

6. **负债端分类明细表**
   - 列：分类 | Spot(亿) | 日均(亿) | 占比(%) | 付息率(%)
   - 数据源：`liabilities_breakdown`

#### Tab 2：月度统计
数据加载：`GET /api/analysis/adb/monthly?year=`

布局：
1. **年份选择器**（2024/2025/2026）
2. **YTD 汇总卡片**（5 列网格）
   - YTD 日均资产 | YTD 日均负债 | YTD 资产收益率 | YTD 负债付息率 | YTD NIM
3. **月度汇总表**（可展开行）
   - 列：月份 | 天数 | 日均资产(亿) | 日均负债(亿) | 资产收益率 | 负债付息率 | NIM | 资产环比 | 负债环比
   - 展开后显示：资产分类明细表 + 负债分类明细表
   - 资产分类明细列：分类 | 日均(亿) | 占比 | 付息率
   - 负债分类明细列：分类 | 日均(亿) | 占比 | 付息率
4. **按月度日均分析 - 深度分析**
   - 月份选择器
   - 选中月份后显示两个并排卡片：
     - 左：资产端分类明细（横向柱状图 + 表格）
     - 右：负债端分类明细（横向柱状图 + 表格）

---

## 五、图表配置（echarts）

### Spot vs ADB 偏离对比图
```typescript
const option: EChartsOption = {
  tooltip: { trigger: 'axis' },
  legend: { data: ['Spot（期末）', 'ADB（日均）'] },
  xAxis: { type: 'category', data: categories },
  yAxis: { type: 'value', axisLabel: { formatter: (v) => (v / 1e8).toFixed(0) + '亿' } },
  series: [
    { name: 'Spot（期末）', type: 'bar', data: spotValues, itemStyle: { color: '#3b82f6' }, barGap: '10%' },
    { name: 'ADB（日均）', type: 'bar', data: avgValues, itemStyle: { color: '#f97316' } },
  ]
};
```

### 月度深度分析横向柱状图
```typescript
// 资产端：蓝色 #2563EB
// 负债端：红色 #DC2626
// 横向柱状图，Y轴=分类名称，X轴=金额(亿元)
// 每个柱子上标注金额
```

---

## 六、业务口径说明（V1 原文）

1. `口径：Spot=期末（end_date）时点规模；Avg=区间日均规模。`
2. `当前区间仅1天，日均为稳态模拟，便于演示图表逻辑`（simulated=true 时）
3. 收益率/付息率/NIM：后端返回百分数格式（2.55 = 2.55%），直接显示，不需要 ×100
4. 金额：后端返回元，前端 ÷1亿 显示

---

## 七、路由和导航注册

routes.tsx:
```typescript
const AverageBalancePage = lazy(() => import("../features/average-balance/pages/AverageBalancePage"));
if (section.path === "/average-balance") {
  return { path: section.path.slice(1), element: routeElement(<AverageBalancePage />) };
}
```

navigation.ts:
```typescript
{
  key: "average-balance",
  label: "日均管理",
  path: "/average-balance",
  icon: "analysis",
  description: "ADB 日均余额管理：Spot vs ADB 偏离、NIM 趋势、月度统计",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接 ADB 日均分析读链路。",
},
```
