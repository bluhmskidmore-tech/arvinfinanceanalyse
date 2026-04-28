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
  return `${match[1]}年${match[2]}月`;
}

export const PRODUCT_CATEGORY_VALUE_TONE_COLORS = {
  default: designTokens.color.neutral[900],
  positive: designTokens.color.semantic.profit,
  negative: designTokens.color.semantic.loss,
} as const;

const YUAN_PER_YI = 100_000_000;

type ProductCategoryDerivedAnalysisTone = "neutral" | "positive" | "negative";

export type ProductCategoryDerivedAnalysisItem = {
  id:
    | "contribution"
    | "interestEarningTrend"
    | "spreadLevel"
    | "interbankLendingTrend"
    | "tplAssetTrend"
    | "driver"
    | "ftp"
    | "review";
  title: string;
  metric: string;
  detail: string;
  tone: ProductCategoryDerivedAnalysisTone;
  points?: ProductCategoryDerivedAnalysisPoint[];
};

export type ProductCategoryDerivedAnalysisPoint = {
  label: string;
  value: string;
  detail?: string;
  tone?: ProductCategoryDerivedAnalysisTone;
};

export type ProductCategoryTrendSnapshot = {
  reportDate: string;
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
};

export type ProductCategoryContributionViewTotals = {
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
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

function toneNameForValue(value: DecimalLike | null | undefined): ProductCategoryDerivedAnalysisTone {
  const parsed = decimalNumber(value);
  if (parsed === null || parsed === 0) {
    return "neutral";
  }
  return parsed > 0 ? "positive" : "negative";
}

function rateLabel(value: DecimalLike | null | undefined): string {
  const parsed = decimalNumber(value);
  if (parsed === null) {
    return "-";
  }
  return `${parsed.toFixed(2).replace(/\.?0+$/, "")}%`;
}

function signedYiDeltaLabel(current: DecimalLike | null | undefined, previous: DecimalLike | null | undefined): string {
  const currentNumber = decimalNumber(current);
  const previousNumber = decimalNumber(previous);
  if (currentNumber === null || previousNumber === null) {
    return "-";
  }
  const deltaYi = (currentNumber - previousNumber) / YUAN_PER_YI;
  if (deltaYi === 0) {
    return "0.00 亿元";
  }
  return `${deltaYi > 0 ? "+" : "-"}${Math.abs(deltaYi).toFixed(2)} 亿元`;
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
  snapshots.slice().reverse().forEach((snapshot) => {
    const point = project(snapshot);
    if (point === null) {
      return;
    }
    labels.push(formatProductCategoryReportMonthLabel(snapshot.reportDate));
    points.push(point);
  });
  return { labels, points };
}

function firstPriorRow(
  snapshots: ProductCategoryTrendSnapshot[],
  categoryId: string,
): ProductCategoryPnlRow | undefined {
  for (const snapshot of snapshots.slice(1)) {
    const row = findProductCategoryRow(snapshot.rows, categoryId);
    if (row) {
      return row;
    }
  }
  return undefined;
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

function buildRowTrendAnalysisItem(input: {
  id: ProductCategoryDerivedAnalysisItem["id"];
  title: string;
  categoryId: string;
  snapshots: ProductCategoryTrendSnapshot[];
  metric: (row: ProductCategoryPnlRow) => string;
  detail: (row: ProductCategoryPnlRow, previousRow: ProductCategoryPnlRow | undefined) => string;
  point: (row: ProductCategoryPnlRow) => string;
}): ProductCategoryDerivedAnalysisItem | null {
  const currentSnapshot = input.snapshots[0];
  if (!currentSnapshot) {
    return null;
  }
  const currentRow = findProductCategoryRow(currentSnapshot.rows, input.categoryId);
  if (!currentRow) {
    return null;
  }
  const previousRow = firstPriorRow(input.snapshots, input.categoryId);
  return {
    id: input.id,
    title: input.title,
    metric: input.metric(currentRow),
    detail: input.detail(currentRow, previousRow),
    tone: toneNameForValue(currentRow.business_net_income),
    points: input.snapshots
      .flatMap((snapshot): ProductCategoryDerivedAnalysisPoint[] => {
        const row = findProductCategoryRow(snapshot.rows, input.categoryId);
        if (!row) {
          return [];
        }
        return [
          {
            label: formatProductCategoryReportMonthLabel(snapshot.reportDate),
            value: input.point(row),
            tone: toneNameForValue(row.business_net_income),
          },
        ];
      }),
  };
}

function buildSpreadLevelAnalysisItem(
  snapshots: ProductCategoryTrendSnapshot[],
): ProductCategoryDerivedAnalysisItem | null {
  const currentSnapshot = snapshots[0];
  if (!currentSnapshot) {
    return null;
  }
  const currentSpread = spreadBp(currentSnapshot);
  if (currentSpread === null) {
    return null;
  }
  const priorSnapshot = snapshots.slice(1).find((snapshot) => spreadBp(snapshot) !== null);
  const priorSpread = priorSnapshot ? spreadBp(priorSnapshot) : null;
  const delta = spreadDeltaBp(currentSpread, priorSpread);
  const assetYield = rateLabel(currentSnapshot.assetTotal?.weighted_yield);
  const liabilityYield = rateLabel(currentSnapshot.liabilityTotal?.weighted_yield);
  return {
    id: "spreadLevel",
    title: "利差水平分析",
    metric: `资产负债利差 ${bpLabel(currentSpread)}`,
    detail: `资产端加权收益率 ${assetYield} / 负债端加权收益率 ${liabilityYield}，较${priorSnapshot ? formatProductCategoryReportMonthLabel(priorSnapshot.reportDate) : "上期"} ${signedBpLabel(delta)}。`,
    tone: currentSpread > 0 ? "positive" : currentSpread < 0 ? "negative" : "neutral",
    points: snapshots
      .flatMap((snapshot): ProductCategoryDerivedAnalysisPoint[] => {
        const value = spreadBp(snapshot);
        if (value === null) {
          return [];
        }
        return [
          {
            label: formatProductCategoryReportMonthLabel(snapshot.reportDate),
            value: bpLabel(value),
            detail: `资产 ${rateLabel(snapshot.assetTotal?.weighted_yield)} / 负债 ${rateLabel(snapshot.liabilityTotal?.weighted_yield)}`,
            tone: value > 0 ? "positive" : value < 0 ? "negative" : "neutral",
          },
        ];
      }),
  };
}

function maxByAbsoluteValue(
  rows: ProductCategoryPnlRow[],
  selector: (row: ProductCategoryPnlRow) => DecimalLike | null | undefined,
): ProductCategoryPnlRow | null {
  let selected: ProductCategoryPnlRow | null = null;
  let selectedAbs = -1;
  rows.forEach((row) => {
    const parsed = decimalNumber(selector(row));
    if (parsed === null) {
      return;
    }
    const abs = Math.abs(parsed);
    if (abs > selectedAbs) {
      selected = row;
      selectedAbs = abs;
    }
  });
  return selected;
}

export function buildProductCategoryDerivedAnalysisPlan(input: {
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  currentRate?: DecimalLike | null;
  baselineRate?: DecimalLike | null;
  trendSnapshots?: ProductCategoryTrendSnapshot[];
  contributionViews?: {
    monthly?: ProductCategoryContributionViewTotals;
    ytd?: ProductCategoryContributionViewTotals;
  };
}): ProductCategoryDerivedAnalysisItem[] {
  const productRows = input.rows.filter((row) => !row.is_total && row.category_id !== "grand_total");
  const topIncomeRow = maxByAbsoluteValue(productRows, (row) => row.business_net_income);
  const largestScaleRow = maxByAbsoluteValue(productRows, (row) => row.cnx_scale);
  const negativeRows = productRows.filter((row) => {
    const income = decimalNumber(row.business_net_income);
    return income !== null && income < 0;
  });
  const trendSnapshots = input.trendSnapshots?.length
    ? input.trendSnapshots
    : [
        {
          reportDate: input.grandTotal?.report_date ?? input.assetTotal?.report_date ?? "",
          rows: input.rows,
          assetTotal: input.assetTotal,
          liabilityTotal: input.liabilityTotal,
          grandTotal: input.grandTotal,
        },
      ].filter((snapshot) => snapshot.reportDate);

  const items: ProductCategoryDerivedAnalysisItem[] = [];
  const monthlyContribution = input.contributionViews?.monthly;
  const ytdContribution = input.contributionViews?.ytd;

  if (input.grandTotal || input.assetTotal || input.liabilityTotal) {
    const hasMonthlyOrYtdContribution =
      monthlyContribution?.grandTotal || monthlyContribution?.assetTotal || ytdContribution?.grandTotal || ytdContribution?.assetTotal;
    items.push({
      id: "contribution",
      title: "经营贡献拆解",
      metric: hasMonthlyOrYtdContribution
        ? `月度损益 ${formatProductCategoryValue(monthlyContribution?.grandTotal?.business_net_income)} 亿元 / 累计损益 ${formatProductCategoryValue(ytdContribution?.grandTotal?.business_net_income)} 亿元`
        : `总收益 ${formatProductCategoryValue(input.grandTotal?.business_net_income)} 亿元`,
      detail: hasMonthlyOrYtdContribution
        ? `月度：资产端 ${formatProductCategoryValue(monthlyContribution?.assetTotal?.business_net_income)} 亿元 / 负债端 ${formatProductCategoryValue(monthlyContribution?.liabilityTotal?.business_net_income)} 亿元；累计：资产端 ${formatProductCategoryValue(ytdContribution?.assetTotal?.business_net_income)} 亿元 / 负债端 ${formatProductCategoryValue(ytdContribution?.liabilityTotal?.business_net_income)} 亿元。`
        : `资产端 ${formatProductCategoryValue(input.assetTotal?.business_net_income)} 亿元 / 负债端 ${formatProductCategoryValue(input.liabilityTotal?.business_net_income)} 亿元，先用总计行确认收益来源。`,
      tone: toneNameForValue(input.grandTotal?.business_net_income),
    });
  }

  const interestEarningTrend = buildRowTrendAnalysisItem({
    id: "interestEarningTrend",
    title: "生息资产走势分析",
    categoryId: "interest_earning_assets",
    snapshots: trendSnapshots,
    metric: (row) =>
      `日均 ${formatProductCategoryRowDisplayValue(row, row.cnx_scale)} 亿元 / 净收入 ${formatProductCategoryRowDisplayValue(row, row.business_net_income)} 亿元`,
    detail: (row, previousRow) =>
      `较${previousRow ? formatProductCategoryReportMonthLabel(previousRow.report_date) : "上期"}日均 ${signedYiDeltaLabel(row.cnx_scale, previousRow?.cnx_scale)}；加权收益率 ${formatProductCategoryYieldValue(row.weighted_yield)}%。`,
    point: (row) =>
      `${formatProductCategoryRowDisplayValue(row, row.cnx_scale)}亿 · 收益率 ${formatProductCategoryYieldValue(row.weighted_yield)}%`,
  });
  if (interestEarningTrend) {
    items.push(interestEarningTrend);
  }

  const spreadLevel = buildSpreadLevelAnalysisItem(trendSnapshots);
  if (spreadLevel) {
    items.push(spreadLevel);
  }

  const interbankTrend = buildRowTrendAnalysisItem({
    id: "interbankLendingTrend",
    title: "拆放同业走势分析",
    categoryId: "interbank_lending_assets",
    snapshots: trendSnapshots,
    metric: (row) =>
      `日均 ${formatProductCategoryRowDisplayValue(row, row.cnx_scale)} 亿元 / 营业净收入 ${formatProductCategoryRowDisplayValue(row, row.business_net_income)} 亿元`,
    detail: (row, previousRow) =>
      `较${previousRow ? formatProductCategoryReportMonthLabel(previousRow.report_date) : "上期"}日均 ${signedYiDeltaLabel(row.cnx_scale, previousRow?.cnx_scale)}；人民币日均 ${formatProductCategoryRowDisplayValue(row, row.cny_scale)} 亿元，外币日均 ${formatProductCategoryRowDisplayValue(row, row.foreign_scale)} 亿元。`,
    point: (row) =>
      `${formatProductCategoryRowDisplayValue(row, row.cnx_scale)}亿 · 净收入 ${formatProductCategoryRowDisplayValue(row, row.business_net_income)}亿`,
  });
  if (interbankTrend) {
    items.push(interbankTrend);
  }

  const tplTrend = buildRowTrendAnalysisItem({
    id: "tplAssetTrend",
    title: "TPL资产规模/收益率走势",
    categoryId: "bond_tpl",
    snapshots: trendSnapshots,
    metric: (row) =>
      `日均 ${formatProductCategoryRowDisplayValue(row, row.cnx_scale)} 亿元 / 收益率 ${formatProductCategoryYieldValue(row.weighted_yield)}%`,
    detail: (row, previousRow) =>
      `较${previousRow ? formatProductCategoryReportMonthLabel(previousRow.report_date) : "上期"}日均 ${signedYiDeltaLabel(row.cnx_scale, previousRow?.cnx_scale)}；经营净收入 ${formatProductCategoryRowDisplayValue(row, row.business_net_income)} 亿元。`,
    point: (row) =>
      `${formatProductCategoryRowDisplayValue(row, row.cnx_scale)}亿 · 收益率 ${formatProductCategoryYieldValue(row.weighted_yield)}%`,
  });
  if (tplTrend) {
    items.push(tplTrend);
  }

  if (topIncomeRow) {
    items.push({
      id: "driver",
      title: "主驱动产品行",
      metric: `${topIncomeRow.category_name} ${formatProductCategoryRowDisplayValue(topIncomeRow, topIncomeRow.business_net_income)} 亿元`,
      detail: "按经营净收入绝对值定位首要驱动，再展开人民币净收入、外币净收入和FTP拆分。",
      tone: toneNameForValue(topIncomeRow.business_net_income),
    });
  }

  items.push({
    id: "ftp",
    title: "FTP情景敏感性",
    metric: `当前 ${rateLabel(input.currentRate)} / 基准 ${rateLabel(input.baselineRate)}`,
    detail: "围绕 2.0%、1.75%、1.6%、1.5% 四档FTP复看总收益、营业净收入和加权收益率变化。",
    tone: "neutral",
  });

  if (largestScaleRow || productRows.length > 0) {
    const reviewNames = negativeRows.slice(0, 3).map((row) => row.category_name).join("、") || "暂无负收益产品行";
    items.push({
      id: "review",
      title: "规模与异常复核",
      metric: largestScaleRow
        ? `${largestScaleRow.category_name} 日均 ${formatProductCategoryRowDisplayValue(largestScaleRow, largestScaleRow.cnx_scale)} 亿元`
        : `负收益 ${negativeRows.length} 行`,
      detail: `最大日均规模与负收益行联动复核；当前负收益 ${negativeRows.length} 行：${reviewNames}。`,
      tone: negativeRows.length > 0 ? "negative" : "neutral",
    });
  }

  return items;
}

export function selectProductCategoryTrendReportDates(
  selectedDate: string,
  reportDates: string[] | undefined,
  limit = 4,
): string[] {
  if (!selectedDate) {
    return [];
  }
  const dates = reportDates?.length ? reportDates : [selectedDate];
  const selectedIndex = dates.indexOf(selectedDate);
  const ordered = selectedIndex >= 0
    ? dates.slice(selectedIndex)
    : [selectedDate, ...dates.filter((date) => date !== selectedDate)];
  return Array.from(new Set(ordered)).slice(0, limit);
}

export function buildProductCategoryTrendSnapshot(
  payload: ProductCategoryPnlPayload,
): ProductCategoryTrendSnapshot {
  return {
    reportDate: payload.report_date,
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
  "归属日期：无独立外显字段（显式合同缺口；勿用本页报告日或生成时间代替）。 ";

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
