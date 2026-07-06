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
import type {
  DashboardHomeFirstScreenView,
  HomeDecisionAction,
  HomeDataStateKind,
  HomeDeltaTone,
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
  snapshotLoading: boolean;
};

const GAP = "—";

const DECISION_ACTION_ROUTES = new Set([
  "/bond-analysis",
  "/cashflow-projection",
  "/concentration-monitor",
  "/cross-asset",
  "/decision-items",
  "/pnl-attribution",
  "/risk-overview",
  "/risk-tensor",
]);

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

/**
 * 水平值（如组合YTM）不是涨跌变化，展示层不带正号；
 * 后端 Numeric 因 sign_aware=true 会在 display 里带 "+"，这里剥掉。
 */
function levelDisplayNumeric(value: NumericLike): NumericLike {
  if (!isNumericObject(value)) {
    return value;
  }
  return {
    ...value,
    sign_aware: false,
    display: value.display?.replace(/^\+/, ""),
  };
}

/**
 * 首屏"规模"语义同时存在 zqtz 资产口径（snapshot overview aum）与
 * 债券持仓市值口径（bond-dashboard headline），标签必须带口径说明。
 */
function metricWithCaliberLabel(
  metric: HomeSnapshotOverviewMetricVM,
): HomeSnapshotOverviewMetricVM {
  if (!metric.caliberLabel || metric.label.includes(metric.caliberLabel)) {
    return metric;
  }
  return { ...metric, label: `${metric.label}（${metric.caliberLabel}）` };
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

function metricToneToDelta(tone: HomeSnapshotOverviewMetricVM["tone"]): HomeDeltaTone {
  if (tone === "positive") return "up";
  if (tone === "negative") return "down";
  if (tone === "warning") return "warn";
  return "flat";
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

function isConcreteReportDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(cleanDate(value));
}

function reportDatePath(path: string | null | undefined, reportDate: string): string | undefined {
  const trimmed = path?.trim();
  if (!trimmed || !trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return undefined;
  }

  try {
    const url = new URL(trimmed, "http://moss.local");
    if (!DECISION_ACTION_ROUTES.has(url.pathname)) {
      return undefined;
    }
    if (isConcreteReportDate(reportDate)) {
      url.searchParams.set("report_date", reportDate);
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return undefined;
  }
}

function decisionItemPath(actionId: string, reportDate: string): string | undefined {
  if (!isConcreteReportDate(reportDate)) {
    return undefined;
  }
  const params = new URLSearchParams({
    source: "dashboard-home",
    report_date: reportDate,
    action_id: actionId,
  });
  return reportDatePath(`/decision-items?${params.toString()}`, reportDate);
}

function sourceLabelForPath(path: string): string {
  const pathname = path.split(/[?#]/, 1)[0] ?? "";
  if (pathname === "/bond-analysis") return "债券分析";
  if (pathname === "/decision-items") return "待办";
  if (pathname === "/risk-tensor") return "风险张量";
  if (pathname === "/risk-overview") return "风险";
  if (pathname === "/pnl-attribution") return "归因";
  if (pathname === "/cross-asset") return "跨资产";

  const firstSegment = pathname.split("/").filter(Boolean)[0];
  return firstSegment || "home";
}

function actionIdForSuggestion(index: number, to: string, title: string): string {
  const source = sourceLabelForPath(to);
  const titleToken = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `suggestion-${index + 1}-${titleToken || source}`;
}

function buildDecisionActions(args: {
  verdict: VerdictPayload | null;
  alertCount: number;
  reportDate: string;
  snapshotUnavailable: boolean;
}): HomeDecisionAction[] {
  if (args.snapshotUnavailable) {
    return [
      {
        id: "snapshot-unavailable",
        title: "首页数据服务不可达",
        priority: "high",
        sourceLabel: "数据服务",
        reason: "恢复首页数据服务后刷新日报",
        to: undefined,
        statusKind: "backend-gap",
      },
    ];
  }

  const actions: HomeDecisionAction[] = [];
  if (args.alertCount > 0) {
    const to = decisionItemPath("risk-review-queue", args.reportDate);
    actions.push({
      id: "risk-review-queue",
      title: "处理风险复核队列",
      priority: "high",
      sourceLabel: "待办",
      reason: `${args.alertCount} 项风险事项需要复核`,
      to,
      statusKind: to ? "ready" : "stale",
    });
  }

  args.verdict?.suggestions?.forEach((suggestion, index) => {
    const title = suggestion.text.trim();
    const to = reportDatePath(suggestion.link, args.reportDate);
    if (!title || !to) {
      return;
    }
    actions.push({
      id: actionIdForSuggestion(index, to, title),
      title,
      priority: args.alertCount > 0 ? "medium" : "high",
      sourceLabel: sourceLabelForPath(to),
      reason: "进入对应页面核对明细",
      to,
      statusKind: "ready",
    });
  });

  if (actions.length > 0) {
    return actions.slice(0, 4);
  }

  return [
    {
      id: "no-action",
      title: "暂无复核入口",
      priority: "low",
      sourceLabel: "首页",
      reason: "当前无待办或复核入口",
      to: undefined,
      statusKind: "empty",
    },
  ];
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

function terminalKpiFromSnapshotMetric(metric: HomeSnapshotOverviewMetricVM): HomeTerminalKpi {
  const split = splitNumericDisplay(metric.value);
  const delta = numericDisplay(metric.delta);
  return {
    id: metric.id,
    label: metric.label,
    value: split.value,
    unit: split.unit,
    delta: delta === GAP ? GAP : `较前日 ${delta}`,
    deltaTone: metricToneToDelta(metric.tone),
    sparkline: buildSparklineFromHistory(metric.history, flatSparkline(numericRaw(metric.value) ?? 1)),
    state: "ready",
  };
}

function buildTerminalKpis(args: {
  aumMetric: HomeSnapshotOverviewMetricVM | undefined;
  yieldMetric: HomeSnapshotOverviewMetricVM | undefined;
  nimMetric: HomeSnapshotOverviewMetricVM | undefined;
  dv01Metric: HomeSnapshotOverviewMetricVM | undefined;
  durationMetric: HomeSnapshotOverviewMetricVM | undefined;
  headline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  attribution: HomeSnapshotPnlAttributionVM | null;
}): HomeTerminalKpi[] {
  const totalMarketValue =
    args.headline?.kpis.total_market_value ?? args.portfolio?.total_market_value ?? args.aumMetric?.value;
  const duration =
    args.durationMetric?.value ??
    args.headline?.kpis.weighted_duration ??
    args.portfolio?.weighted_duration;
  const ytm = args.headline?.kpis.weighted_ytm ?? args.portfolio?.weighted_ytm;
  const creditRatio = args.portfolio?.credit_weight;
  const aumHistory = args.aumMetric?.history ?? null;

  const kpis: HomeTerminalKpi[] = [
    args.aumMetric
      ? terminalKpiFromSnapshotMetric(metricWithCaliberLabel(args.aumMetric))
      : terminalKpiFromNumeric({
      id: "aum",
      label: "组合市值",
      value: totalMarketValue,
      previous: args.headline?.prev_kpis?.total_market_value,
      sparkline: buildSparklineFromHistory(aumHistory, flatSparkline(1)),
      unitHint: "yuan",
    }),
  ];

  if (args.yieldMetric) {
    kpis.push(terminalKpiFromSnapshotMetric(args.yieldMetric));
  }
  if (args.nimMetric) {
    kpis.push(terminalKpiFromSnapshotMetric(args.nimMetric));
  }
  if (args.dv01Metric) {
    kpis.push(terminalKpiFromSnapshotMetric(args.dv01Metric));
  }
  if (args.durationMetric) {
    kpis.push(terminalKpiFromSnapshotMetric(args.durationMetric));
  }

  if (args.attribution?.total) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "day-pnl",
        label: "月度盈亏（本月）",
        value: args.attribution.total,
        sparkline: flatSparkline(0.9),
        unitHint: "yuan",
      }),
    );
  }

  if (args.headline?.kpis.total_market_value) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "bond-market-value",
        label: "债券市值（持仓口径）",
        value: args.headline.kpis.total_market_value,
        previous: args.headline.prev_kpis?.total_market_value,
        sparkline: flatSparkline(1.2),
        unitHint: "yuan",
      }),
    );
  }

  if (args.headline?.kpis.unrealized_pnl) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "unrealized-pnl",
        label: "未实现损益（存量）",
        value: args.headline.kpis.unrealized_pnl,
        previous: args.headline.prev_kpis?.unrealized_pnl,
        sparkline: flatSparkline(0.8),
        unitHint: "yuan",
      }),
    );
  }

  if (duration && !args.durationMetric) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "duration",
        label: "加权久期",
        value: duration,
        previous: args.headline?.prev_kpis?.weighted_duration,
        sparkline: flatSparkline(1.05),
        unitHint: "ratio",
      }),
    );
  }

  if (ytm) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "ytm",
        label: "组合YTM",
        value: levelDisplayNumeric(ytm),
        previous: args.headline?.prev_kpis?.weighted_ytm,
        sparkline: flatSparkline(1.1),
        unitHint: "pct",
      }),
    );
  }

  if (creditRatio) {
    kpis.push(
      terminalKpiFromNumeric({
        id: "credit-ratio",
        label: "信用占比",
        value: ratioAsPercentNumeric(creditRatio),
        sparkline: flatSparkline(0.95),
        unitHint: "pct",
      }),
    );
  }

  return kpis;
}

function riskTickerFromNumeric(args: {
  id: string;
  label: string;
  value: NumericLike;
  unitHint?: string;
}): DashboardHomeFirstScreenView["keyRiskStrip"][number] {
  return {
    id: args.id,
    label: args.label,
    value: numericDisplay(args.value, GAP, args.unitHint),
    delta: "当前值",
    deltaTone: "flat",
  };
}

function buildKeyRiskStrip(args: {
  headline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
}): DashboardHomeFirstScreenView["keyRiskStrip"] {
  const totalDv01 = args.headline?.kpis.total_dv01 ?? args.portfolio?.total_dv01;
  const duration = args.headline?.kpis.weighted_duration ?? args.portfolio?.weighted_duration;
  const creditRatio = args.portfolio?.credit_weight;
  const issuerTop5Weight = args.portfolio?.issuer_top5_weight;

  return [
    riskTickerFromNumeric({
      id: "risk-dv01",
      label: "利率敏感度",
      value: totalDv01,
      unitHint: "dv01",
    }),
    riskTickerFromNumeric({
      id: "risk-duration",
      label: "久期",
      value: duration,
      unitHint: "ratio",
    }),
    riskTickerFromNumeric({
      id: "risk-credit",
      label: "信用占比",
      value: ratioAsPercentNumeric(creditRatio),
      unitHint: "pct",
    }),
    riskTickerFromNumeric({
      id: "risk-top5",
      label: "Top5集中度",
      value: ratioAsPercentNumeric(issuerTop5Weight),
      unitHint: "pct",
    }),
  ].filter((item) => item.value !== GAP);
}

function hasDisplayText(value: string | null | undefined): boolean {
  const trimmed = value?.trim();
  return Boolean(trimmed && trimmed !== GAP && trimmed !== "--");
}

function isGenericVerdictConclusion(conclusion: string): boolean {
  return /首屏整体|方向性判断|偏多|偏空/.test(conclusion);
}

function kpiSummarySegment(kpi: HomeTerminalKpi): string {
  return `${kpi.label} ${kpi.value}${kpi.unit ?? ""}`;
}

function buildKpiSummary(terminalKpis: readonly HomeTerminalKpi[]): string | null {
  const availableKpis = terminalKpis.filter((kpi) => hasDisplayText(kpi.value));
  if (availableKpis.length === 0) {
    return null;
  }
  return availableKpis.slice(0, 2).map(kpiSummarySegment).join("，");
}

function buildDecisionSummary(verdict: VerdictPayload | null, terminalKpis: readonly HomeTerminalKpi[]): string {
  const conclusion = verdict?.conclusion?.trim();
  const kpiSummary = buildKpiSummary(terminalKpis);
  if (!conclusion) {
    return kpiSummary
      ? `${kpiSummary}。`
      : "当前报告日暂无经营读数";
  }
  if (isGenericVerdictConclusion(conclusion)) {
    return kpiSummary
      ? `${kpiSummary}；趋势判断待复核。`
      : "首屏读数已形成，趋势判断待复核。";
  }
  return conclusion;
}

function formatVerdictReason(reason: VerdictPayload["reasons"][number] | undefined): string {
  if (!reason) {
    return GAP;
  }
  const value = reason.value?.trim();
  const detail = reason.detail?.trim();
  const segments = [reason.label.trim(), hasDisplayText(value) ? value : null, hasDisplayText(detail) ? detail : null]
    .filter((item): item is string => Boolean(item));
  return segments.length > 0 ? segments.join(" · ") : GAP;
}

export function mapToHomeFirstScreenView(
  input: MapToHomeFirstScreenViewInput,
): DashboardHomeFirstScreenView {
  const reportDate = cleanDate(input.reportDate) || GAP;
  const dataStatusKind =
    input.snapshotUnavailable ? "error" : input.snapshotLoading ? "loading" : input.snapshotStale ? "stale" : "ok";
  const dataSyncPrefix = input.snapshotUnavailable
    ? "首页数据服务不可达"
    : input.snapshotLoading
      ? "主快照读取中"
    : input.snapshotStale
      ? "展示上一版本"
      : "数据已更新";
  const dataUpdatedAt =
    input.snapshotUnavailable || input.snapshotLoading || input.snapshotStale
      ? reportDate
      : input.snapshotMeta?.generated_at?.slice(11, 16) ?? GAP;
  const aumMetric = findMetric(input.metrics, ["aum"]);
  const yieldMetric = findMetric(input.metrics, ["yield"]);
  const nimMetric = findMetric(input.metrics, ["nim"]);
  const dv01Metric = findMetric(input.metrics, ["dv01"]);
  const durationMetric = findMetric(input.metrics, [
    "duration",
    "weighted_duration",
    "portfolio_modified_duration",
  ]);
  const headlineOk = isSameReportDate(reportDate, input.bondHeadline?.report_date);
  const portfolioOk = isSameReportDate(reportDate, input.portfolio?.report_date);
  const headline = headlineOk ? input.bondHeadline : null;
  const portfolio = portfolioOk ? input.portfolio : null;
  const verdict = input.verdict;
  const suggestions =
    verdict?.suggestions?.map((item) => item.text).filter(Boolean).slice(0, 3) ?? [];
  const terminalKpis = buildTerminalKpis({
    aumMetric,
    yieldMetric,
    nimMetric,
    dv01Metric,
    durationMetric,
    headline,
    portfolio,
    attribution: input.attribution,
  });
  const keyRiskStrip = buildKeyRiskStrip({ headline, portfolio });

  return {
    reportDate,
    useMockFallback: false,
    headerStatus: {
      dataStatusKind,
      dataUpdatedAt,
      marketStatus: input.snapshotUnavailable
        ? "服务未连接"
        : input.snapshotLoading
          ? "等待数据"
        : input.snapshotStale
          ? "新报告日失败"
          : "市场已收盘",
      valuationLabel: input.snapshotUnavailable
        ? "无可用快照"
        : input.snapshotLoading
          ? "读取中"
        : input.snapshotStale
          ? "沿用旧快照"
          : "估值已完成",
      valuationTone: input.snapshotUnavailable || input.snapshotLoading || input.snapshotStale ? "warn" : "ok",
      riskReviewCount: input.alertCount,
      showRiskReview: input.alertCount > 0,
      dataSyncPrefix,
    },
    decisionRail: {
      conclusion: input.snapshotUnavailable ? "首页数据服务不可达" : buildDecisionSummary(verdict, terminalKpis),
      maxDragLabel: GAP,
      maxDragValue: GAP,
      maxContributionLabel: GAP,
      maxContributionValue: GAP,
      keyRisk: input.snapshotUnavailable
        ? "未执行：风险核验依赖主快照，当前服务不可达"
        : formatVerdictReason(verdict?.reasons?.[0]),
      suggestions: input.snapshotUnavailable
        ? ["恢复首页数据服务后刷新日报"]
        : suggestions.length > 0
          ? suggestions
          : ["数据待同步"],
      actions: buildDecisionActions({
        verdict,
        alertCount: input.alertCount,
        reportDate,
        snapshotUnavailable: input.snapshotUnavailable,
      }),
      pendingSummary: `${input.alertCount} 项`,
      reportDate,
      dataUpdatedAt,
      dataSyncPrefix,
    },
    terminalKpis,
    keyRiskStrip,
  };
}
