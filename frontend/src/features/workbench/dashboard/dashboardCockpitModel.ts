import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  ChoiceMacroLatestPoint,
  CoreMetricsResult,
  DailyChangesResult,
  Numeric,
  PnlByBusinessAnalysisRow,
  ResearchCalendarEvent,
} from "../../../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";

export type DashboardCockpitSectionStatus =
  | "landed"
  | "supplemental"
  | "stale"
  | "blocked"
  | "reserved"
  | "demo";

export type DashboardCockpitTone = "positive" | "negative" | "neutral" | "warning";

export type DashboardCockpitSection = {
  id: string;
  label: string;
  status: DashboardCockpitSectionStatus;
  firstScreenAllowed: boolean;
  reason: string;
};

export type DashboardCockpitTickerItem = {
  id: string;
  label: string;
  value: string;
  delta: string;
  unitLabel: string;
  tradeDate: string;
  status: Extract<DashboardCockpitSectionStatus, "landed" | "stale" | "blocked">;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitMetricItem = {
  id: string;
  label: string;
  value: string;
  delta?: string;
  hint: string;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitPreviewSignal = {
  id: string;
  label: string;
  value: string;
  detail: string;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitAnalysisCard = {
  id: string;
  title: string;
  statusLabel: string;
  detail: string;
  primaryLabel: string;
  primaryValue: string;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitWaterfallItem = {
  id: string;
  label: string;
  value: string;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitPortfolioItem = {
  id: string;
  label: string;
  value: string;
  marketValue: string;
  duration: string;
  detail: string;
  status: DashboardCockpitSectionStatus;
};

export type DashboardCockpitRiskItem = {
  id: string;
  label: string;
  value: string;
  hint: string;
  level: number;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitCalendarItem = {
  id: string;
  time: string;
  title: string;
  detail: string;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitWatchRow = {
  id: string;
  code: string;
  name: string;
  maturity: string;
  yieldValue: string;
  dailyChange: string;
  rating: string;
  reason: string;
  route: string;
  actionLabel: string;
  status: DashboardCockpitSectionStatus;
};

export type DashboardCockpitAccountRow = {
  id: string;
  accountName: string;
  segment: string;
  exposure: string;
  weight: string;
  duration: string;
  ytm: string;
  dailyChange: string;
  risk: string;
  source: string;
  route: string;
  actionLabel: string;
  status: DashboardCockpitSectionStatus;
  tone: DashboardCockpitTone;
};

export type DashboardCockpitModel = {
  reportDate: string;
  sections: DashboardCockpitSection[];
  firstScreenSections: DashboardCockpitSection[];
  marketTicker: DashboardCockpitTickerItem[];
  previewSignals: DashboardCockpitPreviewSignal[];
  metricRail: DashboardCockpitMetricItem[];
  analysisCards: DashboardCockpitAnalysisCard[];
  waterfall: DashboardCockpitWaterfallItem[];
  portfolioMix: DashboardCockpitPortfolioItem[];
  riskItems: DashboardCockpitRiskItem[];
  calendarItems: DashboardCockpitCalendarItem[];
  watchRows: DashboardCockpitWatchRow[];
  accountRows: DashboardCockpitAccountRow[];
};

export type DashboardCockpitModelInput = {
  reportDate: string;
  snapshotMode?: string | null;
  isMockMode: boolean;
  coreMetrics?: CoreMetricsResult | null;
  dailyChanges?: DailyChangesResult | null;
  bondHeadline?: BondDashboardHeadlinePayload | null;
  portfolio?: BondPortfolioHeadlinesPayload | null;
  bondBucketRows?: readonly PnlByBusinessAnalysisRow[] | null;
  marketPoints?: readonly ChoiceMacroLatestPoint[] | null;
  calendarItems?: readonly ResearchCalendarEvent[] | null;
};

type NumericLike = Numeric | string | number | null | undefined;

const MARKET_TICKER_PRIORITY: ReadonlyArray<{
  ids: readonly string[];
  label: string;
}> = [
  { ids: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"], label: "10年国债" },
  { ids: ["EMM00166458"], label: "1年国债" },
  { ids: ["CA.DR007", "M002", "EMM00167613"], label: "DR007" },
  { ids: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"], label: "美债10Y" },
  { ids: ["CA.USDCNY", "EMM00058124"], label: "美元/人民币" },
  { ids: ["CA.BRENT"], label: "原油(Brent)" },
  { ids: ["CA.CSI300"], label: "沪深300" },
  { ids: ["CA.CSI300_PCT_CHG"], label: "沪深300涨跌幅" },
  { ids: ["CN_CREDIT_AAA_1Y", "S0059650", "EMM00166655"], label: "中短票AAA 1Y" },
  { ids: ["CN_CREDIT_AAA_3Y", "S0059651", "EMM00166657"], label: "中短票AAA 3Y" },
  { ids: ["CN_CREDIT_AAA_5Y", "S0059652", "EMM00166659"], label: "中短票AAA 5Y" },
];

const EMPTY_DISPLAY = "--";

const ASSET_CLASS_LABELS: Record<string, string> = {
  credit: "信用债",
  rate: "利率债",
  other: "其他",
};

const ASSET_CLASS_ACCOUNT_ORDER: Record<string, number> = {
  credit: 1,
  rate: 2,
  other: 3,
};

const BOND_BUCKET_LABELS: Record<string, readonly string[]> = {
  credit: ["信用债"],
  rate: ["利率债"],
  other: ["金融债", "其它债券", "其他债券"],
};

function cleanDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const expectedDate = cleanDate(expected);
  const actualDate = cleanDate(actual);
  return expectedDate.length > 0 && actualDate.length > 0 && expectedDate === actualDate;
}

function numericObject(value: NumericLike): Numeric | null {
  if (value == null || typeof value === "string" || typeof value === "number") {
    return null;
  }
  return value;
}

function numericRaw(value: NumericLike): number | null {
  if (value == null) {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  const raw = value.raw;
  if (raw == null) {
    return null;
  }
  const parsed = typeof raw === "number" ? raw : Number(String(raw).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function formattedDisplay(value: NumericLike): string | null {
  const display = numericObject(value)?.display?.trim();
  return display && display.length > 0 ? display : null;
}

function formatWithCommas(value: number, digits: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatCompactNumber(value: number, digits = 2): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function numericDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : formatWithCommas(raw, Math.abs(raw) >= 100 ? 0 : 2);
}

function yuanYiDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : `${formatWithCommas(raw / 100_000_000, 2)} 亿`;
}

function percentDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : `${formatWithCommas(raw * 100, 2)}%`;
}

function bpDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  if (raw == null) return fallback;
  const bp = raw * 10_000;
  return `${formatWithCommas(bp, Math.abs(bp) >= 100 ? 0 : 1)}bp`;
}

function durationDisplay(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const display = formattedDisplay(value);
  if (display) return display;
  const raw = numericRaw(value);
  return raw == null ? fallback : formatWithCommas(raw, 2);
}

function percentPointDisplay(value: string | number | null | undefined, fallback = EMPTY_DISPLAY): string {
  const raw = numericRaw(value);
  return raw == null ? fallback : `${formatWithCommas(raw, 2)}%`;
}

function dv01Display(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const raw = numericRaw(value);
  if (raw != null) {
    return `${formatWithCommas(raw / 10_000, 2)} 万`;
  }
  const display = formattedDisplay(value);
  return display ?? fallback;
}

function previewDv01Display(value: NumericLike, fallback = EMPTY_DISPLAY): string {
  const raw = numericRaw(value);
  if (raw != null) {
    return `${formatWithCommas(raw / 10_000, 2)} \u4e07`;
  }
  return dv01Display(value, fallback);
}

function hasNumericValue(value: NumericLike): boolean {
  return numericRaw(value) !== null || formattedDisplay(value) !== null;
}

function buildRiskFocusReasonParts(input: {
  issuerTop5Weight: NumericLike;
  creditWeight: NumericLike;
  totalDv01: NumericLike;
}) {
  const previewParts: string[] = [];
  const sourceParts: string[] = [];

  if (hasNumericValue(input.issuerTop5Weight)) {
    const top5 = percentDisplay(input.issuerTop5Weight);
    previewParts.push(`Top5 ${top5}`);
    sourceParts.push(`Top5集中度 ${top5}`);
  }

  if (hasNumericValue(input.creditWeight)) {
    const credit = percentDisplay(input.creditWeight);
    previewParts.push(`信用 ${credit}`);
    sourceParts.push(`信用占比 ${credit}`);
  }

  if (hasNumericValue(input.totalDv01)) {
    sourceParts.push(`DV01 ${previewDv01Display(input.totalDv01)}`);
  }

  return {
    preview: previewParts.length > 0 ? `因 ${previewParts.join(" / ")}` : null,
    source: sourceParts.length > 0 ? `因 ${sourceParts.join("、")}，进入联合复核。` : null,
  };
}

function buildBondBucketYieldDisplayMap(rows: readonly PnlByBusinessAnalysisRow[] | null | undefined) {
  const normalizedRows = rows ?? [];
  const result: Partial<Record<string, string>> = {};

  const rowByLabel = new Map(normalizedRows.map((row) => [row.dimension_label.trim(), row]));

  for (const assetClass of ["credit", "rate"] as const) {
    const labels = BOND_BUCKET_LABELS[assetClass];
    const match = labels
      .map((label) => rowByLabel.get(label))
      .find((row): row is PnlByBusinessAnalysisRow => Boolean(row));
    if (match) {
      result[assetClass] = percentPointDisplay(match.annualized_yield_pct);
    }
  }

  const otherRows = BOND_BUCKET_LABELS.other
    .map((label) => rowByLabel.get(label))
    .filter((row): row is PnlByBusinessAnalysisRow => Boolean(row));
  if (otherRows.length > 0) {
    let weightedYield = 0;
    let totalAvgBalance = 0;
    for (const row of otherRows) {
      const yieldPct = numericRaw(row.annualized_yield_pct);
      const avgBalance = numericRaw(row.avg_balance);
      if (yieldPct == null || avgBalance == null || avgBalance <= 0) {
        continue;
      }
      weightedYield += yieldPct * avgBalance;
      totalAvgBalance += avgBalance;
    }
    if (totalAvgBalance > 0) {
      result.other = `${formatWithCommas(weightedYield / totalAvgBalance, 2)}%`;
    } else {
      result.other = percentPointDisplay(otherRows[0]?.annualized_yield_pct);
    }
  }

  return result;
}

function numericTone(value: NumericLike): DashboardCockpitTone {
  const raw = numericRaw(value);
  if (raw == null || Number.isNaN(raw)) {
    return "neutral";
  }
  if (raw > 0) {
    return "positive";
  }
  if (raw < 0) {
    return "negative";
  }
  return "neutral";
}

function changeTone(value: number | null | undefined): DashboardCockpitTone {
  if (value == null || Number.isNaN(value)) {
    return "neutral";
  }
  if (value > 0) {
    return "positive";
  }
  if (value < 0) {
    return "negative";
  }
  return "neutral";
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function scaledLevel(value: NumericLike, maxRaw: number): number {
  const raw = numericRaw(value);
  if (raw == null || maxRaw <= 0) return 0;
  return clampPercent((Math.abs(raw) / maxRaw) * 100);
}

function percentLevel(value: NumericLike): number {
  const raw = numericRaw(value);
  if (raw == null) return 0;
  return clampPercent(Math.abs(raw) <= 1 ? Math.abs(raw) * 100 : Math.abs(raw));
}

function buildSupplementalSection(input: {
  id: string;
  label: string;
  reportDate: string;
  actualReportDate?: string | null;
  hasData: boolean;
}): DashboardCockpitSection {
  if (!input.hasData) {
    return {
      id: input.id,
      label: input.label,
      status: "blocked",
      firstScreenAllowed: false,
      reason: "补充读面尚未返回，不能进入首屏结论。",
    };
  }

  if (!isSameReportDate(input.reportDate, input.actualReportDate)) {
    return {
      id: input.id,
      label: input.label,
      status: "blocked",
      firstScreenAllowed: false,
      reason: `补充读面报告日 ${input.actualReportDate || "未知"} 与首页快照 ${input.reportDate || "未知"} 不一致。`,
    };
  }

  return {
    id: input.id,
    label: input.label,
    status: "supplemental",
    firstScreenAllowed: true,
    reason: "同报告日补充读面，可进入首屏但不替代首页快照。",
  };
}

function reservedSection(id: string, label: string): DashboardCockpitSection {
  return {
    id,
    label,
    status: "reserved",
    firstScreenAllowed: false,
    reason: "该读面仍为 reserved/live 候选，不进入首屏判断。",
  };
}

function labelForMarketPoint(point: ChoiceMacroLatestPoint): string {
  const configured = MARKET_TICKER_PRIORITY.find((item) => item.ids.includes(point.series_id));
  return configured?.label ?? point.series_name ?? point.series_id;
}

function findDayChange(
  dailyChanges: DailyChangesResult | null | undefined,
  reportDate: string,
) {
  if (!isSameReportDate(reportDate, dailyChanges?.report_date)) {
    return null;
  }
  return dailyChanges?.periods.find((period) => period.period === "day") ?? null;
}

function cleanMarketUnit(unit: string | null | undefined): string {
  const cleanUnit = unit?.trim() ?? "";
  return cleanUnit && cleanUnit.toLowerCase() !== "unknown" ? cleanUnit : "";
}

function isInlineMarketUnit(unit: string): boolean {
  return unit === "%" || unit.toLowerCase() === "bp";
}

function marketUnitLabel(point: ChoiceMacroLatestPoint): string {
  const unit = cleanMarketUnit(point.unit);
  if (unit.toLowerCase() === "index") return "指数";
  return unit && !isInlineMarketUnit(unit) ? unit : "";
}

function formatMarketTickerValue(point: ChoiceMacroLatestPoint): string {
  const unit = cleanMarketUnit(point.unit);
  if (!unit || isInlineMarketUnit(unit)) {
    return formatChoiceMacroValue(point, { spaceBeforeUnit: false, emptyDisplay: EMPTY_DISPLAY });
  }
  return formatCompactNumber(point.value_numeric);
}

function formatMarketTickerDelta(point: ChoiceMacroLatestPoint): string {
  const unit = cleanMarketUnit(point.unit);
  if (point.latest_change == null) {
    return EMPTY_DISPLAY;
  }
  if (!unit || isInlineMarketUnit(unit)) {
    return formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: EMPTY_DISPLAY });
  }
  const sign = point.latest_change > 0 ? "+" : "";
  return `${sign}${formatCompactNumber(point.latest_change)}`;
}

function pickMarketPoints(points: readonly ChoiceMacroLatestPoint[]): ChoiceMacroLatestPoint[] {
  const candidates = points.filter((point) => (point.refresh_tier ?? "stable") !== "isolated");
  const selected: ChoiceMacroLatestPoint[] = [];
  const seen = new Set<string>();

  for (const item of MARKET_TICKER_PRIORITY) {
    const match = item.ids
      .map((id) => candidates.find((point) => point.series_id === id))
      .find((point): point is ChoiceMacroLatestPoint => Boolean(point));
    if (match && !seen.has(match.series_id)) {
      selected.push(match);
      seen.add(match.series_id);
    }
  }

  for (const point of candidates) {
    if (seen.has(point.series_id)) {
      continue;
    }
    selected.push(point);
    seen.add(point.series_id);
    if (selected.length >= MARKET_TICKER_PRIORITY.length) {
      break;
    }
  }

  return selected.slice(0, MARKET_TICKER_PRIORITY.length);
}

function buildMarketTicker(
  points: readonly ChoiceMacroLatestPoint[] | null | undefined,
  reportDate: string,
): DashboardCockpitTickerItem[] {
  return pickMarketPoints(points ?? []).map((point) => {
    const sameTradeDate = isSameReportDate(reportDate, point.trade_date);
    return {
      id: point.series_id,
      label: labelForMarketPoint(point),
      value: formatMarketTickerValue(point),
      delta: formatMarketTickerDelta(point),
      unitLabel: marketUnitLabel(point),
      tradeDate: point.trade_date,
      status: sameTradeDate ? "landed" : "stale",
      tone: changeTone(point.latest_change),
    };
  });
}

function buildMetricRail(input: DashboardCockpitModelInput): DashboardCockpitMetricItem[] {
  const reportDate = input.reportDate;
  const headlineAllowed = isSameReportDate(reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(reportDate, input.portfolio?.report_date);
  const coreAllowed = isSameReportDate(reportDate, input.coreMetrics?.report_date);
  const changesAllowed = isSameReportDate(reportDate, input.dailyChanges?.report_date);
  const headline = headlineAllowed ? input.bondHeadline : null;
  const portfolio = portfolioAllowed ? input.portfolio : null;
  const core = coreAllowed ? input.coreMetrics : null;
  const dayChange = changesAllowed
    ? input.dailyChanges?.periods.find((period) => period.period === "day") ?? null
    : null;

  return [
    {
      id: "duration",
      label: "久期(年)",
      value: durationDisplay(headline?.kpis.weighted_duration ?? portfolio?.weighted_duration),
      delta: headline?.prev_report_date ? `较 ${headline.prev_report_date}` : "同日读面",
      hint: "债券组合口径",
      status: headlineAllowed || portfolioAllowed ? "supplemental" : "blocked",
      tone: "neutral",
    },
    {
      id: "ytm",
      label: "组合到期收益率",
      value: percentDisplay(headline?.kpis.weighted_ytm ?? portfolio?.weighted_ytm),
      delta: "同报告日",
      hint: "同日报告口径",
      status: headlineAllowed || portfolioAllowed ? "supplemental" : "blocked",
      tone: "positive",
    },
    {
      id: "credit-spread",
      label: "信用利差(BP)",
      value: bpDisplay(headline?.kpis.credit_spread_median),
      delta: "同报告日",
      hint: "同日报告口径",
      status: headlineAllowed ? "supplemental" : "blocked",
      tone: "warning",
    },
    {
      id: "dv01",
      label: "组合DV01",
      value: dv01Display(headline?.kpis.total_dv01 ?? portfolio?.total_dv01),
      delta: "元/1bp",
      hint: "组合风险口径",
      status: headlineAllowed || portfolioAllowed ? "supplemental" : "blocked",
      tone: "neutral",
    },
    {
      id: "coupon",
      label: "票息/Carry",
      value: percentDisplay(headline?.kpis.weighted_coupon ?? portfolio?.weighted_coupon),
      delta: "近似 carry",
      hint: "票息上下文",
      status: headlineAllowed || portfolioAllowed ? "supplemental" : "blocked",
      tone: "neutral",
    },
    {
      id: "daily-net",
      label: "日净变动",
      value: numericDisplay(dayChange?.net_change),
      delta: "债券/同业合计",
      hint: "日变动口径",
      status: changesAllowed ? "supplemental" : "blocked",
      tone: numericTone(dayChange?.net_change),
    },
    {
      id: "total-market-value",
      label: "组合市值",
      value: yuanYiDisplay(
        headline?.kpis.total_market_value ?? portfolio?.total_market_value ?? core?.bond_investments.total_amount,
      ),
      delta: core ? "含规模读面" : "债券读面",
      hint: "规模口径",
      status: headlineAllowed || portfolioAllowed || coreAllowed ? "supplemental" : "blocked",
      tone: "neutral",
    },
  ];
}

function buildPreviewSignals(
  input: DashboardCockpitModelInput,
  marketTicker: readonly DashboardCockpitTickerItem[],
): DashboardCockpitPreviewSignal[] {
  const reportDate = input.reportDate;
  const coreAllowed = isSameReportDate(reportDate, input.coreMetrics?.report_date);
  const changesAllowed = isSameReportDate(reportDate, input.dailyChanges?.report_date);
  const headlineAllowed = isSameReportDate(reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(reportDate, input.portfolio?.report_date);
  const sameDayCount = [coreAllowed, changesAllowed, headlineAllowed, portfolioAllowed].filter(Boolean).length;
  const marketLabel =
    marketTicker.length === 0
      ? "\u5f85\u63a5\u5165"
      : marketTicker.every((item) => item.status === "landed")
        ? "\u540c\u65e5"
        : "\u6700\u8fd1\u4ea4\u6613\u65e5";
  const coverageStatus: DashboardCockpitSectionStatus =
    sameDayCount === 4 ? "supplemental" : sameDayCount === 0 ? "blocked" : "stale";
  const coverageTone: DashboardCockpitTone = sameDayCount === 4 ? "positive" : "warning";

  const dayChange = findDayChange(input.dailyChanges, reportDate);
  const dayDrivers = dayChange
    ? [
        { label: "\u503a\u5238\u6295\u8d44", value: dayChange.bond_investments_change },
        { label: "\u540c\u4e1a\u8d44\u4ea7", value: dayChange.interbank_assets_change },
        { label: "\u540c\u4e1a\u8d1f\u503a", value: dayChange.interbank_liabilities_change },
      ]
        .map((driver) => ({
          ...driver,
          raw: Math.abs(numericRaw(driver.value) ?? -1),
          display: numericDisplay(driver.value),
        }))
        .filter((driver) => driver.raw >= 0)
        .sort((left, right) => right.raw - left.raw)
    : [];
  const topDayDriver = dayDrivers[0] ?? null;
  const secondaryDayDriver = dayDrivers[1] ?? null;

  const concentrationValue = portfolioAllowed
    ? percentDisplay(input.portfolio?.issuer_top5_weight)
    : EMPTY_DISPLAY;
  const riskFocusReasons = buildRiskFocusReasonParts({
    issuerTop5Weight: input.portfolio?.issuer_top5_weight,
    creditWeight: input.portfolio?.credit_weight,
    totalDv01: input.portfolio?.total_dv01,
  });
  const concentrationDetail = portfolioAllowed
    ? riskFocusReasons.preview ?? `\u4fe1\u7528\u5360\u6bd4 ${percentDisplay(input.portfolio?.credit_weight)}`
    : "\u7b49\u5f85\u540c\u65e5\u62a5\u544a\u65e5\u7ec4\u5408\u7ed3\u6784";

  const durationRiskValue =
    input.bondHeadline?.kpis.total_dv01 ?? input.portfolio?.total_dv01;
  const durationRiskDuration =
    input.bondHeadline?.kpis.weighted_duration ?? input.portfolio?.weighted_duration;
  const durationRiskAllowed =
    (headlineAllowed || portfolioAllowed) &&
    (hasNumericValue(durationRiskValue) || hasNumericValue(durationRiskDuration));

  return [
    {
      id: "coverage",
      label: "\u8865\u5145\u8986\u76d6",
      value: `${sameDayCount}/4`,
      detail: `\u8865\u5145\u8bfb\u9762 / \u5e02\u573a ${marketLabel} / \u5feb\u7167 ${input.snapshotMode ?? "\u5f85\u5b9a"}`,
      status: coverageStatus,
      tone: coverageTone,
    },
    {
      id: "net-change",
      label: "\u65e5\u51c0\u53d8\u52a8",
      value: dayChange ? numericDisplay(dayChange.net_change) : EMPTY_DISPLAY,
      detail: topDayDriver
        ? secondaryDayDriver
          ? `\u4e3b ${topDayDriver.label} ${topDayDriver.display} / \u6b21 ${secondaryDayDriver.label} ${secondaryDayDriver.display}`
          : `\u4e3b ${topDayDriver.label} ${topDayDriver.display}`
        : "\u7b49\u5f85\u540c\u65e5\u62a5\u544a\u65e5\u53d8\u52a8\u8bfb\u9762",
      status: dayChange ? "supplemental" : "blocked",
      tone: dayChange ? numericTone(dayChange.net_change) : "warning",
    },
    {
      id: "concentration",
      label: "\u98ce\u9669\u96c6\u4e2d",
      value: concentrationValue,
      detail: concentrationDetail,
      status: portfolioAllowed ? "supplemental" : "blocked",
      tone: "warning",
    },
    {
      id: "duration-dv01",
      label: "\u5229\u7387\u98ce\u9669",
      value: durationRiskAllowed ? previewDv01Display(durationRiskValue) : EMPTY_DISPLAY,
      detail: durationRiskAllowed
        ? `\u4e45\u671f ${durationDisplay(durationRiskDuration)}`
        : "\u7b49\u5f85\u540c\u65e5\u62a5\u544a\u65e5\u98ce\u9669\u8bfb\u9762",
      status: durationRiskAllowed ? "supplemental" : "blocked",
      tone: durationRiskAllowed ? "neutral" : "warning",
    },
  ];
}

function findTicker(ticker: readonly DashboardCockpitTickerItem[], ids: readonly string[]) {
  return ticker.find((item) => ids.includes(item.id));
}

function statusLabel(status: DashboardCockpitSectionStatus): string {
  if (status === "supplemental") return "中性";
  if (status === "landed") return "已落地";
  if (status === "stale") return "最近交易日";
  if (status === "blocked") return "阻断";
  if (status === "reserved") return "待治理";
  return "演示";
}

function buildAnalysisCards(input: {
  ticker: readonly DashboardCockpitTickerItem[];
  bondHeadline?: BondDashboardHeadlinePayload | null;
  portfolio?: BondPortfolioHeadlinesPayload | null;
  reportDate: string;
}): DashboardCockpitAnalysisCard[] {
  const gov10y = findTicker(input.ticker, ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"]);
  const dr007 = findTicker(input.ticker, ["CA.DR007", "M002", "EMM00167613"]);
  const spread = findTicker(input.ticker, ["CA.CN_US_SPREAD", "EM1"]);
  const headlineAllowed = isSameReportDate(input.reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(input.reportDate, input.portfolio?.report_date);

  return [
    {
      id: "rate",
      title: "利率判断",
      statusLabel: gov10y?.status === "stale" ? "最近交易日" : "中性偏谨慎",
      detail: gov10y
        ? `${gov10y.label} ${gov10y.value}，${gov10y.delta}。`
        : "缺少同源行情，利率方向不进入本日判断。",
      primaryLabel: "核心观点",
      primaryValue: gov10y ? "关注长端波动" : "待治理",
      status: gov10y?.status ?? "blocked",
      tone: gov10y?.tone ?? "warning",
    },
    {
      id: "curve",
      title: "曲线判断",
      statusLabel: spread?.status === "stale" ? "最近交易日" : "中性",
      detail: spread
        ? `曲线/利差上下文 ${spread.value}，${spread.delta}。`
        : "缺少曲线同源数据，保留为下钻观察。",
      primaryLabel: "核心观点",
      primaryValue: spread ? "关注曲线变化" : "待治理",
      status: spread?.status ?? "blocked",
      tone: spread?.tone ?? "neutral",
    },
    {
      id: "credit",
      title: "信用判断",
      statusLabel: headlineAllowed ? "可信" : "阻断",
      detail: headlineAllowed
        ? `信用利差中位数 ${bpDisplay(input.bondHeadline?.kpis.credit_spread_median)}。`
        : "债券 headline 报告日不一致或未返回。",
      primaryLabel: "核心观点",
      primaryValue: headlineAllowed ? "分层复核" : "不进结论",
      status: headlineAllowed ? "supplemental" : "blocked",
      tone: headlineAllowed ? "warning" : "warning",
    },
    {
      id: "funding",
      title: "资金判断",
      statusLabel: dr007?.status === "stale" ? "最近交易日" : "中性",
      detail: dr007
        ? `资金利率 ${dr007.value}，${dr007.delta}。`
        : "缺少资金行情，资金判断仅作为下钻入口。",
      primaryLabel: "核心观点",
      primaryValue: portfolioAllowed ? `DV01 ${dv01Display(input.portfolio?.total_dv01)}` : "待治理",
      status: dr007?.status ?? (portfolioAllowed ? "supplemental" : "blocked"),
      tone: dr007?.tone ?? "neutral",
    },
  ];
}

function buildWaterfall(input: {
  coreMetrics?: CoreMetricsResult | null;
  dailyChanges?: DailyChangesResult | null;
  reportDate: string;
}): DashboardCockpitWaterfallItem[] {
  const coreAllowed = isSameReportDate(input.reportDate, input.coreMetrics?.report_date);
  const changesAllowed = isSameReportDate(input.reportDate, input.dailyChanges?.report_date);
  const dayChange = changesAllowed
    ? input.dailyChanges?.periods.find((period) => period.period === "day") ?? null
    : null;

  return [
    {
      id: "starting-bond",
      label: "债券规模",
      value: numericDisplay(input.coreMetrics?.bond_investments.total_amount),
      status: coreAllowed ? "supplemental" : "blocked",
      tone: "neutral",
    },
    {
      id: "bond-change",
      label: "债券日变动",
      value: numericDisplay(dayChange?.bond_investments_change),
      status: changesAllowed ? "supplemental" : "blocked",
      tone: numericTone(dayChange?.bond_investments_change),
    },
    {
      id: "asset-change",
      label: "同业资产",
      value: numericDisplay(dayChange?.interbank_assets_change),
      status: changesAllowed ? "supplemental" : "blocked",
      tone: numericTone(dayChange?.interbank_assets_change),
    },
    {
      id: "liability-change",
      label: "同业负债",
      value: numericDisplay(dayChange?.interbank_liabilities_change),
      status: changesAllowed ? "supplemental" : "blocked",
      tone: numericTone(dayChange?.interbank_liabilities_change),
    },
    {
      id: "net-change",
      label: "净变动",
      value: numericDisplay(dayChange?.net_change),
      status: changesAllowed ? "supplemental" : "blocked",
      tone: numericTone(dayChange?.net_change),
    },
  ];
}

function buildPortfolioMix(
  portfolio: BondPortfolioHeadlinesPayload | null | undefined,
  reportDate: string,
): DashboardCockpitPortfolioItem[] {
  const allowed = isSameReportDate(reportDate, portfolio?.report_date);
  if (!allowed || !portfolio) {
    return [
      {
        id: "portfolio-blocked",
        label: "组合结构",
        value: EMPTY_DISPLAY,
        marketValue: EMPTY_DISPLAY,
        duration: EMPTY_DISPLAY,
        detail: "组合结构读面未返回同日报告日。",
        status: "blocked",
      },
    ];
  }

  const rows = portfolio.by_asset_class
    .filter((item) => hasNumericValue(item.weight) || hasNumericValue(item.market_value))
    .slice(0, 4)
    .map((item) => ({
      id: item.asset_class,
      label: ASSET_CLASS_LABELS[item.asset_class] ?? item.asset_class,
      value: percentDisplay(item.weight),
      marketValue: yuanYiDisplay(item.market_value),
      duration: durationDisplay(item.duration),
      detail: `${yuanYiDisplay(item.market_value)} / 久期 ${durationDisplay(item.duration)}`,
      status: "supplemental" as const,
    }));

  if (rows.length === 0) {
    return [
      {
        id: "portfolio-empty",
        label: "组合结构",
        value: EMPTY_DISPLAY,
        marketValue: EMPTY_DISPLAY,
        duration: EMPTY_DISPLAY,
        detail: "同日报告日已返回，但缺少可展示的资产分类数值。",
        status: "blocked",
      },
    ];
  }

  return rows;
}

export function buildRiskItems(
  portfolio: BondPortfolioHeadlinesPayload | null | undefined,
  reportDate: string,
): DashboardCockpitRiskItem[] {
  const allowed = isSameReportDate(reportDate, portfolio?.report_date);
  if (!allowed || !portfolio) {
    return [
      {
        id: "portfolio-risk-blocked",
        label: "风险摘要",
        value: EMPTY_DISPLAY,
        hint: "风险读面报告日不一致或未返回。",
        level: 0,
        status: "blocked",
        tone: "warning",
      },
    ];
  }

  const hasRiskValues = [
    portfolio.total_dv01,
    portfolio.weighted_duration,
    portfolio.issuer_top5_weight,
    portfolio.credit_weight,
  ].some(hasNumericValue);

  if (!hasRiskValues) {
    return [
      {
        id: "portfolio-risk-empty",
        label: "风险摘要",
        value: EMPTY_DISPLAY,
        hint: "同日报告日已返回，但风险字段缺少可展示数值。",
        level: 0,
        status: "blocked",
        tone: "warning",
      },
    ];
  }

  return [
    {
      id: "dv01",
      label: "DV01",
      value: dv01Display(portfolio.total_dv01),
      hint: "元/1bp",
      level: scaledLevel(portfolio.total_dv01, 150_000_000),
      status: "supplemental",
      tone: "neutral",
    },
    {
      id: "duration",
      label: "久期",
      value: durationDisplay(portfolio.weighted_duration),
      hint: "组合加权",
      level: scaledLevel(portfolio.weighted_duration, 7),
      status: "supplemental",
      tone: "neutral",
    },
    {
      id: "issuer-top5",
      label: "发行人Top5",
      value: percentDisplay(portfolio.issuer_top5_weight),
      hint: "集中度",
      level: percentLevel(portfolio.issuer_top5_weight),
      status: "supplemental",
      tone: "warning",
    },
    {
      id: "credit-weight",
      label: "信用占比",
      value: percentDisplay(portfolio.credit_weight),
      hint: "资产结构",
      level: percentLevel(portfolio.credit_weight),
      status: "supplemental",
      tone: "neutral",
    },
  ];
}

function buildCalendarItems(
  calendarItems: readonly ResearchCalendarEvent[] | null | undefined,
): DashboardCockpitCalendarItem[] {
  return (calendarItems ?? []).slice(0, 5).map((item) => ({
    id: item.id,
    time: item.date.length >= 10 ? item.date.slice(5, 10) : item.date,
    title: item.title,
    detail: [item.issuer, item.amount_label, item.note].filter(Boolean).join(" / "),
    tone: item.severity === "high" ? "warning" : "neutral",
  }));
}

function buildWatchRows(input: DashboardCockpitModelInput): DashboardCockpitWatchRow[] {
  const headlineAllowed = isSameReportDate(input.reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(input.reportDate, input.portfolio?.report_date);
  const changesAllowed = isSameReportDate(input.reportDate, input.dailyChanges?.report_date);
  const dayChange = changesAllowed
    ? input.dailyChanges?.periods.find((period) => period.period === "day") ?? null
    : null;
  if (!headlineAllowed && !portfolioAllowed) {
    return [
      {
        id: "watch-blocked",
        code: "--",
        name: "重点观察待治理",
        maturity: "--",
        yieldValue: EMPTY_DISPLAY,
        dailyChange: EMPTY_DISPLAY,
        rating: "--",
        reason: "缺少同日报告日债券组合读面。",
        route: "/platform-config",
        actionLabel: "治理字段",
        status: "blocked",
      },
    ];
  }

  return [
    {
      id: "portfolio-duration-watch",
      code: "久期",
      name: "组合久期",
      maturity: durationDisplay(input.bondHeadline?.kpis.weighted_duration ?? input.portfolio?.weighted_duration),
      yieldValue: percentDisplay(input.bondHeadline?.kpis.weighted_ytm ?? input.portfolio?.weighted_ytm),
      dailyChange: numericDisplay(dayChange?.net_change),
      rating: "组合",
      reason: "长端利率与久期共同复核。",
      route: "/bond-analysis",
      actionLabel: "看久期",
      status: "supplemental",
    },
    {
      id: "portfolio-credit-watch",
      code: "信用",
      name: "信用仓位",
      maturity: percentDisplay(input.portfolio?.credit_weight),
      yieldValue: bpDisplay(input.bondHeadline?.kpis.credit_spread_median),
      dailyChange: percentDisplay(input.portfolio?.issuer_top5_weight),
      rating: "信用",
      reason: "信用利差与集中度共同复核。",
      route: "/bond-analysis",
      actionLabel: "看信用",
      status: "supplemental",
    },
    {
      id: "portfolio-dv01-watch",
      code: "DV01",
      name: "DV01票息",
      maturity: dv01Display(input.bondHeadline?.kpis.total_dv01 ?? input.portfolio?.total_dv01),
      yieldValue: percentDisplay(input.bondHeadline?.kpis.weighted_coupon ?? input.portfolio?.weighted_coupon),
      dailyChange: numericDisplay(dayChange?.bond_investments_change),
      rating: "风险",
      reason: "DV01、票息与债券规模变动共同复核。",
      route: "/risk-tensor",
      actionLabel: "看风险",
      status: "supplemental",
    },
  ];
}

function buildAccountRows(input: DashboardCockpitModelInput): DashboardCockpitAccountRow[] {
  const headlineAllowed = isSameReportDate(input.reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(input.reportDate, input.portfolio?.report_date);
  const headline = headlineAllowed ? input.bondHeadline : null;
  const portfolio = portfolioAllowed ? input.portfolio : null;
  const dayChange = findDayChange(input.dailyChanges, input.reportDate);

  if (!portfolio) {
    return [
      {
        id: "account-blocked",
        accountName: "\u7ec4\u5408\u8bfb\u9762\u672a\u540c\u65e5",
        segment: "\u6cbb\u7406",
        exposure: EMPTY_DISPLAY,
        weight: EMPTY_DISPLAY,
        duration: EMPTY_DISPLAY,
        ytm: EMPTY_DISPLAY,
        dailyChange: EMPTY_DISPLAY,
        risk: EMPTY_DISPLAY,
        source: "\u7ec4\u5408\u7ed3\u6784\u8bfb\u9762\u672a\u8fd4\u56de\u540c\u65e5\u62a5\u544a\u65e5\u3002",
        route: "/platform-config",
        actionLabel: "\u6cbb\u7406\u5b57\u6bb5",
        status: "blocked",
        tone: "warning",
      },
    ];
  }

  const totalMarketValue = portfolio.total_market_value ?? headline?.kpis.total_market_value;
  const totalDv01 = headline?.kpis.total_dv01 ?? portfolio.total_dv01;
  const bondPortfolioChange = dayChange?.bond_investments_change ?? dayChange?.net_change;
  const bondBucketYieldDisplay = buildBondBucketYieldDisplayMap(input.bondBucketRows);
  const riskFocusReasons = buildRiskFocusReasonParts({
    issuerTop5Weight: portfolio.issuer_top5_weight,
    creditWeight: portfolio.credit_weight,
    totalDv01: portfolio.total_dv01,
  });

  const rows: DashboardCockpitAccountRow[] = [
    {
      id: "account-bond-portfolio",
      accountName: "\u503a\u5238\u7ec4\u5408",
      segment: "\u7ec4\u5408",
      exposure: yuanYiDisplay(totalMarketValue),
      weight: hasNumericValue(totalMarketValue) ? "100.00%" : EMPTY_DISPLAY,
      duration: durationDisplay(headline?.kpis.weighted_duration ?? portfolio.weighted_duration),
      ytm: percentDisplay(headline?.kpis.weighted_ytm ?? portfolio.weighted_ytm),
      dailyChange: numericDisplay(bondPortfolioChange),
      risk: `DV01 ${dv01Display(totalDv01)}`,
      source: "\u7ec4\u5408\u89c4\u6a21\u3001\u6536\u76ca\u7387\u3001\u4e45\u671f\u4e0e DV01 \u540c\u6b65\u590d\u6838\u3002",
      route: "/bond-analysis",
      actionLabel: "\u770b\u7ec4\u5408",
      status: "supplemental",
      tone: numericTone(bondPortfolioChange),
    },
  ];

  const assetRows = portfolio.by_asset_class
    .filter((item) => hasNumericValue(item.weight) || hasNumericValue(item.market_value))
    .slice()
    .sort((left, right) => {
      const leftOrder = ASSET_CLASS_ACCOUNT_ORDER[left.asset_class] ?? 99;
      const rightOrder = ASSET_CLASS_ACCOUNT_ORDER[right.asset_class] ?? 99;
      return leftOrder - rightOrder || left.asset_class.localeCompare(right.asset_class);
    })
    .slice(0, 3)
    .map((item): DashboardCockpitAccountRow => {
      const label = ASSET_CLASS_LABELS[item.asset_class] ?? item.asset_class;
      return {
        id: `account-${item.asset_class}`,
        accountName: label,
        segment: "\u8d44\u4ea7\u7c7b",
        exposure: yuanYiDisplay(item.market_value),
        weight: percentDisplay(item.weight),
        duration: durationDisplay(item.duration),
        ytm: bondBucketYieldDisplay[item.asset_class] ?? EMPTY_DISPLAY,
        dailyChange: EMPTY_DISPLAY,
        risk: `DV01 ${dv01Display(item.dv01)}`,
        source: `${label}\u8d44\u4ea7\u66b4\u9732\u4e0e\u4e45\u671f\u7ed3\u6784\u3002`,
        route: "/bond-analysis",
        actionLabel: "\u770b\u8d44\u4ea7",
        status: "supplemental",
        tone: "neutral",
      };
    });

  rows.push(...assetRows);

  if (hasNumericValue(portfolio.total_dv01) || hasNumericValue(portfolio.weighted_duration)) {
    rows.push({
      id: "account-risk-review",
      accountName: "\u98ce\u9669\u590d\u6838",
      segment: "\u98ce\u9669",
      exposure: yuanYiDisplay(totalMarketValue),
      weight: percentDisplay(portfolio.issuer_top5_weight),
      duration: durationDisplay(portfolio.weighted_duration),
      ytm: EMPTY_DISPLAY,
      dailyChange: EMPTY_DISPLAY,
      risk: `DV01 ${dv01Display(portfolio.total_dv01)}`,
      source: riskFocusReasons.source ?? "DV01 / \u4e45\u671f / \u96c6\u4e2d\u5ea6\u8054\u5408\u590d\u6838\u3002",
      route: "/risk-tensor",
      actionLabel: "\u770b\u98ce\u9669",
      status: "supplemental",
      tone: "warning",
    });
  }

  return rows;
}

export function buildDashboardCockpitModel(input: DashboardCockpitModelInput): DashboardCockpitModel {
  const reportDate = cleanDate(input.reportDate);
  const marketTicker = buildMarketTicker(input.marketPoints, reportDate);
  const previewSignals = buildPreviewSignals(input, marketTicker);
  const hasMarket = marketTicker.length > 0;
  const hasStaleMarket = marketTicker.some((item) => item.status === "stale");

  const sections: DashboardCockpitSection[] = [
    {
      id: "home_snapshot",
      label: "首页快照",
      status: input.isMockMode ? "demo" : "landed",
      firstScreenAllowed: !input.isMockMode,
      reason: input.isMockMode
        ? "当前为演示模式，仅用于界面演示。"
        : `主报告日 ${reportDate || "待定"}，模式 ${input.snapshotMode || "待确认"}。`,
    },
    {
      id: "market_context",
      label: "市场行情",
      status: hasMarket ? (hasStaleMarket ? "stale" : "landed") : "blocked",
      firstScreenAllowed: hasMarket,
      reason: hasStaleMarket
        ? "市场数据存在非同日交易日，只能作为最近交易日上下文。"
        : "市场数据按 trade_date 标注展示。",
    },
    buildSupplementalSection({
      id: "core_metrics",
      label: "债券/同业核心指标",
      reportDate,
      actualReportDate: input.coreMetrics?.report_date,
      hasData: Boolean(input.coreMetrics),
    }),
    buildSupplementalSection({
      id: "daily_changes",
      label: "日/周/月变动",
      reportDate,
      actualReportDate: input.dailyChanges?.report_date,
      hasData: Boolean(input.dailyChanges),
    }),
    buildSupplementalSection({
      id: "bond_headline",
      label: "债券 headline KPI",
      reportDate,
      actualReportDate: input.bondHeadline?.report_date,
      hasData: Boolean(input.bondHeadline),
    }),
    buildSupplementalSection({
      id: "portfolio_headline",
      label: "组合结构与风险摘要",
      reportDate,
      actualReportDate: input.portfolio?.report_date,
      hasData: Boolean(input.portfolio),
    }),
    {
      id: "calendar",
      label: "关键事件日历",
      status: input.calendarItems && input.calendarItems.length > 0 ? "supplemental" : "blocked",
      firstScreenAllowed: Boolean(input.calendarItems && input.calendarItems.length > 0),
      reason: "日历是上下文入口，不参与本日经营判断。",
    },
    reservedSection("executive_risk_overview", "reserved 风险总览"),
    reservedSection("executive_contribution", "reserved 贡献拆解"),
    reservedSection("executive_alerts", "reserved 告警"),
  ];

  const firstScreenSections = sections.filter(
    (section) =>
      section.firstScreenAllowed &&
      section.status !== "blocked" &&
      section.status !== "reserved" &&
      section.status !== "demo",
  );

  return {
    reportDate,
    sections,
    firstScreenSections,
    marketTicker,
    previewSignals,
    metricRail: buildMetricRail(input),
    analysisCards: buildAnalysisCards({
      ticker: marketTicker,
      bondHeadline: input.bondHeadline,
      portfolio: input.portfolio,
      reportDate,
    }),
    waterfall: buildWaterfall({
      coreMetrics: input.coreMetrics,
      dailyChanges: input.dailyChanges,
      reportDate,
    }),
    portfolioMix: buildPortfolioMix(input.portfolio, reportDate),
    riskItems: buildRiskItems(input.portfolio, reportDate),
    calendarItems: buildCalendarItems(input.calendarItems),
    watchRows: buildWatchRows(input),
    accountRows: buildAccountRows(input),
  };
}

export function getDashboardCockpitSectionStatusLabel(
  status: DashboardCockpitSectionStatus,
): string {
  return statusLabel(status);
}
