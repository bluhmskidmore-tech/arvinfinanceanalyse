import type {
  AssetStructurePayload,
  BalanceAnalysisDecisionItemStatusRow,
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  CockpitWarningsPayload,
  CoreMetricsResult,
  CreditSpreadMigrationPayload,
  DailyChangesResult,
  Numeric,
  PortfolioComparisonPayload,
  ProductCategoryMonthlyHeadlinePayload,
  ProductCategoryYtdHeadlinePayload,
  ResearchCalendarEvent,
  ResultMeta,
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
  liabilityWatchBasisNote: string | null;
  decisionRail: HomeDecisionRail;
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
  decisionItems: readonly BalanceAnalysisDecisionItemStatusRow[] | null;
  marketPoints: readonly import("../../../api/contracts").ChoiceMacroLatestPoint[] | null;
  productCategoryYtd: ProductCategoryYtdHeadlinePayload | null;
  productCategoryMonthly: ProductCategoryMonthlyHeadlinePayload | null;
  assetStructure: AssetStructurePayload | null;
  cockpitWarnings: CockpitWarningsPayload | null;
  calendarEvents: readonly ResearchCalendarEvent[] | null;
  calendarLoading: boolean;
  calendarError: boolean;
  calendarStartDate: string;
  calendarEndDate: string;
  snapshotMeta: ResultMeta | null;
  marketMeta: ResultMeta | null;
  alertCount: number;
  snapshotUnavailable: boolean;
  snapshotStale: boolean;
};

const GAP = "—";

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

function numericRaw(value: Numeric | null | undefined): number | null {
  if (value == null || value.raw == null) {
    return null;
  }
  const parsed =
    typeof value.raw === "number"
      ? value.raw
      : Number(String(value.raw).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function numericRawInYuan(value: Numeric | null | undefined): number | null {
  const parsed = numericRaw(value);
  if (parsed == null || value == null) {
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

function formatYiSigned(rawYuan: number): string {
  const yi = rawYuan / 100_000_000;
  const formatted = yi.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${yi >= 0 ? "+" : ""}${formatted} 亿`;
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

function splitNumericDisplay(value: Numeric | null | undefined, fallback = GAP): {
  value: string;
  unit?: string;
} {
  const display = numericDisplay(value, fallback);
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

function numericDisplay(value: Numeric | null | undefined, fallback = GAP): string {
  const display = value?.display?.trim();
  if (display && display.length > 0 && display !== "--") {
    return display;
  }
  return fallback;
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

function buildMockView(): DashboardHomeView {
  const waterfall = DASHBOARD_ATTRIBUTION_WATERFALL_MOCK.map((item) => ({
    id: item.id,
    label: item.label,
    value: item.value,
    tone: item.tone,
  }));
  const extremes = findAttributionExtremes(waterfall);

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
        label: "组合敏感度",
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
    researchCalendar: {
      items: [],
      status: "ready",
      windowLabel: "—",
      message: null,
    },
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

  const waterfall = segmentsToWaterfall(input.attribution);
  const extremes = findAttributionExtremes(waterfall);

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
      label: "组合敏感度",
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
  const researchCalendar = buildHomeResearchCalendarModel({
    events: input.calendarEvents,
    isLoading: input.calendarLoading,
    isError: input.calendarError,
    startDate: input.calendarStartDate,
    endDate: input.calendarEndDate,
  });

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
    marketTape: mapMarketTape(input.marketPoints),
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
      maxDragLabel: extremes.maxDrag?.label ?? GAP,
      maxDragValue: extremes.maxDrag?.value ?? GAP,
      maxContributionLabel: extremes.maxContribution?.label ?? GAP,
      maxContributionValue: extremes.maxContribution?.value ?? GAP,
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
    liabilityWatchBasisNote: cockpitWatchlist.basisNote,
    decisionRail: {
      conclusion: verdict?.conclusion?.trim() || "数据待同步",
      maxDragLabel: extremes.maxDrag?.label ?? GAP,
      maxDragValue: extremes.maxDrag?.value ?? GAP,
      maxContributionLabel: extremes.maxContribution?.label ?? GAP,
      maxContributionValue: extremes.maxContribution?.value ?? GAP,
      keyRisk: verdict?.reasons?.[0]?.label ?? GAP,
      suggestions: suggestions.length > 0 ? suggestions : ["数据待同步"],
      pendingSummary: `${input.decisionItems?.length ?? 0} 项`,
      reportDate,
      dataUpdatedAt,
      dataSyncPrefix,
    },
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
