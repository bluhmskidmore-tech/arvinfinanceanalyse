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
  dashboardHomeSnapshotFailureCopy,
  type DashboardHomeSnapshotFailureCopy,
} from "./dashboardHomeAvailability";
import type {
  DashboardHomeFirstScreenView,
  HomeDecisionAction,
  HomeDecisionSuggestion,
  HomeDataStateKind,
  HomeDeltaTone,
  HomeGovernanceStatusKind,
  HomeMissingDomain,
  HomeProductCategoryHeadline,
  HomeReportDateContext,
  HomeReportDateMode,
  HomeTerminalKpi,
} from "./dashboardHomeFirstScreenTypes";

type NumericLike = Numeric | string | number | null | undefined;

export type MapToHomeFirstScreenViewInput = {
  reportDate: string;
  useMockFallback: boolean;
  requestedReportDate?: string;
  domainsEffectiveDate?: Readonly<Record<string, string>>;
  domainsMissing?: readonly string[];
  productCategoryHeadline?: HomeProductCategoryHeadline;
  snapshotMode?: "strict" | "partial";
  verdict: VerdictPayload | null;
  metrics: readonly HomeSnapshotOverviewMetricVM[];
  attribution: HomeSnapshotPnlAttributionVM | null;
  bondHeadline: BondDashboardHeadlinePayload | null;
  portfolio: BondPortfolioHeadlinesPayload | null;
  snapshotMeta: ResultMeta | null;
  alertCount: number;
  snapshotUnavailable: boolean;
  snapshotErrorDetail?: string | null;
  snapshotStale: boolean;
  snapshotLoading: boolean;
  staleWarning?: string | null;
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

const DOMAIN_LABELS: Readonly<Record<string, string>> = {
  attribution: "损益归因",
  balance_sheet: "资产负债",
  overview: "经营总览",
  pnl: "损益",
  product_category: "产品分类经营",
};

function buildMissingDomains(values: readonly string[] | undefined): HomeMissingDomain[] {
  const seen = new Set<string>();
  const domains: HomeMissingDomain[] = [];
  for (const value of values ?? []) {
    const id = value.trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    domains.push({
      id,
      label: DOMAIN_LABELS[id] ?? id.replace(/[_-]+/g, " "),
    });
  }
  return domains;
}

function missingDomainSummary(domains: readonly HomeMissingDomain[]): string {
  return domains
    .map((domain) => `${domain.label}（${domain.id}）`)
    .join("、");
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

function formatBp(raw: number): string {
  return raw.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatWan(raw: number, signAware = false): string {
  const wan = raw / 10_000;
  const formatted = wan.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${signAware && wan >= 0 ? "+" : ""}${formatted}`;
}

function numericDisplay(value: NumericLike, fallback = GAP, unitHint?: string): string {
  const raw = numericRaw(value);
  const unit = isNumericObject(value) ? value.unit : unitHint;
  const signAware = isNumericObject(value) ? value.sign_aware : false;
  const display = isNumericObject(value) ? value.display?.trim() : undefined;
  if (isNumericObject(value) && raw == null) {
    return fallback;
  }
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


function suggestionId(index: number, title: string): string {
  const titleToken = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `suggestion-${index + 1}-${titleToken || "drilldown"}`;
}

function buildDecisionSuggestions(
  verdict: VerdictPayload | null,
  reportDate: string,
): HomeDecisionSuggestion[] {
  return (verdict?.suggestions ?? [])
    .map((suggestion, index) => {
      const text = suggestion.text.trim();
      const to = reportDatePath(suggestion.link, reportDate);
      return text
        ? { id: suggestionId(index, text), text, ...(to ? { to } : {}) }
        : null;
    })
    .filter((suggestion): suggestion is HomeDecisionSuggestion => suggestion !== null)
    .slice(0, 3);
}

function buildDecisionActions(args: {
  alertCount: number;
  reportDate: string;
  snapshotUnavailable: boolean;
  snapshotFailure: DashboardHomeSnapshotFailureCopy;
}): HomeDecisionAction[] {
  if (args.snapshotUnavailable) {
    return [
      {
        id: "snapshot-unavailable",
        title: args.snapshotFailure.label,
        priority: "high",
        sourceLabel: "首页主快照",
        reason: args.snapshotFailure.recovery,
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
    state: numericRaw(args.value) != null ? args.state ?? "ready" : "empty",
  };
}

function terminalKpiFromSnapshotMetric(metric: HomeSnapshotOverviewMetricVM): HomeTerminalKpi {
  const valueRaw = numericRaw(metric.value);
  const split = splitNumericDisplay(metric.value);
  const delta = valueRaw == null ? GAP : numericDisplay(metric.delta);
  const deltaRaw = numericRaw(metric.delta);
  // 变动方向色跟数值符号（绿涨红跌），后端 tone 只保留 warning 语义与无法判向时的回退。
  const deltaTone: HomeDeltaTone =
    valueRaw == null
      ? "muted"
      : metric.tone === "warning"
        ? "warn"
        : deltaRaw != null
          ? deltaRaw > 0
            ? "up"
            : deltaRaw < 0
              ? "down"
              : "flat"
          : metricToneToDelta(metric.tone);
  return {
    id: metric.id,
    label: metric.label,
    value: split.value,
    unit: split.unit,
    delta: delta === GAP ? GAP : `变动 ${delta}`,
    deltaTone,
    // 无真实历史时不再用常数序列兜底：宁可不画线，不用假走势冒充数据。
    sparkline: buildSparklineFromHistory(metric.history, []),
    state: valueRaw != null ? "ready" : "empty",
  };
}

function rawState(value: NumericLike): HomeDataStateKind {
  return numericRaw(value) == null ? "empty" : "ready";
}

function numericBpParts(value: NumericLike): { value: string; unit?: string } {
  const raw = numericRaw(value);
  if (raw == null) {
    return { value: GAP };
  }
  return { value: formatBp(raw), unit: "bp" };
}

function numericWanParts(value: NumericLike): { value: string; unit?: string } {
  const raw = numericRaw(value);
  if (raw == null) {
    return { value: GAP };
  }
  return { value: formatWan(raw), unit: "万" };
}

// Raw dv01 values carry yuan-level magnitude even when the source Numeric's own
// `unit`/`display` claim "dv01" (see numericDisplay's "dv01" branch), so any
// single-string display (no separate unit field, e.g. keyRiskStrip) must apply
// the same 万 conversion as numericWanParts/dv01-wan instead of trusting `display`.
function dv01WanValueOrGap(value: NumericLike): string {
  const parts = numericWanParts(value);
  return parts.value === GAP ? GAP : `${parts.value} 万`;
}

function rawDeltaDisplay(
  current: NumericLike,
  previous: NumericLike,
  options: { suffix: string; scale?: number; digits?: number },
): { delta: string; tone: HomeDeltaTone } {
  const currentRaw = numericRaw(current);
  const previousRaw = numericRaw(previous);
  if (currentRaw == null || previousRaw == null) {
    return { delta: GAP, tone: "muted" };
  }
  const scale = options.scale ?? 1;
  const digits = options.digits ?? 2;
  const delta = (currentRaw - previousRaw) / scale;
  if (Math.abs(delta) < 1e-9) {
    return { delta: "变动 持平", tone: "flat" };
  }
  const sign = delta > 0 ? "+" : "";
  return {
    delta: `变动 ${sign}${delta.toFixed(digits)}${options.suffix}`,
    tone: delta > 0 ? "up" : "down",
  };
}

function terminalKpiFromParts(args: {
  id: string;
  label: string;
  value: string;
  unit?: string;
  delta: string;
  deltaTone: HomeDeltaTone;
  sparkline?: readonly number[];
  state: HomeDataStateKind;
}): HomeTerminalKpi {
  return {
    id: args.id,
    label: args.label,
    value: args.value,
    unit: args.unit,
    delta: args.delta,
    deltaTone: args.deltaTone,
    sparkline: args.sparkline ?? [],
    state: args.state,
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
  const totalMarketValue = args.aumMetric?.value;
  const spreadBp = args.headline?.kpis.credit_spread_median;
  const prevSpreadBp = args.headline?.prev_kpis?.credit_spread_median;
  const totalDv01 =
    args.headline?.kpis.total_dv01 ??
    args.dv01Metric?.value ??
    args.portfolio?.total_dv01;
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
      sparkline: buildSparklineFromHistory(aumHistory, []),
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
        sparkline: [],
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
        sparkline: [],
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
        sparkline: [],
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
        sparkline: [],
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
        sparkline: [],
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
        sparkline: [],
        unitHint: "pct",
      }),
    );
  }

  const spreadParts = numericBpParts(spreadBp);
  const spreadDelta = rawDeltaDisplay(spreadBp, prevSpreadBp, {
    suffix: "bp",
  });
  kpis.push(
    terminalKpiFromParts({
      id: "spread-bp",
      label: "息差",
      value: spreadParts.value,
      unit: spreadParts.unit,
      delta: spreadDelta.delta,
      deltaTone: spreadDelta.tone,
      state: rawState(spreadBp),
    }),
  );

  const dv01WanParts = numericWanParts(totalDv01);
  const dv01WanDelta = rawDeltaDisplay(totalDv01, args.headline?.prev_kpis?.total_dv01, {
    suffix: "万",
    scale: 10_000,
  });
  kpis.push(
    terminalKpiFromParts({
      id: "dv01-wan",
      label: "DV01",
      value: dv01WanParts.value,
      unit: dv01WanParts.value === GAP ? undefined : "万元/bp",
      delta: dv01WanDelta.delta,
      deltaTone: dv01WanDelta.tone,
      sparkline:
        args.dv01Metric?.history?.length && args.dv01Metric.history.length > 1
          ? args.dv01Metric.history.map((point) => point / 10_000)
          : [],
      state: rawState(totalDv01),
    }),
  );

  kpis.push(
    terminalKpiFromParts({
      id: "holding-occupancy",
      label: "持仓占用",
      value: GAP,
      delta: GAP,
      deltaTone: "muted",
      state: "empty",
    }),
  );

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
    {
      id: "risk-dv01",
      label: "利率敏感度",
      value: dv01WanValueOrGap(totalDv01),
      delta: "当前值",
      deltaTone: "flat" as const,
    },
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

/**
 * 从快照归因段取最大拖累（最负）与最大贡献（最正）：
 * 只做展示层选择，不做任何再计算；无归因数据时全部回 GAP。
 */
function attributionExtremes(attribution: HomeSnapshotPnlAttributionVM | null): {
  maxDragLabel: string;
  maxDragValue: string;
  maxContributionLabel: string;
  maxContributionValue: string;
  hasDrag: boolean;
  hasContribution: boolean;
} {
  let drag: { label: string; raw: number; display: string } | null = null;
  let contribution: { label: string; raw: number; display: string } | null = null;
  for (const segment of attribution?.segments ?? []) {
    const raw = numericRaw(segment.amount);
    if (raw == null || !Number.isFinite(raw)) continue;
    const display = numericDisplay(segment.amount, GAP, "yuan");
    if (display === GAP) continue;
    if (raw < 0 && (!drag || raw < drag.raw)) {
      drag = { label: segment.label, raw, display };
    }
    if (raw > 0 && (!contribution || raw > contribution.raw)) {
      contribution = { label: segment.label, raw, display };
    }
  }
  return {
    maxDragLabel: drag?.label ?? GAP,
    maxDragValue: drag?.display ?? GAP,
    maxContributionLabel: contribution?.label ?? GAP,
    maxContributionValue: contribution?.display ?? GAP,
    hasDrag: drag != null,
    hasContribution: contribution != null,
  };
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

const DOMAIN_EFFECTIVE_DATE_LABELS: Readonly<Record<string, string>> = {
  balance_sheet: "资产负债",
  pnl: "损益",
};

function formatSnapshotGeneratedAt(generatedAt: string | null | undefined): string {
  const trimmed = generatedAt?.trim();
  if (!trimmed) {
    return "";
  }
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(trimmed);
  return match ? `${match[1]} ${match[2]}` : trimmed;
}

function formatDomainEffectiveDates(
  domainsEffectiveDate: Readonly<Record<string, string>> | undefined,
): string {
  return Object.entries(domainsEffectiveDate ?? {})
    .map(([domain, date]) => {
      const trimmedDate = typeof date === "string" ? date.trim() : "";
      if (!trimmedDate) {
        return null;
      }
      const label = DOMAIN_EFFECTIVE_DATE_LABELS[domain] ?? domain;
      return `${label} ${trimmedDate}`;
    })
    .filter((item): item is string => Boolean(item))
    .join(" · ");
}

/**
 * 构建首页报告日期上下文。实际数据日只认 snapshot.result.report_date；
 * 分域有效日期与快照生成时间分别保留，不再用 result_meta 日期互相回填。
 */
function buildReportDateContext(args: {
  reportDate: string;
  useMockFallback: boolean;
  requestedReportDate?: string;
  domainsEffectiveDate?: Readonly<Record<string, string>>;
  snapshotMeta: ResultMeta | null;
  snapshotUnavailable: boolean;
  snapshotErrorDetail?: string | null;
  snapshotStale: boolean;
  snapshotLoading: boolean;
  staleWarning?: string | null;
}): HomeReportDateContext {
  const meta = args.snapshotMeta;
  const requestedDate =
    args.requestedReportDate !== undefined
      ? args.requestedReportDate.trim()
      : typeof meta?.requested_report_date === "string"
        ? meta.requested_report_date.trim()
        : "";
  const actualDataDate = args.reportDate.trim();
  const hasRequestedDateDivergence =
    requestedDate.length > 0 &&
    actualDataDate.length > 0 &&
    requestedDate !== actualDataDate;
  const dataAsOfDate = formatDomainEffectiveDates(args.domainsEffectiveDate);
  const generatedAt = formatSnapshotGeneratedAt(meta?.generated_at);

  let mode: HomeReportDateMode;
  let divergenceReason: string | null = null;

  if (args.useMockFallback) {
    mode = "mock";
    divergenceReason = "样例数据日";
  } else if (args.snapshotUnavailable) {
    mode = "error";
    divergenceReason = dashboardHomeSnapshotFailureCopy(
      args.snapshotErrorDetail,
    ).reason;
  } else if (args.snapshotLoading) {
    mode = "loading";
    divergenceReason = "主快照读取中";
  } else if (args.snapshotStale) {
    mode = "stale";
    divergenceReason = hasRequestedDateDivergence
      ? args.staleWarning ?? "新报告日数据获取失败，当前展示上一版本数据"
      : "主快照刷新失败，当前展示上一版本数据";
  } else if (actualDataDate.length === 0) {
    mode = "empty";
    divergenceReason = "暂无可用数据日";
  } else if (
    meta?.fallback_mode === "latest_snapshot" ||
    hasRequestedDateDivergence
  ) {
    mode = "fallback";
    divergenceReason =
      meta?.fallback_mode === "latest_snapshot"
        ? "回退至最近可用快照"
        : "请求日无数据，已回退至最近可用快照";
  } else {
    mode = "exact";
    divergenceReason = null;
  }

  return {
    requestedDate,
    actualDataDate,
    divergenceReason,
    dataAsOfDate,
    generatedAt,
    mode,
  };
}

type GovernanceReview = {
  kind: Exclude<HomeGovernanceStatusKind, "ok" | "loading" | "error">;
  reason: string;
};

function productCategoryGovernanceReview(
  headline: HomeProductCategoryHeadline | undefined,
): GovernanceReview | null {
  if (!headline || headline.state === "ready") return null;
  if (headline.state === "stale") {
    return { kind: "stale", reason: "产品分类经营摘要偏旧，需复核" };
  }
  if (headline.state === "empty") {
    return { kind: "partial", reason: "产品分类经营摘要未下发，需复核" };
  }
  if (headline.state === "partial") {
    return { kind: "partial", reason: "产品分类经营摘要不完整，需复核" };
  }
  if (headline.state === "error") {
    return { kind: "partial", reason: "产品分类经营摘要读取异常，需复核" };
  }
  return { kind: "partial", reason: "产品分类经营摘要读取中，需复核" };
}

function governanceReviewReason(
  input: MapToHomeFirstScreenViewInput,
  missingDomains: readonly HomeMissingDomain[],
  productCategoryHeadline: HomeProductCategoryHeadline,
): GovernanceReview | null {
  const actualDataDate = cleanDate(input.reportDate);
  if (!actualDataDate) {
    return { kind: "partial", reason: "暂无可用快照，需复核" };
  }
  if (input.snapshotMeta && input.snapshotMeta.fallback_mode !== "none") {
    return { kind: "fallback", reason: "快照使用回退链路，需复核" };
  }
  const requestedDate =
    input.requestedReportDate?.trim() ||
    input.snapshotMeta?.requested_report_date?.trim() ||
    "";
  if (requestedDate && requestedDate !== actualDataDate) {
    return { kind: "fallback", reason: "请求日与实际快照日不一致，需复核" };
  }
  if (
    input.snapshotMeta?.vendor_status === "vendor_stale" ||
    input.snapshotMeta?.quality_flag === "stale"
  ) {
    return { kind: "stale", reason: "快照或外部数据源偏旧，需复核" };
  }
  if (missingDomains.length > 0) {
    return {
      kind: "partial",
      reason: `部分数据域缺失：${missingDomainSummary(missingDomains)}，需复核`,
    };
  }
  const productReview = productCategoryGovernanceReview(productCategoryHeadline);
  if (productReview) {
    return productReview;
  }
  if (input.snapshotMeta && input.snapshotMeta.vendor_status !== "ok") {
    return { kind: "partial", reason: "外部数据源不可用，需复核" };
  }
  if (input.snapshotMeta && input.snapshotMeta.quality_flag !== "ok") {
    return { kind: "partial", reason: "快照质量状态异常，需复核" };
  }
  return null;
}

export function mapToHomeFirstScreenView(
  input: MapToHomeFirstScreenViewInput,
): DashboardHomeFirstScreenView {
  const reportDate = cleanDate(input.reportDate) || GAP;
  const snapshotFailure = dashboardHomeSnapshotFailureCopy(
    input.snapshotErrorDetail,
  );
  const missingDomains = buildMissingDomains(input.domainsMissing);
  const productCategoryHeadline = input.productCategoryHeadline ?? {
    state: "empty",
    metrics: [],
  };
  const governanceReview =
    input.snapshotUnavailable || input.snapshotLoading || input.snapshotStale
      ? null
      : governanceReviewReason(input, missingDomains, productCategoryHeadline);
  const dataStatusKind =
    input.snapshotUnavailable
      ? "error"
      : input.snapshotLoading
        ? "loading"
        : input.snapshotStale
          ? "stale"
          : governanceReview?.kind ?? "ok";
  const dataSyncPrefix = input.snapshotUnavailable
    ? snapshotFailure.label
    : input.snapshotLoading
      ? "主快照读取中"
      : input.snapshotStale
        ? "展示上一版本"
        : governanceReview?.reason ??
          (input.snapshotMeta?.formal_use_allowed === false
            ? "分析快照已更新"
            : input.snapshotMeta?.formal_use_allowed === true
              ? "正式数据已更新"
              : "数据已更新");
  const generatedTime = input.snapshotMeta?.generated_at?.slice(11, 16)?.trim();
  const dataUpdatedAt = input.snapshotUnavailable || input.snapshotLoading
    ? GAP
    : generatedTime || GAP;
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
  const suggestions = buildDecisionSuggestions(verdict, reportDate);
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
  const reportDateContext = buildReportDateContext({
    reportDate: cleanDate(input.reportDate),
    useMockFallback: input.useMockFallback,
    requestedReportDate: input.requestedReportDate,
    domainsEffectiveDate: input.domainsEffectiveDate,
    snapshotMeta: input.snapshotMeta,
    snapshotUnavailable: input.snapshotUnavailable,
    snapshotErrorDetail: input.snapshotErrorDetail,
    snapshotStale: input.snapshotStale,
    snapshotLoading: input.snapshotLoading,
    staleWarning: input.staleWarning,
  });
  const decisionActions = buildDecisionActions({
    alertCount: input.alertCount,
    reportDate,
    snapshotUnavailable: input.snapshotUnavailable,
    snapshotFailure,
  });
  const actionableCount = decisionActions.filter(
    (action) => action.statusKind === "ready" && Boolean(action.to),
  ).length;
  const decisionSuggestions = input.snapshotUnavailable
    ? [{ id: "snapshot-unavailable-suggestion", text: snapshotFailure.recovery }]
    : suggestions;

  return {
    reportDate,
    useMockFallback: false,
    reportDateContext,
    headerStatus: {
      dataStatusKind,
      snapshotFailureKind: input.snapshotUnavailable
        ? snapshotFailure.kind
        : null,
      formalUseAllowed: input.snapshotMeta?.formal_use_allowed ?? null,
      // 首页尚无治理待办 feed；硬编码 0 不能被解释成“真实无待办”。
      governanceFeedAvailable: false,
      dataUpdatedAt,
      marketStatus: input.snapshotUnavailable
        ? snapshotFailure.kind === "permission"
          ? "权限不足"
          : "读取失败"
        : input.snapshotLoading
          ? "等待数据"
          : input.snapshotStale
            ? "新报告日失败"
            : governanceReview
              ? "来源需复核"
              : "市场已收盘",
      valuationLabel: input.snapshotUnavailable
        ? "无可用快照"
        : input.snapshotLoading
          ? "读取中"
          : input.snapshotStale
            ? "沿用旧快照"
            : governanceReview
              ? "估值待复核"
              : "估值已完成",
      valuationTone:
        input.snapshotUnavailable || input.snapshotLoading || input.snapshotStale || governanceReview
          ? "warn"
          : "ok",
      riskReviewCount: input.alertCount,
      showRiskReview: input.alertCount > 0,
      dataSyncPrefix,
    },
    decisionRail: {
      conclusion: input.snapshotUnavailable ? snapshotFailure.label : buildDecisionSummary(verdict, terminalKpis),
      ...attributionExtremes(input.snapshotUnavailable ? null : input.attribution),
      keyRisk: input.snapshotUnavailable
        ? `未执行：风险核验依赖主快照，${snapshotFailure.reason}`
        : formatVerdictReason(verdict?.reasons?.[0]),
      suggestions: decisionSuggestions,
      actions: decisionActions,
      pendingSummary: actionableCount > 0 ? `${actionableCount} 项` : "暂无",
      reportDate,
      dataUpdatedAt,
      dataSyncPrefix,
    },
    missingDomains,
    productCategoryHeadline,
    terminalKpis,
    keyRiskStrip,
  };
}
