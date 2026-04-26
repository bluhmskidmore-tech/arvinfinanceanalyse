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
  global_rates: "全球利率",
  liquidity: "流动性",
  equity_bond_spread: "股债相对估值",
  commodities_inflation: "商品与通胀",
  mega_cap_equities: "大市值结构",
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
  /** 经 normalizeLabel，与后端原始 stance 对应，供 tone/证据字符串使用 */
  stance: string;
  /** 侧栏/卡片上展示的短中文标签 */
  stanceLabel: string;
  summary: string;
  impactedViews: string[];
  requiredSeriesIds: string[];
  warnings: string[];
  source: ResearchCardSource;
};

export type CrossAssetClassAnalysisLine = {
  key: string;
  label: string;
  status: "ready" | "pending_signal";
  stateLabel: "ready" | "stale" | "source_blocked" | "missing_dependency" | "pending_definition";
  direction: string;
  dataLabel: string;
  sourceLabel: string;
  explanation: string;
};

export type CrossAssetClassAnalysisRow = {
  key: "stock" | "commodities" | "options";
  label: string;
  status: "ready" | "pending_signal";
  direction: string;
  explanation: string;
  lines: CrossAssetClassAnalysisLine[];
};

export type CrossAssetEquityEvidenceItem = {
  key: "broad_index" | "csi300_pe" | "mega_cap_weight" | "mega_cap_top5_weight";
  label: string;
  status: "ready" | "missing_dependency";
  valueLabel: string;
  changeLabel: string;
  unitLabel: string;
  tradeDate: string | null;
  sourceLabel: string;
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
  assetClassAnalysisRows: CrossAssetClassAnalysisRow[];
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

function hasBlockedMeta(meta: ResultMeta | undefined) {
  return meta?.vendor_status === "vendor_unavailable";
}

function hasFallbackMeta(meta: ResultMeta | undefined) {
  return Boolean(meta && meta.fallback_mode !== "none");
}

function hasFallbackSeries(series: ChoiceMacroLatestPoint[]) {
  return series.some((point) => point.refresh_tier === "fallback");
}

function hasChoiceSeries(series: ChoiceMacroLatestPoint[]) {
  return series.some((point) => /^(E100|EMM|EMG|EMI|EM\d)/.test(point.series_id));
}

function hasPublicSupplementSeries(series: ChoiceMacroLatestPoint[]) {
  return series.some((point) => point.series_id.startsWith("CA."));
}

function ncdRowCaption(row: NcdFundingProxyPayload["rows"][number]) {
  const parts = (["1M", "3M", "6M", "9M", "1Y"] as const)
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
  const warnings = payload.warnings.map((warning) => warning.trim()).filter(Boolean);
  return {
    asOfDate: payload.as_of_date,
    proxyLabel: payload.proxy_label,
    isActualNcdMatrix: payload.is_actual_ncd_matrix,
    proxyWarning: warnings.length > 0 ? warnings.join(" ") : defaultProxyWarn,
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

/** Macro–bond correlation cells: align with market-data `formatCorrelation` ("不可用" when missing). */
export function formatLinkageCorrelationDisplay(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "不可用";
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

/** UI 短标签；原始 stance 仍保留在 `row.stance` 供逻辑与 tone 判断 */
function transmissionStanceLabel(raw: string): string {
  const key = raw.trim().toLowerCase().replace(/\s+/g, "_");
  const table: Record<string, string> = {
    supportive: "偏有利",
    neutral: "中性",
    restrictive: "偏紧",
    conflicted: "有冲突",
    risk_on: "风险偏强",
    risk_off: "风险偏弱",
  };
  return table[key] ?? normalizeLabel(raw);
}

/** 将 impacted_views 的 key 译成与研究判断区一致的短名 */
export function formatImpactedViewsForDisplay(views: string[]): string {
  return views
    .map((k) => {
      if ((RESEARCH_VIEW_ORDER as readonly string[]).includes(k)) {
        return RESEARCH_VIEW_LABEL[k as (typeof RESEARCH_VIEW_ORDER)[number]];
      }
      return k;
    })
    .join("、");
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
      ? [`${creditCorr.target_family} corr6m ${formatLinkageCorrelationDisplay(creditCorr.correlation_6m)}`]
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
    stanceLabel: transmissionStanceLabel(axis.stance),
    summary: axis.summary,
    impactedViews: axis.impacted_views ?? [],
    requiredSeriesIds: axis.required_series_ids ?? [],
    warnings: axis.warnings ?? [],
    source,
  };
}

function kpiByKey(kpis: ResolvedCrossAssetKpi[], key: string) {
  return kpis.find((kpi) => kpi.key === key);
}

function directionFromKpi(kpi: ResolvedCrossAssetKpi | undefined) {
  if (!kpi) {
    return "pending";
  }
  if (kpi.changeTone === "positive") {
    return "supportive";
  }
  if (kpi.changeTone === "negative") {
    return "restrictive";
  }
  return "neutral";
}

function explanationFromKpi(kpi: ResolvedCrossAssetKpi | undefined, pending: string) {
  if (!kpi) {
    return pending;
  }
  return `${kpi.label} is ${kpi.valueLabel}, latest move ${kpi.changeLabel}.`;
}

function hasUsableKpi(kpi: ResolvedCrossAssetKpi | undefined) {
  return Boolean(kpi && (kpi.sparkline.length > 0 || kpi.changeTone !== "default"));
}

function kpiDateSuffix(kpi: ResolvedCrossAssetKpi) {
  return kpi.tradeDate ? ` · ${kpi.tradeDate}` : "";
}

function compactKpiData(kpi: ResolvedCrossAssetKpi | undefined) {
  if (!hasUsableKpi(kpi)) {
    return null;
  }
  return `${kpi!.label} ${kpi!.valueLabel} / ${kpi!.changeLabel}${kpiDateSuffix(kpi!)}`;
}

function combinedDataLabel(parts: Array<string | null>, pending: string) {
  const readyParts = parts.filter((part): part is string => Boolean(part));
  return readyParts.length > 0 ? readyParts.join("；") : pending;
}

function dataLabelFromKpi(kpi: ResolvedCrossAssetKpi | undefined, pending: string) {
  if (!hasUsableKpi(kpi)) {
    return pending;
  }
  const tradeDate = kpi!.tradeDate ? ` · ${kpi!.tradeDate}` : "";
  return `${kpi!.valueLabel} / ${kpi!.changeLabel}${tradeDate}`;
}

function sourceLabelFromKpi(kpi: ResolvedCrossAssetKpi | undefined, fallback: string) {
  const resolved = kpi;
  if (!resolved || !hasUsableKpi(resolved)) {
    return fallback;
  }
  const normalizedVendor = resolved.vendorName?.trim().toLowerCase();
  let sourcePrefix: string;
  if (resolved.sourceKind === "choice") {
    sourcePrefix = "Choice接入码";
  } else if (resolved.sourceKind === "public" && normalizedVendor === "tushare") {
    sourcePrefix = "Tushare";
  } else if (resolved.sourceKind === "public" && normalizedVendor) {
    sourcePrefix = `公共补充源(${resolved.vendorName})`;
  } else if (resolved.sourceKind === "public") {
    sourcePrefix = "Tushare/公共补充源";
  } else if (resolved.sourceKind === "derived") {
    sourcePrefix = "派生指标";
  } else {
    sourcePrefix = "缺接入码";
  }
  return `${sourcePrefix}: ${resolved.resolvedSeriesId}`;
}

function combinedSourceLabel(kpis: Array<ResolvedCrossAssetKpi | undefined>, fallback: string) {
  const labels = kpis
    .filter((kpi): kpi is ResolvedCrossAssetKpi => hasUsableKpi(kpi))
    .map((kpi) => sourceLabelFromKpi(kpi, fallback));
  return labels.length > 0 ? labels.join("；") : fallback;
}

function stateLabelFromKpi(
  kpi: ResolvedCrossAssetKpi | undefined,
  meta?: ResultMeta,
): CrossAssetClassAnalysisLine["stateLabel"] {
  if (!hasUsableKpi(kpi)) {
    return "missing_dependency";
  }
  if (hasBlockedMeta(meta) && kpi!.sourceKind === "choice") {
    return "source_blocked";
  }
  if (hasStaleMeta(meta)) {
    return "stale";
  }
  return "ready";
}

const EQUITY_EVIDENCE_DEFINITIONS = [
  {
    key: "broad_index",
    kpiKey: "financial_conditions",
    label: "指数层面",
    unitFallback: "index",
    sourceFallback: "需登记 Choice 接入码或 Tushare 指数输入",
  },
  {
    key: "csi300_pe",
    kpiKey: "csi300_pe",
    label: "沪深300市盈率",
    unitFallback: "x",
    sourceFallback: "需登记 Tushare index_dailybasic",
  },
  {
    key: "mega_cap_weight",
    kpiKey: "mega_cap_weight",
    label: "沪深300前十大权重",
    unitFallback: "%",
    sourceFallback: "需登记 Choice 大市值权重码 / Tushare index_weight",
  },
  {
    key: "mega_cap_top5_weight",
    kpiKey: "mega_cap_top5_weight",
    label: "沪深300前五大权重",
    unitFallback: "%",
    sourceFallback: "需登记 Choice 大市值权重码 / Tushare index_weight",
  },
] as const;

function unitLabelFromKpi(kpi: ResolvedCrossAssetKpi | undefined, fallback: string) {
  const unit = kpi?.unit?.trim();
  return unit || fallback;
}

export function buildCrossAssetEquityEvidenceItems(kpis: ResolvedCrossAssetKpi[]): CrossAssetEquityEvidenceItem[] {
  return EQUITY_EVIDENCE_DEFINITIONS.map((definition) => {
    const kpi = kpiByKey(kpis, definition.kpiKey);
    return {
      key: definition.key,
      label: definition.label,
      status: hasUsableKpi(kpi) ? "ready" : "missing_dependency",
      valueLabel: kpi?.valueLabel ?? "—",
      changeLabel: kpi?.changeLabel ?? "—",
      unitLabel: unitLabelFromKpi(kpi, definition.unitFallback),
      tradeDate: kpi?.tradeDate ?? null,
      sourceLabel: sourceLabelFromKpi(kpi, definition.sourceFallback),
    };
  });
}

function axisByKey(rows: CrossAssetTransmissionAxisRow[], key: string) {
  return rows.find((row) => row.axisKey === key);
}

export function buildCrossAssetClassAnalysisRows(input: {
  kpis: ResolvedCrossAssetKpi[];
  transmissionAxes: CrossAssetTransmissionAxisRow[];
  latestMeta?: ResultMeta;
  linkageMeta?: ResultMeta;
}): CrossAssetClassAnalysisRow[] {
  const equityAxis = axisByKey(input.transmissionAxes, "equity_bond_spread");
  const megaCapAxis = axisByKey(input.transmissionAxes, "mega_cap_equities");
  const commodityAxis = axisByKey(input.transmissionAxes, "commodities_inflation");
  const broadIndex = kpiByKey(input.kpis, "financial_conditions");
  const csi300Pe = kpiByKey(input.kpis, "csi300_pe");
  const megaCapTop10 = kpiByKey(input.kpis, "mega_cap_weight");
  const megaCapTop5 = kpiByKey(input.kpis, "mega_cap_top5_weight");
  const energy = kpiByKey(input.kpis, "brent");
  const ferrous = kpiByKey(input.kpis, "steel");
  const stockLines: CrossAssetClassAnalysisLine[] = [
    {
      key: "broad_index",
      label: "指数层面",
      status: hasUsableKpi(broadIndex) ? "ready" : "pending_signal",
      stateLabel: stateLabelFromKpi(broadIndex, input.latestMeta),
      direction: directionFromKpi(broadIndex),
      dataLabel: dataLabelFromKpi(broadIndex, "等待 EMM01843735 / CA.CSI300 / Tushare CSI300"),
      sourceLabel: sourceLabelFromKpi(broadIndex, "需登记 Choice 接入码或 Tushare 指数输入"),
      explanation: explanationFromKpi(
        broadIndex,
        "Pending governed broad-index input; do not turn this into stock-picking or sector rotation.",
      ),
    },
    {
      key: "valuation_spread",
      label: "估值/股债利差",
      status: hasUsableKpi(csi300Pe) || equityAxis?.status === "ready" ? "ready" : "pending_signal",
      stateLabel: hasUsableKpi(csi300Pe)
        ? stateLabelFromKpi(csi300Pe, input.latestMeta)
        : equityAxis?.status === "ready" && hasBlockedMeta(input.linkageMeta)
          ? "source_blocked"
          : equityAxis?.status === "ready" && hasStaleMeta(input.linkageMeta)
            ? "stale"
            : equityAxis?.status === "ready"
              ? "ready"
              : "missing_dependency",
      direction: equityAxis?.stance ?? directionFromKpi(csi300Pe),
      dataLabel: combinedDataLabel(
        [compactKpiData(csi300Pe), equityAxis?.status === "ready" ? "股债利差轴 ready" : null],
        "等待 CA.CSI300_PE / 股债利差轴",
      ),
      sourceLabel: [
        combinedSourceLabel([csi300Pe], "需登记 Tushare index_dailybasic"),
        equityAxis?.status === "ready" ? `双源轴(${equityAxis.source}): ${equityAxis.requiredSeriesIds.join(", ")}` : null,
      ]
        .filter(Boolean)
        .join("；"),
      explanation:
        equityAxis?.summary ??
        explanationFromKpi(csi300Pe, "Pending governed CSI300 valuation and equity-bond spread input."),
    },
    {
      key: "mega_cap_weight",
      label: "大市值权重",
      status: hasUsableKpi(megaCapTop10) || hasUsableKpi(megaCapTop5) || megaCapAxis?.status === "ready" ? "ready" : "pending_signal",
      stateLabel: hasUsableKpi(megaCapTop10) || hasUsableKpi(megaCapTop5)
        ? stateLabelFromKpi(megaCapTop10 ?? megaCapTop5, input.latestMeta)
        : megaCapAxis?.status === "ready" && hasBlockedMeta(input.linkageMeta)
          ? "source_blocked"
          : megaCapAxis?.status === "ready" && hasStaleMeta(input.linkageMeta)
            ? "stale"
            : megaCapAxis?.status === "ready"
              ? "ready"
              : "missing_dependency",
      direction: megaCapAxis?.stance ?? directionFromKpi(megaCapTop10),
      dataLabel: combinedDataLabel(
        [compactKpiData(megaCapTop10), compactKpiData(megaCapTop5)],
        "双源待补：Choice 大市值权重码 / Tushare index_weight",
      ),
      sourceLabel: [
        combinedSourceLabel([megaCapTop10, megaCapTop5], "需登记 Choice 大市值权重码 / Tushare index_weight"),
        megaCapAxis?.status === "ready" ? `双源轴(${megaCapAxis.source}): ${megaCapAxis.requiredSeriesIds.join(", ")}` : null,
      ]
        .filter(Boolean)
        .join("；"),
      explanation:
        megaCapAxis?.summary ??
        explanationFromKpi(megaCapTop10, "Pending governed mega-cap leadership proxy; keep the large-cap-weight channel unresolved."),
    },
  ];
  const commodityLines: CrossAssetClassAnalysisLine[] = [
    {
      key: "energy",
      label: "能源",
      status: hasUsableKpi(energy) ? "ready" : "pending_signal",
      stateLabel: stateLabelFromKpi(energy, input.latestMeta),
      direction: directionFromKpi(energy),
      dataLabel: dataLabelFromKpi(energy, "等待 CA.BRENT"),
      sourceLabel: sourceLabelFromKpi(energy, "需登记能源 Choice 接入码或公共补充源"),
      explanation: explanationFromKpi(energy, "Pending governed energy-chain input."),
    },
    {
      key: "ferrous",
      label: "黑色",
      status: hasUsableKpi(ferrous) ? "ready" : "pending_signal",
      stateLabel: stateLabelFromKpi(ferrous, input.latestMeta),
      direction: directionFromKpi(ferrous),
      dataLabel: dataLabelFromKpi(ferrous, "等待 CA.STEEL"),
      sourceLabel: sourceLabelFromKpi(ferrous, "需登记黑色系 Choice 接入码或公共补充源"),
      explanation: explanationFromKpi(ferrous, "Pending governed ferrous-chain input."),
    },
    {
      key: "nonferrous",
      label: "有色",
      status: "pending_signal",
      stateLabel: "missing_dependency",
      direction: commodityAxis?.status === "ready" ? commodityAxis.stance : "pending",
      dataLabel: "需补齐铜/铝 Choice 接入码或公共补充治理输入",
      sourceLabel: commodityAxis?.requiredSeriesIds.length
        ? `${commodityAxis.source}: ${commodityAxis.requiredSeriesIds.join(", ")}`
        : "missing",
      explanation:
        commodityAxis?.status === "ready"
          ? commodityAxis.summary
          : "Pending governed non-ferrous input; do not proxy copper/aluminum with oil or steel.",
    },
  ];
  const optionLines: CrossAssetClassAnalysisLine[] = [
    {
      key: "equity_options",
      label: "权益期权",
      status: "pending_signal",
      stateLabel: "pending_definition",
      direction: "pending",
      dataLabel: "需登记 IV / skew / put-call Choice 接入码或期权治理源",
      sourceLabel: "missing",
      explanation: "No governed equity-options input for volatility, skew, or put-call pressure.",
    },
    {
      key: "commodity_options",
      label: "商品期权",
      status: "pending_signal",
      stateLabel: "pending_definition",
      direction: "pending",
      dataLabel: "需登记商品期权 IV / skew / tail-risk Choice 接入码或期权治理源",
      sourceLabel: "missing",
      explanation: "No governed commodity-options input for tail risk or supply-shock pricing.",
    },
    {
      key: "rates_bond_options",
      label: "利率/债券期权",
      status: "pending_signal",
      stateLabel: "pending_definition",
      direction: "pending",
      dataLabel: "需登记 rates vol / curve vol Choice 接入码或利率期权治理源",
      sourceLabel: "missing",
      explanation: "No governed rates or bond-options input for duration volatility or curve risk.",
    },
  ];
  const stockReady = stockLines.some((line) => line.status === "ready") || equityAxis?.status === "ready";
  const commodityReady = commodityLines.some((line) => line.status === "ready");

  return [
    {
      key: "stock",
      label: "股票分析",
      status: stockReady ? "ready" : "pending_signal",
      direction: equityAxis?.stance ?? stockLines.find((line) => line.status === "ready")?.direction ?? "pending",
      explanation:
        equityAxis?.summary ??
        megaCapAxis?.summary ??
        "Pending governed equity analysis; keep equity evidence separate from bond conclusions until the proxy is confirmed.",
      lines: stockLines,
    },
    {
      key: "commodities",
      label: "大宗商品分析",
      status: commodityReady ? "ready" : "pending_signal",
      direction: commodityAxis?.stance ?? commodityLines.find((line) => line.status === "ready")?.direction ?? "pending",
      explanation:
        commodityAxis?.summary ??
        "Pending governed commodity chain read; use only visible Brent / steel evidence and avoid adding unsupported inflation pressure.",
      lines: commodityLines,
    },
    {
      key: "options",
      label: "期权分析",
      status: "pending_signal",
      direction: "definition pending",
      explanation:
        "Options analysis definition pending: no governed volatility, skew, or put-call input is available in the current cross-asset chain.",
      lines: optionLines,
    },
  ];
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
  /** When macro/linkage fetches fail, pass stable module keys for status flags. */
  loadingFailures?: string[];
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
  const assetClassAnalysisRows = buildCrossAssetClassAnalysisRows({
    kpis: input.kpis,
    transmissionAxes,
    latestMeta: input.latestMeta,
    linkageMeta: input.linkageMeta,
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
    loadingFailures: input.loadingFailures,
  });

  return {
    researchCards,
    transmissionAxes,
    assetClassAnalysisRows,
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
  loadingFailures?: string[];
}): CrossAssetStatusFlag[] {
  const flags: CrossAssetStatusFlag[] = [];

  const loadingFailures = (input.loadingFailures ?? []).filter(Boolean);
  if (loadingFailures.length > 0) {
    const modules = loadingFailures.join(", ");
    flags.push({
      id: "loading-failure",
      label: `loading failure · ${modules}`,
      tone: "danger",
      detail: `Failed to load ${modules}; do not treat fallback cards as a complete cross-asset read.`,
    });
  }

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

  if (hasBlockedMeta(input.latestMeta) || hasBlockedMeta(input.linkageMeta)) {
    flags.push({
      id: "source-blocked",
      label: "source_blocked",
      tone: "danger",
      detail: "One vendor source is unavailable or permission-blocked; use retained rows and public supplements with explicit caution.",
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

  if (hasChoiceSeries(input.latestSeries) && hasPublicSupplementSeries(input.latestSeries)) {
    flags.push({
      id: "dual-source",
      label: "dual source ready",
      tone: "normal",
      detail: "Choice rows and Tushare/public supplement rows are both present in the governed cross-asset chain.",
    });
  }

  if (hasPublicSupplementSeries(input.latestSeries) && !hasChoiceSeries(input.latestSeries)) {
    flags.push({
      id: "choice-source-missing",
      label: "choice source missing",
      tone: "caution",
      detail: "Public/Tushare supplements are available, but no Choice-coded row is present for this snapshot.",
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
    const warnings = ncd.warnings.map((warning) => warning.trim()).filter(Boolean);
    rows.push({
      tone: "warning",
      action: "将 NCD/资金仅视为代理旁证。",
      reason: warnings.length > 0 ? warnings.join(" ") : "Not an actual NCD issuance matrix.",
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
