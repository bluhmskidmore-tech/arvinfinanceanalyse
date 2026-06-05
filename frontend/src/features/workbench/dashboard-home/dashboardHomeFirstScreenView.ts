import type {
  BondDashboardHeadlinePayload,
  BondPortfolioHeadlinesPayload,
  Numeric,
  ResultMeta,
  VerdictPayload,
} from "../../../api/contracts";
import type {
  HomeSnapshotOverviewMetricVM,
  HomeSnapshotPnlAttributionVM,
} from "./dashboardHomeSnapshotAdapter";
import {
  DASHBOARD_COCKPIT_HEADER_STATUS,
  DASHBOARD_COCKPIT_REPORT_DATE,
  DASHBOARD_MARKET_PULSE_MOCK,
} from "../dashboard/dashboardMockData";
import type {
  DashboardHomeFirstScreenView,
  HomeDataStateKind,
  HomeDeltaTone,
  HomeRiskTicker,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";

type NumericLike = Numeric | string | number | null | undefined;

export type MapToHomeFirstScreenViewInput = {
  reportDate: string;
  useMockFallback: boolean;
  verdict: VerdictPayload | null;
  metrics: readonly HomeSnapshotOverviewMetricVM[];
  attribution: HomeSnapshotPnlAttributionVM | null;
  bondHeadline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  snapshotMeta: ResultMeta | null;
  alertCount: number;
  snapshotUnavailable: boolean;
  snapshotStale: boolean;
};

const GAP = "—";

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

function formatYiSigned(rawYuan: number): string {
  return formatYi(rawYuan, true);
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

function stripDisplayUnit(display: string): { value: string; unit: string } {
  const trimmed = display.trim();
  if (!trimmed || trimmed === GAP) {
    return { value: trimmed, unit: "" };
  }
  const spaced = trimmed.match(/^([+\-]?[\d,]+(?:\.\d+)?)\s*(亿|万|元|%|bp|pp)$/);
  if (spaced) {
    return { value: spaced[1]!, unit: spaced[2]! };
  }
  const tight = trimmed.match(/^([+\-]?[\d,]+(?:\.\d+)?)(%|bp|pp)$/);
  if (tight) {
    return { value: tight[1]!, unit: tight[2]! };
  }
  return { value: trimmed, unit: "" };
}

function splitNumericDisplay(value: NumericLike, fallback = GAP, unitHint?: string): {
  value: string;
  unit?: string;
} {
  const stripped = stripDisplayUnit(numericDisplay(value, fallback, unitHint));
  return {
    value: stripped.value,
    unit: stripped.unit || undefined,
  };
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

function findMetric(
  metrics: readonly HomeSnapshotOverviewMetricVM[],
  ids: readonly string[],
): HomeSnapshotOverviewMetricVM | undefined {
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

function cleanDate(value: string | null | undefined): string {
  return value?.trim() ?? "";
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const a = cleanDate(expected);
  const b = cleanDate(actual);
  return a.length > 0 && b.length > 0 && a === b;
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
  aumMetric: HomeSnapshotOverviewMetricVM | undefined;
  headline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  attribution: HomeSnapshotPnlAttributionVM | null;
}): HomeTerminalKpi[] {
  const totalMarketValue =
    args.headline?.kpis.total_market_value ?? args.portfolio?.total_market_value ?? args.aumMetric?.value;
  const duration =
    args.headline?.kpis.weighted_duration ??
    args.portfolio?.weighted_duration;
  const ytm = args.headline?.kpis.weighted_ytm ?? args.portfolio?.weighted_ytm;
  const creditRatio = args.portfolio?.credit_weight;

  return [
    terminalKpiFromNumeric({
      id: "aum",
      label: "组合市值",
      value: totalMarketValue,
      previous: args.headline?.prev_kpis?.total_market_value,
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
      label: "月度盈亏（本月）",
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
      value: ratioAsPercentNumeric(creditRatio),
      sparkline: flatSparkline(0.95),
      unitHint: "pct",
    }),
  ];
}

function mockFirstScreenView(): DashboardHomeFirstScreenView {
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
    decisionRail: {
      conclusion:
        "组合亏损主要由利率上行导致，信用利差收窄形成部分对冲，组合久期略有上升，需关注集中度风险。",
      maxDragLabel: "利率变动",
      maxDragValue: "-512.34 万",
      maxContributionLabel: "信用利差",
      maxContributionValue: "+286.21 万",
      keyRisk: "Top5 集中度 41.35%，久期小幅上升。",
      suggestions: ["优先复核久期超限账户", "关注 Top5 主体敞口", "跟踪利率曲线陡峭化风险"],
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
        label: "月度盈亏（本月）",
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
  };
}

export function mapToHomeFirstScreenView(
  input: MapToHomeFirstScreenViewInput,
): DashboardHomeFirstScreenView {
  if (input.useMockFallback) {
    return mockFirstScreenView();
  }

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
  const headlineOk = isSameReportDate(reportDate, input.bondHeadline?.report_date);
  const portfolioOk = isSameReportDate(reportDate, input.portfolio?.report_date);
  const headline = headlineOk ? input.bondHeadline : null;
  const portfolio = portfolioOk ? input.portfolio : null;
  const verdict = input.verdict;
  const suggestions =
    verdict?.suggestions?.map((item) => item.text).filter(Boolean).slice(0, 3) ?? [];
  const terminalKpis = buildTerminalKpis({
    aumMetric,
    headline,
    portfolio,
    attribution: input.attribution,
  });
  const keyRiskStrip: HomeRiskTicker[] = DASHBOARD_MARKET_PULSE_MOCK.slice(0, 8).map((item) => ({
    id: item.id,
    label: item.label,
    value: item.value,
    delta: item.delta,
    deltaTone: item.deltaTone === "up" ? "up" : item.deltaTone === "down" ? "down" : "flat",
  }));

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
    decisionRail: {
      conclusion: verdict?.conclusion?.trim() || "数据待同步",
      maxDragLabel: GAP,
      maxDragValue: GAP,
      maxContributionLabel: GAP,
      maxContributionValue: GAP,
      keyRisk: verdict?.reasons?.[0]?.label ?? GAP,
      suggestions: suggestions.length > 0 ? suggestions : ["数据待同步"],
      pendingSummary: `${input.alertCount} 项`,
      reportDate,
      dataUpdatedAt,
      dataSyncPrefix,
    },
    terminalKpis,
    keyRiskStrip,
  };
}
