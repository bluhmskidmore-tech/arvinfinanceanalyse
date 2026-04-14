# Phase 2: 驾驶舱页重构 — 原子任务

> 目标文件: `frontend/src/features/workbench/pages/DashboardPage.tsx` (~216 行)
> Hub 组件: `frontend/src/features/workbench/dashboard/FixedIncomeDashboardHub.tsx`
> Mockup: `.omx/mockups/dashboard_overview_hd.png`

## 已有资产

- ✅ `OverviewSection` — KPI 行（从 `/ui/home/overview` 获取数据）
- ✅ `SummarySection` — 全局判断（从 `/ui/home/summary` 获取数据）
- ✅ `AlertsSection` — 预警中心（从 `/ui/home/alerts` 获取数据）
- ✅ `DashboardModuleSnapshot` — 模块快照卡片
- ✅ `DashboardStructureMaturityTeaser` — 结构与期限预览
- ✅ `DashboardTasksAndCalendar` — 待办与日历（mock 数据）
- ✅ 6 个 useQuery 全部已连接
- ✅ `MODULE_ENTRIES` 含 5 个模块入口卡片
- ✅ Lazy-loaded PnlAttributionSection / ContributionSection

## 核心差距

当前页面**结构已接近 mockup**，但内容还不够丰富。与 mockup 对比:
1. KPI 行用的是 `OverviewSection`（后端驱动），需确认其是否输出 mockup 中的 8 个 KPI
2. `DashboardStructureMaturityTeaser` 是否含真实数据或仅占位
3. `MODULE_ENTRIES` 只有 5 项，mockup 显示 4 张大入口卡片（含问答描述）
4. 缺少筛选栏（日期、口径等）

---

## 任务 2-1: 增加顶部 FilterBar

**改什么**: `DashboardPage.tsx` 行 83-131 的 header 区域之后插入

**添加**: 在标题下方、OverviewSection 上方加入 FilterBar:
```tsx
import { FilterBar } from "../../../components/FilterBar";

// 在 return 内、OverviewSection 之前:
<FilterBar style={{ marginBottom: 20 }}>
  <label>
    <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>区间</span>
    <select style={controlStyle} disabled><option>金融市场条线</option></select>
  </label>
  <label>
    <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>口径</span>
    <select style={controlStyle}><option>摊余成本</option></select>
  </label>
  <label>
    <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>币种</span>
    <select style={controlStyle}><option>全部</option></select>
  </label>
  <label>
    <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>部门</span>
    <select style={controlStyle}><option>全部</option></select>
  </label>
</FilterBar>
```

添加 controlStyle 常量（同 BalanceAnalysisPage 中的样式）。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json`

---

## 任务 2-2: 增强模块联动入口卡片

**改什么**: `FixedIncomeDashboardHub.tsx` 中的 `MODULE_ENTRIES` (行 19-55)

**当前**: 5 个简单条目（key/to/title/blurb）

**替换为** 4 张大卡片格式，每张含"回答什么"和"输出什么":
```typescript
const MODULE_ENTRIES = [
  {
    key: "bond-analysis",
    to: "/bond-analysis",
    title: "债券分析",
    question: "利率、曲线、信用利差怎么走，组合该买卖什么？",
    output: "中段优于长端，信用以票息为主",
  },
  {
    key: "cross-asset",
    to: "/cross-asset",
    title: "跨资产驱动",
    question: "中美利率、原油、A股、商品对债券定价怎么传导？",
    output: "外部约束增强 / 风险偏好趋于稳定",
  },
  {
    key: "balance-analysis",
    to: "/balance-analysis",
    title: "资产负债分析",
    question: "期限缺口、成本压力、滚续安排、风险指标？",
    output: "1年内缺口 -373.0 亿 / 浮盈 68.5 亿",
  },
  {
    key: "market-data",
    to: "/market-data",
    title: "市场数据",
    question: "现券、资金、期货、存单和信用成交在盘中怎么变化？",
    output: "DR007 1.82% / AAA 3Y 45bp / 10Y 国债 1.94%",
  },
];
```

对应渲染区域也要更新：每张卡片显示 question + output + "进入 →" 链接。

**验证**: typecheck + 浏览器确认 4 张大卡片可见

---

## 任务 2-3: 精简标题

**改什么**: 行 94-115

**当前**: 标题 fontSize 34，有一段描述文字

**替换为**: 标题 fontSize 24, 删除描述段落（mockup 中没有大段描述文字）:
```tsx
<h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>驾驶舱</h1>
<p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>
  报期 2026-03-01
</p>
```

**验证**: typecheck

---

## 任务 2-4: 将"扩展视图"标题改为更业务化的名称

**改什么**: 行 177-179

**当前**: "扩展视图" + "管理层损益归因、风险信号与贡献分解..."

**替换为**: "收益归因与风险分解" + 删除描述段落

**验证**: typecheck

---

## 执行顺序

```
2-3 (标题) → 2-1 (FilterBar) → 2-2 (入口卡片) → 2-4 (区块标题)
```

全部完成后: `cd frontend && npm run lint && npm run typecheck && npm run build`
