import type {
  DecimalLike,
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryInterestSpreadPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../api/contracts";
import { buildProductCategoryInterestSpreadAttributionImpl } from "./model/productCategoryPnlInterestSpreadModel";
import {
  buildProductCategoryLiabilitySideTrendSurfaceImpl,
  selectProductCategoryLiabilityDetailMatrixImpl,
  selectProductCategoryLiabilityDetailTrendRowsImpl,
  selectProductCategoryLiabilitySideTrendChartImpl,
} from "./model/productCategoryPnlLiabilityModel";
import { interestSpreadMetricNumberInternal as interestSpreadMetricNumber } from "./model/productCategoryPnlModelInternals";
import {
  buildProductCategoryTrendSnapshotImpl,
  selectProductCategoryCurrencyNetIncomeChartImpl,
  selectProductCategoryInterestEarningAssetLiabilityScaleChartImpl,
  selectProductCategoryInterestEarningIncomeScaleChartImpl,
  selectProductCategoryInterestEarningSpreadChartImpl,
  selectProductCategoryInterestEarningSpreadYearComparisonChartImpl,
  selectProductCategoryInterestSpreadChartImpl,
  selectProductCategoryInterestSpreadYearComparisonChartImpl,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChartImpl,
  selectProductCategoryTplScaleYieldChartImpl,
  selectProductCategoryTrendReportDatesImpl,
  selectProductCategoryTrendReportPointsImpl,
  selectProductCategoryTwoYearInterestSpreadReportPointsImpl,
} from "./model/productCategoryPnlTrendAndChartModel";
import { TONE_DH_CSS_VAR } from "../../../utils/tone";
import { EM_DASH } from "../../../utils/format";

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

function parseProductCategoryReportDate(
  reportDate: string,
): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12
  ) {
    return null;
  }
  return { year, month };
}

function formatProductCategoryShortMonthLabel(month: number): string {
  return `${month}\u6708`;
}

/*
 * 盈亏着色走主题感知 tone 入口（frontend/AGENTS.md：深色路由禁止浅色
 * semantic.profit/loss 直灌）。消费方（本页 + operations-analysis 贡献表）
 * 均为 DOM 内联样式且页根已声明 Nocturne scope，--dh-api-* 在 scope 内
 * 解析为 --nct-* 色板；default 取强墨阶（原 neutral-900 语义）。
 */
export const PRODUCT_CATEGORY_VALUE_TONE_COLORS = {
  default: "var(--dh-api-ink)",
  positive: TONE_DH_CSS_VAR.positive,
  negative: TONE_DH_CSS_VAR.negative,
} as const;

const YUAN_PER_YI = 100_000_000;
const PRODUCT_CATEGORY_CLOSURE_ERROR_ALERT_THRESHOLD_YUAN = 500_000;
const PRODUCT_CATEGORY_CLOSURE_ERROR_WARNING_TEXT =
  "对账残差非零，父级自报变动与子项之和存在缺口";

export type ProductCategoryCandidateMetricStatus = {
  status: "candidate";
  pendingConfirmation: true;
  formalUseAllowed: false;
  source: "frontend_derived";
  label: string;
  disclaimer: string;
};

export const PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS: ProductCategoryCandidateMetricStatus =
  {
    status: "candidate",
    pendingConfirmation: true,
    formalUseAllowed: false,
    source: "frontend_derived",
    label: "候选指标 · 非正式结论",
    disclaimer:
      "本区指标由前端基于后端 formal/scenario 字段进行排序、差额、阈值或诊断归类，仅供内部复核，不构成正式金融指标或业务结论。",
  };

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

export type ProductCategoryManagementMonitoringSurface = {
  metricStatus: ProductCategoryCandidateMetricStatus;
  state: "ready" | "insufficient" | "scenario_blocked";
  periodLabel: string;
  coverageLabel: string;
  emptyCopy: string | null;
  tpl: {
    currentPnlLabel: string;
    currentYieldLabel: string;
    currentScaleLabel: string;
    thresholds: Array<{
      key: "prior_month" | "h1_average" | "q1_average";
      label: string;
      targetPnlLabel: string;
      requiredYieldLabel: string;
      liftBpLabel: string;
    }>;
  } | null;
  liability: {
    h1NetLabel: string;
    positivePoolLabel: string;
    negativePoolLabel: string;
    offsetRatioLabel: string;
    currentMonthDeltaLabel: string;
    leadingMovementLabel: string;
    leadingDriverLabel: string;
  } | null;
  derivatives: {
    h1TotalLabel: string;
    monthlyAverageLabel: string;
    volatilityLabel: string;
    topThreeConcentrationLabel: string;
    negativeMonthCountLabel: string;
  } | null;
  runRate: {
    q1MonthlyAverageLabel: string;
    q2MonthlyAverageLabel: string;
    h1MonthlyAverageLabel: string;
    recoveryLiftLabel: string;
    h2AtQ2PaceLabel: string;
    gapToH1Label: string;
  } | null;
  methodNotes: string[];
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
  metricStatus: ProductCategoryCandidateMetricStatus;
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
  metricStatus: ProductCategoryCandidateMetricStatus;
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
  comparableCount: number;
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

export type ProductCategoryOperatingBacktestCalibrationRow = {
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  recommendationLabel: string;
  reasonLabel: string;
  evidenceLabel: string;
  confidenceLabel: string;
  confidenceDetailLabel: string;
  tone: "positive" | "negative" | "neutral";
};

export type ProductCategoryOperatingBacktestLatestReviewRow = {
  priorityLabel: string;
  categoryId: string;
  categoryLabel: string;
  actionKind: ProductCategoryOperatingActionKind;
  actionLabel: string;
  reviewLabel: string;
  riskRankLabel: string;
  riskReasonLabel: string;
  reasonLabel: string;
  impactLabel: string;
  watchReportDateLabel: string;
  releaseConditionLabel: string;
  observationLabel: string;
  gapLabel: string;
  evidenceLabel: string;
  currentEvidenceItems: string[];
  checkItems: string[];
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
  metricStatus: ProductCategoryCandidateMetricStatus;
  summary: {
    evaluatedMonthCount: number;
    signalCount: number;
    latestPendingCount: number;
    coverageLabel: string;
    attributionCoverageLabel: string;
    attributionCoverageDetailLabel: string;
    backtestGateLabel: string;
    backtestGateDetailLabel: string;
    backtestGateTone: "positive" | "negative" | "neutral";
    sampleRepairLabel: string;
    sampleRepairDetailLabel: string;
    sampleRepairDateLabel: string;
    sampleRepairReviewLabel: string;
    reviewWorkloadLabel: string;
    reviewWorkloadDetailLabel: string;
    dispositionLabel: string;
    dispositionDetailLabel: string;
    evidenceLabel: string;
  };
  coverageRows: Array<{
    reportDate: string;
    nextReportDate: string | null;
    statusLabel: string;
    detailLabel: string;
    signalCount: number;
    tone: "positive" | "negative" | "neutral";
  }>;
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[];
  latestReviewRows: ProductCategoryOperatingBacktestLatestReviewRow[];
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
  metricStatus: ProductCategoryCandidateMetricStatus;
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
  metricStatus: ProductCategoryCandidateMetricStatus;
  title: string;
  deltaLabel: string;
  rows: ProductCategoryAttributionWaterfallRow[];
  emptyCopy: string | null;
};

export type ProductCategoryRootCauseDriverKey =
  | "day_effect"
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
  metricStatus: ProductCategoryCandidateMetricStatus;
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
  metricStatus: ProductCategoryCandidateMetricStatus;
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

export type ProductCategoryInterestEarningAssetLiabilityScaleChart = {
  labels: string[];
  interestEarningAssetScale: number[];
  interestBearingLiabilityScale: number[];
};

export type ProductCategoryInterestSpreadChart = {
  labels: string[];
  assetYield: number[];
  liabilityYield: number[];
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
    return EM_DASH;
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

export type ProductCategoryClosureErrorSignal = {
  hasMaterialGap: boolean;
  warningText: string | null;
};

export function selectProductCategoryClosureErrorSignal(
  value: DecimalLike | null | undefined,
): ProductCategoryClosureErrorSignal {
  const raw = decimalNumber(value);
  if (raw === null) {
    return {
      hasMaterialGap: false,
      warningText: null,
    };
  }
  const hasMaterialGap =
    Math.abs(raw) >= PRODUCT_CATEGORY_CLOSURE_ERROR_ALERT_THRESHOLD_YUAN;
  return {
    hasMaterialGap,
    warningText: hasMaterialGap
      ? PRODUCT_CATEGORY_CLOSURE_ERROR_WARNING_TEXT
      : null,
  };
}

export function formatProductCategoryRowDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
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

export function formatProductCategoryForeignDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  const displayValue = row.side === "liability" ? -parsed : parsed;
  return (displayValue / YUAN_PER_YI).toFixed(digits);
}

export function formatProductCategoryYieldValue(
  value: DecimalLike | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return String(value);
  }
  return parsed.toFixed(digits);
}

export function formatProductCategoryChartNumberTwoDecimals(
  value: unknown,
): string {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : EM_DASH;
}

export function toneForProductCategoryValue(
  value: DecimalLike | null | undefined,
): string {
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

export function toneForProductCategoryForeignDisplayValue(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): string {
  const displayValue = productCategoryForeignDisplayNumber(row, value);
  if (displayValue === null) {
    return PRODUCT_CATEGORY_VALUE_TONE_COLORS.default;
  }
  return toneForProductCategoryValue(displayValue);
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

function rawYiNumber(value: DecimalLike | null | undefined): number | null {
  const parsed = decimalNumber(value);
  return parsed === null ? null : parsed / YUAN_PER_YI;
}

function percentNumber(value: DecimalLike | null | undefined): number | null {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return null;
  }
  return Number(parsed.toFixed(2));
}

function toneNameForValue(
  value: DecimalLike | null | undefined,
): "neutral" | "positive" | "negative" {
  const parsed = decimalNumber(value);
  if (parsed === null || parsed === 0) {
    return "neutral";
  }
  return parsed > 0 ? "positive" : "negative";
}

function productCategoryForeignDisplayNumber(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
): number | null {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return null;
  }
  return row.side === "liability" ? -parsed : parsed;
}

function formatSignedProductCategoryYi(value: number | null): string {
  return signedYiDeltaLabel(value);
}

function productCategoryPercentLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(1)}%`;
}

function productCategoryYiNumberLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toFixed(2);
}

function nonTotalProductCategoryRows(
  rows: ProductCategoryPnlRow[],
): ProductCategoryPnlRow[] {
  return rows.filter(
    (row) =>
      !row.is_total &&
      !row.category_id.endsWith("_total") &&
      row.category_id !== "grand_total",
  );
}

function leafProductCategoryRows(
  rows: ProductCategoryPnlRow[],
): ProductCategoryPnlRow[] {
  return nonTotalProductCategoryRows(rows).filter(
    (row) => row.children.length === 0,
  );
}

function parentProductCategoryIds(rows: ProductCategoryPnlRow[]): Set<string> {
  return new Set(
    nonTotalProductCategoryRows(rows)
      .filter((row) => row.children.length > 0)
      .map((row) => row.category_id),
  );
}

function medianProductCategoryNumber(values: number[]): number | null {
  const sorted = values
    .filter(Number.isFinite)
    .slice()
    .sort((left, right) => left - right);
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

function productCategoryQuadrantLabel(
  quadrant: ProductCategoryOperatingQuadrant,
): string {
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
      const denominator =
        grandTotal !== null && grandTotal !== 0 ? Math.abs(grandTotal) : null;
      const contributionPct = denominator
        ? Number(((value / denominator) * 100).toFixed(1))
        : null;
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name || row.category_id,
        sideLabel: productCategorySideLabel(row.side),
        netIncome: value,
        netIncomeLabel: value.toFixed(2),
        contributionPct,
        contributionLabel: productCategoryPercentLabel(contributionPct),
        tone: value > 0 ? ("positive" as const) : ("negative" as const),
      };
    })
    .filter(
      (row): row is ProductCategoryOperatingContributionRow => row !== null,
    );
  const profitRows = candidates
    .filter((row) => row.netIncome > 0)
    .sort((left, right) => right.netIncome - left.netIncome)
    .slice(0, 5);
  const pressureRows = candidates
    .filter((row) => row.netIncome < 0)
    .sort((left, right) => left.netIncome - right.netIncome)
    .slice(0, 5);
  return {
    grandTotalLabel: input.grandTotal
      ? formatProductCategoryValue(input.grandTotal.business_net_income)
      : null,
    profitRows,
    pressureRows,
    emptyCopy:
      profitRows.length === 0 && pressureRows.length === 0
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
    if (
      row.category_id.endsWith("_total") ||
      row.category_id === "grand_total" ||
      parentCategoryIds.has(row.category_id)
    ) {
      continue;
    }
    const delta = yiNumber(row.effects.delta_business_net_income);
    if (delta === null || delta === 0) {
      continue;
    }
    const leadingDriverKey = PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS.reduce(
      (best, key) => {
        const bestValue = Math.abs(yiNumber(row.effects[best]) ?? 0);
        const currentValue = Math.abs(yiNumber(row.effects[key]) ?? 0);
        return currentValue > bestValue ? key : best;
      },
      PRODUCT_CATEGORY_OPERATING_DRIVER_KEYS[0],
    );
    const leadingDriverValue = yiNumber(row.effects[leadingDriverKey]) ?? 0;
    rows.push({
      categoryId: row.category_id,
      categoryLabel: row.category_name || row.category_id,
      delta,
      deltaLabel: formatSignedProductCategoryYi(delta),
      leadingDriverKey,
      leadingDriverLabel:
        PRODUCT_CATEGORY_OPERATING_DRIVER_LABELS[leadingDriverKey],
      leadingDriverValue,
      leadingDriverValueLabel:
        formatSignedProductCategoryYi(leadingDriverValue),
      closureErrorLabel: formatSignedProductCategoryYi(
        yiNumber(row.effects.closure_error),
      ),
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
  const rows = buildProductCategoryOperatingMovementRows(
    attribution,
    parentCategoryIds,
  );
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
        netIncomeLabel: netIncome !== null ? netIncome.toFixed(2) : EM_DASH,
      };
    })
    .filter(
      (
        row,
      ): row is {
        row: ProductCategoryPnlRow;
        scale: number;
        yieldPct: number;
        netIncome: number | null;
        netIncomeLabel: string;
      } => row !== null,
    );
  const scaleBenchmark = medianProductCategoryNumber(
    candidates.map((item) => item.scale),
  );
  const yieldBenchmark = medianProductCategoryNumber(
    candidates.map((item) => item.yieldPct),
  );
  if (scaleBenchmark === null || yieldBenchmark === null) {
    return {
      scaleBenchmark: null,
      yieldBenchmark: null,
      scaleBenchmarkLabel: EM_DASH,
      yieldBenchmarkLabel: EM_DASH,
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
  const displayRows =
    options.limit === null
      ? quadrantRows
      : quadrantRows.slice(0, options.limit ?? 12);
  return {
    scaleBenchmark,
    yieldBenchmark,
    scaleBenchmarkLabel: scaleBenchmark.toFixed(2),
    yieldBenchmarkLabel: yieldBenchmark.toFixed(2),
    rows: displayRows,
    emptyCopy:
      displayRows.length === 0
        ? "当前缺少可用于规模/收益率象限的产品行。"
        : null,
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
  const actionRows: Array<
    Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">
  > = [];
  const seenCategoryIds = new Set<string>();
  const movementRows = buildProductCategoryOperatingMovementRows(
    input.attribution,
    input.parentCategoryIds,
  );
  const quadrant = selectProductCategoryOperatingQuadrant(input.rows, {
    limit: null,
  });
  const quadrantByCategoryId = new Map(
    quadrant.rows.map((row) => [row.categoryId, row]),
  );
  const appendActionRow = (
    row: Omit<ProductCategoryOperatingActionQueueRow, "priorityLabel">,
  ) => {
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
      const movement = movementRows.find(
        (item) => item.categoryId === row.category_id,
      );
      const quadrantRow = quadrantByCategoryId.get(row.category_id);
      const hasLowYield =
        quadrantRow?.quadrant === "scale_efficiency_watch" ||
        quadrantRow?.quadrant === "shrink_or_reprice";
      if (
        netIncome === null ||
        netIncome >= 0 ||
        yieldPct === null ||
        scale === null ||
        !hasLowYield
      ) {
        return null;
      }
      return { row, netIncome, scale, yieldPct, movement };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((left, right) => left.netIncome - right.netIncome)[0];

  if (lowYieldLoss) {
    appendActionRow(
      productCategoryOperatingActionRow({
        categoryId: lowYieldLoss.row.category_id,
        categoryLabel:
          lowYieldLoss.row.category_name || lowYieldLoss.row.category_id,
        actionKind: "shrink_or_limit",
        actionLabel: "压降或限额复核",
        triggerLabel: "负贡献叠加收益偏低",
        primaryMetricLabel: lowYieldLoss.netIncome.toFixed(2),
        evidenceItems: [
          `净营收 ${lowYieldLoss.netIncome.toFixed(2)} 亿元`,
          `规模 ${lowYieldLoss.scale.toFixed(2)} 亿元`,
          `收益率 ${lowYieldLoss.yieldPct.toFixed(2)}%`,
          `变动 ${lowYieldLoss.movement?.deltaLabel ?? EM_DASH} 亿元`,
        ],
        tone: "negative",
      }),
    );
  }

  const unexplainedReview = movementRows
    .filter(
      (row) =>
        row.leadingDriverKey === "unexplained_effect" &&
        Math.abs(row.leadingDriverValue) > 0,
    )
    .sort(
      (left, right) =>
        Math.abs(right.leadingDriverValue) - Math.abs(left.leadingDriverValue),
    )[0];

  if (unexplainedReview) {
    appendActionRow(
      productCategoryOperatingActionRow({
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
      }),
    );
  }

  const reprice = quadrant.rows.find(
    (row) =>
      row.quadrant === "scale_efficiency_watch" &&
      !seenCategoryIds.has(row.categoryId),
  );
  if (reprice) {
    appendActionRow(
      productCategoryOperatingActionRow({
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
      }),
    );
  }

  const selectiveGrowth = quadrant.rows.find(
    (row) =>
      row.quadrant === "selective_growth" &&
      row.netIncome !== null &&
      row.netIncome > 0 &&
      !seenCategoryIds.has(row.categoryId),
  );
  if (selectiveGrowth) {
    appendActionRow(
      productCategoryOperatingActionRow({
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
      }),
    );
  }

  const rows = actionRows.map((row, index) => ({
    priorityLabel: `P${index + 1}`,
    ...row,
  }));
  return {
    rows,
    emptyCopy:
      rows.length === 0 ? "当前没有需要进入经营动作队列的产品分类。" : null,
  };
}

export function selectProductCategoryOperatingAnalysisSurface(input: {
  rows: ProductCategoryPnlRow[];
  grandTotal?: Pick<ProductCategoryPnlRow, "business_net_income"> | null;
  attribution?: ProductCategoryAttributionPayload | null;
}): ProductCategoryOperatingAnalysisSurface {
  const parentCategoryIds = parentProductCategoryIds(input.rows);
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    contribution: selectProductCategoryOperatingContribution({
      rows: input.rows,
      grandTotal: input.grandTotal,
    }),
    movement: selectProductCategoryOperatingMovement(
      input.attribution,
      parentCategoryIds,
    ),
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

function productCategoryDeltaTone(
  value: number | null,
): "positive" | "negative" | "neutral" {
  if (value === null || value === 0) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

function productCategoryScenarioAnalysisCopy(
  worst: ProductCategoryScenarioSensitivityRow | undefined,
  best: ProductCategoryScenarioSensitivityRow | undefined,
): string | null {
  if (
    !worst ||
    !best ||
    worst.grandDelta === null ||
    best.grandDelta === null
  ) {
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

type ProductCategoryComparableScenarioRow =
  ProductCategoryScenarioSensitivityRow & {
    grandNetIncome: number;
    grandDelta: number;
  };

const EMPTY_PRODUCT_CATEGORY_SCENARIO_PRESSURE_SUMMARY: ProductCategoryScenarioPressureSummary =
  {
    breakeven: {
      label: "临界 FTP",
      valueLabel: EM_DASH,
      detailLabel: "待加载可比较情景后估算；此处仅做线性插值辅助判断。",
      tone: "neutral",
    },
    sideOffset: {
      rateLabel: EM_DASH,
      totalDeltaLabel: EM_DASH,
      assetDeltaLabel: EM_DASH,
      liabilityDeltaLabel: EM_DASH,
      offsetLabel: EM_DASH,
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
  const sortedByGrand = [...comparableRows].sort(
    (left, right) => right.grandNetIncome - left.grandNetIncome,
  );
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
  const slope =
    rateSpanBp === 0
      ? null
      : Number(
          ((worst.grandNetIncome - best.grandNetIncome) / rateSpanBp).toFixed(
            2,
          ),
        );
  cards.push({
    key: "ftp_slope",
    label: "FTP 斜率",
    valueLabel: productCategoryYiNumberLabel(slope),
    detailLabel: "每 1 bp 约影响净营收",
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
    if (row.topMoverCategoryLabel === EM_DASH || row.topMoverDelta === null) {
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
    if (
      current.worstDelta === null ||
      Math.abs(row.topMoverDelta) > Math.abs(current.worstDelta)
    ) {
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
    positionPct:
      span === 0 ? 50 : Math.round(((row.ratePct - minRate) / span) * 100),
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
  if (
    input.worst?.grandDelta !== null &&
    input.worst?.grandDelta !== undefined
  ) {
    const absoluteDelta = Math.abs(input.worst.grandDelta).toFixed(2);
    items.push({
      title:
        input.worst.grandDelta < 0 ? "锁定下行情景敞口" : "确认上行情景弹性",
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
  if (
    input.best &&
    input.worst &&
    input.best.grandNetIncome !== input.worst.grandNetIncome
  ) {
    const range = Number(
      (input.best.grandNetIncome - input.worst.grandNetIncome).toFixed(2),
    );
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
  const exposures = new Map<
    string,
    { categoryLabel: string; exposure: number }
  >();
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
    widthPct:
      maxAbs === 0 ? 0 : Math.round((Math.abs(row.exposure) / maxAbs) * 100),
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
    {
      baselineRow: ProductCategoryPnlRow;
      scenarioRows: Array<{ rate: string; row: ProductCategoryPnlRow }>;
    }
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
        current.scenarioRows.push({
          rate: String(scenarioRate),
          row: scenarioRow,
        });
      } else {
        scenarioRowsByCategory.set(scenarioRow.category_id, {
          baselineRow,
          scenarioRows: [{ rate: String(scenarioRate), row: scenarioRow }],
        });
      }
    }
  }
  const rows: Array<ProductCategoryScenarioComparisonRow | null> = [
    ...scenarioRowsByCategory.entries(),
  ].map(([categoryId, entry]) => {
    const baselineNetIncome = yiNumber(entry.baselineRow.business_net_income);
    const cells = entry.scenarioRows
      .map((scenarioEntry) => {
        const rate = scenarioEntry.rate;
        const ratePct = Number(rate);
        const netIncome = yiNumber(scenarioEntry.row.business_net_income);
        const delta = productCategoryRowDeltaYi(
          input.baselineRowsById,
          scenarioEntry.row,
        );
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
      .filter(
        (cell): cell is ProductCategoryScenarioComparisonCell => cell !== null,
      )
      .sort((left, right) => left.ratePct - right.ratePct);
    const comparableCells = cells.filter(
      (
        cell,
      ): cell is ProductCategoryScenarioComparisonCell & {
        delta: number;
        netIncome: number;
      } => cell.delta !== null && cell.netIncome !== null,
    );
    if (comparableCells.length === 0) {
      return null;
    }
    const best = [...comparableCells].sort(
      (left, right) => right.delta - left.delta,
    )[0];
    const worst = [...comparableCells].sort(
      (left, right) => left.delta - right.delta,
    )[0];
    if (!best || !worst) {
      return null;
    }
    const minNetIncome = Math.min(
      ...comparableCells.map((cell) => cell.netIncome),
    );
    const maxNetIncome = Math.max(
      ...comparableCells.map((cell) => cell.netIncome),
    );
    const range = Number((maxNetIncome - minNetIncome).toFixed(2));
    const maxAbsDelta = Math.max(
      ...comparableCells.map((cell) => Math.abs(cell.delta)),
      0,
    );
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

function productCategoryScenarioClosureRecommendation(
  row: ProductCategoryScenarioComparisonRow,
): string {
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
    .sort(
      (left, right) =>
        Math.abs(right.worstDelta ?? 0) - Math.abs(left.worstDelta ?? 0),
    )
    .slice(0, 4)
    .map((row, index) => {
      const worstCell = row.cells.find(
        (cell) => cell.rateLabel === row.worstRateLabel,
      );
      const scenarioNetIncomeLabel = worstCell?.netIncomeLabel ?? EM_DASH;
      const recommendationLabel =
        productCategoryScenarioClosureRecommendation(row);
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
  const sortedByRate = [...comparableRows].sort(
    (left, right) => left.ratePct - right.ratePct,
  );
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
    const rate =
      left.ratePct +
      ((0 - left.grandDelta) / deltaSpan) * (right.ratePct - left.ratePct);
    return {
      label: "临界 FTP",
      valueLabel: `约 ${rate.toFixed(2)}%`,
      detailLabel: `线性插值：${left.rateLabel} ${productCategoryScenarioBaselineRelation(
        left.grandDelta,
      )}，${right.rateLabel} ${productCategoryScenarioBaselineRelation(right.grandDelta)}`,
      tone: "warning",
    };
  }
  const best = [...sortedByRate].sort(
    (left, right) => right.grandDelta - left.grandDelta,
  )[0];
  const worst = [...sortedByRate].sort(
    (left, right) => left.grandDelta - right.grandDelta,
  )[0];
  if (worst && worst.grandDelta > 0) {
    return {
      label: "临界 FTP",
      valueLabel: `高于 ${sortedByRate[sortedByRate.length - 1]?.rateLabel ?? EM_DASH}`,
      detailLabel: `已加载情景均高于基线，最低差额 ${worst.grandDeltaLabel}；未在当前区间触发临界点。`,
      tone: "positive",
    };
  }
  if (best && best.grandDelta < 0) {
    return {
      label: "临界 FTP",
      valueLabel: `低于 ${sortedByRate[0]?.rateLabel ?? EM_DASH}`,
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
  const assetWidth =
    totalAbs === 0
      ? 0
      : Math.round((Math.abs(worst.assetDelta) / totalAbs) * 100);
  const liabilityWidth =
    totalAbs === 0
      ? 0
      : Math.round((Math.abs(worst.liabilityDelta) / totalAbs) * 100);
  const hasOffset = worst.assetDelta * worst.liabilityDelta < 0;
  const offset = hasOffset
    ? Math.min(Math.abs(worst.assetDelta), Math.abs(worst.liabilityDelta))
    : 0;
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
  return side || EM_DASH;
}

function productCategoryScenarioReviewAction(
  tone: "positive" | "negative" | "neutral",
): string {
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
    const triggerRateLabel =
      scenarioRate === null ? EM_DASH : `${scenarioRate.toFixed(2)}%`;
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
  }).sort(
    (left, right) => Math.abs(right.value ?? 0) - Math.abs(left.value ?? 0),
  );
}

function dominantScenarioExplanationDriver(
  rows: ProductCategoryScenarioExplanationDriverRow[],
): ProductCategoryScenarioExplanationDriverRow | undefined {
  return rows.find((row) => row.value !== null && row.value !== 0);
}

function scenarioExplanationAttributionTotal(
  rows: ProductCategoryScenarioExplanationDriverRow[],
): number | null {
  const values = rows
    .map((row) => row.value)
    .filter((value): value is number => value !== null);
  if (values.length === 0) {
    return null;
  }
  return Number(values.reduce((total, value) => total + value, 0).toFixed(2));
}

function scenarioExplanationBridge(input: {
  scenarioDelta: number | null | undefined;
  attributionTotal: number | null;
}): Pick<
  ProductCategoryScenarioExplanation,
  "bridgeLabel" | "bridgeConclusionLabel" | "bridgeTone"
> {
  const scenarioDeltaLabel = formatSignedProductCategoryYi(
    input.scenarioDelta ?? null,
  );
  const attributionTotalLabel = formatSignedProductCategoryYi(
    input.attributionTotal,
  );
  if (
    input.scenarioDelta === null ||
    input.scenarioDelta === undefined ||
    input.attributionTotal === null
  ) {
    return {
      bridgeLabel: `口径桥：情景压力 ${scenarioDeltaLabel} 亿元；正式归因合计 ${attributionTotalLabel} 亿元；差异 ${EM_DASH}。`,
      bridgeConclusionLabel:
        "当前缺少可比较的情景压力或正式归因驱动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
    };
  }
  const bridgeGap = Number(
    (input.scenarioDelta - input.attributionTotal).toFixed(2),
  );
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
    const driverActionByKey: Record<
      ProductCategoryScenarioExplanationDriverRow["key"],
      string
    > = {
      ftp_effect: "复核 FTP 输入、基准利率和资产负债侧映射。",
      scale_effect: "复核规模口径、日均余额和产品分类映射。",
      rate_effect: "复核收益率/成本率输入、计息天数和基准利率变动。",
      unexplained_effect:
        "复核残差来源，检查缺失字段、四舍五入和未覆盖业务项。",
    };
    actions.push(
      `重点追踪 ${input.dominantDriver.label}：${driverActionByKey[input.dominantDriver.key]}`,
    );
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
  const baselineRow = findProductCategoryRow(
    input.baseline.rows,
    input.categoryId,
  );
  if (!baselineRow) {
    return {
      categoryId: input.categoryId,
      categoryLabel: input.categoryId,
      sideLabel: EM_DASH,
      triggerRateLabel: EM_DASH,
      scenarioDeltaLabel: EM_DASH,
      baselineNetIncomeLabel: EM_DASH,
      scenarioNetIncomeLabel: EM_DASH,
      summaryLabel: "当前正式基线未返回该产品行，无法形成行级情景解释。",
      bridgeLabel: `口径桥：情景压力 ${EM_DASH} 亿元；正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}。`,
      bridgeConclusionLabel:
        "当前缺少可比较的情景压力或正式归因驱动，暂不能做口径差异判断。",
      bridgeTone: "neutral",
      reviewActionItems: ["补齐正式基线和情景矩阵后，再生成行级复核动作。"],
      driverRows: [],
      emptyCopy: "当前正式基线未返回该产品行，无法形成行级情景解释。",
    };
  }
  const baselineNetIncome = yiNumber(baselineRow.business_net_income);
  const scenarioMoves = input.scenarios
    .map((scenario) => {
      const scenarioRow = findProductCategoryRow(
        scenario.rows,
        input.categoryId as string,
      );
      if (!scenarioRow) {
        return null;
      }
      const delta = productCategoryRowDeltaYi(
        new Map([[baselineRow.category_id, baselineRow]]),
        scenarioRow,
      );
      const scenarioNetIncome = yiNumber(scenarioRow.business_net_income);
      const scenarioRate = decimalNumber(scenario.scenario_rate_pct);
      if (
        delta === null ||
        scenarioNetIncome === null ||
        scenarioRate === null
      ) {
        return null;
      }
      return {
        row: scenarioRow,
        delta,
        scenarioNetIncome,
        rateLabel: `${scenarioRate.toFixed(2)}%`,
      };
    })
    .filter(
      (
        move,
      ): move is {
        row: ProductCategoryPnlRow;
        delta: number;
        scenarioNetIncome: number;
        rateLabel: string;
      } => move !== null,
    )
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
  const topMove = scenarioMoves[0];
  const attributionRow = input.attribution?.rows.find(
    (row) => row.category_id === input.categoryId,
  );
  const driverRows = scenarioExplanationDriverRows(attributionRow);
  const dominantDriver = dominantScenarioExplanationDriver(driverRows);
  const attributionTotal = scenarioExplanationAttributionTotal(driverRows);
  const scenarioDeltaLabel = formatSignedProductCategoryYi(
    topMove?.delta ?? null,
  );
  const triggerRateLabel = topMove?.rateLabel ?? EM_DASH;
  const baselineNetIncomeLabel =
    productCategoryYiNumberLabel(baselineNetIncome);
  const scenarioNetIncomeLabel = productCategoryYiNumberLabel(
    topMove?.scenarioNetIncome ?? null,
  );
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
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      baselineGrandTotalLabel: input.baseline
        ? formatProductCategoryValue(
            input.baseline.grand_total.business_net_income,
          )
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
  const baselineRowsById = new Map(
    input.baseline.rows.map((row) => [row.category_id, row]),
  );
  const baselineAssetTotal = yiNumber(
    input.baseline.asset_total.business_net_income,
  );
  const baselineLiabilityTotal = yiNumber(
    input.baseline.liability_total.business_net_income,
  );
  const baselineGrandTotal = yiNumber(
    input.baseline.grand_total.business_net_income,
  );
  const rows: ProductCategoryScenarioSensitivityRow[] = [];
  for (const scenario of input.scenarios) {
    const scenarioRate = scenario.scenario_rate_pct;
    if (scenarioRate === null || scenarioRate === undefined) {
      continue;
    }
    const ratePct = Number(scenarioRate);
    const assetValue = yiNumber(scenario.asset_total.business_net_income);
    const liabilityValue = yiNumber(
      scenario.liability_total.business_net_income,
    );
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
      .filter(
        (item): item is { row: ProductCategoryPnlRow; delta: number } =>
          item.delta !== null,
      )
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
      topMoverCategoryLabel:
        topMover?.row.category_name || topMover?.row.category_id || EM_DASH,
      topMoverDelta: topMover?.delta ?? null,
      topMoverDeltaLabel: formatSignedProductCategoryYi(
        topMover?.delta ?? null,
      ),
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
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    baselineGrandTotalLabel: formatProductCategoryValue(
      input.baseline.grand_total.business_net_income,
    ),
    rows,
    insightCards: selectProductCategoryScenarioInsightCards(rows),
    riskRows,
    pathPoints: selectProductCategoryScenarioPathPoints(rows),
    actionItems: selectProductCategoryScenarioActionItems({
      best,
      worst,
      riskRows,
    }),
    heatRows: selectProductCategoryScenarioHeatRows({
      baselineRowsById,
      scenarios: input.scenarios,
    }),
    comparisonRows,
    actionClosureRows:
      selectProductCategoryScenarioActionClosureRows(comparisonRows),
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
  ["day_effect", "天数因素"],
  ["scale_effect", "规模因素"],
  ["rate_effect", "利率因素"],
  ["ftp_effect", "FTP因素"],
  ["direct_effect", "直接因素"],
  ["unexplained_effect", "未解释"],
  ["closure_error", "闭合误差"],
] as const satisfies ReadonlyArray<
  readonly [ProductCategoryRootCauseDriverKey, string]
>;

export function selectProductCategoryAttributionWaterfallSurface(
  attribution: ProductCategoryAttributionPayload | null | undefined,
): ProductCategoryAttributionWaterfallSurface {
  const headline = attribution?.totals?.grand_total;
  if (!headline || attribution?.state !== "complete") {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      title: "经营差异瀑布",
      deltaLabel: EM_DASH,
      rows: [],
      emptyCopy: "当前缺少可用的全表经营差异归因。",
    };
  }
  const prior = yiNumber(headline.prior?.business_net_income);
  const priorRaw = rawYiNumber(headline.prior?.business_net_income);
  const current = yiNumber(headline.current?.business_net_income);
  const currentRaw = rawYiNumber(headline.current?.business_net_income);
  const delta = yiNumber(headline.effects.delta_business_net_income);
  if (
    prior === null ||
    priorRaw === null ||
    current === null ||
    currentRaw === null
  ) {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      title: `${headline.category_name || "全表合计"}经营差异瀑布`,
      deltaLabel: formatSignedProductCategoryYi(delta),
      rows: [],
      emptyCopy: "当前归因缺少本期或对比期净营收。",
    };
  }
  let cumulative = priorRaw;
  const rows: ProductCategoryAttributionWaterfallRow[] = [
    {
      key: "prior",
      label: "对比期净营收",
      value: prior,
      valueLabel: productCategoryYiNumberLabel(prior),
      cumulative: priorRaw,
      cumulativeLabel: productCategoryYiNumberLabel(priorRaw),
      tone: productCategoryDeltaTone(prior),
    },
  ];
  for (const [key, label] of PRODUCT_CATEGORY_ATTRIBUTION_WATERFALL_STEPS) {
    const value = yiNumber(headline.effects[key]);
    const rawValue = rawYiNumber(headline.effects[key]);
    if (rawValue !== null) {
      cumulative += rawValue;
    }
    rows.push({
      key,
      label,
      value,
      valueLabel: formatSignedProductCategoryYi(value),
      cumulative: rawValue === null ? null : cumulative,
      cumulativeLabel:
        rawValue === null ? EM_DASH : productCategoryYiNumberLabel(cumulative),
      tone: productCategoryDeltaTone(value),
    });
  }
  rows.push({
    key: "current",
    label: "本期净营收",
    value: current,
    valueLabel: productCategoryYiNumberLabel(current),
    cumulative: currentRaw,
    cumulativeLabel: productCategoryYiNumberLabel(currentRaw),
    tone: productCategoryDeltaTone(delta),
  });
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
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
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前缺少可用的产品级正式归因，暂不能拆解根因。",
    };
  }
  const parentIds = parentProductCategoryIds(input.rows);
  const attributionRows = input.attribution.rows.filter(
    (row) =>
      !row.category_id.endsWith("_total") &&
      row.category_id !== "grand_total" &&
      !parentIds.has(row.category_id),
  );
  const headlineRow = attributionRows
    .map((row) => ({
      row,
      delta: yiNumber(row.effects.delta_business_net_income),
    }))
    .filter(
      (item): item is { row: ProductCategoryAttributionRow; delta: number } =>
        item.delta !== null && item.delta !== 0,
    )
    .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
  if (!headlineRow) {
    return {
      metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
      headline: null,
      driverRows: [],
      evidenceItems: [],
      emptyCopy: "当前产品级归因没有可拆解的显著差异。",
    };
  }
  const displayRow = input.rows.find(
    (row) => row.category_id === headlineRow.row.category_id,
  );
  const currentNetIncome = yiNumber(
    headlineRow.row.current?.business_net_income ??
      displayRow?.business_net_income,
  );
  const priorNetIncome = yiNumber(headlineRow.row.prior?.business_net_income);
  const scale = yiNumber(
    headlineRow.row.current?.scale ?? displayRow?.cnx_scale,
  );
  const yieldPct = percentNumber(
    headlineRow.row.current?.yield_pct ?? displayRow?.weighted_yield,
  );
  const driverRows = PRODUCT_CATEGORY_ROOT_CAUSE_DRIVER_STEPS.map(
    ([key, label]) => {
      const value = yiNumber(headlineRow.row.effects[key]) ?? 0;
      const sharePct =
        headlineRow.delta !== 0
          ? Number(((value / headlineRow.delta) * 100).toFixed(1))
          : null;
      return {
        key,
        label,
        value,
        valueLabel: formatSignedProductCategoryYi(value),
        sharePct,
        shareLabel: productCategoryPercentLabel(sharePct),
        tone: productCategoryDeltaTone(value),
      };
    },
  ).sort((left, right) => Math.abs(right.value) - Math.abs(left.value));
  const leadingDriver = driverRows[0] ?? null;
  const closureError = yiNumber(headlineRow.row.effects.closure_error);
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    headline: {
      categoryId: headlineRow.row.category_id,
      categoryLabel:
        headlineRow.row.category_name || headlineRow.row.category_id,
      delta: headlineRow.delta,
      deltaLabel: formatSignedProductCategoryYi(headlineRow.delta),
      driverLabel: leadingDriver?.label ?? "未识别",
      driverValueLabel: leadingDriver?.valueLabel ?? EM_DASH,
      currentNetIncomeLabel: productCategoryYiNumberLabel(currentNetIncome),
      priorNetIncomeLabel: productCategoryYiNumberLabel(priorNetIncome),
      scaleLabel: productCategoryYiNumberLabel(scale),
      yieldLabel: yieldPct === null ? EM_DASH : `${yieldPct.toFixed(2)}%`,
      conclusionLabel: `${headlineRow.row.category_name || headlineRow.row.category_id} 变动 ${formatSignedProductCategoryYi(
        headlineRow.delta,
      )} 亿元，主导原因是 ${leadingDriver?.label ?? "未识别"} ${leadingDriver?.valueLabel ?? EM_DASH} 亿元。`,
      tone: productCategoryDeltaTone(headlineRow.delta),
    },
    driverRows,
    evidenceItems: [
      `本期净营收 ${productCategoryYiNumberLabel(currentNetIncome)} 亿元`,
      `对比期净营收 ${productCategoryYiNumberLabel(priorNetIncome)} 亿元`,
      `当前规模 ${productCategoryYiNumberLabel(scale)} 亿元`,
      `当前收益率 ${yieldPct === null ? EM_DASH : `${yieldPct.toFixed(2)}%`}`,
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
    .filter(
      (item): item is { row: ProductCategoryPnlRow; value: number } =>
        item !== null,
    );
  const items: ProductCategoryDecisionFocusItem[] = [];
  const topContributor = candidates
    .filter((item) => item.value > 0)
    .sort((left, right) => right.value - left.value)[0];
  if (topContributor) {
    items.push(
      focusItemFromRow({
        key: "top_contributor",
        row: topContributor.row,
        value: topContributor.value,
        reasonLabel: "本期贡献最高",
        secondaryLabel: "优先确认利润可持续性",
      }),
    );
  }
  const topPressure = candidates
    .filter((item) => item.value < 0)
    .sort((left, right) => left.value - right.value)[0];
  if (topPressure) {
    items.push(
      focusItemFromRow({
        key: "top_pressure",
        row: topPressure.row,
        value: topPressure.value,
        reasonLabel: "本期压力最大",
        secondaryLabel: "优先定位收入承压来源",
      }),
    );
  }
  if (input.attribution?.state === "complete") {
    const attributionRows = input.attribution.rows.filter(
      (row) =>
        !row.category_id.endsWith("_total") &&
        row.category_id !== "grand_total",
    );
    const largestDeterioration = attributionRows
      .map((row) => ({
        row,
        value: yiNumber(row.effects.delta_business_net_income),
      }))
      .filter(
        (item): item is { row: ProductCategoryAttributionRow; value: number } =>
          item.value !== null && item.value < 0,
      )
      .sort((left, right) => left.value - right.value)[0];
    if (largestDeterioration) {
      items.push({
        key: "largest_deterioration",
        categoryId: largestDeterioration.row.category_id,
        categoryLabel:
          largestDeterioration.row.category_name ||
          largestDeterioration.row.category_id,
        reasonLabel: "环比恶化最大",
        primaryLabel: formatSignedProductCategoryYi(largestDeterioration.value),
        secondaryLabel: "优先查看规模/利率/FTP驱动",
        tone: "negative",
      });
    }
    const largestUnexplained = attributionRows
      .map((row) => ({ row, value: yiNumber(row.effects.unexplained_effect) }))
      .filter(
        (item): item is { row: ProductCategoryAttributionRow; value: number } =>
          item.value !== null && item.value !== 0,
      )
      .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))[0];
    if (largestUnexplained) {
      items.push({
        key: "largest_unexplained",
        categoryId: largestUnexplained.row.category_id,
        categoryLabel:
          largestUnexplained.row.category_name ||
          largestUnexplained.row.category_id,
        reasonLabel: "未解释金额最大",
        primaryLabel: formatSignedProductCategoryYi(largestUnexplained.value),
        secondaryLabel: "需要复核归因残差",
        tone: productCategoryDeltaTone(largestUnexplained.value),
      });
    }
  }
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    items,
    emptyCopy:
      items.length === 0 ? "当前没有可形成决策焦点的产品行或归因结果。" : null,
  };
}

function signedBpLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0 bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1).replace(/\.0$/, "")} bp`;
}

function bpLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(1).replace(/\.0$/, "")} bp`;
}

function signedYiDeltaLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
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

function productCategoryActionLabel(
  kind: ProductCategoryOperatingActionKind,
): string {
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

function averageProductCategoryNumber(
  values: Array<number | null>,
): number | null {
  const candidates = values.filter(
    (value): value is number => value !== null && Number.isFinite(value),
  );
  if (candidates.length === 0) {
    return null;
  }
  return Number(
    (
      candidates.reduce((total, value) => total + value, 0) / candidates.length
    ).toFixed(2),
  );
}

function productCategoryRateLabel(rate: number | null): string {
  if (rate === null || !Number.isFinite(rate)) {
    return EM_DASH;
  }
  return `${(rate * 100).toFixed(1)}%`;
}

function signedProductCategoryBpDeltaLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0.0 bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1)} bp`;
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
  if (
    input.currentUnexplainedAbs === null ||
    input.nextUnexplainedAbs === null
  ) {
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
  const movement = buildProductCategoryOperatingMovementRows(
    attribution,
    parentCategoryIds,
  ).find((row) => row.categoryId === categoryId);
  if (!movement) {
    return 0;
  }
  return movement.leadingDriverKey === "unexplained_effect"
    ? Math.abs(movement.leadingDriverValue)
    : 0;
}

function productCategoryBacktestEvidenceLabel(
  kind: ProductCategoryOperatingActionKind,
): string {
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

function productCategoryBacktestTone(
  hitRate: number | null,
): "positive" | "negative" | "neutral" {
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

const PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER: ProductCategoryOperatingBacktestMissReasonKey[] =
  [
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
    if (
      input.scaleDelta !== null &&
      input.scaleDelta > 0 &&
      (input.yieldDeltaBp === null || input.yieldDeltaBp <= 0)
    ) {
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
    input.currentUnexplainedAbs !== null &&
    input.nextUnexplainedAbs !== null &&
    input.nextUnexplainedAbs >= input.currentUnexplainedAbs
  ) {
    reasons.push("attribution_not_reduced");
  }
  if (reasons.length === 0) {
    reasons.push("outcome_not_improved");
  }
  return reasons;
}

function productCategoryBacktestCalibrationRows(input: {
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  missReasonRows: ProductCategoryOperatingBacktestMissActionRow[];
}): ProductCategoryOperatingBacktestCalibrationRow[] {
  const missRowsByAction = new Map(
    input.missReasonRows.map((row) => [row.actionKind, row]),
  );
  const confidenceForCount = (count: number) => ({
    confidenceLabel: count >= 6 ? "高置信" : count >= 3 ? "中置信" : "低置信",
    confidenceDetailLabel: `${count} 条可评价样本`,
  });
  return input.actionRows
    .map((row) => {
      const missRow = missRowsByAction.get(row.actionKind);
      const confidence = confidenceForCount(row.comparableCount);
      if (row.hitRate !== null && row.hitRate >= 0.5) {
        return {
          actionKind: row.actionKind,
          actionLabel: row.actionLabel,
          recommendationLabel: "保留规则",
          reasonLabel: `命中率 ${row.hitRateLabel}，样本方向可继续复用`,
          evidenceLabel: `${row.signalCount} 条信号 · ${row.evidenceLabel}`,
          ...confidence,
          tone: "positive" as const,
        };
      }
      if (row.hitRate !== null && row.hitRate < 0.3 && missRow) {
        return {
          actionKind: row.actionKind,
          actionLabel: row.actionLabel,
          recommendationLabel: "收紧触发条件",
          reasonLabel: `命中率 ${row.hitRateLabel}，主因${missRow.primaryReasonLabel}`,
          evidenceLabel: `${missRow.missCount}/${missRow.comparableCount} 未命中 · ${row.evidenceLabel}`,
          ...confidence,
          tone: "negative" as const,
        };
      }
      return {
        actionKind: row.actionKind,
        actionLabel: row.actionLabel,
        recommendationLabel: "继续观察",
        reasonLabel: `命中率 ${row.hitRateLabel}，样本仍需累积`,
        evidenceLabel: `${row.signalCount} 条信号 · ${row.evidenceLabel}`,
        ...confidence,
        tone: "neutral" as const,
      };
    })
    .sort((left, right) => {
      const rank = { negative: 0, neutral: 1, positive: 2 };
      return rank[left.tone] - rank[right.tone];
    });
}

function productCategoryBacktestLatestReviewRows(input: {
  latestActionRows: ProductCategoryOperatingActionQueueRow[];
  actionRows: ProductCategoryOperatingBacktestActionRow[];
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[];
  latestReportDate: string | null;
  backtestGateTone: "positive" | "negative" | "neutral";
}): ProductCategoryOperatingBacktestLatestReviewRow[] {
  const actionRowsByAction = new Map(
    input.actionRows.map((row) => [row.actionKind, row]),
  );
  const watchReportDate = input.latestReportDate
    ? productCategoryNextMonthEndDate(input.latestReportDate)
    : null;
  const reviewLabel =
    input.backtestGateTone === "negative" ? "补样本后复核" : "复核后执行";
  const riskRankForCalibration = (
    calibration: ProductCategoryOperatingBacktestCalibrationRow,
  ) => {
    if (calibration.confidenceLabel === "高置信") {
      return "P1 高置信复核";
    }
    if (calibration.confidenceLabel === "中置信") {
      return "P2 中样本复核";
    }
    return "P3 低样本复核";
  };
  const checkItemsForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string[] => {
    if (actionKind === "reprice_or_improve") {
      return [
        "确认最新收益率改善证据",
        "复核规模扩张是否稀释收益率",
        "核对净营收是否同步改善",
      ];
    }
    if (actionKind === "shrink_or_limit") {
      return [
        "确认压降后净营收改善",
        "复核规模回落是否落实",
        "核对收益率是否继续承压",
      ];
    }
    if (actionKind === "selective_growth") {
      return [
        "确认扩张后仍为正贡献",
        "复核新增规模质量",
        "核对收益率是否被摊薄",
      ];
    }
    return ["确认未解释差异下降", "复核归因残差来源", "核对正式归因闭合误差"];
  };
  const releaseConditionForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string => {
    if (actionKind === "reprice_or_improve") {
      return "放行条件：收益率转正改善且净营收不恶化";
    }
    if (actionKind === "shrink_or_limit") {
      return "放行条件：净营收改善且规模不反弹";
    }
    if (actionKind === "selective_growth") {
      return "放行条件：规模扩张且净营收为正";
    }
    return "放行条件：未解释差异下降且闭合误差可接受";
  };
  const observationForAction = (
    actionKind: ProductCategoryOperatingActionKind,
  ): string => {
    if (actionKind === "reprice_or_improve") {
      return "观察口径：下一期收益率改善且净营收不恶化";
    }
    if (actionKind === "shrink_or_limit") {
      return "观察口径：下一期净营收改善且规模不反弹";
    }
    if (actionKind === "selective_growth") {
      return "观察口径：下一期规模扩张且净营收为正";
    }
    return "观察口径：下一期未解释差异下降且闭合误差可接受";
  };
  const gapForAction = (
    row: ProductCategoryOperatingActionQueueRow,
  ): string => {
    if (row.actionKind === "reprice_or_improve") {
      const yieldEvidence =
        row.evidenceItems.find((item) => item.startsWith("收益率 ")) ??
        "收益率 -";
      return `判定缺口：当前${yieldEvidence}，需下一期收益率转正改善`;
    }
    if (row.actionKind === "shrink_or_limit") {
      const netIncomeEvidence =
        row.evidenceItems.find((item) => item.startsWith("净营收 ")) ??
        "净营收 -";
      return `判定缺口：当前${netIncomeEvidence}，需下一期净营收改善`;
    }
    if (row.actionKind === "selective_growth") {
      const scaleEvidence =
        row.evidenceItems.find((item) => item.startsWith("规模 ")) ?? "规模 -";
      return `判定缺口：当前${scaleEvidence}，需下一期规模扩张且净营收为正`;
    }
    return "判定缺口：需下一期正式归因确认未解释差异下降";
  };
  const tightenRowsByAction = new Map(
    input.calibrationRows
      .filter((row) => row.recommendationLabel === "收紧触发条件")
      .map((row) => [row.actionKind, row]),
  );
  return input.latestActionRows.flatMap((row) => {
    const calibration = tightenRowsByAction.get(row.actionKind);
    if (!calibration) {
      return [];
    }
    const actionRow = actionRowsByAction.get(row.actionKind);
    return [
      {
        priorityLabel: row.priorityLabel,
        categoryId: row.categoryId,
        categoryLabel: row.categoryLabel,
        actionKind: row.actionKind,
        actionLabel: row.actionLabel,
        reviewLabel,
        riskRankLabel: riskRankForCalibration(calibration),
        riskReasonLabel: `${calibration.confidenceLabel}；${calibration.reasonLabel.replace(/^命中率 [^，]+，/, "")}`,
        reasonLabel: `历史回测建议${calibration.recommendationLabel}：${calibration.reasonLabel}`,
        impactLabel: actionRow
          ? `历史均值：净营收 ${actionRow.averageNetIncomeDeltaLabel} 亿元、收益率 ${actionRow.averageYieldDeltaBpLabel}、规模 ${actionRow.averageScaleDeltaLabel} 亿元`
          : `历史均值：${EM_DASH}`,
        watchReportDateLabel: `观察月份：${watchReportDate ?? EM_DASH}`,
        releaseConditionLabel: releaseConditionForAction(row.actionKind),
        observationLabel: observationForAction(row.actionKind),
        gapLabel: gapForAction(row),
        evidenceLabel: `${row.triggerLabel}；${calibration.confidenceLabel}，${calibration.evidenceLabel}`,
        currentEvidenceItems: row.evidenceItems,
        checkItems: checkItemsForAction(row.actionKind),
        tone: "negative" as const,
      },
    ];
  });
}

function productCategoryBacktestReviewWorkload(
  latestReviewRows: ProductCategoryOperatingBacktestLatestReviewRow[],
): {
  reviewWorkloadLabel: string;
  reviewWorkloadDetailLabel: string;
} {
  const p1Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P1"),
  ).length;
  const p2Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P2"),
  ).length;
  const p3Count = latestReviewRows.filter((row) =>
    row.riskRankLabel.startsWith("P3"),
  ).length;
  const headline =
    p1Count > 0
      ? `P1 ${p1Count}`
      : p2Count > 0
        ? `P2 ${p2Count}`
        : p3Count > 0
          ? `P3 ${p3Count}`
          : "0";
  return {
    reviewWorkloadLabel: headline,
    reviewWorkloadDetailLabel: `复核 ${latestReviewRows.length} 条；P1 ${p1Count} 条，P2 ${p2Count} 条，P3 ${p3Count} 条`,
  };
}

function productCategoryBacktestRuleDisposition(
  calibrationRows: ProductCategoryOperatingBacktestCalibrationRow[],
): {
  dispositionLabel: string;
  dispositionDetailLabel: string;
} {
  const tightenCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "收紧触发条件",
  ).length;
  const observeCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "继续观察",
  ).length;
  const keepCount = calibrationRows.filter(
    (row) => row.recommendationLabel === "保留规则",
  ).length;
  const headline =
    tightenCount > 0
      ? `收紧 ${tightenCount}`
      : observeCount > 0
        ? `观察 ${observeCount}`
        : `保留 ${keepCount}`;
  return {
    dispositionLabel: headline,
    dispositionDetailLabel: `规则处置：收紧 ${tightenCount} 条，观察 ${observeCount} 条，保留 ${keepCount} 条`,
  };
}

const PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT = 3;
const PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT = 6;

function productCategoryBacktestGate(input: {
  evaluatedMonthCount: number;
  signalCount: number;
}): {
  backtestGateLabel: string;
  backtestGateDetailLabel: string;
  backtestGateTone: "positive" | "negative" | "neutral";
} {
  const enoughHistory =
    input.evaluatedMonthCount >= PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT;
  const enoughSignals =
    input.signalCount >= PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT;
  if (enoughHistory && enoughSignals) {
    return {
      backtestGateLabel: "可用于复核",
      backtestGateDetailLabel: `连续回测 ${input.evaluatedMonthCount}/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月；可评价信号 ${input.signalCount} 条，达到规则复核阈值`,
      backtestGateTone: "positive",
    };
  }
  return {
    backtestGateLabel: "样本不足",
    backtestGateDetailLabel: `连续回测 ${input.evaluatedMonthCount}/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月；可评价信号 ${input.signalCount} 条，未达到规则放行阈值`,
    backtestGateTone: "negative",
  };
}

function productCategoryBacktestSampleRepair(input: {
  evaluatedMonthCount: number;
  signalCount: number;
  latestReportDate: string | null;
}): {
  sampleRepairLabel: string;
  sampleRepairDetailLabel: string;
  sampleRepairDateLabel: string;
  sampleRepairReviewLabel: string;
} {
  const missingMonthCount = Math.max(
    0,
    PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT - input.evaluatedMonthCount,
  );
  const missingSignalCount = Math.max(
    0,
    PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT - input.signalCount,
  );
  const repairDates: string[] = [];
  let cursor = input.latestReportDate;
  for (let index = 0; index < missingMonthCount; index += 1) {
    const nextDate = cursor ? productCategoryNextMonthEndDate(cursor) : null;
    if (!nextDate) {
      break;
    }
    repairDates.push(nextDate);
    cursor = nextDate;
  }
  return {
    sampleRepairLabel:
      missingMonthCount > 0
        ? `补 ${missingMonthCount} 个月`
        : missingSignalCount > 0
          ? `补 ${missingSignalCount} 条信号`
          : "样本已满足",
    sampleRepairDetailLabel: `闸口需 ${PRODUCT_CATEGORY_BACKTEST_REQUIRED_MONTH_COUNT} 个月/${PRODUCT_CATEGORY_BACKTEST_REQUIRED_SIGNAL_COUNT} 条信号；当前 ${input.evaluatedMonthCount} 个月/${input.signalCount} 条信号`,
    sampleRepairDateLabel:
      repairDates.length > 0
        ? `需补月份：${repairDates.join("、")}`
        : "需补月份：-",
    sampleRepairReviewLabel:
      repairDates.length > 0
        ? `最早复核：${repairDates[repairDates.length - 1]} 后`
        : missingSignalCount > 0
          ? "最早复核：待补齐信号后"
          : "最早复核：当前可复核",
  };
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

function productCategoryReportDatesAreConsecutiveMonths(
  current: string,
  next: string,
): boolean {
  return productCategoryNextMonthEndDate(current) === next;
}

function productCategoryBacktestEmptyCopy(
  coverageRows: ProductCategoryOperatingBacktestSurface["coverageRows"],
): string {
  const skippedRow = coverageRows.find(
    (row) => row.statusLabel === "跳过：非连续月份",
  );
  if (skippedRow?.nextReportDate) {
    const expectedNextReportDate = productCategoryNextMonthEndDate(
      skippedRow.reportDate,
    );
    return `需要至少两个连续月度正式 payload 才能回测行动信号；${skippedRow.reportDate} 后缺少 ${expectedNextReportDate ?? EM_DASH}，实际下一期为 ${skippedRow.nextReportDate}。`;
  }
  return "需要至少两个连续月度正式 payload 才能回测行动信号。";
}

function productCategoryAttributionCoverage(input: {
  payloads: ProductCategoryPnlPayload[];
  attributionsByReportDate?: Map<
    string,
    ProductCategoryAttributionPayload | null
  >;
}): {
  attributionCoverageLabel: string;
  attributionCoverageDetailLabel: string;
} {
  const reportDates = Array.from(
    new Set(input.payloads.map((payload) => payload.report_date)),
  ).sort();
  if (reportDates.length === 0) {
    return {
      attributionCoverageLabel: "0/0",
      attributionCoverageDetailLabel: "暂无月度归因样本",
    };
  }
  const coveredDates = reportDates.filter((reportDate) =>
    input.attributionsByReportDate?.get(reportDate),
  );
  const missingDates = reportDates.filter(
    (reportDate) => !input.attributionsByReportDate?.get(reportDate),
  );
  const missingSuffix =
    missingDates.length > 0
      ? `；缺少 ${missingDates.slice(0, 3).join("、")}`
      : "；归因样本完整";
  return {
    attributionCoverageLabel: `${coveredDates.length}/${reportDates.length}`,
    attributionCoverageDetailLabel: `归因覆盖 ${coveredDates.length}/${reportDates.length}${missingSuffix}`,
  };
}

export function selectProductCategoryOperatingActionBacktestSurface(input: {
  payloads: ProductCategoryPnlPayload[];
  attributionsByReportDate?: Map<
    string,
    ProductCategoryAttributionPayload | null
  >;
}): ProductCategoryOperatingBacktestSurface {
  const payloads = input.payloads
    .filter((payload) => payload.view === "monthly")
    .slice()
    .sort((left, right) => left.report_date.localeCompare(right.report_date));
  const attributionCoverage = productCategoryAttributionCoverage({
    payloads,
    attributionsByReportDate: input.attributionsByReportDate,
  });
  const latestPayload = payloads[payloads.length - 1];
  const latestActionRows = latestPayload
    ? selectProductCategoryOperatingActionQueue({
        rows: latestPayload.rows,
        attribution: input.attributionsByReportDate?.get(
          latestPayload.report_date,
        ),
        parentCategoryIds: parentProductCategoryIds(latestPayload.rows),
      }).rows
    : [];
  const latestPendingCount = latestActionRows.length;
  const samples: ProductCategoryOperatingBacktestExample[] = [];
  const coverageRows: ProductCategoryOperatingBacktestSurface["coverageRows"] =
    [];

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
    if (
      !productCategoryReportDatesAreConsecutiveMonths(
        current.report_date,
        next.report_date,
      )
    ) {
      coverageRows.push({
        reportDate: current.report_date,
        nextReportDate: next.report_date,
        statusLabel: "跳过：非连续月份",
        detailLabel: `期望下一月末 ${productCategoryNextMonthEndDate(current.report_date) ?? EM_DASH}，实际 ${next.report_date}`,
        signalCount: currentActions.length,
        tone: "negative",
      });
      continue;
    }
    const currentRowsById = new Map(
      current.rows.map((row) => [row.category_id, row]),
    );
    const nextRowsById = new Map(
      next.rows.map((row) => [row.category_id, row]),
    );
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
      const currentUnexplainedAbs =
        productCategoryBacktestCurrentUnexplainedAbs(action);
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
      detailLabel: "使用下一期 monthly 正式 payload 验证",
      signalCount: currentActions.length,
      tone: "positive",
    });
  }
  if (latestPayload) {
    coverageRows.push({
      reportDate: latestPayload.report_date,
      nextReportDate: null,
      statusLabel: "最新月待观察",
      detailLabel: `等待下一期 ${productCategoryNextMonthEndDate(latestPayload.report_date) ?? EM_DASH} payload 验证`,
      signalCount: latestPendingCount,
      tone: "neutral",
    });
  }

  const evaluatedDates = Array.from(
    new Set(samples.map((sample) => sample.reportDate)),
  ).sort();
  const actionRows = (
    [
      "shrink_or_limit",
      "review_attribution",
      "reprice_or_improve",
      "selective_growth",
    ] as const
  ).flatMap((actionKind) => {
    const rows = samples.filter((sample) => sample.actionKind === actionKind);
    if (rows.length === 0) {
      return [];
    }
    const hitCount = rows.filter((row) => row.outcomeLabel === "命中").length;
    const comparableCount = rows.filter(
      (row) => row.outcomeLabel !== "待判定",
    ).length;
    const hitRate = comparableCount === 0 ? null : hitCount / comparableCount;
    const averageNetIncomeDelta = averageProductCategoryNumber(
      rows.map((row) => row.netIncomeDelta),
    );
    const averageYieldDeltaBp = averageProductCategoryNumber(
      rows.map((row) => row.yieldDeltaBp),
    );
    const averageScaleDelta = averageProductCategoryNumber(
      rows.map((row) => row.scaleDelta),
    );
    return [
      {
        actionKind,
        actionLabel: productCategoryActionLabel(actionKind),
        signalCount: rows.length,
        comparableCount,
        hitCount,
        hitRate,
        hitRateLabel: productCategoryRateLabel(hitRate),
        averageNetIncomeDelta,
        averageNetIncomeDeltaLabel: signedYiDeltaLabel(averageNetIncomeDelta),
        averageYieldDeltaBp,
        averageYieldDeltaBpLabel:
          signedProductCategoryBpDeltaLabel(averageYieldDeltaBp),
        averageScaleDelta,
        averageScaleDeltaLabel: signedYiDeltaLabel(averageScaleDelta),
        evidenceLabel: productCategoryBacktestEvidenceLabel(actionKind),
        tone: productCategoryBacktestTone(hitRate),
      },
    ];
  });
  const missReasonRows = (
    [
      "shrink_or_limit",
      "review_attribution",
      "reprice_or_improve",
      "selective_growth",
    ] as const
  )
    .flatMap((actionKind) => {
      const rows = samples.filter((sample) => sample.actionKind === actionKind);
      const comparableRows = rows.filter(
        (row) => row.outcomeLabel !== "待判定",
      );
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
          return (
            PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(left[0]) -
            PRODUCT_CATEGORY_BACKTEST_MISS_REASON_ORDER.indexOf(right[0])
          );
        })
        .map(([reasonKey, sampleCount]) => ({
          reasonKey,
          reasonLabel: productCategoryBacktestMissReasonLabel(reasonKey),
          sampleCount,
          sampleShareLabel: `${sampleCount}/${missedRows.length}`,
        }));
      const missRate =
        comparableRows.length === 0
          ? null
          : missedRows.length / comparableRows.length;
      return [
        {
          actionKind,
          actionLabel: productCategoryActionLabel(actionKind),
          missCount: missedRows.length,
          comparableCount: comparableRows.length,
          missRate,
          missRateLabel: productCategoryRateLabel(missRate),
          primaryReasonLabel: reasonRows[0]?.reasonLabel ?? EM_DASH,
          reasonRows,
          tone: productCategoryBacktestTone(
            missRate === null ? null : 1 - missRate,
          ),
        },
      ];
    })
    .sort((left, right) => {
      if ((right.missRate ?? -1) !== (left.missRate ?? -1)) {
        return (right.missRate ?? -1) - (left.missRate ?? -1);
      }
      return right.missCount - left.missCount;
    });
  const calibrationRows = productCategoryBacktestCalibrationRows({
    actionRows,
    missReasonRows,
  });
  const backtestGate = productCategoryBacktestGate({
    evaluatedMonthCount: evaluatedDates.length,
    signalCount: samples.length,
  });
  const sampleRepair = productCategoryBacktestSampleRepair({
    evaluatedMonthCount: evaluatedDates.length,
    signalCount: samples.length,
    latestReportDate: latestPayload?.report_date ?? null,
  });
  const latestReviewRows = productCategoryBacktestLatestReviewRows({
    latestActionRows,
    actionRows,
    calibrationRows,
    latestReportDate: latestPayload?.report_date ?? null,
    backtestGateTone: backtestGate.backtestGateTone,
  });
  const reviewWorkload =
    productCategoryBacktestReviewWorkload(latestReviewRows);
  const ruleDisposition =
    productCategoryBacktestRuleDisposition(calibrationRows);

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    summary: {
      evaluatedMonthCount: evaluatedDates.length,
      signalCount: samples.length,
      latestPendingCount,
      coverageLabel:
        evaluatedDates.length > 0
          ? `${evaluatedDates[0]} 至 ${evaluatedDates[evaluatedDates.length - 1]}`
          : EM_DASH,
      attributionCoverageLabel: attributionCoverage.attributionCoverageLabel,
      attributionCoverageDetailLabel:
        attributionCoverage.attributionCoverageDetailLabel,
      backtestGateLabel: backtestGate.backtestGateLabel,
      backtestGateDetailLabel: backtestGate.backtestGateDetailLabel,
      backtestGateTone: backtestGate.backtestGateTone,
      sampleRepairLabel: sampleRepair.sampleRepairLabel,
      sampleRepairDetailLabel: sampleRepair.sampleRepairDetailLabel,
      sampleRepairDateLabel: sampleRepair.sampleRepairDateLabel,
      sampleRepairReviewLabel: sampleRepair.sampleRepairReviewLabel,
      reviewWorkloadLabel: reviewWorkload.reviewWorkloadLabel,
      reviewWorkloadDetailLabel: reviewWorkload.reviewWorkloadDetailLabel,
      dispositionLabel: ruleDisposition.dispositionLabel,
      dispositionDetailLabel: ruleDisposition.dispositionDetailLabel,
      evidenceLabel: "信号来自动作队列；结果使用下一期 monthly 正式口径验证。",
    },
    coverageRows,
    actionRows,
    missReasonRows,
    calibrationRows,
    latestReviewRows,
    examples: samples
      .slice()
      .sort(
        (left, right) =>
          Math.abs(right.netIncomeDelta ?? 0) -
          Math.abs(left.netIncomeDelta ?? 0),
      )
      .slice(0, 6),
    emptyCopy:
      samples.length === 0
        ? productCategoryBacktestEmptyCopy(coverageRows)
        : null,
  };
}

function productCategorySideLabel(side: string): string {
  if (side === "asset") {
    return "\u8d44\u4ea7";
  }
  if (side === "liability") {
    return "\u8d1f\u503a";
  }
  return side || EM_DASH;
}

function formatProductCategoryDiagnosticMoneyLabel(
  row: Pick<ProductCategoryPnlRow, "side">,
  value: DecimalLike | null | undefined,
  options?: { foreignDisplay?: boolean },
): string {
  const display = options?.foreignDisplay
    ? formatProductCategoryForeignDisplayValue(row, value)
    : formatProductCategoryRowDisplayValue(row, value);
  return display === EM_DASH ? "\u7f3a\u5931" : `${display} \u4ebf\u5143`;
}

function formatProductCategoryDiagnosticYieldLabel(
  value: DecimalLike | null | undefined,
): { label: string; missing: boolean } {
  const display = formatProductCategoryYieldValue(value);
  if (display === EM_DASH) {
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
    currencyPressureHints.push(
      "\u4eba\u6c11\u5e01\u51c0\u6536\u5165\u4e3a\u8d1f",
    );
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
  const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(
    row.weighted_yield,
  );
  return {
    categoryId: row.category_id,
    categoryLabel: row.category_name,
    sideLabel: productCategorySideLabel(row.side),
    scaleLabel:
      scaleDisplay === EM_DASH
        ? "\u89c4\u6a21\u7f3a\u5931"
        : `${scaleDisplay} \u4ebf\u5143`,
    scaleMissing: scaleDisplay === EM_DASH,
    businessNetIncomeLabel: formatProductCategoryDiagnosticMoneyLabel(
      row,
      row.business_net_income,
    ),
    businessNetIncomeTone: toneNameForValue(row.business_net_income),
    yieldLabel: yieldDisplay.label,
    yieldMissing: yieldDisplay.missing,
    cnyNetLabel: formatProductCategoryDiagnosticMoneyLabel(row, row.cny_net),
    cnyNetTone: toneNameForValue(row.cny_net),
    foreignNetLabel: formatProductCategoryDiagnosticMoneyLabel(
      row,
      row.foreign_net,
      {
        foreignDisplay: true,
      },
    ),
    foreignNetTone: toneNameForValue(
      productCategoryForeignDisplayNumber(row, row.foreign_net),
    ),
    driverHint: buildProductCategoryDriverHint(row),
  };
}

function buildSpreadMovementDriverHint(
  assetYieldDelta: number | null,
  liabilityYieldDelta: number | null,
  spreadDelta: number | null,
): string {
  if (
    assetYieldDelta === null ||
    liabilityYieldDelta === null ||
    spreadDelta === null
  ) {
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
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
}): ProductCategorySpreadMovementAttribution {
  const currentSnapshot =
    input.trendSnapshots?.[0] ??
    (input.assetTotal || input.liabilityTotal
      ? {
          reportDate:
            input.assetTotal?.report_date ??
            input.liabilityTotal?.report_date ??
            "",
          rows: [],
          assetTotal: input.assetTotal,
          liabilityTotal: input.liabilityTotal,
          interestSpread: input.interestSpread ?? null,
        }
      : null);
  const priorSnapshot = input.trendSnapshots?.slice(1)[0] ?? null;

  const currentLabel =
    currentSnapshot?.label ??
    formatProductCategoryReportMonthLabel(currentSnapshot?.reportDate ?? "");
  const priorLabel =
    priorSnapshot?.label ??
    formatProductCategoryReportMonthLabel(priorSnapshot?.reportDate ?? "");
  const currentAssetYield = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_asset_yield_pct,
  );
  const currentLiabilityYield = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_liability_yield_pct,
  );
  const currentSpread = interestSpreadMetricNumber(
    currentSnapshot?.interestSpread?.all_currency_spread_pct,
  );
  const priorAssetYield = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_asset_yield_pct,
  );
  const priorLiabilityYield = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_liability_yield_pct,
  );
  const priorSpread = interestSpreadMetricNumber(
    priorSnapshot?.interestSpread?.all_currency_spread_pct,
  );
  const assetYieldDelta =
    currentAssetYield === null || priorAssetYield === null
      ? null
      : (currentAssetYield - priorAssetYield) * 100;
  const liabilityYieldDelta =
    currentLiabilityYield === null || priorLiabilityYield === null
      ? null
      : (currentLiabilityYield - priorLiabilityYield) * 100;
  const spreadDelta =
    currentSpread === null || priorSpread === null
      ? null
      : (currentSpread - priorSpread) * 100;

  const base: ProductCategorySpreadMovementAttributionBase = {
    currentLabel: currentLabel || "\u5f53\u524d\u671f",
    priorLabel: priorLabel || "\u4e0a\u671f",
    currentAssetYieldLabel:
      currentAssetYield === null
        ? "\u7f3a\u5931"
        : `${currentAssetYield.toFixed(2)}%`,
    currentLiabilityYieldLabel:
      currentLiabilityYield === null
        ? "\u7f3a\u5931"
        : `${currentLiabilityYield.toFixed(2)}%`,
    currentSpreadLabel: bpLabel(currentSpread),
    priorSpreadLabel: bpLabel(priorSpread),
    assetYieldDeltaLabel: signedBpLabel(assetYieldDelta),
    liabilityYieldDeltaLabel: signedBpLabel(liabilityYieldDelta),
    spreadDeltaLabel: signedBpLabel(spreadDelta),
    driverHint: buildSpreadMovementDriverHint(
      assetYieldDelta,
      liabilityYieldDelta,
      spreadDelta,
    ),
  };

  if (!currentSnapshot) {
    return {
      state: "incomplete",
      reason:
        "\u5f53\u524d\u5feb\u7167\u7f3a\u5931\uff0c\u65e0\u6cd5\u6784\u5efa\u5229\u5dee\u5f52\u56e0\u3002",
      ...base,
    };
  }
  if (currentAssetYield === null || currentLiabilityYield === null) {
    return {
      state: "incomplete",
      reason: "后端未返回资产端或负债端收益率字段，无法展示利差归因。",
      ...base,
    };
  }
  if (currentSpread === null) {
    return {
      state: "incomplete",
      reason: "后端未返回利差指标，无法展示当期利差。",
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
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
}): ProductCategoryDiagnosticsSurface {
  const productRows = input.rows.filter(
    (row) => !row.is_total && row.category_id !== "grand_total",
  );
  const matrixRows = productRows.map(buildProductCategoryDiagnosticsMatrixRow);
  const negativeWatchlistRows = productRows
    .filter((row) => {
      const businessNetIncome = decimalNumber(row.business_net_income);
      return businessNetIncome !== null && businessNetIncome < 0;
    })
    .sort(
      (left, right) =>
        Number(left.business_net_income) - Number(right.business_net_income),
    )
    .map((row) => {
      const scaleDisplay = formatProductCategoryRowDisplayValue(
        row,
        row.cnx_scale,
      );
      const yieldDisplay = formatProductCategoryDiagnosticYieldLabel(
        row.weighted_yield,
      );
      return {
        categoryId: row.category_id,
        categoryLabel: row.category_name,
        sideLabel: productCategorySideLabel(row.side),
        lossLabel: formatProductCategoryDiagnosticMoneyLabel(
          row,
          row.business_net_income,
        ),
        scaleLabel:
          scaleDisplay === EM_DASH
            ? "\u89c4\u6a21\u7f3a\u5931"
            : `${scaleDisplay} \u4ebf\u5143`,
        scaleMissing: scaleDisplay === EM_DASH,
        yieldLabel: yieldDisplay.label,
        yieldMissing: yieldDisplay.missing,
        driverHint: buildProductCategoryDriverHint(row),
      };
    });

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    headlineTotalLabel: input.grandTotal
      ? `${formatProductCategoryValue(input.grandTotal.business_net_income)} \u4ebf\u5143`
      : null,
    matrixRows,
    matrixEmptyCopy:
      matrixRows.length === 0
        ? "\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002"
        : null,
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
      interestSpread: input.interestSpread ?? null,
    }),
  };
}

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

const PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS = [
  "interbank_deposits",
  "interbank_borrowings",
  "repo_liabilities",
  "interbank_cds",
  "credit_linked_notes",
] as const;

function emptyProductCategoryManagementMonitoringSurface(
  state: "insufficient" | "scenario_blocked",
  reportDate: string,
  emptyCopy: string,
  coverageLabel = "待补齐",
): ProductCategoryManagementMonitoringSurface {
  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    state,
    periodLabel: reportDate
      ? formatProductCategoryReportMonthLabel(reportDate)
      : "未选择报告月份",
    coverageLabel,
    emptyCopy,
    tpl: null,
    liability: null,
    derivatives: null,
    runRate: null,
    methodNotes: [],
  };
}

function formatProductCategoryManagementYi(value: number): string {
  return value.toFixed(2);
}

function formatProductCategoryManagementPercent(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? EM_DASH
    : `${value.toFixed(1)}%`;
}

/**
 * Candidate management view derived from six monthly formal payloads and the June MoM attribution.
 * It does not replace governed totals, forecast results, or formal FTP scenario calculations.
 */
export function selectProductCategoryManagementMonitoringSurface(input: {
  reportDate: string;
  snapshots: ProductCategoryTrendSnapshot[];
  currentAttribution?: ProductCategoryAttributionPayload | null;
  scenarioDistinct?: boolean;
}): ProductCategoryManagementMonitoringSurface {
  if (input.scenarioDistinct) {
    return emptyProductCategoryManagementMonitoringSurface(
      "scenario_blocked",
      input.reportDate,
      "经营修复监控只使用正式基准口径；请将 FTP 场景恢复为正式基准后查看。",
      "正式基线停算",
    );
  }

  const selected = parseProductCategoryReportDate(input.reportDate);
  if (!selected || selected.month !== 6) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      "本监控按 1—6 月连续 monthly 正式数据生成，仅在 6 月末报告展示。",
      "需选择 6 月末",
    );
  }

  const snapshotsByMonth = new Map<number, ProductCategoryTrendSnapshot>();
  input.snapshots.forEach((snapshot) => {
    const parsed = parseProductCategoryReportDate(snapshot.reportDate);
    if (
      parsed?.year === selected.year &&
      parsed.month >= 1 &&
      parsed.month <= 6 &&
      (!snapshot.view || snapshot.view === "monthly")
    ) {
      snapshotsByMonth.set(parsed.month, snapshot);
    }
  });
  const missingMonths = [1, 2, 3, 4, 5, 6].filter(
    (month) => !snapshotsByMonth.has(month),
  );
  if (missingMonths.length > 0) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      `需要 1—6 月连续 monthly 正式 payload；当前缺少 ${missingMonths.map(formatProductCategoryShortMonthLabel).join("、")}。`,
      `已覆盖 ${6 - missingMonths.length}/6 月`,
    );
  }
  const h1Snapshots = [1, 2, 3, 4, 5, 6].map((month) =>
    snapshotsByMonth.get(month)!,
  );
  const tplRows = h1Snapshots.map((snapshot) =>
    findProductCategoryRow(snapshot.rows, "bond_tpl"),
  );
  const derivativeRows = h1Snapshots.map((snapshot) =>
    findProductCategoryRow(snapshot.rows, "derivatives"),
  );
  const grandTotalValues = h1Snapshots.map((snapshot) =>
    rawYiNumber(snapshot.grandTotal?.business_net_income),
  );
  const liabilityTotalValues = h1Snapshots.map((snapshot) =>
    rawYiNumber(snapshot.liabilityTotal?.business_net_income),
  );
  const tplPnlValues = tplRows.map((row) =>
    rawYiNumber(row?.business_net_income),
  );
  const derivativePnlValues = derivativeRows.map((row) =>
    rawYiNumber(row?.business_net_income),
  );
  const currentAttribution =
    input.currentAttribution?.compare === "mom" &&
    input.currentAttribution.state === "complete" &&
    input.currentAttribution.report_date === input.reportDate
      ? input.currentAttribution
      : null;
  const tplAttributionRow = currentAttribution?.rows.find(
    (row) => row.category_id === "bond_tpl",
  );
  const currentTplPoint = tplAttributionRow?.current;
  const currentTplRow = tplRows[5];
  const requiredValues = [
    ...grandTotalValues,
    ...liabilityTotalValues,
    ...tplPnlValues,
    ...derivativePnlValues,
  ];
  const currentTplScale = rawYiNumber(currentTplPoint?.scale);
  const currentTplPnl = rawYiNumber(currentTplPoint?.business_net_income);
  const currentTplYield = decimalNumber(currentTplPoint?.yield_pct);
  const currentTplFtp = decimalNumber(currentTplRow?.baseline_ftp_rate_pct);
  const currentTplDays = currentTplPoint?.days ?? null;
  if (
    requiredValues.some((value) => value === null) ||
    currentTplScale === null ||
    currentTplScale <= 0 ||
    currentTplPnl === null ||
    currentTplYield === null ||
    currentTplFtp === null ||
    currentTplDays === null ||
    currentTplDays <= 0
  ) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      "连续月份已覆盖，但 TPL、衍生品、合计行或本期正式归因字段不完整，候选监控未生成。",
      "6/6 月 · 字段不完整",
    );
  }

  const safeTplPnlValues = tplPnlValues as number[];
  const safeGrandTotalValues = grandTotalValues as number[];
  const safeLiabilityTotalValues = liabilityTotalValues as number[];
  const safeDerivativePnlValues = derivativePnlValues as number[];
  const sum = (values: number[]) =>
    values.reduce((total, value) => total + value, 0);
  const average = (values: number[]) => sum(values) / values.length;
  const q1TplAverage = average(safeTplPnlValues.slice(0, 3));
  const h1TplAverage = average(safeTplPnlValues);
  const thresholdInputs = [
    {
      key: "prior_month" as const,
      label: "达到 5 月净营收水平",
      targetPnl: safeTplPnlValues[4]!,
    },
    {
      key: "h1_average" as const,
      label: "达到 H1 月均净营收水平",
      targetPnl: h1TplAverage,
    },
    {
      key: "q1_average" as const,
      label: "达到 Q1 月均净营收水平",
      targetPnl: q1TplAverage,
    },
  ];
  const thresholds = thresholdInputs.map((threshold) => {
    const requiredYield =
      currentTplFtp +
      (threshold.targetPnl / currentTplScale) * (365 / currentTplDays) * 100;
    const liftBp = (requiredYield - currentTplYield) * 100;
    return {
      key: threshold.key,
      label: threshold.label,
      targetPnlLabel: formatProductCategoryManagementYi(threshold.targetPnl),
      requiredYieldLabel: `${requiredYield.toFixed(2)}%`,
      liftBpLabel: signedBpLabel(liftBp),
    };
  });

  const liabilityCategoryTotals = PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS.map(
    (categoryId) => {
      const monthlyValues = h1Snapshots.map((snapshot) =>
        rawYiNumber(
          findProductCategoryRow(snapshot.rows, categoryId)
            ?.business_net_income,
        ),
      );
      return monthlyValues.some((value) => value === null)
        ? null
        : sum(monthlyValues as number[]);
    },
  );
  if (liabilityCategoryTotals.some((value) => value === null)) {
    return emptyProductCategoryManagementMonitoringSurface(
      "insufficient",
      input.reportDate,
      "负债端 1—6 月产品明细不完整，候选监控未生成。",
      "6/6 月 · 负债明细不完整",
    );
  }
  const safeLiabilityCategoryTotals = liabilityCategoryTotals as number[];
  const liabilityPositivePool = sum(
    safeLiabilityCategoryTotals.filter((value) => value > 0),
  );
  const liabilityNegativePool = sum(
    safeLiabilityCategoryTotals.filter((value) => value < 0),
  );
  const liabilityOffsetRatio =
    liabilityPositivePool > 0
      ? (Math.abs(liabilityNegativePool) / liabilityPositivePool) * 100
      : null;
  const liabilityCurrentMonthDelta =
    safeLiabilityTotalValues[5]! - safeLiabilityTotalValues[4]!;
  const liabilityAttributionRows = (currentAttribution?.rows ?? [])
    .filter((row) =>
      PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS.includes(
        row.category_id as (typeof PRODUCT_CATEGORY_MANAGEMENT_LIABILITY_IDS)[number],
      ),
    )
    .map((row) => ({
      row,
      delta: rawYiNumber(row.effects.delta_business_net_income),
    }))
    .filter(
      (item): item is { row: ProductCategoryAttributionRow; delta: number } =>
        item.delta !== null && item.delta < 0,
    )
    .sort((left, right) => left.delta - right.delta);
  const leadingLiabilityMovement = liabilityAttributionRows[0] ?? null;
  const liabilityDriverCandidates = leadingLiabilityMovement
    ? [
        ["天数", leadingLiabilityMovement.row.effects.day_effect],
        ["规模", leadingLiabilityMovement.row.effects.scale_effect],
        ["利率", leadingLiabilityMovement.row.effects.rate_effect],
        ["FTP", leadingLiabilityMovement.row.effects.ftp_effect],
        ["直接项", leadingLiabilityMovement.row.effects.direct_effect],
        ["未解释", leadingLiabilityMovement.row.effects.unexplained_effect],
      ].map(([label, value]) => ({
        label: String(label),
        value: rawYiNumber(value as DecimalLike) ?? 0,
      }))
    : [];
  const leadingLiabilityDriver = liabilityDriverCandidates.sort(
    (left, right) => Math.abs(right.value) - Math.abs(left.value),
  )[0];

  const derivativeH1Total = sum(safeDerivativePnlValues);
  const derivativeMonthlyAverage = average(safeDerivativePnlValues);
  const derivativeVolatility = Math.sqrt(
    average(
      safeDerivativePnlValues.map(
        (value) => (value - derivativeMonthlyAverage) ** 2,
      ),
    ),
  );
  const derivativeTopThreeConcentration =
    derivativeH1Total > 0
      ? (sum(
          safeDerivativePnlValues
            .slice()
            .sort((left, right) => right - left)
            .slice(0, 3),
        ) /
          derivativeH1Total) *
        100
      : null;
  const derivativeNegativeMonthCount = safeDerivativePnlValues.filter(
    (value) => value < 0,
  ).length;

  const q1MonthlyAverage = average(safeGrandTotalValues.slice(0, 3));
  const q2MonthlyAverage = average(safeGrandTotalValues.slice(3, 6));
  const h1MonthlyAverage = average(safeGrandTotalValues);
  const recoveryLift =
    q2MonthlyAverage === 0
      ? null
      : (h1MonthlyAverage / q2MonthlyAverage - 1) * 100;
  const h1Total = sum(safeGrandTotalValues);
  const h2AtQ2Pace = q2MonthlyAverage * 6;

  return {
    metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS,
    state: "ready",
    periodLabel: `${selected.year} 年 1—6 月`,
    coverageLabel: "6/6 月正式数据",
    emptyCopy: null,
    tpl: {
      currentPnlLabel: formatProductCategoryManagementYi(currentTplPnl),
      currentYieldLabel: `${currentTplYield.toFixed(2)}%`,
      currentScaleLabel: formatProductCategoryManagementYi(currentTplScale),
      thresholds,
    },
    liability: {
      h1NetLabel: formatProductCategoryManagementYi(
        sum(safeLiabilityTotalValues),
      ),
      positivePoolLabel: formatProductCategoryManagementYi(
        liabilityPositivePool,
      ),
      negativePoolLabel: signedYiDeltaLabel(liabilityNegativePool),
      offsetRatioLabel:
        formatProductCategoryManagementPercent(liabilityOffsetRatio),
      currentMonthDeltaLabel: signedYiDeltaLabel(liabilityCurrentMonthDelta),
      leadingMovementLabel: leadingLiabilityMovement
        ? `${leadingLiabilityMovement.row.category_name || leadingLiabilityMovement.row.category_id} ${signedYiDeltaLabel(leadingLiabilityMovement.delta)}`
        : "6 月无负向回落",
      leadingDriverLabel: leadingLiabilityDriver
        ? `${leadingLiabilityDriver.label} ${signedYiDeltaLabel(leadingLiabilityDriver.value)}`
        : "无可用驱动",
    },
    derivatives: {
      h1TotalLabel: formatProductCategoryManagementYi(derivativeH1Total),
      monthlyAverageLabel: formatProductCategoryManagementYi(
        derivativeMonthlyAverage,
      ),
      volatilityLabel: formatProductCategoryManagementYi(derivativeVolatility),
      topThreeConcentrationLabel: formatProductCategoryManagementPercent(
        derivativeTopThreeConcentration,
      ),
      negativeMonthCountLabel: `${derivativeNegativeMonthCount} 个月`,
    },
    runRate: {
      q1MonthlyAverageLabel:
        formatProductCategoryManagementYi(q1MonthlyAverage),
      q2MonthlyAverageLabel:
        formatProductCategoryManagementYi(q2MonthlyAverage),
      h1MonthlyAverageLabel:
        formatProductCategoryManagementYi(h1MonthlyAverage),
      recoveryLiftLabel: formatProductCategoryManagementPercent(recoveryLift),
      h2AtQ2PaceLabel: formatProductCategoryManagementYi(h2AtQ2Pace),
      gapToH1Label: signedYiDeltaLabel(h2AtQ2Pace - h1Total),
    },
    methodNotes: [
      "TPL 阈值固定 6 月正式规模、正式 FTP 和归因天数，仅反推达到目标净营收所需收益率，不构成预测。",
      "负债改善质量按五类负债产品 H1 正、负净营收池归组；6 月回落及驱动直接复用正式月环比归因。",
      "衍生品稳定性仅以月度净营收波动、负值月份和 Top3 月份集中度作为代理，不识别一次性或可重复收益。",
      "经营节奏用正式 grand_total 的 Q1、Q2 与 H1 月均做静态延展，不替代预算、计财目标或正式预测。",
    ],
  };
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
    percentNumber,
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
        explanation: "仅展示后端返回的资产端收益率（含TPL）字段，不推导利差贡献",
      },
      {
        key: "liability_cost",
        label: "负债端成本率",
        ...surface.rows.liabilityCost,
        explanation: "仅展示后端返回的负债端成本率字段，不推导利差贡献",
      },
      {
        key: "spread",
        label: "资产负债利差（含TPL）",
        ...surface.rows.spread,
        explanation: "展示后端返回的利差指标变动（含TPL口径），不由前端推导",
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
