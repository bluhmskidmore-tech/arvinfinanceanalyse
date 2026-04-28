import type { DecimalLike, ProductCategoryPnlPayload, ProductCategoryPnlRow, ResultMeta } from "../../../api/contracts";
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

export type ProductCategoryLiabilitySideTrendSurface = {
  chart: ProductCategoryLiabilitySideTrendChart | null;
  detailRows: ProductCategoryLiabilityDetailTrendRow[];
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
  const incompleteReasons = chart?.incompleteReasons ?? [];
  if (!chart && detailRows.length === 0) {
    return {
      chart: null,
      detailRows,
      emptyCopy: "当前 payload 未返回可展示的负债端趋势数据。",
      incompleteReasons,
    };
  }
  return {
    chart,
    detailRows,
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

/** Page-visible copy: standalone `as_of_date` is a known outward contract gap (see truth contract §10). */
export const PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY =
  "归属日期：无独立外显字段（显式合同缺口；勿用本页报告日或生成时间代替）。";

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
