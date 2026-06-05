# Phase 1: 资产负债分析页重构 — 原子任务

> ⚠️ 基于 2026-04-14 仓库实际代码编写。每个任务独立执行+验证。
> 目标文件: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` (~2243 行)
> Mockup: `.omx/mockups/asset_liability_analysis_hd.png`
> 前置: Phase 0 完成

## 真实现状摘要（不要与此矛盾）

以下功能**已经存在**，不需要新增 API 调用或类型：

- ✅ `basisBreakdownQuery` 已连接 `client.getBalanceAnalysisSummaryByBasis` (行 1271-1288)
- ✅ `advancedAttributionQuery` 已连接 `client.getBalanceAnalysisAdvancedAttribution` (行 1290-1298)
- ✅ `BalanceAnalysisBasisBreakdownRow` 类型已在 contracts.ts 中定义并被 import (行 10)
- ✅ Detail 的 `summary[]` 已被渲染为 AG Grid (行 1821-1840)
- ✅ `decisionStatusComment` 已传入 `updateBalanceAnalysisDecisionStatus` (行 1445)
- ✅ Workbook cards/panels/right rail 全部已接通
- ✅ FilterBar, KpiCard, SectionCard, AsyncSection 已存在于 `src/components/`

**核心问题**: 页面所有数据链路已通，但**展示是开发者视角而非业务用户视角**：
- KPI 卡片显示"明细行数""汇总分组"而非"市场资产""静态利差"
- 页面副标题写的是"第一张 governed balance-analysis consumer"
- Result Meta 大段开发调试信息直接暴露
- 缺少 mockup 中的关键业务模块（收益成本分解图、风险全景、期限结构图、风险指标面板）
- 整体布局未按 mockup 的 4 行多列 grid 排列

---

## 任务 1-1: 替换 KPI 卡片为业务指标

**改什么**: `BalanceAnalysisPage.tsx` 行 1601-1629 的 5 个 KpiCard

**当前**:
```tsx
<KpiCard title="明细行数" value={String(overview?.detail_row_count ?? 0)} ... />
<KpiCard title="汇总分组" value={String(overview?.summary_row_count ?? 0)} ... />
<KpiCard title="总规模" value={String(overview?.total_market_value_amount ?? "0.00")} ... />
<KpiCard title="摊余成本" value={String(overview?.total_amortized_cost_amount ?? "0.00")} ... />
<KpiCard title="应计利息" value={String(overview?.total_accrued_interest_amount ?? "0.00")} ... />
```

**替换为** 8 个业务 KPI（数据暂用 mock 常量，后续接真实 API）:

在文件顶部 import 区域后，新增 mock 常量:
```typescript
const BALANCE_MOCK_KPI = {
  marketAssetsYi: 3525.0,
  marketLiabilitiesYi: 1817.9,
  assetYieldPct: 2.07,
  liabilityCostPct: 1.77,
  staticSpreadBp: 29.5,
  oneYearGapYi: -373.0,
  bondFloatingGainYi: 68.48,
  alertCount: 4,
};
```

替换 KpiCard 区域为:
```tsx
<KpiCard label="市场资产" value="3,525.0" unit="亿" detail="债券+买入" />
<KpiCard label="市场负债" value="1,817.9" unit="亿" detail="发行+买入" />
<KpiCard label="静态资产收益率" value="2.07%" detail="加权到期" />
<KpiCard label="静态负债成本" value="1.77%" detail="当期加权" />
<KpiCard label="静态利差" value="29.5" unit="bp" detail="资产收益-负债成本" />
<KpiCard label="1年内净缺口" value="-373.0" unit="亿" tone="negative" detail="短端缺口" />
<KpiCard label="债券资产浮盈" value="+68.48" unit="亿" tone="positive" detail="公允-摊余" />
<KpiCard label="异常预警" value="4" unit="项" status="warning" detail="缺口/滚续/集中度" />
```

同时把 `gridTemplateColumns` 从 `repeat(auto-fit, minmax(220px, 1fr))` 改为 `repeat(auto-fill, minmax(160px, 1fr))` 以适应 8 张卡片。

**验证**: `npx tsc --noEmit -p frontend/tsconfig.json` + 浏览器打开页面确认 8 张 KPI 可见

---

## 任务 1-2: 替换页面标题和副标题

**改什么**: 行 1502-1526

**当前**:
```tsx
<h1 ...>资产负债分析</h1>
<p ...>第一张 governed balance-analysis consumer。页面只消费 formal facts，不读取 preview 或 snapshot。</p>
```

**替换为**:
```tsx
<h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>资产负债分析</h1>
```

删除 `<p>` 副标题。标题字号从 32 降到 24（mockup 中标题不那么大）。

**验证**: typecheck

---

## 任务 1-3: 在 KPI 下方新增业务摘要行

**改什么**: 在 KPI cards `</div>`（约行 1629）之后、`data-testid="balance-analysis-supplemental-panels"` 之前插入。

**新增组件文件**: `frontend/src/features/balance-analysis/components/BalanceSummaryRow.tsx`

**内容**: 一个 3 列 grid:

第 1 列 — **本期资产负债摘要** (SummaryBlock):
```
资产以债券投资为主，占市场资产 93.3%；中长端配置偏稳，资产收益率 2.07%。
负债以发行类债务为主，占市场负债 66.3%；其中国金存单占发行 81.8%。
1年内净缺口 -373.0 亿，91天-1年缺口最大；需回购补量关注滚续节奏与成本。
```
Tags: `资产特征`, `负债特征`, `缺口压力`

第 2 列 — **收益成本分配（静态口径）**: 一个水平 bar chart (ECharts)
- 债券投资 +23.11
- 同业资产 +X
- 发行负债 -X
- 同业负债 -X
- 净值: +XX

第 3 列 — **风险全景**: 一个简单的 5 行表格
- 期限错配 | 偏高 | 中性 | 压力测试
- 流动性压力 | 中性 | ... 
- 负债滚续 | 偏高 | ...
- 对手方集中度 | 中性 | ...
- 异常资产 | 低 | ...
每格用背景色表示风险等级（绿/黄/红）

**在 BalanceAnalysisPage.tsx 中**: 在 KPI div 后面加一行 `<BalanceSummaryRow />`

**验证**: typecheck + 浏览器可见 3 列

---

## 任务 1-4: 在摘要行下方新增贡献表+关注事项+预警行

**新增组件文件**: `frontend/src/features/balance-analysis/components/BalanceContributionRow.tsx`

**内容**: 3 列 grid:

第 1 列 — **资产/负债/缺口贡献**: AG Grid 表格
- 列: 项目 | 市场余额 | 占比 | 负债余额 | 占比 | 净缺口
- 行: 债券投资, 同业资产, 发行负债, 同业负债, 合计
- 底行红色标注: 1年内净缺口, 1-3年净缺口, 3年以上净缺口
- 数据来源: mock (后续接 `overview` 或 `basisBreakdown` API)

第 2 列 — **待关注事项**: 使用 AlertList 组件
- 4月短端缺口压力较大（danger）
- 发行负债集中度偏高（warning）
- 短端缺口已覆盖率 81.8%（caution）
- 异常资产跟踪（info）

第 3 列 — **预警与事件**: 使用 AlertList 组件
- 短端缺口预警 10:15（danger）
- 03-02 大额到期 09:20（warning）
- 发行负债滚续敏感 09:05（caution）
- 异常资产跟踪 06:50（info）

**在 BalanceAnalysisPage.tsx 中**: 在 `<BalanceSummaryRow />` 后面加 `<BalanceContributionRow />`

**验证**: typecheck + 浏览器可见

---

## 任务 1-5: 新增底部行 — 期限结构 + 风险指标 + 关键日历

**新增组件文件**: `frontend/src/features/balance-analysis/components/BalanceBottomRow.tsx`

**内容**: 3 列 grid:

第 1 列 — **期限结构（资产/负债/净缺口）**: ECharts 柱状图
- X 轴: 7天内, 8-30天, 31-90天, 91天-1年, 1-3年, 3-5年, 5年以上, 无固定到期
- 3 组柱: 资产(蓝), 负债(红), 净缺口(正绿负橙)
- 数据: mock

第 2 列 — **风险指标**: 简洁指标列表
- 资产/负债比 1.94x
- 短期负债占比 72.6%
- 发行负债集中度 81.8%
- 异常资产占比 0.21%
- 浮盈覆盖率 18.4%

第 3 列 — **关键日历（负债到期关注）**: 使用 CalendarList
- 6 条 mock 数据

**在 BalanceAnalysisPage.tsx 中**: 在 `<BalanceContributionRow />` 后面加 `<BalanceBottomRow />`

**验证**: typecheck + 浏览器可见

---

## 任务 1-6: 将 result meta 移入可折叠区域

**改什么**: 行 1695-1737 的 result meta 区域

**操作**: 用 antd `<Collapse>` 包裹，默认收起，标题为"开发调试: Result Meta"

```tsx
import { Collapse } from "antd";
// ...
{resultMetaSections.length > 0 && (
  <Collapse
    items={[{
      key: "result-meta",
      label: "开发调试: Result Meta",
      children: (
        <section style={resultMetaGridStyle}>
          {/* 现有 resultMetaSections.map 内容不变 */}
        </section>
      ),
    }]}
    style={{ marginTop: 20 }}
  />
)}
```

**验证**: typecheck + 浏览器确认默认收起

---

## 任务 1-7: 调整现有区块标题为中文业务标题

**改什么**:

1. 行 1636: `title="按会计口径分解（summary-by-basis）"` → `title="按会计口径分解"`
2. 行 1658: `title="高阶归因（试点）"` → `title="高阶归因"`
3. 行 1756: `title="债券/组合汇总表现"` → `title="资产负债汇总"`
4. 行 1877: `title="Excel 参考模块"` → `title="工作簿与分析面板"`
5. 各 badge 文案: "Excel 映射" → "数据来源", "二级驾驶舱" → "分析视图", "Governed rail" → "治理事项"

**验证**: typecheck

---

## 任务 1-8: 整体布局重排

**改什么**: 整个 return 区域的布局结构

**目标布局**（参照 mockup）:
```
[筛选栏]
[8 个 KPI 卡片]
[摘要 | 收益成本分解 | 风险全景]        ← 任务 1-3
[贡献表 | 待关注事项 | 预警与事件]      ← 任务 1-4
[期限结构 | 风险指标 | 关键日历]        ← 任务 1-5
[按会计口径分解 | 高阶归因]            ← 已有 SectionCard
[汇总表 + 明细表]                      ← 已有 AsyncSection
[工作簿面板 + 右侧决策轨]              ← 已有
[Result Meta (折叠)]                   ← 任务 1-6
```

**具体操作**: 将任务 1-3/1-4/1-5 新增的组件插入正确位置。将已有的 `balance-analysis-supplemental-panels` div 移到 3 行新组件之后。

**每个 3 列行使用相同的 grid 样式**:
```typescript
const threeColumnGridStyle = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr 1fr",
  gap: 16,
  marginTop: 20,
} as const;
```

在 ≤1366px 时可退化为 `gridTemplateColumns: "1fr"`。

**验证**: typecheck + 浏览器打开对比 mockup

---

## 执行顺序

```
1-2 (标题) → 1-1 (KPI) → 1-3 (摘要行) → 1-4 (贡献行) → 1-5 (底部行) → 1-7 (标题改名) → 1-6 (meta折叠) → 1-8 (布局重排)
```

每个任务完成后: `npx tsc --noEmit -p frontend/tsconfig.json`
全部完成后: `cd frontend && npm run lint && npm run build`

---

## 禁止事项

- ❌ 不要新增 API client 方法（已全部存在）
- ❌ 不要新增 contracts 类型（已全部存在）
- ❌ 不要修改 `src/api/client.ts` 或 `src/api/contracts.ts`
- ❌ 不要删除任何现有 useQuery 调用
- ❌ 不要删除现有的 AG Grid 表格（可以改列定义但不要删表）
- ❌ 不要把新组件都写在 BalanceAnalysisPage.tsx 里（每个模块独立文件）
- ❌ 不要引入 `recharts`, `d3`, `chart.js` 等新图表库（用现有 echarts）
