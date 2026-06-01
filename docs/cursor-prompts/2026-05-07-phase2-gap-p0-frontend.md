# Cursor Prompt: Phase 2 缺口 P0 — 前端接入四个端点

> 后端 prompt（2026-05-07-phase2-gap-p0-backend.md）执行完成后再跑本 prompt。
> 粘贴到 Cursor chat 执行。

---

## 前置条件

后端已实现以下端点（先确认能 200 再开始前端）：

```bash
# 启动后端后验证
curl "http://localhost:8000/api/dashboard/core_metrics" | python -m json.tool | head -20
curl "http://localhost:8000/api/dashboard/daily-changes" | python -m json.tool | head -20
curl "http://localhost:8000/api/bond-dashboard/business-type-metrics?report_date=2026-03-31" | python -m json.tool | head -20
curl "http://localhost:8000/api/positions/counterparty/bonds?start_date=2026-03-01&end_date=2026-03-31" | python -m json.tool | head -20
```

**先读以下文件再动手：**
- `AGENTS.md`
- `CLAUDE.md`
- `frontend/src/api/client.ts`（了解 ApiClient 组合模式）
- `frontend/src/api/contracts.ts`（了解类型规范）
- `frontend/src/features/workbench/pages/DashboardPage.tsx`（了解 dashboard 现有结构）

---

## 执行前必做

```bash
git status --short
```

只改本任务列出的文件，不碰无关脏文件。

---

## Task 1 — contracts.ts 新增类型

**修改文件：** `frontend/src/api/contracts.ts`

新增以下类型（放在文件末尾，不改现有类型）：

```ts
// ── Dashboard core metrics ──────────────────────────────────────────────────

export type CoreMetricsCardData = {
  total_amount: Numeric;
  weighted_avg_rate: Numeric;
  change_amount: Numeric;
  change_pct: Numeric;
  top_3_details: Array<{ name: string; amount: string; rate: string }>;
};

export type CoreMetricsResult = {
  report_date: string;
  bond_investments: CoreMetricsCardData;
  interbank_assets: CoreMetricsCardData;
  interbank_liabilities: CoreMetricsCardData;
};

export type CoreMetricsPayload = ApiEnvelope<CoreMetricsResult>;

// ── Dashboard daily changes ─────────────────────────────────────────────────

export type DailyChangePeriod = {
  period: "day" | "week" | "month";
  bond_investments_change: Numeric;
  interbank_assets_change: Numeric;
  interbank_liabilities_change: Numeric;
  net_change: Numeric;
};

export type DailyChangesResult = {
  report_date: string;
  periods: DailyChangePeriod[];
};

export type DailyChangesPayload = ApiEnvelope<DailyChangesResult>;

// ── Bond dashboard business type metrics ────────────────────────────────────

export type BondBusinessTypeMetricItem = {
  name: string;
  market_value: string;
  weighted_avg_ytm_pct: string;
  weighted_avg_duration: string;
  duration_source: string;
};

export type BondBusinessTypeMetricsResult = {
  report_date: string;
  items: BondBusinessTypeMetricItem[];
};

export type BondBusinessTypeMetricsPayload = ApiEnvelope<BondBusinessTypeMetricsResult>;

// ── Counterparty bonds（扩展现有类型，补 cr10_ratio）──────────────────────────
// 在现有 CounterpartyStatsResponse 类型中追加字段（如已存在则跳过）：
// cr10_ratio?: string | null;
```

对于 `CounterpartyStatsResponse`，找到现有定义，追加 `cr10_ratio?: string | null`，不要重写整个类型。

---

## Task 2 — API client 新增方法

**修改文件：** `frontend/src/api/client.ts`

### 2a. 新增 DashboardClientMethods 类型

在现有各 `*ClientMethods` 类型附近新增：

```ts
type DashboardClientMethods = {
  getCoreMetrics: (params?: { reportDate?: string }) => Promise<CoreMetricsPayload>;
  getDailyChanges: (params?: { reportDate?: string }) => Promise<DailyChangesPayload>;
};
```

### 2b. 将 DashboardClientMethods 加入 ApiClient 组合

```ts
export type ApiClient = {
  mode: DataSourceMode;
} & ExecutiveClientMethods
  & DashboardClientMethods   // ← 新增
  & PnlClientMethods
  // ... 其余不变
```

### 2c. 新增 BondBusinessTypeMetrics 方法

找到 `BondAnalyticsClientMethods`（或 `BondDashboardClientMethods`），追加：

```ts
getBondBusinessTypeMetrics: (params: { reportDate: string }) => Promise<BondBusinessTypeMetricsPayload>;
```

### 2d. 实现 real 模式方法

在 `createApiClient` 的 real 分支中实现：

```ts
// Dashboard
getCoreMetrics: async ({ reportDate } = {}) => {
  const url = reportDate
    ? `${baseUrl}/api/dashboard/core_metrics?report_date=${reportDate}`
    : `${baseUrl}/api/dashboard/core_metrics`;
  return fetchJson(url);
},
getDailyChanges: async ({ reportDate } = {}) => {
  const url = reportDate
    ? `${baseUrl}/api/dashboard/daily-changes?report_date=${reportDate}`
    : `${baseUrl}/api/dashboard/daily-changes`;
  return fetchJson(url);
},
// Bond business type metrics
getBondBusinessTypeMetrics: async ({ reportDate }) =>
  fetchJson(`${baseUrl}/api/bond-dashboard/business-type-metrics?report_date=${reportDate}`),
```

### 2e. 实现 mock 模式方法

mock 返回稳定的最小 payload，`result_meta.basis = "mock"`，`result_meta.quality_flag = "ok"`：

```ts
getCoreMetrics: async () => buildMockEnvelope("dashboard.core_metrics", {
  report_date: MOCK_REPORT_DATE,
  bond_investments: mockCoreCard("债券投资", "8,234.56 亿", "+12.30 亿"),
  interbank_assets: mockCoreCard("同业资产", "1,456.78 亿", "-5.20 亿"),
  interbank_liabilities: mockCoreCard("同业负债", "2,100.00 亿", "+8.00 亿"),
}),
getDailyChanges: async () => buildMockEnvelope("dashboard.daily_changes", {
  report_date: MOCK_REPORT_DATE,
  periods: [
    { period: "day", bond_investments_change: mockNumeric("+12.30 亿"), interbank_assets_change: mockNumeric("-5.20 亿"), interbank_liabilities_change: mockNumeric("+8.00 亿"), net_change: mockNumeric("+15.10 亿") },
    { period: "week", bond_investments_change: mockNumeric("+45.00 亿"), interbank_assets_change: mockNumeric("-12.00 亿"), interbank_liabilities_change: mockNumeric("+20.00 亿"), net_change: mockNumeric("+53.00 亿") },
    { period: "month", bond_investments_change: mockNumeric("+120.00 亿"), interbank_assets_change: mockNumeric("-30.00 亿"), interbank_liabilities_change: mockNumeric("+50.00 亿"), net_change: mockNumeric("+140.00 亿") },
  ],
}),
getBondBusinessTypeMetrics: async () => buildMockEnvelope("bond_dashboard.business_type_metrics", {
  report_date: MOCK_REPORT_DATE,
  items: [
    { name: "利率债", market_value: "5000000000.00", weighted_avg_ytm_pct: "2.55", weighted_avg_duration: "3.21", duration_source: "formal" },
    { name: "信用债", market_value: "3000000000.00", weighted_avg_ytm_pct: "3.10", weighted_avg_duration: "2.80", duration_source: "formal" },
  ],
}),
```

mock helper 参考现有 `buildMockEnvelope` / `mockNumeric` 等已有工具函数，不要重新发明。

**守则：** `client.ts` 只做组合和 fetch，不做业务逻辑。mock 数据保持最小，够测试用即可。

---

## Task 3 — DashboardPage 接入 core_metrics 和 daily-changes

**修改文件：** `frontend/src/features/workbench/pages/DashboardPage.tsx`

### 3a. 新增两个 query

```ts
const coreMetricsQuery = useQuery({
  queryKey: ["dashboard", "core-metrics", client.mode, reportDate],
  queryFn: () => client.getCoreMetrics({ reportDate: reportDate ?? undefined }),
  retry: false,
  staleTime: 60_000,
});

const dailyChangesQuery = useQuery({
  queryKey: ["dashboard", "daily-changes", client.mode, reportDate],
  queryFn: () => client.getDailyChanges({ reportDate: reportDate ?? undefined }),
  retry: false,
  staleTime: 60_000,
});
```

### 3b. 新增 CoreMetricsSection 展示组件

在 `frontend/src/features/workbench/dashboard/` 新建：
`DashboardCoreMetricsSection.tsx`

展示三张 KPI 卡（债券投资 / 同业资产 / 同业负债），每张卡显示：
- 标题
- `total_amount.display`
- `weighted_avg_rate.display`（利率）
- `change_amount.display` + `change_pct.display`（变动，带正负色）
- `top_3_details` 列表（最多3行）

loading 态：骨架屏占位。
error 态：`数据暂不可用`。
`result_meta.quality_flag !== "ok"` 时显示小角标。

### 3c. 新增 DailyChangesSection 展示组件

在同目录新建：`DashboardDailyChangesSection.tsx`

展示 day / week / month 三行变动表格：

| 周期 | 债券投资 | 同业资产 | 同业负债 | 净变动 |
|------|---------|---------|---------|--------|

正值绿色，负值红色（中国惯例：红涨绿跌，但变动用通用正负色即可，以现有 `tone` 颜色变量为准）。

### 3d. 在 DashboardPage 中挂载

在现有 overview / summary 区块之后，加入：

```tsx
<DashboardCoreMetricsSection
  query={coreMetricsQuery}
  reportDate={reportDate}
/>
<DashboardDailyChangesSection
  query={dailyChangesQuery}
/>
```

布局跟随现有 dashboard 栅格，不引入新的 inline style 块。

---

## Task 4 — BondDashboardPage 接入 business-type-metrics

**先确认实际文件路径：**

```bash
find F:/MOSS-V3/frontend/src/features/bond-dashboard -name "*.tsx" | head -20
```

找到 bond dashboard 主页面文件，在其中：

### 4a. 新增 query

```ts
const businessTypeMetricsQuery = useQuery({
  queryKey: ["bond-dashboard", "business-type-metrics", client.mode, reportDate],
  queryFn: () => client.getBondBusinessTypeMetrics({ reportDate }),
  enabled: Boolean(reportDate),
  retry: false,
  staleTime: 60_000,
});
```

### 4b. 展示

在现有 bond dashboard 页面中找到合适位置（建议在 asset-structure 或 headline-kpis 附近），新增业务类型加权指标表格：

| 业务类型 | 市值（亿） | 加权 YTM | 加权久期 |
|---------|-----------|---------|---------|

loading / error / empty 态处理同现有组件风格。

---

## Task 5 — PositionsPage 展示 cr10_ratio

**修改文件：** `frontend/src/features/positions/components/PositionsView.tsx`（或实际文件）

找到 counterparty bonds 展示区域，在对手方集中度部分补充：

```tsx
{counterpartyData?.result?.cr10_ratio && (
  <span className="positions-view__cr10">
    CR10 集中度：{counterpartyData.result.cr10_ratio}
  </span>
)}
```

如果该区域不存在，在对手方列表顶部加一行摘要即可，不需要新建大组件。

---

## Task 6 — 测试

**新建或修改：**
- `frontend/src/test/DashboardCoreMetrics.test.tsx`
- `frontend/src/test/DashboardDailyChanges.test.tsx`

每个测试文件至少覆盖：
1. loading 态渲染
2. 正常数据渲染（用 mock payload）
3. error 态渲染
4. quality_flag warning 时显示角标

参考现有 `DashboardPage.test.tsx` 的 mock 模式。

---

## 最终验证

```bash
cd frontend && npm run test -- src/test/DashboardCoreMetrics.test.tsx src/test/DashboardDailyChanges.test.tsx --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run test -- src/test/DashboardPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
```

---

## 绝对禁止

- 不在前端做金融计算（change_amount / change_pct 由后端返回，前端只展示）
- 不改 `client.ts` 的大结构，只追加方法
- 不重构现有 DashboardPage 的无关部分
- 不碰 bond-analytics、pnl、balance-analysis 等无关页面
- 不引入新的第三方库

---

## 完成后输出格式

```
Implemented Phase 2 gap P0 frontend.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result

Known risks / follow-up:
- ...
```
