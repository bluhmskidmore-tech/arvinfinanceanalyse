# Phase 0: 全局基础设施 — 原子任务

> ⚠️ 本文件基于 2026-04-14 的仓库实际状态编写。
> 每个任务独立可执行，完成后立即 `npm run typecheck` 验证。

## 已有资产（不要重复创建）

以下组件/配置**已经存在**，任何 prompt 不得指示 agent 重新创建：

- ✅ `src/app/providers.tsx` — `ConfigProvider theme={workbenchTheme}` 已挂载
- ✅ `src/components/KpiCard.tsx` — 276 行，支持 sparkline、trend、change、tone、unit
- ✅ `src/components/SectionCard.tsx` — antd Card 封装，支持 loading/error/retry
- ✅ `src/components/FilterBar.tsx` — 顶部筛选行容器
- ✅ `src/components/StatusPill.tsx` — 状态标签（normal/caution/warning/danger）
- ✅ `src/components/AsyncSection.tsx` — loading/error/empty 状态包装
- ✅ `src/theme/theme.ts` — workbenchTheme
- ✅ `src/theme/tokens.ts` — shellTokens
- ✅ `src/features/workbench/components/KpiCard.tsx` — re-export from `src/components/KpiCard`
- ✅ `src/features/executive-dashboard/components/AsyncSection.tsx` — re-export

---

## 任务 0-1: 新增格式化工具函数

**文件**: 新建 `frontend/src/utils/format.ts`

**内容**:
```typescript
const zhNumberFormat = new Intl.NumberFormat("zh-CN");

export function fmtYi(v: number): string {
  return `${zhNumberFormat.format(v)} 亿`;
}

export function fmtBp(v: number): string {
  return `${v.toFixed(1)} bp`;
}

export function fmtPct(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtChange(v: number): string {
  return v > 0 ? `+${zhNumberFormat.format(v)}` : zhNumberFormat.format(v);
}

export function fmtRate(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtCount(v: number, unit = "项"): string {
  return `${v} ${unit}`;
}
```

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 0-2: 新增 CalendarList 共享组件

**文件**: 新建 `frontend/src/components/CalendarList.tsx`

**参考现有组件风格**: 参照 `src/components/StatusPill.tsx` 的 inline style 模式（不用 CSS modules）。

**Props 接口**:
```typescript
export type CalendarItem = {
  date: string;
  event: string;
  amount?: string;
  level: "high" | "medium" | "low";
  note?: string;
};

export type CalendarListProps = {
  items: CalendarItem[];
};
```

**渲染**: 紧凑表格行，每行: date | event | amount | level(StatusPill) | note。level 映射: high→danger, medium→warning, low→normal。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 0-3: 新增 AlertList 共享组件

**文件**: 新建 `frontend/src/components/AlertList.tsx`

**Props**:
```typescript
export type AlertItem = {
  level: "danger" | "warning" | "caution" | "info";
  title: string;
  detail?: string;
  time?: string;
};

export type AlertListProps = {
  items: AlertItem[];
};
```

**渲染**: 每行左侧彩色圆点（8px, level 对应颜色从 StatusPill 的 COLORS 复制），右侧 title + detail + time。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 0-4: 新增 SummaryBlock 共享组件

**文件**: 新建 `frontend/src/components/SummaryBlock.tsx`

**Props**:
```typescript
export type SummaryBlockProps = {
  title: string;
  content: string;
  tags?: { label: string; color?: string }[];
};
```

**渲染**: 标题（14px bold）+ 正文段落（14px, color #31425b, line-height 1.8）+ 底部一排 antd Tag。参照 `shellTokens` 配色。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 0-5: 新增 ECharts 图表封装

**文件**: 新建 `frontend/src/components/charts/BaseChart.tsx`

**说明**: 项目已有 `echarts-for-react` 依赖。封装一个统一的图表容器，处理 loading/empty/resize。

**Props**:
```typescript
import type { EChartsOption } from "echarts";
export type BaseChartProps = {
  option: EChartsOption;
  height?: number;
  loading?: boolean;
};
```

**实现**: `import ReactEChartsCore from "echarts-for-react/lib/core"` 或项目中已有的 echarts 引入方式。检查 `package.json` 确认 echarts 引入方式后再写。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 0-6: 验证导航顺序

**文件**: `frontend/src/mocks/navigation.ts`

**当前顺序**（行 15-258）:
1. dashboard (/) 
2. operations-analysis (/operations-analysis)
3. bond-analysis (/bond-analysis)
4. cross-asset (/cross-asset)
5. team-performance (/team-performance)
6. decision-items (/decision-items)
7. balance-analysis (/balance-analysis)
8. market-data (/market-data)
9. platform-config (/platform-config)
10. reports-center (/reports)
11. bond-dashboard (/bond-dashboard)
12. positions (/positions)
13. risk-overview (/risk-overview)
14. ... 等

**目标顺序（前 10 项）**: 与当前顺序一致。不需要改动。

**但需要确认**: 侧栏是否实际按这个顺序显示？如果 `primaryWorkbenchNavigation`（所有 readiness=live 且非 hidden）直接使用数组顺序，那当前顺序已正确。

**结论**: 如果导航已按预期顺序显示，**跳过此任务**。只在确认顺序不对时才修改。

---

## Phase 0 完成标志

```bash
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

全部通过，且新增文件:
- `src/utils/format.ts`
- `src/components/CalendarList.tsx`
- `src/components/AlertList.tsx`
- `src/components/SummaryBlock.tsx`
- `src/components/charts/BaseChart.tsx`
