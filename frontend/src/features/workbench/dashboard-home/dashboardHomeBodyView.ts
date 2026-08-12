import type {
  AssetStructurePayload,
  BalanceAnalysisDecisionItemsPayload,
  BondBusinessTypeMetricsResult,
  BondPositionChangesPayload,
  BondTopHoldingsPayload,
  CampisiFourEffectsPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  CreditSpreadMigrationPayload,
  HomeIncomeTrendPayload,
  HomeMacroReleaseContextPayload,
  HomeResearchReportsPayload,
  IndustryDistPayload,
  KRDCurveRiskPayload,
  MaturityStructurePayload,
  Numeric,
  PortfolioComparisonPayload,
  ResearchCalendarEvent,
  ReturnDecompositionPayload,
  ResultMeta,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
  YieldCurveTermStructurePayload,
} from "../../../api/contracts";
import {
  normalizeHomeResearchLink,
  normalizeHomeResearchPublishedDate,
} from "./dashboardHomeResearchContract";
import {
  DASHBOARD_COCKPIT_REPORT_DATE,
  DASHBOARD_MARKET_PULSE_MOCK,
  DASHBOARD_QUICK_DRILLDOWN_MOCK,
} from "../dashboard/dashboardMockData";
import { todayIsoDate as resolveTodayIsoDate } from "../pages/dashboardPageHelpers";
import {
  buildHomeBondNewsModel,
  type HomeBondNewsModel,
} from "./adapters/buildHomeBondNewsModel";
import {
  buildHomeMacroBriefingModel,
  type HomeMacroBriefingModel,
  type HomeMacroNewsItem,
} from "./adapters/buildHomeMacroBriefingModel";
import { buildHomeMacroReleaseHistoryItems } from "./adapters/buildHomeMacroReleaseHistoryItems";
import {
  buildHomeMarketContextModel,
  type HomeMarketContextModel,
} from "./adapters/buildHomeMarketContextModel";
import { buildHomeResearchCalendarModel } from "./adapters/buildHomeResearchCalendarModel";
import {
  mapHomeSummaryDistributions,
  type HomeDistributionView,
} from "./adapters/mapHomeSummaryDistributions";
import type {
  HomeSnapshotOverviewMetricVM,
  HomeSnapshotPnlAttributionVM,
} from "./dashboardHomeSnapshotAdapter";
import { mapMarketTape, type HomeMarketTicker } from "./dashboardHomeMarket";
import type { HomeDataStateKind, HomeDeltaTone } from "./dashboardHomeFirstScreenTypes";
import { formatDv01Wan } from "../../bond-dashboard/utils/format";

export type { HomeDataStateKind, HomeDeltaTone } from "./dashboardHomeFirstScreenTypes";
export { resolveDeltaClass } from "./dashboardHomeFirstScreenTypes";

type NumericLike = Numeric | string | number | null | undefined;

export type HomeQuickDrill = {
  id: string;
  label: string;
  icon: string;
  path: string;
};

export type HomeTerminalListState = {
  kind: HomeDataStateKind;
  label: string;
};

export type HomeTrustedSectionDateBasis =
  | "snapshot_report_date"
  | "supplemental_report_date"
  | "natural_date"
  | "mixed"
  | "unknown";

export type HomeTrustedSection<T> = {
  key: string;
  status: HomeTerminalListState;
  reportDate: string;
  dateBasis: HomeTrustedSectionDateBasis;
  source: string;
  sourceMeta: ResultMeta | null;
  warnings: readonly string[];
  missingComponents: readonly string[];
  unitNotes: readonly string[];
  data: T;
};

export type HomeHoldingRow = {
  id: string;
  code: string;
  name: string;
  assetClass: string;
  marketValue: string;
  marketValueRaw?: number | null;
  weight: string;
  weightRaw?: number | null;
  ytm: string;
  duration: string;
  rating: string;
};

export type HomeDistributionSlice = {
  id: string;
  label: string;
  value: string;
  pct: string;
  pctRaw: number;
};

export type HomeRiskExposureMetric = {
  id: string;
  label: string;
  value: string;
};

export type HomePositionChangeRow = {
  id: string;
  code: string;
  name: string;
  reason: string;
  currentValue: string;
  changeValue: string;
  weightDelta: string;
  direction: "increase" | "decrease" | "flat";
  tone: HomeDeltaTone;
  barPct: number;
};

export type HomeResearchReportRow = {
  id: string;
  title: string;
  category: string;
  publishedAt: string;
  source: string;
  institution: string;
  summary: string;
  link: string | null;
  isNewsFallback: boolean;
};

export type HomeIncomeTrendRow = {
  id: string;
  date: string;
  portfolioPnl: string;
  benchmarkPnl: string;
  excessPnl: string;
  portfolioRaw: number | null;
  benchmarkRaw: number | null;
  excessRaw: number | null;
  /** 基准/超额缺值时的完整原因（进 title），单元格本身用 em dash。 */
  missingReason: string | null;
};

/** 各期限利率风险敞口（来自 /api/bond-analytics/krd-curve-risk 的 krd_buckets）。 */
export type HomeKrdBucketRow = {
  id: string;
  tenor: string;
  dv01Display: string;
  dv01Raw: number | null;
  /** 相对最大桶的条宽百分比；无数值时为 null（不画条）。 */
  barWidthPct: number | null;
};

/** 待复核事项预览（来自 /ui/balance-analysis/decision-items，pending 优先）。 */
export type HomeDecisionItemPreviewRow = {
  id: string;
  title: string;
  severity: "high" | "medium" | "low";
  actionLabel: string;
  reason: string;
};

export type DashboardHomeBodyView = {
  reportDate: string;
  portfolioAum: string;
  marketContext: HomeMarketContextModel;
  marketTape?: readonly HomeMarketTicker[];
  quickDrilldowns: readonly HomeQuickDrill[];
  macroBriefing: HomeMacroBriefingModel;
  bondNews: HomeBondNewsModel;
  holdingRows: readonly HomeHoldingRow[];
  holdingsState: HomeTerminalListState;
  assetDistribution: readonly HomeDistributionSlice[];
  assetDistributionState: HomeTerminalListState;
  ratingDistribution: readonly HomeDistributionSlice[];
  ratingDistributionState: HomeTerminalListState;
  maturityDistribution: readonly HomeDistributionSlice[];
  maturityDistributionState: HomeTerminalListState;
  industryDistribution: readonly HomeDistributionSlice[];
  industryDistributionState: HomeTerminalListState;
  yieldDistribution: readonly HomeDistributionSlice[];
  yieldDistributionState: HomeTerminalListState;
  portfolioComparison: readonly HomeDistributionSlice[];
  portfolioComparisonState: HomeTerminalListState;
  riskExposureMetrics: readonly HomeRiskExposureMetric[];
  riskExposureState: HomeTerminalListState;
  positionChanges: readonly HomePositionChangeRow[];
  positionChangesState: HomeTerminalListState;
  researchReports: readonly HomeResearchReportRow[];
  researchReportsState: HomeTerminalListState;
  incomeTrend: readonly HomeIncomeTrendRow[];
  incomeTrendState: HomeTerminalListState;
  incomeTrendSection: HomeTrustedSection<readonly HomeIncomeTrendRow[]>;
  krdBuckets: readonly HomeKrdBucketRow[];
  krdState: HomeTerminalListState;
  decisionItemsPreview: readonly HomeDecisionItemPreviewRow[];
  decisionItemsState: HomeTerminalListState;
  /** 余额分析域的事项报告日（与债券报告日不同域，供来源标注）。 */
  decisionItemsReportDate: string;
};

export type MapToHomeBodyViewInput = {
  reportDate: string;
  useMockFallback: boolean;
  overviewMetrics?: readonly HomeSnapshotOverviewMetricVM[] | null;
  attribution: HomeSnapshotPnlAttributionVM | null;
  creditSpreadMigration: CreditSpreadMigrationPayload | null;
  returnDecomposition: ReturnDecompositionPayload | null;
  campisiFourEffects: CampisiFourEffectsPayload | null;
  yieldCurveTermStructure: YieldCurveTermStructurePayload | null;
  marketPoints: readonly ChoiceMacroLatestPoint[] | null;
  assetStructure: AssetStructurePayload | null;
  ratingStructure: AssetStructurePayload | null;
  maturityStructure: MaturityStructurePayload | null;
  industryDistribution: IndustryDistPayload | null;
  homeSummaryMeta?: ResultMeta | null;
  homeSummaryLoading?: boolean;
  homeSummaryError?: boolean;
  yieldDistribution?: YieldDistributionPayload | null;
  portfolioComparison?: PortfolioComparisonPayload | null;
  spreadAnalysis?: SpreadAnalysisPayload | null;
  businessType?: BondBusinessTypeMetricsResult | null;
  riskIndicators: RiskIndicatorsPayload | null;
  topHoldings: BondTopHoldingsPayload | null;
  topHoldingsLoading: boolean;
  topHoldingsError: boolean;
  positionChanges: BondPositionChangesPayload | null;
  positionChangesLoading: boolean;
  positionChangesError: boolean;
  researchReports: HomeResearchReportsPayload | null;
  researchReportsLoading: boolean;
  researchReportsError: boolean;
  incomeTrend: HomeIncomeTrendPayload | null;
  incomeTrendLoading: boolean;
  incomeTrendError: boolean;
  krdCurveRisk?: KRDCurveRiskPayload | null;
  krdLoading?: boolean;
  krdError?: boolean;
  decisionItems?: BalanceAnalysisDecisionItemsPayload | null;
  decisionItemsLoading?: boolean;
  decisionItemsError?: boolean;
  calendarEvents: readonly ResearchCalendarEvent[] | null;
  calendarLoading: boolean;
  calendarError: boolean;
  calendarStartDate: string;
  calendarEndDate: string;
  todayIsoDate?: string;
  macroNewsEvents?: readonly ChoiceNewsEvent[] | null;
  macroNewsFallbackEvents?: readonly ChoiceNewsEvent[] | null;
  bondNewsEvents?: readonly ChoiceNewsEvent[] | null;
  bondNewsPayloads?: readonly ChoiceNewsEventsPayload[] | null;
  macroNewsLoading?: boolean;
  macroNewsError?: boolean;
  macroReleaseContext?: HomeMacroReleaseContextPayload | null;
  macroReleaseContextLoading?: boolean;
  macroReleaseContextError?: boolean;
};

const GAP = "—";
const HOME_RESEARCH_REPORT_FOCUS_TERMS = [
  "fixed_income",
  "bond",
  "bonds",
  "duration",
  "curve",
  "rates",
  "macro",
  "债",
  "利率",
  "国债",
  "政金债",
  "金融债",
  "信用债",
  "城投",
  "二永",
  "存单",
  "固收",
  "久期",
  "曲线",
  "利差",
  "收益率",
  "货币",
  "央行",
  "宏观",
] as const;

const MOCK_DISTRIBUTION_SLICES: readonly HomeDistributionSlice[] = [
  { id: "gov", label: "利率债", value: "1,920.00 亿", pct: "51.78%", pctRaw: 51.78 },
  { id: "credit", label: "信用债", value: "1,120.00 亿", pct: "30.20%", pctRaw: 30.2 },
  { id: "financial", label: "金融债", value: "488.00 亿", pct: "13.16%", pctRaw: 13.16 },
  { id: "cd", label: "同业存单", value: "180.10 亿", pct: "4.86%", pctRaw: 4.86 },
];

function isNumericObject(value: NumericLike): value is Numeric {
  return typeof value === "object" && value !== null && "raw" in value;
}

function numericRaw(value: NumericLike): number | null {
  if (typeof value === "string" || typeof value === "number") {
    const parsedValue = typeof value === "number" ? value : Number(value.replace(/,/g, ""));
    return Number.isFinite(parsedValue) ? parsedValue : null;
  }
  if (!isNumericObject(value) || value.raw == null) {
    return null;
  }
  const parsed =
    typeof value.raw === "number"
      ? value.raw
      : Number(String(value.raw).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function formatYi(rawYuan: number, signAware: boolean): string {
  const yi = rawYuan / 100_000_000;
  const formatted = yi.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${signAware && yi >= 0 ? "+" : ""}${formatted} 亿`;
}

function formatPct(raw: number, signAware: boolean): string {
  const pct = raw * 100;
  const formatted = pct.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${signAware && pct >= 0 ? "+" : ""}${formatted}%`;
}

function formatRatio(raw: number): string {
  return raw.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDv01(raw: number): string {
  return raw.toLocaleString("en-US", {
    maximumFractionDigits: 2,
  });
}

function numericDisplay(value: NumericLike, fallback = GAP, unitHint?: string): string {
  const raw = numericRaw(value);
  const unit = isNumericObject(value) ? value.unit : unitHint;
  const signAware = isNumericObject(value) ? value.sign_aware : false;
  const display = isNumericObject(value) ? value.display?.trim() : undefined;
  if (raw != null) {
    if (unit === "yuan") {
      const hasScaledUnit = Boolean(display && /[亿万]/.test(display));
      return hasScaledUnit ? display! : formatYi(raw, signAware);
    }
    if (unit === "pct") {
      const hasPct = Boolean(display && display.includes("%"));
      return hasPct ? display! : formatPct(raw, signAware);
    }
    if (unit === "ratio") {
      return display && display !== "--" ? display : formatRatio(raw);
    }
    if (unit === "dv01") {
      return display && display !== "--" ? display : formatDv01(raw);
    }
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (display && display.length > 0 && display !== "--") {
    return display;
  }
  return fallback;
}

function numericValueOrGap(value: NumericLike, unitHint?: string): string {
  return numericDisplay(value, GAP, unitHint);
}

function dv01WanValueOrGap(value: NumericLike): string {
  const formatted = formatDv01Wan(typeof value === "string" ? undefined : value);
  return formatted === GAP ? GAP : `${formatted} 万`;
}

function ratioAsPercentNumeric(value: NumericLike): NumericLike {
  const raw = numericRaw(value);
  if (raw == null) {
    return value;
  }
  return {
    raw,
    unit: "pct",
    display: formatPct(raw, false),
    precision: 2,
    sign_aware: false,
  };
}

function percentageRaw(value: NumericLike): number {
  const raw = numericRaw(value);
  if (raw == null) {
    return 0;
  }
  if (isNumericObject(value) && value.unit === "pct") {
    return raw * 100;
  }
  return raw;
}

function displayState(kind: HomeDataStateKind, label: string): HomeTerminalListState {
  return { kind, label };
}

function cleanDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const a = cleanDate(expected);
  const b = cleanDate(actual);
  return a.length > 0 && b.length > 0 && a === b;
}

function reportDateState(
  expectedReportDate: string,
  actualReportDate: string | null | undefined,
  emptyLabel: string,
): HomeTerminalListState {
  const actual = cleanDate(actualReportDate);
  if (!actual) {
    return displayState("empty", emptyLabel);
  }
  if (!isSameReportDate(expectedReportDate, actual)) {
    return displayState("stale", `数据日期 ${actual}，未并入 ${expectedReportDate}`);
  }
  return displayState("ready", "已接入");
}

function mapStructureSlices<T extends {
  total_market_value: Numeric;
  percentage: Numeric | null;
}>(
  payload: { report_date: string; items: readonly T[] } | null | undefined,
  expectedReportDate: string,
  getLabel: (item: T) => string,
  emptyLabel: string,
  meta?: ResultMeta | null,
): { slices: HomeDistributionSlice[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, emptyLabel);
  if (state.kind !== "ready" || !payload?.items?.length) {
    return {
      slices: [],
      state: payload?.items?.length ? state : displayState("empty", emptyLabel),
    };
  }
  return {
    state: stateWithSourceMeta(state, meta),
    slices: payload.items.slice(0, 8).map((item, index) => ({
      id: `${getLabel(item) || "slice"}-${index}`,
      label: getLabel(item) || GAP,
      value: numericValueOrGap(item.total_market_value, "yuan"),
      pct: numericValueOrGap(item.percentage, "pct"),
      pctRaw: percentageRaw(item.percentage),
    })),
  };
}

function sourceMetaLabel(meta: ResultMeta | null | undefined): string {
  const parts = [
    meta?.quality_flag && meta.quality_flag !== "ok" ? `quality ${meta.quality_flag}` : "",
    meta?.vendor_status && meta.vendor_status !== "ok" ? `vendor ${meta.vendor_status}` : "",
    meta?.fallback_mode && meta.fallback_mode !== "none" ? `fallback ${meta.fallback_mode}` : "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "已接入";
}

function stateWithSourceMeta(
  state: HomeTerminalListState,
  meta: ResultMeta | null | undefined,
): HomeTerminalListState {
  if (state.kind !== "ready" || !meta) {
    return state;
  }
  if (
    meta.quality_flag !== "ok" ||
    meta.vendor_status === "vendor_stale" ||
    meta.fallback_mode !== "none"
  ) {
    return displayState("partial", sourceMetaLabel(meta));
  }
  return state;
}

/**
 * `HomeDistributionRowView.percentageRaw` 来自后端 `percentage`（unit="pct" 的 Numeric）。
 * 后端 `common_numeric._normalize_numeric_raw` 保证 pct raw 恒为小数比率，因此固定 ×100，
 * 不再使用 |x|<=1 的启发式判断。
 */
export function percentageDisplayRaw(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value)) {
    return null;
  }
  return value * 100;
}

function metricFromDistributionRow(
  row: HomeDistributionView["rows"][number],
  unit: Numeric["unit"] = "yuan",
): Numeric {
  return {
    raw: row.valueRaw,
    unit,
    display: row.valueDisplay,
    precision: 2,
    sign_aware: unit === "pct",
  };
}

function mapDistributionViewToSlices(
  distribution: HomeDistributionView | undefined,
  payloadReportDate: string | null | undefined,
  expectedReportDate: string,
  emptyLabel: string,
  meta: ResultMeta | null | undefined,
): { slices: HomeDistributionSlice[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payloadReportDate, emptyLabel);
  if (state.kind !== "ready" || !distribution?.rows.length) {
    return {
      slices: [],
      state: distribution?.rows.length ? state : displayState("empty", emptyLabel),
    };
  }
  const maxRaw = Math.max(...distribution.rows.map((row) => row.valueRaw ?? 0), 0);
  return {
    state: stateWithSourceMeta(state, meta),
    slices: distribution.rows.slice(0, 8).map((row) => {
      const pctRaw = percentageDisplayRaw(row.percentageRaw);
      return {
        id: row.id,
        label: row.label,
        value: numericDisplay(metricFromDistributionRow(row)),
        pct: row.percentageDisplay ?? (row.count != null ? `${row.count}只` : GAP),
        pctRaw: pctRaw ?? (maxRaw > 0 && row.valueRaw != null ? (row.valueRaw / maxRaw) * 100 : 0),
      };
    }),
  };
}

function localizeAssetClass(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) {
    return GAP;
  }
  if (normalized === "rate") {
    return "利率债";
  }
  if (normalized === "credit") {
    return "信用债";
  }
  if (normalized === "other") {
    return "其他";
  }
  return value?.trim() || GAP;
}

function holdingRatingLabel(rating: string | null | undefined, assetClass: string | null | undefined): string {
  const trimmedRating = rating?.trim();
  if (trimmedRating) {
    return trimmedRating;
  }
  return assetClass?.trim().toLowerCase() === "rate" ? "不适用" : GAP;
}

function buildHoldingRows(
  payload: BondTopHoldingsPayload | null | undefined,
  expectedReportDate: string,
): { rows: HomeHoldingRow[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, "重仓券暂无数据");
  if (state.kind !== "ready" || !payload?.items?.length) {
    return {
      rows: [],
      state: payload?.items?.length ? state : displayState("empty", "重仓券暂无数据"),
    };
  }
  return {
    state,
    rows: payload.items.slice(0, payload.top_n || 8).map((item) => ({
      id: item.instrument_code,
      code: item.instrument_code,
      name: item.instrument_name?.trim() || item.issuer_name?.trim() || GAP,
      assetClass: localizeAssetClass(item.asset_class),
      marketValue: numericValueOrGap(item.market_value, "yuan"),
      marketValueRaw: numericRaw(item.market_value),
      weight: numericValueOrGap(item.weight, "pct"),
      weightRaw: numericRaw(item.weight),
      ytm: numericValueOrGap(item.ytm, "pct"),
      duration: numericValueOrGap(item.modified_duration, "ratio"),
      rating: holdingRatingLabel(item.rating, item.asset_class),
    })),
  };
}

function buildPositionChangeRows(
  payload: BondPositionChangesPayload | null | undefined,
  expectedReportDate: string,
): { rows: HomePositionChangeRow[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, "增减仓暂无数据");
  if (state.kind !== "ready" || payload?.source_status !== "ready" || !payload.items.length) {
    return {
      rows: [],
      state: payload?.items?.length ? state : displayState("empty", "增减仓暂无数据"),
    };
  }
  const maxAbsChange = Math.max(
    ...payload.items.map((item) => Math.abs(numericRaw(item.change_market_value) ?? 0)),
    1,
  );
  return {
    state,
    rows: payload.items.slice(0, payload.top_n || 5).map((item) => {
      const absChange = Math.abs(numericRaw(item.change_market_value) ?? 0);
      return {
        id: item.instrument_code,
        code: item.instrument_code,
        name: item.instrument_name?.trim() || item.issuer_name?.trim() || GAP,
        reason: item.reason_label || item.direction,
        currentValue: numericValueOrGap(item.current_market_value, "yuan"),
        changeValue: numericValueOrGap(item.change_market_value, "yuan"),
        weightDelta: numericValueOrGap(item.change_weight, "ratio"),
        direction: item.direction,
        tone: item.direction === "increase" ? "up" : item.direction === "decrease" ? "down" : "flat",
        barPct: Math.max(4, Math.min(100, (absChange / maxAbsChange) * 100)),
      };
    }),
  };
}

function isHomeResearchReportRelevant(item: HomeResearchReportsPayload["items"][number]): boolean {
  const haystack = `${item.title} ${item.category} ${item.institution ?? ""}`.toLowerCase();
  return HOME_RESEARCH_REPORT_FOCUS_TERMS.some((term) => haystack.includes(term));
}

function buildResearchReportRows(
  payload: HomeResearchReportsPayload | null | undefined,
): { rows: HomeResearchReportRow[]; state: HomeTerminalListState } {
  const relevantItems = (payload?.items ?? []).filter(isHomeResearchReportRelevant);
  if (relevantItems.length === 0 || payload?.source_status === "empty") {
    return {
      rows: [],
      state: displayState("empty", "债券/宏观研报暂无数据"),
    };
  }
  const sourceStatus = payload?.source_status;
  const mappedState =
    sourceStatus === "stale"
      ? displayState("partial", "报告日前无研报 · 展示最新")
      : displayState("ready", "已接入");
  return {
    state: mappedState,
    rows: relevantItems.slice(0, 5).map((item) => ({
      id: item.id,
      title: item.title.trim() || GAP,
      category: item.category.trim() || "research",
      publishedAt: normalizeHomeResearchPublishedDate(item.published_at) ?? GAP,
      source: item.source.trim() || GAP,
      institution: item.institution?.trim() || GAP,
      summary: item.summary?.trim() || GAP,
      link: normalizeHomeResearchLink(item.link),
      isNewsFallback: false,
    })),
  };
}

function buildResearchNewsFallbackRows(
  newsItems: readonly HomeMacroNewsItem[],
  sourceLabel: string,
): { rows: HomeResearchReportRow[]; state: HomeTerminalListState } | null {
  if (newsItems.length === 0) {
    return null;
  }
  const source = sourceLabel.replace(/^来源：/, "").trim() || "宏观新闻";
  return {
    state: displayState("partial", "研报源暂缺 · 新闻补位"),
    rows: newsItems.slice(0, 5).map((item) => ({
      id: `macro-news-${item.id}`,
      title: item.title,
      category: `新闻补位 · ${item.topicLabel}`,
      publishedAt: GAP,
      source,
      institution: source,
      summary: `${source} · ${item.freshnessLabel}`,
      link: null,
      isNewsFallback: true,
    })),
  };
}

function localizeIncomeTrendComponent(component: string): string {
  if (component === "benchmark_pnl") return "基准PnL";
  if (component === "excess_pnl") return "超额PnL";
  if (component === "portfolio_pnl") return "组合PnL";
  return component;
}

function buildIncomeTrendGapLabel(payload: HomeIncomeTrendPayload): string {
  const warnings = payload.warnings.join(" ");
  if (/CDB_INDEX/i.test(warnings) && /YIELD_CURVE_LATEST_FALLBACK|latest available/i.test(warnings)) {
    return "缺 CDB_INDEX 可核验曲线";
  }
  if (/CDB_INDEX/i.test(warnings) && /unavailable|missing|No\s+/i.test(warnings)) {
    return "缺 CDB_INDEX 曲线";
  }
  if (/benchmark_return|excess_return/i.test(warnings)) {
    return "缺 benchmark_return/excess_return";
  }
  if (payload.missing_components.length > 0) {
    return `缺 ${payload.missing_components.map(localizeIncomeTrendComponent).join("/")}`;
  }
  return "收益趋势部分接入";
}

const INCOME_TREND_UNIT_NOTES = [
  "portfolio_pnl, benchmark_pnl, and excess_pnl are yuan Numeric values; preserve Numeric.display when provided.",
] as const;

function buildIncomeTrendRows(
  payload: HomeIncomeTrendPayload | null | undefined,
  expectedReportDate: string,
): { rows: HomeIncomeTrendRow[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, "收益趋势暂无数据");
  if (state.kind !== "ready") {
    return {
      rows: [],
      state: payload?.points.length ? state : displayState("empty", "收益趋势暂无数据"),
    };
  }
  if (!payload?.points.length || payload.source_status === "empty") {
    return {
      rows: [],
      state: displayState("empty", "收益趋势暂无数据"),
    };
  }
  const gapLabel = buildIncomeTrendGapLabel(payload);
  const mappedState =
    payload.source_status === "partial"
      ? displayState("partial", gapLabel)
      : displayState("ready", "已接入");
  return {
    state: mappedState,
    // 缺值单元格统一 em dash（§6），完整原因经 missingReason 进行级 title，
    // 不再往窄列里塞「缺CDB_INDEX」这类会被截断的证据码。
    rows: payload.points.map((point) => {
      const benchmarkRaw = numericRaw(point.benchmark_pnl);
      const excessRaw = numericRaw(point.excess_pnl);
      return {
        id: point.date,
        date: point.date,
        portfolioPnl: numericValueOrGap(point.portfolio_pnl, "yuan"),
        benchmarkPnl: benchmarkRaw == null ? GAP : numericValueOrGap(point.benchmark_pnl, "yuan"),
        excessPnl: excessRaw == null ? GAP : numericValueOrGap(point.excess_pnl, "yuan"),
        portfolioRaw: numericRaw(point.portfolio_pnl),
        benchmarkRaw,
        excessRaw,
        missingReason: benchmarkRaw == null || excessRaw == null ? gapLabel : null,
      };
    }),
  };
}

function buildKrdBucketRows(args: {
  payload: KRDCurveRiskPayload | null | undefined;
  loading?: boolean;
  error?: boolean;
  expectedReportDate: string;
}): { rows: HomeKrdBucketRow[]; state: HomeTerminalListState } {
  if (args.error) {
    return { rows: [], state: displayState("error", "期限敞口读取失败") };
  }
  if (args.loading) {
    return { rows: [], state: displayState("loading", "期限敞口读取中") };
  }
  if (!args.payload?.krd_buckets?.length) {
    return { rows: [], state: displayState("empty", "暂无期限敞口数据") };
  }
  const state = reportDateState(
    args.expectedReportDate,
    args.payload.report_date,
    "暂无期限敞口数据",
  );
  if (state.kind !== "ready") {
    return { rows: [], state };
  }
  // raw 单位为 元/bp，/1e4 转「万元/bp」，与债券分析页 formatDv01Wan 口径一致。
  const sorted = args.payload.krd_buckets
    .map((bucket, index) => {
      const raw = numericRaw(bucket.dv01);
      return {
        id: `${bucket.tenor}-${index}`,
        tenor: bucket.tenor,
        dv01Display:
          raw == null
            ? GAP
            : (raw / 1e4).toLocaleString("zh-CN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }),
        dv01Raw: raw,
      };
    })
    .sort((a, b) => krdTenorSortKey(a.tenor) - krdTenorSortKey(b.tenor));
  const maxAbs = Math.max(
    1e-9,
    ...sorted.map((row) => Math.abs(row.dv01Raw ?? 0)),
  );
  return {
    rows: sorted.map((row) => ({
      ...row,
      barWidthPct:
        row.dv01Raw == null
          ? null
          : Math.max(2, (Math.abs(row.dv01Raw) / maxAbs) * 100),
    })),
    state,
  };
}

/** 期限文本转年限（"6M"→0.5、"10Y"→10），无法解析的排最后。 */
function krdTenorSortKey(tenor: string): number {
  const match = /([\d.]+)\s*([YyMm])?/.exec(tenor);
  const value = match ? Number(match[1]) : Number.NaN;
  if (!Number.isFinite(value)) return Number.MAX_SAFE_INTEGER;
  return match?.[2]?.toLowerCase() === "m" ? value / 12 : value;
}

const DECISION_SEVERITY_ORDER: Record<HomeDecisionItemPreviewRow["severity"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function normalizeDecisionSeverity(value: unknown): HomeDecisionItemPreviewRow["severity"] {
  return value === "high" || value === "medium" || value === "low" ? value : "medium";
}

/** 余额分析域日期与首页债券报告日不同域：不做日期一致性判定，只透传标注。 */
function buildDecisionItemsPreview(args: {
  payload: BalanceAnalysisDecisionItemsPayload | null | undefined;
  loading?: boolean;
  error?: boolean;
}): {
  rows: HomeDecisionItemPreviewRow[];
  state: HomeTerminalListState;
  reportDate: string;
} {
  if (args.error) {
    return { rows: [], state: displayState("error", "决策事项读取失败"), reportDate: "" };
  }
  if (args.loading) {
    return { rows: [], state: displayState("loading", "决策事项读取中"), reportDate: "" };
  }
  if (!args.payload) {
    return { rows: [], state: displayState("empty", "决策事项未接入"), reportDate: "" };
  }
  const rows = args.payload.rows
    .filter((row) => row.latest_status?.status === "pending")
    .sort(
      (a, b) =>
        DECISION_SEVERITY_ORDER[normalizeDecisionSeverity(a.severity)] -
          DECISION_SEVERITY_ORDER[normalizeDecisionSeverity(b.severity)] ||
        a.decision_key.localeCompare(b.decision_key),
    )
    .slice(0, 2)
    .map((row) => ({
      id: row.decision_key,
      title: row.title?.trim() || row.decision_key,
      severity: normalizeDecisionSeverity(row.severity),
      actionLabel: row.action_label?.trim() || "去处理",
      reason: row.reason?.trim() || "",
    }));
  return {
    rows,
    state: displayState(
      "ready",
      rows.length > 0 ? `${rows.length} 项待处理` : "暂无待处理事项",
    ),
    reportDate: cleanDate(args.payload.report_date),
  };
}

function buildIncomeTrendSection(
  payload: HomeIncomeTrendPayload | null | undefined,
  mapped: { rows: readonly HomeIncomeTrendRow[]; state: HomeTerminalListState },
  expectedReportDate: string,
): HomeTrustedSection<readonly HomeIncomeTrendRow[]> {
  const payloadReportDate = cleanDate(payload?.report_date);
  const fallbackReportDate = cleanDate(expectedReportDate);
  const hasSnapshotReportDate = fallbackReportDate.length > 0 && fallbackReportDate !== GAP;
  return {
    key: "income_trend",
    status: mapped.state,
    reportDate: payloadReportDate || fallbackReportDate,
    dateBasis: payloadReportDate
      ? "supplemental_report_date"
      : hasSnapshotReportDate
        ? "snapshot_report_date"
        : "unknown",
    source: "/ui/home/income-trend",
    sourceMeta: null,
    warnings: [...(payload?.warnings ?? [])],
    missingComponents: [...(payload?.missing_components ?? [])],
    unitNotes: INCOME_TREND_UNIT_NOTES,
    data: mapped.rows,
  };
}

function buildRiskExposureMetrics(
  payload: RiskIndicatorsPayload | null | undefined,
  expectedReportDate: string,
  meta?: ResultMeta | null,
): { metrics: HomeRiskExposureMetric[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, "风险指标暂无数据");
  if (state.kind !== "ready" || !payload) {
    return { metrics: [], state };
  }
  return {
    state: stateWithSourceMeta(state, meta),
    metrics: [
      { id: "market-value", label: "总市值", value: numericValueOrGap(payload.total_market_value, "yuan") },
      { id: "dv01", label: "利率风险 DV01", value: dv01WanValueOrGap(payload.total_dv01) },
      { id: "duration", label: "加权久期", value: numericValueOrGap(payload.weighted_duration, "ratio") },
      { id: "credit", label: "信用债占比", value: numericValueOrGap(ratioAsPercentNumeric(payload.credit_ratio), "pct") },
      { id: "convexity", label: "加权凸性", value: numericValueOrGap(payload.weighted_convexity, "ratio") },
      { id: "spread-dv01", label: "利差 DV01", value: dv01WanValueOrGap(payload.total_spread_dv01) },
      { id: "reinvestment", label: "1年再投资", value: numericValueOrGap(payload.reinvestment_ratio_1y, "ratio") },
    ],
  };
}

function attributionHintFromSnapshot(attribution: HomeSnapshotPnlAttributionVM | null): {
  maxDragLabel: string;
  maxContributionLabel: string;
} {
  let maxDragLabel = GAP;
  let maxDragRaw = 0;
  let maxContributionLabel = GAP;
  let maxContributionRaw = 0;

  for (const segment of attribution?.segments ?? []) {
    const raw = numericRaw(segment.amount);
    if (raw == null) {
      continue;
    }
    if (raw < 0 && (maxDragLabel === GAP || raw < maxDragRaw)) {
      maxDragLabel = segment.label;
      maxDragRaw = raw;
    }
    if (raw > 0 && (maxContributionLabel === GAP || raw > maxContributionRaw)) {
      maxContributionLabel = segment.label;
      maxContributionRaw = raw;
    }
  }

  return { maxDragLabel, maxContributionLabel };
}

function normalizeMockDeltaTone(tone: string): HomeMarketTicker["deltaTone"] {
  if (tone === "up" || tone === "down" || tone === "flat" || tone === "muted") {
    return tone;
  }
  return "flat";
}

function buildMockMarketTape(): HomeMarketTicker[] {
  return DASHBOARD_MARKET_PULSE_MOCK.map((item) => ({
    id: item.id,
    label: item.label,
    value: item.value,
    delta: item.delta,
    deltaTone: normalizeMockDeltaTone(item.deltaTone),
    sparkline: item.sparkline,
  }));
}

function buildQuickDrilldowns(): HomeQuickDrill[] {
  return DASHBOARD_QUICK_DRILLDOWN_MOCK.map((item) => ({
    id: item.id,
    label: item.label,
    icon: item.id,
    path: item.path,
  }));
}

function buildMockBodyView(): DashboardHomeBodyView {
  const todayIsoDate = resolveTodayIsoDate();
  const researchCalendar = buildHomeResearchCalendarModel({
    events: [],
    isLoading: false,
    isError: false,
    startDate: todayIsoDate,
    endDate: todayIsoDate,
  });
  const macroBriefing = buildHomeMacroBriefingModel({
    todayIsoDate,
    newsEvents: null,
    newsLoading: false,
    newsError: false,
    supplyCalendar: researchCalendar,
  });
  const marketTape = buildMockMarketTape();
  const marketContext = buildHomeMarketContextModel({
    marketTape,
    marketPoints: null,
    macroNewsEvents: null,
    todayIsoDate,
    campisiFourEffects: null,
    returnDecomposition: null,
    yieldCurveTermStructure: null,
    creditSpreadMigration: null,
    attribution: {
      maxDragLabel: GAP,
      maxContributionLabel: GAP,
    },
  });
  const bondNews = buildHomeBondNewsModel({
    todayIsoDate,
    events: null,
    topHoldings: null,
    positionChanges: null,
    industryDistribution: null,
  });
  const incomeTrendMapped = {
    rows: [] as HomeIncomeTrendRow[],
    state: displayState("empty", "样例模式暂无收益趋势"),
  };

  return {
    reportDate: DASHBOARD_COCKPIT_REPORT_DATE,
    portfolioAum: GAP,
    marketContext,
    marketTape,
    quickDrilldowns: buildQuickDrilldowns(),
    macroBriefing,
    bondNews,
    holdingRows: [],
    holdingsState: displayState("backend-gap", "样例模式不展示正式重仓券"),
    assetDistribution: [...MOCK_DISTRIBUTION_SLICES],
    assetDistributionState: displayState("ready", "样例模式"),
    ratingDistribution: [...MOCK_DISTRIBUTION_SLICES],
    ratingDistributionState: displayState("ready", "样例模式"),
    maturityDistribution: [],
    maturityDistributionState: displayState("backend-gap", "样例模式未提供期限结构"),
    industryDistribution: MOCK_DISTRIBUTION_SLICES.map((slice) => ({
      ...slice,
      id: `industry-${slice.id}`,
    })),
    industryDistributionState: displayState("ready", "样例模式"),
    yieldDistribution: [],
    yieldDistributionState: displayState("empty", "样例模式暂无收益率分布"),
    portfolioComparison: [],
    portfolioComparisonState: displayState("empty", "样例模式暂无组合对比"),
    riskExposureMetrics: [
      { id: "dv01", label: "利率风险 DV01", value: "10,615.59 万" },
      { id: "duration", label: "加权久期", value: "4.14" },
      { id: "credit", label: "信用占比", value: "41.35%" },
      { id: "spread-dv01", label: "利差 DV01", value: GAP },
    ],
    riskExposureState: displayState("ready", "样例模式"),
    positionChanges: [],
    positionChangesState: displayState("empty", "样例模式暂无增减仓"),
    researchReports: [],
    researchReportsState: displayState("empty", "样例模式暂无研究报告"),
    incomeTrend: incomeTrendMapped.rows,
    incomeTrendState: incomeTrendMapped.state,
    incomeTrendSection: buildIncomeTrendSection(
      null,
      incomeTrendMapped,
      DASHBOARD_COCKPIT_REPORT_DATE,
    ),
    krdBuckets: [],
    krdState: displayState("empty", "样例模式暂无期限敞口"),
    decisionItemsPreview: [],
    decisionItemsState: displayState("empty", "样例模式暂无决策事项"),
    decisionItemsReportDate: "",
  };
}

export function mapToHomeBodyView(input: MapToHomeBodyViewInput): DashboardHomeBodyView {
  if (input.useMockFallback) {
    return buildMockBodyView();
  }

  const reportDate = cleanDate(input.reportDate) || GAP;
  const portfolioAum = numericDisplay(
    input.overviewMetrics?.find((metric) => metric.id === "aum")?.value,
  );
  const todayIsoDate = input.todayIsoDate?.trim() || resolveTodayIsoDate();
  const researchCalendar = buildHomeResearchCalendarModel({
    events: input.calendarEvents,
    isLoading: input.calendarLoading,
    isError: input.calendarError,
    startDate: input.calendarStartDate,
    endDate: input.calendarEndDate,
  });
  const macroBriefingBase = buildHomeMacroBriefingModel({
    todayIsoDate,
    newsEvents: input.macroNewsEvents,
    fallbackNewsEvents: input.macroNewsFallbackEvents,
    newsLoading: Boolean(input.macroNewsLoading),
    newsError: Boolean(input.macroNewsError),
    supplyCalendar: researchCalendar,
  });
  const marketTape = mapMarketTape(input.marketPoints);
  const releaseHistoryItems = input.macroReleaseContext
    ? buildHomeMacroReleaseHistoryItems(input.macroReleaseContext.history_items)
    : [];
  const releaseHistoryMessage = input.macroReleaseContextLoading
    ? "历史数据读取中…"
    : input.macroReleaseContextError
      ? "历史数据读取失败，请稍后重试。"
      : releaseHistoryItems.length === 0
        ? "当前窗口暂无可用历史数据。"
        : null;
  const macroBriefing: HomeMacroBriefingModel = {
    ...macroBriefingBase,
    releaseHistoryItems,
    releaseHistoryMessage,
  };
  const marketContext = buildHomeMarketContextModel({
    marketTape,
    marketPoints: input.marketPoints,
    macroNewsEvents: input.macroNewsEvents,
    todayIsoDate,
    campisiFourEffects: input.campisiFourEffects,
    returnDecomposition: input.returnDecomposition,
    yieldCurveTermStructure: input.yieldCurveTermStructure,
    creditSpreadMigration: input.creditSpreadMigration,
    attribution: attributionHintFromSnapshot(input.attribution),
  });
  const homeSummaryDistributionViews = mapHomeSummaryDistributions({
    report_date: reportDate,
    asset_type: input.assetStructure ?? undefined,
    asset_rating: input.ratingStructure ?? undefined,
    maturity: input.maturityStructure ?? undefined,
    industry: input.industryDistribution ?? undefined,
    yield_distribution: input.yieldDistribution ?? undefined,
    portfolio_comparison: input.portfolioComparison ?? undefined,
    spread: input.spreadAnalysis ?? undefined,
    business_type: input.businessType ?? undefined,
  });
  const homeDistributionByKey = new Map(
    homeSummaryDistributionViews.map((section) => [section.key, section]),
  );
  const homeSummaryState = input.homeSummaryLoading
    ? displayState("loading", "home-summary 读取中")
    : input.homeSummaryError
      ? displayState("error", "home-summary 读取失败")
      : null;
  const riskExposure = homeSummaryState
    ? { metrics: [], state: homeSummaryState }
    : buildRiskExposureMetrics(
        input.riskIndicators,
        reportDate,
        input.homeSummaryMeta,
      );
  const holdingsMapped = input.topHoldingsLoading
    ? { rows: [], state: displayState("loading", "重仓券加载中") }
    : input.topHoldingsError
      ? { rows: [], state: displayState("error", "重仓券加载失败") }
      : buildHoldingRows(input.topHoldings, reportDate);
  const positionChangesMapped = input.positionChangesLoading
    ? { rows: [], state: displayState("loading", "增减仓加载中") }
    : input.positionChangesError
      ? { rows: [], state: displayState("error", "增减仓加载失败") }
      : buildPositionChangeRows(input.positionChanges, reportDate);
  const bondNews = buildHomeBondNewsModel({
    todayIsoDate,
    events: input.bondNewsEvents,
    choiceNewsPayloads: input.bondNewsPayloads,
    topHoldings: input.topHoldings,
    positionChanges: input.positionChanges,
    industryDistribution: input.industryDistribution,
  });
  const researchReportsBase = input.researchReportsLoading
    ? { rows: [], state: displayState("loading", "研究报告加载中") }
    : input.researchReportsError
      ? { rows: [], state: displayState("error", "研究报告加载失败") }
      : buildResearchReportRows(input.researchReports);
  const researchReportsMapped =
    researchReportsBase.state.kind === "empty"
      ? buildResearchNewsFallbackRows(macroBriefing.newsItems, macroBriefing.newsSourceLabel) ?? researchReportsBase
      : researchReportsBase;
  const incomeTrendMapped = input.incomeTrendLoading
    ? { rows: [], state: displayState("loading", "收益趋势加载中") }
    : input.incomeTrendError
      ? { rows: [], state: displayState("error", "收益趋势加载失败") }
      : buildIncomeTrendRows(input.incomeTrend, reportDate);
  const incomeTrendSection = buildIncomeTrendSection(
    input.incomeTrend,
    incomeTrendMapped,
    reportDate,
  );
  const krdMapped = buildKrdBucketRows({
    payload: input.krdCurveRisk,
    loading: input.krdLoading,
    error: input.krdError,
    expectedReportDate: reportDate,
  });
  const decisionItemsMapped = buildDecisionItemsPreview({
    payload: input.decisionItems,
    loading: input.decisionItemsLoading,
    error: input.decisionItemsError,
  });
  const assetDistributionMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapStructureSlices(
        input.assetStructure,
        reportDate,
        (item) => item.category,
        "资产分布暂无数据",
        input.homeSummaryMeta,
      );
  const ratingMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapStructureSlices(
        input.ratingStructure,
        reportDate,
        (item) => item.category,
        "评级分布暂无数据",
        input.homeSummaryMeta,
      );
  const maturityMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapStructureSlices(
        input.maturityStructure,
        reportDate,
        (item) => item.maturity_bucket,
        "久期分布暂无数据",
        input.homeSummaryMeta,
      );
  const industryMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapStructureSlices(
        input.industryDistribution,
        reportDate,
        (item) => item.industry_name,
        "行业分布暂无数据",
        input.homeSummaryMeta,
      );
  const yieldDistributionMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapDistributionViewToSlices(
        homeDistributionByKey.get("yield_distribution"),
        input.yieldDistribution?.report_date,
        reportDate,
        "收益率分布暂无数据",
        input.homeSummaryMeta,
      );
  const portfolioComparisonMapped = homeSummaryState
    ? { slices: [], state: homeSummaryState }
    : mapDistributionViewToSlices(
        homeDistributionByKey.get("portfolio_comparison"),
        input.portfolioComparison?.report_date,
        reportDate,
        "组合对比暂无数据",
        input.homeSummaryMeta,
      );

  return {
    reportDate,
    portfolioAum,
    marketContext,
    marketTape,
    quickDrilldowns: buildQuickDrilldowns(),
    macroBriefing,
    bondNews,
    holdingRows: holdingsMapped.rows,
    holdingsState: holdingsMapped.state,
    assetDistribution: assetDistributionMapped.slices,
    assetDistributionState: assetDistributionMapped.state,
    ratingDistribution: ratingMapped.slices,
    ratingDistributionState: ratingMapped.state,
    maturityDistribution: maturityMapped.slices,
    maturityDistributionState: maturityMapped.state,
    industryDistribution: industryMapped.slices,
    industryDistributionState: industryMapped.state,
    yieldDistribution: yieldDistributionMapped.slices,
    yieldDistributionState: yieldDistributionMapped.state,
    portfolioComparison: portfolioComparisonMapped.slices,
    portfolioComparisonState: portfolioComparisonMapped.state,
    riskExposureMetrics: riskExposure.metrics,
    riskExposureState: riskExposure.state,
    positionChanges: positionChangesMapped.rows,
    positionChangesState: positionChangesMapped.state,
    researchReports: researchReportsMapped.rows,
    researchReportsState: researchReportsMapped.state,
    incomeTrend: incomeTrendMapped.rows,
    incomeTrendState: incomeTrendMapped.state,
    incomeTrendSection,
    krdBuckets: krdMapped.rows,
    krdState: krdMapped.state,
    decisionItemsPreview: decisionItemsMapped.rows,
    decisionItemsState: decisionItemsMapped.state,
    decisionItemsReportDate: decisionItemsMapped.reportDate,
  };
}
