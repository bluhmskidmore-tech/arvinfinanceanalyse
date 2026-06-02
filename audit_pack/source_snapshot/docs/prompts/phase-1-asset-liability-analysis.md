# Phase 1: 资产负债分析页重构（第一优先级）

> 前置依赖: Phase 0 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 5 项
> Mockup: `.omx/mockups/asset_liability_analysis_hd.png`
> 差距分析: `.omx/specs/deep-interview-frontend-display.md`

## 目标

将现有 `BalanceAnalysisPage.tsx`（~2000 行）增量重构到 mockup 所示的专业分析工作台水平。

## 现状快照

**现有文件**: `src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
**导出**: `export default function BalanceAnalysisPage`

### 已接通的 API（保持不变）
- `getBalanceAnalysisDates` → 日期列表 ✅
- `getBalanceAnalysisOverview` → KPI 概览 ✅
- `getBalanceAnalysisSummary` → 分页汇总表 ✅
- `getBalanceAnalysisDetail` → 明细数据 ✅
- `getBalanceAnalysisWorkbook` → 工作簿（卡片+表+运营段） ✅
- `getBalanceAnalysisDecisionItems` → 决策项 ✅
- `updateBalanceAnalysisDecisionStatus` → 决策状态更新 ✅
- `getBalanceAnalysisCurrentUser` → 当前用户 ✅
- `refreshBalanceAnalysis` / `getBalanceAnalysisRefreshStatus` ✅
- `exportBalanceAnalysisSummaryCsv` / `exportBalanceAnalysisWorkbookXlsx` ✅

### 完全未接入的 API（需新增）
- ❌ `GET /ui/balance-analysis/summary-by-basis` — 无 client 方法、无类型、无 UI
- ❌ `GET /ui/balance-analysis/advanced-attribution` — 无 client 方法、无类型、无 UI

### 已接但展示不足的数据
- ❌ Detail 返回的 `summary[]` 未渲染
- ❌ 明细表缺字段: `amortized_cost_amount`, `report_date`, `is_issuance_like`
- ❌ 汇总表缺字段: `display_name`, `row_key`, `position_scope`, `currency_basis`
- ❌ Workbook 主面板只用了子集字段，`weighted_rate_pct`, `weighted_term_years`, `floating_pnl_amount` 等被忽略
- ❌ 决策状态更新未传 `comment` 字段
- ❌ KPI 文案 `summary_row_count` 说明不准确

## 实施步骤

### Step 1: 新增 API 类型和 Client 方法

**在 `src/api/contracts.ts` 中新增**:
```typescript
export interface BalanceAnalysisBasisBreakdownRow {
  source_family: string;
  invest_type_std: string;
  accounting_basis: string;
  position_scope: string;
  currency_basis: string;
  detail_row_count: number;
  market_value_amount: number;
  amortized_cost_amount: number;
  accrued_interest_amount: number;
}

export interface BalanceAnalysisBasisBreakdownPayload {
  report_date: string;
  position_scope: string;
  currency_basis: string;
  rows: BalanceAnalysisBasisBreakdownRow[];
}

export interface AdvancedAttributionBundlePayload {
  report_date: string;
  mode: string;
  scenario_name: string;
  scenario_inputs: Record<string, unknown>;
  upstream_summaries: Record<string, unknown>;
  status: string; // 通常为 "not_ready"
  missing_inputs: string[];
  blocked_components: string[];
  warnings: string[];
}
```

**在 `src/api/client.ts` 中新增方法**（mock 和 real 两侧都要加）:
```typescript
// real client
getBalanceAnalysisSummaryByBasis(params: {
  report_date: string;
  position_scope: string;
  currency_basis: string;
}): Promise<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>>

getBalanceAnalysisAdvancedAttribution(params: {
  report_date: string;
  position_scope?: string;
  currency_basis?: string;
}): Promise<ApiEnvelope<AdvancedAttributionBundlePayload>>

// mock client: 返回合理的静态 mock 数据
```

### Step 2: 拆分 BalanceAnalysisPage 为子组件

当前页面 ~2000 行，必须拆分。建议目录结构:
```
src/features/balance-analysis/
├── pages/
│   └── BalanceAnalysisPage.tsx          # 主页面（精简为布局编排+数据获取）
├── components/
│   ├── BalanceKpiRow.tsx                # 顶部 KPI 卡片行
│   ├── BalanceSummaryNarrative.tsx      # 摘要叙述区（资产特征、负债特征、关键问题）
│   ├── RevenueCostBreakdown.tsx         # 收益成本分解（静态口径）— 瀑布图或表格
│   ├── RiskPanorama.tsx                 # 风险全景面板
│   ├── AssetLiabilityContribution.tsx   # 资产/负债/缺口贡献表
│   ├── AttentionItems.tsx              # 待关注事项
│   ├── AlertsAndEvents.tsx            # 预警与事件
│   ├── MaturityStructureChart.tsx      # 期限结构图（资产/负债/净缺口 by 期限桶）
│   ├── RiskMetricsPanel.tsx           # 风险指标面板
│   ├── KeyCalendar.tsx                # 关键日历
│   ├── BasisBreakdownTable.tsx        # 按会计口径分解表（新 API）
│   ├── AdvancedAttributionPanel.tsx   # 高阶归因面板（新 API，可能显示 not_ready）
│   ├── BalanceWorkbookSection.tsx     # 工作簿区域（从主文件提取）
│   └── BalanceDecisionPanel.tsx       # 决策事项面板（从主文件提取）
├── hooks/
│   └── useBalanceAnalysisQueries.ts   # 集中管理所有 useQuery 调用
├── types/
│   └── viewModels.ts                  # 页面级 view model 类型
└── mocks/
    └── balanceAnalysisMock.ts         # 页面级 mock 数据（seed values）
```

### Step 3: 按 Mockup 实现各模块

参照 `.omx/mockups/asset_liability_analysis_hd.png`:

**顶部: 筛选栏**
- 日期选择（现有 `<select>` → 改为 `FilterBar` 组件）
- 口径: 摊余成本 / 市值（现有）
- 币种: 全部 / CNY（现有）
- 组合: 全部（现有）
- 右侧: 管理员角色标识、刷新、导出

**第一行: KPI 卡片行（8 张）**
使用增强后的 `KpiCard`:
1. 市场资产 — `3,525.0 亿`（债券+买入）
2. 市场负债 — `1,817.9 亿`（发行+买入）
3. 静态资产收益率 — `2.07%`
4. 静态负债成本 — `1.77%`（当期加权）
5. 静态利差 — `29.5 bp`（资产收益-负债成本）
6. 1年内净缺口 — `-373.0 亿`（短端缺口）
7. 债券资产浮盈 — `+68.48 亿`（公允-摊余）
8. 异常预警 — `4 项`（缺口/滚续/集中度）

**第二行左: 本期资产负债摘要** (`SummaryBlock`)
- 资产特征: "资产以债券投资为主，占市场资产 93.3%；中长端配置偏稳..."
- 负债特征: "负债以发行类债务为主，占市场负债 66.3%；其中国金存单..."
- 关键问题: "1年内净缺口 -373.0 亿，91天-1年缺口最大..."
- 关键词标签（用 antd Tag）: 资产特征, 负债特征, 缺口压力

**第二行中: 收益成本分配（静态口径）** (`RevenueCostBreakdown`)
- 使用 `WaterfallChart` 或等价 bar chart
- 债券投资收益, 同业资产收益, 发行负债成本, 同业负债成本, 净经营贡献

**第二行右: 风险全景** (`RiskPanorama`)
- 矩阵式布局，行: 各风险维度，列: 当前/短期/中期
- 期限错配、流动性压力、负债滚续、对手方集中度、异常资产
- 每格用颜色编码（绿/黄/红）

**第三行左: 资产/负债/缺口贡献** (`AssetLiabilityContribution`)
- AG Grid 表格，支持行分组
- 列: 项目, 市场余额, 占比, 负债余额, 占比, 净缺口
- Tab 切换: 投资资产大类 / 负债大类 / 按期限桶查看
- 底行小计: 1年内净缺口, 1-3年净缺口, 3年以上净缺口

**第三行中: 待关注事项** (`AttentionItems`)
- 红点列表: 4月短端缺口压力较大, 发行负债集中度偏高, 短端缺口已覆盖率 81.8%...
- 每项前有状态圆点（红/黄/绿）

**第三行右: 预警与事件** (`AlertsAndEvents`)
- 红色圆点: 短端缺口预警
- 橙色圆点: 03-02 大额到期
- 黄色圆点: 发行负债滚续敏感
- 绿色圆点: 异常资产跟踪
- 每项有时间标注

**第四行左: 期限结构（资产/负债/净缺口）** (`MaturityStructureChart`)
- ECharts 柱状图，X 轴: 7天内, 8-30天, 31-90天, 91天-1年, 1-3年, 3-5年, 5年以上, 无固定到期
- 三组柱: 资产（蓝）, 负债（红）, 净缺口（正绿负橙）
- 下方注释: 净缺口数值

**第四行中: 风险指标** (`RiskMetricsPanel`)
- 简洁指标表:
  - 资产/负债比: 1.94x
  - 短期负债占比: 72.6%
  - 发行负债集中度: 81.8%
  - 异常资产占比: 0.21%
  - 浮盈覆盖率: 18.4%
  - 净盈/1年内缺口

**第四行右: 关键日历（负债到期关注）** (`KeyCalendar`)
- 表格: 日期 | 事件 | 金额 | 级别标签(高/中/低) | 说明
- 使用 `CalendarList` 组件

### Step 4: 交互层次 C 实现

**固定筛选器（FilterBar）**:
- 报告日期、持仓口径（zqtz/tyw/全部）、币种（CNY/原币/全部）、组合
- 筛选器变化 → 所有 useQuery 参数联动刷新

**表格内下钻（AG Grid）**:
- 汇总表启用 Row Grouping（按 `source_family` → `invest_type_std`）
- 展开行显示该分类下的明细
- 支持 AG Grid 的 aggregation（小计行）
- 新增的 `BasisBreakdownTable` 支持按 `accounting_basis` 分组

### Step 5: 修复已知缺陷

- [ ] 渲染 Detail 的 `summary[]` 数据（在摘要区或独立表格）
- [ ] 明细表列定义补齐 `amortized_cost_amount`
- [ ] 汇总表列定义补齐 `display_name`, `position_scope`, `currency_basis`
- [ ] 修正 KPI 文案: `summary_row_count` 的说明改为准确描述
- [ ] 决策状态更新传 `comment` 字段（可选文本框）
- [ ] 下钻区空状态文案修正

## Mock 数据 Seed

```typescript
export const BALANCE_ANALYSIS_SEED = {
  reportDate: "2026-03-01",
  marketAssetsYi: 3525.0,
  marketLiabilitiesYi: 1817.9,
  assetYieldPct: 2.07,
  liabilityCostPct: 1.77,
  staticSpreadBp: 29.5,
  oneYearGapYi: -373.0,
  bondFloatingGainYi: 68.48,
  issuedLiabilitySharePct: 66.3,
  ncdShareWithinIssuedPct: 81.8,
  abnormalAlertCount: 4,
  assetLiabilityRatio: 1.94,
  shortTermLiabilityPct: 72.6,
  abnormalAssetPct: 0.21,
  floatingGainCoveragePct: 18.4,
  bondInvestment: { balanceYi: 3287.09, sharePct: 93.3, yieldPct: 2.07 },
  interbankAsset: { balanceYi: 237.92, sharePct: 6.7, yieldPct: 1.27 },
  issuedLiability: { balanceYi: 1204.54, sharePct: 66.3, costPct: 1.73 },
  interbankLiability: { balanceYi: 613.37, sharePct: 33.7, costPct: 1.31 },
  maturityBuckets: [
    { bucket: "7天内", asset: 0, liability: 0, gap: 0 },
    { bucket: "8-30天", asset: 0, liability: 0, gap: 0 },
    { bucket: "31-90天", asset: 0, liability: 0, gap: -95 },
    { bucket: "91天-1年", asset: 0, liability: 0, gap: -278 },
    { bucket: "1-3年", asset: 0, liability: 0, gap: 794.5 },
    { bucket: "3-5年", asset: 0, liability: 0, gap: 0 },
    { bucket: "5年以上", asset: 0, liability: 0, gap: 1285.6 },
  ],
  keyCalendar: [
    { date: "03-02", event: "负债到期", amountYi: 114.54, level: "high", note: "重点滚续" },
    { date: "03-04", event: "负债到期", amountYi: 11.00, level: "medium", note: "关注成本" },
    { date: "03-05", event: "负债到期", amountYi: 10.00, level: "medium", note: "关注成本" },
    { date: "03-09", event: "负债到期", amountYi: 10.00, level: "low", note: "常规观察" },
    { date: "03-10", event: "负债到期", amountYi: 10.00, level: "low", note: "常规观察" },
    { date: "03-17", event: "负债到期", amountYi: 20.98, level: "medium", note: "关注成本" },
  ],
};
```

## 验证

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

**视觉验证**: 打开 `http://localhost:5173/asset-liability-analysis`，对比 `.omx/mockups/asset_liability_analysis_hd.png`，确认:
- 8 个 KPI 卡片可见
- 摘要区有文字
- 收益成本分解图可见
- 风险全景面板可见
- 贡献表可交互（分组/展开）
- 期限结构图可见
- 风险指标面板可见
- 关键日历可见

## 禁止事项

- 不删除现有 API 调用，只新增
- 不在浏览器端解析 xls
- 不引入新的重型依赖
- 不把所有内容塞在一个文件里（拆到 15+ 个子文件）
