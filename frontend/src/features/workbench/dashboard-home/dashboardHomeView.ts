import type {
  AssetStructurePayload,
  BalanceAnalysisDecisionItemStatusRow,
  BondDashboardHeadlinePayload,
  BondPositionChangesPayload,
  BondPortfolioHeadlinesPayload,
  BondTopHoldingsPayload,
  CampisiFourEffectsPayload,
  ChoiceNewsEvent,
  CockpitWarningsPayload,
  CoreMetricsResult,
  CreditSpreadMigrationPayload,
  DailyChangesResult,
  IndustryDistPayload,
  MaturityStructurePayload,
  Numeric,
  PortfolioComparisonPayload,
  ProductCategoryMonthlyHeadlinePayload,
  ProductCategoryYtdHeadlinePayload,
  ResearchCalendarEvent,
  HomeIncomeTrendPayload,
  HomeResearchReportsPayload,
  ReturnDecompositionPayload,
  ResultMeta,
  RiskIndicatorsPayload,
  YieldCurveTermStructurePayload,
  VerdictPayload,
} from "../../../api/contracts";
import type {
  DashboardOverviewMetricVM,
  DashboardPnlAttributionVM,
} from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import {
  DASHBOARD_ASSET_BARS_MOCK,
  DASHBOARD_ATTRIBUTION_NOTE_MOCK,
  DASHBOARD_ATTRIBUTION_WATERFALL_MOCK,
  DASHBOARD_BALANCE_METRICS_MOCK,
  DASHBOARD_COCKPIT_HEADER_STATUS,
  DASHBOARD_COCKPIT_REPORT_DATE,
  DASHBOARD_EXPOSURE_ROWS_MOCK,
  DASHBOARD_INTERBANK_MOCK,
  DASHBOARD_MARKET_PULSE_MOCK,
  DASHBOARD_PORTFOLIO_STATS_MOCK,
  DASHBOARD_QUICK_DRILLDOWN_MOCK,
  DASHBOARD_RISK_ALERT_COUNTS_MOCK,
  DASHBOARD_RISK_RADAR_MOCK,
  DASHBOARD_RISK_TODOS_MOCK,
  DASHBOARD_WATCHLIST_MOCK,
} from "../dashboard/dashboardMockData";
import { findAttributionExtremes, type HomeWaterfallItem } from "./dashboardHomeAttribution";
import { buildHomeAttributionTabs } from "./adapters/buildHomeAttributionTabs";
import {
  buildHomeMacroBriefingModel,
  type HomeMacroBriefingModel,
  type HomeMacroNewsItem,
} from "./adapters/buildHomeMacroBriefingModel";
import {
  buildHomeMarketContextModel,
  type HomeMarketContextModel,
} from "./adapters/buildHomeMarketContextModel";
import {
  buildHomeResearchCalendarModel,
  type HomeResearchCalendarModel,
} from "./adapters/buildHomeResearchCalendarModel";
import { mapAssetStructureToHomeAssetBars } from "./adapters/mapAssetStructureToHomeAssetBars";
import {
  mapCockpitWarningsToRiskCards,
  mapCockpitWarningsToWatchlist,
} from "./adapters/mapCockpitWarningsToHomeRisk";
import { mapHomeRiskRadar } from "./adapters/mapHomeRiskRadar";
import { mapPortfolioComparisonToExposureRows } from "./adapters/mapPortfolioComparisonToExposureRows";
import { mapMarketTape, type HomeMarketTicker } from "./dashboardHomeMarket";
import { todayIsoDate as resolveTodayIsoDate } from "../pages/dashboardPageHelpers";

export type HomeDeltaTone = "up" | "down" | "flat" | "muted" | "warn";

export type HomeKpiCard = {
  id: string;
  label: string;
  value: string;
  unit?: string;
  delta: string;
  deltaTone: HomeDeltaTone;
  sparkline: readonly number[];
  pending?: boolean;
};

export type HomeRiskMini = {
  id: string;
  label: string;
  value: string;
  unit?: string;
  foot: string;
  footTone: HomeDeltaTone;
};

export type HomeAiJudge = {
  conclusion: string;
  healthLabel: string;
  healthScore: number;
  healthTone: "green" | "amber" | "red";
  impact: string;
  sparkline: readonly number[];
};

export type HomePortfolioStat = { id: string; label: string; value: string };
export type HomeAssetBar = {
  id: string;
  label: string;
  pct: number;
  value: string;
  fillClass: "blue" | "redish" | "greenish" | "grey";
};

export type HomeRiskRadar = {
  dimensions: readonly string[];
  values: readonly number[];
  placeholder: boolean;
};
export type HomeInterbank = {
  assets: string;
  liabilities: string;
  net: string;
  netTone: HomeDeltaTone;
};

export type HomeAttributionTab = {
  id: "day" | "week" | "month" | "ytd";
  label: string;
  pnl: string;
  change: string;
  yield: string;
  changeTone: HomeDeltaTone;
};

export type HomeRiskCard = { id: string; label: string; count: number; tone: HomeDeltaTone };
export type HomeTodo = { id: string; title: string; priority: "高" | "中" | "低" };
export type HomeWatchItem = { id: string; label: string; count: string };

export type HomeExposureRow = {
  id: string;
  account: string;
  type: string;
  assetScale: string;
  weight: string;
  duration: string;
  dv01: string;
  dailyPnl: string;
  tone: "positive" | "negative" | "neutral";
};

export type HomeBalanceMetric = {
  id: string;
  label: string;
  value: string;
  delta?: string;
  deltaTone?: HomeDeltaTone;
  placeholder?: boolean;
};

export type HomeQuickDrill = {
  id: string;
  label: string;
  icon: string;
  path: string;
};

export type HomeDataStateKind = "ready" | "partial" | "empty" | "loading" | "error" | "stale" | "backend-gap";

export type HomeTerminalKpi = {
  id: string;
  label: string;
  value: string;
  unit?: string;
  delta: string;
  deltaTone: HomeDeltaTone;
  sparkline: readonly number[];
  state: HomeDataStateKind;
};

export type HomeRiskTicker = {
  id: string;
  label: string;
  value: string;
  delta: string;
  deltaTone: HomeDeltaTone;
};

export type HomeHoldingRow = {
  id: string;
  code: string;
  name: string;
  assetClass: string;
  marketValue: string;
  weight: string;
  ytm: string;
  duration: string;
  rating: string;
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
};

export type HomeTerminalListState = {
  kind: HomeDataStateKind;
  label: string;
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

export type HomeBackendGap = {
  id: string;
  title: string;
  neededEndpoint: string;
  reason: string;
};

export type HomeDecisionRail = {
  conclusion: string;
  maxDragLabel: string;
  maxDragValue: string;
  maxContributionLabel: string;
  maxContributionValue: string;
  keyRisk: string;
  suggestions: readonly string[];
  pendingSummary: string;
  reportDate: string;
  dataUpdatedAt: string;
  dataSyncPrefix: string;
};

export type HomeHeaderStatus = {
  dataStatusKind: "ok" | "stale" | "error";
  dataUpdatedAt: string;
  marketStatus: string;
  valuationLabel: string;
  valuationTone: "ok" | "warn";
  riskReviewCount: number;
  showRiskReview: boolean;
  dataSyncPrefix: string;
};

export type DashboardHomeView = {
  reportDate: string;
  useMockFallback: boolean;
  headerStatus: HomeHeaderStatus;
  aiJudge: HomeAiJudge;
  coreKpis: readonly HomeKpiCard[];
  riskMinis: readonly HomeRiskMini[];
  marketTape: readonly HomeMarketTicker[];
  portfolioStats: readonly HomePortfolioStat[];
  assetBars: readonly HomeAssetBar[];
  assetBarsPlaceholder: boolean;
  centerAum: { label: string; value: string };
  interbank: HomeInterbank;
  attributionTabs: readonly HomeAttributionTab[];
  attributionWaterfall: readonly HomeWaterfallItem[];
  attributionInsights: {
    maxDragLabel: string;
    maxDragValue: string;
    maxContributionLabel: string;
    maxContributionValue: string;
  };
  attributionNote: readonly string[];
  riskCards: readonly HomeRiskCard[];
  riskCardsPlaceholder: boolean;
  riskRadar: HomeRiskRadar;
  todos: readonly HomeTodo[];
  watchlist: readonly HomeWatchItem[];
  watchlistPlaceholder: boolean;
  exposureRows: readonly HomeExposureRow[];
  balanceMetrics: readonly HomeBalanceMetric[];
  quickDrilldowns: readonly HomeQuickDrill[];
  researchCalendar: HomeResearchCalendarModel;
  macroBriefing: HomeMacroBriefingModel;
  marketContext: HomeMarketContextModel;
  liabilityWatchBasisNote: string | null;
  decisionRail: HomeDecisionRail;
  terminalKpis: readonly HomeTerminalKpi[];
  keyRiskStrip: readonly HomeRiskTicker[];
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
  riskExposureMetrics: readonly HomeRiskExposureMetric[];
  riskExposureState: HomeTerminalListState;
  positionChanges: readonly HomePositionChangeRow[];
  positionChangesState: HomeTerminalListState;
  researchReports: readonly HomeResearchReportRow[];
  researchReportsState: HomeTerminalListState;
  incomeTrend: readonly HomeIncomeTrendRow[];
  incomeTrendState: HomeTerminalListState;
  backendGaps: readonly HomeBackendGap[];
};

export type MapToHomeViewInput = {
  reportDate: string;
  useMockFallback: boolean;
  verdict: VerdictPayload | null;
  metrics: readonly DashboardOverviewMetricVM[];
  attribution: DashboardPnlAttributionVM | null;
  coreMetrics: CoreMetricsResult | null;
  dailyChanges: DailyChangesResult | null;
  bondHeadline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  portfolioComparison: PortfolioComparisonPayload | null;
  creditSpreadMigration: CreditSpreadMigrationPayload | null;
  returnDecomposition: ReturnDecompositionPayload | null;
  campisiFourEffects: CampisiFourEffectsPayload | null;
  yieldCurveTermStructure: YieldCurveTermStructurePayload | null;
  decisionItems: readonly BalanceAnalysisDecisionItemStatusRow[] | null;
  marketPoints: readonly import("../../../api/contracts").ChoiceMacroLatestPoint[] | null;
  productCategoryYtd: ProductCategoryYtdHeadlinePayload | null;
  productCategoryMonthly: ProductCategoryMonthlyHeadlinePayload | null;
  assetStructure: AssetStructurePayload | null;
  ratingStructure: AssetStructurePayload | null;
  maturityStructure: MaturityStructurePayload | null;
  industryDistribution: IndustryDistPayload | null;
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
  cockpitWarnings: CockpitWarningsPayload | null;
  calendarEvents: readonly ResearchCalendarEvent[] | null;
  calendarLoading: boolean;
  calendarError: boolean;
  calendarStartDate: string;
  calendarEndDate: string;
  todayIsoDate?: string;
  macroNewsEvents?: readonly ChoiceNewsEvent[] | null;
  macroNewsFallbackEvents?: readonly ChoiceNewsEvent[] | null;
  macroNewsLoading?: boolean;
  macroNewsError?: boolean;
  snapshotMeta: ResultMeta | null;
  marketMeta: ResultMeta | null;
  alertCount: number;
  snapshotUnavailable: boolean;
  snapshotStale: boolean;
};

const GAP = "—";
type NumericLike = Numeric | string | number | null | undefined;
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

const BALANCE_METRIC_SPECS: ReadonlyArray<{
  id: string;
  label: string;
  metricIds: readonly string[];
}> = [
  { id: "assets", label: "总资产规模", metricIds: ["aum"] },
  { id: "ytd-pnl", label: "年度损益", metricIds: ["yield"] },
  { id: "nim", label: "净息差", metricIds: ["nim"] },
  { id: "capital", label: "资本占用", metricIds: [] },
  { id: "leverage", label: "杠杆率", metricIds: [] },
  { id: "liquidity", label: "流动性覆盖率", metricIds: [] },
  { id: "core-tier1", label: "核心一级资本充足率", metricIds: [] },
  { id: "rwa", label: "风险加权资产", metricIds: [] },
];

const DASHBOARD_HOME_BACKEND_GAPS: readonly HomeBackendGap[] = [
  {
    id: "research-reports",
    title: "研究报告列表",
    neededEndpoint: "GET /ui/home/research-reports?report_date=",
    reason: "参考图需要报告标题、日期和类型；现有首页只接入供给/招标日历，不能复用为研究报告。",
  },
  {
    id: "position-changes",
    title: "增减仓 TOP5",
    neededEndpoint: "GET /api/bond-analytics/position-changes?report_date=&top_n=5",
    reason: "现有 top-holdings 只有静态重仓券，没有较昨日增减仓金额和方向。",
  },
  {
    id: "income-trend-benchmark-excess",
    title: "收益趋势基准/超额",
    neededEndpoint: "GET /ui/home/income-trend?report_date=&window=7d",
    reason: "已接入组合月度收益序列；基准收益和超额收益暂无受管字段，不能前端补算。",
  },
  {
    id: "leverage-ratio",
    title: "杠杆率",
    neededEndpoint: "GET /ui/home/leverage?report_date=",
    reason: "现有债券风险指标没有组合杠杆口径，不能用资产规模或久期替代。",
  },
];

const ACTIVE_DASHBOARD_HOME_BACKEND_GAPS = DASHBOARD_HOME_BACKEND_GAPS.filter(
  (gap) => !["research-reports", "position-changes", "income-trend"].includes(gap.id),
);

/** 从 Numeric.display 尾部剥离单位，避免与 Hero 硬编码单位叠加。 */
export function stripDisplayUnit(display: string): { value: string; unit: string } {
  const trimmed = display.trim();
  if (!trimmed || trimmed === GAP) {
    return { value: trimmed, unit: "" };
  }
  const spaced = trimmed.match(/^([+\-]?[\d,]+(?:\.\d+)?)\s*(亿|万|%|bp|pp)$/);
  if (spaced) {
    return { value: spaced[1]!, unit: spaced[2]! };
  }
  const tight = trimmed.match(/^([+\-]?[\d,]+(?:\.\d+)?)(%|bp|pp)$/);
  if (tight) {
    return { value: tight[1]!, unit: tight[2]! };
  }
  return { value: trimmed, unit: "" };
}

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

function numericRawInYuan(value: NumericLike): number | null {
  const parsed = numericRaw(value);
  if (parsed == null || value == null) {
    return null;
  }
  if (!isNumericObject(value)) {
    return null;
  }
  if (value.unit === "yi") {
    return parsed * 100_000_000;
  }
  if (value.unit === "yuan") {
    return parsed;
  }
  return null;
}

function formatYi(rawYuan: number, signAware: boolean): string {
  const yi = rawYuan / 100_000_000;
  const formatted = yi.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${signAware && yi >= 0 ? "+" : ""}${formatted} 亿`;
}

function formatYiSigned(rawYuan: number): string {
  return formatYi(rawYuan, true);
}

function formatWanSigned(rawYuan: number): string {
  const wan = rawYuan / 10_000;
  return `${wan >= 0 ? "+" : ""}${wan.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
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

function resolveInterbankNetTone(netRawYuan: number | null): HomeDeltaTone {
  if (netRawYuan == null) {
    return "flat";
  }
  if (netRawYuan < 0) {
    return "up";
  }
  if (netRawYuan > 0) {
    return "down";
  }
  return "flat";
}

function buildNumericDeltaFoot(
  current: Numeric | null | undefined,
  prev: Numeric | null | undefined,
  options: {
    riseLabel: string;
    fallLabel: string;
    suffix: string;
    decimals: number;
  },
): { foot: string; footTone: HomeDeltaTone } {
  const currRaw = numericRaw(current);
  const prevRaw = numericRaw(prev);
  if (currRaw == null || prevRaw == null) {
    return { foot: GAP, footTone: "flat" };
  }
  const delta = currRaw - prevRaw;
  if (Math.abs(delta) < 1e-9) {
    return { foot: GAP, footTone: "flat" };
  }
  const sign = delta > 0 ? "+" : "";
  const formatted = `${sign}${delta.toFixed(options.decimals)}`;
  const label = delta > 0 ? options.riseLabel : options.fallLabel;
  const suffix = options.suffix.length > 0 ? ` ${options.suffix}` : "";
  return {
    foot: `${label}\n${formatted}${suffix}`,
    footTone: delta > 0 ? "warn" : "down",
  };
}

function splitNumericDisplay(value: NumericLike, fallback = GAP, unitHint?: string): {
  value: string;
  unit?: string;
} {
  const display = numericDisplay(value, fallback, unitHint);
  const stripped = stripDisplayUnit(display);
  return {
    value: stripped.value,
    unit: stripped.unit || undefined,
  };
}

function cleanDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const a = cleanDate(expected);
  const b = cleanDate(actual);
  return a.length > 0 && b.length > 0 && a === b;
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

function buildFormalAttributionExtremes(input: {
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  returnDecomposition: ReturnDecompositionPayload | null | undefined;
}): {
  maxDragLabel: string;
  maxDragValue: string;
  maxContributionLabel: string;
  maxContributionValue: string;
} | null {
  if (input.campisiFourEffects) {
    const totals = input.campisiFourEffects.totals;
    const components = [
      { label: "Carry/Income", raw: totals.income_return },
      { label: "利率曲线", raw: totals.treasury_effect },
      { label: "信用利差", raw: totals.spread_effect },
      { label: "个券选择/残差", raw: totals.selection_effect },
    ];
    const contribution = components.reduce<(typeof components)[number] | null>((best, item) => {
      if (!Number.isFinite(item.raw) || item.raw <= 0) {
        return best;
      }
      return best == null || item.raw > best.raw ? item : best;
    }, null);
    const drag = components.reduce<(typeof components)[number] | null>((best, item) => {
      if (!Number.isFinite(item.raw) || item.raw >= 0) {
        return best;
      }
      return best == null || item.raw < best.raw ? item : best;
    }, null);
    return {
      maxDragLabel: drag?.label ?? GAP,
      maxDragValue: drag ? formatYiSigned(drag.raw) : GAP,
      maxContributionLabel: contribution?.label ?? GAP,
      maxContributionValue: contribution ? formatYiSigned(contribution.raw) : GAP,
    };
  }
  const payload = input.returnDecomposition;
  if (!payload) return null;
  const components = [
    { label: "Carry/Income", value: payload.carry },
    { label: "利率曲线", value: payload.rate_effect },
    { label: "信用利差", value: payload.spread_effect },
    { label: "个券选择/残差", value: payload.trading },
  ];
  const contribution = components.reduce<(typeof components)[number] | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw <= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw > bestRaw ? item : best;
  }, null);
  const drag = components.reduce<(typeof components)[number] | null>((best, item) => {
    const raw = numericRaw(item.value);
    if (raw == null || raw >= 0) {
      return best;
    }
    const bestRaw = numericRaw(best?.value);
    return bestRaw == null || raw < bestRaw ? item : best;
  }, null);
  return {
    maxDragLabel: drag?.label ?? GAP,
    maxDragValue: drag ? numericValueOrGap(drag.value, "yuan") : GAP,
    maxContributionLabel: contribution?.label ?? GAP,
    maxContributionValue: contribution ? numericValueOrGap(contribution.value, "yuan") : GAP,
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

function numericDeltaDisplay(
  current: NumericLike,
  previous: NumericLike,
): { delta: string; tone: HomeDeltaTone } {
  const currentRaw = numericRaw(current);
  const previousRaw = numericRaw(previous);
  if (currentRaw == null || previousRaw == null) {
    return { delta: GAP, tone: "muted" };
  }
  const delta = currentRaw - previousRaw;
  if (Math.abs(delta) < 1e-9) {
    return { delta: "较前日 持平", tone: "flat" };
  }
  const sign = delta > 0 ? "+" : "";
  const unit = isNumericObject(current)
    ? current.unit
    : isNumericObject(previous)
      ? previous.unit
      : undefined;
  const formatted =
    unit === "yuan"
      ? formatYiSigned(delta)
      : unit === "pct"
        ? `${sign}${(delta * 100).toFixed(2)}%`
        : `${sign}${delta.toFixed(2)}`;
  return {
    delta: `较前日 ${formatted}`,
    tone: delta > 0 ? "up" : "down",
  };
}

function metricToneToDelta(tone: DashboardOverviewMetricVM["tone"]): HomeDeltaTone {
  if (tone === "positive") return "up";
  if (tone === "negative") return "down";
  if (tone === "warning") return "warn";
  return "flat";
}

function findMetric(
  metrics: readonly DashboardOverviewMetricVM[],
  ids: readonly string[],
): DashboardOverviewMetricVM | undefined {
  return metrics.find((metric) => ids.includes(metric.id));
}

function flatSparkline(value: number, length = 12): readonly number[] {
  return Array.from({ length }, () => value);
}

function buildSparklineFromHistory(history: number[] | null, fallback: readonly number[]): readonly number[] {
  if (history && history.length > 1) {
    return history;
  }
  return fallback;
}

function mapStructureSlices<T extends {
  total_market_value: Numeric;
  percentage: Numeric | null;
}>(
  payload: { report_date: string; items: readonly T[] } | null | undefined,
  expectedReportDate: string,
  getLabel: (item: T) => string,
  emptyLabel: string,
): { slices: HomeDistributionSlice[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, emptyLabel);
  if (state.kind !== "ready" || !payload?.items?.length) {
    return {
      slices: [],
      state: payload?.items?.length ? state : displayState("empty", emptyLabel),
    };
  }
  return {
    state,
    slices: payload.items.slice(0, 8).map((item, index) => ({
      id: `${getLabel(item) || "slice"}-${index}`,
      label: getLabel(item) || GAP,
      value: numericValueOrGap(item.total_market_value, "yuan"),
      pct: numericValueOrGap(item.percentage, "pct"),
      pctRaw: percentageRaw(item.percentage),
    })),
  };
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
      weight: numericValueOrGap(item.weight, "pct"),
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
      state: payload?.items.length ? state : displayState("empty", "增减仓暂无数据"),
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

function buildResearchReportRows(
  payload: HomeResearchReportsPayload | null | undefined,
  expectedReportDate: string,
): { rows: HomeResearchReportRow[]; state: HomeTerminalListState } {
  void expectedReportDate;
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
      publishedAt: item.published_at.slice(0, 10) || GAP,
      source: item.source.trim() || GAP,
      institution: item.institution?.trim() || GAP,
      summary: item.summary?.trim() || GAP,
      link: item.link,
      isNewsFallback: false,
    })),
  };
}

function isHomeResearchReportRelevant(item: HomeResearchReportsPayload["items"][number]): boolean {
  const haystack = `${item.title} ${item.category} ${item.institution ?? ""}`.toLowerCase();
  return HOME_RESEARCH_REPORT_FOCUS_TERMS.some((term) => haystack.includes(term));
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
    state: displayState("partial", "研报源暂无 · 新闻补位"),
    rows: newsItems.slice(0, 5).map((item) => ({
      id: `macro-news-${item.id}`,
      title: item.title,
      category: `新闻补位 · ${item.topicLabel}`,
      publishedAt: item.timeLabel,
      source,
      institution: source,
      summary: `${source} · ${item.freshnessLabel}`,
      link: null,
      isNewsFallback: true,
    })),
  };
}

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
  const missingValueLabel = incomeTrendMissingValueLabel(gapLabel);
  const mappedState =
    payload.source_status === "partial"
      ? displayState("partial", gapLabel)
      : payload.source_status === "stale"
        ? displayState("stale", "收益趋势数据过期")
        : displayState("ready", "已接入");
  return {
    state: mappedState,
    rows: payload.points.map((point) => {
      const benchmarkRaw = numericRaw(point.benchmark_pnl);
      const excessRaw = numericRaw(point.excess_pnl);
      return {
        id: point.date,
        date: point.date,
        portfolioPnl: numericValueOrGap(point.portfolio_pnl, "yuan"),
        benchmarkPnl: benchmarkRaw == null ? missingValueLabel : numericValueOrGap(point.benchmark_pnl, "yuan"),
        excessPnl: excessRaw == null ? missingValueLabel : numericValueOrGap(point.excess_pnl, "yuan"),
        portfolioRaw: numericRaw(point.portfolio_pnl),
        benchmarkRaw,
        excessRaw,
      };
    }),
  };
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

function localizeIncomeTrendComponent(component: string): string {
  if (component === "benchmark_pnl") return "基准PnL";
  if (component === "excess_pnl") return "超额PnL";
  if (component === "portfolio_pnl") return "组合PnL";
  return component;
}

function incomeTrendMissingValueLabel(gapLabel: string): string {
  if (gapLabel.includes("CDB_INDEX")) {
    return "缺CDB_INDEX";
  }
  if (gapLabel.includes("benchmark_return")) {
    return "缺收益率";
  }
  if (gapLabel.includes("基准PnL") || gapLabel.includes("超额PnL")) {
    return "缺PnL";
  }
  return "缺数据";
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

function buildRiskExposureMetrics(
  payload: RiskIndicatorsPayload | null | undefined,
  expectedReportDate: string,
): { metrics: HomeRiskExposureMetric[]; state: HomeTerminalListState } {
  const state = reportDateState(expectedReportDate, payload?.report_date, "风险指标暂无数据");
  if (state.kind !== "ready" || !payload) {
    return { metrics: [], state };
  }
  return {
    state,
    metrics: [
      { id: "dv01", label: "利率风险 DV01", value: numericValueOrGap(payload.total_dv01, "dv01") },
      { id: "duration", label: "加权久期", value: numericValueOrGap(payload.weighted_duration, "ratio") },
      { id: "credit", label: "信用占比", value: numericValueOrGap(payload.credit_ratio, "ratio") },
      { id: "convexity", label: "加权凸性", value: numericValueOrGap(payload.weighted_convexity, "ratio") },
      { id: "spread-dv01", label: "利差 DV01", value: numericValueOrGap(payload.total_spread_dv01, "dv01") },
      { id: "reinvestment", label: "1年再投资", value: numericValueOrGap(payload.reinvestment_ratio_1y, "ratio") },
    ],
  };
}

function terminalKpiFromNumeric(args: {
  id: string;
  label: string;
  value: NumericLike;
  previous?: NumericLike;
  sparkline: readonly number[];
  state?: HomeDataStateKind;
  unitHint?: string;
}): HomeTerminalKpi {
  const split = splitNumericDisplay(args.value, GAP, args.unitHint);
  const delta = numericDeltaDisplay(args.value, args.previous);
  return {
    id: args.id,
    label: args.label,
    value: split.value,
    unit: split.unit,
    delta: delta.delta,
    deltaTone: delta.tone,
    sparkline: args.sparkline,
    state: args.value ? args.state ?? "ready" : "empty",
  };
}

function buildTerminalKpis(args: {
  aumMetric: DashboardOverviewMetricVM | undefined;
  headline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  attribution: DashboardPnlAttributionVM | null;
  riskIndicators: RiskIndicatorsPayload | null;
  riskState: HomeTerminalListState;
}): HomeTerminalKpi[] {
  const totalMarketValue =
    args.headline?.kpis.total_market_value ?? args.portfolio?.total_market_value ?? args.aumMetric?.value;
  const previousMarketValue = args.headline?.prev_kpis?.total_market_value;
  const duration =
    args.riskIndicators?.weighted_duration ??
    args.headline?.kpis.weighted_duration ??
    args.portfolio?.weighted_duration;
  const ytm = args.headline?.kpis.weighted_ytm ?? args.portfolio?.weighted_ytm;
  const creditRatio = args.riskIndicators?.credit_ratio ?? args.portfolio?.credit_weight;
  const riskMetricState = args.riskState.kind === "ready" ? "ready" : args.riskState.kind;

  return [
    terminalKpiFromNumeric({
      id: "aum",
      label: "组合市值",
      value: totalMarketValue,
      previous: previousMarketValue,
      sparkline: buildSparklineFromHistory(args.aumMetric?.history ?? null, flatSparkline(1)),
      unitHint: "yuan",
    }),
    terminalKpiFromNumeric({
      id: "bond-market-value",
      label: "债券市值",
      value: args.headline?.kpis.total_market_value,
      previous: args.headline?.prev_kpis?.total_market_value,
      sparkline: flatSparkline(1.2),
      unitHint: "yuan",
    }),
    terminalKpiFromNumeric({
      id: "unrealized-pnl",
      label: "持仓收益（当日）",
      value: args.headline?.kpis.unrealized_pnl,
      previous: args.headline?.prev_kpis?.unrealized_pnl,
      sparkline: flatSparkline(0.8),
      unitHint: "yuan",
    }),
    terminalKpiFromNumeric({
      id: "day-pnl",
      label: "今日盈亏（当日）",
      value: args.attribution?.total,
      sparkline: flatSparkline(0.9),
      unitHint: "yuan",
    }),
    terminalKpiFromNumeric({
      id: "duration",
      label: "加权久期",
      value: duration,
      previous: args.headline?.prev_kpis?.weighted_duration,
      sparkline: flatSparkline(1.05),
      state: args.riskIndicators ? riskMetricState : undefined,
      unitHint: "ratio",
    }),
    terminalKpiFromNumeric({
      id: "ytm",
      label: "组合YTM",
      value: ytm,
      previous: args.headline?.prev_kpis?.weighted_ytm,
      sparkline: flatSparkline(1.1),
      unitHint: "pct",
    }),
    terminalKpiFromNumeric({
      id: "credit-ratio",
      label: "信用占比",
      value: creditRatio,
      sparkline: flatSparkline(0.95),
      state: args.riskIndicators ? riskMetricState : undefined,
      unitHint: "ratio",
    }),
  ];
}

function buildKeyRiskStrip(
  marketTape: readonly HomeMarketTicker[],
  riskIndicators: RiskIndicatorsPayload | null,
): HomeRiskTicker[] {
  const riskTickers: HomeRiskTicker[] = riskIndicators
    ? [
        {
          id: "risk-dv01",
          label: "组合DV01",
          value: numericValueOrGap(riskIndicators.total_dv01, "dv01"),
          delta: "现值",
          deltaTone: "flat",
        },
        {
          id: "risk-duration",
          label: "久期",
          value: numericValueOrGap(riskIndicators.weighted_duration, "ratio"),
          delta: "现值",
          deltaTone: "flat",
        },
        {
          id: "spread-dv01",
          label: "利差DV01",
          value: numericValueOrGap(riskIndicators.total_spread_dv01, "dv01"),
          delta: "现值",
          deltaTone: "flat",
        },
      ]
    : [];

  return [
    ...riskTickers,
    ...marketTape.slice(0, Math.max(0, 8 - riskTickers.length)).map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone,
    })),
  ];
}

function buildMockView(): DashboardHomeView {
  const waterfall = DASHBOARD_ATTRIBUTION_WATERFALL_MOCK.map((item) => ({
    id: item.id,
    label: item.label,
    value: item.value,
    tone: item.tone,
  }));
  const extremes = findAttributionExtremes(waterfall);
  const researchCalendar: HomeResearchCalendarModel = {
    items: [],
    status: "ready",
    windowLabel: "—",
    message: null,
  };
  const macroBriefing = buildHomeMacroBriefingModel({
    todayIsoDate: resolveTodayIsoDate(),
    newsEvents: null,
    newsLoading: false,
    newsError: false,
    supplyCalendar: researchCalendar,
  });
  const marketContext = buildHomeMarketContextModel({
    marketTape: DASHBOARD_MARKET_PULSE_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone,
      sparkline: item.sparkline,
    })),
    marketPoints: null,
    macroNewsEvents: null,
    todayIsoDate: resolveTodayIsoDate(),
    campisiFourEffects: null,
    returnDecomposition: null,
    yieldCurveTermStructure: null,
    creditSpreadMigration: null,
    attribution: {
      maxDragLabel: extremes.maxDrag?.label ?? GAP,
      maxContributionLabel: extremes.maxContribution?.label ?? GAP,
    },
  });

  return {
    reportDate: DASHBOARD_COCKPIT_REPORT_DATE,
    useMockFallback: true,
    headerStatus: {
      dataStatusKind: "ok",
      dataUpdatedAt: DASHBOARD_COCKPIT_HEADER_STATUS.dataUpdatedAt,
      marketStatus: DASHBOARD_COCKPIT_HEADER_STATUS.marketStatus,
      valuationLabel: "估值已完成",
      valuationTone: "ok",
      riskReviewCount: 3,
      showRiskReview: true,
      dataSyncPrefix: "数据已更新",
    },
    aiJudge: {
      conclusion:
        "利率上行拖累估值，信用利差收窄提供对冲，组合久期小幅上升，需关注 Top5 集中度和久期超限账户。",
      healthLabel: "良好",
      healthScore: 72,
      healthTone: "green",
      impact: "较昨日 -2　　主要受利率变动影响",
      sparkline: [63, 61, 53, 56, 57, 43, 11, 17, 45, 10],
    },
    coreKpis: [
      {
        id: "aum",
        label: "债券资产规模",
        value: "3,708.10",
        unit: "亿",
        delta: "较昨日 +22.30 亿  +0.61%",
        deltaTone: "down",
        sparkline: [3650, 3668, 3680, 3695, 3700, 3705, 3706, 3707, 3708, 3707.5, 3708, 3708.1],
      },
      {
        id: "yield",
        label: "年度损益",
        value: "+29.71",
        delta: "较昨日 +1.82 亿",
        deltaTone: "down",
        sparkline: [18, 20, 22, 24, 26, 27, 28, 28.5, 29, 29.3, 29.5, 29.71],
      },
      {
        id: "nim",
        label: "净息差",
        value: "1.76",
        unit: "%",
        delta: "较昨日 +0.02bp",
        deltaTone: "up",
        sparkline: [12, 14, 10, 17, 13, 18, 17, 13, 16],
      },
    ],
    riskMinis: [
      {
        id: "dv01",
        label: "组合DV01",
        value: "10,615.59",
        unit: "万",
        foot: "敞口下降\n-4.97 万",
        footTone: "down",
      },
      {
        id: "duration",
        label: "久期（年）",
        value: "4.14",
        foot: "风险上升\n+0.01",
        footTone: "up",
      },
      {
        id: "concentration",
        label: "风险集中度\n(Top5)",
        value: "41.35",
        unit: "%",
        foot: "风险上升\n+0.22pp",
        footTone: "up",
      },
    ],
    marketTape: DASHBOARD_MARKET_PULSE_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone === "up" ? "up" : item.deltaTone === "down" ? "down" : "flat",
      sparkline: item.sparkline,
    })),
    portfolioStats: DASHBOARD_PORTFOLIO_STATS_MOCK.map((stat) => ({ ...stat })),
    assetBars: DASHBOARD_ASSET_BARS_MOCK.map((bar, index) => ({
      id: bar.id,
      label: bar.label,
      pct: bar.pct,
      value: bar.value,
      fillClass: (["blue", "redish", "greenish", "grey"] as const)[index % 4]!,
    })),
    assetBarsPlaceholder: false,
    centerAum: { label: "总资产（账面）", value: "3,708.10 亿" },
    interbank: {
      assets: DASHBOARD_INTERBANK_MOCK.assets,
      liabilities: DASHBOARD_INTERBANK_MOCK.liabilities,
      net: DASHBOARD_INTERBANK_MOCK.netPosition,
      netTone: "up",
    },
    attributionTabs: [
      { id: "day", label: "日度", pnl: "-368.09 万", change: "-223.30 万", yield: "-0.10bp", changeTone: "up" },
      { id: "week", label: "周度", pnl: GAP, change: GAP, yield: GAP, changeTone: "flat" },
      { id: "month", label: "月度", pnl: "+6,428.31 万", change: "+1,032.45 万", yield: "+1.73bp", changeTone: "down" },
      { id: "ytd", label: "YTD", pnl: GAP, change: GAP, yield: GAP, changeTone: "flat" },
    ],
    attributionWaterfall: waterfall,
    attributionInsights: {
      maxDragLabel: extremes.maxDrag?.label ?? "利率变动",
      maxDragValue: extremes.maxDrag?.value ?? "-512.34 万",
      maxContributionLabel: extremes.maxContribution?.label ?? "信用利差",
      maxContributionValue: extremes.maxContribution?.value ?? "+286.21 万",
    },
    attributionNote: [...DASHBOARD_ATTRIBUTION_NOTE_MOCK],
    riskCards: DASHBOARD_RISK_ALERT_COUNTS_MOCK.map((card) => ({
      id: card.id,
      label: card.label.replace("预警", ""),
      count: card.count,
      tone: card.tone === "warn" ? "warn" : card.tone === "down" ? "down" : "flat",
    })),
    riskCardsPlaceholder: false,
    riskRadar: {
      dimensions: [...DASHBOARD_RISK_RADAR_MOCK.dimensions],
      values: [...DASHBOARD_RISK_RADAR_MOCK.values],
      placeholder: false,
    },
    todos: DASHBOARD_RISK_TODOS_MOCK.map((todo) => ({
      id: todo.id,
      title: todo.title,
      priority: todo.priority as HomeTodo["priority"],
    })),
    watchlist: DASHBOARD_WATCHLIST_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      count: item.count,
    })),
    watchlistPlaceholder: false,
    exposureRows: DASHBOARD_EXPOSURE_ROWS_MOCK.map((row) => ({
      id: row.id,
      account: row.account,
      type: row.type,
      assetScale: row.assetScale,
      weight: row.weight,
      duration: row.duration,
      dv01: row.dv01,
      dailyPnl: row.dailyPnl,
      tone: row.tone === "positive" ? "positive" : row.tone === "negative" ? "negative" : "neutral",
    })),
    balanceMetrics: DASHBOARD_BALANCE_METRICS_MOCK.map((metric) => ({
      id: metric.id,
      label: metric.label,
      value: metric.value,
      delta: metric.delta,
      deltaTone:
        metric.tone === "positive"
          ? "down"
          : metric.tone === "negative"
            ? "up"
            : "flat",
    })),
    quickDrilldowns: DASHBOARD_QUICK_DRILLDOWN_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      icon: item.id,
      path: item.path,
    })),
    researchCalendar,
    macroBriefing,
    marketContext,
    liabilityWatchBasisNote: null,
    decisionRail: {
      conclusion:
        "组合亏损主要由利率上行导致，信用利差收窄形成部分对冲，组合久期略有上升，需关注集中度风险。",
      maxDragLabel: "利率变动",
      maxDragValue: "-512.34 万",
      maxContributionLabel: "信用利差",
      maxContributionValue: "+286.21 万",
      keyRisk: "Top5 集中度 41.35%，久期小幅上升。",
      suggestions: [
        "优先复核久期超限账户",
        "关注 Top5 主体敞口",
        "跟踪利率曲线陡峭化风险",
      ],
      pendingSummary: "4 项，其中高优先级 1 项",
      reportDate: DASHBOARD_COCKPIT_REPORT_DATE,
      dataUpdatedAt: DASHBOARD_COCKPIT_HEADER_STATUS.dataUpdatedAt,
      dataSyncPrefix: "数据已更新",
    },
    terminalKpis: [
      {
        id: "aum",
        label: "组合市值",
        value: "3,708.10",
        unit: "亿",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [3650, 3668, 3680, 3695, 3700, 3705, 3706, 3708],
        state: "ready",
      },
      {
        id: "bond-market-value",
        label: "债券市值",
        value: "3,708.10",
        unit: "亿",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [3600, 3620, 3655, 3660, 3678, 3688, 3708],
        state: "ready",
      },
      {
        id: "unrealized-pnl",
        label: "持仓收益（当日）",
        value: "+18.42",
        unit: "亿",
        delta: "样例模式",
        deltaTone: "up",
        sparkline: [8, 11, 10, 13, 15, 18],
        state: "ready",
      },
      {
        id: "day-pnl",
        label: "今日盈亏（当日）",
        value: "+0.85",
        unit: "亿",
        delta: "样例模式",
        deltaTone: "up",
        sparkline: [0.2, 0.3, 0.4, 0.5, 0.85],
        state: "ready",
      },
      {
        id: "duration",
        label: "加权久期",
        value: "4.23",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [4.1, 4.12, 4.18, 4.23],
        state: "ready",
      },
      {
        id: "ytm",
        label: "组合YTM",
        value: "2.3684",
        unit: "%",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [2.3, 2.33, 2.35, 2.36],
        state: "ready",
      },
      {
        id: "credit-ratio",
        label: "信用占比",
        value: "92.36",
        unit: "%",
        delta: "样例模式",
        deltaTone: "flat",
        sparkline: [91, 92, 91.8, 92.36],
        state: "ready",
      },
    ],
    keyRiskStrip: DASHBOARD_MARKET_PULSE_MOCK.slice(0, 8).map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone === "up" ? "up" : item.deltaTone === "down" ? "down" : "flat",
    })),
    holdingRows: [],
    holdingsState: displayState("backend-gap", "样例模式不展示正式重仓券"),
    assetDistribution: DASHBOARD_ASSET_BARS_MOCK.slice(0, 5).map((bar) => ({
      id: bar.id,
      label: bar.label,
      value: bar.value,
      pct: `${bar.pct.toFixed(2)}%`,
      pctRaw: bar.pct,
    })),
    assetDistributionState: displayState("ready", "样例模式"),
    ratingDistribution: DASHBOARD_ASSET_BARS_MOCK.slice(0, 5).map((bar) => ({
      id: bar.id,
      label: bar.label,
      value: bar.value,
      pct: `${bar.pct.toFixed(2)}%`,
      pctRaw: bar.pct,
    })),
    ratingDistributionState: displayState("ready", "样例模式"),
    maturityDistribution: [],
    maturityDistributionState: displayState("backend-gap", "样例模式未提供期限结构"),
    industryDistribution: DASHBOARD_ASSET_BARS_MOCK.slice(0, 5).map((bar) => ({
      id: `industry-${bar.id}`,
      label: bar.label,
      value: bar.value,
      pct: `${bar.pct.toFixed(2)}%`,
      pctRaw: bar.pct,
    })),
    industryDistributionState: displayState("ready", "样例模式"),
    riskExposureMetrics: [
      { id: "dv01", label: "利率风险 DV01", value: "10,615.59 万" },
      { id: "duration", label: "加权久期", value: "4.14" },
      { id: "credit", label: "信用占比", value: "41.35%" },
      { id: "spread-dv01", label: "利差 DV01", value: "—" },
    ],
    riskExposureState: displayState("ready", "样例模式"),
    positionChanges: [],
    positionChangesState: displayState("empty", "样例模式暂无增减仓"),
    researchReports: [],
    researchReportsState: displayState("empty", "样例模式暂无研究报告"),
    incomeTrend: [],
    incomeTrendState: displayState("empty", "样例模式暂无收益趋势"),
    backendGaps: ACTIVE_DASHBOARD_HOME_BACKEND_GAPS,
  };
}

function segmentsToWaterfall(attribution: DashboardPnlAttributionVM | null): HomeWaterfallItem[] {
  if (!attribution?.segments?.length) {
    return [];
  }
  return attribution.segments.map((segment) => ({
    id: segment.id,
    label: segment.label,
    value: segment.amount.display,
    tone:
      segment.tone === "positive"
        ? "positive"
        : segment.tone === "negative"
          ? "negative"
          : segment.tone === "warning"
            ? "warning"
            : "neutral",
  }));
}

function waterfallTone(raw: number): HomeWaterfallItem["tone"] {
  if (raw > 0) return "positive";
  if (raw < 0) return "negative";
  return "neutral";
}

function rawYuanFromNumeric(value: NumericLike): number | null {
  const raw = numericRaw(value);
  return raw == null ? null : raw;
}

function formalAttributionWaterfallItem(
  id: string,
  label: string,
  raw: number | null,
): HomeWaterfallItem | null {
  if (raw == null || !Number.isFinite(raw)) {
    return null;
  }
  return {
    id,
    label,
    value: formatWanSigned(raw),
    tone: waterfallTone(raw),
  };
}

function buildFormalAttributionWaterfall(input: {
  campisiFourEffects: CampisiFourEffectsPayload | null | undefined;
  returnDecomposition: ReturnDecompositionPayload | null | undefined;
}): HomeWaterfallItem[] {
  if (input.campisiFourEffects) {
    const totals = input.campisiFourEffects.totals;
    return [
      formalAttributionWaterfallItem("formal-carry-income", "Carry/Income", totals.income_return),
      formalAttributionWaterfallItem("formal-rate-curve", "利率曲线", totals.treasury_effect),
      formalAttributionWaterfallItem("formal-credit-spread", "信用利差", totals.spread_effect),
      formalAttributionWaterfallItem("formal-selection-residual", "个券选择/残差", totals.selection_effect),
    ].filter((item): item is HomeWaterfallItem => item != null);
  }
  const payload = input.returnDecomposition;
  if (!payload) {
    return [];
  }
  return [
    formalAttributionWaterfallItem("formal-carry-income", "Carry/Income", rawYuanFromNumeric(payload.carry)),
    formalAttributionWaterfallItem("formal-rate-curve", "利率曲线", rawYuanFromNumeric(payload.rate_effect)),
    formalAttributionWaterfallItem("formal-credit-spread", "信用利差", rawYuanFromNumeric(payload.spread_effect)),
    formalAttributionWaterfallItem("formal-selection-residual", "个券选择/残差", rawYuanFromNumeric(payload.trading)),
  ].filter((item): item is HomeWaterfallItem => item != null);
}

function marketContextBlockById(
  marketContext: HomeMarketContextModel,
  id: HomeMarketContextModel["contextBlocks"][number]["id"],
) {
  return marketContext.contextBlocks.find((block) => block.id === id) ?? null;
}

function isDecisionUsableMarketBlock(
  block: HomeMarketContextModel["contextBlocks"][number] | null,
): block is HomeMarketContextModel["contextBlocks"][number] {
  if (!block) {
    return false;
  }
  return !/等待|未收到/.test(`${block.title} ${block.detail}`);
}

function buildDecisionRailConclusion(
  verdict: VerdictPayload | null | undefined,
  marketContext: HomeMarketContextModel,
): string {
  const parts = [
    marketContextBlockById(marketContext, "pnl")?.title,
    marketContextBlockById(marketContext, "curve")?.title,
    marketContextBlockById(marketContext, "credit")?.title,
  ].filter((item): item is string => Boolean(item && !/等待|未收到/.test(item)));
  if (parts.length > 0) {
    return parts.slice(0, 3).join("；");
  }
  return verdict?.conclusion?.trim() || "数据待同步";
}

function buildDecisionRailKeyRisk(
  verdict: VerdictPayload | null | undefined,
  marketContext: HomeMarketContextModel,
): string {
  const credit = marketContextBlockById(marketContext, "credit");
  if (isDecisionUsableMarketBlock(credit)) {
    return `${credit.label}：${credit.detail}`;
  }
  const curve = marketContextBlockById(marketContext, "curve");
  if (isDecisionUsableMarketBlock(curve)) {
    return `${curve.label}：${curve.detail}`;
  }
  return verdict?.reasons?.[0]?.label ?? GAP;
}

function buildDecisionRailSuggestions(
  verdictSuggestions: readonly string[],
  marketContext: HomeMarketContextModel,
): string[] {
  const pnl = marketContextBlockById(marketContext, "pnl");
  const curve = marketContextBlockById(marketContext, "curve");
  const credit = marketContextBlockById(marketContext, "credit");
  const suggestions = [
    isDecisionUsableMarketBlock(pnl) ? `复核收益来源：${pnl.title}` : "",
    isDecisionUsableMarketBlock(curve) ? `关注曲线变化：${curve.title}` : "",
    isDecisionUsableMarketBlock(credit) ? `跟踪信用压力：${credit.title}` : "",
    ...verdictSuggestions,
  ].filter(Boolean);
  return suggestions.length > 0 ? suggestions.slice(0, 3) : ["数据待同步"];
}

function buildRealView(input: MapToHomeViewInput): DashboardHomeView {
  const reportDate = cleanDate(input.reportDate) || GAP;
  const dataStatusKind = input.snapshotUnavailable ? "error" : input.snapshotStale ? "stale" : "ok";
  const dataSyncPrefix = input.snapshotUnavailable
    ? "主快照不可用"
    : input.snapshotStale
      ? "展示上一版本"
      : "数据已更新";
  const dataUpdatedAt =
    input.snapshotUnavailable || input.snapshotStale
      ? reportDate
      : input.snapshotMeta?.generated_at?.slice(11, 16) ?? GAP;
  const aumMetric = findMetric(input.metrics, ["aum"]);
  const yieldMetric = findMetric(input.metrics, ["yield"]);
  const nimMetric = findMetric(input.metrics, ["nim"]);

  const headlineOk = isSameReportDate(reportDate, input.bondHeadline?.report_date);
  const portfolioOk = isSameReportDate(reportDate, input.portfolio?.report_date);
  const headline = headlineOk ? input.bondHeadline : null;
  const portfolio = portfolioOk ? input.portfolio : null;

  const formalWaterfall = buildFormalAttributionWaterfall({
    campisiFourEffects: input.campisiFourEffects,
    returnDecomposition: input.returnDecomposition,
  });
  const waterfall =
    formalWaterfall.length > 0 ? formalWaterfall : segmentsToWaterfall(input.attribution);
  const extremes = findAttributionExtremes(waterfall);
  const formalAttributionExtremes = buildFormalAttributionExtremes({
    campisiFourEffects: input.campisiFourEffects,
    returnDecomposition: input.returnDecomposition,
  });

  const coreKpis: HomeKpiCard[] = [
    {
      id: "aum",
      label: "债券资产规模",
      ...splitNumericDisplay(aumMetric?.value, GAP),
      delta: aumMetric ? `较昨日 ${numericDisplay(aumMetric.delta)}` : GAP,
      deltaTone: aumMetric ? metricToneToDelta(aumMetric.tone) : "muted",
      sparkline: buildSparklineFromHistory(aumMetric?.history ?? null, flatSparkline(3708)),
      pending: !aumMetric,
    },
    {
      id: "yield",
      label: "年度损益",
      ...splitNumericDisplay(yieldMetric?.value, GAP),
      delta: yieldMetric ? `较昨日 ${numericDisplay(yieldMetric.delta)}` : GAP,
      deltaTone: yieldMetric ? metricToneToDelta(yieldMetric.tone) : "muted",
      sparkline: buildSparklineFromHistory(yieldMetric?.history ?? null, flatSparkline(29)),
      pending: !yieldMetric,
    },
    {
      id: "nim",
      label: "净息差",
      ...splitNumericDisplay(nimMetric?.value, GAP),
      delta: nimMetric ? `较昨日 ${numericDisplay(nimMetric.delta)}` : GAP,
      deltaTone: nimMetric ? metricToneToDelta(nimMetric.tone) : "muted",
      sparkline: buildSparklineFromHistory(nimMetric?.history ?? null, flatSparkline(1.76)),
      pending: !nimMetric,
    },
  ];

  const dv01 = headline?.kpis.total_dv01 ?? portfolio?.total_dv01;
  const duration = headline?.kpis.weighted_duration ?? portfolio?.weighted_duration;
  const top5 = portfolio?.issuer_top5_weight;
  const prevKpis = headline?.prev_kpis ?? null;

  const dv01Split = splitNumericDisplay(dv01);
  const durationSplit = splitNumericDisplay(duration);
  const top5Split = splitNumericDisplay(top5);

  const dv01Foot = buildNumericDeltaFoot(dv01, prevKpis?.total_dv01, {
    riseLabel: "敞口上升",
    fallLabel: "敞口下降",
    suffix: "万",
    decimals: 2,
  });
  const durationFoot = buildNumericDeltaFoot(duration, prevKpis?.weighted_duration, {
    riseLabel: "风险上升",
    fallLabel: "久期下降",
    suffix: "",
    decimals: 2,
  });

  const riskMinis: HomeRiskMini[] = [
    {
      id: "dv01",
      label: "组合DV01",
      value: dv01Split.value,
      unit: dv01Split.unit,
      foot: dv01Foot.foot,
      footTone: dv01Foot.footTone,
    },
    {
      id: "duration",
      label: "久期（年）",
      value: durationSplit.value,
      unit: durationSplit.unit,
      foot: durationFoot.foot,
      footTone: durationFoot.footTone,
    },
    {
      id: "concentration",
      label: "风险集中度\n(Top5)",
      value: top5Split.value,
      unit: top5Split.unit,
      foot: GAP,
      footTone: "flat",
    },
  ];

  const verdict = input.verdict;
  const suggestions =
    verdict?.suggestions?.map((item) => item.text).filter(Boolean).slice(0, 3) ?? [];

  const interbankAssetsRaw = numericRawInYuan(input.coreMetrics?.interbank_assets.total_amount);
  const interbankLiabilitiesRaw = numericRawInYuan(
    input.coreMetrics?.interbank_liabilities.total_amount,
  );
  const interbankNetRawYuan =
    interbankAssetsRaw != null && interbankLiabilitiesRaw != null
      ? interbankAssetsRaw - interbankLiabilitiesRaw
      : null;

  const highPriorityCount =
    input.decisionItems?.filter((item) => item.severity === "high").length ?? input.alertCount;

  const assetStructureMapped = mapAssetStructureToHomeAssetBars(
    input.assetStructure,
    reportDate,
  );
  const exposureMapped = mapPortfolioComparisonToExposureRows(
    input.portfolioComparison,
    reportDate,
  );
  const riskRadarMapped = mapHomeRiskRadar(input.portfolio, reportDate);
  const cockpitWatchlist = mapCockpitWarningsToWatchlist(input.cockpitWarnings, reportDate);
  const cockpitRiskCards = mapCockpitWarningsToRiskCards(input.cockpitWarnings, reportDate);
  const todayIsoDate = input.todayIsoDate?.trim() || resolveTodayIsoDate();
  const researchCalendar = buildHomeResearchCalendarModel({
    events: input.calendarEvents,
    isLoading: input.calendarLoading,
    isError: input.calendarError,
    startDate: input.calendarStartDate,
    endDate: input.calendarEndDate,
  });
  const macroBriefing = buildHomeMacroBriefingModel({
    todayIsoDate,
    newsEvents: input.macroNewsEvents,
    fallbackNewsEvents: input.macroNewsFallbackEvents,
    newsLoading: Boolean(input.macroNewsLoading),
    newsError: Boolean(input.macroNewsError),
    supplyCalendar: researchCalendar,
  });
  const marketTape = mapMarketTape(input.marketPoints);
  const marketContext = buildHomeMarketContextModel({
    marketTape,
    marketPoints: input.marketPoints,
    macroNewsEvents: input.macroNewsEvents,
    todayIsoDate,
    campisiFourEffects: input.campisiFourEffects,
    returnDecomposition: input.returnDecomposition,
    yieldCurveTermStructure: input.yieldCurveTermStructure,
    creditSpreadMigration: input.creditSpreadMigration,
    attribution: {
      maxDragLabel: extremes.maxDrag?.label ?? GAP,
      maxContributionLabel: extremes.maxContribution?.label ?? GAP,
    },
  });
  const hasFormalAttribution = Boolean(input.campisiFourEffects || input.returnDecomposition);
  const decisionMaxDragLabel =
    formalAttributionExtremes?.maxDragLabel && formalAttributionExtremes.maxDragLabel !== GAP
      ? formalAttributionExtremes.maxDragLabel
      : hasFormalAttribution
        ? "无负贡献项"
        : extremes.maxDrag?.label ?? GAP;
  const decisionMaxDragValue =
    formalAttributionExtremes?.maxDragValue && formalAttributionExtremes.maxDragValue !== GAP
      ? formalAttributionExtremes.maxDragValue
      : hasFormalAttribution
        ? "0.00 亿"
        : extremes.maxDrag?.value ?? GAP;
  const riskExposure = buildRiskExposureMetrics(input.riskIndicators, reportDate);
  const riskIndicatorsForTerminal =
    riskExposure.state.kind === "ready" ? input.riskIndicators : null;
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
  const researchReportsBase = input.researchReportsLoading
    ? { rows: [], state: displayState("loading", "研究报告加载中") }
    : input.researchReportsError
      ? { rows: [], state: displayState("error", "研究报告加载失败") }
      : buildResearchReportRows(input.researchReports, reportDate);
  const researchReportsMapped =
    researchReportsBase.state.kind === "empty"
      ? buildResearchNewsFallbackRows(macroBriefing.newsItems, macroBriefing.newsSourceLabel) ?? researchReportsBase
      : researchReportsBase;
  const incomeTrendMapped = input.incomeTrendLoading
    ? { rows: [], state: displayState("loading", "收益趋势加载中") }
    : input.incomeTrendError
      ? { rows: [], state: displayState("error", "收益趋势加载失败") }
      : buildIncomeTrendRows(input.incomeTrend, reportDate);
  const assetDistributionMapped = mapStructureSlices(
    input.assetStructure,
    reportDate,
    (item) => item.category,
    "资产分布暂无数据",
  );
  const ratingMapped = mapStructureSlices(
    input.ratingStructure,
    reportDate,
    (item) => item.category,
    "评级分布暂无数据",
  );
  const maturityMapped = mapStructureSlices(
    input.maturityStructure,
    reportDate,
    (item) => item.maturity_bucket,
    "久期分布暂无数据",
  );
  const industryMapped = mapStructureSlices(
    input.industryDistribution,
    reportDate,
    (item) => item.industry_name,
    "行业分布暂无数据",
  );
  const terminalKpis = buildTerminalKpis({
    aumMetric,
    headline,
    portfolio,
    attribution: input.attribution,
    riskIndicators: riskIndicatorsForTerminal,
    riskState: riskExposure.state,
  });
  const keyRiskStrip = buildKeyRiskStrip(marketTape, riskIndicatorsForTerminal);

  return {
    reportDate,
    useMockFallback: false,
    headerStatus: {
      dataStatusKind,
      dataUpdatedAt,
      marketStatus: input.snapshotUnavailable
        ? "数据未同步"
        : input.snapshotStale
          ? "新报告日失败"
          : "市场已收盘",
      valuationLabel: input.snapshotUnavailable
        ? "等待主快照"
        : input.snapshotStale
          ? "沿用旧快照"
          : "估值已完成",
      valuationTone: input.snapshotUnavailable || input.snapshotStale ? "warn" : "ok",
      riskReviewCount: input.alertCount,
      showRiskReview: input.alertCount > 0,
      dataSyncPrefix,
    },
    aiJudge: {
      conclusion: verdict?.conclusion?.trim() || "数据状态需先复核，再做方向性判断",
      healthLabel:
        verdict?.tone === "positive"
          ? "良好"
          : verdict?.tone === "negative"
            ? "偏弱"
            : verdict?.tone === "warning"
              ? "关注"
              : "中性",
      healthScore: verdict?.tone === "positive" ? 78 : verdict?.tone === "warning" ? 62 : 72,
      healthTone:
        verdict?.tone === "negative"
          ? "red"
          : verdict?.tone === "warning"
            ? "amber"
            : "green",
      impact: verdict?.reasons?.[0]?.detail ?? "等待下一组观测",
      sparkline: flatSparkline(72),
    },
    coreKpis,
    riskMinis,
    marketTape,
    portfolioStats: [
      {
        id: "books",
        label: "组合数",
        value:
          input.portfolioComparison?.items?.length != null
            ? `${input.portfolioComparison.items.length}`
            : GAP,
      },
      {
        id: "positions",
        label: "持仓债券",
        value:
          headline?.kpis.bond_count != null
            ? `${headline.kpis.bond_count.toLocaleString("en-US")} 只`
            : GAP,
      },
      {
        id: "coupon",
        label: "平均票面利率",
        value: headline ? numericDisplay(headline.kpis.weighted_coupon) : GAP,
      },
      {
        id: "rating",
        label: "主体评级",
        value:
          input.creditSpreadMigration?.concentration_by_rating?.top_items?.[0]?.name?.trim() ??
          GAP,
      },
    ],
    assetBars: assetStructureMapped.hasData ? assetStructureMapped.bars : [],
    assetBarsPlaceholder: !assetStructureMapped.hasData,
    centerAum: {
      label: "总资产（账面）",
      value: aumMetric ? `${numericDisplay(aumMetric.value)}` : GAP,
    },
    interbank: {
      assets: input.coreMetrics
        ? numericDisplay(input.coreMetrics.interbank_assets.total_amount)
        : GAP,
      liabilities: input.coreMetrics
        ? numericDisplay(input.coreMetrics.interbank_liabilities.total_amount)
        : GAP,
      net: interbankNetRawYuan != null ? formatYiSigned(interbankNetRawYuan) : GAP,
      netTone: resolveInterbankNetTone(interbankNetRawYuan),
    },
    attributionTabs: buildHomeAttributionTabs({
      reportDate,
      attribution: input.attribution,
      dailyChanges: input.dailyChanges,
      productCategoryYtd: input.productCategoryYtd,
      productCategoryMonthly: input.productCategoryMonthly,
    }),
    attributionWaterfall: waterfall,
    attributionInsights: {
      maxDragLabel: formalAttributionExtremes?.maxDragLabel ?? extremes.maxDrag?.label ?? GAP,
      maxDragValue: formalAttributionExtremes?.maxDragValue ?? extremes.maxDrag?.value ?? GAP,
      maxContributionLabel:
        formalAttributionExtremes?.maxContributionLabel ?? extremes.maxContribution?.label ?? GAP,
      maxContributionValue:
        formalAttributionExtremes?.maxContributionValue ?? extremes.maxContribution?.value ?? GAP,
    },
    attributionNote: verdict?.reasons?.map((reason) => reason.detail).filter(Boolean) ?? [],
    riskCards: cockpitRiskCards.hasData
      ? cockpitRiskCards.cards
      : [
          { id: "high", label: "高风险", count: highPriorityCount, tone: "up" as const },
          { id: "mid", label: "中风险", count: 0, tone: "muted" as const },
          { id: "low", label: "低风险", count: 0, tone: "muted" as const },
        ],
    riskCardsPlaceholder: false,
    riskRadar: riskRadarMapped,
    todos:
      input.decisionItems?.slice(0, 4).map((item, index) => ({
        id: `todo-${index}`,
        title: item.title?.trim() || GAP,
        priority:
          item.severity === "high" ? "高" : item.severity === "medium" ? "中" : "低",
      })) ?? [],
    watchlist: cockpitWatchlist.hasData ? cockpitWatchlist.items : [],
    watchlistPlaceholder: !cockpitWatchlist.hasData,
    exposureRows: exposureMapped.hasData
      ? exposureMapped.rows
      : [
          {
            id: "exp-gap",
            account: "组合暴露",
            type: GAP,
            assetScale: GAP,
            weight: GAP,
            duration: GAP,
            dv01: GAP,
            dailyPnl: GAP,
            tone: "neutral" as const,
          },
        ],
    balanceMetrics: BALANCE_METRIC_SPECS.map((spec) => {
      if (spec.metricIds.length === 0) {
        return { id: spec.id, label: spec.label, value: GAP, placeholder: true };
      }
      const metric = findMetric(input.metrics, spec.metricIds);
      return {
        id: spec.id,
        label: spec.label,
        value: metric ? numericDisplay(metric.value) : GAP,
        placeholder: !metric,
      };
    }),
    quickDrilldowns: DASHBOARD_QUICK_DRILLDOWN_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      icon: item.id,
      path: item.path,
    })),
    researchCalendar,
    macroBriefing,
    marketContext,
    liabilityWatchBasisNote: cockpitWatchlist.basisNote,
    decisionRail: {
      conclusion: buildDecisionRailConclusion(verdict, marketContext),
      maxDragLabel: decisionMaxDragLabel,
      maxDragValue: decisionMaxDragValue,
      maxContributionLabel:
        formalAttributionExtremes?.maxContributionLabel ?? extremes.maxContribution?.label ?? GAP,
      maxContributionValue:
        formalAttributionExtremes?.maxContributionValue ?? extremes.maxContribution?.value ?? GAP,
      keyRisk: buildDecisionRailKeyRisk(verdict, marketContext),
      suggestions: buildDecisionRailSuggestions(suggestions, marketContext),
      pendingSummary: `${input.decisionItems?.length ?? 0} 项`,
      reportDate,
      dataUpdatedAt,
      dataSyncPrefix,
    },
    terminalKpis,
    keyRiskStrip,
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
    riskExposureMetrics: riskExposure.metrics,
    riskExposureState: riskExposure.state,
    positionChanges: positionChangesMapped.rows,
    positionChangesState: positionChangesMapped.state,
    researchReports: researchReportsMapped.rows,
    researchReportsState: researchReportsMapped.state,
    incomeTrend: incomeTrendMapped.rows,
    incomeTrendState: incomeTrendMapped.state,
    backendGaps: ACTIVE_DASHBOARD_HOME_BACKEND_GAPS,
  };
}

export function mapToHomeView(input: MapToHomeViewInput): DashboardHomeView {
  if (input.useMockFallback) {
    return buildMockView();
  }
  return buildRealView(input);
}

export function resolveDeltaClass(
  tone: HomeDeltaTone,
  styles: Record<string, string>,
): string {
  if (tone === "up" || tone === "warn") {
    return styles.dhUpRed ?? "";
  }
  if (tone === "down") {
    return styles.dhDownGreen ?? "";
  }
  return styles.dhMuted ?? "";
}
