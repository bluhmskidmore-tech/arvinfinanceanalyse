# Prompt 1：负债结构分析 LiabilityAnalytics

## 任务
在 V3 前端 `F:/MOSS-V3/frontend/` 补建「负债结构分析」页面，完全对齐 V1 的计算口径和功能。

## V3 架构模式（必须遵守）
- 参考 `src/features/positions/components/PositionsView.tsx` 的写法
- `useApiClient()` + `useQuery`（@tanstack/react-query）
- antd 组件（Card, Table, Tabs, Select, Button, Typography, Spin, Row, Col, Space）
- 图表：`import ReactECharts, { type EChartsOption } from "../../../lib/echarts"`
- 类型追加到 `src/api/contracts.ts`
- API 方法添加到 `src/api/client.ts` 的 ApiClient 类（后端不存在的加 `// TODO: 后端待实现`）
- 路由注册 `src/router/routes.tsx`（lazy import + Suspense + WorkbenchRouteFallback）
- 导航注册 `src/mocks/navigation.ts`
- Feature-Sliced：`src/features/liability-analytics/pages/` + `components/`

---

## 一、TypeScript 类型定义（追加到 contracts.ts）

```typescript
/** 负债结构分析 */
export type LiabBucketAmountItem = {
  bucket: string;
  amount?: number | null;
  amount_yi?: number | null;
};

export type LiabNameAmountItem = {
  name: string;
  amount?: number | null;
  amount_yi?: number | null;
};

export type LiabRiskAnalysis = {
  report_date: string;
  liabilities_structure: LiabNameAmountItem[];
  liabilities_term_buckets: LiabBucketAmountItem[];
  interbank_liabilities_structure?: LiabNameAmountItem[];
  interbank_liabilities_term_buckets?: LiabBucketAmountItem[];
  issued_liabilities_structure?: LiabNameAmountItem[];
  issued_liabilities_term_buckets?: LiabBucketAmountItem[];
};

export type LiabYieldKpi = {
  asset_yield: number | null;       // 小数，如 0.025
  liability_cost: number | null;    // 小数
  market_liability_cost: number | null; // 小数
  nim: number | null;               // 小数
};

export type LiabYieldMetricsResponse = {
  report_date: string;
  kpi: LiabYieldKpi;
};

export type LiabCounterpartyItem = {
  name: string;
  value: number;       // 元
  type?: string;       // "Bank" | "NonBank" | "Other"
};

export type LiabTypeItem = {
  name: string;        // "Bank" | "NonBank"
  value: number;       // 元
};

export type LiabCounterpartyResponse = {
  report_date: string;
  total_value: number;
  top_10: LiabCounterpartyItem[];
  by_type: LiabTypeItem[];
};

/** 月度统计 */
export type LiabMonthlyCounterpartyDetailItem = {
  name: string;
  avg_value: number;
  proportion: number;          // 百分数，如 15.5 = 15.5%
  weighted_cost?: number | null; // 小数
  type?: string | null;
};

export type LiabMonthlyCategoryBreakdownItem = {
  category: string;
  avg_balance: number;
  proportion: number;
};

export type LiabMonthlyBucketItem = {
  bucket: string;
  avg_balance: number;
};

export type LiabMonthlyInstitutionTypeItem = {
  type: string;
  avg_value: number;
};

export type LiabilitiesMonthlyItem = {
  month: string;                    // "2026-01"
  month_label: string;              // "2026年1月"
  avg_total_liabilities: number;
  avg_interbank_liabilities: number;
  avg_issued_liabilities: number;
  avg_liability_cost: number | null;
  mom_change: number | null;
  mom_change_pct: number | null;
  counterparty_top10?: LiabMonthlyCounterpartyDetailItem[];
  by_institution_type?: LiabMonthlyInstitutionTypeItem[];
  structure_overview?: LiabMonthlyCategoryBreakdownItem[];
  term_buckets?: LiabMonthlyBucketItem[];
  interbank_by_type?: LiabMonthlyCategoryBreakdownItem[];
  interbank_term_buckets?: LiabMonthlyBucketItem[];
  issued_by_type?: LiabMonthlyCategoryBreakdownItem[];
  issued_term_buckets?: LiabMonthlyBucketItem[];
  counterparty_details?: LiabMonthlyCounterpartyDetailItem[];
  num_days: number;
};

export type LiabilitiesMonthlyResponse = {
  year: number;
  months: LiabilitiesMonthlyItem[];
  ytd_avg_total_liabilities: number;
  ytd_avg_liability_cost: number | null;
};

export type LiabAdbMonthlyItem = {
  month: string;
  asset_yield: number | null;          // 百分数（年化），如 2.55
  liability_cost: number | null;       // 百分数
  net_interest_margin: number | null;  // 百分数
};

export type LiabAdbMonthlyResponse = {
  year: number;
  months: LiabAdbMonthlyItem[];
};
```

---

## 二、API 调用清单

| 用途 | V1 URL | 参数 | 返回类型 | client.ts 方法名 |
|------|--------|------|----------|-----------------|
| 负债结构主数据 | `GET /api/risk/buckets` | `?report_date=YYYY-MM-DD` | `LiabRiskAnalysis` | `getLiabRiskBuckets(reportDate)` |
| 收益率/NIM KPI | `GET /api/analysis/yield_metrics` | `?report_date=YYYY-MM-DD` | `LiabYieldMetricsResponse` | `getLiabYieldMetrics(reportDate)` |
| 对手方维度 | `GET /api/analysis/liabilities/counterparty` | `?report_date=&top_n=2000` | `LiabCounterpartyResponse` | `getLiabCounterparty(reportDate, topN)` |
| 月度统计 | `GET /api/liabilities/monthly` | `?year=2026` | `LiabilitiesMonthlyResponse` | `getLiabilitiesMonthly(year)` |
| 月度ADB | `GET /api/analysis/adb/monthly` | `?year=2026` | `LiabAdbMonthlyResponse` | `getLiabAdbMonthly(year)` |

---

## 三、核心计算逻辑

### NIM 压力测试（最重要的计算）
```typescript
// 口径：资产收益率 - 金融市场同业负债成本（全口径TYWL + 发行同业存单）
const stress = useMemo(() => {
  const ay = yieldKpi?.asset_yield ?? null;       // 小数，如 0.025
  const mlc = yieldKpi?.market_liability_cost ?? null; // 小数
  const nim = yieldKpi?.nim ?? (ay !== null && mlc !== null ? ay - mlc : null);
  // +50bps = +0.50% = +0.005（decimal）
  const projected = ay !== null && mlc !== null ? ay - (mlc + 0.005) : null;
  const delta = projected !== null && nim !== null ? projected - nim : null;
  const isCritical = projected !== null ? projected < 0.005 : false; // <0.50% 触发预警
  return { ay, mlc, nim, projected, delta, isCritical };
}, [yieldKpi]);
```

### 机构类型结构（银行 vs 非银行）
```typescript
const donut = useMemo(() => {
  const by = cp?.by_type || [];
  const bank = by.find((x) => x.name === 'Bank')?.value || 0;
  const nonbank = by.reduce((sum, x) => (x.name === 'Bank' ? sum : sum + (x.value || 0)), 0);
  return [
    { name: '银行', value: bank },
    { name: '非银行', value: nonbank },
  ];
}, [cp]);
```

### 金额转换
```typescript
// 后端返回元或亿元，统一转为亿元
const toAmountYi = (item) => item.amount_yi ?? ((item.amount ?? 0) / 100000000);
```

### 月度口径 NIM 压力测试
```typescript
// 月度口径下，ADB 返回的 asset_yield/liability_cost/net_interest_margin 已经是百分数（如 2.55 = 2.55%）
// 压力后 NIM = net_interest_margin - 0.5（即 -50bp）
const projectedMonthly = selectedAdbMonthData.net_interest_margin - 0.5;
```

---

## 四、页面布局

### 两个 Tab：日常分析 / 月度统计

#### Tab 1：日常分析
数据加载：并行请求 `/api/risk/buckets` + `/api/analysis/yield_metrics`，单独请求 `/api/analysis/liabilities/counterparty`

布局从上到下：

1. **NIM 压力测试卡片**（4 列网格）
   - 资产收益率 | 金融市场同业负债成本(增值税前) | 当前 NIM | 压力后 NIM(+50bps)
   - 口径说明：`资产收益率 - 金融市场同业负债成本（全口径TYWL + 发行同业存单）`
   - NIM < 0 显示红色，isCritical 时右上角显示"NIM 预警"徽章
   - delta 用 bp 显示：`(stress.delta * 10000).toFixed(0) bp`

2. **资金来源依赖度**（3 列网格：左 2/3 + 右 1/3）
   - 左：Top 10 对手方横向柱状图
     - 口径：`TYWL 负债端（对手方名称 × 余额；剔除"青岛银行股份有限公司"）`
     - 横向柱状图，数据倒序（最大在上）
     - Tooltip：名称、余额(亿)、占比(%)、加权负债成本(%)、类型
   - 右：机构类型饼图（银行 vs 非银行）
     - 环形饼图，银行=#DC2626，非银行=#0f172a
     - 底部说明：`银行占比越高，通常资金稳定性更强；非银行占比上升需关注期限错配与流动性压力。`

3. **负债结构三栏**（3 列网格）
   - 负债结构总览饼图（`liabilities_structure`）
   - 同业负债结构饼图（`interbank_liabilities_structure`）
   - 发行负债结构饼图（`issued_liabilities_structure`）
   - 颜色：`['#dc2626', '#2563eb', '#0891b2', '#059669', '#7c3aed']`

4. **期限分布三栏**（3 列网格）
   - 负债期限分布柱状图（`liabilities_term_buckets`）
   - 同业负债期限分布柱状图（`interbank_liabilities_term_buckets`）
   - 发行负债期限分布柱状图（`issued_liabilities_term_buckets`）
   - 柱状图颜色：#DC2626

5. **客户维度全量明细表**
   - 数据源：`cp.top_10`（实际请求 top_n=2000，全量）
   - 列：排名 | 对手方名称 | 余额(亿元) | 占比(%) | 加权负债成本(%) | 类型
   - 加权负债成本：`(Number(item.weighted_cost) * 100).toFixed(2)%`（小数→百分比）

#### Tab 2：月度统计
数据加载：`/api/liabilities/monthly?year=` + `/api/analysis/adb/monthly?year=`

布局：
1. **年份选择器 + 月份选择器**
2. **NIM 压力测试卡片**（同日常分析，但用月度 ADB 数据）
   - 口径：`月度日均（ADB月度收益率/付息率；若缺失则仅展示结构）`
3. **Top 10 对手方横向柱状图**（月度日均口径）
4. **机构类型饼图**
5. **月度汇总表**（可展开行）
   - 列：月份 | 日均总负债(亿) | 日均同业(亿) | 日均发行(亿) | 付息率 | 环比变化(亿) | 环比(%)
   - 展开后显示：Top10 对手方明细表 + 分类明细表
6. **YTD 汇总卡片**：年度日均总负债、年度日均付息率

---

## 五、图表配置（echarts）

### 横向柱状图（Top 10 对手方）
```typescript
const option: EChartsOption = {
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const d = params[0].data;
      return `${d.name}<br/>余额：${d.value_yi.toFixed(2)} 亿元<br/>占比：${d.pct.toFixed(2)}%<br/>加权负债成本：${d.weighted_cost != null ? (d.weighted_cost * 100).toFixed(2) + '%' : '—'}<br/>类型：${d.type || '—'}`;
    }
  },
  grid: { left: 140, right: 20, top: 6, bottom: 6 },
  xAxis: { type: 'value' },
  yAxis: { type: 'category', data: [...cpTop10].reverse().map(d => d.name) },
  series: [{ type: 'bar', data: [...cpTop10].reverse().map(d => d.value_yi), itemStyle: { color: '#DC2626', borderRadius: 6 } }]
};
```

### 环形饼图（机构类型）
```typescript
const option: EChartsOption = {
  series: [{
    type: 'pie',
    radius: ['55%', '80%'],
    data: [
      { name: '银行', value: bankValue, itemStyle: { color: '#DC2626' } },
      { name: '非银行', value: nonbankValue, itemStyle: { color: '#0f172a' } },
    ],
    label: { formatter: '{b}: {d}%' },
  }]
};
```

### 负债结构饼图
```typescript
const COLORS = ['#dc2626', '#2563eb', '#0891b2', '#059669', '#7c3aed'];
// 环形饼图，innerRadius=60, outerRadius=100
```

### 期限分布柱状图
```typescript
// 普通竖向柱状图，X轴=期限桶名称，Y轴=金额(亿元)
// 柱子颜色=#DC2626，圆角=[6,6,0,0]
```

---

## 六、业务口径说明（V1 原文）

1. NIM 压力测试：`口径：资产收益率 - 金融市场同业负债成本（全口径TYWL + 发行同业存单）`
2. 对手方依赖度：`口径：TYWL 负债端（对手方名称 × 余额；剔除"青岛银行股份有限公司"）`
3. 月度口径：`口径：月度日均（ADB月度收益率/付息率；若缺失则仅展示结构）`
4. 月度对手方：`口径：月度日均（TYWL 负债端）`
5. 加权负债成本：V1 中 `weighted_cost` 是小数格式（0.025 = 2.5%），显示时 ×100

---

## 七、路由和导航注册

routes.tsx:
```typescript
const LiabilityAnalyticsPage = lazy(() => import("../features/liability-analytics/pages/LiabilityAnalyticsPage"));
// 在 buildWorkbenchChildRoutes 中添加：
if (section.path === "/liability-analytics") {
  return { path: section.path.slice(1), element: routeElement(<LiabilityAnalyticsPage />) };
}
```

navigation.ts:
```typescript
{
  key: "liability-analytics",
  label: "负债结构",
  path: "/liability-analytics",
  icon: "analysis",
  description: "负债结构深度分析：NIM 压力测试、对手方集中度、期限分布",
  readiness: "live",
  readinessLabel: "Live",
  readinessNote: "已接负债分析读链路，含 NIM 压力测试与对手方维度。",
},
```
