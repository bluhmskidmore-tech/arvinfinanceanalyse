# Phase 5: 经营分析页重构 — 原子任务

> 目标文件: `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx` (~681 行)
> Mockup: `.omx/mockups/business_analysis_hd.png`

## 已有资产

- ✅ 标题 "经营分析"，副标题 "资产负债正式读面速览 · 数据源与宏观观测"
- ✅ 多路 useQuery: sourcePreview, macroCatalog, macroLatest, fxFormalStatus, choiceNews, balanceDates, balanceOverview
- ✅ KpiCard 行 — 显示余额分析的 overview 数据
- ✅ 源预览摘要表
- ✅ 宏观目录展示
- ✅ FX 正式状态/缺失报告
- ✅ Choice 新闻展示
- ✅ PnL 刷新按钮
- ✅ 余额分析 overview 速览 + 跳转到余额分析页的链接

## 核心差距

当前页面是**运维/数据源**视角（源预览、宏观目录、FX 状态），与 mockup 的**经营管理**视角差距很大:
1. 缺少 **本期经营结论**叙述
2. 缺少 **收益成本桥（瀑布图）**
3. 缺少 **经营质量观察**（状态标签面板）
4. 缺少 **资产/负债经营贡献表**
5. 缺少 **期限与集中度**
6. 缺少 **管理输出**面板
7. 现有 KPI 不是 mockup 中的 8 个经营 KPI

**策略**: 现有数据源/运维模块保留（可折叠），在页面上方新增经营分析模块。

---

## 任务 5-1: 替换/增强 KPI 行为经营 KPI

**改什么**: 找到现有 KpiCard 区域

**替换为** 8 个经营 KPI (mock):
```tsx
<KpiCard label="市场资产" value="3,525.0" unit="亿" detail="债券+买入" />
<KpiCard label="市场负债" value="1,817.9" unit="亿" detail="发行+买入" />
<KpiCard label="静态资产收益率" value="2.07%" detail="加权到期" />
<KpiCard label="静态负债成本" value="1.77%" detail="当期加权" />
<KpiCard label="静态利差" value="29.5" unit="bp" detail="资产收益-负债成本" />
<KpiCard label="净经营贡献" value="40.65" unit="亿" detail="静态年化口径" />
<KpiCard label="发行负债占比" value="66.3%" detail="CD占发行 81.8%" />
<KpiCard label="重大关注" value="4" unit="项" status="warning" detail="缺口/滚续/集中度" />
```

保留现有 balanceOverview 数据驱动的 KPI 作为备选（后续接 API 时切换）。

**验证**: typecheck

---

## 任务 5-2: 新增经营结论组件

**新建文件**: `frontend/src/features/workbench/business-analysis/BusinessConclusion.tsx`

**内容**: `SummaryBlock`:
- 正文: "从当前两张台账口径看，经营结果仍由债券资产配置与票息收入主导..."
- Tags: `收益质量:稳定`, `负债结构:偏短`, `短端滚续:压力`, `预警`

**验证**: typecheck

---

## 任务 5-3: 新增收益成本桥（瀑布图）

**新建文件**: `frontend/src/features/workbench/business-analysis/RevenueCostBridge.tsx`

**内容**: ECharts 瀑布图 (用 bar + stack 实现):

| 项目 | 金额(亿) |
|------|----------|
| 债券资产收益 | +68.56 |
| 同业资产收益 | +4.31 |
| (合计资产) | (+72.87) |
| 发行负债成本 | -22.11 |
| 同业负债成本 | -9.11 |
| 净经营贡献 | = 40.65 |

注释: "净利差 29.5bp，净经营贡献主要来源于债券资产"

**验证**: typecheck + 浏览器可见瀑布图

---

## 任务 5-4: 新增经营质量观察

**新建文件**: `frontend/src/features/workbench/business-analysis/QualityObservation.tsx`

**内容**: 指标列表 + StatusPill:

| 指标 | 当前值 | 状态 |
|------|--------|------|
| 资产/负债比 | 1.94x | normal |
| 发行负债集中度 | 81.8% | caution |
| 短期负债占比 | 72.6% | warning |
| 1年内缺口/负债 | 20.5% | caution |
| 异常资产占比 | 0.21% | normal |

**验证**: typecheck

---

## 任务 5-5: 新增管理输出面板

**新建文件**: `frontend/src/features/workbench/business-analysis/ManagementOutput.tsx`

**内容**: SectionCard 内 4 条:
- **经营判断**: 收益仍由债券票息主导，利差不厚但相对稳定。
- **核心矛盾**: 负债对发行类工具依赖度高，短端滚续压力偏大。
- **当前优先级**: 先管缺口和滚续，再谋进一步提升收益。
- **下钻方向**: 资产负债分析看缺口，债券分析看利差，市场数据看盘中变化。

每条标题加粗，内容为正文。

**验证**: typecheck

---

## 任务 5-6: 页面布局重组

**改什么**: `OperationsAnalysisPage.tsx` 的 return 区域

**目标布局**:
```
[标题: 经营分析 | 筛选栏]
[8 个经营 KPI]
[经营结论 | 收益成本桥 | 经营质量观察]
[贡献表(复用余额API) | 关注事项 | 经营日历]
[期限与集中度 | 管理输出]
--- Collapse: 数据源与运维 ---
[现有的源预览、宏观目录、FX 状态、新闻模块 — 全部折叠]
```

**操作**:
1. 在 KPI 下方插入任务 5-2~5-5 的组件
2. 将现有数据源/运维模块用 antd `<Collapse>` 包裹，默认收起，标题 "数据源与运维状态"
3. 标题精简: 删除副标题 "资产负债正式读面速览 · 数据源与宏观观测"
4. 关注事项和经营日历可复用 `AlertList` 和 `CalendarList` + mock 数据

**验证**: `cd frontend && npm run lint && npm run typecheck && npm run build`

---

## 执行顺序

```
5-1 (KPI) → 5-2 (结论) → 5-3 (瀑布图) → 5-4 (质量观察) → 5-5 (管理输出) → 5-6 (布局重组)
```

## 禁止事项

- ❌ 不要删除现有的源预览/宏观/FX/新闻模块（折叠保留）
- ❌ 不要伪造预算完成率、资本占用等无来源指标
- ❌ 不要重复 Dashboard 的"总览"内容
