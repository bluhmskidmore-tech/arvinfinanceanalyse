# Phase 6: 跨资产驱动页重构 — 原子任务

> 目标文件: `frontend/src/features/cross-asset/pages/CrossAssetPage.tsx` (~608 行)
> 辅助文件: `cross-asset/lib/` 和 `cross-asset/components/`
> Mockup: `.omx/mockups/cross_asset_drivers_hd.png`

## 已有资产

- ✅ `CrossAssetPage.tsx` ~608 行
- ✅ `MiniKpiCard` — 自定义 KPI 卡片（含 sparkline）
- ✅ `CrossAssetSparkline` 组件
- ✅ `resolveCrossAssetKpis` — 从宏观序列解析 KPI
- ✅ `buildCrossAssetTrendOption` — 跨资产走势 ECharts option
- ✅ `buildDriverColumns` / `buildEnvironmentTags` / `driverStanceStyle` — 驱动拆解
- ✅ useQuery: `getChoiceMacroLatest` + `getMacroBondLinkageAnalysis`
- ✅ KPI 行（动态解析，含 sparkline 和变动标签）
- ✅ 市场判断区域（从 `env.signal_description` 获取）
- ✅ 驱动拆解面板（从 environment_score 构建）
- ✅ 跨资产走势图（ECharts）
- ✅ 估值热力图行（硬编码 4 行 mock: 10Y国债/美债/金融条件/布油）
- ✅ 环境标签 (`envTags`)

## 核心差距

这个页面**已经最接近 mockup**。主要差距:
1. 估值热力图只有 4 行硬编码，mockup 有 5+ 行且含"分位"和"可配/拥挤"标签
2. 缺少 **市场候选动作** 列表
3. 缺少 **事件与供给日历** 
4. 缺少 **观察名单** 面板
5. 缺少 **页面输出**（环境标签/方向判断/主要风险/关注窗口）
6. 布局可以更紧凑地匹配 mockup

---

## 任务 6-1: 增强估值热力图

**改什么**: `CrossAssetPage.tsx` 行 130-135 的 `heatmapRows`

**替换为** 更完整的数据（加入 mockup 中的指标）:
```typescript
const heatmapRows = [
  { indicator: "10Y国债收益率", current: "1.94%", pct: "18%", eval: "中性", evalTone: "warning" as const },
  { indicator: "5Y国开-国债", current: "12bp", pct: "72%", eval: "偏贵宜", evalTone: "bull" as const },
  { indicator: "AAA 3Y", current: "45bp", pct: "10%", eval: "偏拥挤", evalTone: "bear" as const },
  { indicator: "1Y AAA存单", current: "28bp", pct: "81%", eval: "可配", evalTone: "bull" as const },
  { indicator: "中美国债利差", current: "-210bp", pct: "5%", eval: "倒挂", evalTone: "bear" as const },
];
```

**验证**: typecheck

---

## 任务 6-2: 新增市场候选动作

**新建文件**: `frontend/src/features/cross-asset/components/MarketCandidateActions.tsx`

**内容**: SectionCard "市场候选动作" + 列表:

| 动作 | 理由 | 触发条件 |
|------|------|---------|
| 🟢 关注 5Y 国债 | 中段中期率优于长端 | 利差回归至 14bp+ |
| 🟡 观察 1Y AAA 存单 | 等待供给落地 | 分位回到 60% 以下 |
| 🔴 暂不追 10Y 长端 | 海外约束+供给压力 | 美债回落至 4.0% |
| 🟡 信用仅做票息 | 利差偏拥挤 | AAA 3Y > 50bp |

每行用颜色圆点 + 文字。

**验证**: typecheck

---

## 任务 6-3: 新增事件与供给日历

**新建文件**: `frontend/src/features/cross-asset/components/CrossAssetEventCalendar.tsx`

**内容**: CalendarList:
- 03-05 国债招标 | 可能压制长端 | 高
- 03-08 同业存单到期集中 | 短期关注 | 中
- 03-10 美国非农 | 影响美债反应 | 高
- 03-12 CPI 数据 | 关注通胀 | 中

**验证**: typecheck

---

## 任务 6-4: 新增观察名单

**新建文件**: `frontend/src/features/cross-asset/components/WatchList.tsx`

**内容**: SectionCard "观察名单" + 紧凑表格:

| 品种 | 当前 | 分位 | 信号 |
|------|------|------|------|
| 5Y 国开 | 分位 74% | 等待供给落地 | 🟡 |
| 1Y AAA 存单 | 分位 81% | 偏高可观察 | 🟢 |
| AA+ 3Y 城投 | 分位 41% | 不宜追涨 | 🔴 |

**验证**: typecheck

---

## 任务 6-5: 新增页面输出面板

**新建文件**: `frontend/src/features/cross-asset/components/PageOutput.tsx`

**内容**: SectionCard "页面输出" + 4 条:
- **环境标签**: 资金偏松 / 外部约束增强 / 长端偏贵
- **方向判断**: 中段优于长端，信用以票息为主
- **主要风险**: 美债继续上行，油价持续抬升
- **关注窗口**: 1Y AAA 存单, 5Y 国开

**验证**: typecheck

---

## 任务 6-6: 整合新组件到页面

**改什么**: `CrossAssetPage.tsx` 的 return 区域

**操作**: 在现有内容的合适位置插入:
1. `MarketCandidateActions` — 驱动拆解面板下方
2. `CrossAssetEventCalendar` — 走势图下方
3. `WatchList` — 与事件日历同行
4. `PageOutput` — 页面底部

每个都 import 并用 SectionCard 或直接渲染。

**验证**: `cd frontend && npm run lint && npm run typecheck && npm run build`

---

## 执行顺序

```
6-1 (热力图) → 6-2 (候选动作) → 6-3 (日历) → 6-4 (观察名单) → 6-5 (页面输出) → 6-6 (整合)
```

## 禁止事项

- ❌ 不要重写 `resolveCrossAssetKpis` 或 `buildCrossAssetTrendOption`
- ❌ 不要删除现有的联动分析面板和相关性卡片
- ❌ 不要重复 Bond Analysis 的内部债市分析内容
- ❌ 不要改变 `cross-asset/lib/` 下的模型文件
