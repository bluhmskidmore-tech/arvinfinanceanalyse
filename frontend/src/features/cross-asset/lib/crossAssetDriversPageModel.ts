import type {
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  MacroBondLinkageEnvironmentScore,
  MacroBondLinkageTopCorrelation,
  MacroBondResearchView,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  MacroBondTransmissionAxis,
  ResultMeta,
} from "../../../api/contracts";
import type { CalendarItem } from "../../../components/CalendarList";
import { mapResearchCalendarEventToCalendarItem } from "../../../lib/researchCalendarToCalendarItem";
import type { ResolvedCrossAssetKpi } from "./crossAssetKpiModel";

type StatusTone = "normal" | "caution" | "warning" | "danger";
type ActionTone = "bull" | "warning" | "bear";
type WatchSignal = "green" | "yellow" | "red";
type ResearchCardSource = "backend" | "fallback";

const RESEARCH_VIEW_ORDER = ["duration", "curve", "credit", "instrument"] as const;
const TRANSMISSION_AXIS_ORDER = [
  "global_rates",
  "liquidity",
  "equity_bond_spread",
  "commodities_inflation",
  "mega_cap_equities",
] as const;

const RESEARCH_VIEW_LABEL: Record<(typeof RESEARCH_VIEW_ORDER)[number], string> = {
  duration: "久期判断",
  curve: "曲线判断",
  credit: "信用判断",
  instrument: "品种判断",
};

const TRANSMISSION_AXIS_LABEL: Record<(typeof TRANSMISSION_AXIS_ORDER)[number], string> = {
  global_rates: "Global rates",
  liquidity: "Liquidity",
  equity_bond_spread: "Equity-bond spread",
  commodities_inflation: "Commodities and inflation",
  mega_cap_equities: "Mega-cap equities",
};

export type CrossAssetStatusFlag = {
  id: string;
  label: string;
  tone: StatusTone;
  detail: string;
};

export type CrossAssetResearchViewCard = {
  key: string;
  label: string;
  stance: string;
  confidence: string;
  summary: string;
  status: "ready" | "pending_signal";
  affectedTargets: string[];
  evidence: string[];
  source: ResearchCardSource;
};

export type CrossAssetTransmissionAxisRow = {
  axisKey: string;
  label: string;
  status: "ready" | "pending_signal";
  stance: string;
  summary: string;
  impactedViews: string[];
  requiredSeriesIds: string[];
  warnings: string[];
  source: ResearchCardSource;
};

export type CrossAssetCandidateAction = {
  tone: ActionTone;
  action: string;
  reason: string;
  evidence: string;
};

export type CrossAssetWatchRow = {
  name: string;
  current: string;
  note: string;
  signal: WatchSignal;
  signalText: string;
};

export type CrossAssetNcdProxyEvidence = {
  asOfDate: string | null;
  proxyLabel: string;
  isActualNcdMatrix: boolean;
  /** 人类可读警告：非真实 NCD 发行矩阵时必须展示 */
  proxyWarning: string;
  rowCaptions: string[];
  sourceMeta: "backend" | "unavailable";
};

/** UI-free aggregate for the cross-asset drivers workbench (single build entry point). */
export type CrossAssetDriversViewModel = {
  researchCards: CrossAssetResearchViewCard[];
  transmissionAxes: CrossAssetTransmissionAxisRow[];
  candidateActions: CrossAssetCandidateAction[];
  watchList: CrossAssetWatchRow[];
  eventCalendarRows: CalendarItem[];
  ncdProxyEvidence: CrossAssetNcdProxyEvidence;
  statusFlags: CrossAssetStatusFlag[];
};

function hasStaleMeta(meta: ResultMeta | undefined) {
  if (!meta) {
    return false;
  }
  return meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale";
}

function hasFallbackMeta(meta: ResultMeta | undefined) {
  return Boolean(meta && meta.fallback_mode !== "none");
}

function hasFallbackSeries(series: ChoiceMacroLatestPoint[]) {
  return series.some((point) => point.refresh_tier === "fallback");
}

function ncdRowCaption(row: NcdFundingProxyPayload["rows"][number]) {
  const parts = (["1M", "3M", "6M", "1Y"] as const)
    .map((k) => (row[k] != null ? `${k} ${row[k]}` : null))
    .filter(Boolean);
  return `${row.label}: ${parts.join(" · ")}`;
}

export function buildCrossAssetNcdProxyEvidence(input: {
  result?: NcdFundingProxyPayload | null;
  /** false when the client request failed or returned nothing usable */
  available: boolean;
}): CrossAssetNcdProxyEvidence {
  if (!input.available || !input.result) {
    return {
      asOfDate: null,
      proxyLabel: "NCD / funding",
      isActualNcdMatrix: false,
      proxyWarning: "NCD 资金代理数据不可用（请求失败或空载荷）。",
      rowCaptions: [],
      sourceMeta: "unavailable",
    };
  }
  const payload = input.result;
  const defaultProxyWarn =
    payload.is_actual_ncd_matrix === false
      ? "此为资金利率代理，不是真实 NCD 发行矩阵；禁止当作正式 NCD 表使用。"
      : "后端标记为实际矩阵，仍请核对数据血缘。";
  return {
    asOfDate: payload.as_of_date,
    proxyLabel: payload.proxy_label,
    isActualNcdMatrix: payload.is_actual_ncd_matrix,
    proxyWarning: (payload.warnings[0] ?? defaultProxyWarn).trim(),
    rowCaptions: payload.rows.slice(0, 3).map((row) => ncdRowCaption(row)),
    sourceMeta: "backend",
  };
}

function formatScore(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(2);
}

function formatCorrelation(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(2);
}

function correlationStrength(point: MacroBondLinkageTopCorrelation) {
  return Math.max(
    Math.abs(point.correlation_1y ?? 0),
    Math.abs(point.correlation_6m ?? 0),
    Math.abs(point.correlation_3m ?? 0),
  );
}

function strongestCorrelation(
  topCorrelations: MacroBondLinkageTopCorrelation[],
  targetFamily?: string,
) {
  const rows = targetFamily
    ? topCorrelations.filter((item) => item.target_family === targetFamily)
    : topCorrelations;
  return rows.slice().sort((left, right) => correlationStrength(right) - correlationStrength(left))[0];
}

function summarizeNewsText(event: ChoiceNewsEvent) {
  if (event.payload_text?.trim()) {
    return event.payload_text.trim();
  }
  if (event.payload_json?.trim()) {
    try {
      const parsed = JSON.parse(event.payload_json) as Record<string, unknown>;
      const headline = typeof parsed.headline === "string" ? parsed.headline.trim() : "";
      const summary = typeof parsed.summary === "string" ? parsed.summary.trim() : "";
      return [headline, summary].filter(Boolean).join(" - ") || event.payload_json.trim();
    } catch {
      return event.payload_json.trim();
    }
  }
  if (event.error_code !== 0) {
    return event.error_msg?.trim() || "vendor callback error";
  }
  return "empty event payload";
}

function eventSeverity(event: ChoiceNewsEvent): CalendarItem["level"] {
  if (event.error_code !== 0) {
    return "high";
  }
  const text = summarizeNewsText(event).toLowerCase();
  if (
    text.includes("cpi") ||
    text.includes("nonfarm") ||
    text.includes("policy") ||
    text.includes("rate")
  ) {
    return "high";
  }
  if (text.includes("industrial") || text.includes("credit") || text.includes("liquidity")) {
    return "medium";
  }
  return "low";
}

function calendarDateLabel(raw: string) {
  if (!raw.trim()) {
    return "n/a";
  }
  if (raw.length >= 10) {
    return raw.slice(5, 10);
  }
  return raw;
}

function signalFromTone(changeTone: ResolvedCrossAssetKpi["changeTone"]): WatchSignal {
  if (changeTone === "positive") {
    return "green";
  }
  if (changeTone === "negative") {
    return "red";
  }
  return "yellow";
}

function signalTextFromTone(changeTone: ResolvedCrossAssetKpi["changeTone"]) {
  if (changeTone === "positive") {
    return "Move is extending.";
  }
  if (changeTone === "negative") {
    return "Move is fading.";
  }
  return "Signal needs confirmation.";
}

function normalizeLabel(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function stanceTone(stance: string): ActionTone {
  const lowered = stance.toLowerCase();
  if (
    lowered.includes("bull") ||
    lowered.includes("support") ||
    lowered.includes("constructive") ||
    lowered.includes("prefer")
  ) {
    return "bull";
  }
  if (
    lowered.includes("bear") ||
    lowered.includes("restrict") ||
    lowered.includes("tight") ||
    lowered.includes("caution")
  ) {
    return "bear";
  }
  return "warning";
}

function buildFallbackResearchViews(input: {
  env: Partial<MacroBondLinkageEnvironmentScore>;
  topCorrelations: MacroBondLinkageTopCorrelation[];
  linkageWarnings: string[];
}): MacroBondResearchView[] {
  const liq = input.env.liquidity_score ?? 0;
  const rate = input.env.rate_direction_score ?? 0;
  const growth = input.env.growth_score ?? 0;
  const creditCorr = strongestCorrelation(input.topCorrelations, "credit_spread");
  const topCorr = strongestCorrelation(input.topCorrelations);

  const duration: MacroBondResearchView = {
    key: "duration",
    status: "pending_signal",
    stance: rate < -0.2 && liq >= 0 ? "bullish" : rate > 0.2 ? "bearish" : "neutral",
    confidence: Math.abs(rate) > 0.25 || Math.abs(liq) > 0.25 ? "medium" : "low",
    summary:
      rate < -0.2 && liq >= 0
        ? `Fallback read: easing rates and supportive liquidity favor duration (${formatScore(rate)} / ${formatScore(liq)}).`
        : rate > 0.2
          ? `Fallback read: higher rate pressure caps long duration (${formatScore(rate)}).`
          : `Fallback read: duration conviction is limited while rates and liquidity stay mixed.`,
    affected_targets: ["rates", "ncd", "high_grade_credit"],
    evidence: [`liquidity_score ${formatScore(liq)}`, `rate_direction_score ${formatScore(rate)}`],
  };

  const curve: MacroBondResearchView = {
    key: "curve",
    status: "pending_signal",
    stance: liq > 0.15 ? "front_end_preferred" : rate < -0.15 ? "steepening_bias" : "neutral",
    confidence: Math.abs(liq) > 0.2 ? "medium" : "low",
    summary:
      liq > 0.15
        ? `Fallback read: front-end carry still benefits from easier funding (${formatScore(liq)}).`
        : rate < -0.15
          ? `Fallback read: falling-rate setup leaves room for selective extension.`
          : "Fallback read: curve message is balanced rather than directional.",
    affected_targets: ["rates", "ncd"],
    evidence: [`liquidity_score ${formatScore(liq)}`, `rate_direction_score ${formatScore(rate)}`],
  };

  const credit: MacroBondResearchView = {
    key: "credit",
    status: "pending_signal",
    stance: creditCorr?.direction === "negative" ? "selective" : growth < -0.1 ? "defensive" : "neutral",
    confidence: creditCorr ? "medium" : "low",
    summary: creditCorr
      ? `Fallback read: credit should stay selective while ${creditCorr.target_family} remains the dominant linkage.`
      : growth < -0.1
        ? "Fallback read: softer growth argues for staying in higher-quality credit only."
        : "Fallback read: no strong governed credit stance is available yet.",
    affected_targets: ["high_grade_credit"],
    evidence: creditCorr
      ? [`${creditCorr.target_family} corr6m ${formatCorrelation(creditCorr.correlation_6m)}`]
      : [`growth_score ${formatScore(growth)}`],
  };

  const instrument: MacroBondResearchView = {
    key: "instrument",
    status: "pending_signal",
    stance: liq > 0 ? "barbell" : "balanced",
    confidence: topCorr ? "medium" : "low",
    summary:
      liq > 0
        ? "Fallback read: keep implementation concentrated in rates, NCD, and high-grade credit."
        : "Fallback read: stay balanced across rates, NCD, and high-grade credit until conviction improves.",
    affected_targets: ["rates", "ncd", "high_grade_credit"],
    evidence: topCorr
      ? [`${topCorr.series_name} -> ${topCorr.target_family} ${topCorr.target_tenor ?? ""}`.trim()]
      : input.linkageWarnings.slice(0, 1),
  };

  return [duration, curve, credit, instrument];
}

function fallbackAxis(axisKey: (typeof TRANSMISSION_AXIS_ORDER)[number]): MacroBondTransmissionAxis {
  if (axisKey === "equity_bond_spread") {
    return {
      axis_key: axisKey,
      status: "pending_signal",
      stance: "neutral",
      summary: "Pending governed equity-bond spread proxy; do not infer from unrelated signals.",
      impacted_views: ["duration", "credit"],
      required_series_ids: ["CA.CSI300"],
      warnings: ["missing governed proxy series"],
    };
  }
  return {
    axis_key: axisKey,
    status: "pending_signal",
    stance: "neutral",
    summary: "Pending governed mega-cap leadership proxy; keep this axis visible but unresolved.",
    impacted_views: ["duration", "instrument"],
    required_series_ids: ["CA.MEGA_CAP_LEADERSHIP"],
    warnings: ["missing governed proxy series"],
  };
}

const HEURISTIC_AXIS_WARNING =
  "Heuristic read from environment scores only; not a governed transmission-axis signal.";

function buildFallbackTransmissionAxes(input: {
  env: Partial<MacroBondLinkageEnvironmentScore>;
}): MacroBondTransmissionAxis[] {
  const rate = input.env.rate_direction_score ?? 0;
  const liq = input.env.liquidity_score ?? 0;
  const inflation = input.env.inflation_score ?? 0;

  return [
    {
      axis_key: "global_rates",
      status: "pending_signal",
      stance: rate > 0.15 ? "restrictive" : rate < -0.15 ? "supportive" : "neutral",
      summary:
        rate > 0.15
          ? `Fallback read: global rates are a constraint on aggressive duration (${formatScore(rate)}).`
          : rate < -0.15
            ? `Fallback read: softer global rates reduce long-end pressure (${formatScore(rate)}).`
            : "Fallback read: global-rate pressure is balanced.",
      impacted_views: ["duration", "curve"],
      required_series_ids: [],
      warnings: [HEURISTIC_AXIS_WARNING],
    },
    {
      axis_key: "liquidity",
      status: "pending_signal",
      stance: liq > 0.15 ? "supportive" : liq < -0.15 ? "restrictive" : "neutral",
      summary:
        liq > 0.15
          ? `Fallback read: funding conditions remain supportive (${formatScore(liq)}).`
          : liq < -0.15
            ? `Fallback read: tighter liquidity is a headwind (${formatScore(liq)}).`
            : "Fallback read: liquidity is not sending a strong signal.",
      impacted_views: ["duration", "curve", "instrument"],
      required_series_ids: [],
      warnings: [HEURISTIC_AXIS_WARNING],
    },
    fallbackAxis("equity_bond_spread"),
    {
      axis_key: "commodities_inflation",
      status: "pending_signal",
      stance: inflation > 0.15 ? "restrictive" : inflation < -0.15 ? "supportive" : "neutral",
      summary:
        inflation > 0.15
          ? `Fallback read: commodity-inflation pressure limits valuation expansion (${formatScore(inflation)}).`
          : inflation < -0.15
            ? `Fallback read: softer inflation helps duration and high-grade carry.`
            : "Fallback read: commodities and inflation are not dominant today.",
      impacted_views: ["duration", "credit", "instrument"],
      required_series_ids: [],
      warnings: [HEURISTIC_AXIS_WARNING],
    },
    fallbackAxis("mega_cap_equities"),
  ];
}

function viewCardFromSource(
  view: MacroBondResearchView,
  source: ResearchCardSource,
): CrossAssetResearchViewCard {
  const typedKey = RESEARCH_VIEW_ORDER.find((key) => key === view.key);
  return {
    key: view.key,
    label: typedKey ? RESEARCH_VIEW_LABEL[typedKey] : normalizeLabel(view.key),
    stance: normalizeLabel(view.stance),
    confidence: normalizeLabel(view.confidence),
    summary: view.summary,
    status: view.status,
    affectedTargets: view.affected_targets ?? [],
    evidence: view.evidence ?? [],
    source,
  };
}

function transmissionAxisFromSource(
  axis: MacroBondTransmissionAxis,
  source: ResearchCardSource,
): CrossAssetTransmissionAxisRow {
  const typedKey = TRANSMISSION_AXIS_ORDER.find((key) => key === axis.axis_key);
  return {
    axisKey: axis.axis_key,
    label: typedKey ? TRANSMISSION_AXIS_LABEL[typedKey] : normalizeLabel(axis.axis_key),
    status: axis.status,
    stance: normalizeLabel(axis.stance),
    summary: axis.summary,
    impactedViews: axis.impacted_views ?? [],
    requiredSeriesIds: axis.required_series_ids ?? [],
    warnings: axis.warnings ?? [],
    source,
  };
}

export function buildCrossAssetDriversViewModel(input: {
  researchViews?: MacroBondResearchView[];
  transmissionAxes?: MacroBondTransmissionAxis[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
  topCorrelations: MacroBondLinkageTopCorrelation[];
  linkageWarnings: string[];
  kpis: ResolvedCrossAssetKpi[];
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
  latestSeries: ChoiceMacroLatestPoint[];
  crossAssetDataDate: string;
  linkageReportDate: string;
  calendarEvents?: ResearchCalendarEvent[];
  calendarReportDate?: string;
  newsEvents?: ChoiceNewsEvent[];
  ncdProxy?: NcdFundingProxyPayload | null;
  ncdProxyAvailable: boolean;
}): CrossAssetDriversViewModel {
  const researchCards = buildResearchSummaryCards({
    researchViews: input.researchViews,
    env: input.env,
    topCorrelations: input.topCorrelations,
    linkageWarnings: input.linkageWarnings,
  });
  const transmissionAxes = buildTransmissionAxisRows({
    transmissionAxes: input.transmissionAxes,
    env: input.env,
  });
  const candidateActions = buildCrossAssetCandidateActions({
    researchViews: input.researchViews,
    transmissionAxes: input.transmissionAxes,
    env: input.env,
    topCorrelations: input.topCorrelations,
    linkageWarnings: input.linkageWarnings,
    ncdProxy: input.ncdProxy,
  });
  const watchList = buildCrossAssetWatchList({
    kpis: input.kpis,
    researchViews: input.researchViews,
    transmissionAxes: input.transmissionAxes,
    topCorrelations: input.topCorrelations,
    linkageWarnings: input.linkageWarnings,
  });
  const eventCalendarRows = buildCrossAssetEventItems({
    events: input.calendarEvents,
    reportDate: input.calendarReportDate,
    linkageWarnings: input.linkageWarnings,
    newsEvents: input.newsEvents,
  });
  const ncdProxyEvidence = buildCrossAssetNcdProxyEvidence({
    result: input.ncdProxy,
    available: input.ncdProxyAvailable,
  });
  const statusFlags = buildCrossAssetStatusFlags({
    latestMeta: input.latestMeta,
    linkageMeta: input.linkageMeta,
    latestSeries: input.latestSeries,
    crossAssetDataDate: input.crossAssetDataDate,
    linkageReportDate: input.linkageReportDate,
  });

  return {
    researchCards,
    transmissionAxes,
    candidateActions,
    watchList,
    eventCalendarRows,
    ncdProxyEvidence,
    statusFlags,
  };
}

export function buildCrossAssetStatusFlags(input: {
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
  latestSeries: ChoiceMacroLatestPoint[];
  crossAssetDataDate: string;
  linkageReportDate: string;
}): CrossAssetStatusFlag[] {
  const flags: CrossAssetStatusFlag[] = [];

  if (input.latestMeta && !input.latestMeta.formal_use_allowed) {
    flags.push({
      id: "analytical-only",
      label: "analytical only",
      tone: "warning",
      detail: "This page reads the analytical chain and does not replace formal execution output.",
    });
  }

  if (hasStaleMeta(input.latestMeta) || hasStaleMeta(input.linkageMeta)) {
    flags.push({
      id: "stale",
      label: "stale",
      tone: "warning",
      detail: "Result metadata is stale or vendor-stale; confirm dates before using the readout.",
    });
  }

  if (hasFallbackMeta(input.latestMeta) || hasFallbackMeta(input.linkageMeta) || hasFallbackSeries(input.latestSeries)) {
    flags.push({
      id: "fallback",
      label: "fallback",
      tone: "caution",
      detail: "Fallback snapshots are present, so conclusions should be used with reduced confidence.",
    });
  }

  if (input.latestSeries.length === 0 || (!input.crossAssetDataDate && !input.linkageReportDate)) {
    flags.push({
      id: "no-data",
      label: "no data",
      tone: "danger",
      detail: "There is not enough governed data yet to form a cross-asset read.",
    });
  }

  return flags;
}

export function buildResearchSummaryCards(input: {
  researchViews?: MacroBondResearchView[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
  topCorrelations: MacroBondLinkageTopCorrelation[];
  linkageWarnings: string[];
}): CrossAssetResearchViewCard[] {
  const backendViews = new Map((input.researchViews ?? []).map((row) => [row.key, row]));
  const fallbackViews = new Map(
    buildFallbackResearchViews(input).map((row) => [row.key, row] as const),
  );

  return RESEARCH_VIEW_ORDER.map((key) => {
    const backend = backendViews.get(key);
    if (backend) {
      return viewCardFromSource(backend, "backend");
    }
    return viewCardFromSource(fallbackViews.get(key)!, "fallback");
  });
}

export function buildTransmissionAxisRows(input: {
  transmissionAxes?: MacroBondTransmissionAxis[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
}): CrossAssetTransmissionAxisRow[] {
  const backendAxes = new Map((input.transmissionAxes ?? []).map((row) => [row.axis_key, row]));
  const fallbackAxes = new Map(
    buildFallbackTransmissionAxes(input).map((row) => [row.axis_key, row] as const),
  );

  return TRANSMISSION_AXIS_ORDER.map((axisKey) => {
    const backend = backendAxes.get(axisKey);
    if (backend) {
      return transmissionAxisFromSource(backend, "backend");
    }
    return transmissionAxisFromSource(fallbackAxes.get(axisKey)!, "fallback");
  });
}

export function buildCrossAssetCandidateActions(input: {
  researchViews?: MacroBondResearchView[];
  transmissionAxes?: MacroBondTransmissionAxis[];
  env: Partial<MacroBondLinkageEnvironmentScore>;
  topCorrelations: MacroBondLinkageTopCorrelation[];
  linkageWarnings: string[];
  /** 仅作旁证，不得当作真实 NCD 发行矩阵 */
  ncdProxy?: NcdFundingProxyPayload | null;
}): CrossAssetCandidateAction[] {
  const views = buildResearchSummaryCards(input);
  const axes = buildTransmissionAxisRows({
    transmissionAxes: input.transmissionAxes,
    env: input.env,
  });
  const rows: CrossAssetCandidateAction[] = [];
  const ncd = input.ncdProxy;
  if (ncd && ncd.is_actual_ncd_matrix === false) {
    rows.push({
      tone: "warning",
      action: "将 NCD/资金仅视为代理旁证。",
      reason: ncd.warnings[0] ?? "Not an actual NCD issuance matrix.",
      evidence: ncd.proxy_label,
    });
  }

  const durationCard = views.find((row) => row.key === "duration");
  const instrumentCard = views.find((row) => row.key === "instrument");
  const readyAxes = axes.filter((row) => row.status === "ready");
  const firstAxis = readyAxes[0];
  const globalRatesAxis = axes.find((row) => row.axisKey === "global_rates");
  const pendingAxis = axes.find((row) => row.status === "pending_signal");
  const topCorr = strongestCorrelation(input.topCorrelations);

  if (durationCard) {
    rows.push({
      tone: stanceTone(durationCard.stance),
      action: "Anchor the first trade discussion on duration.",
      reason: `duration view: ${durationCard.summary}`,
      evidence:
        durationCard.evidence[0] ??
        `${globalRatesAxis?.axisKey ?? firstAxis?.axisKey ?? "liquidity"} | ${globalRatesAxis?.summary ?? firstAxis?.summary ?? "no axis detail"}`,
    });
  }

  if (instrumentCard) {
    rows.push({
      tone: stanceTone(instrumentCard.stance),
      action: "Keep instrument preference inside rates, NCD, and high-grade credit.",
      reason: `instrument view: ${instrumentCard.summary}`,
      evidence:
        instrumentCard.evidence[0] ??
        (instrumentCard.affectedTargets.length > 0
          ? `targets ${instrumentCard.affectedTargets.join(", ")}`
          : "instrument targets pending"),
    });
  }

  if (globalRatesAxis) {
    rows.push({
      tone: stanceTone(globalRatesAxis.stance),
      action: "Use the global-rates axis as the risk cap for long-end positioning.",
      reason: `global_rates axis: ${globalRatesAxis.summary}`,
      evidence: `${globalRatesAxis.axisKey} | ${globalRatesAxis.stance}`,
    });
  }

  if (pendingAxis) {
    rows.push({
      tone: "warning",
      action: `Keep ${pendingAxis.label} visible as pending.`,
      reason: `${pendingAxis.label} is still waiting for a governed signal and should not be fabricated.`,
      evidence: pendingAxis.warnings[0] ?? pendingAxis.summary,
    });
  }

  if (rows.length === 0) {
    rows.push({
      tone: topCorr?.direction === "positive" ? "bull" : "warning",
      action: "Hold off on a candidate action.",
      reason: "There is not enough aligned research-view evidence yet.",
      evidence: topCorr
        ? `${topCorr.series_name} -> ${topCorr.target_family} ${topCorr.target_tenor ?? ""}`.trim()
        : "environment score and top correlations remain weak",
    });
  }

  if (input.linkageWarnings.length > 0) {
    rows.push({
      tone: "warning",
      action: "Check provenance before escalation.",
      reason: "Analytical warnings still need to be read alongside the investment-research output.",
      evidence: input.linkageWarnings[0],
    });
  }

  return rows.slice(0, 5);
}

export function buildCrossAssetEventItems(input: {
  events?: ResearchCalendarEvent[];
  reportDate?: string;
  linkageWarnings?: string[];
  newsEvents?: ChoiceNewsEvent[];
}): CalendarItem[] {
  if (input.events) {
    return input.events
      .slice()
      .sort((left, right) => right.date.localeCompare(left.date))
      .slice(0, 4)
      .map(mapResearchCalendarEventToCalendarItem);
  }

  const warningRows = (input.linkageWarnings ?? []).map((warning, index) => ({
    date: input.reportDate ? input.reportDate.slice(5) : "n/a",
    event: warning,
    amount: "linkage warning",
    level: "high" as const,
    note: `warning ${index + 1}`,
  }));

  const newsRows = (input.newsEvents ?? [])
    .slice()
    .sort((left, right) => right.received_at.localeCompare(left.received_at))
    .slice(0, 4)
    .map((event) => ({
      date: calendarDateLabel(event.received_at),
      event: summarizeNewsText(event),
      amount: event.topic_code || event.content_type,
      level: eventSeverity(event),
      note: event.group_id || event.content_type,
    }));

  return [...warningRows, ...newsRows].slice(0, 6);
}

export function buildCrossAssetWatchList(input: {
  kpis: ResolvedCrossAssetKpi[];
  researchViews?: MacroBondResearchView[];
  transmissionAxes?: MacroBondTransmissionAxis[];
  topCorrelations: MacroBondLinkageTopCorrelation[];
  linkageWarnings: string[];
}): CrossAssetWatchRow[] {
  const researchCards = buildResearchSummaryCards({
    researchViews: input.researchViews,
    env: {},
    topCorrelations: input.topCorrelations,
    linkageWarnings: input.linkageWarnings,
  });
  const axisRows = buildTransmissionAxisRows({
    transmissionAxes: input.transmissionAxes,
    env: {},
  });
  const readyResearch = researchCards.filter((row) => row.status === "ready");
  const readyAxes = axisRows.filter((row) => row.status === "ready");
  const topCorr = strongestCorrelation(input.topCorrelations);
  const warningText = input.linkageWarnings[0];

  return input.kpis
    .filter((kpi) => kpi.valueLabel !== "-" && kpi.valueLabel !== "不可用")
    .slice(0, 4)
    .map((kpi, index) => {
      const researchCard = readyResearch[index % Math.max(readyResearch.length, 1)];
      const axisRow = readyAxes[index % Math.max(readyAxes.length, 1)];
      const correlationNote =
        topCorr && index === 0
          ? `corr ${topCorr.target_family}${topCorr.target_tenor ? ` ${topCorr.target_tenor}` : ""}`
          : "";
      return {
        name: kpi.label,
        current: kpi.valueLabel,
        note: researchCard
          ? `${kpi.tag} · ${researchCard.key}: ${researchCard.summary}`
          : `${kpi.tag} · ${kpi.changeLabel}`,
        signal: signalFromTone(kpi.changeTone),
        signalText: warningText && index === 0
          ? `Check provenance first. ${axisRow ? `${axisRow.label}: ${axisRow.summary}` : ""}`.trim()
          : [signalTextFromTone(kpi.changeTone), axisRow ? `${axisRow.label}: ${axisRow.summary}` : "", correlationNote]
              .filter(Boolean)
              .join(" · "),
      };
    });
}
