# T1 — 拆分 ProductCategoryPnlPage.tsx 与 productCategoryPnlPageModel.ts（行为等价重构）

## 目标

把两份 5000+ 行文件按区块/域拆成子模块，**外部可见行为与导入路径零变化**。这是纯重构：不改任何逻辑、文案、样式、导出名、测试断言。

## 行为不变的验证标准（先跑基线，后跑对比）

拆分前，在干净工作区先跑一遍并记录结果；拆分后跑同一组命令，结果必须一致（同样的通过数）：

```bash
cd frontend
npm run test -- ProductCategoryPnlPage
npm run test -- productCategoryPnlPageModel
npm run test -- ProductCategoryAdjustmentAuditPage
npm run test -- ProductCategoryBranchSwitcher
npm run lint
npm run typecheck
npm run debt:audit
```

任何一条测试的断言都**不允许修改**。如果拆分导致必须改测试，说明拆错了，回退重来。

## 拆分方案

### 1. 页面组件 `ProductCategoryPnlPage.tsx`（5253 行）

新建 `frontend/src/features/product-category-pnl/pages/sections/`，按既有组件边界搬移（行号为当前基线，动手前重新确认）：

| 新文件 | 搬入内容（当前行号） |
| --- | --- |
| `sections/FormalReadinessSection.tsx` | `SectionLead` :143、`ProductCategoryFormalReadinessBand` :171、`ProductCategoryOwnerSignableStatus` :289、`ProductCategoryFormalTableMobileReadout` :305-388 及其字段子组件 |
| `sections/DerivedCharts.tsx` | `buildAxisLabelFormatter`/`buildAxisTooltipFormatter` :469-487、六个 `build*ChartOption` :489-916、`DerivedChartPanel` :918-940 |
| `sections/AttributionSection.tsx` | `ATTRIBUTION_*` 常量 :942-967、`ProductCategoryInterestSpreadAttributionPanel` :983、`ProductCategoryAttributionPanel` :1070、`ProductCategoryAttributionCompareSwitch` :2401、`AttributionMetric` :2434、归因相关 mobile readout :2448-2803、`AttributionComparisonTable` :2805 |
| `sections/OperatingAnalysisSection.tsx` | `ProductCategoryOperatingAnalysisPanel` :1215、`ProductCategoryOperatingActionBacktestPanel` :1414、`ProductCategoryOperatingContributionList` :1628 |
| `sections/ScenarioSection.tsx` | Scenario 相关 type/常量 :80-117、`ProductCategoryScenarioExplanationCard` :1651、`ProductCategoryScenarioComparisonPanel` :1812、`ProductCategoryScenarioActionClosurePanel` :1906 |
| `sections/FinancialAnalysisSection.tsx` | `ProductCategoryFinancialAnalysisPanel` :2012 |
| `sections/LiabilityReadouts.tsx` | Liability 相关 mobile readout :2529-2687 |

主文件保留：路由级默认导出组件（约 :2982 起的主函数）、`buildAdjustmentDraft`、`formatProductCategoryRefreshStatusLine`、少量纯工具（`reportDateYearMonth`、`diagnosticsToneClassName`、`formalValueToneClassName` 等可挪到 `sections/shared.ts`）。

约束：
- 仅做"剪切 + import 调整"，不改组件内部任何一行逻辑。
- `data-testid`、CSS 类名、文案全部原样保留（页面测试以此为锚）。
- CSS 文件不动。

### 2. 页面 model `productCategoryPnlPageModel.ts`（5052 行）

新建 `frontend/src/features/product-category-pnl/pages/model/`，按域搬移：

| 新文件 | 内容 |
| --- | --- |
| `model/constants.ts` | :39-146 的视图常量、`PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS`、`defaultProductCategoryScenarioRateForReportDate`、色板等 |
| `model/formatters.ts` | :919-1013 的 `format*` / `tone*` 系列 |
| `model/operatingAnalysis.ts` | `selectProductCategoryOperatingAnalysisSurface` :1470 及其私有 helper、`selectProductCategoryOperatingActionBacktestSurface` :3218 |
| `model/scenario.ts` | `selectProductCategoryScenarioExplanation` :2185、`selectProductCategoryScenarioSensitivitySurface` :2278 及 :1900-1965 一带的 scenario 私有 helper |
| `model/attribution.ts` | `selectProductCategoryAttributionWaterfallSurface` :2410、`selectProductCategoryRootCauseSurface` :2477、`selectProductCategoryDecisionFocusSurface` :2576 |
| `model/charts.ts` | `selectProductCategoryTrend*` :3837 起、各 `select*Chart` 系列、`buildProductCategoryDiagnosticsSurface` :3782 |
| `model/liability.ts` | Liability trend/matrix 相关 selector 与类型 |
| `model/types.ts` | 跨模块共享的导出类型（:147-918 的 type 块按归属就近放，跨域共享的进 types.ts） |

**原文件 `productCategoryPnlPageModel.ts` 保留为纯 re-export barrel**（`export * from "./model/..."` / 显式具名 re-export），保证：
- `ProductCategoryPnlPage.tsx` 现有 import（:24-77 的大 import 块）不需要动；
- `productCategoryPnlPageModel.test.ts`、`*.dateSemantics.test.ts` 及其他 27 个引用方（`teamPerformancePageModel.ts`、`executiveDashboardAdapter.ts` 等）零改动。

约束：
- 所有 `export` 名称、签名、默认值不变；私有 helper 跟随其唯一调用方所在文件走，被多处调用的进 `model/shared.ts`。
- 禁止在搬移过程中"顺手"合并重复代码、改命名、加类型注解。

## 执行步骤（每步带验证）

1. 基线：跑上面的验证命令组，记录结果 -> verify: 全绿并留存输出
2. 先拆 model（风险更低，无 JSX）：建 `model/` 各文件 + barrel 化原文件 -> verify: `npm run test -- productCategoryPnlPageModel` 全绿、`npm run typecheck` 通过
3. 再拆 page sections -> verify: `npm run test -- ProductCategoryPnlPage` 全绿
4. 全量对比基线 -> verify: 与第 1 步结果一致
5. `npm run debt:audit`（触碰了 pages/selectors 必跑）-> verify: 无新增告警

## 禁止事项

- 不改 `frontend/src/router/routes.tsx` 的懒加载路径（主文件位置不变）
- 不动 `ProductCategoryAdjustmentAuditPage.tsx`、`MonthlyOperatingAnalysisBranch.tsx`、`ProductCategoryGovernanceStrip.tsx`（它们已经是独立文件）
- 不动任何测试文件、mock、CSS

## 验收标准

- [ ] 两份原文件各缩到 < 1000 行（page 主文件保留主组件可放宽到 ~1500 行）
- [ ] 全部验证命令与基线一致
- [ ] 外部 import 方（grep `productCategoryPnlPageModel` / `ProductCategoryPnlPage` 的所有引用）零 diff
- [ ] 不影响正式金融口径（重构声明：是——零影响）
