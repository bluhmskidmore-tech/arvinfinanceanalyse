import type {
  DecimalLike,
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";

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
    (PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS as readonly string[]).includes(view),
  );
}

/** True when the API surface includes both views required by the main-page selector. */
export function availableViewsSupportMainPageSelector(availableViews: string[]): boolean {
  return PRODUCT_CATEGORY_MAIN_PAGE_VIEWS.every((view) => availableViews.includes(view));
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

export function formatProductCategoryReportMonthLabel(reportDate: string): string {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return reportDate;
  }
  return `${match[1]}\u5e74${match[2]}\u6708`;
}

function parseProductCategoryReportDate(
  reportDate: string,
): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return null;
  }
  return { year, month };
}

function productCategoryReportMonthPrefix(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}-`;
}

function formatProductCategoryShortMonthLabel(month: number): string {
  return `${month}\u6708`;
}

function findProductCategoryReportDateForMonth(
  reportDates: string[],
  year: number,
  month: number,
  selectedDate: string,
): string | null {
  const prefix = productCategoryReportMonthPrefix(year, month);
  if (selectedDate.startsWith(prefix)) {
    return selectedDate;
  }
  return reportDates.find((reportDate) => reportDate.startsWith(prefix)) ?? null;
}

function pushUniqueProductCategoryTrendPoint(
  points: ProductCategoryTrendReportPoint[],
  point: ProductCategoryTrendReportPoint,
): void {
  if (points.some((existing) => existing.reportDate === point.reportDate && existing.view === point.view)) {
    return;
  }
  points.push(point);
}

export const PRODUCT_CATEGORY_VALUE_TONE_COLORS = {
  default: designTokens.color.neutral[900],
  positive: designTokens.color.semantic.profit,
  negative: designTokens.color.semantic.loss,
} as const;

const YUAN_PER_YI = 100_000_000;
const DAYS_IN_YEAR = 365;

export type ProductCategoryTrendSnapshot = {
  reportDate: string;
  label?: string;
  view?: string;
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
};

export type ProductCategoryTrendReportPoint = {
  reportDate: string;
  view: string;
  label: string;
};

export type ProductCategoryDiagnosticsMatrixRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  scaleLabel: string;
  scaleMissing: boolean;
  businessNetIncomeLabel: string;
  businessNetIncomeTone: "neutral" | "positive" | "negative";
  yieldLabel: string;
  yieldMissing: boolean;
  cnyNetLabel: string;
  cnyNetTone: "neutral" | "positive" | "negative";
  foreignNetLabel: string;
  foreignNetTone: "neutral" | "positive" | "negative";
  driverHint: string;
};

export type ProductCategoryNegativeContributionRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  lossLabel: string;
  scaleLabel: string;
  scaleMissing: boolean;
  yieldLabel: string;
  yieldMissing: boolean;
  driverHint: string;
};

type ProductCategorySpreadMovementAttributionBase = {
  currentLabel: string;
  priorLabel: string;
  currentAssetYieldLabel: string;
  currentLiabilityYieldLabel: string;
  currentSpreadLabel: string;
  priorSpreadLabel: string;
  assetYieldDeltaLabel: string;
  liabilityYieldDeltaLabel: string;
  spreadDeltaLabel: string;
  driverHint: string;
};

export type ProductCategorySpreadMovementAttribution =
  | ({
      state: "ready";
    } & ProductCategorySpreadMovementAttributionBase)
  | ({
      state: "incomplete";
      reason: string;
    } & ProductCategorySpreadMovementAttributionBase);

export type ProductCategoryDiagnosticsSurface = {
  headlineTotalLabel: string | null;
  matrixRows: ProductCategoryDiagnosticsMatrixRow[];
  matrixEmptyCopy: string | null;
  negativeWatchlistRows: ProductCategoryNegativeContributionRow[];
  negativeWatchlistEmptyCopy: string | null;
  spreadAttribution: ProductCategorySpreadMovementAttribution;
};

export type ProductCategoryOperatingContributionRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  netIncome: number;
  netIncomeLabel: string;
  contributionPct: number | null;
  contributionLabel: string;
  tone: "positive" | "negative";
};

export type ProductCategoryOperatingMovementRow = {
  categoryId: string;
  categoryLabel: string;
  delta: number;
  deltaLabel: string;
  leadingDriverKey: keyof Pick<
    ProductCategoryAttributionRow["effects"],
    | "day_effect"
    | "scale_effect"
    | "rate_effect"
    | "ftp_effect"
    | "direct_effect"
    | "unexplained_effect"
  >;
  leadingDriverLabel: string;
  leadingDriverValue: number;
  leadingDriverValueLabel: string;
  closureErrorLabel: string;
};

export type ProductCategoryOperatingQuadrant =
  | "core_profit_pool"
  | "scale_efficiency_watch"
  | "selective_growth"
  | "shrink_or_reprice";

export type ProductCategoryOperatingQuadrantRow = {
  categoryId: string;
  categoryLabel: string;
  scale: number;
  scaleLabel: string;
  yieldPct: number;
  yieldLabel: string;
  netIncome: number | null;
  netIncomeLabel: string;
  quadrant: ProductCategoryOperatingQuadrant;
  quadrantLabel: string;
};

export type ProductCategoryOperatingActionKind =
  | "shrink_or_limit"
  | "review_attribution"
  | "reprice_or_improve"
  | "selective_growth";

export type ProductCategoryOperatingActionQueueRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  triggerLabel: string;
  primaryMetricLabel: string;
  evidenceItems: string[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingAnalysisSurface = {
  contribution: {
    grandTotalLabel: string | null;
    profitRows: ProductCategoryOperatingContributionRow[];
    pressureRows: ProductCategoryOperatingContributionRow[];
    emptyCopy: string | null;
  };
  movement: {
    rows: ProductCategoryOperatingMovementRow[];
    emptyCopy: string | null;
  };
  quadrant: {
    scaleBenchmark: number | null;
    yieldBenchmark: number | null;
    scaleBenchmarkLabel: string;
    yieldBenchmarkLabel: string;
    rows: ProductCategoryOperatingQuadrantRow[];
    emptyCopy: string | null;
  };
  actionQueue: {
    rows: ProductCategoryOperatingActionQueueRow[];
    emptyCopy: string | null;
  };
};

export type ProductCategoryOperatingBacktestActionRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  signalCount: number;
  hitCount: number;
  hitRate: number | null;
  hitRateLabel: string;
  averageNetIncomeDelta: number | null;
  averageNetIncomeDeltaLabel: string;
  averageYieldDeltaBp: number | null;
  averageYieldDeltaBpLabel: string;
  averageScaleDelta: number | null;
  averageScaleDeltaLabel: string;
  evidenceLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestMissReasonKey =
  | "net_income_not_improved"
  | "yield_not_improved"
  | "scale_not_expanded"
  | "positive_contribution_missing"
  | "attribution_not_reduced"
  | "scale_mismatch"
  | "net_income_drag"
  | "outcome_not_improved";

export type ProductCategoryOperatingBacktestMissReasonRow = {
  reasonKey: ProductCategoryOperatingBacktestMissReasonKey;
  reasonLabel: string;
  sampleCount: number;
  sampleShareLabel: string;
};

export type ProductCategoryOperatingBacktestMissActionRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  missCount: number;
  comparableCount: number;
  missRate: number | null;
  missRateLabel: string;
  primaryReasonLabel: string;
  reasonRows: ProductCategoryOperatingBacktestMissReasonRow[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestExample = {
  reportDate: string;
  nextReportDate: string;
  categoryId: string;
  categoryLabel: string;
  priorityLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  outcomeLabel: string;
  netIncomeDelta: number | null;
  netIncomeDeltaLabel: string;
  yieldDeltaBp: number | null;
  yieldDeltaBpLabel: string;
  scaleDelta: number | null;
  scaleDeltaLabel: string;
  missReasonKeys: ProductCategoryOperatingBacktestMissReasonKey[];
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestSurface = {
  summary: {
    evaluatedMonthCount: number;
    signalCount: number;
    latestPendingCount: number;
    coverageLabel: string;
    evidenceLabel: string;
  };
  coverageRows: Array<{
    reportDate: string;
    nextReportDate: string | null;
    statusLabel: string;
    signalCount: number;
    tone: "positive" | "negative" | "neutral";
  }>;
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
  examples: ProductCategoryOperatingBacktestExample[];
  emptyCopy: string | null;
};

export type ProductCategoryScenarioSensitivityRow = {
  rate: string;
  ratePct: number;
  rateLabel: string;
  assetDelta: number | null;
  assetNetIncomeLabel: string;
  assetDeltaLabel: string;
  liabilityDelta: number | null;
  liabilityNetIncomeLabel: string;
  liabilityDeltaLabel: string;
  grandNetIncome: number | null;
  grandDelta: number | null;
  grandNetIncomeLabel: string;
  grandDeltaLabel: string;
  topMoverCategoryLabel: string;
  topMoverDelta: number | null;
  topMoverDeltaLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioInsightCard = {
  key: "best_case" | "worst_case" | "range" | "ftp_slope";
  label: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioRiskRow = {
  categoryLabel: string;
  worstRateLabel: string;
  worstDelta: number | null;
  worstDeltaLabel: string;
  occurrenceLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioPathPoint = {
  rateLabel: string;
  grandNetIncomeLabel: string;
  grandDeltaLabel: string;
  positionPct: number;
  positionClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioActionItem = {
  title: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioHeatRow = {
  categoryLabel: string;
  exposureLabel: string;
  widthPct: number;
  widthClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioComparisonCell = {
  rate: string;
  ratePct: number;
  rateLabel: string;
  netIncome: number | null;
  netIncomeLabel: string;
  delta: number | null;
  deltaLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioComparisonRow = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  baselineNetIncome: number | null;
  baselineNetIncomeLabel: string;
  cells: ProductCategoryScenarioComparisonCell[];
  bestRateLabel: string;
  bestDelta: number | null;
  bestDeltaLabel: string;
  worstRateLabel: string;
  worstDelta: number | null;
  worstDeltaLabel: string;
  range: number | null;
  rangeLabel: string;
  maxAbsDelta: number;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioActionClosureRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  exposure: number;
  exposureLabel: string;
  scenarioNetIncomeLabel: string;
  recommendationLabel: string;
  evidenceItems: string[];
  memoLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioBreakeven = {
  label: string;
  valueLabel: string;
  detailLabel: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export type ProductCategoryScenarioSideOffset = {
  rateLabel: string;
  totalDeltaLabel: string;
  assetDeltaLabel: string;
  liabilityDeltaLabel: string;
  offsetLabel: string;
  conclusionLabel: string;
  assetWidthClassName: string;
  liabilityWidthClassName: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioReviewRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  delta: number;
  deltaLabel: string;
  actionLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioPressureSummary = {
  breakeven: ProductCategoryScenarioBreakeven;
  sideOffset: ProductCategoryScenarioSideOffset;
  reviewRows: ProductCategoryScenarioReviewRow[];
};

export type ProductCategoryScenarioExplanationDriverRow = {
  key: keyof Pick<
    ProductCategoryAttributionRow["effects"],
    "ftp_effect" | "scale_effect" | "rate_effect" | "unexplained_effect"
  >;
  label: string;
  value: number | null;
  valueLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryScenarioExplanation = {
  categoryId: string;
  categoryLabel: string;
  sideLabel: string;
  triggerRateLabel: string;
  scenarioDeltaLabel: string;
  baselineNetIncomeLabel: string;
  scenarioNetIncomeLabel: string;
  summaryLabel: string;
  bridgeLabel: string;
  bridgeConclusionLabel: string;
  bridgeTone: "positive" | "negative" | "neutral" | "warning";
  reviewActionItems: string[];
  driverRows: ProductCategoryScenarioExplanationDriverRow[];
  emptyCopy: string | null;
};

export type ProductCategoryScenarioSensitivitySurface = {
  baselineGrandTotalLabel: string | null;
  rows: ProductCategoryScenarioSensitivityRow[];
  insightCards: ProductCategoryScenarioInsightCard[];
  riskRows: ProductCategoryScenarioRiskRow[];
  pathPoints: ProductCategoryScenarioPathPoint[];
  actionItems: ProductCategoryScenarioActionItem[];
  heatRows: ProductCategoryScenarioHeatRow[];
  comparisonRows: ProductCategoryScenarioComparisonRow[];
  actionClosureRows: ProductCategoryScenarioActionClosureRow[];
  pressureSummary: ProductCategoryScenarioPressureSummary;
  analysisCopy: string | null;
  emptyCopy: string | null;
};

export type ProductCategoryAttributionWaterfallKey =
  | "prior"
  | "day_effect"
  | "scale_effect"
  | "rate_effect"
  | "ftp_effect"
  | "direct_effect"
  | "unexplained_effect"
  | "closure_error"
  | "current";

export type ProductCategoryAttributionWaterfallRow = {
  key: ProductCategoryAttributionWaterfallKey;
  label: string;
  value: number | null;
  valueLabel: string;
  cumulative: number | null;
  cumulativeLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryAttributionWaterfallSurface = {
  title: string;
  deltaLabel: string;
  rows: ProductCategoryAttributionWaterfallRow[];
  emptyCopy: string | null;
};

export type ProductCategoryRootCauseDriverKey =
  | "scale_effect"
  | "rate_effect"
  | "ftp_effect"
  | "direct_effect"
  | "unexplained_effect"
  | "closure_error";

export type ProductCategoryRootCauseDriverRow = {
  key: ProductCategoryRootCauseDriverKey;
  label: string;
  value: number;
  valueLabel: string;
  sharePct: number | null;
  shareLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryRootCauseSurface = {
  headline: {
    categoryId: string;
    categoryLabel: string;
    delta: number;
    deltaLabel: string;
    driverLabel: string;
    driverValueLabel: string;
    currentNetIncomeLabel: string;
    priorNetIncomeLabel: string;
    scaleLabel: string;
    yieldLabel: string;
    conclusionLabel: string;
    tone: "positive" | "negative" | "neutral";
  } | null;
  driverRows: ProductCategoryRootCauseDriverRow[];
  evidenceItems: string[];
  emptyCopy: string | null;
};

export type ProductCategoryDecisionFocusKey =
  | "top_contributor"
  | "top_pressure"
  | "largest_deterioration"
  | "largest_unexplained";

export type ProductCategoryDecisionFocusItem = {
  key: ProductCategoryDecisionFocusKey;
  categoryId: string;
  categoryLabel: string;
  reasonLabel: string;
  primaryLabel: string;
  secondaryLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryDecisionFocusSurface = {
  items: ProductCategoryDecisionFocusItem[];
  emptyCopy: string | null;
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

export type ProductCategoryInterestSpreadChart = {
  labels: string[];
  assetYield: number[];
  liabilityYield: number[];
  spread: number[];
};

export type ProductCategoryInterestSpreadYearComparisonChart = {
  labels: string[];
  monthKeys: number[];
  series: Array<{
    year: string;
    spread: Array<number | null>;
  }>;
};

export type ProductCategoryIntermediateBusinessIncomeYearComparisonChart = {
  labels: string[];
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
  key: "interest_earning_assets" | "liability_total";
  label: string;
  prior: ProductCategoryInterestSpreadAttributionDetailPoint;
  current: ProductCategoryInterestSpreadAttributionDetailPoint;
};

export type ProductCategoryInterestSpreadAttributionSurface = {
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
  chart: ProductCategoryLiabilitySideTrendChart | null;
  detailRows: ProductCategoryLiabilityDetailTrendRow[];
  detailMatrix: ProductCategoryLiabilityDetailMatrix;
  emptyCopy: string | null;
  incompleteReasons: string[];
};

export function formatProductCategoryValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return (parsed / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryAttributionEffect(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  return formatProductCategoryValue(value, digits);
}

export function formatProductCategoryRowDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  if (row.side === "liability") {
    return (Math.abs(parsed) / YUAN_PER_YI).toFixed(digits);
  }
  return (parsed / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryYieldValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

export function toneForProductCategoryValue(value: DecimalLike | null | undefined): string {
  if (value === null || value === undefined) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  if (parsed > 0) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.positive;
  }
  if (parsed < 0) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.negative;
  }
  return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
}

function decimalNumber(value: DecimalLike | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function yiNumber(value: DecimalLike | null | undefined): number | null {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return null;
  }
  return Number((parsed / YUAN_PER_YI).toFixed(2));
}

function percentNumber(value: DecimalLike | null | undefined): number | null {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return null;
  }
  return Number(parsed.toFixed(2));
}

function toneNameForValue(value: DecimalLike | null | undefined): "neutral" | "positive" | "negative" {
  const parsed = decimalNumber(value);
  if (parsed === null || parsed === 0) {
    return "neutral";
  }
  return parsed > 0 ? "positive" : "negative";
}

function formatSignedProductCategoryYi(value: number | null): string {
  return signedYiDeltaLabel(value);
}

function productCategoryPercentLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return `${value.toFixed(1)}%`;
}

function productCategoryYiNumberLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function nonTotalProductCategoryRows(rows: ProductCategoryPnlRow[]): ProductCategoryPnlRow[] {
  return rows.filter((row) => !row.is_total && !row.category_id.endsWith("_total") && row.category_id !== "grand_total");
}

function leafProductCategoryRows(rows: ProductCategoryPnlRow[]): ProductCategoryPnlRow[] {
  return nonTotalProductCategoryRows(rows).filter((row) => row.children.length === 0);
}

function parentProductCategoryIds(rows: ProductCategoryPnlRow[]): Set<string> {
  return new Set(nonTotalProductCategoryRows(rows).filter((row) => row.children.length > 0).map((row) => row.category_id));
}

function medianProductCategoryNumber(values: number[]): number | null {
  const sorted = values.filter(Number.isFinite).slice().sort((left, right) => left - right);
  if (sorted.length === 0) {
    return null;
  }
  const midpoint = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[midpoint] ?? null;
  }
  const left = sorted[midpoint - 1];
  const right = sorted[midpoint];
  return left === undefined || right === undefined ? null : (left + right) / 2;
}

const PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS = {
  scale_effect: "规模因素",
  rate_effect: "利率因素",
  day_effect: "天数因素",
  ftp_effect: "FTP因素",
  direct_effect: "直接因素",
  unexplained_effect: "未解释",
} as const;

const PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS = Object.keys(
  PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS,
) as Array<keyof typeof PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS>;

function productCategoryQuadrantLabel(quadrant: ProductCategoryOperatingQuadrant): string {
  if (quadrant === "core_profit_pool") {
    return "核心利润池";
  }
  if (quadrant === "scale_efficiency_watch") {
    return "高规模低收益";
  }
  if (quadrant === "selective_growth") {
    return "低规模高收益";
  }
  return "低规模低收益";
}

function productCategoryQuadrantForPoint(input: {
  scale: number;
  yieldPct: number;
  scaleBenchmark: number;
  yieldBenchmark: number;
}): ProductCategoryOperatingQuadrant {
  const highScale = input.scale >= input.scaleBenchmark;
  const highYield = input.yieldPct > input.yieldBenchmark;
  if (highScale && highYield) {
    return "core_profit_pool";
  }
  if (highScale) {
    return "scale_efficiency_watch";
  }
  if (highYield) {
    return "selective_growth";
  }
  return "shrink_or_reprice";
}

function selectProductCategoryOperatingContribution(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
}): ProductCategoryOperatingAnalysisSurface["contribution"] {
  const candidates = leafProductCategoryRows(input.rows)
    .map((row) => {
      const value = yiNumber(row.business_net_income);
      if (value === null || value === 0) {
        return null;
      }
      const grandTotal = yiNumber(input.grandTotal?.business_net_income);
      const denominator = grandTotal !== null && grandTotal !== 0
        ? Math.abs(grandTotal)
        : null;
      const contributionPct = denominator ? Number((value / denominator * 100).toFixed(1)) : null;
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name || row.category_id,
        sideLabel: productCategorySideLabel(row.side),
        netIncome: value,
        netIncomeLabel: value.toFixed(2),
        contributionPct,
        contributionLabel: productCategoryPercentLabel(contributionPct),
        tone: value > 0 ? "positive" as const : "negative" as const,
      };
    })
    .filter((row): row is ProductCategoryOperatingContributionRow => row !== null);
  const profitRows = candidates
    .filter((row) => row.netIncome > 0)
    .sort((left, right) => right.netIncome - left.netIncome)
    .slice(0, 5);
  const pressureRows = candidates
    .filter((row) => row.netIncome < 0)
    .sort((left, right) => left.netIncome - right.netIncome)
    .slice(0, 5);
  return {
    grandTotalLabel: input.grandTotal ? formatProductCategoryValue(input.grandTotal.business_net_income) : null,
    profitRows,
    pressureRows,
    emptyCopy: profitRows.length === 0 && pressureRows.length === 0
      ? "当前正式表没有可排序的产品贡献。"
      : null,
  };
}

function buildProductCategoryOperatingMovementRows(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  parentCategoryIds: Set<string>,
): ProductCategoryOperatingMovementRow[] {
  if (!attribution || attribution.state !== "complete") {
    return [];
  }
  const rows: ProductCategoryOperatingMovementRow[] = [];
  for (const row of attribution.rows) {
    if (row.category_id.endsWith("_total") || row.category_id === "grand_total" || parentCategoryIds.has(row.category_id)) {
      continue;
    }
    const delta = yiNumber(row.effects.delta_business_net_income);
    if (delta === null || delta === 0) {
      continue;
    }
    const leadingDriverKey = PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS.reduce((best, key) => {
      const bestValue = Math.abs(yiNumber(row.effects[best]) ?? 0);
      const currentValue = Math.abs(yiNumber(row.effects[key]) ?? 0);
      return currentValue > bestValue ? key : best;
    }, PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS[0]);
    const leadingDriverValue = yiNumber(row.effects[leadingDriverKey]) ?? 0;
    rows.push({
      categoryId: row.category_id,
      categoryLabel: row.category_name || row.category_id,
      delta,
      deltaLabel: formatSignedProductCategoryYi(delta),
      leadingDriverKey,
      leadingDriverLabel: PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS[leadingDriverKey],
      leadingDriverValue,
      leadingDriverValueLabel: formatSignedProductCategoryYi(leadingDriverValue),
      closureErrorLabel: formatSignedProductCategoryYi(yiNumber(row.effects.closure_error)),
    });
  }
  rows.sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
  return rows;
}

function selectProductCategoryOperatingMovement(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  parentCategoryIds: Set<string>,
): ProductCategoryOperatingAnalysisSurface["movement"] {
  if (!attribution || attribution.state !== "complete") {
    return {
      rows: [],
      emptyCopy: "当前缺少可用的月度经营差异归因。",
    };
  }
  const rows = buildProductCategoryOperatingMovementRows(attribution, parentCategoryIds);
  const topRows = rows.slice(0, 5);
  return {
    rows: topRows,
    emptyCopy: topRows.length === 0 ? "当前归因结果没有显著变动项。" : null,
  };
}

function selectProductCategoryOperatingQuadrant(
  rows: ProductCategoryPnlRow[],
  options: { limit?: number | null } = {},
): ProductCategoryOperatingAnalysisSurface["quadrant"] {
  const candidates = leafProductCategoryRows(rows)
    .map((row) => {
      const scale = yiNumber(row.cnx_scale);
      const yieldPct = percentNumber(row.weighted_yield);
      const netIncome = yiNumber(row.business_net_income);
      if (scale === null || yieldPct === null || scale <= 0) {
        return null;
      }
      return {
        row,
        scale,
        yieldPct,
        netIncome,
        netIncomeLabel: netIncome !== null ? netIncome.toFixed(2) : "-",
      };
    })
    .filter((row): row is {
      row: ProductCategoryPnlRow;
      scale: number;
      yieldPct: number;
      netIncome: number | null;
      netIncomeLabel: string;
    } => row !== null);
  const scaleBenchmark = medianProductCategoryNumber(candidates.map((item) => item.scale));
  const yieldBenchmark = medianProductCategoryNumber(candidates.map((item) => item.yieldPct));
  if (scaleBenchmark === null || yieldBenchmark === null) {
    return {
      scaleBenchmark: null,
      yieldBenchmark: null,
      scaleBenchmarkLabel: "-",
      yieldBenchmarkLabel: "-",
      rows: [],
      emptyCopy: "当前缺少可用于规模/收益率象限的规模或收益率。",
    };
  }
  const quadrantRows = candidates
    .map((item) => {
      const quadrant = productCategoryQuadrantForPoint({
        scale: item.scale,
        yieldPct: item.yieldPct,
        scaleBenchmark,
        yieldBenchmark,
      });
      return {
        categoryId: item.row.category_id,
        categoryLabel: item.row.category_name || item.row.category_id,
        scale: item.scale,
        scaleLabel: item.scale.toFixed(2),
        yieldPct: item.yieldPct,
        yieldLabel: item.yieldPct.toFixed(2),
        netIncome: item.netIncome,
        netIncomeLabel: item.netIncomeLabel,
        quadrant,
        quadrantLabel: productCategoryQuadrantLabel(quadrant),
      };
    })
    .sort((left, right) => right.scale - left.scale);
  const displayRows = options.limit === null ? quadrantRows : quadrantRows.slice(0, options.limit ?? 12);
  return {
    scaleBenchmark,
    yieldBenchmark,
    scaleBenchmarkLabel: scaleBenchmark.toFixed(2),
    yieldBenchmarkLabel: yieldBenchmark.toFixed(2),
    rows: displayRows,
    emptyCopy: displayRows.length === 0 ? "当前缺少可用于规模/收益率象限的产品行。" : null,
  };
}

function productCategoryOperatingActionRow(input: {
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  triggerLabel: string;
  primaryMetricLabel: string;
  evidenceItems: string[];
  tone: "positive" | "negative" | "neutral";
}): Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel"> {
  return input;
}

function selectProductCategoryOperatingActionQueue(input: {
  rows: ProductCategoryPnlRow[];
  attribution?: ProductCategoryAttributionPayload | null;
  parentCategoryIds: Set<string>;
}): ProductCategoryOperatingAnalysisSurface["actionQueue"] {
  const leafRows = leafProductCategoryRows(input.rows);
  const actionRows: Array<Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">> = [];
  const seenCategoryIds = new Set<string>();
  const movementRows = buildProductCategoryOperatingMovementRows(input.attribution, input.parentCategoryIds);
  const quadrant = selectProductCategoryOperatingQuadrant(input.rows, { limit: null });
  const quadrantByCategoryId = new Map(quadrant.rows.map((row) => [row.categoryId, row]));
  const appendActionRow = (row: Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">) => {
    if (seenCategoryIds.has(row.categoryId)) {
      return;
    }
    seenCategoryIds.add(row.categoryId);
    actionRows.push(row);
  };

  const lowYieldLoss = leafRows
    .map((row) => {
      const netIncome = yiNumber(row.business_net_income);
      const scale = yiNumber(row.cnx_scale);
      const yieldPct = percentNumber(row.weighted_yield);
      const movement = movementRows.find((item) => item.categoryId === row.category_id);
      const quadrantRow = quadrantByCategoryId.get(row.category_id);
      const hasLowYield = quadrantRow?.quadrant === "scale_efficiency_watch" || quadrantRow?.quadrant === "shrink_or_reprice";
      if (netIncome === null || netIncome >= 0 || yieldPct === null || scale === null || !hasLowYield) {
        return null;
      }
      return { row, netIncome, scale, yieldPct, movement };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((left, right) => left.netIncome - right.netIncome)[0];

  if (lowYieldLoss) {
    appendActionRow(productCategoryOperatingActionRow({
      categoryId: lowYieldLoss.row.category_id,
      categoryLabel: lowYieldLoss.row.category_name || lowYieldLoss.row.category_id,
      actionKind: "shrink_or_limit",
      actionLabel: "压降或限额复核",
      triggerLabel: "负贡献叠加收益偏低",
      primaryMetricLabel: lowYieldLoss.netIncome.toFixed(2),
      evidenceItems: [
        `净营收 ${lowYieldLoss.netIncome.toFixed(2)} 亿元`,
        `规模 ${lowYieldLoss.scale.toFixed(2)} 亿元`,
        `收益率 ${lowYieldLoss.yieldPct.toFixed(2)}%`,
        `变动 ${lowYieldLoss.movement?.deltaLabel ?? "-"} 亿元`,
      ],
      tone: "negative",
    }));
  }

  const unexplainedReview = movementRows
    .filter((row) => row.leadingDriverKey === "unexplained_effect" && Math.abs(row.leadingDriverValue) > 0)
    .sort((left, right) => Math.abs(right.leadingDriverValue) - Math.abs(left.leadingDriverValue))[0];

  if (unexplainedReview) {
    appendActionRow(productCategoryOperatingActionRow({
      categoryId: unexplainedReview.categoryId,
      categoryLabel: unexplainedReview.categoryLabel,
      actionKind: "review_attribution",
      actionLabel: "归因复核",
      triggerLabel: "未解释差异偏高",
      primaryMetricLabel: unexplainedReview.leadingDriverValueLabel,
      evidenceItems: [
        `未解释 ${unexplainedReview.leadingDriverValueLabel} 亿元`,
        `变动 ${unexplainedReview.deltaLabel} 亿元`,
      ],
      tone: "neutral",
    }));
  }

  const reprice = quadrant.rows.find(
    (row) => row.quadrant === "scale_efficiency_watch" && !seenCategoryIds.has(row.categoryId),
  );
  if (reprice) {
    appendActionRow(productCategoryOperatingActionRow({
      categoryId: reprice.categoryId,
      categoryLabel: reprice.categoryLabel,
      actionKind: "reprice_or_improve",
      actionLabel: "重定价/提效",
      triggerLabel: "高规模低收益",
      primaryMetricLabel: `${reprice.yieldLabel}%`,
      evidenceItems: [
        `规模 ${reprice.scaleLabel} 亿元`,
        `收益率 ${reprice.yieldLabel}%`,
        `净营收 ${reprice.netIncomeLabel} 亿元`,
      ],
      tone: "negative",
    }));
  }

  const selectiveGrowth = quadrant.rows.find(
    (row) =>
      row.quadrant === "selective_growth" &&
      row.netIncome !== null &&
      row.netIncome > 0 &&
      !seenCategoryIds.has(row.categoryId),
  );
  if (selectiveGrowth) {
    appendActionRow(productCategoryOperatingActionRow({
      categoryId: selectiveGrowth.categoryId,
      categoryLabel: selectiveGrowth.categoryLabel,
      actionKind: "selective_growth",
      actionLabel: "选择性扩张",
      triggerLabel: "低规模高收益",
      primaryMetricLabel: `${selectiveGrowth.yieldLabel}%`,
      evidenceItems: [
        `规模 ${selectiveGrowth.scaleLabel} 亿元`,
        `收益率 ${selectiveGrowth.yieldLabel}%`,
        `净营收 ${selectiveGrowth.netIncomeLabel} 亿元`,
      ],
      tone: "positive",
    }));
  }

  const rows = actionRows.map((row, index) => ({
    priorityLabel: `P${index + 1}`,
    ...row,
  }));
  return {
    rows,
    emptyCopy: rows.length === 0 ? "当前没有需要进入经营动作队列的产品分类。" : null,
  };
}

export function selectProductCategoryOperatingAnalysisSurface(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryOperatingAnalysisSurface {
  const parentCategoryIds = parentProductCategoryIds(input.rows);
  return {
    contribution: selectProductCategoryOperatingContribution({
      rows: input.rows,
      grandTotal: input.grandTotal,
    }),
    movement: selectProductCategoryOperatingMovement(input.attribution, parentCategoryIds),
    quadrant: selectProductCategoryOperatingQuadrant(input.rows),
    actionQueue: selectProductCategoryOperatingActionQueue({
      rows: input.rows,
      attribution: input.attribution,
      parentCategoryIds,
    }),
  };
}

function productCategoryRowDeltaYi(
  baselineRowsById: Map<string, ProductCategoryPnlRow>,
  scenarioRow: ProductCategoryPnlRow,
): number | null {
  const baselineRow = baselineRowsById.get(scenarioRow.category_id);
  if (!baselineRow) {
    return null;
  }
  const baselineValue = yiNumber(baselineRow.business_net_income);
  const scenarioValue = yiNumber(scenarioRow.business_net_income);
  if (baselineValue === null || scenarioValue === null) {
    return null;
  }
  return Number((scenarioValue - baselineValue).toFixed(2));
}

function productCategoryDeltaTone(value: number | null): "positive" | "negative" | "neutral" {
  if (value === null || value === 0) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

function productCategoryScenarioAnalysisCopy(
  worst: ProductCategoryScenarioSensitivityRow | undefined,
  best: ProductCategoryScenarioSensitivityRow | undefined,
): string | null {
  if (!worst || !best || worst.grandDelta === null || best.grandDelta === null) {
    return null;
  }
  if (worst.grandDelta < 0) {
    return `FTP 上行时全表净营收承压，最差情景较基线 ${worst.grandDeltaLabel} 亿元。`;
  }
  if (best.grandDelta > 0) {
    return `四档 FTP 情景均未低于基线，最佳情景较基线 ${best.grandDeltaLabel} 亿元。`;
  }
  return "四档 FTP 情景围绕基线窄幅波动，建议结合产品行变动继续复核。";
}

type ProductCategoryComparableScenarioRow = ProductCategoryScenarioSensitivityRow & {
  grandNetIncome: number;
  grandDelta: number;
};

const EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY: ProductCategoryScenarioPressureSummary = {
  breakeven: {
    label: "临界 FTP",
    valueLabel: "-",
    detailLabel: "待加载可比较情景后估算；此处仅做线性插值辅助判断。",
    tone: "neutral",
  },
  sideOffset: {
    rateLabel: "-",
    totalDeltaLabel: "-",
    assetDeltaLabel: "-",
    liabilityDeltaLabel: "-",
    offsetLabel: "-",
    conclusionLabel: "待加载情景矩阵后拆分资产端与负债端冲抵关系。",
    assetWidthClassName: "is-width-0",
    liabilityWidthClassName: "is-width-0",
    tone: "neutral",
  },
  reviewRows: [],
};

function hasComparableScenarioGrandTotal(
  row: ProductCategoryScenarioSensitivityRow,
): row is ProductCategoryComparableScenarioRow {
  return row.grandNetIncome !== null && row.grandDelta !== null;
}

function productCategoryBucketPct(value: number): 0 | 25 | 50 | 75 | 100 {
  if (value <= 12.5) {
    return 0;
  }
  if (value <= 37.5) {
    return 25;
  }
  if (value <= 62.5) {
    return 50;
  }
  if (value <= 87.5) {
    return 75;
  }
  return 100;
}

function selectProductCategoryScenarioInsightCards(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioInsightCard[] {
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  if (comparableRows.length === 0) {
    return [];
  }
  const sortedByGrand = [...comparableRows].sort((left, right) => right.grandNetIncome - left.grandNetIncome);
  const best = sortedByGrand[0];
  const worst = sortedByGrand[sortedByGrand.length - 1];
  const cards: ProductCategoryScenarioInsightCard[] = [
    {
      key: "best_case",
      label: "最佳情景",
      valueLabel: `${best.rateLabel} / ${best.grandNetIncomeLabel}`,
      detailLabel: `较基线 ${best.grandDeltaLabel} 亿元`,
      tone: productCategoryDeltaTone(best.grandDelta),
    },
    {
      key: "worst_case",
      label: "最差情景",
      valueLabel: `${worst.rateLabel} / ${worst.grandNetIncomeLabel}`,
      detailLabel: `较基线 ${worst.grandDeltaLabel} 亿元`,
      tone: productCategoryDeltaTone(worst.grandDelta),
    },
  ];
  const range = Number((best.grandNetIncome - worst.grandNetIncome).toFixed(2));
  cards.push({
    key: "range",
    label: "情景区间",
    valueLabel: productCategoryYiNumberLabel(range),
    detailLabel: `${best.grandNetIncomeLabel} - ${worst.grandNetIncomeLabel} 亿元`,
    tone: "neutral",
  });
  const rateSpanBp = (worst.ratePct - best.ratePct) * 100;
  const slope = rateSpanBp === 0 ? null : Number(((worst.grandNetIncome - best.grandNetIncome) / rateSpanBp).toFixed(2));
  cards.push({
    key: "ftp_slope",
    label: "FTP 斜率",
    valueLabel: productCategoryYiNumberLabel(slope),
    detailLabel: "每 1bp 约影响净营收",
    tone: productCategoryDeltaTone(slope),
  });
  return cards;
}

function selectProductCategoryScenarioRiskRows(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioRiskRow[] {
  const byCategory = new Map<
    string,
    {
      categoryLabel: string;
      count: number;
      worstRateLabel: string;
      worstDelta: number | null;
    }
  >();
  for (const row of rows) {
    if (row.topMoverCategoryLabel === "-" || row.topMoverDelta === null) {
      continue;
    }
    const current = byCategory.get(row.topMoverCategoryLabel);
    if (!current) {
      byCategory.set(row.topMoverCategoryLabel, {
        categoryLabel: row.topMoverCategoryLabel,
        count: 1,
        worstRateLabel: row.rateLabel,
        worstDelta: row.topMoverDelta,
      });
      continue;
    }
    current.count += 1;
    if (current.worstDelta === null || Math.abs(row.topMoverDelta) > Math.abs(current.worstDelta)) {
      current.worstRateLabel = row.rateLabel;
      current.worstDelta = row.topMoverDelta;
    }
  }
  return [...byCategory.values()]
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return Math.abs(right.worstDelta ?? 0) - Math.abs(left.worstDelta ?? 0);
    })
    .slice(0, 3)
    .map((row) => ({
      categoryLabel: row.categoryLabel,
      worstRateLabel: row.worstRateLabel,
      worstDelta: row.worstDelta,
      worstDeltaLabel: formatSignedProductCategoryYi(row.worstDelta),
      occurrenceLabel: `${row.count} 个情景触发最大变动`,
      tone: productCategoryDeltaTone(row.worstDelta),
    }));
}

function selectProductCategoryScenarioPathPoints(
  rows: ProductCategoryScenarioSensitivityRow[],
): ProductCategoryScenarioPathPoint[] {
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  if (comparableRows.length === 0) {
    return [];
  }
  const minRate = Math.min(...comparableRows.map((row) => row.ratePct));
  const maxRate = Math.max(...comparableRows.map((row) => row.ratePct));
  const span = maxRate - minRate;
  return comparableRows.map((row) => ({
    rateLabel: row.rateLabel,
    grandNetIncomeLabel: row.grandNetIncomeLabel,
    grandDeltaLabel: row.grandDeltaLabel,
    positionPct: span === 0 ? 50 : Math.round(((row.ratePct - minRate) / span) * 100),
    positionClassName: `is-position-${productCategoryBucketPct(
      span === 0 ? 50 : Math.round(((row.ratePct - minRate) / span) * 100),
    )}`,
    tone: row.tone,
  }));
}

function selectProductCategoryScenarioActionItems(input: {
  best?: ProductCategoryComparableScenarioRow;
  worst?: ProductCategoryComparableScenarioRow;
  riskRows: ProductCategoryScenarioRiskRow[];
}): ProductCategoryScenarioActionItem[] {
  const items: ProductCategoryScenarioActionItem[] = [];
  if (input.worst?.grandDelta !== null && input.worst?.grandDelta !== undefined) {
    const absoluteDelta = Math.abs(input.worst.grandDelta).toFixed(2);
    items.push({
      title: input.worst.grandDelta < 0 ? "锁定下行情景敞口" : "确认上行情景弹性",
      valueLabel: input.worst.grandDeltaLabel,
      detailLabel: `${input.worst.rateLabel} 情景较基线${input.worst.grandDelta < 0 ? "少" : "多"} ${absoluteDelta} 亿元`,
      tone: productCategoryDeltaTone(input.worst.grandDelta),
    });
  }
  const topRisk = input.riskRows[0];
  if (topRisk) {
    items.push({
      title: `优先复核 ${topRisk.categoryLabel}`,
      valueLabel: topRisk.worstDeltaLabel,
      detailLabel: `最大产品行变动出现在 ${topRisk.worstRateLabel}`,
      tone: topRisk.tone,
    });
  }
  if (input.best && input.worst && input.best.grandNetIncome !== input.worst.grandNetIncome) {
    const range = Number((input.best.grandNetIncome - input.worst.grandNetIncome).toFixed(2));
    items.push({
      title: "设置情景监控阈值",
      valueLabel: productCategoryYiNumberLabel(range),
      detailLabel: "覆盖最佳到最差情景净营收区间",
      tone: "neutral",
    });
  }
  return items.slice(0, 3);
}

function selectProductCategoryScenarioHeatRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioHeatRow[] {
  const exposures = new Map<string, { categoryLabel: string; exposure: number }>();
  for (const scenario of input.scenarios) {
    for (const row of leafProductCategoryRows(scenario.rows)) {
      const delta = productCategoryRowDeltaYi(input.baselineRowsById, row);
      if (delta === null || delta === 0) {
        continue;
      }
      const current = exposures.get(row.category_id);
      if (!current || Math.abs(delta) > Math.abs(current.exposure)) {
        exposures.set(row.category_id, {
          categoryLabel: row.category_name || row.category_id,
          exposure: delta,
        });
      }
    }
  }
  const sorted = [...exposures.values()]
    .sort((left, right) => Math.abs(right.exposure) - Math.abs(left.exposure))
    .slice(0, 4);
  const maxAbs = Math.max(...sorted.map((row) => Math.abs(row.exposure)), 0);
  return sorted.map((row) => ({
    categoryLabel: row.categoryLabel,
    exposureLabel: formatSignedProductCategoryYi(row.exposure),
    widthPct: maxAbs === 0 ? 0 : Math.round((Math.abs(row.exposure) / maxAbs) * 100),
    widthClassName: `is-width-${productCategoryBucketPct(
      maxAbs === 0 ? 0 : Math.round((Math.abs(row.exposure) / maxAbs) * 100),
    )}`,
    tone: productCategoryDeltaTone(row.exposure),
  }));
}

function selectProductCategoryScenarioComparisonRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioComparisonRow[] {
  const scenarioRowsByCategory = new Map<
    string,
    { baselineRow: ProductCategoryPnlRow; scenarioRows: Array<{ rate: string; row: ProductCategoryPnlRow }> }
  >();
  for (const scenario of input.scenarios) {
    const scenarioRate = scenario.scenario_rate_pct;
    if (scenarioRate === null || scenarioRate === undefined) {
      continue;
    }
    for (const scenarioRow of leafProductCategoryRows(scenario.rows)) {
      const baselineRow = input.baselineRowsById.get(scenarioRow.category_id);
      if (!baselineRow) {
        continue;
      }
      const current = scenarioRowsByCategory.get(scenarioRow.category_id);
      if (current) {
        current.scenarioRows.push({ rate: String(scenarioRate), row: scenarioRow });
      } else {
        scenarioRowsByCategory.set(scenarioRow.category_id, {
          baselineRow,
          scenarioRows: [{ rate: String(scenarioRate), row: scenarioRow }],
        });
      }
    }
  }
  const rows: Array<ProductCategoryScenarioComparisonRow | null> = [...scenarioRowsByCategory.entries()]
    .map(([categoryId, entry]) => {
      const baselineNetIncome = yiNumber(entry.baselineRow.business_net_income);
      const cells = entry.scenarioRows
        .map((scenarioEntry) => {
          const rate = scenarioEntry.rate;
          const ratePct = Number(rate);
          const netIncome = yiNumber(scenarioEntry.row.business_net_income);
          const delta = productCategoryRowDeltaYi(input.baselineRowsById, scenarioEntry.row);
          return {
            rate: String(rate),
            ratePct,
            rateLabel: `${ratePct.toFixed(2)}%`,
            netIncome,
            netIncomeLabel: productCategoryYiNumberLabel(netIncome),
            delta,
            deltaLabel: formatSignedProductCategoryYi(delta),
            tone: productCategoryDeltaTone(delta),
          };
        })
        .filter((cell): cell is ProductCategoryScenarioComparisonCell => cell !== null)
        .sort((left, right) => left.ratePct - right.ratePct);
      const comparableCells = cells.filter((cell): cell is ProductCategoryScenarioComparisonCell & {
        delta: number;
        netIncome: number;
      } => cell.delta !== null && cell.netIncome !== null);
      if (comparableCells.length === 0) {
        return null;
      }
      const best = [...comparableCells].sort((left, right) => right.delta - left.delta)[0];
      const worst = [...comparableCells].sort((left, right) => left.delta - right.delta)[0];
      if (!best || !worst) {
        return null;
      }
      const minNetIncome = Math.min(...comparableCells.map((cell) => cell.netIncome));
      const maxNetIncome = Math.max(...comparableCells.map((cell) => cell.netIncome));
      const range = Number((maxNetIncome - minNetIncome).toFixed(2));
      const maxAbsDelta = Math.max(...comparableCells.map((cell) => Math.abs(cell.delta)), 0);
      return {
        categoryId,
        categoryLabel: entry.baselineRow.category_name || categoryId,
        sideLabel: productCategoryScenarioSideLabel(entry.baselineRow.side),
        baselineNetIncome,
        baselineNetIncomeLabel: productCategoryYiNumberLabel(baselineNetIncome),
        cells,
        bestRateLabel: best.rateLabel,
        bestDelta: best.delta,
        bestDeltaLabel: formatSignedProductCategoryYi(best.delta),
        worstRateLabel: worst.rateLabel,
        worstDelta: worst.delta,
        worstDeltaLabel: formatSignedProductCategoryYi(worst.delta),
        range,
        rangeLabel: productCategoryYiNumberLabel(range),
        maxAbsDelta,
        tone: productCategoryDeltaTone(worst.delta),
      };
    });
  return rows
    .filter((row): row is ProductCategoryScenarioComparisonRow => row !== null)
    .sort((left, right) => right.maxAbsDelta - left.maxAbsDelta);
}

function productCategoryScenarioClosureRecommendation(row: ProductCategoryScenarioComparisonRow): string {
  if (row.sideLabel === "负债端") {
    return "复核负债成本、FTP 曲线与定价传导";
  }
  if (row.worstDelta !== null && row.worstDelta <= -0.5) {
    return "压降 FTP 敞口并复核规模、收益率输入";
  }
  return "复核 FTP 敞口、规模与收益率输入";
}

function selectProductCategoryScenarioActionClosureRows(
  comparisonRows: ProductCategoryScenarioComparisonRow[],
): ProductCategoryScenarioActionClosureRow[] {
  return comparisonRows
    .filter((row) => row.worstDelta !== null && row.worstDelta < 0)
    .sort((left, right) => Math.abs(right.worstDelta ?? 0) - Math.abs(left.worstDelta ?? 0))
    .slice(0, 4)
    .map((row, index) => {
      const worstCell = row.cells.find((cell) => cell.rateLabel === row.worstRateLabel);
      const scenarioNetIncomeLabel = worstCell?.netIncomeLabel ?? "-";
      const recommendationLabel = productCategoryScenarioClosureRecommendation(row);
      return {
        priorityLabel: `动作 ${index + 1}`,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        sideLabel: row.sideLabel,
        triggerRateLabel: row.worstRateLabel,
        exposure: row.worstDelta ?? 0,
        exposureLabel: row.worstDeltaLabel,
        scenarioNetIncomeLabel,
        recommendationLabel,
        evidenceItems: [
          `正式基线净营收 ${row.baselineNetIncomeLabel} 亿元`,
          `${row.worstRateLabel} 情景净营收 ${scenarioNetIncomeLabel} 亿元`,
          `较基线 ${row.worstDeltaLabel} 亿元`,
        ],
        memoLabel: `${row.categoryLabel}在 ${row.worstRateLabel} 情景较基线 ${row.worstDeltaLabel} 亿元；${recommendationLabel}。`,
        tone: row.tone,
      };
    });
}

function productCategoryScenarioBaselineRelation(delta: number): string {
  if (delta > 0) {
    return `高于基线 ${formatSignedProductCategoryYi(delta)}`;
  }
  if (delta < 0) {
    return `低于基线 ${formatSignedProductCategoryYi(delta)}`;
  }
  return "与基线持平 0.00";
}

function selectProductCategoryScenarioBreakeven(
  comparableRows: ProductCategoryComparableScenarioRow[],
): ProductCategoryScenarioBreakeven {
  if (comparableRows.length === 0) {
    return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.breakeven;
  }
  const sortedByRate = [...comparableRows].sort((left, right) => left.ratePct - right.ratePct);
  const exact = sortedByRate.find((row) => row.grandDelta === 0);
  if (exact) {
    return {
      label: "临界 FTP",
      valueLabel: `约 ${exact.ratePct.toFixed(2)}%`,
      detailLabel: `${exact.rateLabel} 情景与正式基线持平；此处仅做情景辅助判断。`,
      tone: "neutral",
    };
  }
  for (let index = 1; index < sortedByRate.length; index += 1) {
    const left = sortedByRate[index - 1];
    const right = sortedByRate[index];
    if (!left || !right || left.grandDelta * right.grandDelta > 0) {
      continue;
    }
    const deltaSpan = right.grandDelta - left.grandDelta;
    if (deltaSpan === 0) {
      continue;
    }
    const rate = left.ratePct + ((0 - left.grandDelta) / deltaSpan) * (right.ratePct - left.ratePct);
    return {
      label: "临界 FTP",
      valueLabel: `约 ${rate.toFixed(2)}%`,
      detailLabel: `线性插值：${left.rateLabel} ${productCategoryScenarioBaselineRelation(
        left.grandDelta,
      )}，${right.rateLabel} ${productCategoryScenarioBaselineRelation(right.grandDelta)}`,
      tone: "warning",
    };
  }
  const best = [...sortedByRate].sort((left, right) => right.grandDelta - left.grandDelta)[0];
  const worst = [...sortedByRate].sort((left, right) => left.grandDelta - right.grandDelta)[0];
  if (worst && worst.grandDelta > 0) {
    return {
      label: "临界 FTP",
      valueLabel: `高于 ${sortedByRate[sortedByRate.length - 1]?.rateLabel ?? "-"}`,
      detailLabel: `已加载情景均高于基线，最低差额 ${worst.grandDeltaLabel}；未在当前区间触发临界点。`,
      tone: "positive",
    };
  }
  if (best && best.grandDelta < 0) {
    return {
      label: "临界 FTP",
      valueLabel: `低于 ${sortedByRate[0]?.rateLabel ?? "-"}`,
      detailLabel: `已加载情景均低于基线，最高差额 ${best.grandDeltaLabel}；需复核情景输入或基线安全垫。`,
      tone: "negative",
    };
  }
  return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.breakeven;
}

function selectProductCategoryScenarioSideOffset(
  worst: ProductCategoryComparableScenarioRow | undefined,
): ProductCategoryScenarioSideOffset {
  if (!worst || worst.assetDelta === null || worst.liabilityDelta === null) {
    return EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY.sideOffset;
  }
  const totalAbs = Math.abs(worst.assetDelta) + Math.abs(worst.liabilityDelta);
  const assetWidth = totalAbs === 0 ? 0 : Math.round((Math.abs(worst.assetDelta) / totalAbs) * 100);
  const liabilityWidth =
    totalAbs === 0 ? 0 : Math.round((Math.abs(worst.liabilityDelta) / totalAbs) * 100);
  const hasOffset = worst.assetDelta * worst.liabilityDelta < 0;
  const offset = hasOffset ? Math.min(Math.abs(worst.assetDelta), Math.abs(worst.liabilityDelta)) : 0;
  let conclusionLabel = "资产端与负债端变化较小，当前情景未形成显著冲抵。";
  if (hasOffset) {
    conclusionLabel = `资产端与负债端形成 ${productCategoryYiNumberLabel(
      offset,
    )} 亿元冲抵，净影响 ${worst.grandDeltaLabel}。`;
  } else if (worst.grandDelta < 0) {
    conclusionLabel = "资产端与负债端同向承压，未形成冲抵。";
  } else if (worst.grandDelta > 0) {
    conclusionLabel = "资产端与负债端同向改善，未形成冲抵。";
  }
  return {
    rateLabel: worst.rateLabel,
    totalDeltaLabel: worst.grandDeltaLabel,
    assetDeltaLabel: formatSignedProductCategoryYi(worst.assetDelta),
    liabilityDeltaLabel: formatSignedProductCategoryYi(worst.liabilityDelta),
    offsetLabel: productCategoryYiNumberLabel(offset),
    conclusionLabel,
    assetWidthClassName: `is-width-${productCategoryBucketPct(assetWidth)}`,
    liabilityWidthClassName: `is-width-${productCategoryBucketPct(liabilityWidth)}`,
    tone: productCategoryDeltaTone(worst.grandDelta),
  };
}

function productCategoryScenarioSideLabel(side: string): string {
  if (side === "asset") {
    return "资产端";
  }
  if (side === "liability") {
    return "负债端";
  }
  return side || "-";
}

function productCategoryScenarioReviewAction(tone: "positive" | "negative" | "neutral"): string {
  if (tone === "negative") {
    return "复核 FTP 敞口、规模与收益率输入";
  }
  if (tone === "positive") {
    return "确认情景收益改善来源可持续";
  }
  return "核对情景输入与产品行映射";
}

function selectProductCategoryScenarioReviewRows(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioReviewRow[] {
  const reviewByCategory = new Map<
    string,
    {
      categoryId: string;
      categoryLabel: string;
      sideLabel: string;
      triggerRateLabel: string;
      delta: number;
    }
  >();
  for (const scenario of input.scenarios) {
    const scenarioRate = decimalNumber(scenario.scenario_rate_pct);
    const triggerRateLabel = scenarioRate === null ? "-" : `${scenarioRate.toFixed(2)}%`;
    for (const row of leafProductCategoryRows(scenario.rows)) {
      const delta = productCategoryRowDeltaYi(input.baselineRowsById, row);
      if (delta === null || delta === 0) {
        continue;
      }
      const existing = reviewByCategory.get(row.category_id);
      if (!existing || Math.abs(delta) > Math.abs(existing.delta)) {
        reviewByCategory.set(row.category_id, {
          categoryId: row.category_id,
          categoryLabel: row.category_name || row.category_id,
          sideLabel: productCategoryScenarioSideLabel(row.side),
          triggerRateLabel,
          delta,
        });
      }
    }
  }
  return [...reviewByCategory.values()]
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))
    .slice(0, 3)
    .map((row, index) => {
      const tone = productCategoryDeltaTone(row.delta);
      return {
        priorityLabel: `复核 ${index + 1}`,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        sideLabel: row.sideLabel,
        triggerRateLabel: row.triggerRateLabel,
        delta: row.delta,
        deltaLabel: formatSignedProductCategoryYi(row.delta),
        actionLabel: productCategoryScenarioReviewAction(tone),
        tone,
      };
    });
}

function selectProductCategoryScenarioPressureSummary(input: {
  baselineRowsById: Map<string, ProductCategoryPnlRow>;
  comparableRows: ProductCategoryComparableScenarioRow[];
  scenarios: ProductCategoryPnlPayload[];
  worst?: ProductCategoryComparableScenarioRow;
}): ProductCategoryScenarioPressureSummary {
  return {
    breakeven: selectProductCategoryScenarioBreakeven(input.comparableRows),
    sideOffset: selectProductCategoryScenarioSideOffset(input.worst),
    reviewRows: selectProductCategoryScenarioReviewRows({
      baselineRowsById: input.baselineRowsById,
      scenarios: input.scenarios,
    }),
  };
}

const PRODUCT_CATEGORY_SCENARIO_EXPLANATION_DRIVERS = [
  ["ftp_effect", "FTP因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["unexplained_effect", "未解释"],
] as const;

function scenarioExplanationDriverRows(
  attributionRow: ProductCategoryAttributionRow | undefined,
): ProductCategoryScenarioExplanationDriverRow[] {
  if (!attributionRow) {
    return [];
  }
  return PRODUCT_CATEGORY_SCENARIO_EXPLANATION_DRIVERS.map(([key, label]) => {
    const value = yiNumber(attributionRow.effects[key]);
    return {
      key,
      label,
      value,
      valueLabel: formatSignedProductCategoryYi(value),
      tone: productCategoryDeltaTone(value),
    };
  }).sort((left, right) => Math.abs(right.value ?? 0) - Math.abs(left.value ?? 0));
}

function dominantScenarioExplanationDriver(
  rows: ProductCategoryScenarioExplanationDriverRow[],
): ProductCategoryScenarioExplanationDriverRow | undefined {
  return rows.find((row) => row.value !== null && row.value !== 0);
}

function scenarioExplanationAttributionTotal(
  rows: ProductCategoryScenarioExplanationDriverRow[],
): number | null {
  const values = rows.map((row) => row.value).filter((value): value is number => value !== null);
  if (values.length === 0) {
    return null;
  }
  return Number(values.reduce((total, value) => total + value, 0).toFixed(2));
}

function scenarioExplanationBridge(input: {
  scenarioDelta: number | null | undefined;
  attributionTotal: number | null;
}): Pick<ProductCategoryScenarioExplanation, "bridgeLabel" | "bridgeConclusionLabel" | "bridgeTone"> {
  const scenarioDeltaLabel = formatSignedProductCategoryYi(input.scenarioDelta ?? null);
  const attributionTotalLabel = formatSignedProductCategoryYi(input.attributionTotal);
  if (input.scenarioDelta === null || input.scenarioDelta === undefined || input.attributionTotal === null) {
    return {
      bridgeLabel: `口径桥：情景压力 ${scenarioDeltaLabel} 亿元；正式归因合计 ${attributionTotalLabel} 亿元；差异 -。`,
      bridgeConclusionLabel: "当前缺少可比较的情景压力或正式归因驱动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
    };
  }
  const bridgeGap = Number((input.scenarioDelta - input.attributionTotal).toFixed(2));
  const bridgeGapAbs = Math.abs(bridgeGap);
  const bridgeTone = bridgeGapAbs <= 0.01 ? "neutral" : "warning";
  return {
    bridgeLabel: `口径桥：情景压力 ${scenarioDeltaLabel} 亿元；正式归因合计 ${attributionTotalLabel} 亿元；差异 ${formatSignedProductCategoryYi(bridgeGap)} 亿元。`,
    bridgeConclusionLabel:
      bridgeTone === "neutral"
        ? "情景压力与正式归因合计接近，可优先复核主导驱动和输入来源。"
        : `情景压力与正式归因差异 ${productCategoryYiNumberLabel(bridgeGapAbs)} 亿元，需分开复核情景 FTP 假设和正式归因期间口径。`,
    bridgeTone,
  };
}

function scenarioExplanationReviewActions(input: {
  bridgeTone: ProductCategoryScenarioExplanation["bridgeTone"];
  dominantDriver?: ProductCategoryScenarioExplanationDriverRow;
  triggerRateLabel: string;
}): string[] {
  const actions =
    input.bridgeTone === "warning"
      ? [
          `先复核情景 FTP 假设：确认 ${input.triggerRateLabel} 情景是否只改变 FTP，不混入正式期间变动。`,
          "核对正式归因期间口径：确认正式归因的 current/prior 日期、月度/同比口径与情景基线不同。",
        ]
      : [
          "先确认情景压力与正式归因合计接近，再复核主导驱动和输入来源。",
          "核对正式归因期间口径：确认 current/prior 日期、月度/同比口径与情景基线不同。",
        ];
  if (input.dominantDriver) {
    const driverActionByKey: Record<ProductCategoryScenarioExplanationDriverRow["key"], string> = {
      ftp_effect: "复核 FTP 输入、基准利率和资产负债侧映射。",
      scale_effect: "复核规模口径、日均余额和产品分类映射。",
      rate_effect: "复核收益率/成本率输入、计息天数和基准利率变动。",
      unexplained_effect: "复核残差来源，检查缺失字段、四舍五入和未覆盖业务项。",
    };
    actions.push(`重点追踪 ${input.dominantDriver.label}：${driverActionByKey[input.dominantDriver.key]}`);
  }
  return actions.slice(0, 3);
}

export function selectProductCategoryScenarioExplanation(input: {
  categoryId: string | null | undefined;
  baseline?: ProductCategoryPnlPayload | null;
  scenarios: ProductCategoryPnlPayload[];
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryScenarioExplanation | null {
  if (!input.categoryId || !input.baseline) {
    return null;
  }
  const baselineRow = findProductCategoryRow(input.baseline.rows, input.categoryId);
  if (!baselineRow) {
    return {
      categoryId: input.categoryId,
      categoryLabel: input.categoryId,
      sideLabel: "-",
      triggerRateLabel: "-",
      scenarioDeltaLabel: "-",
      baselineNetIncomeLabel: "-",
      scenarioNetIncomeLabel: "-",
      summaryLabel: "当前正式基线未返回该产品行，无法形成行级情景解释。",
      bridgeLabel: "口径桥：情景压力 - 亿元；正式归因合计 - 亿元；差异 -。",
      bridgeConclusionLabel: "当前缺少可比较的情景压力或正式归因驱动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
      reviewActionItems: ["补齐正式基线和情景矩阵后，再生成行级复核动作。"],
      driverRows: [],
      emptyCopy: "当前正式基线未返回该产品行，无法形成行级情景解释。",
    };
  }
  const baselineNetIncome = yiNumber(baselineRow.business_net_income);
  const scenarioMoves = input.scenarios
    .map((scenario) => {
      const scenarioRow = findProductCategoryRow(scenario.rows, input.categoryId as string);
      if (!scenarioRow) {
        return null;
      }
      const delta = productCategoryRowDeltaYi(new Map([[baselineRow.category_id, baselineRow]]), scenarioRow);
      const scenarioNetIncome = yiNumber(scenarioRow.business_net_income);
      const scenarioRate = decimalNumber(scenario.scenario_rate_pct);
      if (delta === null || scenarioNetIncome === null || scenarioRate === null) {
        return null;
      }
      return {
        row: scenarioRow,
        delta,
        scenarioNetIncome,
        rateLabel: `${scenarioRate.toFixed(2)}%`,
      };
    })
    .filter((move): move is {
      row: ProductCategoryPnlRow;
      delta: number;
      scenarioNetIncome: number;
      rateLabel: string;
    } => move !== null)
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
  const topMove = scenarioMoves[0];
  const attributionRow = input.attribution?.rows.find((row) => row.category_id === input.categoryId);
  const driverRows = scenarioExplanationDriverRows(attributionRow);
  const dominantDriver = dominantScenarioExplanationDriver(driverRows);
  const attributionTotal = scenarioExplanationAttributionTotal(driverRows);
  const scenarioDeltaLabel = formatSignedProductCategoryYi(topMove?.delta ?? null);
  const triggerRateLabel = topMove?.rateLabel ?? "-";
  const baselineNetIncomeLabel = productCategoryYiNumberLabel(baselineNetIncome);
  const scenarioNetIncomeLabel = productCategoryYiNumberLabel(topMove?.scenarioNetIncome ?? null);
  const bridge = scenarioExplanationBridge({
    scenarioDelta: topMove?.delta,
    attributionTotal,
  });
  const reviewActionItems = scenarioExplanationReviewActions({
    bridgeTone: bridge.bridgeTone,
    dominantDriver,
    triggerRateLabel,
  });
  const driverCopy = dominantDriver
    ? `正式归因显示主导因素为 ${dominantDriver.label} ${dominantDriver.valueLabel} 亿元。`
    : "当前正式归因未返回可排序的驱动项。";
  const summaryLabel = `${baselineRow.category_name || baselineRow.category_id}在 ${triggerRateLabel} 情景较正式基线 ${scenarioDeltaLabel} 亿元；${driverCopy}`;
  return {
    categoryId: baselineRow.category_id,
    categoryLabel: baselineRow.category_name || baselineRow.category_id,
    sideLabel: productCategoryScenarioSideLabel(baselineRow.side),
    triggerRateLabel,
    scenarioDeltaLabel,
    baselineNetIncomeLabel,
    scenarioNetIncomeLabel,
    summaryLabel,
    ...bridge,
    reviewActionItems,
    driverRows,
    emptyCopy: topMove ? null : "当前情景矩阵未返回该产品行的可比较结果。",
  };
}

export function selectProductCategoryScenarioSensitivitySurface(input: {
  baseline?: ProductCategoryPnlPayload | null;
  scenarios: ProductCategoryPnlPayload[];
}): ProductCategoryScenarioSensitivitySurface {
  if (!input.baseline || input.scenarios.length === 0) {
    return {
      baselineGrandTotalLabel: input.baseline
        ? formatProductCategoryValue(input.baseline.grand_total.business_net_income)
        : null,
      rows: [],
      insightCards: [],
      riskRows: [],
      pathPoints: [],
      actionItems: [],
      heatRows: [],
      comparisonRows: [],
      actionClosureRows: [],
      pressureSummary: EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY,
      analysisCopy: null,
      emptyCopy: "当前尚未返回可比较的 FTP 情景结果。",
    };
  }
  const baselineRowsById = new Map(input.baseline.rows.map((row) => [row.category_id, row]));
  const baselineAssetTotal = yiNumber(input.baseline.asset_total.business_net_income);
  const baselineLiabilityTotal = yiNumber(input.baseline.liability_total.business_net_income);
  const baselineGrandTotal = yiNumber(input.baseline.grand_total.business_net_income);
  const rows: ProductCategoryScenarioSensitivityRow[] = [];
  for (const scenario of input.scenarios) {
    const scenarioRate = scenario.scenario_rate_pct;
    if (scenarioRate === null || scenarioRate === undefined) {
      continue;
    }
    const ratePct = Number(scenarioRate);
    const assetValue = yiNumber(scenario.asset_total.business_net_income);
    const liabilityValue = yiNumber(scenario.liability_total.business_net_income);
    const grandValue = yiNumber(scenario.grand_total.business_net_income);
    const assetDelta =
      assetValue === null || baselineAssetTotal === null
        ? null
        : Number((assetValue - baselineAssetTotal).toFixed(2));
    const liabilityDelta =
      liabilityValue === null || baselineLiabilityTotal === null
        ? null
        : Number((liabilityValue - baselineLiabilityTotal).toFixed(2));
    const grandDelta =
      grandValue === null || baselineGrandTotal === null
        ? null
        : Number((grandValue - baselineGrandTotal).toFixed(2));
    const topMover = leafProductCategoryRows(scenario.rows)
      .map((row) => ({
        row,
        delta: productCategoryRowDeltaYi(baselineRowsById, row),
      }))
      .filter((item): item is { row: ProductCategoryPnlRow; delta: number } => item.delta !== null)
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
    rows.push({
      rate: String(scenarioRate),
      ratePct,
      rateLabel: `${ratePct.toFixed(2)}%`,
      assetDelta,
      assetNetIncomeLabel: productCategoryYiNumberLabel(assetValue),
      assetDeltaLabel: formatSignedProductCategoryYi(assetDelta),
      liabilityDelta,
      liabilityNetIncomeLabel: productCategoryYiNumberLabel(
        liabilityValue === null ? null : Math.abs(liabilityValue),
      ),
      liabilityDeltaLabel: formatSignedProductCategoryYi(liabilityDelta),
      grandNetIncome: grandValue,
      grandDelta,
      grandNetIncomeLabel: productCategoryYiNumberLabel(grandValue),
      grandDeltaLabel: formatSignedProductCategoryYi(grandDelta),
      topMoverCategoryLabel: topMover?.row.category_name || topMover?.row.category_id || "-",
      topMoverDelta: topMover?.delta ?? null,
      topMoverDeltaLabel: formatSignedProductCategoryYi(topMover?.delta ?? null),
      tone: productCategoryDeltaTone(grandDelta),
    });
  }
  rows.sort((left, right) => Number(left.rate) - Number(right.rate));
  const comparableRows = rows.filter(hasComparableScenarioGrandTotal);
  const sortedByGrand = [...comparableRows].sort(
    (left, right) => right.grandNetIncome - left.grandNetIncome,
  );
  const best = sortedByGrand[0];
  const worst = sortedByGrand[sortedByGrand.length - 1];
  const riskRows = selectProductCategoryScenarioRiskRows(rows);
  const comparisonRows = selectProductCategoryScenarioComparisonRows({
    baselineRowsById,
    scenarios: input.scenarios,
  });
  return {
    baselineGrandTotalLabel: formatProductCategoryValue(input.baseline.grand_total.business_net_income),
    rows,
    insightCards: selectProductCategoryScenarioInsightCards(rows),
    riskRows,
    pathPoints: selectProductCategoryScenarioPathPoints(rows),
    actionItems: selectProductCategoryScenarioActionItems({ best, worst, riskRows }),
    heatRows: selectProductCategoryScenarioHeatRows({
      baselineRowsById,
      scenarios: input.scenarios,
    }),
    comparisonRows,
    actionClosureRows: selectProductCategoryScenarioActionClosureRows(comparisonRows),
    pressureSummary: selectProductCategoryScenarioPressureSummary({
      baselineRowsById,
      comparableRows,
      scenarios: input.scenarios,
      worst,
    }),
    analysisCopy: productCategoryScenarioAnalysisCopy(worst, best),
    emptyCopy: rows.length === 0 ? "当前尚未返回可比较的 FTP 情景结果。" : null,
  };
}

const PRODUCT_CATEGORY_ATTRIBUTION_WATERFALL_STEPS = [
  ["day_effect", "天数因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合误差"],
] as const;

const PRODUCT_CATEGORY_ROOT_CAUSE_DRIVER_STEPS = [
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合误差"],
] as const satisfies ReadonlyArray<readonly [ProductCategoryRootCauseDriverKey, string]>;

export function selectProductCategoryAttributionWaterfallSurface(
  attribution: ProductCategoryAttributionPayload | null | undefined,
): ProductCategoryAttributionWaterfallSurface {
  const headline = attribution?.totals?.grand_total;
  if (!headline || attribution?.state !== "complete") {
    return {
      title: "经营差异瀑布",
      deltaLabel: "-",
      rows: [],
      emptyCopy: "当前缺少可用的全表经营差异归因。",
    };
  }
  const prior = yiNumber(headline.prior?.business_net_income);
  const current = yiNumber(headline.current?.business_net_income);
  const delta = yiNumber(headline.effects.delta_business_net_income);
  if (prior === null || current === null) {
    return {
      title: `${headline.category_name || "全表合计"}经营差异瀑布`,
      deltaLabel: formatSignedProductCategoryYi(delta),
      rows: [],
      emptyCopy: "当前归因缺少本期或对比期净营收。",
    };
  }
  let cumulative = prior;
  const rows: ProductCategoryAttributionWaterfallRow[] = [
    {
      key: "prior",
      label: "对比期净营收",
      value: prior,
      valueLabel: productCategoryYiNumberLabel(prior),
      cumulative: prior,
      cumulativeLabel: productCategoryYiNumberLabel(prior),
      tone: productCategoryDeltaTone(prior),
    },
  ];
  for (const [key, label] of PRODUCT_CATEGORY_ATTRIBUTION_WATERFALL_STEPS) {
    const value = yiNumber(headline.effects[key]);
    if (value !== null) {
      cumulative = Number((cumulative + value).toFixed(2));
    }
    rows.push({
      key,
      label,
      value,
      valueLabel: formatSignedProductCategoryYi(value),
      cumulative: value === null ? null : cumulative,
      cumulativeLabel: value === null ? "-" : productCategoryYiNumberLabel(cumulative),
      tone: productCategoryDeltaTone(value),
    });
  }
  rows.push({
    key: "current",
    label: "本期净营收",
    value: current,
    valueLabel: productCategoryYiNumberLabel(current),
    cumulative: current,
    cumulativeLabel: productCategoryYiNumberLabel(current),
    tone: productCategoryDeltaTone(delta),
  });
  return {
    title: `${headline.category_name || "全表合计"}经营差异瀑布`,
    deltaLabel: formatSignedProductCategoryYi(delta),
    rows,
    emptyCopy: null,
  };
}

export function selectProductCategoryRootCauseSurface(input: {
  rows: ProductCategoryPnlRow[];
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryRootCauseSurface {
  if (!input.attribution || input.attribution.state !== "complete") {
    return {
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前缺少可用的产品级正式归因，暂不能拆解根因。",
    };
  }
  const parentIds = parentProductCategoryIds(input.rows);
  const attributionRows = input.attribution.rows.filter(
    (row) => !row.category_id.endsWith("_total") && row.category_id !== "grand_total" && !parentIds.has(row.category_id),
  );
  const headlineRow = attributionRows
    .map((row) => ({ row, delta: yiNumber(row.effects.delta_business_net_income) }))
    .filter((item): item is { row: ProductCategoryAttributionRow; delta: number } =>
      item.delta !== null && item.delta !== 0,
    )
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
  if (!headlineRow) {
    return {
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前产品级归因没有可拆解的显著差异。",
    };
  }
  const displayRow = input.rows.find((row) => row.category_id === headlineRow.row.category_id);
  const currentNetIncome = yiNumber(headlineRow.row.current?.business_net_income ?? displayRow?.business_net_income);
  const priorNetIncome = yiNumber(headlineRow.row.prior?.business_net_income);
  const scale = yiNumber(headlineRow.row.current?.scale ?? displayRow?.cnx_scale);
  const yieldPct = percentNumber(headlineRow.row.current?.yield_pct ?? displayRow?.weighted_yield);
  const driverRows = PRODUCT_CATEGORY_ROOT_CAUSE_DRIVER_STEPS
    .map(([key, label]) => {
      const value = yiNumber(headlineRow.row.effects[key]) ?? 0;
      const sharePct = headlineRow.delta !== 0 ? Number((value / headlineRow.delta * 100).toFixed(1)) : null;
      return {
        key,
        label,
        value,
        valueLabel: formatSignedProductCategoryYi(value),
        sharePct,
        shareLabel: productCategoryPercentLabel(sharePct),
        tone: productCategoryDeltaTone(value),
      };
    })
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value));
  const leadingDriver = driverRows[0] ?? null;
  const closureError = yiNumber(headlineRow.row.effects.closure_error);
  return {
    headline: {
      categoryId: headlineRow.row.category_id,
      categoryLabel: headlineRow.row.category_name || headlineRow.row.category_id,
      delta: headlineRow.delta,
      deltaLabel: formatSignedProductCategoryYi(headlineRow.delta),
      driverLabel: leadingDriver?.label ?? "未识别",
      driverValueLabel: leadingDriver?.valueLabel ?? "-",
      currentNetIncomeLabel: productCategoryYiNumberLabel(currentNetIncome),
      priorNetIncomeLabel: productCategoryYiNumberLabel(priorNetIncome),
      scaleLabel: productCategoryYiNumberLabel(scale),
      yieldLabel: yieldPct === null ? "-" : `${yieldPct.toFixed(2)}%`,
      conclusionLabel: `${headlineRow.row.category_name || headlineRow.row.category_id} 变动 ${formatSignedProductCategoryYi(
        headlineRow.delta,
      )} 亿元，主导原因是 ${leadingDriver?.label ?? "未识别"} ${leadingDriver?.valueLabel ?? "-"} 亿元。`,
      tone: productCategoryDeltaTone(headlineRow.delta),
    },
    driverRows,
    evidenceItems: [
      `本期净营收 ${productCategoryYiNumberLabel(currentNetIncome)} 亿元`,
      `对比期净营收 ${productCategoryYiNumberLabel(priorNetIncome)} 亿元`,
      `当前规模 ${productCategoryYiNumberLabel(scale)} 亿元`,
      `当前收益率 ${yieldPct === null ? "-" : `${yieldPct.toFixed(2)}%`}`,
      `闭合误差 ${formatSignedProductCategoryYi(closureError)} 亿元`,
    ],
    emptyCopy: null,
  };
}

function focusItemFromRow(input: {
  key: ProductCategoryDecisionFocusKey;
  row: ProductCategoryPnlRow;
  value: number;
  reasonLabel: string;
  secondaryLabel: string;
}): ProductCategoryDecisionFocusItem {
  return {
    key: input.key,
    categoryId: input.row.category_id,
    categoryLabel: input.row.category_name || input.row.category_id,
    reasonLabel: input.reasonLabel,
    primaryLabel: productCategoryYiNumberLabel(input.value),
    secondaryLabel: input.secondaryLabel,
    tone: productCategoryDeltaTone(input.value),
  };
}

export function selectProductCategoryDecisionFocusSurface(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryDecisionFocusSurface {
  const candidates = leafProductCategoryRows(input.rows)
    .map((row) => {
      const value = yiNumber(row.business_net_income);
      return value === null || value === 0 ? null : { row, value };
    })
    .filter((item): item is { row: ProductCategoryPnlRow; value: number } => item !== null);
  const items: ProductCategoryDecisionFocusItem[] = [];
  const topContributor = candidates.filter((item) => item.value > 0).sort((left, right) => right.value - left.value)[0];
  if (topContributor) {
    items.push(focusItemFromRow({
      key: "top_contributor",
      row: topContributor.row,
      value: topContributor.value,
      reasonLabel: "本期贡献最高",
      secondaryLabel: "优先确认利润可持续性",
    }));
  }
  const topPressure = candidates.filter((item) => item.value < 0).sort((left, right) => left.value - right.value)[0];
  if (topPressure) {
    items.push(focusItemFromRow({
      key: "top_pressure",
      row: topPressure.row,
      value: topPressure.value,
      reasonLabel: "本期压力最大",
      secondaryLabel: "优先定位收入承压来源",
    }));
  }
  if (input.attribution?.state === "complete") {
    const attributionRows = input.attribution.rows.filter(
      (row) => !row.category_id.endsWith("_total") && row.category_id !== "grand_total",
    );
    const largestDeterioration = attributionRows
      .map((row) => ({ row, value: yiNumber(row.effects.delta_business_net_income) }))
      .filter((item): item is { row: ProductCategoryAttributionRow; value: number } =>
        item.value !== null && item.value < 0,
      )
      .sort((left, right) => left.value - right.value)[0];
    if (largestDeterioration) {
      items.push({
        key: "largest_deterioration",
        categoryId: largestDeterioration.row.category_id,
        categoryLabel: largestDeterioration.row.category_name || largestDeterioration.row.category_id,
        reasonLabel: "环比恶化最大",
        primaryLabel: formatSignedProductCategoryYi(largestDeterioration.value),
        secondaryLabel: "优先查看规模/利率/FTP驱动",
        tone: "negative",
      });
    }
    const largestUnexplained = attributionRows
      .map((row) => ({ row, value: yiNumber(row.effects.unexplained_effect) }))
      .filter((item): item is { row: ProductCategoryAttributionRow; value: number } =>
        item.value !== null && item.value !== 0,
      )
      .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))[0];
    if (largestUnexplained) {
      items.push({
        key: "largest_unexplained",
        categoryId: largestUnexplained.row.category_id,
        categoryLabel: largestUnexplained.row.category_name || largestUnexplained.row.category_id,
        reasonLabel: "未解释金额最大",
        primaryLabel: formatSignedProductCategoryYi(largestUnexplained.value),
        secondaryLabel: "需要复核归因残差",
        tone: productCategoryDeltaTone(largestUnexplained.value),
      });
    }
  }
  return {
    items,
    emptyCopy: items.length === 0 ? "当前没有可形成决策焦点的产品行或归因结果。" : null,
  };
}

function signedBpLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  if (value === 0) {
    return "0bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1).replace(/\.0$/, "")}bp`;
}

function bpLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return `${value.toFixed(1).replace(/\.0$/, "")}bp`;
}

function signedYiDeltaLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  if (value === 0) {
    return "0.00";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(2)}`;
}

function findProductCategoryRow(
  rows: ProductCategoryPnlRow[],
  categoryId: string,
): ProductCategoryPnlRow | undefined {
  return rows.find((row) => row.category_id === categoryId);
}

function productCategoryActionLabel(kind: ProductCategoryOperatingActionKind): string {
  if (kind === "shrink_or_limit") {
    return "压降或限额复核";
  }
  if (kind === "review_attribution") {
    return "归因复核";
  }
  if (kind === "reprice_or_improve") {
    return "重定价/提效";
  }
  return "选择性扩张";
}

function averageProductCategoryNumber(values: Array<number | null>): number | null {
  const candidates = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (candidates.length === 0) {
    return null;
  }
  return Number((candidates.reduce((total, value) => total + value, 0) / candidates.length).toFixed(2));
}

function productCategoryRateLabel(rate: number | null): string {
  if (rate === null || !Number.isFinite(rate)) {
    return "-";
  }
  return `${(rate * 100).toFixed(1)}%`;
}

function signedProductCategoryBpDeltaLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  if (value === 0) {
    return "0.0bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1)}bp`;
}

function productCategoryOutcomeHit(input: {
  actionKind: ProductCategoryOperatingActionKind;
  netIncomeDelta: number | null;
  nextNetIncome: number | null;
  yieldDeltaBp: number | null;
  scaleDelta: number | null;
  currentUnexplainedAbs: number | null;
  nextUnexplainedAbs: number | null;
}): boolean | null {
  if (input.actionKind === "shrink_or_limit") {
    return input.netIncomeDelta === null ? null : input.netIncomeDelta > 0;
  }
  if (input.actionKind === "reprice_or_improve") {
    return input.yieldDeltaBp === null ? null : input.yieldDeltaBp > 0;
  }
  if (input.actionKind === "selective_growth") {
    if (input.scaleDelta === null || input.nextNetIncome === null) {
      return null;
    }
    return input.scaleDelta > 0 && input.nextNetIncome > 0;
  }
  if (input.currentUnexplainedAbs === null || input.nextUnexplainedAbs === null) {
    return null;
  }
  return input.nextUnexplainedAbs < input.currentUnexplainedAbs;
}

function productCategoryBacktestCurrentUnexplainedAbs(
  action: ProductCategoryOperatingActionQueueRow,
): number | null {
  if (action.actionKind !== "review_attribution") {
    return null;
  }
  const parsed = Number(action.primaryMetricLabel);
  return Number.isFinite(parsed) ? Math.abs(parsed) : null;
}

function productCategoryBacktestNextUnexplainedAbs(
  attribution: ProductCategoryAttributionPayload | null | undefined,
  rows: ProductCategoryPnlRow[],
  categoryId: string,
): number | null {
  const parentCategoryIds = parentProductCategoryIds(rows);
  const movement = buildProductCategoryOperatingMovementRows(attribution, parentCategoryIds)
    .find((row) => row.categoryId === categoryId);
  if (!movement) {
    return 0;
  }
  return movement.leadingDriverKey === "unexplained_effect"
    ? Math.abs(movement.leadingDriverValue)
    : 0;
}

function productCategoryBacktestEvidenceLabel(kind: ProductCategoryOperatingActionKind): string {
  if (kind === "shrink_or_limit") {
    return "命中=次月净营收改善";
  }
  if (kind === "reprice_or_improve") {
    return "命中=次月收益率改善";
  }
  if (kind === "selective_growth") {
    return "命中=次月规模扩张且仍为正贡献";
  }
  return "命中=次月未解释差异下降";
}

function productCategoryBacktestTone(hitRate: number | null): "positive" | "negative" | "neutral" {
  if (hitRate === null) {
    return "neutral";
  }
  if (hitRate >= 0.5) {
    return "positive";
  }
  if (hitRate < 0.3) {
    return "negative";
  }
  return "neutral";
}

const PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER: ProductCategoryOperatingBacktestMissReasonKey[] = [
  "yield_not_improved",
  "net_income_not_improved",
  "scale_not_expanded",
  "positive_contribution_missing",
  "attribution_not_reduced",
  "scale_mismatch",
  "net_income_drag",
  "outcome_not_improved",
];

function productCategoryBacktestMissReasonLabel(
  reasonKey: ProductCategoryOperatingBacktestMissReasonKey,
): string {
  if (reasonKey === "yield_not_improved") {
    return "收益率未改善";
  }
  if (reasonKey === "net_income_not_improved") {
    return "净营收未改善";
  }
  if (reasonKey === "scale_not_expanded") {
    return "规模未扩张";
  }
  if (reasonKey === "positive_contribution_missing") {
    return "正贡献不足";
  }
  if (reasonKey === "attribution_not_reduced") {
    return "未解释差异未下降";
  }
  if (reasonKey === "scale_mismatch") {
    return "规模方向错配";
  }
  if (reasonKey === "net_income_drag") {
    return "净营收拖累";
  }
  return "结果未改善";
}

function productCategoryBacktestMissReasonKeys(input: {
  actionKind: ProductCategoryOperatingActionKind;
  hit: boolean | null;
  netIncomeDelta: number | null;
  nextNetIncome: number | null;
  yieldDeltaBp: number | null;
  scaleDelta: number | null;
  currentUnexplainedAbs: number | null;
  nextUnexplainedAbs: number | null;
}): ProductCategoryOperatingBacktestMissReasonKey[] {
  if (input.hit !== false) {
    return [];
  }
  const reasons: ProductCategoryOperatingBacktestMissReasonKey[] = [];
  if (input.actionKind === "reprice_or_improve") {
    if (input.yieldDeltaBp !== null && input.yieldDeltaBp <= 0) {
      reasons.push("yield_not_improved");
    }
    if (input.scaleDelta !== null && input.scaleDelta > 0 && (input.yieldDeltaBp === null || input.yieldDeltaBp <= 0)) {
      reasons.push("scale_mismatch");
    }
    if (input.netIncomeDelta !== null && input.netIncomeDelta < 0) {
      reasons.push("net_income_drag");
    }
  } else if (input.actionKind === "shrink_or_limit") {
    if (input.netIncomeDelta !== null && input.netIncomeDelta <= 0) {
      reasons.push("net_income_not_improved");
    }
    if (input.scaleDelta !== null && input.scaleDelta > 0) {
      reasons.push("scale_mismatch");
    }
  } else if (input.actionKind === "selective_growth") {
    if (input.scaleDelta !== null && input.scaleDelta <= 0) {
      reasons.push("scale_not_expanded");
    }
    if (input.nextNetIncome !== null && input.nextNetIncome <= 0) {
      reasons.push("positive_contribution_missing");
    }
    if (input.yieldDeltaBp !== null && input.yieldDeltaBp <= 0) {
      reasons.push("yield_not_improved");
    }
  } else if (
    input.currentUnexplainedAbs !== null
    && input.nextUnexplainedAbs !== null
    && input.nextUnexplainedAbs >= input.currentUnexplainedAbs
  ) {
    reasons.push("attribution_not_reduced");
  }
  if (reasons.length === 0) {
    reasons.push("outcome_not_improved");
  }
  return reasons;
}

function productCategoryNextMonthEndDate(reportDate: string): string | null {
  const parsed = parseProductCategoryReportDate(reportDate);
  if (!parsed) {
    return null;
  }
  const nextMonth = parsed.month === 12 ? 1 : parsed.month + 1;
  const nextYear = parsed.month === 12 ? parsed.year + 1 : parsed.year;
  const lastDay = new Date(nextYear, nextMonth, 0).getDate();
  return `${nextYear}-${String(nextMonth).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
}

function productCategoryReportDatesAreConsecutiveMonths(current: string, next: string): boolean {
  return productCategoryNextMonthEndDate(current) === next;
}

export function selectProductCategoryOperatingActionBacktestSurface(input: {
  payloads: ProductCategoryPnlPayload[];
  attributionsByReportDate?: Map<string, ProductCategoryAttributionPayload | null>;
}): ProductCategoryOperatingBacktestSurface {
  const payloads = input.payloads
    .filter((payload) => payload.view === "monthly")
    .slice()
    .sort((left, right) => left.report_date.localeCompare(right.report_date));
  const latestPayload = payloads[payloads.length - 1];
  const latestPendingCount = latestPayload
    ? selectProductCategoryOperatingActionQueue({
        rows: latestPayload.rows,
        attribution: input.attributionsByReportDate?.get(latestPayload.report_date),
        parentCategoryIds: parentProductCategoryIds(latestPayload.rows),
      }).rows.length
    : 0;
  const samples: ProductCategoryOperatingBacktestExample[] = [];
  const coverageRows: ProductCategoryOperatingBacktestSurface["coverageRows"] = [];

  for (let index = 0; index < payloads.length - 1; index += 1) {
    const current = payloads[index];
    const next = payloads[index + 1];
    if (!current || !next) {
      continue;
    }
    const currentActions = selectProductCategoryOperatingActionQueue({
      rows: current.rows,
      attribution: input.attributionsByReportDate?.get(current.report_date),
      parentCategoryIds: parentProductCategoryIds(current.rows),
    }).rows;
    if (!productCategoryReportDatesAreConsecutiveMonths(current.report_date, next.report_date)) {
      coverageRows.push({
        reportDate: current.report_date,
        nextReportDate: next.report_date,
        statusLabel: "跳过：非连续月份",
        signalCount: currentActions.length,
        tone: "negative",
      });
      continue;
    }
    const currentRowsById = new Map(current.rows.map((row) => [row.category_id, row]));
    const nextRowsById = new Map(next.rows.map((row) => [row.category_id, row]));
    for (const action of currentActions) {
      const currentRow = currentRowsById.get(action.categoryId);
      const nextRow = nextRowsById.get(action.categoryId);
      if (!currentRow || !nextRow) {
        continue;
      }
      const currentNetIncome = yiNumber(currentRow.business_net_income);
      const nextNetIncome = yiNumber(nextRow.business_net_income);
      const netIncomeDelta =
        currentNetIncome === null || nextNetIncome === null
          ? null
          : Number((nextNetIncome - currentNetIncome).toFixed(2));
      const currentYield = percentNumber(currentRow.weighted_yield);
      const nextYield = percentNumber(nextRow.weighted_yield);
      const yieldDeltaBp =
        currentYield === null || nextYield === null
          ? null
          : Number(((nextYield - currentYield) * 100).toFixed(1));
      const currentScale = yiNumber(currentRow.cnx_scale);
      const nextScale = yiNumber(nextRow.cnx_scale);
      const scaleDelta =
        currentScale === null || nextScale === null
          ? null
          : Number((nextScale - currentScale).toFixed(2));
      const currentUnexplainedAbs = productCategoryBacktestCurrentUnexplainedAbs(action);
      const nextUnexplainedAbs = productCategoryBacktestNextUnexplainedAbs(
        input.attributionsByReportDate?.get(next.report_date),
        next.rows,
        action.categoryId,
      );
      const hit = productCategoryOutcomeHit({
        actionKind: action.actionKind,
        netIncomeDelta,
        nextNetIncome,
        yieldDeltaBp,
        scaleDelta,
        currentUnexplainedAbs,
        nextUnexplainedAbs,
      });
      const missReasonKeys = productCategoryBacktestMissReasonKeys({
        actionKind: action.actionKind,
        hit,
        netIncomeDelta,
        nextNetIncome,
        yieldDeltaBp,
        scaleDelta,
        currentUnexplainedAbs,
        nextUnexplainedAbs,
      });
      samples.push({
        reportDate: current.report_date,
        nextReportDate: next.report_date,
        categoryId: action.categoryId,
        categoryLabel: action.categoryLabel,
        priorityLabel: action.priorityLabel,
        actionKind: action.actionKind,
        actionLabel: action.actionLabel,
        outcomeLabel: hit === null ? "待判定" : hit ? "命中" : "未命中",
        netIncomeDelta,
        netIncomeDeltaLabel: signedYiDeltaLabel(netIncomeDelta),
        yieldDeltaBp,
        yieldDeltaBpLabel: signedProductCategoryBpDeltaLabel(yieldDeltaBp),
        scaleDelta,
        scaleDeltaLabel: signedYiDeltaLabel(scaleDelta),
        missReasonKeys,
        tone: hit === null ? "neutral" : hit ? "positive" : "negative",
      });
    }
    coverageRows.push({
      reportDate: current.report_date,
      nextReportDate: next.report_date,
      statusLabel: "已回测",
      signalCount: currentActions.length,
      tone: "positive",
    });
  }
  if (latestPayload) {
    coverageRows.push({
      reportDate: latestPayload.report_date,
      nextReportDate: null,
      statusLabel: "最新月待观察",
      signalCount: latestPendingCount,
      tone: "neutral",
    });
  }

  const evaluatedDates = Array.from(new Set(samples.map((sample) => sample.reportDate))).sort();
  const actionRows = ([
    "shrink_or_limit",
    "review_attribution",
    "reprice_or_improve",
    "selective_growth",
  ] as const).flatMap((actionKind) => {
    const rows = samples.filter((sample) => sample.actionKind === actionKind);
    if (rows.length === 0) {
      return [];
    }
    const hitCount = rows.filter((row) => row.outcomeLabel === "命中").length;
    const comparableCount = rows.filter((row) => row.outcomeLabel !== "待判定").length;
    const hitRate = comparableCount === 0 ? null : hitCount / comparableCount;
    const averageNetIncomeDelta = averageProductCategoryNumber(rows.map((row) => row.netIncomeDelta));
    const averageYieldDeltaBp = averageProductCategoryNumber(rows.map((row) => row.yieldDeltaBp));
    const averageScaleDelta = averageProductCategoryNumber(rows.map((row) => row.scaleDelta));
    return [{
      actionKind,
      actionLabel: productCategoryActionLabel(actionKind),
      signalCount: rows.length,
      hitCount,
      hitRate,
      hitRateLabel: productCategoryRateLabel(hitRate),
      averageNetIncomeDelta,
      averageNetIncomeDeltaLabel: signedYiDeltaLabel(averageNetIncomeDelta),
      averageYieldDeltaBp,
      averageYieldDeltaBpLabel: signedProductCategoryBpDeltaLabel(averageYieldDeltaBp),
      averageScaleDelta,
      averageScaleDeltaLabel: signedYiDeltaLabel(averageScaleDelta),
      evidenceLabel: productCategoryBacktestEvidenceLabel(actionKind),
      tone: productCategoryBacktestTone(hitRate),
    }];
  });
  const missReasonRows = ([
    "shrink_or_limit",
    "review_attribution",
    "reprice_or_improve",
    "selective_growth",
  ] as const).flatMap((actionKind) => {
    const rows = samples.filter((sample) => sample.actionKind === actionKind);
    const comparableRows = rows.filter((row) => row.outcomeLabel !== "待判定");
    const missedRows = rows.filter((row) => row.outcomeLabel === "未命中");
    if (missedRows.length === 0) {
      return [];
    }
    const reasonCounts = missedRows.reduce((counts, row) => {
      row.missReasonKeys.forEach((reasonKey) => {
        counts.set(reasonKey, (counts.get(reasonKey) ?? 0) + 1);
      });
      return counts;
    }, new Map<ProductCategoryOperatingBacktestMissReasonKey, number>());
    const reasonRows = Array.from(reasonCounts.entries())
      .sort((left, right) => {
        if (right[1] !== left[1]) {
          return right[1] - left[1];
        }
        return PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(left[0])
          - PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(right[0]);
      })
      .map(([reasonKey, sampleCount]) => ({
        reasonKey,
        reasonLabel: productCategoryBacktestMissReasonLabel(reasonKey),
        sampleCount,
        sampleShareLabel: `${sampleCount}/${missedRows.length}`,
      }));
    const missRate = comparableRows.length === 0 ? null : missedRows.length / comparableRows.length;
    return [{
      actionKind,
      actionLabel: productCategoryActionLabel(actionKind),
      missCount: missedRows.length,
      comparableCount: comparableRows.length,
      missRate,
      missRateLabel: productCategoryRateLabel(missRate),
      primaryReasonLabel: reasonRows[0]?.reasonLabel ?? "-",
      reasonRows,
      tone: productCategoryBacktestTone(missRate === null ? null : 1 - missRate),
    }];
  }).sort((left, right) => {
    if ((right.missRate ?? -1) !== (left.missRate ?? -1)) {
      return (right.missRate ?? -1) - (left.missRate ?? -1);
    }
    return right.missCount - left.missCount;
  });

  return {
    summary: {
      evaluatedMonthCount: evaluatedDates.length,
      signalCount: samples.length,
      latestPendingCount,
      coverageLabel: evaluatedDates.length > 0
        ? `${evaluatedDates[0]} 至 ${evaluatedDates[evaluatedDates.length - 1]}`
        : "-",
      evidenceLabel: "信号来自动作队列；结果使用下一期 monthly 正式口径验证。",
    },
    coverageRows,
    actionRows,
    missReasonRows,
    examples: samples
      .slice()
      .sort((left, right) => Math.abs(right.netIncomeDelta ?? 0) - Math.abs(left.netIncomeDelta ?? 0))
      .slice(0, 6),
    emptyCopy: samples.length === 0 ? "需要至少两个连续月度正式 payload 才能回测行动信号。" : null,
  };
}

function buildSnapshotChart<T>(
  snapshots: ProductCategoryTrendSnapshot[],
  project: (snapshot: ProductCategoryTrendSnapshot) => T | null,
): { labels: string[]; points: T[] } {
  const labels: string[] = [];
  const points: T[] = [];
  snapshots
    .slice()
    .sort((left, right) => left.reportDate.localeCompare(right.reportDate))
    .forEach((snapshot) => {
      const point = project(snapshot);
      if (point === null) {
        return;
      }
      labels.push(snapshot.label ?? formatProductCategoryReportMonthLabel(snapshot.reportDate));
      points.push(point);
    });
  return { labels, points };
}

function chronologicalProductCategorySnapshots(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryTrendSnapshot[] {
  return snapshots.slice().sort((left, right) => left.reportDate.localeCompare(right.reportDate));
}

function liabilityDetailRowsFromSnapshot(snapshot: ProductCategoryTrendSnapshot): ProductCategoryPnlRow[] {
  return snapshot.rows
    .filter((row) => row.side === "liability" && !row.is_total && row.category_id !== "liability_total")
    .sort((left, right) => {
      const leftIndex = DISPLAY_ORDER_INDEX.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
      const rightIndex = DISPLAY_ORDER_INDEX.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex;
    });
}

function spreadBp(snapshot: ProductCategoryTrendSnapshot): number | null {
  const assetYield = decimalNumber(snapshot.assetTotal?.weighted_yield);
  const liabilityYield = decimalNumber(snapshot.liabilityTotal?.weighted_yield);
  if (assetYield === null || liabilityYield === null) {
    return null;
  }
  return (assetYield - liabilityYield) * 100;
}

function spreadDeltaBp(current: number | null, previous: number | null): number | null {
  if (current === null || previous === null) {
    return null;
  }
  return current - previous;
}

function productCategorySideLabel(side: string): string {
  if (side === "asset") {
    return "\u8d44\u4ea7";
  }
  if (side === "liability") {
    return "\u8d1f\u503a";
  }
  return side || "-";
}

function formatProductCategoryDiagnosticMoneyLabel(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): string {
  const display = formatProductCategoryRowDisplayValue(row, value);
  return display === "-" ? "\u7f3a\u5931" : `${display} \u4ebf\u5143`;
}

function formatProductCategoryDiagnosticYieldLabel(
  value: DecimalLike | null | undefined,
): { label: string; missing: boolean } {
  const display = formatProductCategoryYieldValue(value);
  if (display === "-") {
    return { label: "\u6536\u76ca\u7387\u7f3a\u5931", missing: true };
  }
  return { label: `${display}%`, missing: false };
}

function dominantNetHint(label: string, value: number | null): string | null {
  if (value === null || value === 0) {
    return null;
  }
  return value > 0
    ? `${label}\u51c0\u6536\u5165\u4e3b\u5bfc`
    : `${label}\u51c0\u6536\u5165\u627f\u538b`;
}

function buildProductCategoryDriverHint(row: ProductCategoryPnlRow): string {
  const hints: string[] = [];
  const cnyNet = decimalNumber(row.cny_net);
  const foreignNet = decimalNumber(row.foreign_net);
  const cnyCash = decimalNumber(row.cny_cash);
  const foreignCash = decimalNumber(row.foreign_cash);
  const cnyFtp = decimalNumber(row.cny_ftp);
  const foreignFtp = decimalNumber(row.foreign_ftp);

  if (cnyNet === null && foreignNet === null) {
    hints.push("\u51c0\u6536\u5165\u62c6\u5206\u7f3a\u5931");
  } else {
    const dominantCurrency =
      Math.abs(cnyNet ?? 0) >= Math.abs(foreignNet ?? 0)
        ? dominantNetHint("\u4eba\u6c11\u5e01", cnyNet)
        : dominantNetHint("\u5916\u5e01", foreignNet);
    if (dominantCurrency) {
      hints.push(dominantCurrency);
    }
  }

  const currencyPressureHints: string[] = [];
  if (cnyNet !== null && cnyNet < 0) {
    currencyPressureHints.push("\u4eba\u6c11\u5e01\u51c0\u6536\u5165\u4e3a\u8d1f");
  } else if (
    cnyCash !== null &&
    cnyFtp !== null &&
    Math.abs(cnyFtp) > Math.abs(cnyCash) &&
    Math.abs(cnyFtp) > 0
  ) {
    currencyPressureHints.push("\u4eba\u6c11\u5e01FTP\u9ad8\u4e8e\u73b0\u91d1");
  }

  if (foreignNet !== null && foreignNet < 0) {
    currencyPressureHints.push("\u5916\u5e01\u51c0\u6536\u5165\u4e3a\u8d1f");
  } else if (
    foreignCash !== null &&
    foreignFtp !== null &&
    Math.abs(foreignFtp) > Math.abs(foreignCash) &&
    Math.abs(foreignFtp) > 0
  ) {
    currencyPressureHints.push("\u5916\u5e01FTP\u9ad8\u4e8e\u73b0\u91d1");
  }

  if (currencyPressureHints.length > 0) {
    hints.push(currencyPressureHints.join("\uff0c"));
  }

  if (hints.length === 0) {
    return "\u73b0\u91d1\u3001FTP\u3001\u51c0\u6536\u5165\u62c6\u5206\u5e73\u7a33";
  }
  return hints.slice(0, 2).join("\uff1b");
}

function buildProductCategoryDiagnosticsMatrixRow(
  row: ProductCategoryPnlRow,
): ProductCategoryDiagnosticsMatrixRow {
  const scaleDisplay = formatProductCategoryRowDisplayValue(row, row.cnx_scale);
  const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(row.weighted_yield);
  return {
    categoryId: row.category_id,
    categoryLabel: row.category_name,
    sideLabel: productCategorySideLabel(row.side),
    scaleLabel: scaleDisplay === "-" ? "\u89c4\u6a21\u7f3a\u5931" : `${scaleDisplay} \u4ebf\u5143`,
    scaleMissing: scaleDisplay === "-",
    businessNetIncomeLabel: formatProductCategoryDiagnosticMoneyLabel(row, row.business_net_income),
    businessNetIncomeTone: toneNameForValue(row.business_net_income),
    yieldLabel: yieldDisplay.label,
    yieldMissing: yieldDisplay.missing,
    cnyNetLabel: formatProductCategoryDiagnosticMoneyLabel(row, row.cny_net),
    cnyNetTone: toneNameForValue(row.cny_net),
    foreignNetLabel: formatProductCategoryDiagnosticMoneyLabel(row, row.foreign_net),
    foreignNetTone: toneNameForValue(row.foreign_net),
    driverHint: buildProductCategoryDriverHint(row),
  };
}

function buildSpreadMovementDriverHint(
  assetYieldDelta: number | null,
  liabilityYieldDelta: number | null,
  spreadDelta: number | null,
): string {
  if (assetYieldDelta === null || liabilityYieldDelta === null || spreadDelta === null) {
    return "\u7f3a\u5c11\u5b8c\u6574\u6536\u76ca\u7387\u5bf9\u6bd4";
  }
  if (spreadDelta === 0) {
    return "\u8d44\u4ea7\u4e0e\u8d1f\u503a\u6536\u76ca\u7387\u53d8\u52a8\u57fa\u672c\u5bf9\u51b2\uff0c\u5229\u5dee\u6301\u5e73";
  }

  const assetAbs = Math.abs(assetYieldDelta);
  const liabilityAbs = Math.abs(liabilityYieldDelta);
  if (spreadDelta > 0) {
    if (assetAbs >= liabilityAbs) {
      return assetYieldDelta >= 0
        ? "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0a\u884c\u4e3b\u5bfc\u5229\u5dee\u8d70\u9614"
        : "\u8d44\u4ea7\u6536\u76ca\u7387\u56de\u843d\u8f83\u7f13\uff0c\u5229\u5dee\u4ecd\u8d70\u9614";
    }
    return liabilityYieldDelta <= 0
      ? "\u8d1f\u503a\u6536\u76ca\u7387\u4e0b\u884c\u4e3b\u5bfc\u5229\u5dee\u8d70\u9614"
      : "\u8d1f\u503a\u6536\u76ca\u7387\u4e0a\u884c\u8f83\u7f13\uff0c\u5229\u5dee\u4ecd\u8d70\u9614";
  }

  if (assetAbs >= liabilityAbs) {
    return assetYieldDelta <= 0
      ? "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0b\u884c\u4e3b\u5bfc\u5229\u5dee\u6536\u7a84"
      : "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0a\u884c\u4e0d\u8db3\uff0c\u5229\u5dee\u6536\u7a84";
  }
  return liabilityYieldDelta >= 0
    ? "\u8d1f\u503a\u6536\u76ca\u7387\u4e0a\u884c\u4e3b\u5bfc\u5229\u5dee\u6536\u7a84"
    : "\u8d1f\u503a\u6536\u76ca\u7387\u4e0b\u884c\u4e0d\u8db3\uff0c\u5229\u5dee\u6536\u7a84";
}

function buildProductCategorySpreadMovementAttribution(input: {
  trendSnapshots?: ProductCategoryTrendSnapshot[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
}): ProductCategorySpreadMovementAttribution {
  const currentSnapshot =
    input.trendSnapshots?.[0] ??
    (input.assetTotal || input.liabilityTotal
      ? {
          reportDate: input.assetTotal?.report_date ?? input.liabilityTotal?.report_date ?? "",
          rows: [],
          assetTotal: input.assetTotal,
          liabilityTotal: input.liabilityTotal,
        }
      : null);
  const priorSnapshot =
    input.trendSnapshots?.slice(1).find((snapshot) => spreadBp(snapshot) !== null) ?? null;

  const currentLabel = currentSnapshot?.label ?? formatProductCategoryReportMonthLabel(currentSnapshot?.reportDate ?? "");
  const priorLabel = priorSnapshot?.label ?? formatProductCategoryReportMonthLabel(priorSnapshot?.reportDate ?? "");
  const currentAssetYield = decimalNumber(currentSnapshot?.assetTotal?.weighted_yield);
  const currentLiabilityYield = decimalNumber(currentSnapshot?.liabilityTotal?.weighted_yield);
  const currentSpread = currentSnapshot ? spreadBp(currentSnapshot) : null;
  const priorAssetYield = decimalNumber(priorSnapshot?.assetTotal?.weighted_yield);
  const priorLiabilityYield = decimalNumber(priorSnapshot?.liabilityTotal?.weighted_yield);
  const priorSpread = priorSnapshot ? spreadBp(priorSnapshot) : null;
  const assetYieldDelta =
    currentAssetYield === null || priorAssetYield === null ? null : (currentAssetYield - priorAssetYield) * 100;
  const liabilityYieldDelta =
    currentLiabilityYield === null || priorLiabilityYield === null
      ? null
      : (currentLiabilityYield - priorLiabilityYield) * 100;
  const spreadDelta = spreadDeltaBp(currentSpread, priorSpread);

  const base: ProductCategorySpreadMovementAttributionBase = {
    currentLabel: currentLabel || "\u5f53\u524d\u671f",
    priorLabel: priorLabel || "\u4e0a\u671f",
    currentAssetYieldLabel: currentAssetYield === null ? "\u7f3a\u5931" : `${currentAssetYield.toFixed(2)}%`,
    currentLiabilityYieldLabel:
      currentLiabilityYield === null ? "\u7f3a\u5931" : `${currentLiabilityYield.toFixed(2)}%`,
    currentSpreadLabel: bpLabel(currentSpread),
    priorSpreadLabel: bpLabel(priorSpread),
    assetYieldDeltaLabel: signedBpLabel(assetYieldDelta),
    liabilityYieldDeltaLabel: signedBpLabel(liabilityYieldDelta),
    spreadDeltaLabel: signedBpLabel(spreadDelta),
    driverHint: buildSpreadMovementDriverHint(assetYieldDelta, liabilityYieldDelta, spreadDelta),
  };

  if (!currentSnapshot) {
    return {
      state: "incomplete",
      reason: "\u5f53\u524d\u5feb\u7167\u7f3a\u5931\uff0c\u65e0\u6cd5\u6784\u5efa\u5229\u5dee\u5f52\u56e0\u3002",
      ...base,
    };
  }
  if (currentAssetYield === null || currentLiabilityYield === null || currentSpread === null) {
    return {
      state: "incomplete",
      reason:
        "\u5f53\u524d\u8d44\u4ea7\u7aef\u6216\u8d1f\u503a\u7aef\u6536\u76ca\u7387\u7f3a\u5931\uff0c\u65e0\u6cd5\u8ba1\u7b97\u5f53\u671f\u5229\u5dee\u3002",
      ...base,
    };
  }
  if (!priorSnapshot) {
    return {
      state: "incomplete",
      reason:
        "\u7f3a\u5c11\u53ef\u6bd4\u4e0a\u671f\u8d8b\u52bf\u5feb\u7167\uff0c\u65e0\u6cd5\u5b8c\u6210\u5229\u5dee\u53d8\u52a8\u5f52\u56e0\u3002",
      ...base,
    };
  }

  return {
    state: "ready",
    ...base,
  };
}

export function buildProductCategoryDiagnosticsSurface(input: {
  rows: ProductCategoryPnlRow[];
  trendSnapshots?: ProductCategoryTrendSnapshot[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
}): ProductCategoryDiagnosticsSurface {
  const productRows = input.rows.filter((row) => !row.is_total && row.category_id !== "grand_total");
  const matrixRows = productRows.map(buildProductCategoryDiagnosticsMatrixRow);
  const negativeWatchlistRows = productRows
    .filter((row) => {
      const businessNetIncome = decimalNumber(row.business_net_income);
      return businessNetIncome !== null && businessNetIncome < 0;
    })
    .sort((left, right) => Number(left.business_net_income) - Number(right.business_net_income))
    .map((row) => {
      const scaleDisplay = formatProductCategoryRowDisplayValue(row, row.cnx_scale);
      const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(row.weighted_yield);
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name,
        sideLabel: productCategorySideLabel(row.side),
        lossLabel: formatProductCategoryDiagnosticMoneyLabel(row, row.business_net_income),
        scaleLabel: scaleDisplay === "-" ? "\u89c4\u6a21\u7f3a\u5931" : `${scaleDisplay} \u4ebf\u5143`,
        scaleMissing: scaleDisplay === "-",
        yieldLabel: yieldDisplay.label,
        yieldMissing: yieldDisplay.missing,
        driverHint: buildProductCategoryDriverHint(row),
      };
    });

  return {
    headlineTotalLabel: input.grandTotal
      ? `${formatProductCategoryValue(input.grandTotal.business_net_income)} \u4ebf\u5143`
      : null,
    matrixRows,
    matrixEmptyCopy:
      matrixRows.length === 0 ? "\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002" : null,
    negativeWatchlistRows,
    negativeWatchlistEmptyCopy:
      matrixRows.length === 0
        ? "\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002"
        : negativeWatchlistRows.length === 0
          ? "\u5f53\u524d\u6240\u9009\u53e3\u5f84\u4e0b\u6682\u65e0 business_net_income \u4e3a\u8d1f\u7684\u4ea7\u54c1\u884c\u3002"
          : null,
    spreadAttribution: buildProductCategorySpreadMovementAttribution({
      trendSnapshots: input.trendSnapshots,
      assetTotal: input.assetTotal,
      liabilityTotal: input.liabilityTotal,
    }),
  };
}

export function selectProductCategoryTrendReportDates(
  selectedDate: string,
  reportDates: string[] | undefined,
  limit = 8,
): string[] {
  return selectProductCategoryTrendReportPoints(selectedDate, reportDates, "monthly", limit).map(
    (point) => point.reportDate,
  );
}

export function selectProductCategoryTrendReportPoints(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
  limit = 8,
): ProductCategoryTrendReportPoint[] {
  if (!selectedDate) {
    return [];
  }
  const dates = Array.from(new Set([selectedDate, ...(reportDates ?? [])].filter(Boolean)));
  const selected = parseProductCategoryReportDate(selectedDate);
  if (!selected) {
    return dates
      .slice(0, limit)
      .map((reportDate) => ({
        reportDate,
        view: monthlyView,
        label: formatProductCategoryReportMonthLabel(reportDate),
      }));
  }

  const chronologicalPoints: ProductCategoryTrendReportPoint[] = [];
  const previousYear = selected.year - 1;
  ([1, 2, 3] as const).forEach((quarter) => {
    const reportDate = findProductCategoryReportDateForMonth(dates, previousYear, quarter * 3, selectedDate);
    if (!reportDate) {
      return;
    }
    pushUniqueProductCategoryTrendPoint(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: `${previousYear}\u5e74Q${quarter}`,
    });
  });

  ([11, 12] as const).forEach((month) => {
    const reportDate = findProductCategoryReportDateForMonth(dates, previousYear, month, selectedDate);
    if (!reportDate) {
      return;
    }
    pushUniqueProductCategoryTrendPoint(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabel(reportDate),
    });
  });

  for (let month = 1; month <= selected.month; month += 1) {
    const reportDate = findProductCategoryReportDateForMonth(dates, selected.year, month, selectedDate);
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPoint(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabel(reportDate),
    });
  }

  if (chronologicalPoints.length === 0) {
    return dates
      .slice(0, limit)
      .map((reportDate) => ({
        reportDate,
        view: monthlyView,
        label: formatProductCategoryReportMonthLabel(reportDate),
      }));
  }
  return chronologicalPoints.slice(-limit).reverse();
}

export function selectProductCategoryTwoYearInterestSpreadReportPoints(
  selectedDate: string,
  reportDates: string[] | undefined,
  monthlyView = "monthly",
): ProductCategoryTrendReportPoint[] {
  if (!selectedDate) {
    return [];
  }
  const dates = Array.from(new Set([selectedDate, ...(reportDates ?? [])].filter(Boolean)));
  const selected = parseProductCategoryReportDate(selectedDate);
  if (!selected) {
    return dates.slice(0, 6).map((reportDate) => ({
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabel(reportDate),
    }));
  }

  const chronologicalPoints: ProductCategoryTrendReportPoint[] = [];
  const previousYear = selected.year - 1;
  for (let month = 1; month <= 12; month += 1) {
    const reportDate = findProductCategoryReportDateForMonth(dates, previousYear, month, selectedDate);
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPoint(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabel(reportDate),
    });
  }

  for (let month = 1; month <= selected.month; month += 1) {
    const reportDate = findProductCategoryReportDateForMonth(dates, selected.year, month, selectedDate);
    if (!reportDate) {
      continue;
    }
    pushUniqueProductCategoryTrendPoint(chronologicalPoints, {
      reportDate,
      view: monthlyView,
      label: formatProductCategoryReportMonthLabel(reportDate),
    });
  }
  return chronologicalPoints.reverse();
}

export function buildProductCategoryTrendSnapshot(
  payload: ProductCategoryPnlPayload,
  label?: string,
): ProductCategoryTrendSnapshot {
  return {
    reportDate: payload.report_date,
    label,
    view: payload.view,
    rows: selectProductCategoryDetailRows(payload.rows, undefined),
    assetTotal: payload.asset_total,
    liabilityTotal: payload.liability_total,
    grandTotal: payload.grand_total,
  };
}

export function selectProductCategoryTplScaleYieldChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryTplScaleYieldChart | null {
  const chart = buildSnapshotChart(snapshots, (snapshot) => {
    const row = findProductCategoryRow(snapshot.rows, "bond_tpl");
    if (!row) {
      return null;
    }
    const cnyScale = yiNumber(row.cny_scale);
    const foreignScale = yiNumber(row.foreign_scale);
    const weightedYield = percentNumber(row.weighted_yield);
    if (cnyScale === null || foreignScale === null || weightedYield === null) {
      return null;
    }
    return { cnyScale, foreignScale, weightedYield };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    cnyScale: chart.points.map((point) => point.cnyScale),
    foreignScale: chart.points.map((point) => point.foreignScale),
    weightedYield: chart.points.map((point) => point.weightedYield),
  };
}

export function selectProductCategoryCurrencyNetIncomeChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryCurrencyNetIncomeChart | null {
  const chart = buildSnapshotChart(snapshots, (snapshot) => {
    const row = snapshot.grandTotal;
    if (!row) {
      return null;
    }
    const cnyNet = yiNumber(row.cny_net);
    const foreignNet = yiNumber(row.foreign_net);
    if (cnyNet === null || foreignNet === null) {
      return null;
    }
    return { cnyNet, foreignNet };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    cnyNet: chart.points.map((point) => point.cnyNet),
    foreignNet: chart.points.map((point) => point.foreignNet),
  };
}

export function selectProductCategoryInterestEarningIncomeScaleChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestEarningIncomeScaleChart | null {
  const chart = buildSnapshotChart(snapshots, (snapshot) => {
    const row = findProductCategoryRow(snapshot.rows, "interest_earning_assets");
    if (!row) {
      return null;
    }
    const scale = yiNumber(row.cnx_scale);
    const income = yiNumber(row.business_net_income);
    if (scale === null || income === null) {
      return null;
    }
    return { scale, income };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    scale: chart.points.map((point) => point.scale),
    income: chart.points.map((point) => point.income),
  };
}

export function selectProductCategoryInterestSpreadChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryInterestSpreadChart | null {
  const chart = buildSnapshotChart(snapshots, (snapshot) => {
    const assetRow = findProductCategoryRow(snapshot.rows, "interest_earning_assets");
    const liabilityRow = snapshot.liabilityTotal;
    if (!assetRow || !liabilityRow) {
      return null;
    }
    const assetYield = percentNumber(assetRow.weighted_yield);
    const liabilityYield = percentNumber(liabilityRow.weighted_yield);
    if (assetYield === null || liabilityYield === null) {
      return null;
    }
    return {
      assetYield,
      liabilityYield,
      spread: Number((assetYield - liabilityYield).toFixed(2)),
    };
  });
  if (chart.labels.length === 0) {
    return null;
  }
  return {
    labels: chart.labels,
    assetYield: chart.points.map((point) => point.assetYield),
    liabilityYield: chart.points.map((point) => point.liabilityYield),
    spread: chart.points.map((point) => point.spread),
  };
}

export function selectProductCategoryInterestSpreadYearComparisonChart(
  snapshots: ProductCategoryTrendSnapshot[],
  basis: ProductCategoryInterestSpreadBasis = "weighted",
): ProductCategoryInterestSpreadYearComparisonChart | null {
  const yearMonthSpread = new Map<number, Map<number, number | null>>();
  const months = new Set<number>();
  chronologicalProductCategorySnapshots(snapshots).forEach((snapshot) => {
    const parsed = parseProductCategoryReportDate(snapshot.reportDate);
    const assetRow = findProductCategoryRow(snapshot.rows, "interest_earning_assets");
    const liabilityRow = snapshot.liabilityTotal;
    if (!parsed || !assetRow || !liabilityRow) {
      return;
    }
    const spread = productCategoryInterestSpreadForBasis(snapshot, assetRow, liabilityRow, basis);
    if (spread === null && basis === "weighted") {
      return;
    }
    const existing = yearMonthSpread.get(parsed.year) ?? new Map<number, number | null>();
    existing.set(parsed.month, spread);
    yearMonthSpread.set(parsed.year, existing);
    months.add(parsed.month);
  });
  if (yearMonthSpread.size === 0 || months.size === 0) {
    return null;
  }

  const sortedMonths = Array.from(months).sort((left, right) => left - right);
  const sortedYears = Array.from(yearMonthSpread.keys()).sort((left, right) => left - right);
  return {
    labels: sortedMonths.map((month) => formatProductCategoryShortMonthLabel(month)),
    monthKeys: sortedMonths,
    series: sortedYears.map((year) => ({
      year: `${year}\u5e74`,
      spread: sortedMonths.map((month) => yearMonthSpread.get(year)?.get(month) ?? null),
    })),
  };
}

export function selectProductCategoryIntermediateBusinessIncomeYearComparisonChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryIntermediateBusinessIncomeYearComparisonChart | null {
  const yearMonthIncome = new Map<number, Map<number, number | null>>();
  const months = new Set<number>();
  let hasIncomeValue = false;

  chronologicalProductCategorySnapshots(snapshots).forEach((snapshot) => {
    const parsed = parseProductCategoryReportDate(snapshot.reportDate);
    if (!parsed) {
      return;
    }
    const row = findProductCategoryRow(snapshot.rows, "intermediate_business_income");
    const income = row ? yiNumber(row.business_net_income) : null;
    if (income !== null) {
      hasIncomeValue = true;
    }
    const existing = yearMonthIncome.get(parsed.year) ?? new Map<number, number | null>();
    existing.set(parsed.month, income);
    yearMonthIncome.set(parsed.year, existing);
    months.add(parsed.month);
  });

  if (!hasIncomeValue || yearMonthIncome.size === 0 || months.size === 0) {
    return null;
  }

  const sortedMonths = Array.from(months).sort((left, right) => left - right);
  const sortedYears = Array.from(yearMonthIncome.keys()).sort((left, right) => left - right);
  return {
    labels: sortedMonths.map((month) => formatProductCategoryShortMonthLabel(month)),
    series: sortedYears.map((year) => ({
      year: `${year}\u5e74`,
      income: sortedMonths.map((month) => yearMonthIncome.get(year)?.get(month) ?? null),
    })),
  };
}

export function selectProductCategoryInterestSpreadAttributionSurface(
  snapshots: ProductCategoryTrendSnapshot[],
  options: ProductCategoryInterestSpreadAttributionSelection,
  currentYear: number,
): ProductCategoryInterestSpreadAttributionSurface {
  const current = findInterestSpreadAttributionSnapshot(snapshots, currentYear, options.month);
  const prior = findInterestSpreadAttributionSnapshot(snapshots, currentYear - 1, options.month);
  const currentMetrics = interestSpreadAttributionMetrics(current, options.basis);
  const priorMetrics = interestSpreadAttributionMetrics(prior, options.basis);
  const assetContributionBp = basisPointDelta(currentMetrics.assetYield, priorMetrics.assetYield);
  const liabilityContributionBp = basisPointDelta(priorMetrics.liabilityYield, currentMetrics.liabilityYield);
  const spreadDelta =
    assetContributionBp === null || liabilityContributionBp === null
      ? null
      : Number((assetContributionBp + liabilityContributionBp).toFixed(1));
  const incompleteReasons = interestSpreadAttributionIncompleteReasons({
    current,
    prior,
    currentMetrics,
    priorMetrics,
    basis: options.basis,
  });

  return {
    selected: {
      basis: options.basis,
      month: options.month,
      currentYear,
      priorYear: currentYear - 1,
      currentReportDate: current?.reportDate ?? null,
      priorReportDate: prior?.reportDate ?? null,
    },
    complete: incompleteReasons.length === 0,
    incompleteReasons,
    summary: {
      assetYieldCurrent: currentMetrics.assetYield,
      assetYieldPrior: priorMetrics.assetYield,
      liabilityYieldCurrent: currentMetrics.liabilityYield,
      liabilityYieldPrior: priorMetrics.liabilityYield,
      spreadCurrent: currentMetrics.spread,
      spreadPrior: priorMetrics.spread,
      assetContributionBp,
      liabilityContributionBp,
      spreadDeltaBp: spreadDelta,
    },
    rows: [
      {
        key: "asset_yield",
        label: "\u751f\u606f\u8d44\u4ea7\u6536\u76ca\u7387",
        priorValue: priorMetrics.assetYield,
        currentValue: currentMetrics.assetYield,
        deltaBp: assetContributionBp,
        priorLabel: interestSpreadPercentLabel(priorMetrics.assetYield),
        currentLabel: interestSpreadPercentLabel(currentMetrics.assetYield),
        contributionLabel: signedBpLabelWithOneDecimal(assetContributionBp),
        explanation: "\u8d44\u4ea7\u6536\u76ca\u7387\u4e0a\u884c\u6269\u5927\u5229\u5dee\uff0c\u4e0b\u884c\u538b\u7f29\u5229\u5dee",
      },
      {
        key: "liability_cost",
        label: "\u8d1f\u503a\u7aef\u6210\u672c",
        priorValue: priorMetrics.liabilityYield,
        currentValue: currentMetrics.liabilityYield,
        deltaBp: liabilityContributionBp,
        priorLabel: interestSpreadPercentLabel(priorMetrics.liabilityYield),
        currentLabel: interestSpreadPercentLabel(currentMetrics.liabilityYield),
        contributionLabel: signedBpLabelWithOneDecimal(liabilityContributionBp),
        explanation: "\u8d1f\u503a\u6210\u672c\u4e0a\u884c\u538b\u7f29\u5229\u5dee\uff0c\u4e0b\u884c\u6269\u5927\u5229\u5dee",
      },
      {
        key: "spread",
        label: "\u751f\u606f\u8d44\u4ea7\u5229\u5dee",
        priorValue: priorMetrics.spread,
        currentValue: currentMetrics.spread,
        deltaBp: spreadDelta,
        priorLabel: interestSpreadPercentLabel(priorMetrics.spread),
        currentLabel: interestSpreadPercentLabel(currentMetrics.spread),
        contributionLabel: signedBpLabelWithOneDecimal(spreadDelta),
        explanation: "\u5229\u5dee\u53d8\u5316=\u8d44\u4ea7\u6536\u76ca\u7387\u8d21\u732e+\u8d1f\u503a\u6210\u672c\u8d21\u732e",
      },
    ],
    details: [
      {
        key: "interest_earning_assets",
        label: "\u751f\u606f\u8d44\u4ea7",
        prior: interestSpreadAttributionDetailPoint(prior, priorMetrics.assetRow, priorMetrics.assetYield, options.basis),
        current: interestSpreadAttributionDetailPoint(
          current,
          currentMetrics.assetRow,
          currentMetrics.assetYield,
          options.basis,
        ),
      },
      {
        key: "liability_total",
        label: "\u8d1f\u503a\u7aef\u5408\u8ba1",
        prior: interestSpreadAttributionDetailPoint(
          prior,
          priorMetrics.liabilityRow,
          priorMetrics.liabilityYield,
          options.basis,
        ),
        current: interestSpreadAttributionDetailPoint(
          current,
          currentMetrics.liabilityRow,
          currentMetrics.liabilityYield,
          options.basis,
        ),
      },
    ],
  };
}

function findInterestSpreadAttributionSnapshot(
  snapshots: ProductCategoryTrendSnapshot[],
  year: number,
  month: number,
): ProductCategoryTrendSnapshot | null {
  return (
    snapshots.find((snapshot) => {
      const parsed = parseProductCategoryReportDate(snapshot.reportDate);
      return parsed?.year === year && parsed.month === month;
    }) ?? null
  );
}

function interestSpreadAttributionMetrics(
  snapshot: ProductCategoryTrendSnapshot | null,
  basis: ProductCategoryInterestSpreadBasis,
): {
  assetYield: number | null;
  liabilityYield: number | null;
  spread: number | null;
  assetRow: ProductCategoryPnlRow | null;
  liabilityRow: ProductCategoryPnlRow | null;
} {
  if (!snapshot) {
    return { assetYield: null, liabilityYield: null, spread: null, assetRow: null, liabilityRow: null };
  }
  const assetRow = findProductCategoryRow(snapshot.rows, "interest_earning_assets") ?? null;
  const liabilityRow = snapshot.liabilityTotal ?? null;
  if (!assetRow || !liabilityRow) {
    return { assetYield: null, liabilityYield: null, spread: null, assetRow, liabilityRow };
  }
  const assetYield =
    basis === "cny"
      ? annualizedProductCategoryYield(assetRow.cny_cash, assetRow.cny_scale, snapshot.reportDate, snapshot.view)
      : percentNumber(assetRow.weighted_yield);
  const liabilityYield =
    basis === "cny"
      ? annualizedProductCategoryYield(
          liabilityRow.cny_cash,
          liabilityRow.cny_scale,
          snapshot.reportDate,
          snapshot.view,
        )
      : percentNumber(liabilityRow.weighted_yield);
  return {
    assetYield,
    liabilityYield,
    spread: assetYield === null || liabilityYield === null ? null : Number((assetYield - liabilityYield).toFixed(2)),
    assetRow,
    liabilityRow,
  };
}

function basisPointDelta(current: number | null, prior: number | null): number | null {
  if (current === null || prior === null) {
    return null;
  }
  return Number(((current - prior) * 100).toFixed(1));
}

function interestSpreadPercentLabel(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

function signedBpLabelWithOneDecimal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${Math.abs(value).toFixed(1)}bp`;
}

function interestSpreadAttributionIncompleteReasons(input: {
  current: ProductCategoryTrendSnapshot | null;
  prior: ProductCategoryTrendSnapshot | null;
  currentMetrics: { assetYield: number | null; liabilityYield: number | null };
  priorMetrics: { assetYield: number | null; liabilityYield: number | null };
  basis: ProductCategoryInterestSpreadBasis;
}): string[] {
  const prefix = input.basis === "cny" ? "\u4eba\u6c11\u5e01" : "\u5168\u53e3\u5f84";
  const reasons: string[] = [];
  if (!input.current) {
    reasons.push("\u7f3a\u5c11\u5f53\u524d\u6708\u6570\u636e");
  }
  if (!input.prior) {
    reasons.push("\u7f3a\u5c11\u4e0a\u5e74\u540c\u6708\u6570\u636e");
  }
  if (input.currentMetrics.assetYield === null) {
    reasons.push(`${prefix}\u5f53\u524d\u6708\u751f\u606f\u8d44\u4ea7\u6536\u76ca\u7387\u4e0d\u53ef\u7528`);
  }
  if (input.priorMetrics.assetYield === null) {
    reasons.push(`${prefix}\u4e0a\u5e74\u540c\u6708\u751f\u606f\u8d44\u4ea7\u6536\u76ca\u7387\u4e0d\u53ef\u7528`);
  }
  if (input.currentMetrics.liabilityYield === null) {
    reasons.push(`${prefix}\u5f53\u524d\u6708\u8d1f\u503a\u7aef\u6210\u672c\u4e0d\u53ef\u7528`);
  }
  if (input.priorMetrics.liabilityYield === null) {
    reasons.push(`${prefix}\u4e0a\u5e74\u540c\u6708\u8d1f\u503a\u7aef\u6210\u672c\u4e0d\u53ef\u7528`);
  }
  return reasons;
}

function interestSpreadAttributionDetailPoint(
  snapshot: ProductCategoryTrendSnapshot | null,
  row: ProductCategoryPnlRow | null,
  yieldValue: number | null,
  basis: ProductCategoryInterestSpreadBasis,
): ProductCategoryInterestSpreadAttributionDetailPoint {
  const amountField = basis === "cny" ? "cny_scale" : "cnx_scale";
  const cashField = basis === "cny" ? "cny_cash" : "cnx_cash";
  return {
    reportLabel: snapshot?.label ?? (snapshot ? formatProductCategoryReportMonthLabel(snapshot.reportDate) : "-"),
    amountLabel: row ? `${formatProductCategoryRowDisplayValue(row, row[amountField])}\u4ebf\u5143` : "-",
    cashLabel: row ? `${formatProductCategoryRowDisplayValue(row, row[cashField])}\u4ebf\u5143` : "-",
    yieldLabel: yieldValue === null ? "-" : `${formatProductCategoryYieldValue(yieldValue)}%`,
  };
}

function productCategoryInterestSpreadForBasis(
  snapshot: ProductCategoryTrendSnapshot,
  assetRow: ProductCategoryPnlRow,
  liabilityRow: ProductCategoryPnlRow,
  basis: ProductCategoryInterestSpreadBasis,
): number | null {
  const assetYield =
    basis === "cny"
      ? annualizedProductCategoryYield(assetRow.cny_cash, assetRow.cny_scale, snapshot.reportDate, snapshot.view)
      : percentNumber(assetRow.weighted_yield);
  const liabilityYield =
    basis === "cny"
      ? annualizedProductCategoryYield(
          liabilityRow.cny_cash,
          liabilityRow.cny_scale,
          snapshot.reportDate,
          snapshot.view,
        )
      : percentNumber(liabilityRow.weighted_yield);
  if (assetYield === null || liabilityYield === null) {
    return null;
  }
  return Number((assetYield - liabilityYield).toFixed(2));
}

export function selectProductCategoryLiabilitySideTrendChart(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilitySideTrendChart | null {
  const ordered = chronologicalProductCategorySnapshots(snapshots);
  if (ordered.length === 0) {
    return null;
  }
  const labels: string[] = [];
  const totalAverageDaily: Array<number | null> = [];
  const totalRate: Array<number | null> = [];
  const incompleteReasons: string[] = [];

  ordered.forEach((snapshot) => {
    const label = snapshot.label ?? formatProductCategoryReportMonthLabel(snapshot.reportDate);
    const averageDaily = yiNumber(snapshot.liabilityTotal?.cnx_scale);
    const rate = percentNumber(snapshot.liabilityTotal?.weighted_yield);
    labels.push(label);
    totalAverageDaily.push(averageDaily);
    totalRate.push(rate);
    if (averageDaily === null) {
      incompleteReasons.push(`${label}负债端日均额缺失`);
    }
    if (rate === null) {
      incompleteReasons.push(`${label}负债端利率缺失`);
    }
  });

  return { labels, totalAverageDaily, totalRate, incompleteReasons };
}

function latestComparableLiabilityValue(input: {
  snapshots: ProductCategoryTrendSnapshot[];
  categoryId: string;
  metric: "cnx_scale" | "weighted_yield";
  beforeIndex?: number;
}): { value: number; label: string; index: number } | null {
  const upperBound = input.beforeIndex ?? input.snapshots.length;
  for (let index = upperBound - 1; index >= 0; index -= 1) {
    const snapshot = input.snapshots[index];
    if (!snapshot) {
      continue;
    }
    const row = liabilityDetailRowsFromSnapshot(snapshot).find((item) => item.category_id === input.categoryId);
    const value =
      input.metric === "cnx_scale" ? yiNumber(row?.cnx_scale) : percentNumber(row?.weighted_yield);
    if (value !== null) {
      return {
        value,
        label: snapshot.label ?? formatProductCategoryReportMonthLabel(snapshot.reportDate),
        index,
      };
    }
  }
  return null;
}

function liabilityComparisonLabel(input: {
  amountLatestLabel: string | null;
  amountPriorLabel: string | null;
  rateLatestLabel: string | null;
  ratePriorLabel: string | null;
}): string {
  const amountLabel =
    input.amountLatestLabel && input.amountPriorLabel
      ? `${input.amountPriorLabel} → ${input.amountLatestLabel}`
      : null;
  const rateLabel =
    input.rateLatestLabel && input.ratePriorLabel
      ? `${input.ratePriorLabel} → ${input.rateLatestLabel}`
      : null;
  if (amountLabel && rateLabel && amountLabel !== rateLabel) {
    return `日均额：${amountLabel}；利率：${rateLabel}`;
  }
  if (!input.amountLatestLabel && !input.rateLatestLabel) {
    return "当前指标缺失";
  }
  return amountLabel ?? rateLabel ?? "缺少可比上期";
}

function adjacentProductCategoryMonths(
  previous: ProductCategoryTrendSnapshot | undefined,
  latest: ProductCategoryTrendSnapshot | undefined,
): boolean {
  const previousDate = previous ? parseProductCategoryReportDate(previous.reportDate) : null;
  const latestDate = latest ? parseProductCategoryReportDate(latest.reportDate) : null;
  if (!previousDate || !latestDate) {
    return false;
  }
  return latestDate.year * 12 + latestDate.month - (previousDate.year * 12 + previousDate.month) === 1;
}

type ProductCategoryLiabilityAmountField = "cnx_scale" | "cny_scale" | "foreign_scale";
type ProductCategoryLiabilityCashField = "cnx_cash" | "cny_cash" | "foreign_cash";

function daysForProductCategoryView(reportDate: string | undefined, view: string | undefined): number | null {
  if (!reportDate) {
    return null;
  }
  const parsed = parseProductCategoryReportDate(reportDate);
  if (!parsed) {
    return null;
  }
  const monthDays = new Date(parsed.year, parsed.month, 0).getDate();
  if (view === "monthly") {
    return monthDays;
  }
  if (view === "qtd") {
    const quarterStartMonth = Math.floor((parsed.month - 1) / 3) * 3 + 1;
    let days = 0;
    for (let month = quarterStartMonth; month <= parsed.month; month += 1) {
      days += new Date(parsed.year, month, 0).getDate();
    }
    return days;
  }
  let days = 0;
  for (let month = 1; month <= parsed.month; month += 1) {
    days += new Date(parsed.year, month, 0).getDate();
  }
  return days;
}

function annualizedProductCategoryYield(
  cash: DecimalLike | null | undefined,
  scale: DecimalLike | null | undefined,
  reportDate: string | undefined,
  view: string | undefined,
): number | null {
  const cashValue = decimalNumber(cash);
  const scaleValue = decimalNumber(scale);
  const days = daysForProductCategoryView(reportDate, view);
  if (cashValue === null || scaleValue === null || scaleValue === 0 || days === null || days <= 0) {
    return null;
  }
  return Number(((cashValue / days) * DAYS_IN_YEAR / scaleValue * 100).toFixed(2));
}

function liabilityDetailMetricLabels(
  row: ProductCategoryPnlRow | undefined,
  amountField: ProductCategoryLiabilityAmountField = "cnx_scale",
): {
  amountLabel: string;
  amountValue: number | null;
  rateLabel: string;
  rateValue: number | null;
} {
  const amountValue = yiNumber(row?.[amountField]);
  const rateValue = percentNumber(row?.weighted_yield);
  return {
    amountLabel: amountValue !== null ? amountValue.toFixed(2) : "-",
    amountValue,
    rateLabel: rateValue !== null ? rateValue.toFixed(2) : "-",
    rateValue,
  };
}

function liabilityCurrencyMetricLabels(
  row: ProductCategoryPnlRow | undefined,
  amountField: ProductCategoryLiabilityAmountField,
  cashField: ProductCategoryLiabilityCashField,
): {
  amountLabel: string;
  amountValue: number | null;
  rateLabel: string;
  rateValue: number | null;
} {
  const amountValue = yiNumber(row?.[amountField]);
  const rateValue = annualizedProductCategoryYield(
    row?.[cashField],
    row?.[amountField],
    row?.report_date,
    row?.view,
  );
  return {
    amountLabel: amountValue !== null ? amountValue.toFixed(2) : "-",
    amountValue,
    rateLabel: rateValue !== null ? rateValue.toFixed(2) : "-",
    rateValue,
  };
}

function buildLiabilityDetailMatrixRow(input: {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  periods: ProductCategoryLiabilityDetailMatrixPeriod[];
  latestIndex: number;
  previousIndex: number;
  rowAt: (index: number) => ProductCategoryPnlRow | undefined;
}): ProductCategoryLiabilityDetailMatrixRow {
  const latestMetrics = liabilityDetailMetricLabels(input.rowAt(input.latestIndex));
  const previousMetrics = liabilityDetailMetricLabels(input.rowAt(input.previousIndex));
  const amountDelta =
    latestMetrics.amountValue !== null && previousMetrics.amountValue !== null
      ? Number((latestMetrics.amountValue - previousMetrics.amountValue).toFixed(2))
      : null;
  const rateDelta =
    latestMetrics.rateValue !== null && previousMetrics.rateValue !== null
      ? Number(((latestMetrics.rateValue - previousMetrics.rateValue) * 100).toFixed(1))
      : null;

  return {
    categoryId: input.categoryId,
    categoryLabel: input.categoryLabel,
    isSummary: input.isSummary,
    cells: input.periods.map((period, index) => {
      const labels = liabilityDetailMetricLabels(input.rowAt(index));
      return {
        periodKey: period.key,
        amountLabel: labels.amountLabel,
        rateLabel: labels.rateLabel,
      };
    }),
    movement: {
      amountLabel: signedYiDeltaLabel(amountDelta),
      rateLabel: signedBpLabel(rateDelta),
    },
  };
}

function buildLiabilityCurrencyMatrixRow(input: {
  categoryId: string;
  categoryLabel: string;
  isSummary?: boolean;
  amountField: ProductCategoryLiabilityAmountField;
  cashField: ProductCategoryLiabilityCashField;
  periods: ProductCategoryLiabilityDetailMatrixPeriod[];
  latestIndex: number;
  previousIndex: number;
  rowAt: (index: number) => ProductCategoryPnlRow | undefined;
}): ProductCategoryLiabilityCurrencyMatrixRow {
  const latestMetrics = liabilityCurrencyMetricLabels(
    input.rowAt(input.latestIndex),
    input.amountField,
    input.cashField,
  );
  const previousMetrics = liabilityCurrencyMetricLabels(
    input.rowAt(input.previousIndex),
    input.amountField,
    input.cashField,
  );
  const amountDelta =
    latestMetrics.amountValue !== null && previousMetrics.amountValue !== null
      ? Number((latestMetrics.amountValue - previousMetrics.amountValue).toFixed(2))
      : null;
  const rateDelta =
    latestMetrics.rateValue !== null && previousMetrics.rateValue !== null
      ? Number(((latestMetrics.rateValue - previousMetrics.rateValue) * 100).toFixed(1))
      : null;

  return {
    categoryId: input.categoryId,
    categoryLabel: input.categoryLabel,
    isSummary: input.isSummary,
    cells: input.periods.map((period, index) => {
      const labels = liabilityCurrencyMetricLabels(input.rowAt(index), input.amountField, input.cashField);
      return {
        periodKey: period.key,
        amountLabel: labels.amountLabel,
        rateLabel: labels.rateLabel,
      };
    }),
    movement: {
      amountLabel: signedYiDeltaLabel(amountDelta),
      rateLabel: signedBpLabel(rateDelta),
    },
  };
}

export function selectProductCategoryLiabilityDetailMatrix(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilityDetailMatrix {
  const ordered = chronologicalProductCategorySnapshots(snapshots);
  const periods = ordered.map((snapshot) => ({
    key: `${snapshot.reportDate}:${snapshot.view ?? ""}`,
    label: snapshot.label ?? formatProductCategoryReportMonthLabel(snapshot.reportDate),
    reportDate: snapshot.reportDate,
  }));
  const rowsBySnapshot = ordered.map((snapshot) => liabilityDetailRowsFromSnapshot(snapshot));
  const rowMaps = rowsBySnapshot.map((rows) => new Map(rows.map((row) => [row.category_id, row])));
  const rowRefs = new Map<string, { first: ProductCategoryPnlRow; latest: ProductCategoryPnlRow }>();

  rowsBySnapshot.forEach((rows) => {
    rows.forEach((row) => {
      const existing = rowRefs.get(row.category_id);
      rowRefs.set(row.category_id, {
        first: existing?.first ?? row,
        latest: row,
      });
    });
  });

  const categoryIds = Array.from(rowRefs.keys()).sort((left, right) => {
    const leftIndex = DISPLAY_ORDER_INDEX.get(left) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = DISPLAY_ORDER_INDEX.get(right) ?? Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) {
      return leftIndex - rightIndex;
    }
    return left.localeCompare(right);
  });
  const latestIndex = ordered.length - 1;
  const previousIndex = ordered.length - 2;
  const latestTotal = ordered[latestIndex]?.liabilityTotal ?? undefined;
  const firstTotal = ordered.find((snapshot) => snapshot.liabilityTotal)?.liabilityTotal ?? undefined;
  const totalRow =
    latestTotal || firstTotal
      ? buildLiabilityDetailMatrixRow({
          categoryId: "liability_total",
          categoryLabel: latestTotal?.category_name || firstTotal?.category_name || "负债合计",
          isSummary: true,
          periods,
          latestIndex,
          previousIndex,
          rowAt: (index) => ordered[index]?.liabilityTotal ?? undefined,
        })
      : null;
  const detailRows = categoryIds.map((categoryId) => {
    const refs = rowRefs.get(categoryId);
    const latestRow = refs?.latest;
    const firstRow = refs?.first;
    return buildLiabilityDetailMatrixRow({
      categoryId,
      categoryLabel: latestRow?.category_name || firstRow?.category_name || categoryId,
      periods,
      latestIndex,
      previousIndex,
      rowAt: (index) => rowMaps[index]?.get(categoryId),
    });
  });
  const movementGroupLabel = adjacentProductCategoryMonths(ordered[previousIndex], ordered[latestIndex])
    ? "环比月度变动情况"
    : "较上期变动";
  const currencyMatrices: ProductCategoryLiabilityCurrencyMatrix[] = [
    { currencyKey: "cny", currencyLabel: "人民币结构", amountField: "cny_scale", cashField: "cny_cash" },
    {
      currencyKey: "foreign",
      currencyLabel: "外币结构",
      amountField: "foreign_scale",
      cashField: "foreign_cash",
    },
  ].map((currency) => {
    const totalCurrencyRow =
      latestTotal || firstTotal
        ? buildLiabilityCurrencyMatrixRow({
            categoryId: "liability_total",
            categoryLabel: latestTotal?.category_name || firstTotal?.category_name || "负债合计",
            isSummary: true,
            amountField: currency.amountField as ProductCategoryLiabilityAmountField,
            cashField: currency.cashField as ProductCategoryLiabilityCashField,
            periods,
            latestIndex,
            previousIndex,
            rowAt: (index) => ordered[index]?.liabilityTotal ?? undefined,
          })
        : null;
    const currencyRows = categoryIds.map((categoryId) => {
      const refs = rowRefs.get(categoryId);
      const latestRow = refs?.latest;
      const firstRow = refs?.first;
      return buildLiabilityCurrencyMatrixRow({
        categoryId,
        categoryLabel: latestRow?.category_name || firstRow?.category_name || categoryId,
        amountField: currency.amountField as ProductCategoryLiabilityAmountField,
        cashField: currency.cashField as ProductCategoryLiabilityCashField,
        periods,
        latestIndex,
        previousIndex,
        rowAt: (index) => rowMaps[index]?.get(categoryId),
      });
    });
    return {
      currencyKey: currency.currencyKey as ProductCategoryLiabilityCurrencyKey,
      currencyLabel: currency.currencyLabel,
      movementGroupLabel,
      rows: totalCurrencyRow ? [totalCurrencyRow, ...currencyRows] : currencyRows,
    };
  });

  return {
    periods,
    movementGroupLabel,
    rows: totalRow ? [totalRow, ...detailRows] : detailRows,
    currencyMatrices,
  };
}

export function selectProductCategoryLiabilityDetailTrendRows(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilityDetailTrendRow[] {
  const ordered = chronologicalProductCategorySnapshots(snapshots);
  const latestSnapshot = ordered[ordered.length - 1];
  if (!latestSnapshot) {
    return [];
  }
  const latestLabel = latestSnapshot.label ?? formatProductCategoryReportMonthLabel(latestSnapshot.reportDate);
  const latestIndex = ordered.length - 1;
  return liabilityDetailRowsFromSnapshot(latestSnapshot).map((row) => {
    const latestAmount = yiNumber(row.cnx_scale);
    const priorAmount = latestAmount !== null
      ? latestComparableLiabilityValue({
          snapshots: ordered,
          categoryId: row.category_id,
          metric: "cnx_scale",
          beforeIndex: latestIndex,
        })
      : null;
    const latestRate = percentNumber(row.weighted_yield);
    const priorRate = latestRate !== null
      ? latestComparableLiabilityValue({
          snapshots: ordered,
          categoryId: row.category_id,
          metric: "weighted_yield",
          beforeIndex: latestIndex,
        })
      : null;
    const amountDelta =
      latestAmount !== null && priorAmount ? Number((latestAmount - priorAmount.value).toFixed(2)) : null;
    const rateDelta =
      latestRate !== null && priorRate ? Number(((latestRate - priorRate.value) * 100).toFixed(1)) : null;
    return {
      categoryId: row.category_id,
      categoryLabel: row.category_name || row.category_id,
      latestAmountLabel: latestAmount !== null ? latestAmount.toFixed(2) : "-",
      amountDeltaLabel: signedYiDeltaLabel(amountDelta),
      latestRateLabel: latestRate !== null ? latestRate.toFixed(2) : "-",
      rateDeltaLabel: signedBpLabel(rateDelta),
      comparisonLabel: liabilityComparisonLabel({
        amountLatestLabel: latestAmount !== null ? latestLabel : null,
        amountPriorLabel: priorAmount?.label ?? null,
        rateLatestLabel: latestRate !== null ? latestLabel : null,
        ratePriorLabel: priorRate?.label ?? null,
      }),
    };
  });
}

export function buildProductCategoryLiabilitySideTrendSurface(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryLiabilitySideTrendSurface {
  const chart = selectProductCategoryLiabilitySideTrendChart(snapshots);
  const detailRows = selectProductCategoryLiabilityDetailTrendRows(snapshots);
  const detailMatrix = selectProductCategoryLiabilityDetailMatrix(snapshots);
  const incompleteReasons = chart?.incompleteReasons ?? [];
  if (!chart && detailRows.length === 0 && detailMatrix.rows.length === 0) {
    return {
      chart: null,
      detailRows,
      detailMatrix,
      emptyCopy: "当前 payload 未返回可展示的负债端趋势数据。",
      incompleteReasons,
    };
  }
  return {
    chart,
    detailRows,
    detailMatrix,
    emptyCopy: chart ? null : "负债端趋势数据不完整，无法绘制完整走势。",
    incompleteReasons,
  };
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
      const leftIndex = DISPLAY_ORDER_INDEX.get(left.category_id) ?? Number.MAX_SAFE_INTEGER;
      const rightIndex = DISPLAY_ORDER_INDEX.get(right.category_id) ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex;
    });
}

export function selectDisplayedProductCategoryGrandTotal<
  T extends Pick<ProductCategoryPnlRow, "business_net_income">,
>(scenarioGrand: T | null | undefined, baselineGrand: T | null | undefined): T | undefined {
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
  if (meta.vendor_status === "vendor_stale" || meta.vendor_status === "vendor_unavailable") {
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
