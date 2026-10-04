import type { EChartsOption } from "echarts";

import type {
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  LivermoreCandidateHistoryRow,
  LivermoreStockDetailCandle,
  LivermoreStockDetailPayload,
  StockKlineAnalysisPayload,
} from "../../../api/contracts";
import {
  EM_DASH,
  fixedOrDash,
  pctOrDash,
  textOrDash,
  type LabeledValue,
  type MetricTone,
} from "../../../pageModel";
import type {
  StockCandidateReviewQueueItem,
  StockRiskExitRow,
} from "./stockAnalysisPageModel";
import { nocturneTokens } from "../../../theme/designSystem";
import {
  choiceNewsDataDateLabel,
  choiceNewsTopicLabel,
  formatChoiceNewsReceivedAt,
  formatFixed,
  formatMultiple,
  formatPointSignedPercent,
  formatRatioPercent,
  formatRatioSignedPercent,
  truncateChoiceNewsText,
} from "./stockAnalysisFormat";

export type ResearchDeskPoolTab = "queue" | "watchlist" | "history";
export type ResearchDeskDossierTab =
  | "summary"
  | "fundamentals"
  | "valuation"
  | "momentum"
  | "events"
  | "finance"
  | "research"
  | "sentiment"
  | "appendix";

export type ResearchDeskQueryState = "idle" | "loading" | "error" | "success";
export type ResearchDeskSurfaceState = "ready" | "loading" | "error" | "missing" | "mismatch";

export type ResearchDeskMetricCard = {
  key: string;
  label: string;
  value: string;
  detail: string;
  accent: string;
};

export type ResearchDeskEvidenceItem = {
  key: string;
  label: string;
  value: string;
  rail: "primary" | "supporting";
};

export type ResearchDeskAuditRow = {
  time: string;
  kind: string;
  subject: string;
  detail: string;
  source: string;
  score: string;
  status: string;
  owner: string;
};

export type ResearchDeskEndpointItem = {
  key: string;
  label: string;
  statusLabel: string;
  businessDateLabel: string;
  description: string;
  tone: MetricTone;
};

export type ResearchDeskSignalWindow = {
  horizonLabel: string;
  sampleLabel: string;
  winRateLabel: string;
  medianLabel: string;
  longHorizonLabel: string | null;
  guidance: string;
  tone: MetricTone;
} | null;

export type ResearchDeskHistoryRowView = {
  snapshot_as_of_date: string;
  candidate_rank: number;
  data_status: string;
  signalLabel: string;
  return1d: string;
  return5d: string;
  return20d: string;
};

export type ResearchDeskSurfaceMessage = {
  headline: string;
  detail: string;
  tone: MetricTone;
};

export type ResearchDeskTimelineItem = {
  key: string;
  time: string;
  label: string;
  detail: string;
  tone: MetricTone;
};

export type ResearchDeskSummaryView = {
  chartState: ResearchDeskSurfaceState;
  chartMessage: ResearchDeskSurfaceMessage | null;
  chartOption: EChartsOption | null;
  chartFootnote: string;
  quoteValue: string;
  dailyChangeLabel: string;
  dailyChangeTone: MetricTone;
  /** 综合得分（融合分 / 因子分 / 景气分 / 观察分中首个可用值，3 位小数）。 */
  compositeScoreLabel: string;
  /** 综合分缺省时的后端诊断（缺哪些打分因子）；无则 null。 */
  compositeScoreNote: string | null;
  /** 成交量 / 成交额 / 市值 / 流通市值，来自行情富化后的原始字段文本。 */
  marketSnapshotItems: LabeledValue[];
  keyFactsTitle: string;
  keyFacts: LabeledValue[];
  conclusionTitle: string;
  conclusionTone: MetricTone;
  conclusionBadge: string;
  conclusionBody: string;
  conclusionBullets: string[];
  conclusionFootnote: string;
  researchHeadline: string;
  researchSummary: string;
  researchDetail: string;
  evidenceHeadline: string;
  evidenceItems: ResearchDeskEvidenceItem[];
  factorCells: Array<{
    key: string;
    label: string;
    value: string;
    accent: string;
    /** 候选池内截面分位（如 "P90"）；样本不足或无数值时为 null。 */
    percentile: string | null;
  }>;
  timelineItems: ResearchDeskTimelineItem[];
  financeItems: LabeledValue[];
  sourceItems: ResearchDeskEndpointItem[];
};

export type StockAnalysisResearchDeskModel = {
  statusLabel: string;
  /** 首屏门禁的主理由原文，供结论区与硬性门禁复用。 */
  decisionReason: string;
  progressionLabel: string;
  progressionTone: MetricTone;
  selectedSectorLabel: string;
  poolLabel: string;
  selectedCandidateTitle: string;
  selectedCandidateSubtitle: string;
  selectedHeaderItems: LabeledValue[];
  selectedWatchlisted: boolean;
  hardGateItems: Array<{ key: string; text: string; tone: MetricTone }>;
  riskTags: string[];
  riskSummary: string;
  summary: ResearchDeskSummaryView;
  valuationCards: ResearchDeskMetricCard[];
  momentumCards: ResearchDeskMetricCard[];
  financeCards: ResearchDeskMetricCard[];
  signalWindow: ResearchDeskSignalWindow;
  fundamentalsLines: string[];
  invalidationRules: string[];
  eventBoundaryLines: string[];
  rawFieldRows: Array<{ key: string; label: string; value: string }>;
  historyRows: ResearchDeskHistoryRowView[];
  sourceItems: ResearchDeskEndpointItem[];
  displayAuditRows: ResearchDeskAuditRow[];
  auditVisibleCount: number;
  auditTotalCount: number;
};

export type BuildStockAnalysisResearchDeskModelInput = {
  decisionStatusLabel: string;
  decisionReason: string;
  candidateProgressionAllowed: boolean;
  poolTab: ResearchDeskPoolTab;
  selectedSectorLabel: string;
  selectedCandidate: StockCandidateReviewQueueItem | null;
  /** 当前标的池内的全部候选；用于因子格的截面分位，不传则不算分位。 */
  poolCandidates?: StockCandidateReviewQueueItem[];
  signalWindow: ResearchDeskSignalWindow;
  selectedRisk: StockRiskExitRow | null;
  detailQueryState: ResearchDeskQueryState;
  detailPayload: LivermoreStockDetailPayload | null;
  klineQueryState: ResearchDeskQueryState;
  klinePayload: StockKlineAnalysisPayload | null;
  newsQueryState: ResearchDeskQueryState;
  newsPayload: ChoiceNewsEventsPayload | null;
  selectedHistoryRows: LivermoreCandidateHistoryRow[];
  /** Extra provenance rows appended after the derived detail/K-line/news items. */
  endpointItems?: ResearchDeskEndpointItem[];
  noteDraft: string;
  savedNote: string;
  auditRows: ResearchDeskAuditRow[];
  analyticsAsOfDate: string | null;
};

/** 综合得分候选键，按优先级取首个可用值；标的池行与档案头共用同一顺序。 */
export const COMPOSITE_SCORE_RAW_KEYS = ["fusion_score", "factor_score", "cycle_score", "score"] as const;

const FACTOR_SPECS = [
  { key: "composite", label: "综合分", rawKeys: [...COMPOSITE_SCORE_RAW_KEYS], accent: "rose" },
  { key: "valuation", label: "估值", rawKeys: ["pe_ttm", "pe", "pb"], accent: "green" },
  { key: "quality", label: "质量", rawKeys: ["roe", "gross_margin"], accent: "green" },
  { key: "momentum", label: "动量", rawKeys: ["three_month_return", "return_20d", "return_60d", "twelve_month_return", "price_confirm_score"], accent: "blue" },
  { key: "sentiment", label: "情绪", rawKeys: ["abnormal_turnover", "attention_score", "sentiment_score"], accent: "amber" },
  { key: "crowding", label: "拥挤度", rawKeys: ["breakout_extension_norm", "crowding_penalty", "gap_norm"], accent: "rose" },
  { key: "liquidity", label: "流动性", rawKeys: ["daily_amount", "amount_ratio", "liquidity_score"], accent: "green" },
  { key: "volatility", label: "波动率", rawKeys: ["volatility", "amplitude", "volatility_20d"], accent: "amber" },
] as const;

/** FACTOR_SPECS 中以百分比展示的因子格。 */
const PERCENT_FACTOR_SPEC_KEYS = new Set<string>(["quality", "momentum", "volatility"]);

function normalizeText(value: string | null | undefined): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function compactText(value: string | null | undefined, max = 72, fallback = "待补"): string {
  const normalized = normalizeText(value);
  if (!normalized) return fallback;
  return normalized.length > max ? `${normalized.slice(0, max - 1)}…` : normalized;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * 状态文案 → 语义色。只认后端/模型已固定的状态词（阻断/观察/通过 与英文枚举），
 * 研究台各组件统一从这里取色，避免各自维护子串表。
 */
export function statusTone(status: string | null | undefined): MetricTone {
  const normalized = normalizeText(status).toLowerCase();
  if (
    normalized.includes("阻断") ||
    normalized.includes("error") ||
    normalized.includes("negative") ||
    normalized.includes("fail")
  ) {
    return "negative";
  }
  if (
    normalized.includes("观察") ||
    normalized.includes("warning") ||
    normalized.includes("待") ||
    normalized.includes("partial") ||
    normalized.includes("stale") ||
    normalized.includes("degraded")
  ) {
    return "warning";
  }
  if (
    normalized.includes("通过") ||
    normalized.includes("ready") ||
    normalized.includes("positive") ||
    normalized.includes("已就绪")
  ) {
    return "positive";
  }
  return "neutral";
}

function numericTone(value: number | null | undefined): MetricTone {
  if (!isFiniteNumber(value) || value === 0) return "neutral";
  return value > 0 ? "positive" : "negative";
}

function uniqueText(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.map((value) => normalizeText(value)).filter(Boolean))];
}

/** 首个可用原始字段的展示文本（原样，不做单位换算）；缺失返回 EM_DASH。 */
export function candidateRawValue(candidate: StockCandidateReviewQueueItem, keys: string[]): string {
  for (const key of keys) {
    const field = candidate.rawFields.find((item) => item.key === key);
    const normalized = normalizeText(field?.value);
    if (normalized && normalized !== EM_DASH) {
      return normalized;
    }
  }
  return EM_DASH;
}

/**
 * 后端以比率（0-1）返回、展示为百分比时需 ×100 的原始字段键。
 * 与 stockAnalysisWorkbenchQueueModel.evidenceFields 的 ratioPercent 口径一致。
 */
const RATIO_RAW_KEYS = new Set([
  "roe",
  "roe_ttm",
  "gross_margin",
  "dividend_yield",
  "three_month_return",
  "twelve_month_return",
  "volatility",
  "return_20d",
  "return_60d",
  "return_120d",
  "close_to_ma20",
  "advance_ratio",
]);

/** 后端已按百分点（如 3.21 表示 3.21%）返回、展示时直接加 % 的原始字段键。 */
const POINT_PERCENT_KEYS = new Set([
  "pctchange",
  "avg_pctchange",
  "turn",
  "avg_turn",
  "turnover_rate",
  "turnover",
  "amplitude",
  "amplitude_pct",
  "distance_to_breakout_pct",
]);

const PERCENT_TEXT = /^([+-]?\d+(?:\.\d+)?)%$/;

type CandidateNumericField = { key: string; numeric: number };

/**
 * 首个可用的数值字段（后端单位）。优先读 `numeric`；没有 `numeric` 的旧字符串字段只接受
 * 纯数字或 "12.3%" 形式（按键的单位表换算回后端单位），不再剥离 亿/万/x 等单位后缀。
 */
function candidateNumericField(
  candidate: StockCandidateReviewQueueItem,
  keys: string[],
): CandidateNumericField | null {
  for (const key of keys) {
    const field = candidate.rawFields.find((item) => item.key === key);
    if (!field) continue;
    if (isFiniteNumber(field.numeric)) return { key, numeric: field.numeric };
    const text = normalizeText(field.value);
    if (!text || text === EM_DASH) continue;
    const percentMatch = text.match(PERCENT_TEXT);
    if (percentMatch) {
      const points = Number(percentMatch[1]);
      return { key, numeric: RATIO_RAW_KEYS.has(key) ? points / 100 : points };
    }
    // 倍数后缀 x 不改变量纲，可直接去掉；亿/万/元/股/手 会改变量纲，一律不反解析。
    const plain = Number(text.replace(/,/g, "").replace(/[xX×]$/, ""));
    if (Number.isFinite(plain)) return { key, numeric: plain };
  }
  return null;
}

/** 后端单位的原始数值。 */
export function candidateRawNumber(candidate: StockCandidateReviewQueueItem, keys: string[]): number | null {
  return candidateNumericField(candidate, keys)?.numeric ?? null;
}

/** 百分点值：比率键 ×100，其余键视为已是百分点。 */
function candidatePercentPoints(candidate: StockCandidateReviewQueueItem, keys: string[]): number | null {
  const field = candidateNumericField(candidate, keys);
  if (!field) return null;
  return RATIO_RAW_KEYS.has(field.key) ? field.numeric * 100 : field.numeric;
}

/**
 * 百分比展示："12.34%"。比率键 ×100；百分点键或原文已带 % 的直接加 %；
 * 其他数值（如 0-1 评分）按小数展示；没有数值时回退到原始文本（如"待补"）。
 */
export function candidatePercentLabel(
  candidate: StockCandidateReviewQueueItem,
  keys: string[],
  digits = 2,
): string {
  const field = candidateNumericField(candidate, keys);
  if (!field) return candidateRawValue(candidate, keys);
  if (RATIO_RAW_KEYS.has(field.key)) return pctOrDash(field.numeric * 100, digits);
  if (POINT_PERCENT_KEYS.has(field.key) || PERCENT_TEXT.test(candidateRawValue(candidate, [field.key]))) {
    return pctOrDash(field.numeric, digits);
  }
  return fixedOrDash(field.numeric, digits);
}

/**
 * 价格/倍数类数值展示（收盘、PE、PB、评分）：有数值按 `digits` 定点；原文带 % 时保留 %；
 * 无法解析的带量纲文本（如 "6.40亿"）原样返回。不要用于比率字段（用 candidatePercentLabel）。
 */
export function candidateNumberLabel(
  candidate: StockCandidateReviewQueueItem,
  keys: string[],
  digits = 2,
): string {
  const field = candidateNumericField(candidate, keys);
  if (!field) return candidateRawValue(candidate, keys);
  if (PERCENT_TEXT.test(candidateRawValue(candidate, [field.key]))) return pctOrDash(field.numeric, digits);
  return fixedOrDash(field.numeric, digits);
}

/** 研究台左侧标的池的 Tab 定义：唯一文案来源，工具栏视图切换与池内 Tab 都从这里取。 */
export const RESEARCH_DESK_POOL_TABS: ReadonlyArray<readonly [ResearchDeskPoolTab, string]> = [
  ["queue", "精选池"],
  ["watchlist", "自选股"],
  ["history", "历史回溯"],
];

export function poolTabLabel(tab: ResearchDeskPoolTab): string {
  return RESEARCH_DESK_POOL_TABS.find(([key]) => key === tab)?.[1] ?? tab;
}

function candidateDailyChangeValue(candidate: StockCandidateReviewQueueItem): number | null {
  return candidateRawNumber(candidate, ["pctchange"]);
}

/** 当日涨跌幅（pctchange 为百分点）→ "+1.66%"。 */
export function candidateDailyChangeLabel(candidate: StockCandidateReviewQueueItem): string {
  return formatPointSignedPercent(candidateDailyChangeValue(candidate));
}

export function candidateDailyChangeTone(candidate: StockCandidateReviewQueueItem): MetricTone {
  return numericTone(candidateDailyChangeValue(candidate));
}

function latestCandleWithClose(candles: LivermoreStockDetailCandle[]): LivermoreStockDetailCandle | null {
  for (let index = candles.length - 1; index >= 0; index -= 1) {
    if (isFiniteNumber(candles[index]?.close_value)) return candles[index];
  }
  return null;
}

function previousClose(
  candles: LivermoreStockDetailCandle[],
  latest: LivermoreStockDetailCandle | null,
): number | null {
  if (!latest) return null;
  const latestIndex = candles.lastIndexOf(latest);
  for (let index = latestIndex - 1; index >= 0; index -= 1) {
    const close = candles[index]?.close_value;
    if (isFiniteNumber(close)) return close;
  }
  return null;
}

function buildResearchDeskChartOption(
  candles: LivermoreStockDetailCandle[],
  fallbackCandidate: StockCandidateReviewQueueItem,
  klinePayload: StockKlineAnalysisPayload | null,
): EChartsOption | null {
  const candleRows = Array.isArray(candles) ? candles : [];
  const pricePoints = candleRows.flatMap((candle) =>
    isFiniteNumber(candle.close_value)
      ? [{ tradeDate: candle.trade_date, close: candle.close_value }]
      : [],
  );
  if (pricePoints.length >= 2) {
    const closes = pricePoints.map((point) => point.close);
    const movingAverage5 = closes.map((_, index) => {
      const start = Math.max(0, index - 4);
      const window = closes.slice(start, index + 1);
      if (window.length < 3) return null;
      return window.reduce((sum, value) => sum + value, 0) / window.length;
    });
    const movingAverage20 = closes.map((_, index) => {
      const start = Math.max(0, index - 19);
      const window = closes.slice(start, index + 1);
      if (window.length < 5) return null;
      return window.reduce((sum, value) => sum + value, 0) / window.length;
    });
    return {
      backgroundColor: "transparent",
      animation: false,
      textStyle: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
      grid: { left: 42, right: 14, top: 20, bottom: 28 },
      tooltip: {
        trigger: "axis",
        backgroundColor: nocturneTokens.color.panel2,
        borderColor: nocturneTokens.color.lineSoft,
        textStyle: { color: nocturneTokens.color.ink },
      },
      xAxis: {
        type: "category",
        data: pricePoints.map((point) => point.tradeDate.slice(5)),
        boundaryGap: false,
        axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
        axisTick: { show: false },
        axisLabel: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          color: nocturneTokens.color.inkMuted,
          fontSize: 11,
          formatter: (value: number) => value.toFixed(2),
        },
        splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft, type: "dashed" } },
      },
      series: [
        {
          name: "收盘",
          type: "line",
          data: closes,
          showSymbol: false,
          lineStyle: { color: nocturneTokens.color.blue, width: 1.8 },
          itemStyle: { color: nocturneTokens.color.blue },
        },
        {
          name: "MA5",
          type: "line",
          data: movingAverage5,
          connectNulls: true,
          showSymbol: false,
          lineStyle: { color: nocturneTokens.color.amber, width: 1.1 },
          itemStyle: { color: nocturneTokens.color.amber },
        },
        {
          name: "MA20",
          type: "line",
          data: movingAverage20,
          connectNulls: true,
          showSymbol: false,
          lineStyle: { color: nocturneTokens.color.green, width: 1.1 },
          itemStyle: { color: nocturneTokens.color.green },
        },
      ],
    };
  }

  const indicators = klinePayload?.indicators;
  const metrics = [
    { label: "收盘", value: indicators?.latest_close ?? candidateRawNumber(fallbackCandidate, ["close"]) },
    { label: "MA5", value: indicators?.ma5 },
    { label: "MA20", value: indicators?.ma20 ?? candidateRawNumber(fallbackCandidate, ["ma20"]) },
    { label: "MA60", value: indicators?.ma60 ?? candidateRawNumber(fallbackCandidate, ["ma60"]) },
  ].filter((item): item is { label: string; value: number } => isFiniteNumber(item.value));
  if (metrics.length < 2) return null;
  const minValue = Math.min(...metrics.map((item) => item.value));
  const maxValue = Math.max(...metrics.map((item) => item.value));
  const padding = Math.max((maxValue - minValue) * 0.18, maxValue * 0.04, 0.12);
  return {
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
    grid: { left: 42, right: 18, top: 22, bottom: 30 },
    tooltip: {
      trigger: "axis",
      backgroundColor: nocturneTokens.color.panel2,
      borderColor: nocturneTokens.color.lineSoft,
      textStyle: { color: nocturneTokens.color.ink },
    },
    xAxis: {
      type: "category",
      data: metrics.map((item) => item.label),
      axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
      axisTick: { show: false },
      axisLabel: { color: nocturneTokens.color.inkMuted, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      min: Math.max(minValue - padding, 0),
      max: maxValue + padding,
      axisLabel: { formatter: (value: number) => value.toFixed(2) },
      splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft, type: "dashed" } },
    },
    series: [
      {
        type: "line",
        data: metrics.map((item) => item.value),
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { color: nocturneTokens.color.blue, width: 2 },
        itemStyle: { color: nocturneTokens.color.blue },
      },
    ],
  };
}

function stockKlineReasonLabel(value: string): string {
  const key = value.trim();
  const labels: Record<string, string> = {
    bullish_breakout: "放量突破",
    bullish_followthrough: "突破延续",
    ma20_support: "MA20 支撑",
    close_below_ma20: "收于 MA20 下方",
    doji_indecision: "十字星，方向待确认",
    volume_expansion: "量能放大",
    insufficient_volume_confirmation: "量能确认不足",
    negative_20d_return: "近20日转弱",
    positive_20d_return: "近20日转强",
    breakdown_risk: "存在回撤风险",
  };
  return labels[key] ?? key;
}

function stockKlinePatternLabel(value: string | null | undefined): string {
  const key = normalizeText(value);
  const labels: Record<string, string> = {
    breakout: "突破形态",
    pullback: "回踩确认",
    consolidation: "平台整理",
  };
  return labels[key] ?? (key || "形态待补");
}

function firstStockKlinePattern(payload: StockKlineAnalysisPayload | null): string {
  const pattern = payload?.patterns?.[0];
  if (!pattern) return "形态待补";
  return stockKlinePatternLabel(pattern.key);
}

function eventBoundaryTimelineLabel(event: ChoiceNewsEvent): string {
  const label = choiceNewsTopicLabel(event.topic_code, event.content_type, "事件待确认");
  return label === "事件待确认" ? label : `${label}事件`;
}

function candidateHistorySignalLabel(value: string | null | undefined): string {
  const key = value?.trim().toLowerCase().replace(/[\s-]+/g, "_") || "stock_candidate";
  const labels: Record<string, string> = {
    livermore: "趋势突破",
    hybrid_fusion: "融合策略",
    stock_candidate: "趋势突破",
    factor_screen: "多因子",
    theme_breakout: "题材突破",
    mean_reversion: "超跌反弹",
  };
  return labels[key] ?? "策略待确认";
}

function candidateHistoryDataStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    complete: "已成熟",
    partial_halt: "部分停牌",
    pending: "待成熟",
  };
  return labels[status.trim().toLowerCase()] ?? "状态待确认";
}

function buildMetricCards(
  candidate: StockCandidateReviewQueueItem,
  detailPayload: LivermoreStockDetailPayload | null,
  klinePayload: StockKlineAnalysisPayload | null,
): ResearchDeskMetricCard[] {
  const detailFactor = detailPayload?.factor;
  return [
    {
      key: "composite",
      label: "综合分",
      value: formatFixed(candidateRawNumber(candidate, [...COMPOSITE_SCORE_RAW_KEYS]), 3),
      accent: "rose",
      detail: candidate.sourcePoolLabel,
    },
    {
      key: "valuation",
      label: "估值",
      value: `PE ${formatFixed(detailFactor?.pe ?? candidateRawNumber(candidate, ["pe_ttm", "pe"]), 2)}`,
      accent: "green",
      detail: `PB ${formatFixed(detailFactor?.pb ?? candidateRawNumber(candidate, ["pb", "pb_lf"]), 2)}`,
    },
    {
      key: "quality",
      label: "质量",
      // 个股详情 factor.roe 与候选 roe 都是比率（0-1），统一 ×100 后展示，避免与详情抽屉口径不一致。
      value: `ROE ${
        detailFactor?.roe != null
          ? formatRatioPercent(detailFactor.roe, 2)
          : pctOrDash(candidatePercentPoints(candidate, ["roe", "roe_ttm"]), 2)
      }`,
      accent: "blue",
      detail: `毛利 ${candidatePercentLabel(candidate, ["gross_margin", "gross_margin_pct"])}`,
    },
    {
      key: "momentum",
      label: "动量",
      value: formatRatioSignedPercent(
        klinePayload?.indicators.return_20d ?? candidateRawNumber(candidate, ["return_20d"]),
      ),
      accent: "cyan",
      detail: `5日 ${formatRatioSignedPercent(klinePayload?.indicators.return_5d)}`,
    },
    {
      key: "crowding",
      label: "拥挤度",
      value: formatFixed(candidateRawNumber(candidate, ["crowding_penalty"]), 3),
      accent: "amber",
      detail: `形态 ${firstStockKlinePattern(klinePayload)}`,
    },
    {
      key: "liquidity",
      label: "流动性",
      value: formatMultiple(
        klinePayload?.indicators.volume_ratio_20d ?? candidateRawNumber(candidate, ["amount_ratio"]),
      ),
      accent: "slate",
      detail: candidate.dailyAmountLabel ?? `换手 ${candidatePercentLabel(candidate, ["turn"])}`,
    },
  ];
}

/**
 * 因子格：值取候选的真实原始字段（不是指标卡的派生值），指标卡只贡献标签与色调；
 * 质量/动量/波动率按单位表换算成百分比，个股详情返回的 PE/ROE 优先于队列快照。
 */
function buildFactorCells(
  candidate: StockCandidateReviewQueueItem,
  detailPayload: LivermoreStockDetailPayload | null,
  metricCards: ResearchDeskMetricCard[],
  poolCandidates: StockCandidateReviewQueueItem[] | undefined,
): StockAnalysisResearchDeskModel["summary"]["factorCells"] {
  const factor = detailPayload?.factor;
  return FACTOR_SPECS.map((spec) => {
    const metric = metricCards.find((item) => item.key === spec.key);
    const rawKeys = [...spec.rawKeys];
    const rawValue = candidateRawValue(candidate, rawKeys);
    let value = PERCENT_FACTOR_SPEC_KEYS.has(spec.key) ? candidatePercentLabel(candidate, rawKeys) : rawValue;
    if (spec.key === "composite") {
      // 综合分与档案头、标的池列保持同一精度（3 位）。
      value = candidateNumberLabel(candidate, rawKeys, 3);
    }
    if (spec.key === "valuation" && factor?.pe != null) {
      value = formatFixed(factor.pe, 2);
    }
    if (spec.key === "quality" && factor?.roe != null) {
      value = formatRatioPercent(factor.roe, 2);
    }
    return {
      key: spec.key,
      label: metric?.label ?? spec.label,
      value,
      accent: metric?.accent ?? spec.accent,
      percentile:
        poolCandidates && rawValue !== EM_DASH ? crossSectionPercentile(poolCandidates, candidate, rawKeys) : null,
    };
  });
}

function buildFinanceItems(
  candidate: StockCandidateReviewQueueItem,
  detailPayload: LivermoreStockDetailPayload | null,
): LabeledValue[] {
  const factor = detailPayload?.factor;
  return [
    {
      key: "pe",
      label: "市盈率(TTM)",
      value: factor?.pe != null ? formatFixed(factor.pe, 2) : candidateNumberLabel(candidate, ["pe_ttm", "pe"], 2),
    },
    {
      key: "pb",
      label: "市净率(LF)",
      value: factor?.pb != null ? formatFixed(factor.pb, 2) : candidateNumberLabel(candidate, ["pb", "pb_lf"], 2),
    },
    {
      key: "roe",
      label: "ROE",
      value:
        factor?.roe != null
          ? formatRatioPercent(factor.roe, 2)
          : candidatePercentLabel(candidate, ["roe", "roe_ttm"]),
    },
    {
      key: "gross-margin",
      label: "毛利率",
      value: candidatePercentLabel(candidate, ["gross_margin", "gross_margin_pct"]),
    },
    {
      key: "dividend-yield",
      label: "股息率(TTM)",
      value:
        factor?.dividend_yield != null
          ? formatRatioPercent(factor.dividend_yield, 2)
          : candidatePercentLabel(candidate, ["dividend_yield"]),
    },
    {
      key: "ps",
      label: "市销率",
      value: candidateNumberLabel(candidate, ["ps", "ps_ratio"], 2),
    },
  ];
}

/** 档案头的市场快照：成交量 / 成交额 / 市值 / 流通市值，均为带量纲的原始文本，直接透传。 */
function buildMarketSnapshotItems(candidate: StockCandidateReviewQueueItem): LabeledValue[] {
  return [
    { key: "volume", label: "成交量", value: candidateRawValue(candidate, ["volume", "amount_volume"]) },
    {
      key: "amount",
      label: "成交额",
      value: candidateRawValue(candidate, ["amount", "turnover_amount", "daily_amount"]),
    },
    { key: "market-cap", label: "市值", value: candidateRawValue(candidate, ["market_cap", "total_mv"]) },
    {
      key: "circulating-market-cap",
      label: "流通市值",
      value: candidateRawValue(candidate, ["circulating_market_cap", "circ_mv"]),
    },
  ];
}

/** 综合分缺省时透出后端诊断（缺哪些打分因子），不猜不补。 */
function buildCompositeScoreNote(candidate: StockCandidateReviewQueueItem, compositeScoreLabel: string): string | null {
  if (compositeScoreLabel !== EM_DASH) return null;
  const missingInputs = candidateRawValue(candidate, ["factor_missing_inputs"]);
  return missingInputs === EM_DASH ? null : `缺 ${missingInputs}，未参与因子打分`;
}

/**
 * 截面分位：在候选池内对同一原始字段（后端单位的 numeric）做 <= 计数占比；
 * 样本不足（<5）或值缺失时返回 null。
 */
function crossSectionPercentile(
  pool: StockCandidateReviewQueueItem[],
  selected: StockCandidateReviewQueueItem,
  rawKeys: string[],
): string | null {
  const selectedValue = candidateRawNumber(selected, rawKeys);
  if (selectedValue == null) return null;
  const samples = pool
    .map((candidate) => candidateRawNumber(candidate, rawKeys))
    .filter((value): value is number => value != null);
  if (samples.length < 5) return null;
  const belowOrEqual = samples.filter((value) => value <= selectedValue).length;
  return `P${Math.round((belowOrEqual / samples.length) * 100)}`;
}

function finiteCandleValue(value: number | null | undefined): number | null {
  return isFiniteNumber(value) ? value : null;
}

/**
 * 用个股详情与 K 线分析的真实行情字段丰富选中候选的 rawFields。
 * 只注入接口实际返回的字段；新增键覆盖同名旧键（个股级数据比队列快照更细）。
 */
export function enrichResearchDeskCandidateWithQuotes(
  candidate: StockCandidateReviewQueueItem | null,
  detailPayload: LivermoreStockDetailPayload | null,
  klinePayload: StockKlineAnalysisPayload | null,
): StockCandidateReviewQueueItem | null {
  if (!candidate) return null;
  const extra: StockCandidateReviewQueueItem["rawFields"] = [];
  // 展示字符串保持既有口径；numeric 存后端原值（点/比率/元/股），供下游按单位表换算。
  const push = (key: string, label: string, value: string | null, raw?: number | null) => {
    if (value == null || value === EM_DASH) return;
    extra.push({ key, label, value, numeric: isFiniteNumber(raw) ? raw : null });
  };
  const percentPoints = (value: number | null | undefined): string | null =>
    isFiniteNumber(value) ? `${value.toFixed(2)}%` : null;

  const latestKlineCandle = klinePayload?.latest_candle ?? null;
  const indicators = klinePayload?.indicators ?? null;
  const turn = latestKlineCandle?.turn ?? indicators?.latest_turnover ?? null;
  const amplitude = latestKlineCandle?.amplitude ?? indicators?.latest_amplitude ?? null;
  push("pctchange", "涨跌幅", formatPointSignedPercent(latestKlineCandle?.pctchange), latestKlineCandle?.pctchange);
  push("turn", "换手率", percentPoints(turn), turn);
  push("amplitude", "振幅", percentPoints(amplitude), amplitude);
  push("return_5d", "近5日收益", formatRatioSignedPercent(indicators?.return_5d), indicators?.return_5d);
  push("return_20d", "近20日收益", formatRatioSignedPercent(indicators?.return_20d), indicators?.return_20d);
  push(
    "volume_ratio_20d",
    "量比(20日)",
    formatMultiple(indicators?.volume_ratio_20d),
    indicators?.volume_ratio_20d,
  );

  const candles = detailPayload?.state === "ok" ? (detailPayload.candles ?? []) : [];
  const latestCandle = latestCandleWithClose(candles) ?? candles.at(-1) ?? null;
  const volume = finiteCandleValue(latestCandle?.volume);
  const amount = finiteCandleValue(latestCandle?.amount);
  push("volume", "成交量", volume != null ? `${(volume / 10_000).toFixed(2)}万股` : null, volume);
  push("amount", "成交额", amount != null ? `${(amount / 100_000_000).toFixed(2)}亿` : null, amount);
  // 市值单位：后端统一为元（Tushare daily_basic 万元 × 10000 入库），此处转亿展示。
  const totalMv = finiteCandleValue(detailPayload?.factor?.total_mv);
  const circMv = finiteCandleValue(detailPayload?.factor?.circ_mv);
  push("market_cap", "总市值", totalMv != null ? `${(totalMv / 100_000_000).toFixed(2)}亿` : null, totalMv);
  push(
    "circulating_market_cap",
    "流通市值",
    circMv != null ? `${(circMv / 100_000_000).toFixed(2)}亿` : null,
    circMv,
  );
  const highs = candles.map((candle) => finiteCandleValue(candle.high_value)).filter((v): v is number => v != null);
  const lows = candles.map((candle) => finiteCandleValue(candle.low_value)).filter((v): v is number => v != null);
  if (highs.length >= 5) push("high_60d", "近60日最高", formatFixed(Math.max(...highs), 2), Math.max(...highs));
  if (lows.length >= 5) push("low_60d", "近60日最低", formatFixed(Math.min(...lows), 2), Math.min(...lows));

  if (extra.length === 0) return candidate;
  const extraKeys = new Set(extra.map((item) => item.key));
  return {
    ...candidate,
    rawFields: [...extra, ...candidate.rawFields.filter((field) => !extraKeys.has(field.key))],
  };
}

function buildResearchSummary(
  candidate: StockCandidateReviewQueueItem,
  detailState: ResearchDeskSurfaceState,
  klinePayload: StockKlineAnalysisPayload | null,
): { headline: string; summary: string; detail: string } {
  const klineLabel = normalizeText(klinePayload?.observation_signal.label) || "K 线待确认";
  const klineReason = compactText(klinePayload?.observation_signal.reasons?.[0], 72, "价格与量能仍需复核");
  if (detailState === "mismatch") {
    return {
      headline: "观察日错配",
      summary: "个股详情日期与当前观察日不一致，价格与估值仅作旁证，不进入主结论。",
      detail: "先统一观察日，再继续核验价格、估值与事件证据。",
    };
  }
  return {
    headline: compactText(candidate.headline, 80, "研究摘要待补"),
    summary: compactText(candidate.reviewFocus, 120, "当前候选尚未形成可读的复核摘要。"),
    detail: `${klineLabel} · ${klineReason}`,
  };
}

function buildConclusion(
  candidate: StockCandidateReviewQueueItem,
  decisionStatusLabel: string,
  decisionReason: string,
  candidateProgressionAllowed: boolean,
  detailState: ResearchDeskSurfaceState,
  selectedRisk: StockRiskExitRow | null,
  klinePayload: StockKlineAnalysisPayload | null,
): Pick<ResearchDeskSummaryView, "conclusionTitle" | "conclusionTone" | "conclusionBadge" | "conclusionBody" | "conclusionBullets" | "conclusionFootnote"> {
  const mismatchLine =
    detailState === "mismatch"
      ? "个股详情观察日与主页面不一致，本轮只保留队列与边界结论。"
      : null;
  const riskLine =
    selectedRisk?.status === "triggered"
      ? `退出位已触发：${selectedRisk.reason}`
      : selectedRisk
        ? `退出位观察中：${selectedRisk.distanceToExitPct}`
        : null;
  const klineLine = normalizeText(klinePayload?.observation_signal.label);
  const bullets = uniqueText([
    mismatchLine,
    riskLine,
    klineLine ? `K线观察：${klineLine}` : null,
    ...candidate.invalidationRules.slice(0, 3),
  ]).slice(0, 4);
  return {
    conclusionTitle: "综合结论",
    conclusionTone:
      detailState === "mismatch"
        ? "warning"
        : selectedRisk?.status === "triggered"
          ? "negative"
          : candidateProgressionAllowed
            ? "positive"
            : statusTone(decisionStatusLabel),
    conclusionBadge: selectedRisk?.status === "triggered" ? "阻断" : decisionStatusLabel,
    conclusionBody:
      detailState === "mismatch"
        ? "详情日期错配，当前只保留观察结论，不追加价格确认。"
        : compactText(candidate.reviewFocus, 120, "当前没有可显示的复核主结论。"),
    conclusionBullets: bullets,
    conclusionFootnote: compactText(decisionReason, 96, "观察边界待补"),
  };
}

function buildTimelineItems(
  candidate: StockCandidateReviewQueueItem,
  newsQueryState: ResearchDeskQueryState,
  newsPayload: ChoiceNewsEventsPayload | null,
  selectedHistoryRows: LivermoreCandidateHistoryRow[],
  boundaryItems: string[],
): ResearchDeskTimelineItem[] {
  const newsItems = (newsPayload?.events ?? []).slice(0, 3).map((event) => ({
    key: `news:${event.event_key}`,
    time: formatChoiceNewsReceivedAt(event.received_at),
    label: eventBoundaryTimelineLabel(event),
    detail: truncateChoiceNewsText(event.payload_text, 72),
    tone: "neutral" as const,
  }));
  const historyItems = selectedHistoryRows.slice(0, 3).map((row) => ({
    key: `history:${row.snapshot_as_of_date}:${row.candidate_rank}`,
    time: row.snapshot_as_of_date || EM_DASH,
    label: candidateHistorySignalLabel(row.signal_kind),
    detail: `T+5 ${formatRatioSignedPercent(row.return_5d)} · T+20 ${formatRatioSignedPercent(row.return_20d)}`,
    tone: statusTone(candidateHistoryDataStatusLabel(row.data_status)),
  }));
  const fallbackItems = boundaryItems.slice(0, 3).map((item, index) => ({
    key: `boundary:${index}`,
    time: EM_DASH,
    label: "观察边界",
    detail: compactText(item, 72),
    tone: "warning" as const,
  }));
  if (newsItems.length > 0) return [...newsItems, ...historyItems].slice(0, 5);
  if (newsQueryState === "success" && historyItems.length > 0) return historyItems;
  return fallbackItems;
}

function buildSourceItems(
  endpointItems: ResearchDeskEndpointItem[],
  detailQueryState: ResearchDeskQueryState,
  detailPayload: LivermoreStockDetailPayload | null,
  klineQueryState: ResearchDeskQueryState,
  klinePayload: StockKlineAnalysisPayload | null,
  newsQueryState: ResearchDeskQueryState,
  newsPayload: ChoiceNewsEventsPayload | null,
): ResearchDeskEndpointItem[] {
  const derived: ResearchDeskEndpointItem[] = [
    {
      key: "selected-stock-detail",
      label: "个股详情",
      statusLabel:
        detailQueryState === "loading"
          ? "读取中"
          : detailQueryState === "error"
            ? "失败"
            : detailPayload?.state === "missing"
              ? "缺失"
              : detailPayload?.state === "ok"
                ? "已就绪"
                : "待触发",
      businessDateLabel: textOrDash(detailPayload?.as_of_date),
      description:
        detailQueryState === "error"
          ? "个股详情读取失败，当前只保留候选侧证据。"
          : detailPayload?.state === "missing"
            ? "个股详情当前无有效记录。"
            : "收盘、估值与均线来自个股详情。",
      tone:
        detailQueryState === "error"
          ? "negative"
          : detailPayload?.state === "missing"
            ? "warning"
            : detailPayload?.state === "ok"
              ? "positive"
              : "neutral",
    },
    {
      key: "selected-kline",
      label: "K线观察",
      statusLabel:
        klineQueryState === "loading"
          ? "读取中"
          : klineQueryState === "error"
            ? "失败"
            : klinePayload?.state === "ok"
              ? "已就绪"
              : klinePayload?.state === "insufficient"
                ? "样本不足"
                : "待确认",
      businessDateLabel: textOrDash(klinePayload?.as_of_date),
      description:
        klineQueryState === "error"
          ? "K 线观察暂不可用，保留原始价格图。"
          : klinePayload?.state === "ok"
            ? `观察信号 ${normalizeText(klinePayload.observation_signal.label) || "待确认"}`
            : "K 线观察当前未形成稳定结论。",
      tone:
        klineQueryState === "error"
          ? "negative"
          : klinePayload?.state === "ok"
            ? "positive"
            : "warning",
    },
    {
      key: "selected-news",
      label: "市场事件",
      statusLabel:
        newsQueryState === "loading"
          ? "读取中"
          : newsQueryState === "error"
            ? "失败"
            : newsQueryState === "success"
              ? (newsPayload?.events?.length ?? 0) > 0
                ? "已就绪"
                : "空结果"
              : "待触发",
      businessDateLabel: choiceNewsDataDateLabel(
        newsPayload?.as_of_date,
        newsPayload?.excluded_future_rows,
      ),
      description:
        newsQueryState === "error"
          ? "事件边界读取失败，仍需人工确认。"
          : newsQueryState === "success"
            ? (newsPayload?.events?.length ?? 0) > 0
              ? `已返回 ${(newsPayload?.events?.length ?? 0).toString()} 条事件`
              : "当前没有命中的公告/新闻事件。"
            : "等待观察日确认后读取市场事件。",
      tone:
        newsQueryState === "error"
          ? "negative"
          : newsQueryState === "success"
            ? (newsPayload?.events?.length ?? 0) > 0
              ? "positive"
              : "warning"
            : "neutral",
    },
  ];
  return [...derived, ...endpointItems].slice(0, 6);
}

function buildAuditRows(
  candidate: StockCandidateReviewQueueItem,
  analyticsAsOfDate: string | null,
  summary: ResearchDeskSummaryView,
  selectedHistoryRows: LivermoreCandidateHistoryRow[],
  selectedRisk: StockRiskExitRow | null,
  newsPayload: ChoiceNewsEventsPayload | null,
  auditRows: ResearchDeskAuditRow[],
): ResearchDeskAuditRow[] {
  const sourceRows = summary.sourceItems.slice(0, 2).map((item) => ({
    time: item.businessDateLabel,
    kind: "接口状态",
    subject: `${candidate.stockName} ${candidate.stockCode}`,
    detail: item.description,
    source: item.label,
    score: item.statusLabel,
    status: item.tone === "negative" ? "阻断" : item.tone === "warning" ? "观察" : "通过",
    owner: "系统",
  }));
  const historyRows = selectedHistoryRows.slice(0, 2).map((row) => ({
    time: row.snapshot_as_of_date || EM_DASH,
    kind: "历史验证",
    subject: `${row.stock_name ?? row.stock_code} ${row.stock_code}`,
    detail: `${candidateHistorySignalLabel(row.signal_kind)} · T+5 ${formatRatioSignedPercent(row.return_5d)}`,
    source: "候选历史",
    score: `Rank ${row.candidate_rank}`,
    status: candidateHistoryDataStatusLabel(row.data_status),
    owner: "策略回放",
  }));
  const newsRows = (newsPayload?.events ?? []).slice(0, 3).map((event) => ({
    time: formatChoiceNewsReceivedAt(event.received_at),
    kind: "事件更新",
    subject: `${candidate.stockName} ${candidate.stockCode}`,
    detail: truncateChoiceNewsText(event.payload_text, 96),
    source: `Choice ${eventBoundaryTimelineLabel(event)}`,
    score: event.topic_code || EM_DASH,
    status: event.error_code === 0 ? "通过" : "观察",
    owner: "事件库",
  }));
  return [
    {
      time: analyticsAsOfDate ?? EM_DASH,
      kind: "候选选择",
      subject: `${candidate.stockName} ${candidate.stockCode}`,
      detail: `${compactText(candidate.headline, 72)}；${compactText(candidate.reviewFocus, 96)}`,
      source: candidate.sourcePoolLabel,
      score: summary.factorCells[0]?.value ?? EM_DASH,
      status: selectedRisk?.status === "triggered" ? "阻断" : "通过",
      owner: "研究席",
    },
    ...sourceRows,
    ...newsRows,
    ...historyRows,
    ...auditRows,
  ].slice(0, 10);
}

export function buildStockAnalysisResearchDeskModel(
  input: BuildStockAnalysisResearchDeskModelInput,
): StockAnalysisResearchDeskModel {
  const {
    analyticsAsOfDate,
    auditRows,
    candidateProgressionAllowed,
    decisionReason,
    decisionStatusLabel,
    detailPayload,
    detailQueryState,
    endpointItems = [],
    klinePayload,
    klineQueryState,
    newsPayload,
    newsQueryState,
    noteDraft,
    poolCandidates,
    poolTab,
    savedNote,
    selectedCandidate,
    selectedHistoryRows,
    selectedRisk,
    selectedSectorLabel,
    signalWindow,
  } = input;

  if (!selectedCandidate) {
    const emptySummary: ResearchDeskSummaryView = {
      chartState: "missing",
      chartMessage: {
        headline: "未选择标的",
        detail: "从左侧候选池选择一只股票后，这里才会形成研究档案。",
        tone: "warning",
      },
      chartOption: null,
      chartFootnote: "等待候选选择。",
      quoteValue: EM_DASH,
      dailyChangeLabel: EM_DASH,
      dailyChangeTone: "neutral",
      compositeScoreLabel: EM_DASH,
      compositeScoreNote: null,
      marketSnapshotItems: [],
      keyFactsTitle: "关键数据",
      keyFacts: [],
      conclusionTitle: "综合结论",
      conclusionTone: "warning",
      conclusionBadge: "待选择",
      conclusionBody: "当前没有选中的标的。",
      conclusionBullets: [],
      conclusionFootnote: compactText(decisionReason, 96, "观察边界待补"),
      researchHeadline: "研究观点（摘要）",
      researchSummary: "选择标的后显示。",
      researchDetail: "价格、估值、K线与事件证据会在同一观察日下展开。",
      evidenceHeadline: "最新信号与关键证据",
      evidenceItems: [],
      factorCells: FACTOR_SPECS.map((spec) => ({
        key: spec.key,
        label: spec.label,
        value: EM_DASH,
        accent: spec.accent,
        percentile: null,
      })),
      timelineItems: [],
      financeItems: [],
      sourceItems: endpointItems.slice(0, 6),
    };
    return {
      statusLabel: decisionStatusLabel,
      decisionReason,
      progressionLabel: candidateProgressionAllowed ? "允许复核" : "只读观察",
      progressionTone: candidateProgressionAllowed ? "positive" : "warning",
      selectedSectorLabel,
      poolLabel: poolTabLabel(poolTab),
      selectedCandidateTitle: "未选择标的",
      selectedCandidateSubtitle: "从左侧候选池选择一个标的",
      selectedHeaderItems: [],
      selectedWatchlisted: false,
      hardGateItems: uniqueText([decisionReason]).slice(0, 4).map((text, index) => ({
        key: `gate-${index}`,
        text,
        tone: statusTone(text),
      })),
      riskTags: [candidateProgressionAllowed ? "允许复核" : "只读观察"],
      riskSummary: "当前没有独立标的，右侧仅保留总门控。",
      summary: emptySummary,
      valuationCards: [],
      momentumCards: [],
      financeCards: [],
      signalWindow: null,
      fundamentalsLines: [],
      invalidationRules: [],
      eventBoundaryLines: [],
      rawFieldRows: [],
      historyRows: [],
      sourceItems: emptySummary.sourceItems,
      displayAuditRows: auditRows.slice(0, 6),
      auditVisibleCount: auditRows.slice(0, 6).length,
      auditTotalCount: auditRows.length,
    };
  }

  const latestCandle = latestCandleWithClose(detailPayload?.candles ?? []);
  const previousCloseValue = previousClose(detailPayload?.candles ?? [], latestCandle);
  const latestCloseValue = latestCandle?.close_value ?? detailPayload?.candles?.at(-1)?.close_value ?? null;
  const chartReturnValue =
    isFiniteNumber(latestCloseValue) && isFiniteNumber(previousCloseValue) && previousCloseValue !== 0
      ? latestCloseValue / previousCloseValue - 1
      : null;
  const detailDate = normalizeText(detailPayload?.as_of_date);
  const pageDate = normalizeText(analyticsAsOfDate);
  const detailMismatch = Boolean(detailDate && pageDate && detailDate !== pageDate);
  const detailState: ResearchDeskSurfaceState =
    detailQueryState === "loading"
      ? "loading"
      : detailQueryState === "error"
        ? "error"
        : detailPayload?.state === "missing"
          ? "missing"
          : detailMismatch
            ? "mismatch"
            : "ready";
  const chartOption = buildResearchDeskChartOption(
    detailPayload?.candles ?? [],
    selectedCandidate,
    klinePayload,
  );
  const chartMessage =
    detailState === "loading"
      ? {
          headline: "价格序列读取中",
          detail: "正在补齐个股详情，不阻塞候选和结论骨架。",
          tone: "warning" as const,
        }
      : detailState === "error"
        ? {
            headline: "价格序列暂不可用",
            detail: "个股详情读取失败，当前只保留候选侧证据。",
            tone: "negative" as const,
          }
        : detailState === "missing"
          ? {
              headline: "价格序列待补",
              detail: "当前个股详情未返回足够行情字段，保持显式空状态。",
              tone: "warning" as const,
            }
          : detailState === "mismatch"
            ? {
                headline: "观察日不一致",
                detail: `主页面 ${pageDate || "待确认"}，个股详情 ${detailDate || "待确认"}，价格只作旁证。`,
                tone: "warning" as const,
              }
            : null;
  const metricCards = buildMetricCards(selectedCandidate, detailPayload, klinePayload);
  const factorCells = buildFactorCells(selectedCandidate, detailPayload, metricCards, poolCandidates);
  const financeItems = buildFinanceItems(selectedCandidate, detailPayload);
  const compositeScoreLabel = candidateNumberLabel(selectedCandidate, [...COMPOSITE_SCORE_RAW_KEYS], 3);
  const primaryEvidenceItems = (selectedCandidate.primaryEvidence ?? []).map((item) => ({
    ...item,
    rail: "primary" as const,
  }));
  const supportingEvidenceItems = (selectedCandidate.supportingEvidence ?? []).map((item) => ({
    ...item,
    rail: "supporting" as const,
  }));
  const evidenceItems = [...primaryEvidenceItems, ...supportingEvidenceItems].slice(0, 6);
  const boundaryItems = uniqueText(selectedCandidate.boundaryEvidence).slice(0, 5);
  const sourceItems = buildSourceItems(
    endpointItems,
    detailQueryState,
    detailPayload,
    klineQueryState,
    klinePayload,
    newsQueryState,
    newsPayload,
  );
  const researchSummary = buildResearchSummary(selectedCandidate, detailState, klinePayload);
  const conclusion = buildConclusion(
    selectedCandidate,
    decisionStatusLabel,
    decisionReason,
    candidateProgressionAllowed,
    detailState,
    selectedRisk,
    klinePayload,
  );
  const keyFacts: LabeledValue[] = [
    {
      key: "turnover",
      label: "换手率",
      value: candidatePercentLabel(selectedCandidate, ["turn", "turnover_rate", "turnover"]),
    },
    {
      key: "amplitude",
      label: "振幅",
      value: candidatePercentLabel(selectedCandidate, ["amplitude", "amplitude_pct"]),
    },
    {
      key: "pe",
      label: "市盈率(TTM)",
      value:
        detailPayload?.factor.pe != null
          ? formatFixed(detailPayload.factor.pe, 2)
          : candidateNumberLabel(selectedCandidate, ["pe_ttm", "pe", "pe_ratio"], 2),
    },
    {
      key: "pb",
      label: "市净率(LF)",
      value:
        detailPayload?.factor.pb != null
          ? formatFixed(detailPayload.factor.pb, 2)
          : candidateNumberLabel(selectedCandidate, ["pb", "pb_lf", "pb_ratio"], 2),
    },
    {
      key: "roe",
      label: "ROE",
      value:
        detailPayload?.factor.roe != null
          ? formatRatioPercent(detailPayload.factor.roe, 2)
          : candidatePercentLabel(selectedCandidate, ["roe", "roe_ttm"]),
    },
    {
      key: "gross-margin",
      label: "毛利率",
      value: candidatePercentLabel(selectedCandidate, ["gross_margin", "gross_margin_pct"]),
    },
    {
      key: "high-60d",
      label: "近60日最高",
      value: candidateNumberLabel(selectedCandidate, ["high_60d"], 2),
    },
    {
      key: "low-60d",
      label: "近60日最低",
      value: candidateNumberLabel(selectedCandidate, ["low_60d"], 2),
    },
  ];
  const headerItems: LabeledValue[] = [
    { key: "source", label: "来源池", value: selectedCandidate.sourcePoolLabel },
    { key: "observation", label: "观察位", value: selectedCandidate.distanceToBreakoutPct },
    {
      key: "signal",
      label: "K线观察",
      value: normalizeText(klinePayload?.observation_signal.label) || "待确认",
    },
    {
      key: "risk",
      label: "风险状态",
      value: selectedRisk == null ? "未触发" : selectedRisk.status === "triggered" ? "阻断" : "观察",
    },
    {
      key: "detail-date",
      label: "详情日期",
      value: detailDate || EM_DASH,
    },
    {
      key: "event-date",
      label: "事件日期",
      value: choiceNewsDataDateLabel(newsPayload?.as_of_date, newsPayload?.excluded_future_rows),
    },
  ];
  const riskTags = uniqueText([
    candidateProgressionAllowed ? "允许复核" : "只读观察",
    selectedRisk?.status === "triggered" ? "风险阻断" : selectedRisk ? "风险观察" : null,
    selectedRisk ? `退出价 ${selectedRisk.exitWatchPrice}` : null,
    selectedRisk ? `距退出 ${selectedRisk.distanceToExitPct}` : null,
    detailState === "mismatch" ? "日期错配" : null,
  ]).slice(0, 5);
  const hardGateItems = uniqueText([
    decisionReason,
    ...boundaryItems,
    selectedRisk?.reason,
    detailState === "mismatch" ? "价格与估值详情日期错配，当前不进入主结论。" : null,
    ...((klinePayload?.observation_signal.risks ?? []).slice(0, 2).map(stockKlineReasonLabel)),
  ])
    .slice(0, 4)
    .map((text, index) => ({
      key: `gate-${index}`,
      text,
      tone: statusTone(text),
    }));
  const summary: ResearchDeskSummaryView = {
    chartState: detailState,
    chartMessage,
    chartOption,
    chartFootnote:
      detailState === "ready"
        ? "来自个股详情日频收盘与均线。"
        : detailState === "mismatch"
          ? "日期错配时只展示旁证，不并入主结论。"
          : "来自个股详情日频收盘；失败时保持显式空状态。",
    quoteValue:
      detailPayload?.state === "ok" && isFiniteNumber(latestCloseValue)
        ? formatFixed(latestCloseValue, 2)
        : candidateNumberLabel(selectedCandidate, ["close", "latest_close"], 2),
    dailyChangeLabel:
      detailPayload?.state === "ok" && chartReturnValue != null
        ? formatRatioSignedPercent(chartReturnValue)
        : candidateDailyChangeLabel(selectedCandidate),
    dailyChangeTone: detailPayload?.state === "ok" ? numericTone(chartReturnValue) : numericTone(candidateDailyChangeValue(selectedCandidate)),
    compositeScoreLabel,
    compositeScoreNote: buildCompositeScoreNote(selectedCandidate, compositeScoreLabel),
    marketSnapshotItems: buildMarketSnapshotItems(selectedCandidate),
    keyFactsTitle: `关键数据${detailDate ? `（${detailDate}）` : ""}`,
    keyFacts,
    ...conclusion,
    researchHeadline: "研究观点（摘要）",
    researchSummary: researchSummary.summary,
    researchDetail: researchSummary.detail,
    evidenceHeadline: "最新信号与关键证据",
    evidenceItems,
    factorCells,
    timelineItems: buildTimelineItems(
      selectedCandidate,
      newsQueryState,
      newsPayload,
      selectedHistoryRows,
      boundaryItems,
    ),
    financeItems,
    sourceItems,
  };
  const historyRows = selectedHistoryRows.slice(0, 6).map((row) => ({
    snapshot_as_of_date: row.snapshot_as_of_date,
    candidate_rank: row.candidate_rank,
    data_status: candidateHistoryDataStatusLabel(row.data_status),
    signalLabel: candidateHistorySignalLabel(row.signal_kind),
    return1d: formatRatioSignedPercent(row.return_1d),
    return5d: formatRatioSignedPercent(row.return_5d),
    return20d: formatRatioSignedPercent(row.return_20d),
  }));
  const displayAuditRows = buildAuditRows(
    selectedCandidate,
    analyticsAsOfDate,
    summary,
    selectedHistoryRows,
    selectedRisk,
    newsPayload,
    auditRows,
  );
  return {
    statusLabel: decisionStatusLabel,
    decisionReason,
    progressionLabel: candidateProgressionAllowed ? "允许复核" : "只读观察",
    progressionTone: candidateProgressionAllowed ? "positive" : "warning",
    selectedSectorLabel,
    poolLabel: poolTabLabel(poolTab),
    selectedCandidateTitle: `${selectedCandidate.stockName} ${selectedCandidate.stockCode}`,
    selectedCandidateSubtitle: `${selectedCandidate.sectorName} · ${selectedCandidate.sourcePoolLabel}`,
    selectedHeaderItems: headerItems,
    selectedWatchlisted:
      noteDraft.includes(selectedCandidate.stockCode) || savedNote.includes(selectedCandidate.stockCode),
    hardGateItems,
    riskTags,
    riskSummary:
      selectedRisk?.reason ??
      (detailState === "mismatch"
        ? "详情日期与观察日不一致，当前不推进价格确认。"
        : "该标的当前没有独立风险退出记录，沿用总门控与边界提示。"),
    summary,
    valuationCards: metricCards.slice(0, 4),
    momentumCards: metricCards,
    financeCards: metricCards,
    signalWindow,
    fundamentalsLines: [
      compactText(selectedCandidate.reviewFocus, 120, "研究观点待补"),
      compactText(selectedCandidate.patternNote, 96, "形态说明待补"),
      compactText(researchSummary.detail, 96, "K 线与事件证据待补"),
    ],
    invalidationRules: selectedCandidate.invalidationRules.slice(0, 4),
    eventBoundaryLines: uniqueText([
      ...boundaryItems,
      ...(newsPayload?.events ?? []).slice(0, 2).map(
        (event) => `${eventBoundaryTimelineLabel(event)}：${truncateChoiceNewsText(event.payload_text, 48)}`,
      ),
    ]).slice(0, 4),
    rawFieldRows: selectedCandidate.rawFields.slice(0, 14),
    historyRows,
    sourceItems,
    displayAuditRows,
    auditVisibleCount: displayAuditRows.length,
    auditTotalCount: displayAuditRows.length,
  };
}
