# A6 — 前端补算经营/分析指标残留面：逐项验真与处置分类

- 任务：技术债清偿调查 A6-侦查（30 并行专家之一）
- 日期：2026-08-12
- 方法：只读代码验真。逐项打开被点名文件核对行号与公式，另核对消费方（路由挂载、引用链）、页面 informal 标注、治理裁决文档。不修改任何业务代码。
- 结论先行：**7 项全部真实存在，无虚构证据**；审计清单行号基本准确（个别偏差 1–5 行，属函数体边界差异）。其中 1 项命中红线且已被 P1-10 治理挂账（zqtzAdbAvgRollup）、1 项为未挂路由死代码（yieldAnalysisAggregates，自注属实）、2 项建议下沉或补标注、3 项判定不违规。

---

## 0. 裁决依据（红线与例外）

**红线**：前端不得计算正式金融指标。

> `frontend/AGENTS.md:40`："Keep official finance calculations out of the frontend."
> `frontend/CLAUDE.md`（Business display rules）："Do not calculate official finance metrics in the frontend."

**展示层例外**（DV01 类裁决）：

> `.planning/STATE.md:63`："Frontend finance logic remains guarded; the DV01 exception is display-only and narrowly scoped."

**P1-10 治理裁决现状**（`docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md`）：

> 第 33 行（P1-10 Frontend formal aggregation）候选决策："A: backend DTO only; B: frontend may derive display aggregates; C: frontend derives only clearly non-formal UI helpers." 默认建议："**Prefer A for formal metrics and C for labeled non-formal helpers**."
> 第 56 行（2026-08-06 refresh）：P1-10、P1-11 **仍在待 owner 决策行列**，尚未关闭。
> 第 84 行（P1-10 prework）直接点名两个文件："move or label formal aggregation currently in `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts` and `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`"。

判定框架：正式口径指标（PnL/余额/收益率/归因等 core_finance 官方口径）在前端聚合/派生 = 命中红线；已清晰标注的非正式 UI 辅助（候选/分析口径）= P1-10 C 类容忍面，待 owner 决策收敛；两个后端返回值之间的展示层差值/环比 = DV01 例外同类，不违规。

---

## 1. 验真表

| # | 审计声称位置 | 验真结果 | 实际位置 | 行号准确性 |
|---|---|---|---|---|
| 1 | productCategoryPnlPageModel.ts ~4707-4718 TPL 所需收益率反推 + 1–6 月 sum/average | **存在** | 4685-4689（sum/average）、4707-4719（requiredYield/liftBp） | 准确 |
| 2 | crossAssetAnalytics.ts ~111-135、601-626 Pearson 矩阵、ERP | **存在** | 77-103（pearsonR）、111-140（矩阵）、601-626（ERP） | 准确 |
| 3 | AverageBalanceView.tsx ~128-136、555-562、713-715 YoY%、偏离度、>5% 文案 | **存在** | 128-137、555-562、713-716 | 准确 |
| 4 | zqtzAdbAvgRollup.ts ~7-48 父子类目 rollup 求和日均 | **存在** | 7-49 | 准确 |
| 5 | yieldAnalysisAggregates.ts 对正式 PnL 明细 sum/占比/排名；自注 P1 违规；页面未挂路由 | **存在，自注属实，未挂路由属实** | 1-5（自注）、34-70（aggBy）、72-86（入口） | 准确 |
| 6 | bondAnalyticsHomeCalculations.ts ~52-72 computeRelativeChangePct / computeBpDelta | **存在** | 52-60、62-72 | 准确 |
| 7 | LiabilityAnalyticsPage.tsx ~418-438 市值÷1e8、期限桶 sum 负债合计/一年内压力 | **存在** | 417-438（计算）、443-465（驱动风险文案） | 准确 |

---

## 2. 逐项证据与处置判定

### 项 1：产品大类 PnL — TPL 所需收益率反推与 1–6 月均值

**位置**：`frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts:4685-4719`

```ts
// 4685-4689
const sum = (values: number[]) =>
  values.reduce((total, value) => total + value, 0);
const average = (values: number[]) => sum(values) / values.length;
const q1TplAverage = average(safeTplPnlValues.slice(0, 3));
const h1TplAverage = average(safeTplPnlValues);
// 4707-4711
const thresholds = thresholdInputs.map((threshold) => {
  const requiredYield =
    currentTplFtp +
    (threshold.targetPnl / currentTplScale) * (365 / currentTplDays) * 100;
  const liftBp = (requiredYield - currentTplYield) * 100;
```

同一 surface 还包含负债端六月合计与正负池抵消比例（4721-4752 行，`liabilityOffsetRatio`）。

**上下文与标注**：

- selector 自注（4568-4571）："Candidate management view derived from six monthly formal payloads and the June MoM attribution. **It does not replace governed totals, forecast results, or formal FTP scenario calculations.**"
- 展示组件 `ProductCategoryOperatingPanels.tsx:42-49` 有显式标签："候选管理视图 / 经营修复监控 / …不新增正式指标"，并带 `metricStatus.disclaimer` 悬浮说明（第 53 行）。
- 输入全部来自正式月度 payload（`business_net_income`、`scale`、`days`、`baseline_ftp_rate_pct`），页面 `/product-category-pnl` 已挂路由（`routes.tsx:273`）。

**判定**：命中"前端补算经营指标"面——`requiredYield` 是年化收益率反推公式（FTP 加点 + 365 年化），不是简单展示差值；但组件与 selector 双层 informal 标注已存在，符合 P1-10 默认方向的 C 类（labeled non-formal helpers）。**分类：标注 informal 展示辅助（现状可容忍），随 P1-10 裁决复核**。若管理层将该"恢复阈值"用于正式汇报，必须下沉后端。

**最小处置**：现状维持 0 工作量；将本 surface 列入 P1-10 owner 决策清单附录（0.5 天文档工作）。若裁决下沉：后端新增 DTO 字段（复用月度正式 payload 服务端已有数据）+ 前端改为消费，约 2 天。

### 项 2：跨资产 — 前端 Pearson 相关矩阵与股债 ERP

**位置**：`frontend/src/features/cross-asset/lib/crossAssetAnalytics.ts`

```ts
// 77-79
function pearsonR(xs: number[], ys: number[]): number | null {
  const n = xs.length;
  if (n < 3) return null;
// 111-115
export function buildCorrelationMatrix(kpis: ResolvedCrossAssetKpi[]): CorrelationMatrix {
  const minimumObservations = 5;
  const eligible = kpis
    .map((kpi) => ({ kpi, points: normalizeDatedValues(kpi.sparklinePoints) }))
    .filter(({ kpi, points }) => isAssetLevelKpiKey(kpi.key) && points.length >= minimumObservations);
// 601-604, 625-626
export function computeEquityBondERP(kpis: ResolvedCrossAssetKpi[]): EquityBondERP {
  const byKey = new Map(kpis.map((k) => [k.key, k]));
  const peKpi = byKey.get("csi300_pe");
  const bondKpi = byKey.get("cn_gov_10y");
  ...
  const earningsYield = (1 / pe) * 100;
  const erp = earningsYield - bondYield;
```

**上下文**：输入是**市场公开行情 KPI**（沪深300 市盈率、10Y 国债收益率），不是本行正式财务口径；模块头注释（1-11 行）自述为纯计算函数。消费页面 `/cross-asset`（`routes.tsx:322`）为市场跨资产驱动分析页。相关矩阵已做日期对齐防护（106-109 行注释禁止无日期数组按位置配对）。

**判定**：**不命中红线**。"正式金融指标"红线针对 core_finance 官方口径（PnL/余额/收益率/归因）；ERP 与相关系数是市场数据的分析统计，无对应后端正式实现可复算冲突。**分类：不违规（市场分析口径）**。

**残余风险**：`CrossAssetDriversPage.tsx` 中未见 `result_meta`/`basis` 治理标注字样（grep 零命中），页面级"分析口径、非正式指标"声明依赖组件文案。**最小处置**：在页面头部补一条口径声明（对齐 average-balance 的做法），0.5 天。

### 项 3：日均分析 — YoY%、期末偏离度与 >5% 风险文案

**位置**：`frontend/src/features/average-balance/components/AverageBalanceView.tsx`

```tsx
// 128-137
function computeYoyPct(current: number | null, prior: number | null): number | null {
  ...
  return ((current - prior) / prior) * 100;
}
// 555-562
const assetDeviationPct =
  dailyData && dailyData.total_avg_assets > 0
    ? ((dailyData.total_spot_assets - dailyData.total_avg_assets) / dailyData.total_avg_assets) * 100
    : 0;
const liabilityDeviationPct = ...（同构）
// 713-716
const deviationWarning =
  assetDeviationPct > 5 || liabilityDeviationPct > 5
    ? "偏离度 > 5%，存在“窗口粉饰”风险，请结合实际头寸变化核查。"
    : null;
```

**上下文**：

- 页面副标题（735-738）自述："页面只消费后端返回结果，**不在前端补算正式金融口径**，正式资产负债分析仍从专用正式页面进入。"第 748 行明示"当前页面为资产负债分析的**分析口径子视图**"。
- YoY 表格在 UI 中明示公式（879-884："同比% =（本期−去年）/ 去年（分母为 0 时显示为「—」）"）。

**判定**：YoY 与偏离度均为**两个后端返回值之间的展示层比较**，与 DV01 例外（display-only）同类；页面本身即分析口径子视图且有声明。**分类：不违规（informal 展示辅助，标注已存在）**。>5% 阈值是前端硬编码的业务判断规则，仅驱动提示性 Alert，不产出指标数值，风险可接受但阈值来源未声明。

**最小处置**：为 5% 阈值加一行口径注释（阈值出处/责任人），并复核副标题措辞与偏离度计算的表述一致性，0.5 天。无下沉必要。

### 项 4：业务种类 PnL — 父子类目 rollup 求和日均余额 ⚠ 命中红线

**位置**：`frontend/src/features/pnl/zqtzAdbAvgRollup.ts:1-49`

```ts
// 1-5 注释
/**
 * 日均 breakdown 使用 classify_zqtz_asset_bond_label（最细一档类目）；父级「非底层投资资产」、
 * 「证券业资管计划」在明细里常常没有单独一行，PnL 父级行却仍汇总损益，
 * 故日均列应对其子类日均（元）求和以便对齐口径。
 * 与 backend/app/core_finance/zqtz_asset_bond_category.py 中 sort_order 83–88 行一致。
 */
export const ADB_AVG_ROLLUP_CHILDREN_BY_PARENT: Record<string, readonly string[]> = {
  非底层投资资产: ["信托计划", "证券业资管计划"],
  ...
};
// 38-48：递归对子类目日均（元）求和，任一子类缺数则返回 undefined
let sum = 0;
for (const label of children) {
  const v = resolveAdbAvgYuanFromRollup(label, directMap, visiting);
  ...
  sum += v;
}
```

**消费方**（均为挂路由的正式页面 `/pnl-by-business`，`routes.tsx:245`）：

- `frontend/src/features/pnl/PnlByBusinessPage.tsx:65,1447`
- `frontend/src/features/pnl/pnlByBusinessPageModel.ts:15,1257`

**判定**：**命中红线**。正式月报/YTD 页面的日均余额聚合在前端完成，且 `ADB_AVG_ROLLUP_CHILDREN_BY_PARENT` 是后端类目树（`zqtz_asset_bond_category.py` sort_order 83–88）的前端复制——这正是 P1-10 影响描述的原文风险："category trees are duplicated, and frontend can diverge from governed rules"。P1-10 prework（决策矩阵第 84 行）已点名本文件为待迁移/待标注对象，且 P1-10 至 2026-08-06 refresh 仍未关闭。

**分类：下沉后端（P1-10 候选 A）**。**注意：owner 决策未落地前不要擅动**（同批的 `yieldAnalysisAggregates.ts:5` 明确要求"在 owner 决策落地前"冻结），本项的正确动作是推动 P1-10 裁决而非直接改码。

**最小处置**：裁决通过后——后端在 ADB comparison / by-business 月度 DTO 中输出父级 rollup 日均（服务端已有类目树与明细，聚合成本低），前端删除 `zqtzAdbAvgRollup.ts` + `zqtzAdbAvgRollup.test.ts` + fixture，改读 DTO 字段；保留一条"前端不再本地 rollup"的回归断言。工作量：中，2–3 天（后端聚合 + 契约 + 前端替换 + 测试迁移）。

### 项 5：收益分析聚合 — 对正式 PnL 明细 sum/占比/排名（死代码）

**位置**：`frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts`

```ts
// 1-5 文件头自注（属实）
// 状态标注（2026-07-19 审计）：本模块由 YieldAnalysisPage 使用，该页面当前未挂路由
// （见 frontend/src/router/routes.tsx，无对应 route）。此处对正式 PnL 明细行做
// sum/占比/分组排名，属于前端聚合口径，待下沉后端（审计记录 P1-10，
// docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md）。
// 在 owner 决策落地前：不要将本模块接入新页面，也不要以其结果为正式口径。
// 72-77
export function buildYieldAnalysisAggregates(rows: PnlV1DetailRow[]) {
  const totalPnl = rows.reduce((s, r) => addMoney(s, r.total_pnl), 0);
  const nonstdRows = rows.filter((r) => r.source === "NonStd");
  ...
```

**路由核实（任务专项要求）**：**确认未挂路由**。

- `frontend/src/router/routes.tsx` 全文（大小写不敏感）grep `yield` 零命中；lazy import 清单（37-102 行）无 `YieldAnalysisPage`。
- `YieldAnalysisPage` 在 `frontend/src` 的全部引用只有 `frontend/src/test/PnlRoutesSmoke.test.tsx:37-40`，且是 `readFileSync` **读源码文本做设计令牌断言**（该测试 1065-1076 行检查颜色 token），不渲染、不挂载；smoke 测试实际渲染的 `/pnl` 路由指向 `FormalPnlV1Page`（"正式损益明细"）。
- 子组件 `PnlFilterBar` / `RankingBarsCard` / `YieldByPeriodPanel` 也只被 `YieldAnalysisPage` 与各自测试引用——整个 `yieldAnalysis` 目录是不可达闭包。

**判定**：计算本身命中红线（对正式 PnL 明细的 float 聚合，且 `parseYuan` 把 Decimal 字符串转 `Number`，正是 P1-10 影响描述"Decimal values are converted to floating point"），但**当前不可达**，风险被路由隔离 + 文件头围栏注释双重控制。

**分类：删除（未挂路由死代码）**，备选为维持围栏等 P1-10/P1-05 裁决。**牵连提醒**：P1 决策矩阵第 82 行（P1-05 prework）与第 84 行（P1-10 prework）均以本目录文件为落点，`PnlRoutesSmoke.test.tsx:37-40,1065-1094` 读取其源码文本；删除时需同步：(a) 更新两处决策文档指针，(b) 移除 smoke 测试中的样式断言块。工作量：0.5–1 天。等待裁决则 0。

### 项 6：债券分析主页 — computeRelativeChangePct / computeBpDelta

**位置**：`frontend/src/features/bond-analytics/lib/bondAnalyticsHomeCalculations.ts:52-72`

```ts
export function computeRelativeChangePct(current, previous): number | null {
  if (!isFiniteNumber(current) || !isFiniteNumber(previous) || previous === 0) return null;
  return ((current - previous) / Math.abs(previous)) * 100;
}
export function computeBpDelta(current, previous): number | null {
  const currentBp = toBp(current);
  const previousBp = toBp(previous);
  ...
  return currentBp - previousBp;
}
```

**消费方**：`BondKpiRow.tsx:22-31,106-116`（KPI 卡"较上期 +x bp / 较上期 x%"脚注）、`BondAnalyticsInstitutionalCockpit.tsx`；有专项测试 `src/test/BondAnalyticsHomeCalculations.test.ts`。

**判定**：**不违规**。KPI 本体（市值/YTM/久期/DV01）全部来自后端 `kpis`/`prev_kpis`，前端只做两期差值与环比，属 `.planning/STATE.md:63` "display-only and narrowly scoped" 例外同类，且是该例外辖域内的模块（bond-analytics）。

**单位复核（附加验真）**：`toBp`（30-40 行）对 `pct`/`ratio` 单位 ×10000——已核对后端契约 `backend/app/services/executive_service.py:224`（"raw 是 decimal ratio"）与 2545-2547（"the pct contract stores raw as a decimal ratio"），`pct` 的 raw 为小数比率，×10000 换算**正确**，无隐藏单位 bug。

**分类：不违规，保留**。工作量 0。

### 项 7：负债分析 — 市值÷1e8 与期限桶求和驱动风险文案

**位置**：`frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx`

```tsx
// 417-427：单位换算（有口径注释）
/** `total_market_value_amount` 与资产负债页一致，为「元」口径；KPI 展示「亿元」需 ÷1e8。 */
const assetTotalYi = useMemo(() => {
  ...
  return parsed / 100_000_000;
// 429-438：负债合计（权威值优先，回退前端桶求和）与一年内压力（纯前端桶求和）
const liabilityTotalYi = useMemo((): number | null => {
  const fromCp = numericToYiNumeric(cpQuery.data?.total_value ?? null)?.raw;
  const fromBuckets = sumKnownNumericRaw(dailyStructure.map((item) => item.amountYi?.raw));
  return fromCp ?? fromBuckets;
}, ...);
const firstYearPressureYi = useMemo((): number | null => {
  return sumKnownNumericRaw(
    dailyTerm.filter((item) => bucketFallsWithinOneYear(item.bucket)).map((item) => item.amountYi?.raw),
  );
}, [dailyTerm]);
// 443-465：驱动风险等级文案
{ label: "期限错配", level: firstYearPressureYi === null ? EM_DASH : firstYearPressureYi > 0 ? "中高" : "低", ... }
{ label: "流动性压力", level: liabilityTotalYi === null ? EM_DASH : liabilityTotalYi > 0 ? "中高" : "低", ... }
{ label: "负债滚续压力", level: firstYearPressureYi === null ? EM_DASH : firstYearPressureYi > 100 ? "高" : "中", ... }
```

**上下文**：`dailyStructure`/`dailyTerm` 来自后端负债风险接口（293-301 行，`riskQuery.data.liabilities_structure` / `liabilities_term_buckets`）；页面已有自我约束注释（442 行："风险全景：只展示后端权威集中度值，不在前端追加集中度评级推断"），但期限压力仍是前端 sum + 阈值分级（>0 → 中高、>100 亿 → 高，阈值硬编码无出处）。页面 `/liability-analytics` 已挂路由（`routes.tsx:231`）。

**判定**：拆开看——(a) `assetTotalYi` ÷1e8 是纯单位换算，**不违规**；(b) `liabilityTotalYi` 已实现"后端权威值优先、桶求和仅回退"，方向正确；(c) `firstYearPressureYi` 桶求和 + 三处硬编码阈值分级是**前端补算经营/风险辅助指标**，与页面 442 行自我约束存在不一致。**分类：(c) 下沉后端为主（后端补合计字段），阈值分级标注 informal 为辅**。

**最小处置**：后端 liabilities-risk DTO 增加 `total_liabilities` 与 `within_one_year_total` 两个合计字段（桶数据已在服务端，聚合成本低），前端删 `sumKnownNumericRaw` 回退路径与桶过滤求和；三处等级阈值或者后端化、或者就地注明"前端推演阈值，非正式评级"。工作量：1–2 天。

---

## 3. 处置清单与优先级

| 优先级 | 项 | 分类 | 最小处置 | 预估工作量 | 前置条件 |
|---|---|---|---|---|---|
| **P0** | 4. zqtzAdbAvgRollup | **下沉后端** | 推动 P1-10 owner 裁决 → 后端 DTO 输出父级 rollup 日均，前端删 rollup 与类目树复制 | 2–3 天 | **P1-10 裁决（决策前冻结）** |
| **P1** | 5. yieldAnalysisAggregates | **删除（死代码）** | 删 `YieldAnalysisPage` + `yieldAnalysis/` 目录 + smoke 测试样式断言块；同步更新 P1-05/P1-10 prework 文档指针 | 0.5–1 天 | 与 P1-05/P1-10 文档联动 |
| **P1** | 7. LiabilityAnalyticsPage 桶求和 | **下沉后端 + 标注** | 后端 DTO 补 2 个合计字段；前端删回退求和；阈值分级注明 informal | 1–2 天 | 无 |
| **P2** | 1. productCategory requiredYield | **标注 informal（现状容忍）** | 维持双层标注；列入 P1-10 裁决附录；若用于正式汇报则下沉 | 0（维持）/ 2 天（下沉） | P1-10 裁决 |
| **P2** | 3. AverageBalanceView 偏离度/YoY | **不违规（informal 已标注）** | 5% 阈值补口径注释 | 0.5 天 | 无 |
| **P3** | 2. crossAssetAnalytics | **不违规（市场分析口径）** | 页面头部补"分析口径、非正式指标"声明 | 0.5 天 | 无 |
| — | 6. bondAnalyticsHomeCalculations | **不违规，保留** | 无（单位换算已复核正确） | 0 | 无 |

排序理由：项 4 是唯一"正式挂路由页面 + 正式口径聚合 + 治理文档点名"的三重命中，但受 P1-10 冻结约束，短期动作是推动裁决；项 5 处置成本最低且消除的是"死代码 + P1 违规注释长期挂账"的审计噪音；项 7 无治理冻结约束、可立即执行；其余为标注补强或无需处置。

## 4. 残余风险与未尽事项

1. **P1-10 未裁决是项 1/4/5 的共同阻塞**：三项的最终形态（A 下沉 / C 标注容忍）取决于同一个 owner 决策；本报告的分类采用决策矩阵的默认建议方向（Prefer A for formal, C for labeled non-formal）。
2. 项 5 删除会使 P1-05 prework（决策矩阵第 82 行指向 `YieldByPeriodPanel.tsx`）的落点悬空，删除 PR 必须同步修订该文档，否则制造新的文档-代码漂移。
3. 本审计只读验真，未运行前端测试；引用的测试（`zqtzAdbAvgRollup.test.ts`、`BondAnalyticsHomeCalculations.test.ts`、`PnlRoutesSmoke.test.tsx`）以其在仓库中的当前内容为证据，未验证其通过状态。
4. 项 2 的 cross-asset KPI 数据源治理标注（result_meta/basis）在页面层未见，若该页面后续接入本行持仓类数据，需重新评估红线命中。
