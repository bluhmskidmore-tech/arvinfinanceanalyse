# Phase 0: 全局基础设施

> 前置阶段，必须在任何页面重构之前完成。
> 主规格文档: `docs/moss-fixed-income-platform-spec.md`
> Mockup 参考: `.omx/mockups/*.png`

## 目标

建立统一的设计基础设施和通用组件库，让后续 6 个页面的重构有一致的底座。

## 必须完成的任务

### 1. 挂载 workbenchTheme 到 ConfigProvider

**现状**: `src/theme/theme.ts` 导出了 `workbenchTheme`（antd ThemeConfig），但 `src/app/App.tsx` 和 `src/main.tsx` 均未使用 `ConfigProvider`。antd 组件使用默认主题。

**要求**:
- 在 `src/app/App.tsx` 或 `src/main.tsx` 的 `AppProviders` 中包裹 `<ConfigProvider theme={workbenchTheme}>`
- 确保不破坏现有页面的视觉效果
- 运行 `npm run build` 验证无类型错误

**涉及文件**:
- `src/app/App.tsx`
- `src/main.tsx`
- `src/theme/theme.ts`（只读参考）
- `src/theme/tokens.ts`（只读参考）

### 2. 创建通用组件目录并抽出/新建共享组件

**现状**: 无顶层 `src/shared` 或 `src/components` 目录。复用组件散落在：
- `src/features/workbench/components/KpiCard.tsx`
- `src/features/workbench/components/PlaceholderCard.tsx`
- `src/features/executive-dashboard/components/AsyncSection.tsx`

**要求**:
- 创建 `src/components/` 目录作为共享组件库
- 将以下组件从 feature 目录移动或创建新版本到 `src/components/`，保留旧位置的 re-export 以避免破坏现有 import:

| 组件 | 来源 | 动作 |
|------|------|------|
| `KpiCard` | `workbench/components/KpiCard.tsx` | 增强（支持 sparkline、趋势箭头、变动值） |
| `AsyncSection` | `executive-dashboard/components/AsyncSection.tsx` | 移入共享，保留 re-export |
| `SectionCard` | 新建 | 统一的内容区块卡片（标题+操作栏+内容） |
| `StatusPill` | 新建 | 状态标签（正常/关注/预警/危险），统一颜色 |
| `DenseTable` | 新建 | 高密度表格封装（基于 antd Table，紧凑行高） |
| `FilterBar` | 新建 | 页面顶部筛选条（日期、口径、币种等 slot 式组合） |
| `GapBar` | 新建 | 期限缺口条形图组件（正值/负值双向条） |
| `CalendarList` | 新建 | 事件日历列表（日期+事件+级别标签） |
| `AlertList` | 新建 | 预警列表（图标+文字+级别） |
| `CandidateActionList` | 新建 | 候选动作列表（动作+说明+状态） |
| `SummaryBlock` | 新建 | 叙述性摘要区块（标题+正文+关键词高亮标签） |
| `CurveChart` | 新建 | ECharts 曲线图封装（收益率曲线等） |
| `WaterfallChart` | 新建 | ECharts 瀑布图封装（收益成本桥等） |
| `HeatmapTable` | 新建 | 估值/分位热力表（值+颜色+百分位） |

**KpiCard 增强规格**:
```typescript
interface KpiCardProps {
  label: string;
  value: string | number;
  unit?: string;            // "亿" | "bp" | "%" 等
  change?: number;          // 变动值
  changeLabel?: string;     // "较上期" 等
  trend?: "up" | "down" | "flat";
  sparklineData?: number[]; // 迷你趋势线数据
  status?: "normal" | "warning" | "danger";
  onClick?: () => void;
}
```

**SectionCard 规格**:
```typescript
interface SectionCardProps {
  title: string;
  extra?: React.ReactNode;  // 右上角操作区
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  children: React.ReactNode;
  noPadding?: boolean;       // 表格类内容不需要内边距
}
```

**StatusPill 规格**:
```typescript
interface StatusPillProps {
  status: "normal" | "caution" | "warning" | "danger";
  label: string;
}
// 颜色映射: normal=#52c41a, caution=#faad14, warning=#fa8c16, danger=#f5222d
```

### 3. 统一数字格式化工具

**要求**: 创建 `src/utils/format.ts`（如已有类似文件则增强）:
```typescript
formatYi(value: number): string        // 3525.0 → "3,525.0 亿"
formatBp(value: number): string        // 29.5 → "29.5 bp"
formatPct(value: number): string       // 2.07 → "2.07%"
formatChange(value: number): string    // +68.48 → "+68.48" / -373.0 → "-373.0"
formatRate(value: number): string      // 1.94 → "1.94%"
formatCount(value: number): string     // 4 → "4 项"
```

### 4. 导航顺序调整

**现状**: `src/mocks/navigation.ts` 中 `workbenchNavigation` 数组的顺序和项目。

**目标顺序**:
1. 驾驶舱 (`/` 或 `/dashboard`)
2. 经营分析 (`/business-analysis`)
3. 债券分析 (`/bond-analysis`)
4. 跨资产驱动 (`/cross-asset-drivers`)
5. 团队绩效 (`/team-performance`) — 保持现有
6. 决策事项 (`/decision-items`) — 保持现有或占位
7. 资产负债分析 (`/asset-liability-analysis`)
8. 市场数据 (`/market-data`)
9. 中台配置 (`/platform-config`) — 保持现有
10. 报表中心 (`/reports`) — 占位

**要求**:
- 调整 `workbenchNavigation` 数组顺序
- 6 个目标页面标记为 `readiness: "live"`
- 其他项根据现有状态保持，无实际页面的标 `"placeholder"`
- 确保 `routes.tsx` 的 `buildWorkbenchChildRoutes()` 能正确映射
- 如需新增路由项（如 `/business-analysis` 目前可能不存在），在 `routes.tsx` 中添加对应的 lazy import

**涉及文件**:
- `src/mocks/navigation.ts`
- `src/router/routes.tsx`

### 5. Mock 模式标识组件

**要求**: 创建一个小的浮动标识，当 `VITE_DATA_SOURCE !== "real"` 时在页面右下角显示 "Mock Mode"，让用户知道当前看到的是模拟数据。

**涉及文件**:
- `src/app/App.tsx` 或 `src/layouts/WorkbenchShell.tsx`

## 验证

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

所有必须通过。如果现有测试因导航顺序变化而失败，修复测试中的硬编码顺序断言。

## 禁止事项

- 不要修改任何页面级组件的业务逻辑
- 不要引入新的 npm 依赖（antd, echarts, ag-grid 已有）
- 不要改变 WorkbenchShell 的整体布局结构
- 不要删除任何现有组件
