import type {
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionStatus,
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  CoreMetricsResult,
  CreditSpreadMigrationPayload,
  Numeric,
  PnlByBusinessAnalysisPayload,
  PortfolioComparisonPayload,
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
import { buildDashboardProductPnlTrendFromBondBucketMonthly } from "./dashboardProductPnlTrendModel";
import type {
  DashboardCockpitAccountRow,
  DashboardCockpitModel,
  DashboardCockpitRiskItem,
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
  sparkline: readonly number[];
  group: "core" | "risk";
  groupLabel: string;
  signalLabel?: string;
  relationLabel?: string;
  sparklineMuted?: boolean;
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
  impactLabel: string;
  isEstimated?: boolean;
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
  dataSyncPrefix: string;
  valuationLabel: string | null;
  valuationTone: "ok" | "muted";
  dataFreshnessState: "mock-fallback" | "missing-snapshot-time" | "fresh";
  riskReviewCount: number;
  showRiskReview: boolean;
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

export type DashboardRiskRadarVM = {
  dimensions: readonly string[];
  values: readonly number[];
  pending?: boolean;
};

export type DashboardPortfolioCenterAumVM = {
  value: string;
  label: string;
};

export type DashboardDecisionSidebarTone = "neutral" | "positive" | "negative" | "warning";

export type DashboardDecisionSourceType =
  | "governed"
  | "derived"
  | "pending"
  | "mock-fallback"
  | "static-ui";

type DashboardDecisionSource = {
  sourceType: DashboardDecisionSourceType;
  sourceLabel: string;
};

export type DashboardDecisionSidebarSectionVM = {
  id: string;
  title: string;
  body: string;
  tone?: DashboardDecisionSidebarTone;
  badge?: string;
  evidenceLabel?: string;
  statusLabel?: string;
  href?: string;
  targetId?: string;
  sourceType: DashboardDecisionSourceType;
  sourceLabel: string;
};

export type DashboardDecisionSpineTone = DashboardDecisionSidebarTone | "info" | "muted";

export type DashboardDecisionSpineItemVM = {
  id: "market-focus" | "portfolio-impact" | "risk-focus";
  label: string;
  value: string;
  tone: DashboardDecisionSpineTone;
  href: string;
  targetId: string;
  sourceType: DashboardDecisionSourceType;
  sourceLabel: string;
};

export type DashboardExecutiveOverviewVM = {
  summary: string;
  coreMetrics: readonly DashboardKpiCardVM[];
  riskConstraints: readonly DashboardKpiCardVM[];
  healthLabel: string;
  healthText: string;
  healthSparkline: readonly number[];
};

export type DashboardAiDecisionSummaryItemVM = {
  id:
    | "mainline"
    | "max-drag"
    | "max-contribution"
    | "key-risk"
    | "suggested-actions"
    | "pending-todos";
  title: string;
  body: string;
  tone?: DashboardDecisionSidebarTone;
  badge?: string;
  evidenceLabel?: string;
  statusLabel?: string;
  href?: string;
  targetId?: string;
  sourceType: DashboardDecisionSourceType;
  sourceLabel: string;
};

export type DashboardRiskActionStripVM = {
  radar: DashboardRiskRadarVM;
  alertCounts: readonly DashboardRiskAlertCountVM[];
  totalAlerts: number;
  todoCount: number;
  highPriorityTodoCount: number;
  watchCount: number;
  riskReviewOnly: boolean;
  usesMockRiskRadar: boolean;
  entryHref: string;
};

const DASHBOARD_HOME_MARKET_TARGET = "dashboard-home-market-section";
const DASHBOARD_HOME_PORTFOLIO_TARGET = "dashboard-home-portfolio-section";
const DASHBOARD_HOME_RISK_TARGET = "dashboard-home-risk-section";

const DASHBOARD_DECISION_SOURCE_LABELS: Record<DashboardDecisionSourceType, string> = {
  governed: "正式链路",
  derived: "前端衍生",
  pending: "口径待确认",
  "mock-fallback": "本地模拟",
  "static-ui": "固定导航",
};

function decisionSource(sourceType: DashboardDecisionSourceType): DashboardDecisionSource {
  return { sourceType, sourceLabel: DASHBOARD_DECISION_SOURCE_LABELS[sourceType] };
}

function decisionSourceWithLabel(
  sourceType: DashboardDecisionSourceType,
  sourceLabel: string,
): DashboardDecisionSource {
  return { sourceType, sourceLabel };
}

function realDecisionSource(
  useMockFallback: boolean,
  sourceType: Exclude<DashboardDecisionSourceType, "mock-fallback">,
): DashboardDecisionSource {
  return decisionSource(useMockFallback ? "mock-fallback" : sourceType);
}

function resolveMainlineDecisionSource(input: {
  useMockFallback: boolean;
  snapshotPartialNote?: string | null;
  dataWarningMessages?: readonly string[];
}): DashboardDecisionSource {
  if (input.useMockFallback) {
    return decisionSource("mock-fallback");
  }
  if (
    input.snapshotPartialNote ||
    input.dataWarningMessages?.some(isFirstScreenBlockingWarning)
  ) {
    return decisionSourceWithLabel("pending", "待复核");
  }
  return decisionSourceWithLabel("derived", "衍生判断");
}

export type DashboardDecisionSpineVM = {
  marketFocus: string;
  portfolioImpact: string;
  pnlDriver: string;
  riskConstraint: string;
  nextAction: string;
  evidenceState: string;
  rail: readonly DashboardDecisionSpineItemVM[];
};

export type DashboardCockpitHomeViewModel = {
  reportDate: string;
  headerStatus: DashboardCockpitHeaderStatus;
  navGroups: typeof DASHBOARD_COCKPIT_NAV_GROUPS;
  kpiCards: DashboardKpiCardVM[];
  executiveOverview: DashboardExecutiveOverviewVM;
  portfolioCenterAum: DashboardPortfolioCenterAumVM;
  marketPulse: DashboardMarketPulseVM[];
  portfolioStats: DashboardPortfolioStatVM[];
  assetBars: DashboardAssetBarVM[];
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
  interbankNetPositionTone: DashboardDeltaTone;
  attributionTabs: DashboardAttributionTabVM[];
  activeAttributionTab: DashboardAttributionTab;
  attributionWaterfall: DashboardCockpitWaterfallItem[];
  attributionNote: readonly string[];
  riskRadar: DashboardRiskRadarVM;
  alertCount: number;
  riskAlertCounts: DashboardRiskAlertCountVM[];
  todos: DashboardRiskTodoVM[];
  watchlist: DashboardWatchItemVM[];
  exposureRows: readonly DashboardExposureRowMock[];
  balanceMetrics: readonly DashboardBalanceMetricMock[];
  productPnl: DashboardProductPnlTrendVM;
  quickDrilldowns: typeof DASHBOARD_QUICK_DRILLDOWN_MOCK;
  /** P1：今日决策侧舱业务卡片（由 judgment / 归因 / 预警 / 待办等现有字段组装）。 */
  decisionSidebarSections: DashboardDecisionSidebarSectionVM[];
  /** AI 决策舱六条结论，复用现有业务数据与 provenance。 */
  aiDecisionSummary: readonly DashboardAiDecisionSummaryItemVM[];
  /** 主工作区下方横向风险处置条。 */
  riskActionStrip: DashboardRiskActionStripVM;
  /** 首屏信息脊柱：仅由现有首页字段派生，用于串联市场、组合、归因、风险和处置状态。 */
  decisionSpine: DashboardDecisionSpineVM;
  /** 真实模式下预警仅有 review 桶、无分级明细时为 true。 */
  riskReviewOnly: boolean;
  /** riskRadar 仍来自 dashboardMockData 演示常量时为 true。 */
  usesMockRiskRadar: boolean;
  /** 快捷下钻为固定导航（非 live 摘要）时为 true；真实模式也为 true，但不表示 mock 数据。 */
  usesStaticQuickDrilldown: boolean;
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
  mockSparkline: readonly number[];
  iconLabel: string;
  group: "core" | "risk";
  relationLabel: string;
}> = [
  {
    id: "aum",
    label: "债券资产规模",
    metricIds: ["aum"],
    mockValue: "3,708.10 亿",
    mockDelta: "较昨日 +22.30 亿  +0.61%",
    mockTone: "warn",
    mockSparkline: [3650, 3668, 3680, 3695, 3700, 3705, 3706, 3707, 3708, 3707.5, 3708, 3708.1],
    iconLabel: "规",
    group: "core",
    relationLabel: "关联资产结构",
  },
  {
    id: "yield",
    label: "年度损益（不扣FTP）",
    metricIds: ["yield"],
    mockValue: "+29.71 亿",
    mockDelta: "较昨日 +1.82 亿",
    mockTone: "up",
    mockSparkline: [18, 20, 22, 24, 26, 27, 28, 28.5, 29, 29.3, 29.5, 29.71],
    iconLabel: "益",
    group: "core",
    relationLabel: "关联今日归因",
  },
  {
    id: "nim",
    label: "净息差（年化）",
    metricIds: ["nim"],
    mockValue: "1.76%",
    mockDelta: "较昨日 +0.02bp",
    mockTone: "up",
    mockSparkline: [1.68, 1.69, 1.7, 1.71, 1.72, 1.73, 1.735, 1.74, 1.745, 1.75, 1.755, 1.76],
    iconLabel: "息",
    group: "core",
    relationLabel: "关联资金成本",
  },
  {
    id: "dv01",
    label: "组合DV01",
    metricIds: ["dv01"],
    mockValue: "10,615.59 万",
    mockDelta: "较昨日 -4.97 万",
    mockTone: "down",
    mockSparkline: [10820, 10780, 10740, 10710, 10690, 10670, 10655, 10640, 10630, 10625, 10620, 10615.59],
    iconLabel: "久",
    group: "risk",
    relationLabel: "关联利率风险",
  },
  {
    id: "duration",
    label: "久期（年）",
    metricIds: ["duration"],
    mockValue: "4.14",
    mockDelta: "较昨日 +0.01",
    mockTone: "up",
    mockSparkline: [4.08, 4.09, 4.1, 4.105, 4.11, 4.115, 4.12, 4.125, 4.13, 4.132, 4.135, 4.14],
    iconLabel: "期",
    group: "risk",
    relationLabel: "关联久期约束",
  },
  {
    id: "concentration",
    label: "风险集中度（Top5）",
    metricIds: ["concentration", "issuer_concentration"],
    mockValue: "41.35%",
    mockDelta: "较昨日 +0.22pp",
    mockTone: "warn",
    mockSparkline: [40.4, 40.55, 40.7, 40.82, 40.9, 41, 41.05, 41.1, 41.18, 41.24, 41.3, 41.35],
    iconLabel: "险",
    group: "risk",
    relationLabel: "关联主体敞口",
  },
];

const MARKET_PULSE_LABELS: ReadonlyArray<{
  id: string;
  label: string;
  matchLabels: readonly string[];
  matchIds: readonly string[];
  impactLabel: string;
}> = [
  { id: "cgb10y", label: "10年国债", matchLabels: ["10年国债", "10年期国债"], matchIds: ["CA.CN_GOV_10Y", "E1000180"], impactLabel: "估值敏感" },
  { id: "dr007", label: "DR007", matchLabels: ["DR007"], matchIds: ["CA.DR007", "M002"], impactLabel: "资金成本" },
  { id: "slope", label: "1Y-10Y利差", matchLabels: ["1Y-10Y", "期限利差"], matchIds: ["CA.CN_SLOPE_1Y10Y"], impactLabel: "期限结构" },
  { id: "us10y", label: "美债10Y", matchLabels: ["美债", "美国10年"], matchIds: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"], impactLabel: "外部利率" },
  { id: "usdcny", label: "人民币汇率", matchLabels: ["人民币", "美元兑人民币"], matchIds: ["CA.USDCNY", "EMM00058124"], impactLabel: "汇率扰动" },
  { id: "brent", label: "原油 Brent", matchLabels: ["Brent", "原油"], matchIds: ["CA.BRENT"], impactLabel: "通胀预期" },
  { id: "csi300", label: "A股指数 沪深300", matchLabels: ["沪深300"], matchIds: ["CA.CSI300"], impactLabel: "风险偏好" },
  { id: "credit-spread", label: "信用利差 中短票AAA", matchLabels: ["信用利差"], matchIds: ["CA.CREDIT_SPREAD"], impactLabel: "信用定价" },
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

function unsignedDisplay(value: string): string {
  return value.startsWith("+") ? value.slice(1) : value;
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
    delta: "专题补充",
    tone: "neutral",
  };
}

const ATTRIBUTION_TAB_SPECS: ReadonlyArray<{ id: DashboardAttributionTab; label: string }> = [
  { id: "day", label: "日度" },
  { id: "week", label: "周度" },
  { id: "month", label: "月度" },
  { id: "ytd", label: "YTD" },
];

const ATTRIBUTION_YIELD_MISSING_WARNING =
  "归因收益率待读取，日度收益率口径待复核（来源: pnl-attribution.total.display）";
const PORTFOLIO_BOOKS_PENDING_WARNING =
  "资产分布组合数待读取，组合明细口径待复核（来源: portfolio-comparison.items）";
const PORTFOLIO_POSITIONS_PENDING_WARNING =
  "资产分布持仓债券待读取，持仓口径待复核（来源: bond-dashboard-headline.kpis.bond_count）";
const PORTFOLIO_COUPON_PENDING_WARNING =
  "资产分布票面利率待读取，收益口径待复核（来源: bond-dashboard-headline.kpis.weighted_coupon）";
const PORTFOLIO_RATING_PENDING_WARNING =
  "资产分布主体评级待读取，信用集中度口径待复核（来源: credit-spread-migration.concentration_by_rating.top_items[0].name）";

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

function hasUsableAttributionWaterfall(
  waterfall: readonly DashboardCockpitWaterfallItem[],
): boolean {
  return waterfall.some((item) => {
    const n = parseFloat(item.value.replace(/[^\d.-]/g, ""));
    return item.status !== "blocked" && Number.isFinite(n);
  });
}

function parseMetricNumber(value: string): number | null {
  const parsed = Number(value.replace(/,/g, "").replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function buildKpiSparkline(
  value: string,
  tone: DashboardDeltaTone,
  fallback: readonly number[],
  pending = false,
): { sparkline: readonly number[]; sparklineMuted: boolean } {
  if (pending) {
    return { sparkline: flatSparkline(0, 12), sparklineMuted: true };
  }

  const parsed = parseMetricNumber(value);
  if (parsed === null) {
    return { sparkline: fallback, sparklineMuted: false };
  }

  const length = 12;
  const drift =
    tone === "up" ? -0.06 : tone === "down" ? 0.06 : tone === "warn" ? -0.03 : 0;
  const start = parsed * (1 + drift);
  const amplitude = Math.max(Math.abs(parsed) * 0.012, 0.0001);
  const sparkline = Array.from({ length }, (_, index) => {
    const t = index / (length - 1);
    const wave = Math.sin(index * 0.85) * amplitude;
    return start + (parsed - start) * t + wave;
  });

  return { sparkline, sparklineMuted: false };
}

function withKpiSparkline(
  card: Omit<DashboardKpiCardVM, "sparkline" | "sparklineMuted" | "group" | "groupLabel" | "signalLabel">,
  spec: (typeof KPI_SPECS)[number],
): DashboardKpiCardVM {
  const { sparkline, sparklineMuted } = buildKpiSparkline(
    card.value,
    card.deltaTone,
    spec.mockSparkline,
    card.pending,
  );
  return {
    ...card,
    sparkline,
    sparklineMuted,
    group: spec.group,
    groupLabel: spec.group === "core" ? "经营核心" : "风险约束",
    signalLabel: resolveKpiSignalLabel(spec.id, card.deltaTone),
    relationLabel: spec.relationLabel,
  };
}

function resolveKpiSignalLabel(id: string, tone: DashboardDeltaTone): string | undefined {
  if (tone === "muted" || tone === "flat") {
    return undefined;
  }
  if (id === "dv01") {
    if (tone === "down") return "敞口下降";
    if (tone === "up" || tone === "warn") return "敞口上升";
  }
  if (id === "duration") {
    if (tone === "down") return "久期下降";
    if (tone === "up" || tone === "warn") return "久期上升";
  }
  if (id === "concentration") {
    if (tone === "down") return "集中度下降";
    if (tone === "up" || tone === "warn") return "集中度上升";
  }
  return undefined;
}

function pendingKpiCard(spec: (typeof KPI_SPECS)[number]): DashboardKpiCardVM {
  return withKpiSparkline(
    {
      id: spec.id,
      label: spec.label,
      value: GAP_VALUE,
      delta: GAP_DELTA,
      deltaTone: "muted",
      iconLabel: spec.iconLabel,
      pending: true,
    },
    spec,
  );
}

function mockKpiCard(spec: (typeof KPI_SPECS)[number]): DashboardKpiCardVM {
  return withKpiSparkline(
    {
      id: spec.id,
      label: spec.label,
      value: spec.mockValue,
      delta: spec.mockDelta,
      deltaTone: spec.mockTone,
      iconLabel: spec.iconLabel,
    },
    spec,
  );
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
      return withKpiSparkline(
        {
          id: spec.id,
          label: spec.label,
          value: durationRail.value,
          delta: durationRail.delta ?? GAP_DELTA,
          deltaTone: cockpitToneToDelta(durationRail.tone),
          iconLabel: spec.iconLabel,
        },
        spec,
      );
    }
    if (spec.id === "dv01" && dv01Rail?.value && dv01Rail.value !== "--") {
      return withKpiSparkline(
        {
          id: spec.id,
          label: spec.label,
          value: dv01Rail.value,
          delta: dv01Rail.delta ?? GAP_DELTA,
          deltaTone: cockpitToneToDelta(dv01Rail.tone),
          iconLabel: spec.iconLabel,
        },
        spec,
      );
    }
    if (spec.id === "concentration") {
      const top5 = cockpit.previewSignals.find((s) => s.id === "concentration");
      if (top5?.value && top5.value !== "--") {
        return withKpiSparkline(
          {
            id: spec.id,
            label: spec.label,
            value: top5.value,
            delta: top5.detail || GAP_DELTA,
            deltaTone: cockpitToneToDelta(top5.tone),
            iconLabel: spec.iconLabel,
          },
          spec,
        );
      }
    }
    if (metric?.value?.display && metric.value.display !== "--") {
      const delta = metric.delta?.display ?? GAP_DELTA;
      return withKpiSparkline(
        {
          id: spec.id,
          label: spec.label,
          value: metric.value.display,
          delta,
          deltaTone: metricToneToDelta(metric.tone, delta),
          iconLabel: spec.iconLabel,
        },
        spec,
      );
    }
    return pendingKpiCard(spec);
  });
}

function flatSparkline(value: number, length = 12): readonly number[] {
  return Array.from({ length }, () => value);
}

function sparklineFromTicker(item: DashboardCockpitTickerItem | undefined): readonly number[] {
  if (!item) {
    return flatSparkline(1);
  }
  const parsed = parseFloat(item.value.replace(/[^\d.-]/g, ""));
  const base = Number.isFinite(parsed) ? parsed : 1;
  return flatSparkline(base);
}

function parseMarketNumber(value: string | undefined): number | null {
  const parsed = Number(value?.replace(/[^\d.-]/g, "") ?? "");
  return Number.isFinite(parsed) ? parsed : null;
}

function findTickerByIds(
  ticker: readonly DashboardCockpitTickerItem[],
  ids: readonly string[],
): DashboardCockpitTickerItem | undefined {
  return ticker.find((item) => ids.includes(item.id));
}

function formatBpNumber(value: number): string {
  return `${value.toLocaleString("en-US", {
    minimumFractionDigits: Math.abs(value) < 10 ? 1 : 0,
    maximumFractionDigits: 1,
  })}bp`;
}

function buildDerivedMarketPulse(
  spec: (typeof MARKET_PULSE_LABELS)[number],
  ticker: readonly DashboardCockpitTickerItem[],
): DashboardMarketPulseVM | null {
  if (spec.id === "slope") {
    const oneYear = findTickerByIds(ticker, ["EMM00166458", "M003"]);
    const tenYear = findTickerByIds(ticker, ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"]);
    const oneYearValue = parseMarketNumber(oneYear?.value);
    const tenYearValue = parseMarketNumber(tenYear?.value);
    if (oneYearValue == null || tenYearValue == null) {
      return null;
    }
    const spreadBp = (oneYearValue - tenYearValue) * 100;
    const oneYearDelta = parseMarketNumber(oneYear?.delta);
    const tenYearDelta = parseMarketNumber(tenYear?.delta);
    const deltaBp =
      oneYearDelta != null && tenYearDelta != null ? oneYearDelta - tenYearDelta : null;
    return {
      id: spec.id,
      label: spec.label,
      value: formatBpNumber(spreadBp),
      delta: deltaBp == null ? GAP_DELTA : `${deltaBp > 0 ? "+" : ""}${formatBpNumber(deltaBp)}`,
      deltaTone: deltaBp == null ? "flat" : deltaBp > 0 ? "up" : deltaBp < 0 ? "down" : "flat",
      sparkline: flatSparkline(spreadBp, 7),
      statusLabel: oneYear?.status === "landed" && tenYear?.status === "landed" ? "同日" : "最近交易日",
      impactLabel: spec.impactLabel,
      isEstimated: true,
    };
  }

  if (spec.id === "credit-spread") {
    const credit = findTickerByIds(ticker, ["CN_CREDIT_AAA_1Y", "S0059650", "EMM00166655"]);
    const treasury = findTickerByIds(ticker, ["EMM00166458", "M003"]);
    const creditValue = parseMarketNumber(credit?.value);
    const treasuryValue = parseMarketNumber(treasury?.value);
    if (creditValue == null || treasuryValue == null) {
      return null;
    }
    const spreadBp = (creditValue - treasuryValue) * 100;
    return {
      id: spec.id,
      label: spec.label,
      value: formatBpNumber(spreadBp),
      delta: "同曲线",
      deltaTone: "flat",
      sparkline: flatSparkline(spreadBp, 7),
      statusLabel: credit?.status === "landed" && treasury?.status === "landed" ? "同日" : "最近交易日",
      impactLabel: spec.impactLabel,
      isEstimated: true,
    };
  }

  return null;
}

function buildMarketPulse(
  ticker: readonly DashboardCockpitTickerItem[],
  useMockFallback: boolean,
): DashboardMarketPulseVM[] {
  if (useMockFallback) {
    return DASHBOARD_MARKET_PULSE_MOCK.map((mock) => ({
      ...mock,
      impactLabel:
        MARKET_PULSE_LABELS.find((spec) => spec.id === mock.id)?.impactLabel ?? "市场观测",
    }));
  }

  return MARKET_PULSE_LABELS.map((spec) => {
    const item =
      ticker.find((t) => spec.matchIds.includes(t.id)) ??
      ticker.find((t) => spec.matchLabels.some((l) => t.label.includes(l)));
    const hasLiveValue = Boolean(item?.value && item.value !== "--");
    if (!hasLiveValue) {
      const derived = buildDerivedMarketPulse(spec, ticker);
      if (derived) {
        return derived;
      }
      return {
        id: spec.id,
        label: spec.label,
        value: GAP_VALUE,
        delta: PENDING_SYNC,
        deltaTone: "muted" as const,
        sparkline: flatSparkline(0),
        statusLabel: PENDING_SYNC,
        impactLabel: spec.impactLabel,
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
      impactLabel: spec.impactLabel,
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
    portfolioComparison?: PortfolioComparisonPayload | null;
    creditSpreadMigration?: CreditSpreadMigrationPayload | null;
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
      ? unsignedDisplay(numericDisplay(input.bondHeadline.kpis.weighted_coupon))
      : portfolioAllowed && input.portfolio?.weighted_coupon
        ? unsignedDisplay(numericDisplay(input.portfolio.weighted_coupon))
        : null;
  const couponRail = cockpit.metricRail.find((item) => item.id === "coupon");
  const bookCount = resolvePortfolioBookCount(input.portfolioComparison, input.reportDate);
  const dominantRating = resolveDominantIssuerRating(
    input.creditSpreadMigration,
    input.reportDate,
  );

  return [
    {
      id: "books",
      label: "组合数",
      value: bookCount != null ? `${bookCount.toLocaleString("en-US")} 个` : PENDING_SYNC,
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
    {
      id: "rating",
      label: "主导评级（Top1）",
      value: dominantRating ?? PENDING_SYNC,
    },
  ];
}

function resolvePortfolioBookCount(
  portfolioComparison: PortfolioComparisonPayload | null | undefined,
  reportDate: string,
): number | null {
  if (!isSameReportDate(reportDate, portfolioComparison?.report_date)) {
    return null;
  }
  const count =
    portfolioComparison?.items?.filter((item) => item.portfolio_name?.trim().length > 0).length ??
    0;
  return count > 0 ? count : null;
}

function resolveDominantIssuerRating(
  creditSpreadMigration: CreditSpreadMigrationPayload | null | undefined,
  reportDate: string,
): string | null {
  if (!isSameReportDate(reportDate, creditSpreadMigration?.report_date)) {
    return null;
  }
  const topItem = creditSpreadMigration?.concentration_by_rating?.top_items?.[0];
  const name = topItem?.name?.trim();
  return name && name.length > 0 ? name : null;
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
          yield: GAP_VALUE,
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

  const hasUsableWaterfall = hasUsableAttributionWaterfall(waterfall);
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
        yield: GAP_VALUE,
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

function mapDecisionStatus(status: BalanceAnalysisDecisionStatus): string {
  if (status === "pending") {
    return "待复核";
  }
  if (status === "confirmed") {
    return "已确认";
  }
  return "已关闭";
}

function buildTodos(
  alerts: readonly DashboardAlert[],
  decisionItems: readonly BalanceAnalysisDecisionItemStatusRow[] | null | undefined,
  useMockFallback: boolean,
): DashboardRiskTodoVM[] {
  if (useMockFallback) {
    return DASHBOARD_RISK_TODOS_MOCK.map((todo) => ({ ...todo }));
  }

  const pendingDecisionItems =
    decisionItems?.filter((row) => row.latest_status.status === "pending") ?? [];
  if (pendingDecisionItems.length > 0) {
    return pendingDecisionItems.slice(0, 4).map((row) => ({
      id: row.decision_key,
      title: row.title,
      priority: row.severity === "high" ? "高" : row.severity === "medium" ? "中" : "低",
      status: mapDecisionStatus(row.latest_status.status),
      path: "/decision-items",
    }));
  }

  if (alerts.length === 0) {
    return [];
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
  if (useMockFallback) {
    return DASHBOARD_WATCHLIST_MOCK.map((item) => ({ ...item }));
  }
  const usableRows = rows.filter((row) => row.status !== "blocked");
  if (usableRows.length === 0) {
    return [
      {
        id: "watch-gap",
        count: PENDING_SYNC,
        label: "观察清单",
        note: PENDING_SYNC,
        path: "/bond-analysis",
      },
    ];
  }
  return usableRows.slice(0, 5).map((row) => ({
    id: row.id,
    count: firstDisplayValue(row.maturity, row.yieldValue, row.dailyChange),
    label: row.name,
    note: row.reason,
    path: row.route,
  }));
}

function firstDisplayValue(...values: string[]): string {
  return values.find((value) => value && value !== "--") ?? "--";
}

function resolveInterbankNetPositionTone(
  netPosition: string,
  netRawYuan: number | null,
): DashboardDeltaTone {
  if (netPosition === PENDING_SYNC) {
    return "muted";
  }
  if (netRawYuan != null) {
    if (netRawYuan > 0) return "up";
    if (netRawYuan < 0) return "down";
    return "flat";
  }
  if (netPosition.startsWith("+")) return "up";
  if (netPosition.startsWith("-")) return "down";
  return "flat";
}

function buildInterbankDisplay(input: {
  coreMetrics?: CoreMetricsResult | null;
  reportDate: string;
  useMockFallback: boolean;
}): {
  interbankAssets: string;
  interbankLiabilities: string;
  interbankNetPosition: string;
  interbankNetPositionTone: DashboardDeltaTone;
} {
  if (input.useMockFallback) {
    return {
      interbankAssets: DASHBOARD_INTERBANK_MOCK.assets,
      interbankLiabilities: DASHBOARD_INTERBANK_MOCK.liabilities,
      interbankNetPosition: DASHBOARD_INTERBANK_MOCK.netPosition,
      interbankNetPositionTone: resolveInterbankNetPositionTone(
        DASHBOARD_INTERBANK_MOCK.netPosition,
        null,
      ),
    };
  }

  const coreAllowed = isSameReportDate(input.reportDate, input.coreMetrics?.report_date);
  const core = coreAllowed ? input.coreMetrics : null;
  const assets = numericDisplay(core?.interbank_assets.total_amount, PENDING_SYNC);
  const liabilities = numericDisplay(core?.interbank_liabilities.total_amount, PENDING_SYNC);
  const assetsRaw = numericRawInYuan(core?.interbank_assets.total_amount);
  const liabilitiesRaw = numericRawInYuan(core?.interbank_liabilities.total_amount);
  const netRawYuan =
    assetsRaw != null && liabilitiesRaw != null ? assetsRaw - liabilitiesRaw : null;
  const netPosition = netRawYuan != null ? formatYiSigned(netRawYuan) : PENDING_SYNC;

  return {
    interbankAssets: assets,
    interbankLiabilities: liabilities,
    interbankNetPosition: netPosition,
    interbankNetPositionTone: resolveInterbankNetPositionTone(netPosition, netRawYuan),
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
        dailyPnl: GAP_VALUE,
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
    dailyPnl: row.dailyChange !== "--" ? row.dailyChange : GAP_VALUE,
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

/** 真实模式无 bond_bucket_monthly 序列时的 pending 占位。 */
export const DASHBOARD_PRODUCT_PNL_PENDING: DashboardProductPnlTrendVM = {
  months: [],
  series: [],
  pending: true,
};

function buildProductPnlTrend(input: {
  useMockFallback: boolean;
  reportDate: string;
  bondBucketMonthly?: PnlByBusinessAnalysisPayload | null;
}): DashboardProductPnlTrendVM {
  if (input.useMockFallback) {
    return {
      months: DASHBOARD_PRODUCT_PNL_SERIES_MOCK.months,
      series: DASHBOARD_PRODUCT_PNL_SERIES_MOCK.series,
      pending: false,
    };
  }
  return buildDashboardProductPnlTrendFromBondBucketMonthly(
    input.bondBucketMonthly,
    input.reportDate,
  );
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

const ATTRIBUTION_NOTE_PENDING = "归因说明待同步";

const GENERIC_JUDGMENT_CONCLUSION_PATTERNS = [
  "数据状态需先复核",
  "等待下一组观测",
  "尚无有效判断载荷",
] as const;

function isGenericJudgmentConclusion(conclusion: string): boolean {
  return GENERIC_JUDGMENT_CONCLUSION_PATTERNS.some((pattern) => conclusion.includes(pattern));
}

function buildAttributionNote(input: {
  judgment: VerdictPayload;
  useMockFallback: boolean;
}): readonly string[] {
  if (input.useMockFallback) {
    return DASHBOARD_ATTRIBUTION_NOTE_MOCK;
  }

  const conclusion = input.judgment.conclusion.trim();
  if (conclusion.length > 0 && !isGenericJudgmentConclusion(conclusion)) {
    return [conclusion];
  }

  if (input.judgment.reasons.length > 0) {
    return input.judgment.reasons
      .slice(0, 3)
      .map((reason) => {
        const detail = reason.detail.trim();
        return detail.length > 0
          ? `${reason.label}：${reason.value}，${detail}`
          : `${reason.label}：${reason.value}`;
      });
  }

  if (input.judgment.suggestions.length > 0) {
    return input.judgment.suggestions.slice(0, 2).map((suggestion) => suggestion.text);
  }

  return [ATTRIBUTION_NOTE_PENDING];
}

function parseWaterfallNumeric(value: string): number | null {
  const parsed = parseFloat(value.replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function isAttributionSegment(item: DashboardCockpitWaterfallItem): boolean {
  return item.id !== "total" && !item.label.includes("综合");
}

const WATERFALL_KNOWN_UNIT_PATTERN = /[万亿%bp]/;

/** 归因瀑布数值展示：有单位则原样；纯数字不盲补「万」。 */
export function formatWaterfallValueDisplay(value: string): string {
  if (value === GAP_VALUE || value === PENDING_SYNC) {
    return value;
  }
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return GAP_DELTA;
  }
  if (WATERFALL_KNOWN_UNIT_PATTERN.test(trimmed)) {
    return trimmed;
  }
  if (/^[-+]?[\d,]+(?:\.\d+)?$/.test(trimmed)) {
    return GAP_DELTA;
  }
  return trimmed;
}

function findAttributionExtremes(waterfall: readonly DashboardCockpitWaterfallItem[]): {
  maxDrag: DashboardCockpitWaterfallItem | null;
  maxContribution: DashboardCockpitWaterfallItem | null;
} {
  let maxDrag: DashboardCockpitWaterfallItem | null = null;
  let maxDragValue = 0;
  let maxContribution: DashboardCockpitWaterfallItem | null = null;
  let maxContributionValue = 0;

  for (const item of waterfall) {
    if (!isAttributionSegment(item)) {
      continue;
    }
    const numeric = parseWaterfallNumeric(item.value);
    if (numeric == null) {
      continue;
    }
    if (numeric < 0 && (maxDrag == null || numeric < maxDragValue)) {
      maxDrag = item;
      maxDragValue = numeric;
    }
    if (numeric > 0 && (maxContribution == null || numeric > maxContributionValue)) {
      maxContribution = item;
      maxContributionValue = numeric;
    }
  }

  return { maxDrag, maxContribution };
}

function verdictToneToSidebarTone(tone: VerdictPayload["tone"]): DashboardDecisionSidebarTone {
  if (tone === "positive") return "positive";
  if (tone === "negative") return "negative";
  if (tone === "warning") return "warning";
  return "neutral";
}

function buildKeyRiskBody(input: {
  concentration: DashboardKpiCardVM | undefined;
  alertCount: number;
  riskAlertCounts: DashboardRiskAlertCountVM[];
  useMockFallback: boolean;
}): string {
  const parts: string[] = [];
  const concentration = input.concentration;

  if (concentration && concentration.value !== GAP_VALUE && !concentration.pending) {
    parts.push(`${concentration.label} ${concentration.value}，${concentration.delta}`);
  } else if (concentration) {
    parts.push(`${concentration.label} ${PENDING_SYNC}`);
  }

  const highRisk = input.riskAlertCounts.find((item) => item.id === "high");
  const hasTierBreakdown = input.useMockFallback
    || input.riskAlertCounts.some((item) => item.id !== "high" && item.count > 0);
  if (input.alertCount > 0) {
    if (hasTierBreakdown) {
      parts.push(
        `预警 ${input.alertCount} 项${highRisk && highRisk.count > 0 ? `（高风险 ${highRisk.count}）` : ""}`,
      );
    } else {
      parts.push(`待复核 ${input.alertCount} 项`);
    }
  } else if (parts.length > 0) {
    parts.push("当前无开放预警");
  }

  return parts.length > 0 ? parts.join("；") : PENDING_SYNC;
}

function buildTodosSectionBody(
  todos: readonly DashboardRiskTodoVM[],
  alertCount: number,
): { body: string; badge?: string } {
  if (todos.length === 0 && alertCount === 0) {
    return { body: "暂无待办事项" };
  }

  const lines = todos.slice(0, 3).map((todo) => `${todo.title}（${todo.priority}·${todo.status}）`);
  return {
    body: lines.length > 0 ? lines.join("；") : PENDING_SYNC,
    badge: alertCount > 0 ? `${alertCount} 项预警` : undefined,
  };
}

function buildSuggestedActionsBody(input: {
  judgment: VerdictPayload;
  attributionNote: readonly string[];
}): string {
  if (input.judgment.reasons.length > 0) {
    return input.judgment.reasons
      .slice(0, 3)
      .map((reason) => {
        const detail = reason.detail.trim();
        return detail.length > 0
          ? `${reason.label}：${reason.value}，${detail}`
          : `${reason.label}：${reason.value}`;
      })
      .join("；");
  }

  if (input.judgment.suggestions.length > 0) {
    return input.judgment.suggestions
      .slice(0, 3)
      .map((suggestion) => suggestion.text)
      .join("；");
  }

  if (input.attributionNote.length > 0) {
    return input.attributionNote.slice(0, 2).join(" ");
  }

  return PENDING_SYNC;
}

function firstAvailableText(values: readonly (string | null | undefined)[]): string {
  return values.find((value) => {
    const text = value?.trim() ?? "";
    return text.length > 0 && text !== GAP_VALUE && text !== GAP_DELTA && text !== PENDING_SYNC;
  }) ?? PENDING_SYNC;
}

function marketFocusScore(item: DashboardMarketPulseVM): number {
  const toneScore =
    item.deltaTone === "warn"
      ? 1_000
      : item.deltaTone === "up" || item.deltaTone === "down"
        ? 500
        : 0;
  const deltaMagnitude = Math.min(Math.abs(parseMarketNumber(item.delta) ?? 0), 100);
  return toneScore + deltaMagnitude;
}

function buildMarketFocus(marketPulse: readonly DashboardMarketPulseVM[]): {
  body: string;
  tone: DashboardDecisionSpineTone;
} {
  const candidates = marketPulse.filter(
    (item) =>
      !item.isEstimated &&
      item.value !== GAP_VALUE &&
      item.statusLabel !== PENDING_SYNC &&
      item.deltaTone !== "muted",
  );
  const focus =
    candidates
      .filter((item) => item.deltaTone !== "flat")
      .sort((a, b) => marketFocusScore(b) - marketFocusScore(a))[0] ??
    candidates.sort((a, b) => marketFocusScore(b) - marketFocusScore(a))[0];
  if (!focus) {
    return { body: PENDING_SYNC, tone: "muted" };
  }
  const qualifiers = [
    focus.statusLabel && focus.statusLabel !== "同日" ? focus.statusLabel : null,
    focus.isEstimated ? "估算" : null,
  ].filter(Boolean);
  const qualifierText = qualifiers.length > 0 ? `（${qualifiers.join("·")}）` : "";
  return {
    body: `${focus.label} ${focus.value}，${focus.delta}${qualifierText}`,
    tone: focus.deltaTone === "warn" ? "warning" : focus.deltaTone === "muted" ? "muted" : "info",
  };
}

function buildPnlDriver(waterfall: readonly DashboardCockpitWaterfallItem[]): string {
  const { maxDrag, maxContribution } = findAttributionExtremes(waterfall);
  const drag = maxDrag ? `拖累 ${maxDrag.label} ${formatWaterfallValueDisplay(maxDrag.value)}` : null;
  const contribution = maxContribution
    ? `贡献 ${maxContribution.label} ${formatWaterfallValueDisplay(maxContribution.value)}`
    : null;
  return firstAvailableText([drag && contribution ? `${drag}；${contribution}` : drag ?? contribution]);
}

export function buildDecisionSpine(input: {
  headerStatus: DashboardCockpitHeaderStatus;
  judgment: VerdictPayload;
  kpiCards: DashboardKpiCardVM[];
  marketPulse: readonly DashboardMarketPulseVM[];
  attributionWaterfall: readonly DashboardCockpitWaterfallItem[];
  alertCount: number;
  riskAlertCounts: DashboardRiskAlertCountVM[];
  todos: readonly DashboardRiskTodoVM[];
  dataSource: "real" | "mock";
  dataWarningMessages: readonly string[];
  snapshotPartialNote?: string | null;
  useMockFallback: boolean;
}): DashboardDecisionSpineVM {
  const aum = input.kpiCards.find((card) => card.id === "aum");
  const duration = input.kpiCards.find((card) => card.id === "duration");
  const concentration = input.kpiCards.find((card) => card.id === "concentration");
  const marketFocus = buildMarketFocus(input.marketPulse);
  const portfolioImpact = firstAvailableText([
    aum && !aum.pending ? `${aum.label} ${aum.value}` : null,
    duration && !duration.pending ? `${duration.label} ${duration.value}` : null,
  ]);
  const pnlDriver = buildPnlDriver(input.attributionWaterfall);
  const riskConstraint = buildKeyRiskBody({
    concentration,
    alertCount: input.alertCount,
    riskAlertCounts: input.riskAlertCounts,
    useMockFallback: input.useMockFallback,
  });
  const topTodo = input.todos[0];
  const nextAction = topTodo
    ? `${topTodo.title}（${topTodo.priority}·${topTodo.status}）`
    : buildSuggestedActionsBody({ judgment: input.judgment, attributionNote: [] });
  const firstBlockingWarning = input.dataWarningMessages.find(isFirstScreenBlockingWarning);
  const evidenceState =
    input.dataSource === "mock"
      ? "数据使用本地模拟数据"
      : (input.snapshotPartialNote?.trim() || firstBlockingWarning)
        ?? `${input.headerStatus.dataSyncPrefix} ${input.headerStatus.dataUpdatedAt}`;
  const useMockSource = input.useMockFallback || input.dataSource === "mock";
  const marketSource = useMockSource
    ? decisionSource("mock-fallback")
    : marketFocus.body === PENDING_SYNC
      ? decisionSource("pending")
      : decisionSourceWithLabel("derived", "市场上下文");
  const portfolioSource = realDecisionSource(
    useMockSource,
    portfolioImpact === PENDING_SYNC ? "pending" : "derived",
  );
  const riskSource =
    input.snapshotPartialNote || firstBlockingWarning
      ? resolveMainlineDecisionSource(input)
      : realDecisionSource(
          useMockSource,
          firstAvailableText([riskConstraint, nextAction]) === PENDING_SYNC
            ? "pending"
            : "derived",
        );

  return {
    marketFocus: marketFocus.body,
    portfolioImpact,
    pnlDriver,
    riskConstraint,
    nextAction,
    evidenceState,
    rail: [
      {
        id: "market-focus",
        label: "市场关注",
        value: marketFocus.body,
        tone: marketFocus.tone,
        href: `#${DASHBOARD_HOME_MARKET_TARGET}`,
        targetId: DASHBOARD_HOME_MARKET_TARGET,
        ...marketSource,
      },
      {
        id: "portfolio-impact",
        label: "组合影响",
        value: portfolioImpact,
        tone: portfolioImpact === PENDING_SYNC ? "muted" : "info",
        href: `#${DASHBOARD_HOME_PORTFOLIO_TARGET}`,
        targetId: DASHBOARD_HOME_PORTFOLIO_TARGET,
        ...portfolioSource,
      },
      {
        id: "risk-focus",
        label: "需处置项",
        value: firstAvailableText([riskConstraint, nextAction]),
        tone: input.alertCount > 0 ? "warning" : "neutral",
        href: `#${DASHBOARD_HOME_RISK_TARGET}`,
        targetId: DASHBOARD_HOME_RISK_TARGET,
        ...riskSource,
      },
    ],
  };
}

/** 侧舱六段：仅格式化/拼接 viewModel 已有字段，不做正式金融计算。riskRadar / quickDrilldown 仍为 mock，见 build 处注释。 */
export function buildDecisionSidebarSections(input: {
  judgment: VerdictPayload;
  kpiCards: DashboardKpiCardVM[];
  attributionWaterfall: readonly DashboardCockpitWaterfallItem[];
  attributionNote: readonly string[];
  alertCount: number;
  riskAlertCounts: DashboardRiskAlertCountVM[];
  todos: readonly DashboardRiskTodoVM[];
  useMockFallback: boolean;
  decisionSpine?: DashboardDecisionSpineVM;
  riskReviewOnly?: boolean;
  snapshotPartialNote?: string | null;
  dataWarningMessages?: readonly string[];
}): DashboardDecisionSidebarSectionVM[] {
  const conclusion = input.judgment.conclusion.trim();
  const concentration = input.kpiCards.find((card) => card.id === "concentration");
  const { maxDrag, maxContribution } = findAttributionExtremes(input.attributionWaterfall);
  const attributionExtremeEvidenceLabel =
    maxDrag || maxContribution ? "归因瀑布" : "归因极值待确认";
  const attributionExtremeSource = realDecisionSource(
    input.useMockFallback,
    maxDrag || maxContribution ? "derived" : "pending",
  );
  const todosSection = buildTodosSectionBody(input.todos, input.alertCount);
  const hasRiskTierBreakdown = input.useMockFallback
    || input.riskAlertCounts.some((item) => item.id !== "high" && item.count > 0);
  const riskReviewOnly = input.riskReviewOnly ?? (!hasRiskTierBreakdown && input.alertCount > 0);

  return [
    {
      id: "mainline",
      title: "今日主线",
      body: conclusion || PENDING_SYNC,
      tone: verdictToneToSidebarTone(input.judgment.tone),
      evidenceLabel: input.decisionSpine?.evidenceState,
      statusLabel: input.decisionSpine?.marketFocus,
      href: `#${DASHBOARD_HOME_MARKET_TARGET}`,
      targetId: DASHBOARD_HOME_MARKET_TARGET,
      ...resolveMainlineDecisionSource({
        useMockFallback: input.useMockFallback,
        snapshotPartialNote: input.snapshotPartialNote,
        dataWarningMessages: input.dataWarningMessages,
      }),
    },
    {
      id: "key-risk",
      title: "关键风险",
      body: buildKeyRiskBody({
        concentration,
        alertCount: input.alertCount,
        riskAlertCounts: input.riskAlertCounts,
        useMockFallback: input.useMockFallback,
      }),
      tone:
        input.alertCount > 0 || concentration?.deltaTone === "warn" ? "warning" : "neutral",
      evidenceLabel: riskReviewOnly ? "待复核口径" : "风险计数",
      href: `#${DASHBOARD_HOME_RISK_TARGET}`,
      targetId: DASHBOARD_HOME_RISK_TARGET,
      ...realDecisionSource(input.useMockFallback, riskReviewOnly ? "pending" : "governed"),
    },
    {
      id: "max-drag",
      title: "最大拖累",
      body: maxDrag
        ? `${maxDrag.label} ${formatWaterfallValueDisplay(maxDrag.value)}`
        : PENDING_SYNC,
      tone: maxDrag ? "negative" : "neutral",
      evidenceLabel: attributionExtremeEvidenceLabel,
      href: `#${DASHBOARD_HOME_PORTFOLIO_TARGET}`,
      targetId: DASHBOARD_HOME_PORTFOLIO_TARGET,
      ...attributionExtremeSource,
    },
    {
      id: "max-contribution",
      title: "最大贡献",
      body: maxContribution
        ? `${maxContribution.label} ${formatWaterfallValueDisplay(maxContribution.value)}`
        : PENDING_SYNC,
      tone: maxContribution ? "positive" : "neutral",
      evidenceLabel: attributionExtremeEvidenceLabel,
      href: `#${DASHBOARD_HOME_PORTFOLIO_TARGET}`,
      targetId: DASHBOARD_HOME_PORTFOLIO_TARGET,
      ...attributionExtremeSource,
    },
    {
      id: "pending-todos",
      title: "待处理事项",
      body: todosSection.body,
      tone: input.todos.some((todo) => todo.priority === "高") ? "warning" : "neutral",
      badge: todosSection.badge,
      evidenceLabel: "待办队列",
      href: `#${DASHBOARD_HOME_RISK_TARGET}`,
      targetId: DASHBOARD_HOME_RISK_TARGET,
      ...realDecisionSource(input.useMockFallback, input.todos.length > 0 ? "governed" : "static-ui"),
    },
    {
      id: "suggested-actions",
      title: "建议动作",
      body: buildSuggestedActionsBody({
        judgment: input.judgment,
        attributionNote: input.attributionNote,
      }),
      tone: "neutral",
      statusLabel: input.decisionSpine?.nextAction,
      evidenceLabel: "经营判断",
      href: `#${DASHBOARD_HOME_RISK_TARGET}`,
      targetId: DASHBOARD_HOME_RISK_TARGET,
      ...realDecisionSource(input.useMockFallback, "derived"),
    },
  ];
}

function buildExecutiveOverview(input: {
  kpiCards: readonly DashboardKpiCardVM[];
  judgment: VerdictPayload;
  dataWarningMessages: readonly string[];
  useMockFallback: boolean;
}): DashboardExecutiveOverviewVM {
  const { kpiCards } = input;
  const coreMetrics = kpiCards.filter((card) => card.group === "core");
  const riskConstraints = kpiCards.filter((card) => card.group === "risk");
  const healthSource =
    coreMetrics.find((card) => card.id === "aum" && !card.pending) ??
    coreMetrics.find((card) => !card.pending) ??
    coreMetrics[0];
  const hasPendingMetric = kpiCards.some((card) => card.pending);
  const hasBlockingWarnings =
    input.dataWarningMessages.some(isFirstScreenBlockingWarning) || hasPendingMetric;
  const judgmentConclusion = input.judgment.conclusion.trim();
  const sanitizedJudgmentConclusion = sanitizeExecutiveOverviewJudgment(judgmentConclusion);
  const summary = input.useMockFallback
    ? "当前为本地模拟数据，经营指标仅用于版式和流程演示，正式判断需等待真实快照。"
    : hasBlockingWarnings
      ? "部分指标仍待同步或复核，经营判断暂按当前可用数据展示，需先确认口径后再做方向性动作。"
      : sanitizedJudgmentConclusion.length > 0 &&
          !isGenericJudgmentConclusion(sanitizedJudgmentConclusion)
        ? sanitizedJudgmentConclusion
        : "同日报告日数据已落地，核心经营指标可用于当日复核，方向性结论待正式判断补充。";

  return {
    summary,
    coreMetrics,
    riskConstraints,
    healthLabel: "经营健康度",
    healthText: hasBlockingWarnings || input.useMockFallback
      ? "数据链路待复核，核心指标不生成正式结论。"
      : input.dataWarningMessages.length > 0
        ? "首屏核心指标已进入可复核区间；下方缺口保留局部空态。"
      : "核心指标已进入可复核区间。",
    healthSparkline: healthSource?.sparkline ?? flatSparkline(0, 12),
  };
}

function sanitizeExecutiveOverviewJudgment(conclusion: string): string {
  return conclusion.replaceAll("正式经营判断", "首页快照判断");
}

function isFirstScreenBlockingWarning(message: string): boolean {
  return (
    !message.startsWith("资产分布") &&
    !message.startsWith("归因收益率待读取")
  );
}

const AI_DECISION_SUMMARY_ORDER: readonly DashboardAiDecisionSummaryItemVM["id"][] = [
  "mainline",
  "max-drag",
  "max-contribution",
  "key-risk",
  "suggested-actions",
  "pending-todos",
];

const AI_DECISION_TITLE_OVERRIDES: Partial<
  Record<DashboardAiDecisionSummaryItemVM["id"], string>
> = {
  mainline: "今日结论",
};

function buildAiDecisionSummary(
  sections: readonly DashboardDecisionSidebarSectionVM[],
): DashboardAiDecisionSummaryItemVM[] {
  const sectionById = new Map(sections.map((section) => [section.id, section]));
  return AI_DECISION_SUMMARY_ORDER.flatMap((id) => {
    const section = sectionById.get(id);
    if (!section) {
      return [];
    }
    return [
      {
        id,
        title: AI_DECISION_TITLE_OVERRIDES[id] ?? section.title,
        body: section.body,
        tone: section.tone,
        badge: section.badge,
        evidenceLabel: section.evidenceLabel,
        statusLabel: section.statusLabel,
        href: section.href,
        targetId: section.targetId,
        sourceType: section.sourceType,
        sourceLabel: section.sourceLabel,
      },
    ];
  });
}

function buildRiskActionStrip(input: {
  radar: DashboardRiskRadarVM;
  alertCounts: readonly DashboardRiskAlertCountVM[];
  totalAlerts: number;
  todos: readonly DashboardRiskTodoVM[];
  watchlist: readonly DashboardWatchItemVM[];
  riskReviewOnly: boolean;
  usesMockRiskRadar: boolean;
}): DashboardRiskActionStripVM {
  return {
    radar: input.radar,
    alertCounts: input.alertCounts,
    totalAlerts: input.totalAlerts,
    todoCount: input.todos.length,
    highPriorityTodoCount: input.todos.filter((todo) => todo.priority === "高").length,
    watchCount: input.watchlist.length,
    riskReviewOnly: input.riskReviewOnly,
    usesMockRiskRadar: input.usesMockRiskRadar,
    entryHref: "/risk-tensor",
  };
}

function buildRiskAlertCounts(
  alerts: readonly DashboardAlert[],
  useMockFallback: boolean,
): DashboardRiskAlertCountVM[] {
  if (useMockFallback) {
    return DASHBOARD_RISK_ALERT_COUNTS_MOCK.map((item) => ({
      id: item.id,
      label: item.label,
      count: item.count,
      tone: item.tone as DashboardDeltaTone,
    }));
  }

  const counts = { high: 0, medium: 0, low: 0 };
  for (const alert of alerts) {
    counts[alert.severity] += 1;
  }

  return [
    {
      id: "high",
      label: "高风险预警",
      count: counts.high,
      tone: counts.high > 0 ? "warn" : "flat",
    },
    {
      id: "medium",
      label: "中风险预警",
      count: counts.medium,
      tone: counts.medium > 0 ? "warn" : "flat",
    },
    {
      id: "low",
      label: "低风险预警",
      count: counts.low,
      tone: counts.low > 0 ? "flat" : "flat",
    },
  ];
}

const RISK_RADAR_SPECS: ReadonlyArray<{ riskId: string; label: string }> = [
  { riskId: "dv01", label: "利率风险" },
  { riskId: "duration", label: "久期风险" },
  { riskId: "issuer-top5", label: "集中度风险" },
  { riskId: "credit-weight", label: "信用风险" },
];

export function buildRiskRadarFromRiskItems(
  riskItems: readonly DashboardCockpitRiskItem[],
  useMockFallback: boolean,
): { radar: DashboardRiskRadarVM; usesMock: boolean } {
  if (useMockFallback) {
    return {
      radar: {
        dimensions: [...DASHBOARD_RISK_RADAR_MOCK.dimensions],
        values: [...DASHBOARD_RISK_RADAR_MOCK.values],
      },
      usesMock: true,
    };
  }

  const byId = new Map(riskItems.map((item) => [item.id, item]));
  const dimensions: string[] = [];
  const values: number[] = [];

  for (const spec of RISK_RADAR_SPECS) {
    const item = byId.get(spec.riskId);
    if (item && item.status !== "blocked" && item.level > 0) {
      dimensions.push(spec.label);
      values.push(item.level);
    }
  }

  if (dimensions.length >= 3) {
    return {
      radar: { dimensions, values, pending: false },
      usesMock: false,
    };
  }

  const usable = riskItems.filter((item) => item.status !== "blocked" && item.level > 0);
  if (usable.length >= 3) {
    return {
      radar: {
        dimensions: usable.map((item) => item.label),
        values: usable.map((item) => item.level),
        pending: false,
      },
      usesMock: false,
    };
  }

  return {
    radar: { dimensions: [], values: [], pending: true },
    usesMock: false,
  };
}

function resolveRiskReviewOnly(
  useMockFallback: boolean,
  riskAlertCounts: readonly DashboardRiskAlertCountVM[],
): boolean {
  if (useMockFallback) {
    return false;
  }
  return !riskAlertCounts.some((item) => item.id !== "high" && item.count > 0);
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
  useMockFallback?: boolean;
}): DashboardCockpitHeaderStatus {
  const useMockFallback = input.useMockFallback === true;
  const alertCount = input.alertCount ?? DASHBOARD_COCKPIT_HEADER_STATUS.notificationCount;
  const hasSnapshotTime = Boolean(input.snapshotMeta?.generated_at?.trim());
  const dataFreshnessState = useMockFallback
    ? "mock-fallback"
    : hasSnapshotTime
      ? "fresh"
      : "missing-snapshot-time";
  const valuation =
    dataFreshnessState !== "fresh"
      ? { label: "估值待同步" as const, tone: "muted" as const }
      : { label: "估值已完成" as const, tone: "ok" as const };

  const dataUpdatedAt =
    formatMetaGeneratedAtTime(input.snapshotMeta?.generated_at) ??
    (dataFreshnessState === "mock-fallback"
      ? DASHBOARD_COCKPIT_HEADER_STATUS.dataUpdatedAt
      : PENDING_SYNC);
  const dataSyncPrefix =
    dataFreshnessState === "mock-fallback"
      ? "数据使用本地模拟数据"
      : dataFreshnessState === "fresh"
        ? "数据已更新"
        : "数据时间待同步";

  return {
    dataUpdatedAt,
    marketStatus: resolveMarketStatusLabel({
      marketMeta: input.marketMeta,
      reportDate: input.reportDate,
    }),
    notificationCount: alertCount,
    dataSyncPrefix,
    valuationLabel: valuation.label,
    valuationTone: valuation.tone,
    dataFreshnessState,
    riskReviewCount: alertCount,
    showRiskReview: alertCount > 0,
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
  portfolioComparison?: PortfolioComparisonPayload | null;
  creditSpreadMigration?: CreditSpreadMigrationPayload | null;
  decisionItems?: readonly BalanceAnalysisDecisionItemStatusRow[] | null;
  attribution?: DashboardPnlAttributionVM | null;
  bondBucketMonthly?: PnlByBusinessAnalysisPayload | null;
  /** API 失败或空序列时回落到 dashboardMockData 演示数 */
  useMockFallback?: boolean;
};

function buildDataWarningMessages(input: {
  useMockFallback: boolean;
  home: DashboardHomeModel;
  kpiCards: DashboardKpiCardVM[];
  marketPulse: DashboardMarketPulseVM[];
  portfolioStats: DashboardPortfolioStatVM[];
  attributionYieldMissing: boolean;
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

  if (hasPendingKpi || hasPendingMarket) {
    warnings.push("部分指标待同步");
  }
  if (hasPendingPortfolio) {
    warnings.push(...buildPortfolioStatsWarningMessages(input.portfolioStats));
  }
  if (input.kpiCards.some((card) => card.delta.includes("口径"))) {
    warnings.push("部分指标口径待确认");
  }
  if (input.attributionYieldMissing) {
    warnings.push(ATTRIBUTION_YIELD_MISSING_WARNING);
  }
  if (input.home.attentionItems.length > 0) {
    warnings.push(...input.home.attentionItems);
  }
  if (input.home.snapshotPartialNote) {
    warnings.push(input.home.snapshotPartialNote);
  }
  return warnings;
}

function buildPortfolioStatsWarningMessages(
  portfolioStats: readonly DashboardPortfolioStatVM[],
): string[] {
  const messages: string[] = [];
  for (const stat of portfolioStats) {
    if (stat.value !== PENDING_SYNC) {
      continue;
    }
    if (stat.id === "books") {
      messages.push(PORTFOLIO_BOOKS_PENDING_WARNING);
    } else if (stat.id === "positions") {
      messages.push(PORTFOLIO_POSITIONS_PENDING_WARNING);
    } else if (stat.id === "coupon") {
      messages.push(PORTFOLIO_COUPON_PENDING_WARNING);
    } else if (stat.id === "rating") {
      messages.push(PORTFOLIO_RATING_PENDING_WARNING);
    }
  }
  return messages;
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
  const aumCard = kpiCards.find((card) => card.id === "aum");
  const aumKpiLabel = KPI_SPECS.find((spec) => spec.id === "aum")?.label ?? "债券资产规模";
  const portfolioCenterAum: DashboardPortfolioCenterAumVM = {
    value: aumCard?.value ?? GAP_VALUE,
    label: aumCard?.label ?? aumKpiLabel,
  };
  const marketPulse = buildMarketPulse(cockpit.marketTicker, useMockFallback);
  const portfolioStats = buildPortfolioStats(cockpit, useMockFallback, {
    reportDate,
    bondHeadline: input.bondHeadline,
    portfolio: input.portfolio,
    portfolioComparison: input.portfolioComparison,
    creditSpreadMigration: input.creditSpreadMigration,
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
    attributionYieldMissing: Boolean(input.attribution?.total.display),
  });
  const alertCount = useMockFallback
    ? DASHBOARD_RISK_ALERT_COUNTS_MOCK.reduce((sum, item) => sum + item.count, 0)
    : home.alerts.length;
  const riskAlertCounts = buildRiskAlertCounts(home.alerts, useMockFallback);
  const riskReviewOnly = resolveRiskReviewOnly(useMockFallback, riskAlertCounts);
  const riskRadarBundle = buildRiskRadarFromRiskItems(cockpit.riskItems, useMockFallback);
  const attributionWaterfall = buildAttributionWaterfall(
    cockpit.waterfall,
    useMockFallback,
    input.attribution,
  );
  const attributionNote = buildAttributionNote({
    judgment: home.judgment,
    useMockFallback,
  });
  const todos = buildTodos(home.alerts, input.decisionItems, useMockFallback);
  const headerStatus = buildDashboardCockpitHeaderStatus({
    snapshotMeta: useMockFallback ? null : input.snapshotMeta,
    marketMeta: useMockFallback ? null : input.marketMeta,
    reportDate,
    alertCount,
    useMockFallback,
  });
  const decisionSpine = buildDecisionSpine({
    headerStatus,
    judgment: home.judgment,
    kpiCards,
    marketPulse,
    attributionWaterfall,
    alertCount,
    riskAlertCounts,
    todos,
    dataSource,
    dataWarningMessages: warnings,
    snapshotPartialNote: home.snapshotPartialNote,
    useMockFallback,
  });
  const watchlist = buildWatchlist(cockpit.watchRows, useMockFallback);
  const decisionSidebarSections = buildDecisionSidebarSections({
    judgment: home.judgment,
    kpiCards,
    attributionWaterfall,
    attributionNote,
    alertCount,
    riskAlertCounts,
    todos,
    useMockFallback,
    decisionSpine,
    riskReviewOnly,
    snapshotPartialNote: home.snapshotPartialNote,
    dataWarningMessages: warnings,
  });

  return {
    reportDate,
    headerStatus,
    navGroups: DASHBOARD_COCKPIT_NAV_GROUPS,
    kpiCards,
    executiveOverview: buildExecutiveOverview({
      kpiCards,
      judgment: home.judgment,
      dataWarningMessages: warnings,
      useMockFallback,
    }),
    portfolioCenterAum,
    marketPulse,
    portfolioStats,
    assetBars: buildAssetBars(cockpit, useMockFallback),
    interbankAssets: interbank.interbankAssets,
    interbankLiabilities: interbank.interbankLiabilities,
    interbankNetPosition: interbank.interbankNetPosition,
    interbankNetPositionTone: interbank.interbankNetPositionTone,
    attributionTabs: buildAttributionTabs(
      cockpit.waterfall,
      useMockFallback,
      input.attribution,
    ),
    activeAttributionTab: "day",
    attributionWaterfall,
    attributionNote,
    riskRadar: riskRadarBundle.radar,
    alertCount,
    riskAlertCounts,
    todos,
    watchlist,
    exposureRows: buildExposureRows(cockpit, useMockFallback),
    balanceMetrics: buildBalanceMetrics(metrics ?? undefined, useMockFallback),
    productPnl: buildProductPnlTrend({
      useMockFallback,
      reportDate,
      bondBucketMonthly: input.bondBucketMonthly,
    }),
    quickDrilldowns: DASHBOARD_QUICK_DRILLDOWN_MOCK,
    riskReviewOnly,
    usesMockRiskRadar: riskRadarBundle.usesMock,
    usesStaticQuickDrilldown: true,
    decisionSidebarSections,
    aiDecisionSummary: buildAiDecisionSummary(decisionSidebarSections),
    riskActionStrip: buildRiskActionStrip({
      radar: riskRadarBundle.radar,
      alertCounts: riskAlertCounts,
      totalAlerts: alertCount,
      todos,
      watchlist,
      riskReviewOnly,
      usesMockRiskRadar: riskRadarBundle.usesMock,
    }),
    decisionSpine,
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
