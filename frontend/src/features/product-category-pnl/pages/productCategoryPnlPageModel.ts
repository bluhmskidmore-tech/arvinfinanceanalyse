import type {
  ResultMeta,
  ProductCategoryPnlRow,
  ProductCategoryInterestSpreadPayload,
  ProductCategoryPnlPayload,
  ProductCategoryAttributionRow,
} from "../../../api/contracts";
import type { ProductCategoryCandidateMetricStatus } from "./model/productCategoryPnlModelInternals";
import {
  selectProductCategoryTrendReportDatesImpl,
  selectProductCategoryTrendReportPointsImpl,
  selectProductCategoryTwoYearInterestSpreadReportPointsImpl,
  buildProductCategoryTrendSnapshotImpl,
  selectProductCategoryTplScaleYieldChartImpl,
  selectProductCategoryCurrencyNetIncomeChartImpl,
  selectProductCategoryInterestEarningIncomeScaleChartImpl,
  selectProductCategoryInterestEarningAssetLiabilityScaleChartImpl,
  selectProductCategoryInterestSpreadChartImpl,
  selectProductCategoryInterestEarningSpreadChartImpl,
  selectProductCategoryInterestSpreadYearComparisonChartImpl,
  selectProductCategoryInterestEarningSpreadYearComparisonChartImpl,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChartImpl,
} from "./model/productCategoryPnlTrendAndChartModel";
import {
  parseProductCategoryReportDateInternal as parseProductCategoryReportDate,
  decimalNumberInternal as decimalNumber,
  signedYiDeltaLabelInternal as signedYiDeltaLabel,
  signedBpLabelInternal as signedBpLabel,
  PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
} from "./model/productCategoryPnlModelInternals";
import {
  formatProductCategoryRowDisplayValue,
  formatProductCategoryForeignDisplayValue,
  formatProductCategoryYieldValue,
} from "./model/productCategoryPnlDisplayModel";
import { buildProductCategoryInterestSpreadAttributionImpl } from "./model/productCategoryPnlInterestSpreadModel";
import {
  selectProductCategoryLiabilitySideTrendChartImpl,
  selectProductCategoryLiabilityDetailMatrixImpl,
  selectProductCategoryLiabilityDetailTrendRowsImpl,
  buildProductCategoryLiabilitySideTrendSurfaceImpl,
} from "./model/productCategoryPnlLiabilityModel";

export type { ProductCategoryClosureErrorSignal } from "./model/productCategoryPnlDisplayModel";
export {
  PRODUCT_CATEGORY_VALUE_TONE_COLORS,
  formatProductCategoryValue,
  formatProductCategoryAttributionEffect,
  selectProductCategoryClosureErrorSignal,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryForeignDisplayValue,
  formatProductCategoryYieldValue,
  formatProductCategoryChartNumberTwoDecimals,
  toneForProductCategoryValue,
  toneForProductCategoryForeignDisplayValue,
} from "./model/productCategoryPnlDisplayModel";
export type { ProductCategoryCandidateMetricStatus } from "./model/productCategoryPnlModelInternals";
export { PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS } from "./model/productCategoryPnlModelInternals";
export type {
  ProductCategoryOperatingContributionRow,
  ProductCategoryOperatingMovementRow,
  ProductCategoryOperatingQuadrant,
  ProductCategoryOperatingQuadrantRow,
  ProductCategoryOperatingActionQueueRow,
  ProductCategoryOperatingAnalysisSurface,
} from "./model/productCategoryOperatingAnalysisModel";
export { selectProductCategoryOperatingAnalysisSurface } from "./model/productCategoryOperatingAnalysisModel";
export type {
  ProductCategoryOperatingBacktestLatestReviewRow,
  ProductCategoryOperatingBacktestSurface,
} from "./model/productCategoryOperatingBacktestModel";
export { selectProductCategoryOperatingActionBacktestSurface } from "./model/productCategoryOperatingBacktestModel";
export type {
  ProductCategoryScenarioSensitivityRow,
  ProductCategoryScenarioInsightCard,
  ProductCategoryScenarioRiskRow,
  ProductCategoryScenarioPathPoint,
  ProductCategoryScenarioActionItem,
  ProductCategoryScenarioHeatRow,
  ProductCategoryScenarioComparisonCell,
  ProductCategoryScenarioComparisonRow,
  ProductCategoryScenarioActionClosureRow,
  ProductCategoryScenarioBreakeven,
  ProductCategoryScenarioSideOffset,
  ProductCategoryScenarioReviewRow,
  ProductCategoryScenarioPressureSummary,
  ProductCategoryScenarioSensitivitySurface,
} from "./model/productCategoryScenarioSensitivityModel";
export { selectProductCategoryScenarioSensitivitySurface } from "./model/productCategoryScenarioSensitivityModel";
export type {
  ProductCategoryScenarioExplanationDriverRow,
  ProductCategoryScenarioExplanation,
} from "./model/productCategoryScenarioExplanationModel";
export { selectProductCategoryScenarioExplanation } from "./model/productCategoryScenarioExplanationModel";
export type {
  ProductCategoryAttributionWaterfallKey,
  ProductCategoryAttributionWaterfallRow,
  ProductCategoryAttributionWaterfallSurface,
  ProductCategoryRootCauseDriverKey,
  ProductCategoryRootCauseDriverRow,
  ProductCategoryRootCauseSurface,
  ProductCategoryDecisionFocusKey,
  ProductCategoryDecisionFocusItem,
  ProductCategoryDecisionFocusSurface,
} from "./model/productCategoryAttributionDecisionModel";
export {
  selectProductCategoryAttributionWaterfallSurface,
  selectProductCategoryRootCauseSurface,
  selectProductCategoryDecisionFocusSurface,
} from "./model/productCategoryAttributionDecisionModel";
export type {
  ProductCategoryDiagnosticsMatrixRow,
  ProductCategoryNegativeContributionRow,
  ProductCategorySpreadMovementAttribution,
  ProductCategoryDiagnosticsSurface,
} from "./model/productCategoryPnlDiagnosticsModel";
export { buildProductCategoryDiagnosticsSurface } from "./model/productCategoryPnlDiagnosticsModel";
export { selectProductCategoryManagementMonitoringSurface } from "./model/productCategoryManagementMonitoringModel";
export type {
  ProductCategoryOperatingActionKind,
  ProductCategoryOperatingBacktestActionRow,
  ProductCategoryOperatingBacktestCalibrationRow,
  ProductCategoryOperatingBacktestExample,
  ProductCategoryOperatingBacktestMissActionRow,
  ProductCategoryOperatingBacktestMissReasonKey,
  ProductCategoryOperatingBacktestMissReasonRow,
} from "./model/productCategoryOperatingBacktestOutcomeModel";
export type { ProductCategoryManagementMonitoringSurface } from "./model/productCategoryManagementMonitoringModel";

/** Display order for category rows; does not re-aggregate backend totals. */
const DISPLAY_ORDER = [
  "interbank_lending_assets",
  "repo_assets",
  "bond_investment",
  "bond_tpl",
  "bond_ac",
  "bond_ac_other",
  "bond_fvoci",
  "bond_valuation_spread",
  "interest_earning_assets",
  "derivatives",
  "intermediate_business_income",
  "asset_total",
  "interbank_deposits",
  "interbank_borrowings",
  "repo_liabilities",
  "interbank_cds",
  "credit_linked_notes",
  "liability_total",
] as const;

const DISPLAY_ORDER_INDEX = new Map<string, number>(
  DISPLAY_ORDER.map((categoryId, index) => [categoryId, index]),
);

/** First-screen selector scope for the main product-category PnL page (truth contract). */
export const PRODUCT_CATEGORY_MAIN_PAGE_VIEWS = ["monthly", "ytd"] as const;

/**
 * Formal reads may return 503 while the shared read model is being refreshed.
 * Keep recovery page-local and bounded: 24 retries cover about five minutes
 * once the delay reaches its 15-second cap.
 */
export const PRODUCT_CATEGORY_READ_503_RETRY_LIMIT = 24;
const PRODUCT_CATEGORY_READ_503_MAX_DELAY_MS = 15_000;

function productCategoryReadErrorStatus(error: unknown): number | null {
  if (typeof error === "object" && error !== null && "status" in error) {
    const status = (error as { status?: unknown }).status;
    if (typeof status === "number") {
      return status;
    }
  }

  const message = error instanceof Error ? error.message : "";
  const match = message.match(/\((\d{3})\)\s*$/);
  return match ? Number(match[1]) : null;
}

export function shouldRetryProductCategoryRead(
  failureCount: number,
  error: unknown,
): boolean {
  return (
    failureCount < PRODUCT_CATEGORY_READ_503_RETRY_LIMIT &&
    productCategoryReadErrorStatus(error) === 503
  );
}

export function productCategoryReadRetryDelay(failureCount: number): number {
  return Math.min(
    1_000 * 2 ** Math.max(0, failureCount),
    PRODUCT_CATEGORY_READ_503_MAX_DELAY_MS,
  );
}

/**
 * Views the governed detail API may advertise via `available_views` (superset of main-page scope).
 * Main page does not add `qtd` / `year_to_report_month_end` controls without contract updates.
 */
export const PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS = [
  "monthly",
  "qtd",
  "ytd",
  "year_to_report_month_end",
] as const;

export function mainPageViewsAreGovernedDetailSubset(): boolean {
  return PRODUCT_CATEGORY_MAIN_PAGE_VIEWS.every((view) =>
    (PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS as readonly string[]).includes(
      view,
    ),
  );
}

/** True when the API surface includes both views required by the main-page selector. */
export function availableViewsSupportMainPageSelector(
  availableViews: string[],
): boolean {
  return PRODUCT_CATEGORY_MAIN_PAGE_VIEWS.every((view) =>
    availableViews.includes(view),
  );
}

export const PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS = [
  { value: "2.00", label: "2.0%" },
  { value: "1.75", label: "1.75%" },
  { value: "1.60", label: "1.6%" },
  { value: "1.50", label: "1.5%" },
] as const;

export type ProductCategoryFtpScenarioRate =
  (typeof PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS)[number]["value"];

export function defaultProductCategoryScenarioRateForReportDate(
  reportDate: string,
): ProductCategoryFtpScenarioRate {
  if (reportDate.startsWith("2026-")) {
    return "1.60";
  }
  if (reportDate.startsWith("2025-")) {
    return "1.75";
  }
  return "1.75";
}

export function formatProductCategoryReportMonthLabel(
  reportDate: string,
): string {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return reportDate;
  }
  return `${match[1]}\u5e74${match[2]}\u6708`;
}

export type ProductCategoryTrendSnapshot = {
  reportDate: string;
  label?: string;
  view?: string;
  meta?: ResultMeta;
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
  interestEarningSpread?: ProductCategoryInterestSpreadPayload | null;
};

export type ProductCategoryTrendReportPoint = {
  reportDate: string;
  view: string;
  label: string;
};

export type ProductCategoryTplScaleYieldChart = {
  labels: string[];
  cnyScale: number[];
  foreignScale: number[];
  weightedYield: number[];
};

export type ProductCategoryCurrencyNetIncomeChart = {
  labels: string[];
  cnyNet: number[];
  foreignNet: number[];
};

export type ProductCategoryInterestEarningIncomeScaleChart = {
  labels: string[];
  scale: number[];
  income: number[];
};

export type ProductCategoryInterestEarningAssetLiabilityScaleChart = {
  labels: string[];
  interestEarningAssetScale: number[];
  interestBearingLiabilityScale: number[];
};

export type ProductCategoryInterestSpreadChart = {
  labels: string[];
  assetYield: Array<number | null>;
  liabilityYield: Array<number | null>;
  spread: Array<number | null>;
};

export type ProductCategoryYearComparisonStatus = {
  comparableMonthCount: number;
  qualityState: "ok" | "degraded" | "unknown";
  qualityIssueMonthCount: number;
};

export type ProductCategoryInterestSpreadYearComparisonChart = {
  labels: string[];
  monthKeys: number[];
  comparisonStatus: ProductCategoryYearComparisonStatus;
  series: Array<{
    year: string;
    spread: Array<number | null>;
  }>;
};

export type ProductCategoryIntermediateBusinessIncomeYearComparisonChart = {
  labels: string[];
  comparisonStatus: ProductCategoryYearComparisonStatus;
  series: Array<{
    year: string;
    income: Array<number | null>;
  }>;
};

export type ProductCategoryInterestSpreadBasis = "weighted" | "cny";

export type ProductCategoryInterestSpreadAttributionSelection = {
  basis: ProductCategoryInterestSpreadBasis;
  month: number;
};

export type ProductCategoryInterestSpreadAttributionSummary = {
  assetYieldCurrent: number | null;
  assetYieldPrior: number | null;
  liabilityYieldCurrent: number | null;
  liabilityYieldPrior: number | null;
  spreadCurrent: number | null;
  spreadPrior: number | null;
  assetContributionBp: number | null;
  liabilityContributionBp: number | null;
  spreadDeltaBp: number | null;
};

export type ProductCategoryInterestSpreadAttributionRow = {
  key: "asset_yield" | "liability_cost" | "spread";
  label: string;
  priorValue: number | null;
  currentValue: number | null;
  deltaBp: number | null;
  priorLabel: string;
  currentLabel: string;
  contributionLabel: string;
  explanation: string;
};

export type ProductCategoryInterestSpreadAttributionDetailPoint = {
  reportLabel: string;
  amountLabel: string;
  cashLabel: string;
  yieldLabel: string;
};

export type ProductCategoryInterestSpreadAttributionDetail = {
  key: "asset_total" | "liability_total";
  label: string;
  prior: ProductCategoryInterestSpreadAttributionDetailPoint;
  current: ProductCategoryInterestSpreadAttributionDetailPoint;
};

export type ProductCategoryInterestSpreadAttributionSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  selected: {
    basis: ProductCategoryInterestSpreadBasis;
    month: number;
    currentYear: number;
    priorYear: number;
    currentReportDate: string | null;
    priorReportDate: string | null;
  };
  complete: boolean;
  incompleteReasons: string[];
  summary: ProductCategoryInterestSpreadAttributionSummary;
  rows: ProductCategoryInterestSpreadAttributionRow[];
  details: ProductCategoryInterestSpreadAttributionDetail[];
};

export type ProductCategoryLiabilitySideTrendChart = {
  labels: string[];
  totalAverageDaily: Array<number | null>;
  totalRate: Array<number | null>;
  incompleteReasons: string[];
};

export type ProductCategoryLiabilityDetailTrendRow = {
  categoryId: string;
  categoryLabel: string;
  latestAmountLabel: string;
  amountDeltaLabel: string;
  latestRateLabel: string;
  rateDeltaLabel: string;
  comparisonLabel: string;
};

export type ProductCategoryLiabilityDetailMatrixPeriod = {
  key: string;
  label: string;
  reportDate: string;
};

export type ProductCategoryLiabilityDetailMatrixCell = {
  periodKey: string;
  amountLabel: string;
  rateLabel: string;
};

export type ProductCategoryLiabilityDetailMovement = {
  amountLabel: string;
  rateLabel: string;
};

export type ProductCategoryLiabilityCurrencyKey = "cny" | "foreign";

export type ProductCategoryLiabilityCurrencyMatrixCell = {
  periodKey: string;
  amountLabel: string;
  rateLabel: string;
};

export type ProductCategoryLiabilityCurrencyMatrixRow = {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  cells: ProductCategoryLiabilityCurrencyMatrixCell[];
  movement: {
    amountLabel: string;
    rateLabel: string;
  };
};

export type ProductCategoryLiabilityCurrencyMatrix = {
  currencyKey: ProductCategoryLiabilityCurrencyKey;
  currencyLabel: string;
  movementGroupLabel: string;
  rows: ProductCategoryLiabilityCurrencyMatrixRow[];
};

export type ProductCategoryLiabilityDetailMatrixRow = {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  cells: ProductCategoryLiabilityDetailMatrixCell[];
  movement: ProductCategoryLiabilityDetailMovement;
};

export type ProductCategoryLiabilityDetailMatrix = {
  periods: ProductCategoryLiabilityDetailMatrixPeriod[];
  movementGroupLabel: string;
  rows: ProductCategoryLiabilityDetailMatrixRow[];
  currencyMatrices: ProductCategoryLiabilityCurrencyMatrix[];
};

export type ProductCategoryLiabilitySideTrendSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  chart: ProductCategoryLiabilitySideTrendChart | null;
  totalReadout: ProductCategoryLiabilityDetailTrendRow | null;
  detailRows: ProductCategoryLiabilityDetailTrendRow[];
  detailMatrix: ProductCategoryLiabilityDetailMatrix;
  emptyCopy: string | null;
  incompleteReasons: string[];
};

export function selectProductCategoryTrendReportDates(
  selectedDate: string,
  reportDates: string[] | undefined,
  limit = 8,
): string[] {
  return selectProductCategoryTrendReportDatesImpl(
    selectedDate,
    reportDates,
    limit,
  );
}

export function selectProductCategoryTrendReportPoints(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
  limit = 8,
): ProductCategoryTrendReportPoint[] {
  return selectProductCategoryTrendReportPointsImpl(
    selectedDate,
    reportDates,
    monthlyView,
    limit,
  ) as ProductCategoryTrendReportPoint[];
}

export function selectProductCategoryTwoYearInterestSpreadReportPoints(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
): ProductCategoryTrendReportPoint[] {
  return selectProductCategoryTwoYearInterestSpreadReportPointsImpl(
    selectedDate,
    reportDates,
    monthlyView,
  ) as ProductCategoryTrendReportPoint[];
}

export function buildProductCategoryTrendSnapshot(
  payload: ProductCategoryPnlPayload,
  label?: string,
  meta?: ResultMeta,
): ProductCategoryTrendSnapshot {
  return buildProductCategoryTrendSnapshotImpl(
    payload,
    label,
    meta,
    selectProductCategoryDetailRows,
  ) as ProductCategoryTrendSnapshot;
}

export function selectProductCategoryTplScaleYieldChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryTplScaleYieldChart | null {
  return selectProductCategoryTplScaleYieldChartImpl(
    snapshots,
  ) as ProductCategoryTplScaleYieldChart | null;
}

export function selectProductCategoryCurrencyNetIncomeChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryCurrencyNetIncomeChart | null {
  return selectProductCategoryCurrencyNetIncomeChartImpl(
    snapshots,
  ) as ProductCategoryCurrencyNetIncomeChart | null;
}

export function selectProductCategoryInterestEarningIncomeScaleChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestEarningIncomeScaleChart | null {
  return selectProductCategoryInterestEarningIncomeScaleChartImpl(
    snapshots,
  ) as ProductCategoryInterestEarningIncomeScaleChart | null;
}

export function selectProductCategoryInterestEarningAssetLiabilityScaleChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestEarningAssetLiabilityScaleChart | null {
  return selectProductCategoryInterestEarningAssetLiabilityScaleChartImpl(
    snapshots,
  ) as ProductCategoryInterestEarningAssetLiabilityScaleChart | null;
}

export function selectProductCategoryInterestSpreadChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestSpreadChart | null {
  return selectProductCategoryInterestSpreadChartImpl(
    snapshots,
  ) as ProductCategoryInterestSpreadChart | null;
}

export function selectProductCategoryInterestEarningSpreadChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestSpreadChart | null {
  return selectProductCategoryInterestEarningSpreadChartImpl(
    snapshots,
  ) as ProductCategoryInterestSpreadChart | null;
}

export function selectProductCategoryInterestSpreadYearComparisonChart(
  snapshots: ProductCategoryTrendSnapshot[],
  basis: ProductCategoryInterestSpreadBasis = "weighted",
): ProductCategoryInterestSpreadYearComparisonChart | null {
  return selectProductCategoryInterestSpreadYearComparisonChartImpl(
    snapshots,
    basis,
  ) as ProductCategoryInterestSpreadYearComparisonChart | null;
}

export function selectProductCategoryInterestEarningSpreadYearComparisonChart(
  snapshots: ProductCategoryTrendSnapshot[],
  basis: ProductCategoryInterestSpreadBasis = "weighted",
): ProductCategoryInterestSpreadYearComparisonChart | null {
  return selectProductCategoryInterestEarningSpreadYearComparisonChartImpl(
    snapshots,
    basis,
  ) as ProductCategoryInterestSpreadYearComparisonChart | null;
}

export function selectProductCategoryIntermediateBusinessIncomeYearComparisonChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryIntermediateBusinessIncomeYearComparisonChart | null {
  return selectProductCategoryIntermediateBusinessIncomeYearComparisonChartImpl(
    snapshots,
  ) as ProductCategoryIntermediateBusinessIncomeYearComparisonChart | null;
}

const PRODUCT_CATEGORY_LIABILITY_COPY = {
  missingAverageDailySuffix: "负债端日均额缺失",
  missingRateSuffix: "负债端利率缺失",
  comparisonArrow: " → ",
  comparisonAmountPrefix: "日均额：",
  comparisonRatePrefix: "利率：",
  comparisonJoiner: "；",
  comparisonMissingCurrent: "当前指标缺失",
  comparisonMissingPrior: "缺少可比上期",
  liabilityTotalFallbackLabel: "负债合计",
  movementGroupAdjacent: "环比月度变动情况",
  movementGroupFallback: "较上期变动",
  cnyCurrencyLabel: "人民币结构",
  foreignCurrencyLabel: "外币结构",
  emptySurfaceCopy: "当前 payload 未返回可展示的负债端趋势数据。",
  emptyChartCopy: "负债端趋势数据不完整，无法绘制完整走势。",
} as const;

function buildProductCategoryLiabilityModelInput(
  snapshots: ProductCategoryTrendSnapshot[],
) {
  return {
    snapshots,
    displayOrderIndex: DISPLAY_ORDER_INDEX,
    formatReportMonthLabel: formatProductCategoryReportMonthLabel,
    parseReportDate: parseProductCategoryReportDate,
    formatRowDisplayValue: formatProductCategoryRowDisplayValue,
    formatForeignDisplayValue: formatProductCategoryForeignDisplayValue,
    percentNumber: decimalNumber,
    signedYiDeltaLabel,
    signedBpLabel,
    copy: PRODUCT_CATEGORY_LIABILITY_COPY,
  };
}

export function selectProductCategoryInterestSpreadAttributionSurface(
  snapshots: ProductCategoryTrendSnapshot[],
  options: ProductCategoryInterestSpreadAttributionSelection,
  currentYear: number,
): ProductCategoryInterestSpreadAttributionSurface {
  const surface = buildProductCategoryInterestSpreadAttributionImpl({
    snapshots,
    options,
    currentYear,
    formatRowDisplayValue: formatProductCategoryRowDisplayValue,
    formatYieldValue: formatProductCategoryYieldValue,
  });

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    selected: surface.selected,
    complete: surface.complete,
    incompleteReasons: surface.incompleteReasons,
    summary: surface.summary,
    rows: [
      {
        key: "asset_yield",
        label: "资产端收益率（含TPL）",
        ...surface.rows.assetYield,
        explanation: "资产端收益率变化为当前月减上年同月，不推导利差贡献",
      },
      {
        key: "liability_cost",
        label: "负债端成本率",
        ...surface.rows.liabilityCost,
        explanation: "负债端成本率变化为当前月减上年同月，成本下降显示负值",
      },
      {
        key: "spread",
        label: "资产负债利差（含TPL）",
        ...surface.rows.spread,
        explanation: "含TPL口径利差变化为后端当前月字段减上年同月字段，不由前端推导",
      },
    ],
    details: [
      {
        key: "asset_total",
        label: "资产端合计",
        prior: surface.details.assetTotal.prior,
        current: surface.details.assetTotal.current,
      },
      {
        key: "liability_total",
        label: "负债端合计",
        prior: surface.details.liabilityTotal.prior,
        current: surface.details.liabilityTotal.current,
      },
    ],
  };
}

export function selectProductCategoryLiabilitySideTrendChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilitySideTrendChart | null {
  return selectProductCategoryLiabilitySideTrendChartImpl(
    buildProductCategoryLiabilityModelInput(snapshots),
  );
}

export function selectProductCategoryLiabilityDetailMatrix(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilityDetailMatrix {
  return selectProductCategoryLiabilityDetailMatrixImpl(
    buildProductCategoryLiabilityModelInput(snapshots),
  );
}

export function selectProductCategoryLiabilityDetailTrendRows(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilityDetailTrendRow[] {
  return selectProductCategoryLiabilityDetailTrendRowsImpl(
    buildProductCategoryLiabilityModelInput(snapshots),
  );
}

export function buildProductCategoryLiabilitySideTrendSurface(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilitySideTrendSurface {
  return buildProductCategoryLiabilitySideTrendSurfaceImpl({
    ...buildProductCategoryLiabilityModelInput(snapshots),
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
  }) as ProductCategoryLiabilitySideTrendSurface;
}

/**
 * Table body rows: same row objects as the chosen payload (baseline vs scenario), filtered and sorted only.
 * When `scenarioRows` is non-nullish, it wins; otherwise baseline rows are shown - no client-side rollups.
 */
export function selectProductCategoryDetailRows(
  baselineRows: ProductCategoryPnlRow[] | null | undefined,
  scenarioRows: ProductCategoryPnlRow[] | null | undefined,
): ProductCategoryPnlRow[] {
  const source = scenarioRows ?? baselineRows ?? [];
  return source
    .filter((row) => row.category_id !== "grand_total")
    .sort((left, right) => {
      const leftIndex =
        DISPLAY_ORDER_INDEX.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
      const rightIndex =
        DISPLAY_ORDER_INDEX.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex;
    });
}

export function selectDisplayedProductCategoryGrandTotal<
  T extends Pick<ProductCategoryPnlRow, "business_net_income">,
>(
  scenarioGrand: T | null | undefined,
  baselineGrand: T | null | undefined,
): T | undefined {
  return scenarioGrand ?? baselineGrand ?? undefined;
}

/**
 * Next value for page `selectedDate` when the user has not chosen one yet.
 *
 * - Non-empty `selectedDate` is never overridden (returns `null`).
 * - Missing or empty `report_dates` yields no default (returns `null`).
 * - Otherwise returns the first list element; API list order is authoritative (see backend flow tests).
 */
export function nextDefaultReportDateIfUnset(
  selectedDate: string,
  reportDates: string[] | undefined,
): string | null {
  if (selectedDate) {
    return null;
  }
  if (!reportDates?.length) {
    return null;
  }
  return reportDates[0] ?? "";
}

/** Deep link to ledger PnL for the same `report_date` as the product-category page selection. */
export function buildLedgerPnlHrefForReportDate(reportDate: string): string {
  if (!reportDate) {
    return "/ledger-pnl";
  }
  return `/ledger-pnl?report_date=${encodeURIComponent(reportDate)}`;
}

/** Page-visible copy: product-category PnL intentionally has no standalone `as_of_date` field. */
export const PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY =
  "归属日期：本页不提供独立 as_of_date；请分别查看报告日期和生成时间，二者不互相代替。";

export type ProductCategoryDataHealthState =
  "loading" | "ready" | "degraded" | "empty" | "error";

export type ProductCategoryDataHealth = {
  state: ProductCategoryDataHealthState;
  judgementState: "pending" | "allowed" | "blocked";
  judgementLabel: "等待数据完成" | "可用于经营判断" | "正式判断阻断";
  title: string;
  description: string;
  facts: Array<{ label: string; value: string }>;
  retryTarget: "dates" | "baseline" | null;
};

export function buildProductCategoryDataHealth(input: {
  datesLoading: boolean;
  datesError: boolean;
  reportDates: string[] | undefined;
  selectedDate: string;
  baselineLoading: boolean;
  baselineError: boolean;
  baseline: ProductCategoryPnlPayload | null | undefined;
  meta: ResultMeta | null | undefined;
}): ProductCategoryDataHealth {
  if (input.datesLoading) {
    return {
      state: "loading",
      judgementState: "pending",
      judgementLabel: "等待数据完成",
      title: "报告月份加载中",
      description: "正在确认可用报告月份。",
      facts: [],
      retryTarget: null,
    };
  }
  if (input.datesError) {
    return {
      state: "error",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      title: "报告月份加载失败",
      description: "无法确定可用报告月份，正式基线尚未查询。",
      facts: [],
      retryTarget: "dates",
    };
  }
  if (input.reportDates?.length === 0) {
    return {
      state: "empty",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      title: "暂无可选报告月份",
      description: "日期接口未返回可查询月份。",
      facts: [],
      retryTarget: null,
    };
  }

  const reportDate = input.baseline?.report_date || input.selectedDate;
  const facts: Array<{ label: string; value: string }> = [];
  if (reportDate) {
    facts.push({ label: "报告日期", value: reportDate });
  }

  if (input.baselineError) {
    return {
      state: "error",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      title: "正式基线加载失败",
      description: "当前未展示历史缓存结果，请重新查询正式读模型。",
      facts,
      retryTarget: "baseline",
    };
  }
  if (input.baselineLoading || !input.baseline) {
    return {
      state: "loading",
      judgementState: "pending",
      judgementLabel: "等待数据完成",
      title: "正式基线加载中",
      description: "正在读取所选月份的正式产品分类损益。",
      facts,
      retryTarget: null,
    };
  }

  if (input.meta?.source_version) {
    facts.push({ label: "来源版本", value: input.meta.source_version });
  }
  const detailRowCount = input.baseline.rows.filter(
    (row) => row.category_id !== "grand_total",
  ).length;
  facts.push({ label: "明细", value: `${detailRowCount} 行` });
  if (input.meta?.generated_at) {
    facts.push({ label: "生成时间", value: input.meta.generated_at });
  }

  if (detailRowCount === 0) {
    return {
      state: "empty",
      judgementState: "blocked",
      judgementLabel: "正式判断阻断",
      title: "所选月份暂无产品明细",
      description: "正式读模型已响应，但没有返回可展示的分类行。",
      facts,
      retryTarget: null,
    };
  }

  const formalJudgementAllowed =
    input.meta?.basis === "formal" &&
    input.meta.formal_use_allowed === true &&
    input.meta.scenario_flag === false &&
    input.meta.quality_flag === "ok" &&
    input.meta.vendor_status === "ok" &&
    input.meta.fallback_mode === "none";
  const degraded = !formalJudgementAllowed;
  return {
    state: degraded ? "degraded" : "ready",
    judgementState: degraded ? "blocked" : "allowed",
    judgementLabel: degraded ? "正式判断阻断" : "可用于经营判断",
    title: degraded ? "正式基线需复核" : "正式基线已就绪",
    description: degraded
      ? "数据已返回，但结果元数据未满足正式经营判断门禁，需复核。"
      : "正式读模型已返回当前报告口径。",
    facts,
    retryTarget: null,
  };
}

export type ProductCategoryGovernanceNotice = {
  id: "fallback_mode" | "vendor_status" | "quality_flag";
  text: string;
};

function resultMetaBasisLabel(value: ResultMeta["basis"]): string {
  if (value === "formal") return "正式口径";
  if (value === "scenario") return "情景口径";
  if (value === "analytical") return "分析口径";
  if (value === "mock") return "演示口径";
  return value;
}

function resultMetaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function resultMetaVendorLabel(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function resultMetaFallbackLabel(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

/**
 * Notices for degraded governance signals from a single `result_meta` (typ. formal baseline on first screen).
 * Does not invent dates or categories; only reflects backend-reported fields.
 */
export function collectProductCategoryGovernanceNotices(
  meta: ResultMeta | null | undefined,
): ProductCategoryGovernanceNotice[] {
  if (!meta) {
    return [];
  }
  const out: ProductCategoryGovernanceNotice[] = [];
  if (meta.fallback_mode !== "none") {
    out.push({
      id: "fallback_mode",
      text: `读链路回退中：降级模式=${resultMetaFallbackLabel(meta.fallback_mode)}（仅元数据展示，非前端补算）。`,
    });
  }
  if (
    meta.vendor_status === "vendor_stale" ||
    meta.vendor_status === "vendor_unavailable"
  ) {
    out.push({
      id: "vendor_status",
      text: `供应侧状态需关注：供应商状态=${resultMetaVendorLabel(meta.vendor_status)}。`,
    });
  }
  if (meta.quality_flag !== "ok") {
    out.push({
      id: "quality_flag",
      text: `质量标记需关注：质量标记=${resultMetaQualityLabel(meta.quality_flag)}。`,
    });
  }
  return out;
}

/**
 * One-line evidence that formal vs scenario `result_meta` are separate envelopes (trace/basis not assumed equal).
 */
export function formatProductCategoryDualMetaDistinctLine(
  formalMeta: ResultMeta,
  scenarioMeta: ResultMeta,
): string {
  return `正式与情景分开展示：正式口径=${resultMetaBasisLabel(formalMeta.basis)} 追踪编号=${formalMeta.trace_id}；情景口径=${resultMetaBasisLabel(scenarioMeta.basis)} 追踪编号=${scenarioMeta.trace_id}（两路结果元信息分卡展示，不混用）。`;
}

export function isProductCategoryAttributionTotalRow(
  row: ProductCategoryAttributionRow,
): boolean {
  return (
    row.category_id.endsWith("_total") || row.category_id === "grand_total"
  );
}

export function isProductCategoryAttributionDetailRow(
  row: ProductCategoryAttributionRow,
): boolean {
  return !isProductCategoryAttributionTotalRow(row);
}
