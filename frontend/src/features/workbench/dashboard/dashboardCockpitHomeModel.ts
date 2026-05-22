import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  CoreMetricsResult,
  Numeric,
  ResultMeta,
  VerdictPayload,
} from "../../../api/contracts";
import type {
  DashboardOverviewMetricVM,
  DashboardPnlAttributionVM,
} from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import type { DashboardAlert } from "./DashboardOverviewSections";
import {
  DASHBOARD_BALANCE_METRICS_MOCK,
  DASHBOARD_COCKPIT_HEADER_STATUS,
  DASHBOARD_COCKPIT_IMPROVEMENT_NOTES,
  DASHBOARD_COCKPIT_NAV_GROUPS,
  DASHBOARD_COCKPIT_REPORT_DATE,
  DASHBOARD_ASSET_BARS_MOCK,
  DASHBOARD_ATTRIBUTION_NOTE_MOCK,
  DASHBOARD_ATTRIBUTION_TABS_MOCK,
  DASHBOARD_ATTRIBUTION_WATERFALL_MOCK,
  DASHBOARD_EXPOSURE_ROWS_MOCK,
  DASHBOARD_INTERBANK_MOCK,
  DASHBOARD_MARKET_PULSE_MOCK,
  DASHBOARD_PORTFOLIO_STATS_MOCK,
  DASHBOARD_PRODUCT_PNL_SERIES_MOCK,
  DASHBOARD_QUICK_DRILLDOWN_MOCK,
  DASHBOARD_RISK_ALERT_COUNTS_MOCK,
  DASHBOARD_RISK_RADAR_MOCK,
  DASHBOARD_RISK_TODOS_MOCK,
  DASHBOARD_WATCHLIST_MOCK,
  type DashboardBalanceMetricMock,
  type DashboardExposureRowMock,
} from "./dashboardMockData";
import type { DashboardHomeModel } from "./dashboardHomeModel";
import type {
  DashboardCockpitAccountRow,
  DashboardCockpitModel,
  DashboardCockpitTickerItem,
  DashboardCockpitWatchRow,
  DashboardCockpitWaterfallItem,
} from "./dashboardCockpitModel";
import { COCKPIT_CHART_PALETTE } from "./dashboardCockpitVisualTokens";

export type DashboardDeltaTone = "up" | "down" | "flat" | "warn" | "muted";

export type DashboardKpiCardVM = {
  id: string;
  label: string;
  value: string;
  delta: string;
  deltaTone: DashboardDeltaTone;
  iconLabel: string;
  pending?: boolean;
};

export type DashboardMarketPulseVM = {
  id: string;
  label: string;
  value: string;
  delta: string;
  deltaTone: DashboardDeltaTone;
  sparkline: readonly number[];
  statusLabel: string;
};

export type DashboardPortfolioStatVM = {
  id: string;
  label: string;
  value: string;
};

export type DashboardAssetBarVM = {
  id: string;
  label: string;
  pct: number;
  value: string;
  color: string;
};

export type DashboardAttributionTab = "day" | "week" | "month" | "ytd";

export type DashboardAttributionTabVM = {
  id: DashboardAttributionTab;
  label: string;
  pnl: string;
  change: string;
  yield: string;
  changeTone: DashboardDeltaTone;
};

export type DashboardRiskTodoVM = {
  id: string;
  title: string;
  priority: string;
  status: string;
  path: string;
};

export type DashboardWatchItemVM = {
  id: string;
  count: string;
  label: string;
  note: string;
  path: string;
};

export type DashboardRiskAlertCountVM = {
  id: string;
  label: string;
  count: number;
  tone: DashboardDeltaTone;
};

export type DashboardCockpitHeaderStatus = {
  dataUpdatedAt: string;
  marketStatus: string;
  notificationCount: number;
};

export type DashboardProductPnlTrendVM = {
  months: readonly string[];
  series: readonly {
    id: string;
    name: string;
    values: readonly number[];
  }[];
  pending?: boolean;
};

export type DashboardCockpitHomeViewModel = {
  reportDate: string;
  headerStatus: DashboardCockpitHeaderStatus;
  navGroups: typeof DASHBOARD_COCKPIT_NAV_GROUPS;
  kpiCards: DashboardKpiCardVM[];
  marketPulse: DashboardMarketPulseVM[];
  portfolioStats: DashboardPortfolioStatVM[];
  assetBars: DashboardAssetBarVM[];
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
  attributionTabs: DashboardAttributionTabVM[];
  activeAttributionTab: DashboardAttributionTab;
  attributionWaterfall: DashboardCockpitWaterfallItem[];
  attributionNote: readonly string[];
  riskRadar: typeof DASHBOARD_RISK_RADAR_MOCK;
  alertCount: number;
  riskAlertCounts: DashboardRiskAlertCountVM[];
  todos: DashboardRiskTodoVM[];
  watchlist: DashboardWatchItemVM[];
  exposureRows: readonly DashboardExposureRowMock[];
  balanceMetrics: readonly DashboardBalanceMetricMock[];
  productPnl: DashboardProductPnlTrendVM;
  quickDrilldowns: typeof DASHBOARD_QUICK_DRILLDOWN_MOCK;
  improvementNotes: typeof DASHBOARD_COCKPIT_IMPROVEMENT_NOTES;
  judgment: VerdictPayload;
  showDataWarning: boolean;
  dataWarningMessages: string[];
  dataSource: "real" | "mock";
};

const KPI_SPECS: ReadonlyArray<{
  id: string;
  label: string;
  metricIds: string[];
  mockValue: string;
  mockDelta: string;
  mockTone: DashboardDeltaTone;
  iconLabel: string;
}> = [
  {
    id: "aum",
    label: "债券资产规模",
    metricIds: ["aum"],
    mockValue: "3,708.10 亿",
    mockDelta: "较昨日 +22.30 亿  +0.61%",
    mockTone: "warn",
    iconLabel: "规",
  },
  {
    id: "yield",
    label: "年度损益（不扣FTP）",
    metricIds: ["yield"],
    mockValue: "+29.71 亿",
    mockDelta: "较昨日 +1.82 亿",
    mockTone: "up",
    iconLabel: "益",
  },
  {
    id: "nim",
    label: "净息差（年化）",
    metricIds: ["nim"],
    mockValue: "1.76%",
    mockDelta: "较昨日 +0.02bp",
    mockTone: "up",
    iconLabel: "息",
  },
  {
    id: "dv01",
    label: "组合DV01",
    metricIds: ["dv01"],
    mockValue: "10,615.59 万",
    mockDelta: "较昨日 -4.97 万",
    mockTone: "down",
    iconLabel: "久",
  },
  {
    id: "duration",
    label: "久期（年）",
    metricIds: ["duration"],
    mockValue: "4.14",
    mockDelta: "较昨日 +0.01",
    mockTone: "up",
    iconLabel: "期",
  },
  {
    id: "concentration",
    label: "风险集中度（Top5）",
    metricIds: ["concentration", "issuer_concentration"],
    mockValue: "41.35%",
    mockDelta: "较昨日 +0.22pp",
    mockTone: "warn",
    iconLabel: "险",
  },
];

const MARKET_PULSE_LABELS: ReadonlyArray<{
  id: string;
  label: string;
  matchLabels: readonly string[];
  matchIds: readonly string[];
}> = [
  { id: "cgb10y", label: "10年国债", matchLabels: ["10年国债", "10年期国债"], matchIds: ["CA.CN_GOV_10Y", "E1000180"] },
  { id: "dr007", label: "DR007", matchLabels: ["DR007"], matchIds: ["CA.DR007", "M002"] },
  { id: "slope", label: "1Y-10Y利差", matchLabels: ["1Y-10Y", "期限利差"], matchIds: ["CA.CN_SLOPE_1Y10Y"] },
  { id: "us10y", label: "美债10Y", matchLabels: ["美债", "美国10年"], matchIds: ["CA.US_GOV_10Y", "EMG00001310"] },
  { id: "usdcny", label: "人民币汇率", matchLabels: ["人民币", "美元兑人民币"], matchIds: ["CA.USDCNY", "EMM00058124"] },
  { id: "brent", label: "原油 Brent", matchLabels: ["Brent", "原油"], matchIds: ["CA.BRENT"] },
  { id: "csi300", label: "A股指数 沪深300", matchLabels: ["沪深300"], matchIds: ["CA.CSI300"] },
  { id: "credit-spread", label: "信用利差 中短票AAA", matchLabels: ["信用利差"], matchIds: ["CA.CREDIT_SPREAD"] },
];

const ASSET_BAR_COLORS = COCKPIT_CHART_PALETTE;

function metricToneToDelta(tone: string | undefined, deltaDisplay: string): DashboardDeltaTone {
  if (deltaDisplay.includes("待确认") || deltaDisplay.includes("口径")) {
    return "muted";
  }
  const n = parseFloat(deltaDisplay.replace(/[^\d.-]/g, ""));
  if (!Number.isFinite(n)) {
    if (tone === "warning") return "warn";
    if (tone === "negative") return "down";
    if (tone === "positive") return "up";
    return "flat";
  }
  if (tone === "warning") return "warn";
  if (n < 0) return "down";
  if (n > 0) return "up";
  return "flat";
}

function cockpitToneToDelta(tone: string): DashboardDeltaTone {
  if (tone === "negative") return "down";
  if (tone === "positive") return "up";
  if (tone === "warning") return "warn";
  return "flat";
}

function findMetric(
  metrics: readonly DashboardOverviewMetricVM[] | undefined,
  ids: readonly string[],
): DashboardOverviewMetricVM | undefined {
  if (!metrics?.length) return undefined;
  return metrics.find((m) => ids.includes(m.id));
}

const GAP_VALUE = "—";
const GAP_DELTA = "口径待确认";
const PENDING_SYNC = "待同步";

function cleanReportDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const expectedDate = cleanReportDate(expected);
  const actualDate = cleanReportDate(actual);
  return expectedDate.length > 0 && actualDate.length > 0 && expectedDate === actualDate;
}

function numericRaw(value: Numeric | string | number | null | undefined): number | null {
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

function numericDisplay(value: Numeric | null | undefined, fallback = GAP_VALUE): string {
  const display = value?.display?.trim();
  if (display && display.length > 0 && display !== "--") {
    return display;
  }
  const raw = numericRaw(value);
  if (raw == null) {
    return fallback;
  }
  return raw.toLocaleString("en-US", {
    minimumFractionDigits: Math.abs(raw) >= 100 ? 0 : 2,
    maximumFractionDigits: Math.abs(raw) >= 100 ? 0 : 2,
  });
}

function formatYiSigned(rawYuan: number): string {
  const yi = rawYuan / 100_000_000;
  const formatted = yi.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${yi >= 0 ? "+" : ""}${formatted} 亿`;
}

/** 同业净头寸等计算必须用元；Numeric.raw 可能为 yuan 或 yi，不可解析 display。 */
function numericRawInYuan(value: Numeric | null | undefined): number | null {
  if (value == null || value.raw == null) {
    return null;
  }
  const parsed =
    typeof value.raw === "number"
      ? value.raw
      : Number(String(value.raw).replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
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

function pendingBalanceMetric(spec: { id: string; label: string }): DashboardBalanceMetricMock {
  return {
    id: spec.id,
    label: spec.label,
    value: GAP_VALUE,
    delta: PENDING_SYNC,
    tone: "neutral",
  };
}

const ATTRIBUTION_TAB_SPECS: ReadonlyArray<{ id: DashboardAttributionTab; label: string }> = [
  { id: "day", label: "日度" },
  { id: "week", label: "周度" },
  { id: "month", label: "月度" },
  { id: "ytd", label: "YTD" },
];

function pendingAttributionTabs(): DashboardAttributionTabVM[] {
  return ATTRIBUTION_TAB_SPECS.map((spec) => ({
    id: spec.id,
    label: spec.label,
    pnl: GAP_VALUE,
    change: PENDING_SYNC,
    yield: GAP_VALUE,
    changeTone: "muted" as const,
  }));
}

function pendingKpiCard(spec: (typeof KPI_SPECS)[number]): DashboardKpiCardVM {
  return {
    id: spec.id,
    label: spec.label,
    value: GAP_VALUE,
    delta: GAP_DELTA,
    deltaTone: "muted",
    iconLabel: spec.iconLabel,
    pending: true,
  };
}

function mockKpiCard(spec: (typeof KPI_SPECS)[number]): DashboardKpiCardVM {
  return {
    id: spec.id,
    label: spec.label,
    value: spec.mockValue,
    delta: spec.mockDelta,
    deltaTone: spec.mockTone,
    iconLabel: spec.iconLabel,
  };
}

function buildKpiCards(
  metrics: readonly DashboardOverviewMetricVM[] | undefined,
  cockpit: DashboardCockpitModel,
  useMockFallback: boolean,
): DashboardKpiCardVM[] {
  if (useMockFallback) {
    return KPI_SPECS.map(mockKpiCard);
  }

  const durationRail = cockpit.metricRail.find((m) => m.id === "duration");
  const dv01Rail = cockpit.metricRail.find((m) => m.id === "dv01");

  return KPI_SPECS.map((spec) => {
    const metric = findMetric(metrics, spec.metricIds);
    if (spec.id === "duration" && durationRail?.value && durationRail.value !== "--") {
      return {
        id: spec.id,
        label: spec.label,
        value: durationRail.value,
        delta: durationRail.delta ?? GAP_DELTA,
        deltaTone: cockpitToneToDelta(durationRail.tone),
        iconLabel: spec.iconLabel,
      };
    }
    if (spec.id === "dv01" && dv01Rail?.value && dv01Rail.value !== "--") {
      return {
        id: spec.id,
        label: spec.label,
        value: dv01Rail.value,
        delta: dv01Rail.delta ?? GAP_DELTA,
        deltaTone: cockpitToneToDelta(dv01Rail.tone),
        iconLabel: spec.iconLabel,
      };
    }
    if (spec.id === "concentration") {
      const top5 = cockpit.previewSignals.find((s) => s.id === "concentration");
      if (top5?.value && top5.value !== "--") {
        return {
          id: spec.id,
          label: spec.label,
          value: top5.value,
          delta: top5.detail || GAP_DELTA,
          deltaTone: cockpitToneToDelta(top5.tone),
          iconLabel: spec.iconLabel,
        };
      }
    }
    if (metric?.value?.display && metric.value.display !== "--") {
      const delta = metric.delta?.display ?? GAP_DELTA;
      return {
        id: spec.id,
        label: spec.label,
        value: metric.value.display,
        delta,
        deltaTone: metricToneToDelta(metric.tone, delta),
        iconLabel: spec.iconLabel,
      };
    }
    return pendingKpiCard(spec);
  });
}

function sparklineFromTicker(item: DashboardCockpitTickerItem | undefined): readonly number[] {
  if (!item) {
    return [1, 1.02, 0.99, 1.01, 1.03, 1.02, 1.04];
  }
  const parsed = parseFloat(item.value.replace(/[^\d.-]/g, ""));
  const base = Number.isFinite(parsed) ? parsed : 1;
  const delta = parseFloat(item.delta.replace(/[^\d.-]/g, "")) || 0;
  return Array.from({ length: 12 }, (_, i) => base + (delta * (i - 6)) / 100);
}

function buildMarketPulse(
  ticker: readonly DashboardCockpitTickerItem[],
  useMockFallback: boolean,
): DashboardMarketPulseVM[] {
  if (useMockFallback) {
    return DASHBOARD_MARKET_PULSE_MOCK.map((mock) => ({ ...mock }));
  }

  return MARKET_PULSE_LABELS.map((spec) => {
    const item =
      ticker.find((t) => spec.matchIds.includes(t.id)) ??
      ticker.find((t) => spec.matchLabels.some((l) => t.label.includes(l)));
    const hasLiveValue = Boolean(item?.value && item.value !== "--");
    if (!hasLiveValue) {
      return {
        id: spec.id,
        label: spec.label,
        value: GAP_VALUE,
        delta: PENDING_SYNC,
        deltaTone: "muted" as const,
        sparkline: sparklineFromTicker(undefined),
        statusLabel: PENDING_SYNC,
      };
    }
    return {
      id: spec.id,
      label: spec.label,
      value: item!.value,
      delta: item!.delta ?? GAP_DELTA,
      deltaTone: cockpitToneToDelta(item!.tone),
      sparkline: sparklineFromTicker(item),
      statusLabel: item!.status === "stale" ? "最近交易日" : "同日",
    };
  });
}

function buildAssetBars(
  cockpit: DashboardCockpitModel,
  useMockFallback: boolean,
): DashboardAssetBarVM[] {
  if (useMockFallback) {
    return DASHBOARD_ASSET_BARS_MOCK.map((row) => ({ ...row }));
  }
  const items = cockpit.portfolioMix.filter((row) => row.status !== "blocked");
  if (items.length === 0) {
    return [];
  }
  const total = items.reduce((sum, row) => {
    const n = parseFloat(row.marketValue.replace(/[^\d.]/g, ""));
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);
  return items.map((row, index) => {
    const n = parseFloat(row.marketValue.replace(/[^\d.]/g, ""));
    const pct = total > 0 && Number.isFinite(n) ? Math.round((n / total) * 100) : 0;
    return {
      id: row.id,
      label: row.label,
      pct,
      value: row.marketValue,
      color: ASSET_BAR_COLORS[index % ASSET_BAR_COLORS.length]!,
    };
  });
}

function buildPortfolioStats(
  cockpit: DashboardCockpitModel,
  useMockFallback: boolean,
  input: {
    reportDate: string;
    bondHeadline?: BondDashboardHeadlinePayload | null;
    portfolio?: BondPortfolioHeadlinesPayload | null;
  },
): DashboardPortfolioStatVM[] {
  if (useMockFallback) {
    return DASHBOARD_PORTFOLIO_STATS_MOCK.map((stat) => ({ ...stat }));
  }

  const headlineAllowed = isSameReportDate(input.reportDate, input.bondHeadline?.report_date);
  const portfolioAllowed = isSameReportDate(input.reportDate, input.portfolio?.report_date);
  const bondCount =
    (headlineAllowed ? input.bondHeadline?.kpis.bond_count : null) ??
    (portfolioAllowed ? input.portfolio?.bond_count : null);
  const couponValue =
    headlineAllowed && input.bondHeadline?.kpis.weighted_coupon
      ? numericDisplay(input.bondHeadline.kpis.weighted_coupon)
      : portfolioAllowed && input.portfolio?.weighted_coupon
        ? numericDisplay(input.portfolio.weighted_coupon)
        : null;
  const couponRail = cockpit.metricRail.find((item) => item.id === "coupon");

  return [
    {
      id: "books",
      label: "组合数",
      value: PENDING_SYNC,
    },
    {
      id: "positions",
      label: "持仓债券",
      value:
        bondCount != null && Number.isFinite(bondCount)
          ? `${bondCount.toLocaleString("en-US")} 只`
          : PENDING_SYNC,
    },
    {
      id: "coupon",
      label: "平均票面利率",
      value:
        couponValue && couponValue !== GAP_VALUE
          ? couponValue
          : couponRail?.value && couponRail.value !== "--"
            ? couponRail.value
            : PENDING_SYNC,
    },
    { id: "rating", label: "平均主体评级", value: PENDING_SYNC },
  ];
}

function attributionSegmentsToWaterfall(
  attribution: DashboardPnlAttributionVM,
): DashboardCockpitWaterfallItem[] {
  return attribution.segments.map((segment) => ({
    id: segment.id,
    label: segment.label,
    value: segment.amount.display,
    status: "supplemental" as const,
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

function buildAttributionTabs(
  waterfall: readonly DashboardCockpitWaterfallItem[],
  useMockFallback: boolean,
  attribution?: DashboardPnlAttributionVM | null,
): DashboardAttributionTabVM[] {
  if (!useMockFallback && attribution?.total.display) {
    const totalDisplay = attribution.total.display;
    const firstSegment = attribution.segments[0];
    const specs: ReadonlyArray<{ id: DashboardAttributionTab; label: string }> = [
      { id: "day", label: "日度" },
      { id: "week", label: "周度" },
      { id: "month", label: "月度" },
      { id: "ytd", label: "YTD" },
    ];
    return specs.map((spec) => {
      if (spec.id === "day") {
        return {
          id: spec.id,
          label: spec.label,
          pnl: totalDisplay,
          change: firstSegment?.amount.display ?? GAP_VALUE,
          yield: GAP_DELTA,
          changeTone: firstSegment ? cockpitToneToDelta(firstSegment.tone) : ("muted" as const),
        };
      }
      return {
        id: spec.id,
        label: spec.label,
        pnl: GAP_VALUE,
        change: PENDING_SYNC,
        yield: GAP_VALUE,
        changeTone: "muted" as const,
      };
    });
  }

  const hasUsableWaterfall = waterfall.some((item) => {
    const n = parseFloat(item.value.replace(/[^\d.-]/g, ""));
    return item.status !== "blocked" && Number.isFinite(n);
  });
  if (useMockFallback) {
    return DASHBOARD_ATTRIBUTION_TABS_MOCK.map((tab) => ({
      id: tab.id as DashboardAttributionTab,
      label: tab.label,
      pnl: tab.pnl,
      change: tab.change,
      yield: tab.yield,
      changeTone: tab.changeTone as DashboardDeltaTone,
    }));
  }
  if (!hasUsableWaterfall) {
    return pendingAttributionTabs();
  }
  const total = waterfall.reduce((sum, row) => {
    const n = parseFloat(row.value.replace(/[^\d.-]/g, ""));
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);
  const totalDisplay = total !== 0 ? `${total >= 0 ? "+" : ""}${total.toFixed(2)} 亿` : GAP_VALUE;
  const firstDriver = waterfall[0];
  const dayChange = firstDriver?.value ?? GAP_VALUE;
  const specs: ReadonlyArray<{
    id: DashboardAttributionTab;
    label: string;
  }> = [
    { id: "day", label: "日度" },
    { id: "week", label: "周度" },
    { id: "month", label: "月度" },
    { id: "ytd", label: "YTD" },
  ];
  return specs.map((spec) => {
    if (spec.id === "day" && waterfall.length > 0) {
      return {
        id: spec.id,
        label: spec.label,
        pnl: totalDisplay,
        change: dayChange,
        yield: GAP_DELTA,
        changeTone: cockpitToneToDelta(firstDriver?.tone ?? "neutral"),
      };
    }
    return {
      id: spec.id,
      label: spec.label,
      pnl: GAP_VALUE,
      change: GAP_DELTA,
      yield: GAP_VALUE,
      changeTone: "muted" as const,
    };
  });
}

function buildTodos(
  alerts: readonly DashboardAlert[],
  useMockFallback: boolean,
): DashboardRiskTodoVM[] {
  if (useMockFallback) {
    return DASHBOARD_RISK_TODOS_MOCK.map((todo) => ({ ...todo }));
  }
  return alerts.slice(0, 4).map((alert) => ({
    id: alert.id,
    title: alert.title,
    priority: alert.severity === "high" ? "高" : alert.severity === "medium" ? "中" : "低",
    status: alert.severity === "high" ? "需处理" : "待复核",
    path: "/decision-items",
  }));
}

function buildWatchlist(
  rows: readonly DashboardCockpitWatchRow[],
  useMockFallback: boolean,
): DashboardWatchItemVM[] {
  if (useMockFallback || rows.length === 0) {
    return DASHBOARD_WATCHLIST_MOCK.map((item) => ({ ...item }));
  }
  return rows.slice(0, 5).map((row) => ({
    id: row.id,
    count: row.dailyChange || "--",
    label: row.name,
    note: row.reason,
    path: row.route,
  }));
}

function buildInterbankDisplay(input: {
  coreMetrics?: CoreMetricsResult | null;
  reportDate: string;
  useMockFallback: boolean;
}): {
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
} {
  if (input.useMockFallback) {
    return {
      interbankAssets: DASHBOARD_INTERBANK_MOCK.assets,
      interbankLiabilities: DASHBOARD_INTERBANK_MOCK.liabilities,
      interbankNetPosition: DASHBOARD_INTERBANK_MOCK.netPosition,
    };
  }

  const coreAllowed = isSameReportDate(input.reportDate, input.coreMetrics?.report_date);
  const core = coreAllowed ? input.coreMetrics : null;
  const assets = numericDisplay(core?.interbank_assets.total_amount, PENDING_SYNC);
  const liabilities = numericDisplay(core?.interbank_liabilities.total_amount, PENDING_SYNC);
  const assetsRaw = numericRawInYuan(core?.interbank_assets.total_amount);
  const liabilitiesRaw = numericRawInYuan(core?.interbank_liabilities.total_amount);
  const netPosition =
    assetsRaw != null && liabilitiesRaw != null
      ? formatYiSigned(assetsRaw - liabilitiesRaw)
      : PENDING_SYNC;

  return {
    interbankAssets: assets,
    interbankLiabilities: liabilities,
    interbankNetPosition: netPosition,
  };
}

function cockpitToneToExposureTone(tone: DashboardCockpitAccountRow["tone"]): DashboardExposureRowMock["tone"] {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "warning") return "warning";
  return "neutral";
}

function buildExposureRows(
  cockpit: DashboardCockpitModel,
  useMockFallback: boolean,
): readonly DashboardExposureRowMock[] {
  if (useMockFallback) {
    return DASHBOARD_EXPOSURE_ROWS_MOCK;
  }
  const assetRows = cockpit.accountRows.filter((row) => row.segment === "资产类" || row.segment === "组合");
  if (assetRows.length === 0) {
    return [
      {
        id: "exp-gap",
        account: "账户与暴露摘要",
        type: GAP_VALUE,
        assetScale: GAP_VALUE,
        weight: GAP_VALUE,
        duration: GAP_VALUE,
        dv01: GAP_VALUE,
        dailyPnl: GAP_DELTA,
        tone: "warning",
      },
    ];
  }

  return assetRows.map((row) => ({
    id: row.id,
    account: row.accountName,
    type: row.segment,
    assetScale: row.exposure.replace(/\s*亿$/, ""),
    weight: row.weight,
    duration: row.duration,
    dv01: row.risk.replace(/^DV01\s*/, ""),
    dailyPnl: row.dailyChange !== "--" ? row.dailyChange : GAP_DELTA,
    tone: cockpitToneToExposureTone(row.tone),
  }));
}

function metricToneToBalanceTone(tone: string | undefined): DashboardBalanceMetricMock["tone"] {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "warning") return "warning";
  return "neutral";
}

function buildBalanceMetrics(
  metrics: readonly DashboardOverviewMetricVM[] | undefined,
  useMockFallback: boolean,
): readonly DashboardBalanceMetricMock[] {
  if (useMockFallback) {
    return DASHBOARD_BALANCE_METRICS_MOCK;
  }

  return BALANCE_METRIC_SPECS.map((spec) => {
    if (spec.metricIds.length === 0) {
      return pendingBalanceMetric(spec);
    }
    const metric = findMetric(metrics, spec.metricIds);
    if (metric?.value?.display && metric.value.display !== "--") {
      return {
        id: spec.id,
        label: spec.label,
        value: metric.value.display,
        delta: metric.delta?.display ?? PENDING_SYNC,
        tone: metricToneToBalanceTone(metric.tone),
      };
    }
    return pendingBalanceMetric(spec);
  });
}

/** 首页无产品分类月度序列 API；inventory 仅允许 YTD/月度摘要，不展示占位曲线。 */
export const DASHBOARD_PRODUCT_PNL_PENDING: DashboardProductPnlTrendVM = {
  months: [],
  series: [],
  pending: true,
};

function buildProductPnlTrend(useMockFallback: boolean): DashboardProductPnlTrendVM {
  if (!useMockFallback) {
    return DASHBOARD_PRODUCT_PNL_PENDING;
  }
  return {
    months: DASHBOARD_PRODUCT_PNL_SERIES_MOCK.months,
    series: DASHBOARD_PRODUCT_PNL_SERIES_MOCK.series,
    pending: false,
  };
}

function buildAttributionWaterfall(
  waterfall: readonly DashboardCockpitWaterfallItem[],
  useMockFallback: boolean,
  attribution?: DashboardPnlAttributionVM | null,
): DashboardCockpitWaterfallItem[] {
  if (!useMockFallback && attribution && attribution.segments.length > 0) {
    return attributionSegmentsToWaterfall(attribution);
  }

  const usable = waterfall.filter((item) => {
    const n = parseFloat(item.value.replace(/[^\d.-]/g, ""));
    return item.status !== "blocked" && Number.isFinite(n);
  });
  if (useMockFallback) {
    return DASHBOARD_ATTRIBUTION_WATERFALL_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      value: item.value,
      status: item.status,
      tone: item.tone,
    }));
  }
  return [...usable];
}

function buildAttributionNote(input: {
  judgment: VerdictPayload;
  useMockFallback: boolean;
}): readonly string[] {
  if (input.useMockFallback) {
    return DASHBOARD_ATTRIBUTION_NOTE_MOCK;
  }
  const conclusion = input.judgment.conclusion.trim();
  return conclusion
    ? [conclusion]
    : ["组合变化主要来自规模与利差；请先复核治理状态再下结论。"];
}

function buildRiskAlertCounts(alertCount: number, useMockFallback: boolean): DashboardRiskAlertCountVM[] {
  if (useMockFallback) {
    return DASHBOARD_RISK_ALERT_COUNTS_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      count: item.count,
      tone: item.tone as DashboardDeltaTone,
    }));
  }
  return [
    { id: "high", label: "高风险预警", count: alertCount, tone: alertCount > 0 ? "warn" : "flat" },
    { id: "medium", label: "中风险预警", count: 0, tone: "flat" },
    { id: "low", label: "低风险预警", count: 0, tone: "flat" },
  ];
}

function formatMetaGeneratedAtTime(iso: string | undefined | null): string | null {
  const trimmed = iso?.trim() ?? "";
  if (!trimmed) {
    return null;
  }
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function resolveMarketStatusLabel(input: {
  marketMeta?: ResultMeta | null;
  reportDate?: string;
}): string {
  if (input.marketMeta?.vendor_status === "vendor_unavailable") {
    return "行情暂不可用";
  }
  if (input.marketMeta?.vendor_status === "vendor_stale") {
    return "行情最近交易日";
  }
  const asOf = input.marketMeta?.as_of_date?.trim() || input.reportDate?.trim() || "";
  if (asOf) {
    const today = new Date();
    const todayIso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    if (asOf < todayIso) {
      return "市场已收盘";
    }
    return "市场交易中";
  }
  // data-source: mock fallback when market meta / report date unavailable
  return DASHBOARD_COCKPIT_HEADER_STATUS.marketStatus;
}

export function buildDashboardCockpitHeaderStatus(input: {
  snapshotMeta?: ResultMeta | null;
  marketMeta?: ResultMeta | null;
  reportDate?: string;
  alertCount?: number;
}): DashboardCockpitHeaderStatus {
  return {
    dataUpdatedAt:
      formatMetaGeneratedAtTime(input.snapshotMeta?.generated_at) ??
      DASHBOARD_COCKPIT_HEADER_STATUS.dataUpdatedAt,
    marketStatus: resolveMarketStatusLabel({
      marketMeta: input.marketMeta,
      reportDate: input.reportDate,
    }),
    notificationCount: input.alertCount ?? DASHBOARD_COCKPIT_HEADER_STATUS.notificationCount,
  };
}

export type BuildDashboardCockpitHomeViewModelInput = {
  home: DashboardHomeModel;
  cockpit: DashboardCockpitModel;
  metrics?: readonly DashboardOverviewMetricVM[] | null;
  snapshotMeta?: ResultMeta | null;
  marketMeta?: ResultMeta | null;
  coreMetrics?: CoreMetricsResult | null;
  bondHeadline?: BondDashboardHeadlinePayload | null;
  portfolio?: BondPortfolioHeadlinesPayload | null;
  attribution?: DashboardPnlAttributionVM | null;
  /** API 失败或空序列时回落到 dashboardMockData 演示数 */
  useMockFallback?: boolean;
};

function buildDataWarningMessages(input: {
  useMockFallback: boolean;
  home: DashboardHomeModel;
  kpiCards: DashboardKpiCardVM[];
  marketPulse: DashboardMarketPulseVM[];
  portfolioStats: DashboardPortfolioStatVM[];
}): string[] {
  if (input.useMockFallback) {
    return ["数据使用本地模拟数据，待真实接口同步。"];
  }

  const warnings: string[] = [];
  const hasPendingKpi = input.kpiCards.some((card) => card.pending);
  const hasPendingMarket = input.marketPulse.some(
    (item) => item.value === GAP_VALUE || item.statusLabel === PENDING_SYNC,
  );
  const hasPendingPortfolio = input.portfolioStats.some((stat) => stat.value === PENDING_SYNC);

  if (hasPendingKpi || hasPendingMarket || hasPendingPortfolio) {
    warnings.push("部分指标待同步");
  }
  if (input.kpiCards.some((card) => card.delta.includes("口径"))) {
    warnings.push("部分指标口径待确认");
  }
  if (input.home.attentionItems.length > 0) {
    warnings.push(...input.home.attentionItems);
  }
  if (input.home.snapshotPartialNote) {
    warnings.push(input.home.snapshotPartialNote);
  }
  return warnings;
}

export function buildDashboardCockpitHomeViewModel(
  input: BuildDashboardCockpitHomeViewModelInput,
): DashboardCockpitHomeViewModel {
  const { home, cockpit, metrics } = input;
  const useMockFallback =
    input.useMockFallback === true || home.meta.sourceMode === "mock";
  const dataSource: "real" | "mock" = useMockFallback ? "mock" : "real";
  const reportDate = useMockFallback
    ? DASHBOARD_COCKPIT_REPORT_DATE
    : home.effectiveReportDate || DASHBOARD_COCKPIT_REPORT_DATE;
  const kpiCards = buildKpiCards(metrics ?? undefined, cockpit, useMockFallback);
  const marketPulse = buildMarketPulse(cockpit.marketTicker, useMockFallback);
  const portfolioStats = buildPortfolioStats(cockpit, useMockFallback, {
    reportDate,
    bondHeadline: input.bondHeadline,
    portfolio: input.portfolio,
  });
  const interbank = buildInterbankDisplay({
    coreMetrics: input.coreMetrics,
    reportDate,
    useMockFallback,
  });
  const warnings = buildDataWarningMessages({
    useMockFallback,
    home,
    kpiCards,
    marketPulse,
    portfolioStats,
  });

  return {
    reportDate,
    headerStatus: buildDashboardCockpitHeaderStatus({
      snapshotMeta: useMockFallback ? null : input.snapshotMeta,
      marketMeta: useMockFallback ? null : input.marketMeta,
      reportDate,
      alertCount: home.reviewCount,
    }),
    navGroups: DASHBOARD_COCKPIT_NAV_GROUPS,
    kpiCards,
    marketPulse,
    portfolioStats,
    assetBars: buildAssetBars(cockpit, useMockFallback),
    interbankAssets: interbank.interbankAssets,
    interbankLiabilities: interbank.interbankLiabilities,
    interbankNetPosition: interbank.interbankNetPosition,
    attributionTabs: buildAttributionTabs(
      cockpit.waterfall,
      useMockFallback,
      input.attribution,
    ),
    activeAttributionTab: "day",
    attributionWaterfall: buildAttributionWaterfall(
      cockpit.waterfall,
      useMockFallback,
      input.attribution,
    ),
    attributionNote: buildAttributionNote({
      judgment: home.judgment,
      useMockFallback,
    }),
    riskRadar: DASHBOARD_RISK_RADAR_MOCK,
    alertCount: useMockFallback
      ? DASHBOARD_RISK_ALERT_COUNTS_MOCK.reduce((sum, item) => sum + item.count, 0)
      : home.reviewCount,
    riskAlertCounts: buildRiskAlertCounts(home.reviewCount, useMockFallback),
    todos: buildTodos(home.alerts, useMockFallback),
    watchlist: buildWatchlist(cockpit.watchRows, useMockFallback),
    exposureRows: buildExposureRows(cockpit, useMockFallback),
    balanceMetrics: buildBalanceMetrics(metrics ?? undefined, useMockFallback),
    productPnl: buildProductPnlTrend(useMockFallback),
    quickDrilldowns: DASHBOARD_QUICK_DRILLDOWN_MOCK,
    improvementNotes: DASHBOARD_COCKPIT_IMPROVEMENT_NOTES,
    judgment: home.judgment,
    showDataWarning: warnings.length > 0,
    dataWarningMessages: warnings,
    dataSource,
  };
}

export function resolveKpiDeltaClass(tone: DashboardDeltaTone): string {
  if (tone === "up") return "dashboard-cockpit-delta--up";
  if (tone === "down") return "dashboard-cockpit-delta--down";
  if (tone === "warn") return "dashboard-cockpit-delta--warn";
  if (tone === "muted") return "dashboard-cockpit-delta--muted";
  return "dashboard-cockpit-delta--flat";
}
