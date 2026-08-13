import type {
  ChoiceMacroLatestPoint,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSectorRankSeriesPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  MarketDataCoverageSummaryPayload,
  MacroVendorPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  ResultMeta,
  TushareSupplementPayload,
} from "../../../api/contracts";
import type { MacroToolkitAnalysisPayload } from "../../../api/macroToolkitClient";
import { marketCatalogRefreshTier, marketSeriesRefreshTier } from "../lib/marketDataCategoryStore";
import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import type { MarketDataTerminalModel } from "../lib/marketDataTerminalModel";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import { EM_DASH } from "../../../utils/format";

type Tone = "formal" | "analytical" | "proxy" | "gap" | "neutral";

export type MarketDataOverviewStat = {
  key: string;
  tone: Tone;
  label: string;
  value: string;
  unit: string;
  detail: string;
};

export type MarketDataOverviewDomain = {
  key: string;
  tone: Tone;
  lane: string;
  subLabel: string;
  status: string;
  count: string;
  date: string;
  note: string;
};

export type MarketDataOverviewAnalyticalRow = {
  key: string;
  tone: Tone;
  label: string;
  subLabel: string;
  badge: string;
  count: string;
  date: string;
  note: string;
};

export type MarketDataOverviewSourceGap = {
  key: string;
  label: string;
  subLabel: string;
  badge: string;
  code: string;
  status: string;
};

export type MarketDataTapeEvent = {
  key: string;
  time: string;
  label: string;
  text: string;
};

export type MarketDataTapeLedgerRow = {
  key: string;
  source: string;
  product: string;
  domain: string;
  endpoint: string;
  basis: string;
  formalAllowed: string;
  quality: string;
  fallback: string;
  latest: string;
  date: string;
  note: string;
};

export type MarketDataTapeKeyRateTile = {
  key: string;
  label: string;
  value: string;
  delta: string;
};

export type MarketDataTapeFxRow = {
  key: string;
  pairLabel: string;
  rateText: string;
  statusText: string;
  dateText: string;
};

export type MarketDataTapeMacroRow = {
  key: string;
  name: string;
  valueText: string;
  deltaText: string;
  dateText: string;
  tierText: string;
};

export type MarketDataTapeNcdRow = {
  key: string;
  label: string;
  threeMonthText: string;
  oneYearText: string;
  quoteCountText: string;
};

export type MarketDataTapeLivermoreRow = {
  key: string;
  tone: Tone;
  label: string;
  countText: string;
  statusText: string;
  dateText: string;
};

export type MarketDataTapeSupplementRow = {
  key: string;
  tone: Tone;
  label: string;
  countText: string;
  statusText: string;
  dateText: string;
};

export type MarketDataTushareSignalTile = {
  key: string;
  tone: Tone;
  label: string;
  value: string;
  detail: string;
};

export type MarketDataExternalComparisonPlacementRow = {
  key: string;
  tone: Tone;
  dataset: string;
  targetSurface: string;
  compareWith: string;
  evidence: string;
  dateText: string;
  statusText: string;
};

export type MarketDataEndpointCoverageRow = {
  key: string;
  tone: Tone;
  label: string;
  endpoint: string;
  status: string;
  count: string;
  date: string;
  note: string;
};

export type MarketDataTapeCockpitModel = {
  topbarUpdatedAt: string;
  ratesBasisText: string;
  formalUseAllowedLabel: string;
  newsCalendarStatus: string;
  overviewStats: MarketDataOverviewStat[];
  formalDomainRows: MarketDataOverviewDomain[];
  analyticalRows: MarketDataOverviewAnalyticalRow[];
  sourceGapRows: MarketDataOverviewSourceGap[];
  newsEventRows: MarketDataTapeEvent[];
  calendarEventRows: MarketDataTapeEvent[];
  sourceLedgerRows: MarketDataTapeLedgerRow[];
  keyRateTiles: MarketDataTapeKeyRateTile[];
  moneyRows: MarketDataTerminalModel["moneyMarket"]["rows"];
  fundingCurveSeries: ChoiceMacroLatestPoint | null;
  fxRows: MarketDataTapeFxRow[];
  macroLatestRows: MarketDataTapeMacroRow[];
  ncdProxyRows: MarketDataTapeNcdRow[];
  livermoreDeepRows: MarketDataTapeLivermoreRow[];
  tushareSupplementRows: MarketDataTapeSupplementRow[];
  tushareSignalTiles: MarketDataTushareSignalTile[];
  externalComparisonPlacements: MarketDataExternalComparisonPlacementRow[];
  macroToolkitRows: MarketDataTapeSupplementRow[];
  endpointCoverageRows: MarketDataEndpointCoverageRow[];
};

export type BuildMarketDataTapeCockpitInput = {
  catalog: MacroVendorPayload["series"];
  latestSeries: ChoiceMacroLatestPoint[];
  latestSeriesIsLoading?: boolean;
  latestSeriesIsError?: boolean;
  formalRateSeries: ChoiceMacroLatestPoint[];
  terminalModel: MarketDataTerminalModel;
  fxFormalStatus: FxFormalStatusPayload | null;
  fxAnalyticalGroups: FxAnalyticalPayload["groups"];
  watchDate: string;
  ratesBasisLabel: string;
  formalRatesSeriesCount: number | null;
  formalRatesMeta?: ResultMeta;
  fxFormalMeta?: ResultMeta;
  fxAnalyticalMeta?: ResultMeta;
  ncdFundingProxy?: NcdFundingProxyPayload | null;
  ncdFundingProxyMeta?: ResultMeta;
  livermoreStrategy?: LivermoreStrategyModel | null;
  livermoreMeta?: ResultMeta;
  livermoreIsLoading: boolean;
  livermoreIsError: boolean;
  livermoreSignalConfluence?: LivermoreSignalConfluencePayload | null;
  livermoreSignalConfluenceMeta?: ResultMeta;
  livermoreSignalConfluenceIsLoading?: boolean;
  livermoreSignalConfluenceIsError?: boolean;
  livermoreStrategyScore?: LivermoreStrategyScorePayload | null;
  livermoreStrategyScoreMeta?: ResultMeta;
  livermoreStrategyScoreIsLoading?: boolean;
  livermoreStrategyScoreIsError?: boolean;
  livermoreSectorRankSeries?: LivermoreSectorRankSeriesPayload | null;
  livermoreSectorRankSeriesMeta?: ResultMeta;
  livermoreSectorRankSeriesIsLoading?: boolean;
  livermoreSectorRankSeriesIsError?: boolean;
  livermoreCandidateHistory?: LivermoreCandidateHistoryPayload | null;
  livermoreCandidateHistoryMeta?: ResultMeta;
  livermoreCandidateHistoryIsLoading?: boolean;
  livermoreCandidateHistoryIsError?: boolean;
  livermoreStrategyOptimization?: LivermoreStrategyOptimizationPayload | null;
  livermoreStrategyOptimizationMeta?: ResultMeta;
  livermoreStrategyOptimizationIsLoading?: boolean;
  livermoreStrategyOptimizationIsError?: boolean;
  livermoreCycleProxyBacktest?: LivermoreCycleProxyBacktestPayload | null;
  livermoreCycleProxyBacktestMeta?: ResultMeta;
  livermoreCycleProxyBacktestIsLoading?: boolean;
  livermoreCycleProxyBacktestIsError?: boolean;
  livermorePortfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  livermorePortfolioBacktestMeta?: ResultMeta;
  livermorePortfolioBacktestIsLoading?: boolean;
  livermorePortfolioBacktestIsError?: boolean;
  tushareSupplement?: TushareSupplementPayload | null;
  tushareSupplementMeta?: ResultMeta;
  tushareSupplementIsLoading?: boolean;
  tushareSupplementIsError?: boolean;
  macroToolkitAnalysis?: MacroToolkitAnalysisPayload | null;
  macroToolkitAnalysisMeta?: ResultMeta;
  macroToolkitAnalysisIsLoading?: boolean;
  macroToolkitAnalysisIsError?: boolean;
  coverageSummary?: MarketDataCoverageSummaryPayload | null;
  coverageSummaryMeta?: ResultMeta;
  coverageSummaryIsLoading?: boolean;
  coverageSummaryIsError?: boolean;
  newsPayload: ChoiceNewsEventsPayload | null;
  newsIsLoading: boolean;
  newsIsError: boolean;
  calendarRows: readonly ResearchCalendarEvent[];
  calendarIsLoading: boolean;
  calendarIsError: boolean;
};

function resultMetaQualityLabel(value: ResultMeta["quality_flag"] | undefined): string {
  if (!value) return "待确认";
  const labels: Record<ResultMeta["quality_flag"], string> = {
    ok: "数据正常",
    warning: "部分缺失",
    stale: "数据延迟",
    error: "不可用",
    missing: "部分缺失",
  };
  return labels[value] ?? value;
}

function marketDataBasisLabel(value: string | null | undefined): string {
  const normalized = value ?? "";
  if (normalized.includes("formal")) return normalized.includes("blocked") ? "暂不可正式使用" : "正式可用";
  if (normalized.includes("analytical")) return "仅分析使用";
  if (normalized.includes("proxy")) return "代理数据";
  if (normalized.includes("mock")) return "演示数据";
  if (normalized.includes("source-pending")) return "未接入";
  if (normalized === "unknown" || normalized === "pending") return "待确认";
  return normalized || EM_DASH;
}

function marketDataStatusLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    ready: "数据正常",
    empty: "暂无数据",
    warning: "部分缺失",
    stale: "数据延迟",
    error: "不可用",
    source_pending: "未接入",
    "source-pending": "未接入",
    proxy_only: "代理数据",
    "proxy-only": "代理数据",
    deferred: "接入中",
    pending: "未接入",
    formal: "正式可用",
    analytical: "仅分析使用",
    ok: "数据正常",
    missing: "部分缺失",
    unknown: "待确认",
    vendor_unavailable: "技术异常",
  };
  return labels[value ?? ""] ?? value ?? EM_DASH;
}

function formalUseAllowedText(value: boolean | undefined): string {
  if (value === undefined) return "待确认";
  return value ? "是" : "否";
}

function resultMetaFallbackLabel(value: ResultMeta["fallback_mode"] | undefined): string {
  if (value === "latest_snapshot") return "数据延迟";
  if (value === "none") return "数据正常";
  return "待确认";
}

function resultMetaBusinessDate(meta: ResultMeta | undefined): string {
  return meta?.resolved_report_date ?? meta?.as_of_date ?? meta?.fallback_date ?? meta?.requested_report_date ?? EM_DASH;
}

function formatGeneratedAt(value: string | null | undefined): string {
  return value ? value.replace("T", " ").slice(0, 16) : EM_DASH;
}

function formatFxPreviewRate(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return EM_DASH;
  return value.toFixed(4);
}

function formatNcdProxyRate(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return EM_DASH;
  return value.toFixed(3);
}

function formatTusharePct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return EM_DASH;
  return `${value.toFixed(2)}%`;
}

function formatTusharePp(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return EM_DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}pp`;
}

function findLatestSeriesPoint(
  rows: ChoiceMacroLatestPoint[],
  query: { ids: string[]; nameIncludes?: string[] },
): ChoiceMacroLatestPoint | undefined {
  const sortedRows = [...rows].sort((left, right) => right.trade_date.localeCompare(left.trade_date));
  const exactIds = new Set(query.ids.map((id) => id.toLowerCase()));
  const exactMatch = sortedRows.find((row) => exactIds.has(row.series_id.toLowerCase()));
  if (exactMatch) return exactMatch;

  const nameNeedles = (query.nameIncludes ?? []).map((needle) => needle.toLowerCase());
  if (nameNeedles.length === 0) return undefined;
  return sortedRows.find((row) => {
    const name = row.series_name.toLowerCase();
    return nameNeedles.some((needle) => name.includes(needle));
  });
}

function formatLatestSeriesEvidence(row: ChoiceMacroLatestPoint | undefined): string {
  if (!row) return "数据未接入";
  const label = compactLatestSeriesLabel(row);
  if (row.value_numeric == null || Number.isNaN(row.value_numeric)) return label;
  const unit = row.unit ? ` ${row.unit}` : "";
  return `${compactLatestSeriesLabel(row, 18)} ${row.value_numeric.toFixed(2)}${unit}`;
}

function externalPointQualityLabel(points: Array<ChoiceMacroLatestPoint | undefined>): string {
  const qualityFlags = points
    .map((point) => point?.quality_flag)
    .filter((value): value is NonNullable<ChoiceMacroLatestPoint["quality_flag"]> => Boolean(value));
  if (qualityFlags.includes("error")) return "不可用";
  if (qualityFlags.includes("stale")) return "数据延迟";
  if (qualityFlags.includes("warning") || qualityFlags.includes("missing")) return "部分缺失";
  return qualityFlags.length > 0 ? resultMetaQualityLabel(qualityFlags[0]) : "数据正常";
}

function externalPlacementStatus(input: {
  isLoading?: boolean;
  isError?: boolean;
  hasData: boolean;
  metas?: Array<ResultMeta | undefined>;
  points?: Array<ChoiceMacroLatestPoint | undefined>;
  fallbackTone?: Tone;
}): { tone: Tone; statusText: string } {
  if (input.isLoading) return { tone: "analytical", statusText: "接入中" };
  if (input.isError) return { tone: "gap", statusText: "技术异常" };
  if (!input.hasData) return { tone: "neutral", statusText: "未接入" };

  const metas = input.metas?.filter((meta): meta is ResultMeta => Boolean(meta)) ?? [];
  const metaQuality =
    metas.find((meta) => meta.quality_flag === "error")?.quality_flag ??
    metas.find((meta) => meta.quality_flag === "stale")?.quality_flag ??
    metas.find((meta) => meta.quality_flag === "warning")?.quality_flag ??
    metas.find((meta) => meta.quality_flag === "missing")?.quality_flag ??
    metas[0]?.quality_flag;
  const qualityLabel = metaQuality ? resultMetaQualityLabel(metaQuality) : externalPointQualityLabel(input.points ?? []);
  const hasFallback = metas.some((meta) => meta.fallback_mode !== "none");
  const hasStale = metas.some((meta) => meta.vendor_status === "vendor_stale") || qualityLabel === "数据延迟";
  const hasError = qualityLabel === "不可用";
  const basisLabel = marketDataBasisLabel(metas[0]?.basis ?? "analytical");
  const statusText = [basisLabel, qualityLabel, hasFallback ? resultMetaFallbackLabel("latest_snapshot") : null]
    .filter(Boolean)
    .join(" / ");
  return {
    tone: hasError ? "gap" : hasStale || hasFallback ? "proxy" : input.fallbackTone ?? "analytical",
    statusText,
  };
}

function endpointStatusLabel(input: { isLoading?: boolean; isError?: boolean; hasData: boolean }): string {
  if (input.isLoading) return "接入中";
  if (input.isError) return "技术异常";
  if (input.hasData) return "已接入";
  return "未接入";
}

function endpointTone(input: { isLoading?: boolean; isError?: boolean; hasData: boolean }): Tone {
  if (input.isError) return "gap";
  if (input.hasData || input.isLoading) return "analytical";
  return "neutral";
}

function compactMarketLabel(value: string, maxLength = 28): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}...` : normalized;
}

function compactLatestSeriesLabel(point: ChoiceMacroLatestPoint, maxLength = 28): string {
  return compactMarketLabel(point.series_name || point.series_id || "unknown series", maxLength);
}

function refreshTierLabel(value: ReturnType<typeof marketSeriesRefreshTier>): string {
  if (value === "fallback") return "数据延迟";
  if (value === "isolated") return "单点观察";
  return "数据正常";
}

function summarizeChoiceNewsEvent(event: ChoiceNewsEvent): string {
  const raw =
    event.payload_text?.trim() ||
    event.payload_json?.trim() ||
    (event.error_code !== 0 ? event.error_msg : "") ||
    "空内容";
  const normalized = raw.replace(/\s+/g, " ");
  return normalized.length > 64 ? `${normalized.slice(0, 64)}...` : normalized;
}

function formatPreviewTime(value: string | null | undefined): string {
  if (!value) return EM_DASH;
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value.slice(0, 16);
    return d.toLocaleString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return value.slice(0, 16);
  }
}

function calendarKindShortLabel(kind: ResearchCalendarEvent["kind"]): string {
  if (kind === "supply") return "供给";
  if (kind === "auction") return "招标";
  if (kind === "macro") return "宏观";
  return "内部";
}

function calendarSeverityShortLabel(severity: ResearchCalendarEvent["severity"]): string {
  if (severity === "high") return "高";
  if (severity === "medium") return "中";
  return "低";
}

function latestTradeDate(series: ChoiceMacroLatestPoint[], fallback: string): string {
  const dates = series.map((point) => point.trade_date).filter(Boolean);
  return dates.length > 0 ? dates.sort((left, right) => left.localeCompare(right))[dates.length - 1] : fallback;
}

function latestDateText(values: Array<string | null | undefined>, fallback = EM_DASH): string {
  const dates = values.filter((value): value is string => Boolean(value));
  return dates.length > 0 ? dates.sort((left, right) => left.localeCompare(right))[dates.length - 1] : fallback;
}

function normalizeCompactDate(value: string | null | undefined): string | null {
  if (!value) return null;
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}

function normalizeCompactMonth(value: string | null | undefined): string {
  const normalized = normalizeCompactDate(value);
  return normalized ? normalized.slice(0, 7) : EM_DASH;
}

function fxAnalyticalObservationCount(groups: FxAnalyticalPayload["groups"]): number {
  return groups.reduce((total, group) => total + group.series.length + (group.events?.length ?? 0), 0);
}

function fxAnalyticalEventCount(groups: FxAnalyticalPayload["groups"]): number {
  return groups.reduce((total, group) => total + (group.events?.length ?? 0), 0);
}

function pickFundingSeries(
  formalRateSeries: ChoiceMacroLatestPoint[],
  moneyRows: MarketDataTerminalModel["moneyMarket"]["rows"],
): ChoiceMacroLatestPoint | null {
  const preferredRow = moneyRows.find((row) => row.name === "DR007") ?? moneyRows[0];
  if (!preferredRow) return null;
  return formalRateSeries.find((point) => point.series_id === preferredRow.seriesId) ?? null;
}

export function buildMarketDataTapeCockpitModel(input: BuildMarketDataTapeCockpitInput): MarketDataTapeCockpitModel {
  const primaryMoney =
    input.terminalModel.moneyMarket.rows.find((row) => row.name === "DR007") ?? input.terminalModel.moneyMarket.rows[0];
  const fxFormalMaterialized = input.fxFormalStatus?.materialized_count ?? 0;
  const fxFormalCandidates = input.fxFormalStatus?.candidate_count ?? 0;
  const fxAnalyticalSeriesCount = fxAnalyticalObservationCount(input.fxAnalyticalGroups);
  const fxEventCount = fxAnalyticalEventCount(input.fxAnalyticalGroups);
  const catalogStableCount = input.catalog.filter((series) => marketCatalogRefreshTier(series) === "stable").length;
  const catalogFallbackCount = input.catalog.filter((series) => marketCatalogRefreshTier(series) === "fallback").length;
  const latestStableCount = input.latestSeries.filter((point) => marketSeriesRefreshTier(point) === "stable").length;
  const latestFallbackCount = input.latestSeries.filter((point) => marketSeriesRefreshTier(point) === "fallback").length;
  const formalRatesCountText =
    input.formalRatesSeriesCount == null ? String(input.terminalModel.rateQuotes.rows.length) : String(input.formalRatesSeriesCount);
  const ratesBasisText = marketDataBasisLabel(input.ratesBasisLabel);
  const formalUseAllowedLabel = formalUseAllowedText(input.formalRatesMeta?.formal_use_allowed);
  const proxyFallbackCount =
    (input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? 1 : 0) +
    (input.ncdFundingProxy?.is_actual_ncd_matrix ? 0 : 1);
  const analyticalUseCount = 3 + input.fxAnalyticalGroups.length + (input.latestSeries.length > 0 ? 1 : 0) + 1;
  const formalRatesBusinessDate = resultMetaBusinessDate(input.formalRatesMeta);
  const formalRatesDisplayDate =
    formalRatesBusinessDate === EM_DASH ? input.watchDate || EM_DASH : formalRatesBusinessDate;
  const dataLatestDate = latestTradeDate(input.formalRateSeries, input.watchDate || formalRatesDisplayDate);
  const topbarUpdatedAt = formatGeneratedAt(
    input.formalRatesMeta?.generated_at ??
      input.fxFormalMeta?.generated_at ??
      input.fxAnalyticalMeta?.generated_at ??
      input.ncdFundingProxyMeta?.generated_at ??
      input.livermoreMeta?.generated_at,
  );
  const newsRows = input.newsPayload?.events.slice(0, 3) ?? [];
  const newsTotalRows = input.newsPayload?.total_rows ?? newsRows.length;
  const calendarPreviewRows = [...input.calendarRows]
    .sort((a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title))
    .slice(0, 3);
  const newsCalendarStatus = `${
    input.newsIsLoading ? "资讯加载中" : input.newsIsError ? "资讯失败" : `${newsTotalRows} 条资讯`
  } / ${
    input.calendarIsLoading ? "日历加载中" : input.calendarIsError ? "日历失败" : `${input.calendarRows.length} 条日历`
  }`;
  const allRateRows = input.terminalModel.rateQuotes.rows;
  const findRateRow = (variety: string, tenor: string) =>
    allRateRows.find((row) => row.variety === variety && row.tenor === tenor);
  const findMoneyRow = (name: string) =>
    input.terminalModel.moneyMarket.rows.find((row) => row.name.toLowerCase().includes(name.toLowerCase()));
  const cgb10y = findRateRow("国债", "10Y");
  const cgb5y = findRateRow("国债", "5Y");
  const dr007 = findMoneyRow("DR007") ?? primaryMoney;
  const shibor3m =
    input.terminalModel.moneyMarket.rows.find(
      (row) => row.seriesId.toLowerCase().includes("shibor") || row.name.includes("SHIBOR"),
    ) ?? allRateRows.find((row) => row.seriesId.toLowerCase().includes("shibor"));
  const fundingCurveSeries = pickFundingSeries(input.formalRateSeries, input.terminalModel.moneyMarket.rows);
  const livermoreBadge = input.livermoreIsLoading
    ? "加载"
    : input.livermoreIsError
      ? "失败"
      : input.livermoreStrategy
        ? "分析"
        : "未接入";
  const livermoreCount = input.livermoreStrategy
    ? `${input.livermoreStrategy.ruleBlocks.length} 模块`
    : "Gate / 行业 / 因子";
  const livermoreNote = input.livermoreStrategy
    ? `${input.livermoreStrategy.marketGate.state}，${input.livermoreStrategy.supportedOutputs.length} 项输出`
    : "分析假设，非正式结论";
  const fxRows = (input.fxFormalStatus?.rows.slice(0, 5) ?? []).map((row) => ({
    key: row.series_id,
    pairLabel: row.pair_label,
    rateText: formatFxPreviewRate(row.mid_rate),
    statusText: row.is_carry_forward ? "数据延迟" : marketDataStatusLabel(row.status),
    dateText: row.trade_date ?? row.observed_trade_date ?? EM_DASH,
  }));
  const macroLatestRows = input.latestSeries
    .filter((point) => marketSeriesRefreshTier(point) !== "isolated")
    .slice(0, 6)
    .map((point) => ({
      key: point.series_id,
      name: compactLatestSeriesLabel(point),
      valueText: formatChoiceMacroValue(point, { spaceBeforeUnit: false }),
      deltaText: formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: EM_DASH }),
      dateText: point.trade_date,
      tierText: refreshTierLabel(marketSeriesRefreshTier(point)),
    }));
  const ncdProxyRows = (input.ncdFundingProxy?.rows.slice(0, 4) ?? []).map((row) => ({
    key: row.row_key,
    label: row.label,
    threeMonthText: formatNcdProxyRate(row["3M"]),
    oneYearText: formatNcdProxyRate(row["1Y"]),
    quoteCountText: row.quote_count == null ? EM_DASH : String(row.quote_count),
  }));
  const livermoreSignalObservationCount =
    (input.livermoreSignalConfluence?.entry_observations.length ?? 0) +
    (input.livermoreSignalConfluence?.exit_observations.length ?? 0);
  const livermoreScoreRows = input.livermoreStrategyScore?.rows.length ?? 0;
  const livermoreSectorSeriesRows = input.livermoreSectorRankSeries?.series.length ?? 0;
  const livermoreCandidateHistoryRows = input.livermoreCandidateHistory?.items.length ?? 0;
  const livermoreCandidateHistoryDate =
    input.livermoreCandidateHistory?.snapshot_to ??
    input.livermoreCandidateHistory?.backtest_window_summary?.snapshot_to ??
    latestDateText(
      input.livermoreCandidateHistory?.items.map((row) => row.snapshot_as_of_date) ?? [],
      resultMetaBusinessDate(input.livermoreCandidateHistoryMeta),
    );
  const livermoreOptimizationRecs = input.livermoreStrategyOptimization?.recommendations.length ?? 0;
  const livermoreOptimizationSlices = input.livermoreStrategyOptimization?.slices.length ?? 0;
  const livermoreCycleNavPoints = input.livermoreCycleProxyBacktest?.nav_series.length ?? 0;
  const livermorePortfolioRebalances = input.livermorePortfolioBacktest?.rebalance_log.length ?? 0;
  const livermoreDeepEndpointReadCount = [
    input.livermoreSignalConfluence,
    input.livermoreStrategyScore,
    input.livermoreSectorRankSeries,
    input.livermoreCandidateHistory,
    input.livermoreStrategyOptimization,
    input.livermoreCycleProxyBacktest,
    input.livermorePortfolioBacktest,
  ].filter(Boolean).length;
  const livermoreDeepRows: MarketDataTapeLivermoreRow[] = [
    {
      key: "candidate-history",
      tone: endpointTone({
        isLoading: input.livermoreCandidateHistoryIsLoading,
        isError: input.livermoreCandidateHistoryIsError,
        hasData: Boolean(input.livermoreCandidateHistory),
      }),
      label: "Candidate History",
      countText: `${livermoreCandidateHistoryRows} rows`,
      statusText: endpointStatusLabel({
        isLoading: input.livermoreCandidateHistoryIsLoading,
        isError: input.livermoreCandidateHistoryIsError,
        hasData: Boolean(input.livermoreCandidateHistory),
      }),
      dateText: livermoreCandidateHistoryDate,
    },
    {
      key: "strategy-optimization",
      tone: endpointTone({
        isLoading: input.livermoreStrategyOptimizationIsLoading,
        isError: input.livermoreStrategyOptimizationIsError,
        hasData: Boolean(input.livermoreStrategyOptimization),
      }),
      label: "Strategy Optimization",
      countText: `${livermoreOptimizationRecs} rec / ${livermoreOptimizationSlices} slices`,
      statusText: endpointStatusLabel({
        isLoading: input.livermoreStrategyOptimizationIsLoading,
        isError: input.livermoreStrategyOptimizationIsError,
        hasData: Boolean(input.livermoreStrategyOptimization),
      }),
      dateText:
        input.livermoreStrategyOptimization?.snapshot_to ??
        input.livermoreStrategyOptimization?.as_of_date ??
        resultMetaBusinessDate(input.livermoreStrategyOptimizationMeta),
    },
    {
      key: "cycle-proxy-backtest",
      tone: endpointTone({
        isLoading: input.livermoreCycleProxyBacktestIsLoading,
        isError: input.livermoreCycleProxyBacktestIsError,
        hasData: Boolean(input.livermoreCycleProxyBacktest),
      }),
      label: "Cycle Proxy Backtest",
      countText: `${livermoreCycleNavPoints} nav`,
      statusText: endpointStatusLabel({
        isLoading: input.livermoreCycleProxyBacktestIsLoading,
        isError: input.livermoreCycleProxyBacktestIsError,
        hasData: Boolean(input.livermoreCycleProxyBacktest),
      }),
      dateText:
        input.livermoreCycleProxyBacktest?.snapshot_to ??
        resultMetaBusinessDate(input.livermoreCycleProxyBacktestMeta),
    },
    {
      key: "portfolio-proxy-backtest",
      tone: endpointTone({
        isLoading: input.livermorePortfolioBacktestIsLoading,
        isError: input.livermorePortfolioBacktestIsError,
        hasData: Boolean(input.livermorePortfolioBacktest),
      }),
      label: "Portfolio Proxy",
      countText: `${livermorePortfolioRebalances} rebal`,
      statusText: endpointStatusLabel({
        isLoading: input.livermorePortfolioBacktestIsLoading,
        isError: input.livermorePortfolioBacktestIsError,
        hasData: Boolean(input.livermorePortfolioBacktest),
      }),
      dateText:
        input.livermorePortfolioBacktest?.snapshot_to ??
        resultMetaBusinessDate(input.livermorePortfolioBacktestMeta),
    },
  ];
  const tushareMoneyRows = input.tushareSupplement?.money_supply_rows.length ?? 0;
  const tushareEcoRows = input.tushareSupplement?.eco_cal_rows.length ?? 0;
  const latestTushareMoneyRow = [...(input.tushareSupplement?.money_supply_rows ?? [])].sort((left, right) =>
    right.month.localeCompare(left.month),
  )[0];
  const latestTushareEcoRow = [...(input.tushareSupplement?.eco_cal_rows ?? [])].sort((left, right) =>
    `${right.event_date}${right.event_time ?? ""}`.localeCompare(`${left.event_date}${left.event_time ?? ""}`),
  )[0];
  const m1M2Spread =
    latestTushareMoneyRow?.m1_yoy == null || latestTushareMoneyRow.m2_yoy == null
      ? null
      : latestTushareMoneyRow.m2_yoy - latestTushareMoneyRow.m1_yoy;
  const tushareMoneyLatestDate = latestDateText(
    input.tushareSupplement?.money_supply_rows.map((row) => normalizeCompactDate(row.month)) ?? [],
    resultMetaBusinessDate(input.tushareSupplementMeta),
  );
  const tushareEcoLatestDate = latestDateText(
    input.tushareSupplement?.eco_cal_rows.map((row) => normalizeCompactDate(row.event_date)) ?? [],
    resultMetaBusinessDate(input.tushareSupplementMeta),
  );
  const tushareSupplementDate = latestDateText(
    [tushareMoneyLatestDate, tushareEcoLatestDate],
    resultMetaBusinessDate(input.tushareSupplementMeta),
  );
  const macroToolkitCoverage = input.macroToolkitAnalysis?.coverage;
  const macroToolkitReadiness = input.macroToolkitAnalysis?.readiness_summary;
  const macroToolkitDate =
    input.macroToolkitAnalysis?.as_of_date ?? resultMetaBusinessDate(input.macroToolkitAnalysisMeta);
  const macroToolkitIndicatorCount = macroToolkitCoverage?.indicator_count ?? 0;
  const macroToolkitHitCount = macroToolkitCoverage?.hit_count ?? 0;
  const macroToolkitSignalCardCount = input.macroToolkitAnalysis?.signal_cards.length ?? 0;
  const macroToolkitHitRateText =
    macroToolkitCoverage == null ? EM_DASH : `${Math.round(macroToolkitCoverage.hit_rate * 100)}%`;
  const supplementalEndpointReadCount = [
    input.tushareSupplement,
    input.macroToolkitAnalysis,
  ].filter(Boolean).length;
  const tushareSupplementRows: MarketDataTapeSupplementRow[] = [
    {
      key: "money-supply",
      tone: endpointTone({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      label: "Money Supply",
      countText: `${tushareMoneyRows} months`,
      statusText: endpointStatusLabel({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      dateText: tushareMoneyLatestDate,
    },
    {
      key: "eco-calendar",
      tone: endpointTone({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      label: "Eco Calendar",
      countText: `${tushareEcoRows} events`,
      statusText: endpointStatusLabel({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      dateText: tushareEcoLatestDate,
    },
  ];
  const tushareSignalTiles: MarketDataTushareSignalTile[] = [
    {
      key: "m2-yoy",
      tone: "analytical",
      label: "M2 YoY",
      value: formatTusharePct(latestTushareMoneyRow?.m2_yoy),
      detail: `latest ${normalizeCompactMonth(latestTushareMoneyRow?.month)}`,
    },
    {
      key: "m2-m1-spread",
      tone: "analytical",
      label: "M2 - M1",
      value: formatTusharePp(m1M2Spread),
      detail: `M1 ${formatTusharePct(latestTushareMoneyRow?.m1_yoy)} / M2 ${formatTusharePct(latestTushareMoneyRow?.m2_yoy)}`,
    },
    {
      key: "eco-calendar",
      tone: "analytical",
      label: "Eco Calendar",
      value: `${tushareEcoRows}`,
      detail: latestTushareEcoRow
        ? `${normalizeCompactDate(latestTushareEcoRow.event_date) ?? EM_DASH} ${latestTushareEcoRow.currency ?? "event"}`
        : "no event rows",
    },
    {
      key: "tushare-lineage",
      tone: input.tushareSupplementMeta?.quality_flag === "stale" ? "proxy" : "analytical",
      label: "Tushare Lineage",
      value: endpointStatusLabel({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      detail: `basis ${marketDataBasisLabel(input.tushareSupplementMeta?.basis)} / ${resultMetaQualityLabel(input.tushareSupplementMeta?.quality_flag)}`,
    },
  ];
  const pmiPoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["M0017127"],
    nameIncludes: ["PMI", "采购经理"],
  });
  const cpiPoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["EMM00072301", "M0000612", "cn_cpi_yoy", "tushare.macro.cn_cpi.monthly"],
    nameIncludes: ["CPI", "居民消费价格"],
  });
  const ppiPoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["M0001227", "cn_ppi_yoy", "tushare.macro.cn_ppi.monthly"],
    nameIncludes: ["PPI", "工业生产者"],
  });
  const csi300Point = findLatestSeriesPoint(input.latestSeries, {
    ids: ["CA.CSI300"],
    nameIncludes: ["CSI300 close", "CSI 300 close", "沪深300指数"],
  });
  const csi300PePoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["CA.CSI300_PE"],
    nameIncludes: ["CSI300 PE", "CSI 300 PE", "沪深300市盈率", "沪深300估值"],
  });
  const copperPoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["CA.COPPER"],
    nameIncludes: ["Copper futures", "Copper main", "铜主力期货", "铜期货"],
  });
  const aluminumPoint = findLatestSeriesPoint(input.latestSeries, {
    ids: ["CA.ALUMINUM"],
    nameIncludes: ["Aluminum futures", "Aluminum main", "铝主力期货", "铝期货"],
  });
  const commodityPoint = copperPoint ?? aluminumPoint;
  const macroComparisonEvidence = [
    latestTushareMoneyRow ? `M2 ${formatTusharePct(latestTushareMoneyRow.m2_yoy)}` : null,
    pmiPoint ? formatLatestSeriesEvidence(pmiPoint) : null,
    cpiPoint ? formatLatestSeriesEvidence(cpiPoint) : null,
    ppiPoint ? formatLatestSeriesEvidence(ppiPoint) : null,
  ].filter(Boolean);
  const equityComparisonEvidence = [
    csi300Point ? formatLatestSeriesEvidence(csi300Point) : null,
    csi300PePoint ? formatLatestSeriesEvidence(csi300PePoint) : null,
  ].filter(Boolean);
  const eventComparisonCount = (input.newsPayload?.events.length ?? 0) + input.calendarRows.length + tushareEcoRows;
  const macroPlacementStatus = externalPlacementStatus({
    isLoading: input.latestSeriesIsLoading || input.tushareSupplementIsLoading || input.macroToolkitAnalysisIsLoading,
    isError: input.latestSeriesIsError || input.tushareSupplementIsError || input.macroToolkitAnalysisIsError,
    hasData: macroComparisonEvidence.length > 0,
    metas: [input.tushareSupplementMeta, input.macroToolkitAnalysisMeta],
    points: [pmiPoint, cpiPoint, ppiPoint],
  });
  const equityPlacementStatus = externalPlacementStatus({
    isLoading: input.latestSeriesIsLoading,
    isError: input.latestSeriesIsError,
    hasData: equityComparisonEvidence.length > 0,
    points: [csi300Point, csi300PePoint],
  });
  const commodityPlacementStatus = externalPlacementStatus({
    isLoading: input.latestSeriesIsLoading,
    isError: input.latestSeriesIsError,
    hasData: Boolean(commodityPoint),
    points: [commodityPoint],
    fallbackTone: "proxy",
  });
  const eventPlacementStatus = externalPlacementStatus({
    isLoading: input.newsIsLoading || input.calendarIsLoading || input.tushareSupplementIsLoading,
    isError: input.newsIsError || input.calendarIsError || input.tushareSupplementIsError,
    hasData: eventComparisonCount > 0,
    metas: [input.tushareSupplementMeta],
  });
  const latestEventDate = latestDateText([
    ...((input.tushareSupplement?.eco_cal_rows ?? []).map((row) => normalizeCompactDate(row.event_date))),
    ...input.calendarRows.map((row) => row.date),
    ...(input.newsPayload?.events.map((event) => event.received_at.slice(0, 10)) ?? []),
  ], EM_DASH);
  const externalComparisonPlacements: MarketDataExternalComparisonPlacementRow[] = [
    {
      key: "macro-rates",
      tone: macroPlacementStatus.tone,
      dataset: "Macro liquidity",
      targetSurface: "/macro-toolkit + rates",
      compareWith: "M2/M1, CPI/PPI/PMI vs SHIBOR/NCD and CGB curve",
      evidence: macroComparisonEvidence.length > 0 ? macroComparisonEvidence.slice(0, 2).join(" / ") : "pending macro source",
      dateText: latestDateText([
        normalizeCompactDate(latestTushareMoneyRow?.month),
        pmiPoint?.trade_date,
        cpiPoint?.trade_date,
        ppiPoint?.trade_date,
      ], tushareSupplementDate),
      statusText: macroPlacementStatus.statusText,
    },
    {
      key: "equity-theme",
      tone: equityPlacementStatus.tone,
      dataset: "Equity beta/theme",
      targetSurface: "/stock-analysis",
      compareWith: "CSI300, valuation, breadth, limit flags, concept membership",
      evidence: equityComparisonEvidence.length > 0 ? equityComparisonEvidence.join(" / ") : "pending equity source",
      dateText: latestDateText([csi300Point?.trade_date, csi300PePoint?.trade_date], EM_DASH),
      statusText: equityPlacementStatus.statusText,
    },
    {
      key: "commodity-cycle",
      tone: commodityPlacementStatus.tone,
      dataset: "Commodity cycle",
      targetSurface: "/cross-asset + /risk-tensor",
      compareWith: "Copper/aluminum vs PMI/PPI, rates, and equity sectors",
      evidence: formatLatestSeriesEvidence(commodityPoint),
      dateText: commodityPoint?.trade_date ?? EM_DASH,
      statusText: commodityPlacementStatus.statusText,
    },
    {
      key: "event-reaction",
      tone: eventPlacementStatus.tone,
      dataset: "Event reaction",
      targetSurface: "/news-events + /risk-tensor",
      compareWith: "Policy/news/calendar events vs 1D/5D price and rate moves",
      evidence: `${eventComparisonCount} event rows`,
      dateText: latestEventDate,
      statusText: eventPlacementStatus.statusText,
    },
  ];
  const macroToolkitRows: MarketDataTapeSupplementRow[] = [
    {
      key: "indicator-coverage",
      tone: endpointTone({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      label: "Indicator Coverage",
      countText: `${macroToolkitHitCount}/${macroToolkitIndicatorCount}`,
      statusText: macroToolkitHitRateText,
      dateText: macroToolkitDate,
    },
    {
      key: "signal-cards",
      tone: endpointTone({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      label: "Signal Cards",
      countText: `${macroToolkitSignalCardCount} cards`,
      statusText: input.macroToolkitAnalysis?.conclusion.stance ?? endpointStatusLabel({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      dateText: macroToolkitDate,
    },
    {
      key: "model-readiness",
      tone: endpointTone({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      label: "Model Readiness",
      countText: `${macroToolkitReadiness?.artifact_backed_count ?? 0}/${macroToolkitReadiness?.total_count ?? 0}`,
      statusText: `${macroToolkitReadiness?.degraded_count ?? 0} degraded`,
      dateText: macroToolkitDate,
    },
  ];
  const bondFuturesRows = input.terminalModel.bondFutures.rows.length;
  const bondFuturesDate =
    input.terminalModel.bondFutures.status === "source-pending"
      ? input.watchDate || dataLatestDate
      : input.terminalModel.bondFutures.asOfDate ?? input.watchDate ?? dataLatestDate;
  const coverageSummarySectionCount = input.coverageSummary?.sections.length ?? 0;
  const macroLatestEndpointStatus = endpointStatusLabel({
    isLoading: input.latestSeriesIsLoading,
    isError: input.latestSeriesIsError,
    hasData: input.latestSeries.length > 0,
  });
  const macroLatestEndpointTone: Tone = input.latestSeriesIsError
    ? "gap"
    : input.latestSeries.length > 0 || input.latestSeriesIsLoading
      ? "analytical"
      : "neutral";
  const macroLatestQuality = input.latestSeriesIsLoading
    ? macroLatestEndpointStatus
    : input.latestSeriesIsError
      ? macroLatestEndpointStatus
      : input.latestSeries.length > 0
        ? externalPointQualityLabel(input.latestSeries)
        : macroLatestEndpointStatus;
  const macroLatestNote = macroLatestEndpointStatus;
  const endpointCoverageRows: MarketDataEndpointCoverageRow[] = [
    {
      key: "rates",
      tone: "formal",
      label: "正式利率",
      endpoint: "/ui/market-data/rates",
      status: "已接入",
      count: `${formalRatesCountText} series`,
      date: formalRatesDisplayDate,
      note: "首屏曲线与行情带",
    },
    {
      key: "catalog",
      tone: "formal",
      label: "市场目录",
      endpoint: "/ui/market-data/catalog",
      status: "已接入",
      count: `${input.catalog.length} series`,
      date: input.watchDate || dataLatestDate,
      note: "序列清单",
    },
    {
      key: "macro-latest",
      tone: macroLatestEndpointTone,
      label: "宏观最新点",
      endpoint: "/ui/macro/choice-series/latest",
      status: macroLatestEndpointStatus,
      count: `${input.latestSeries.length} rows`,
      date: latestTradeDate(input.latestSeries, input.watchDate || dataLatestDate),
      note: macroLatestNote,
    },
    {
      key: "fx-formal",
      tone: input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? "proxy" : "formal",
      label: "外汇正式片段",
      endpoint: "/ui/market-data/fx/formal-status",
      status: "已接入",
      count: `${fxFormalMaterialized}/${fxFormalCandidates}`,
      date: input.fxFormalStatus?.latest_trade_date ?? resultMetaBusinessDate(input.fxFormalMeta),
      note: input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? "数据延迟" : "正式片段",
    },
    {
      key: "fx-analytical",
      tone: "analytical",
      label: "外汇分析",
      endpoint: "/ui/market-data/fx/analytical",
      status: "已接入",
      count: `${input.fxAnalyticalGroups.length}/${fxAnalyticalSeriesCount}`,
      date: resultMetaBusinessDate(input.fxAnalyticalMeta),
      note: "分析分组与事件",
    },
    {
      key: "ncd-proxy",
      tone: "proxy",
      label: "存单代理",
      endpoint: "/ui/market-data/ncd-funding-proxy",
      status: endpointStatusLabel({ hasData: Boolean(input.ncdFundingProxy) }),
      count: `${input.ncdFundingProxy?.rows.length ?? 0} rows`,
      date: input.ncdFundingProxy?.as_of_date ?? resultMetaBusinessDate(input.ncdFundingProxyMeta),
      note: input.ncdFundingProxy?.is_actual_ncd_matrix ? "正式矩阵" : "代理资金矩阵",
    },
    {
      key: "bond-futures-rankings",
      tone: bondFuturesRows > 0 ? "analytical" : "gap",
      label: "国债期货排名",
      endpoint: "/ui/market-data/bond-futures/rankings",
      status: endpointStatusLabel({ hasData: bondFuturesRows > 0 }),
      count: `${bondFuturesRows} rows`,
      date: bondFuturesDate,
      note: bondFuturesRows > 0 ? "会员排名数据" : "暂不可用",
    },
    {
      key: "coverage-summary",
      tone: endpointTone({
        isLoading: input.coverageSummaryIsLoading,
        isError: input.coverageSummaryIsError,
        hasData: Boolean(input.coverageSummary),
      }),
      label: "覆盖摘要",
      endpoint: "/ui/market-data/coverage-summary",
      status: endpointStatusLabel({
        isLoading: input.coverageSummaryIsLoading,
        isError: input.coverageSummaryIsError,
        hasData: Boolean(input.coverageSummary),
      }),
      count: `${coverageSummarySectionCount} sections`,
      date: input.coverageSummary?.as_of_date ?? resultMetaBusinessDate(input.coverageSummaryMeta),
      note: input.coverageSummary?.headline.readiness_label ?? "来源覆盖台账",
    },
    {
      key: "tushare-supplement",
      tone: endpointTone({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      label: "补充宏观数据",
      endpoint: "/ui/market-data/tushare-supplement",
      status: endpointStatusLabel({
        isLoading: input.tushareSupplementIsLoading,
        isError: input.tushareSupplementIsError,
        hasData: Boolean(input.tushareSupplement),
      }),
      count: `${tushareMoneyRows} money / ${tushareEcoRows} events`,
      date: tushareSupplementDate,
      note: "货币供应与经济日历",
    },
    {
      key: "macro-toolkit-core",
      tone: endpointTone({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      label: "宏观工具核心",
      endpoint: "/ui/macro/toolkit/analysis?detail=core",
      status: endpointStatusLabel({
        isLoading: input.macroToolkitAnalysisIsLoading,
        isError: input.macroToolkitAnalysisIsError,
        hasData: Boolean(input.macroToolkitAnalysis),
      }),
      count: `${macroToolkitHitCount}/${macroToolkitIndicatorCount} indicators`,
      date: macroToolkitDate,
      note: `${macroToolkitSignalCardCount} 张信号卡`,
    },
    {
      key: "news",
      tone: input.newsIsError ? "gap" : "formal",
      label: "资讯事件",
      endpoint: "/ui/news/choice-events/latest",
      status: endpointStatusLabel({
        isLoading: input.newsIsLoading,
        isError: input.newsIsError,
        hasData: Boolean(input.newsPayload),
      }),
      count: `${newsTotalRows} rows`,
      date: input.watchDate || dataLatestDate,
      note: "市场事件流",
    },
    {
      key: "calendar",
      tone: input.calendarIsError ? "gap" : "formal",
      label: "供给日历",
      endpoint: "/ui/calendar/supply-auctions",
      status: endpointStatusLabel({
        isLoading: input.calendarIsLoading,
        isError: input.calendarIsError,
        hasData: input.calendarRows.length > 0,
      }),
      count: `${input.calendarRows.length} events`,
      date: input.watchDate || dataLatestDate,
      note: "招标与供给安排",
    },
    {
      key: "livermore",
      tone: endpointTone({
        isLoading: input.livermoreIsLoading,
        isError: input.livermoreIsError,
        hasData: Boolean(input.livermoreStrategy),
      }),
      label: "Livermore Strategy",
      endpoint: "/ui/market-data/livermore",
      status: endpointStatusLabel({
        isLoading: input.livermoreIsLoading,
        isError: input.livermoreIsError,
        hasData: Boolean(input.livermoreStrategy),
      }),
      count: input.livermoreStrategy ? `${input.livermoreStrategy.supportedOutputs.length} outputs` : "0 outputs",
      date: input.livermoreStrategy?.asOfDate ?? resultMetaBusinessDate(input.livermoreMeta),
      note: "market gate + modules",
    },
    {
      key: "livermore-signal",
      tone: endpointTone({
        isLoading: input.livermoreSignalConfluenceIsLoading,
        isError: input.livermoreSignalConfluenceIsError,
        hasData: Boolean(input.livermoreSignalConfluence),
      }),
      label: "Signal Confluence",
      endpoint: "/ui/market-data/livermore/signal-confluence",
      status: endpointStatusLabel({
        isLoading: input.livermoreSignalConfluenceIsLoading,
        isError: input.livermoreSignalConfluenceIsError,
        hasData: Boolean(input.livermoreSignalConfluence),
      }),
      count: `${livermoreSignalObservationCount} obs`,
      date:
        input.livermoreSignalConfluence?.as_of_date ??
        resultMetaBusinessDate(input.livermoreSignalConfluenceMeta),
      note: "entry/exit + adversarial gate",
    },
    {
      key: "livermore-score",
      tone: endpointTone({
        isLoading: input.livermoreStrategyScoreIsLoading,
        isError: input.livermoreStrategyScoreIsError,
        hasData: Boolean(input.livermoreStrategyScore),
      }),
      label: "Strategy Score",
      endpoint: "/ui/market-data/livermore/strategy-score",
      status: endpointStatusLabel({
        isLoading: input.livermoreStrategyScoreIsLoading,
        isError: input.livermoreStrategyScoreIsError,
        hasData: Boolean(input.livermoreStrategyScore),
      }),
      count: `${livermoreScoreRows} rows`,
      date: input.livermoreStrategyScore?.as_of_date ?? resultMetaBusinessDate(input.livermoreStrategyScoreMeta),
      note: "candidate replay score",
    },
    {
      key: "livermore-sector-series",
      tone: endpointTone({
        isLoading: input.livermoreSectorRankSeriesIsLoading,
        isError: input.livermoreSectorRankSeriesIsError,
        hasData: Boolean(input.livermoreSectorRankSeries),
      }),
      label: "Sector Rank Series",
      endpoint: "/ui/market-data/livermore/sector-rank-series",
      status: endpointStatusLabel({
        isLoading: input.livermoreSectorRankSeriesIsLoading,
        isError: input.livermoreSectorRankSeriesIsError,
        hasData: Boolean(input.livermoreSectorRankSeries),
      }),
      count: `${livermoreSectorSeriesRows} points`,
      date:
        input.livermoreSectorRankSeries?.as_of_date ??
        resultMetaBusinessDate(input.livermoreSectorRankSeriesMeta),
      note: "sector momentum path",
    },
    {
      key: "livermore-candidate-history",
      tone: endpointTone({
        isLoading: input.livermoreCandidateHistoryIsLoading,
        isError: input.livermoreCandidateHistoryIsError,
        hasData: Boolean(input.livermoreCandidateHistory),
      }),
      label: "Candidate History",
      endpoint: "/ui/market-data/livermore/candidate-history",
      status: endpointStatusLabel({
        isLoading: input.livermoreCandidateHistoryIsLoading,
        isError: input.livermoreCandidateHistoryIsError,
        hasData: Boolean(input.livermoreCandidateHistory),
      }),
      count: `${livermoreCandidateHistoryRows} rows`,
      date: livermoreCandidateHistoryDate,
      note: "candidate replay window",
    },
    {
      key: "livermore-strategy-optimization",
      tone: endpointTone({
        isLoading: input.livermoreStrategyOptimizationIsLoading,
        isError: input.livermoreStrategyOptimizationIsError,
        hasData: Boolean(input.livermoreStrategyOptimization),
      }),
      label: "Strategy Optimization",
      endpoint: "/ui/market-data/livermore/strategy-optimization",
      status: endpointStatusLabel({
        isLoading: input.livermoreStrategyOptimizationIsLoading,
        isError: input.livermoreStrategyOptimizationIsError,
        hasData: Boolean(input.livermoreStrategyOptimization),
      }),
      count: `${livermoreOptimizationRecs} recs`,
      date:
        input.livermoreStrategyOptimization?.snapshot_to ??
        input.livermoreStrategyOptimization?.as_of_date ??
        resultMetaBusinessDate(input.livermoreStrategyOptimizationMeta),
      note: "strategy and slice review",
    },
    {
      key: "livermore-cycle-proxy-backtest",
      tone: endpointTone({
        isLoading: input.livermoreCycleProxyBacktestIsLoading,
        isError: input.livermoreCycleProxyBacktestIsError,
        hasData: Boolean(input.livermoreCycleProxyBacktest),
      }),
      label: "Cycle Proxy Backtest",
      endpoint: "/ui/market-data/livermore/cycle-proxy-backtest",
      status: endpointStatusLabel({
        isLoading: input.livermoreCycleProxyBacktestIsLoading,
        isError: input.livermoreCycleProxyBacktestIsError,
        hasData: Boolean(input.livermoreCycleProxyBacktest),
      }),
      count: `${livermoreCycleNavPoints} nav`,
      date:
        input.livermoreCycleProxyBacktest?.snapshot_to ??
        resultMetaBusinessDate(input.livermoreCycleProxyBacktestMeta),
      note: "proxy cycle replay",
    },
    {
      key: "livermore-portfolio-backtest",
      tone: endpointTone({
        isLoading: input.livermorePortfolioBacktestIsLoading,
        isError: input.livermorePortfolioBacktestIsError,
        hasData: Boolean(input.livermorePortfolioBacktest),
      }),
      label: "Portfolio Proxy",
      endpoint: "/ui/market-data/livermore/candidate-history-portfolio-backtest",
      status: endpointStatusLabel({
        isLoading: input.livermorePortfolioBacktestIsLoading,
        isError: input.livermorePortfolioBacktestIsError,
        hasData: Boolean(input.livermorePortfolioBacktest),
      }),
      count: `${livermorePortfolioRebalances} rebal`,
      date:
        input.livermorePortfolioBacktest?.snapshot_to ??
        resultMetaBusinessDate(input.livermorePortfolioBacktestMeta),
      note: "portfolio proxy replay",
    },
  ];
  const sourceGapRows: MarketDataOverviewSourceGap[] = [
    ...(input.terminalModel.bondFutures.status === "source-pending"
      ? [
          {
            key: "bond-futures-rankings",
            label: "国债期货排名",
            subLabel: "会员排名",
            badge: "部分缺失",
            code: "未接入",
            status: "暂不可用于正式决策",
          },
        ]
      : []),
    ...(input.terminalModel.bondTrades.status === "source-pending"
      ? [
          {
            key: "cash-bond-trades",
            label: "现券成交",
            subLabel: "成交明细",
            badge: "部分缺失",
            code: "未接入",
            status: "暂不可用于正式决策",
          },
        ]
      : []),
    ...(input.terminalModel.creditTrades.status === "source-pending"
      ? [
          {
            key: "credit-trades",
            label: "信用成交",
            subLabel: "信用成交明细",
            badge: "部分缺失",
            code: "未接入",
            status: "暂不可用于正式决策",
          },
        ]
      : []),
  ];

  return {
    topbarUpdatedAt,
    ratesBasisText,
    formalUseAllowedLabel,
    newsCalendarStatus,
    overviewStats: [
      { key: "formal", tone: "formal", label: "正式可用", value: "6", unit: "", detail: "可用于当前观察" },
      { key: "analytical", tone: "analytical", label: "仅分析使用", value: String(analyticalUseCount + livermoreDeepEndpointReadCount + supplementalEndpointReadCount), unit: "", detail: "需复核后使用" },
      { key: "proxy", tone: "proxy", label: "代理数据", value: String(proxyFallbackCount), unit: "", detail: "不作正式结论" },
      { key: "gap", tone: "gap", label: "数据缺口", value: String(sourceGapRows.length), unit: "", detail: "查看数据诊断" },
      { key: "coverage", tone: "neutral", label: "覆盖指标", value: formalRatesCountText, unit: "Series", detail: "" },
      { key: "catalog", tone: "neutral", label: "目录", value: String(input.catalog.length), unit: "Series", detail: "" },
      { key: "latest", tone: "neutral", label: "最新点", value: String(input.latestSeries.length), unit: "Series", detail: "" },
      { key: "date", tone: "neutral", label: "数据最新", value: dataLatestDate, unit: "多数组度", detail: "" },
    ],
    keyRateTiles: [
      { key: "cgb10y", label: "10Y 国债", value: cgb10y?.rateText ?? EM_DASH, delta: cgb10y?.deltaText ?? EM_DASH },
      { key: "cgb5y", label: "5Y 国债", value: cgb5y?.rateText ?? EM_DASH, delta: cgb5y?.deltaText ?? EM_DASH },
      { key: "dr007", label: "DR007", value: dr007?.rateText ?? EM_DASH, delta: dr007?.deltaText ?? EM_DASH },
      { key: "shibor3m", label: "SHIBOR 3M", value: shibor3m?.rateText ?? EM_DASH, delta: shibor3m?.deltaText ?? EM_DASH },
    ],
    moneyRows: input.terminalModel.moneyMarket.rows.slice(0, 4),
    fundingCurveSeries,
    fxRows,
    macroLatestRows,
    ncdProxyRows,
    livermoreDeepRows,
    tushareSupplementRows,
    tushareSignalTiles,
    externalComparisonPlacements,
    macroToolkitRows,
    endpointCoverageRows,
    formalDomainRows: [
      {
        key: "formal-rates",
        tone: "formal",
        lane: "正式利率",
        subLabel: "曲线 / 资金",
        status: "正式可用",
        count: `${formalRatesCountText} series`,
        date: formalRatesDisplayDate,
        note: `${ratesBasisText}；正式使用 ${formalUseAllowedLabel}`,
      },
      {
        key: "catalog",
        tone: "formal",
        lane: "市场目录",
        subLabel: "序列清单",
        status: "正式可用",
        count: `${input.catalog.length} series`,
        date: input.watchDate || dataLatestDate,
        note: `稳定 ${catalogStableCount} / 延迟 ${catalogFallbackCount}`,
      },
      {
        key: "fx-formal",
        tone: input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? "proxy" : "formal",
        lane: "外汇正式片段",
        subLabel: "外汇状态",
        status: "正式可用",
        count: `${fxFormalMaterialized} / ${fxFormalCandidates} candidates`,
        date: input.fxFormalStatus?.latest_trade_date ?? resultMetaBusinessDate(input.fxFormalMeta),
        note: input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? "数据延迟" : "数据正常",
      },
      {
        key: "news",
        tone: "formal",
        lane: "资讯事件",
        subLabel: "最新资讯",
        status: endpointStatusLabel({
          isLoading: input.newsIsLoading,
          isError: input.newsIsError,
          hasData: Boolean(input.newsPayload),
        }),
        count: `${newsTotalRows} total`,
        date: input.watchDate || dataLatestDate,
        note: input.newsIsLoading ? "接入中" : "市场事件流",
      },
      {
        key: "calendar",
        tone: "formal",
        lane: "供给日历",
        subLabel: "招标 / 供给",
        status: endpointStatusLabel({
          isLoading: input.calendarIsLoading,
          isError: input.calendarIsError,
          hasData: input.calendarRows.length > 0,
        }),
        count: `${input.calendarRows.length} events`,
        date: input.watchDate || dataLatestDate,
        note: "公告事件",
      },
      {
        key: "research-calendar",
        tone: "formal",
        lane: "研究日历",
        subLabel: "宏观 + 供给",
        status: endpointStatusLabel({
          isLoading: input.calendarIsLoading,
          isError: input.calendarIsError,
          hasData: input.calendarRows.length + fxEventCount > 0,
        }),
        count: `${input.calendarRows.length + fxEventCount} events`,
        date: input.watchDate || dataLatestDate,
        note: "宏观与供给事件",
      },
    ],
    analyticalRows: [
      {
        key: "macro-latest",
        tone: "analytical",
        label: "宏观最新点",
        subLabel: "Choice 最新值",
        badge: "仅分析使用",
        count: `${input.latestSeries.length} series`,
        date: input.watchDate || dataLatestDate,
        note: `数据正常 ${latestStableCount} / 数据延迟 ${latestFallbackCount}`,
      },
      {
        key: "fx-analytical",
        tone: "analytical",
        label: "外汇分析",
        subLabel: "外汇分组",
        badge: "仅分析使用",
        count: `${input.fxAnalyticalGroups.length} groups / ${fxAnalyticalSeriesCount} rows`,
        date: input.watchDate || dataLatestDate,
        note: "不可用于正式决策",
      },
      {
        key: "livermore",
        tone: "analytical",
        label: "Livermore Strategy",
        subLabel: "Livermore Analytical",
        badge: livermoreBadge,
        count: livermoreCount,
        date: input.livermoreStrategy?.asOfDate ?? input.watchDate ?? dataLatestDate,
        note: livermoreNote,
      },
      {
        key: "tushare-supplement",
        tone: "analytical",
        label: "Tushare Macro",
        subLabel: "Money Supply / Eco Calendar",
        badge: endpointStatusLabel({
          isLoading: input.tushareSupplementIsLoading,
          isError: input.tushareSupplementIsError,
          hasData: Boolean(input.tushareSupplement),
        }),
        count: `${tushareMoneyRows + tushareEcoRows} rows`,
        date: tushareSupplementDate,
        note: "仅分析使用",
      },
      {
        key: "macro-toolkit-core",
        tone: "analytical",
        label: "Macro Toolkit",
        subLabel: "Core Analysis",
        badge: endpointStatusLabel({
          isLoading: input.macroToolkitAnalysisIsLoading,
          isError: input.macroToolkitAnalysisIsError,
          hasData: Boolean(input.macroToolkitAnalysis),
        }),
        count: `${macroToolkitHitCount}/${macroToolkitIndicatorCount} indicators`,
        date: macroToolkitDate,
        note: input.macroToolkitAnalysis?.conclusion.summary ?? "仅分析使用",
      },
      {
        key: "ncd-proxy",
        tone: "proxy",
        label: "存单资金代理",
        subLabel: "NCD 代理",
        badge: "代理数据",
        count: `${input.ncdFundingProxy?.rows.length ?? 0} rows`,
        date: input.ncdFundingProxy?.as_of_date ?? resultMetaBusinessDate(input.ncdFundingProxyMeta),
        note: input.ncdFundingProxy?.is_actual_ncd_matrix ? "正式矩阵" : "代理数据，不作正式结论",
      },
    ],
    sourceGapRows,
    newsEventRows: newsRows.map((event) => ({
      key: `news-${event.event_key}`,
      time: formatPreviewTime(event.received_at),
      label: "资讯",
      text: summarizeChoiceNewsEvent(event),
    })),
    calendarEventRows: calendarPreviewRows.map((event) => ({
      key: `calendar-${event.id}`,
      time: event.date,
      label: calendarKindShortLabel(event.kind),
      text: `${event.title}${event.amount_label ? ` / ${event.amount_label}` : ""} / ${calendarSeverityShortLabel(
        event.severity,
      )}`,
    })),
    sourceLedgerRows: [
      {
        key: "formal-rates",
        source: "中债 (CBEX)",
        product: "BondAPI / Yield Curve",
        domain: "利率 / 债券收益率",
        endpoint: "/ui/market-data/rates",
        basis: ratesBasisText,
        formalAllowed: formalUseAllowedLabel,
        quality: resultMetaQualityLabel(input.formalRatesMeta?.quality_flag ?? input.terminalModel.rateQuotes.source?.qualityFlag),
        fallback: resultMetaFallbackLabel(input.formalRatesMeta?.fallback_mode ?? input.terminalModel.rateQuotes.source?.fallbackMode),
        latest: formalRatesDisplayDate,
        date: input.watchDate || formalRatesDisplayDate,
        note: "正式可用",
      },
      {
        key: "catalog",
        source: "中债 (CBEX)",
        product: "系列目录",
        domain: "市场目录",
        endpoint: "/ui/market-data/catalog",
        basis: marketDataBasisLabel(input.formalRatesMeta?.basis),
        formalAllowed: "是",
        quality: "数据正常",
        fallback: "数据正常",
        latest: dataLatestDate,
        date: input.watchDate || dataLatestDate,
        note: "正式可用",
      },
      {
        key: "macro-latest",
        source: "Choice 宏观",
        product: "宏观最新点",
        domain: "宏观观察点",
        endpoint: "/ui/macro/choice-series/latest",
        basis: "分析",
        formalAllowed: "否",
        quality: macroLatestQuality,
        fallback: "不可正式口径",
        latest: latestTradeDate(input.latestSeries, input.watchDate || dataLatestDate),
        date: input.watchDate || dataLatestDate,
        note: macroLatestNote,
      },
      {
        key: "fx-formal",
        source: "Choice 外汇",
        product: "外汇正式片段",
        domain: "FX Spot",
        endpoint: "/ui/market-data/fx/formal-status",
        basis: marketDataBasisLabel(input.fxFormalMeta?.basis),
        formalAllowed: formalUseAllowedText(input.fxFormalMeta?.formal_use_allowed),
        quality: resultMetaQualityLabel(input.fxFormalMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.fxFormalMeta?.fallback_mode),
        latest: input.fxFormalStatus?.latest_trade_date ?? resultMetaBusinessDate(input.fxFormalMeta),
        date: input.watchDate || dataLatestDate,
        note: input.fxFormalMeta?.fallback_mode === "latest_snapshot" ? "数据延迟" : "正式可用",
      },
      {
        key: "fx-analytical",
        source: "Choice 外汇",
        product: "外汇分析",
        domain: "FX Analytical",
        endpoint: "/ui/market-data/fx/analytical",
        basis: marketDataBasisLabel(input.fxAnalyticalMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.fxAnalyticalMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.fxAnalyticalMeta?.fallback_mode),
        latest: resultMetaBusinessDate(input.fxAnalyticalMeta),
        date: input.watchDate || dataLatestDate,
        note: "分析仅用",
      },
      {
        key: "ncd-proxy",
        source: "Choice 资金",
        product: "NCD 资金代理",
        domain: "资金代理",
        endpoint: "/ui/market-data/ncd-funding-proxy",
        basis: marketDataBasisLabel(input.ncdFundingProxyMeta?.basis),
        formalAllowed: input.ncdFundingProxy?.is_actual_ncd_matrix ? "是" : "否",
        quality: resultMetaQualityLabel(input.ncdFundingProxyMeta?.quality_flag),
        fallback: input.ncdFundingProxy?.is_actual_ncd_matrix ? "数据正常" : "代理数据",
        latest: input.ncdFundingProxy?.as_of_date ?? resultMetaBusinessDate(input.ncdFundingProxyMeta),
        date: input.watchDate || dataLatestDate,
        note: "非 NCD 矩阵",
      },
      {
        key: "tushare-supplement",
        source: "Tushare",
        product: "Money Supply / Eco Calendar",
        domain: "Macro Supplement",
        endpoint: "/ui/market-data/tushare-supplement",
        basis: marketDataBasisLabel(input.tushareSupplementMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.tushareSupplementMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.tushareSupplementMeta?.fallback_mode),
        latest: tushareSupplementDate,
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.tushareSupplementIsLoading,
          isError: input.tushareSupplementIsError,
          hasData: Boolean(input.tushareSupplement),
        }),
      },
      {
        key: "macro-toolkit-core",
        source: "MOSS Macro Toolkit",
        product: "Core Analysis",
        domain: "Macro Signals",
        endpoint: "/ui/macro/toolkit/analysis?detail=core",
        basis: marketDataBasisLabel(input.macroToolkitAnalysisMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.macroToolkitAnalysisMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.macroToolkitAnalysisMeta?.fallback_mode),
        latest: macroToolkitDate,
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.macroToolkitAnalysisIsLoading,
          isError: input.macroToolkitAnalysisIsError,
          hasData: Boolean(input.macroToolkitAnalysis),
        }),
      },
      {
        key: "news",
        source: "Choice 资讯",
        product: "资讯事件",
        domain: "事件流",
        endpoint: "/ui/news/choice-events/latest",
        basis: "分析",
        formalAllowed: "是",
        quality: input.newsIsError ? "技术异常" : "数据正常",
        fallback: "数据正常",
        latest: input.watchDate || dataLatestDate,
        date: input.watchDate || dataLatestDate,
        note: "正式可用",
      },
      {
        key: "calendar",
        source: "Choice 日历",
        product: "供给 / 招标",
        domain: "公告",
        endpoint: "/ui/calendar/supply-auctions",
        basis: "分析",
        formalAllowed: "是",
        quality: input.calendarIsError ? "技术异常" : "数据正常",
        fallback: "数据正常",
        latest: input.watchDate || dataLatestDate,
        date: input.watchDate || dataLatestDate,
        note: "正式可用",
      },
      {
        key: "livermore",
        source: "Choice 策略",
        product: "Livermore 策略",
        domain: "策略计算",
        endpoint: "/ui/market-data/livermore",
        basis: marketDataBasisLabel(input.livermoreMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreMeta?.fallback_mode),
        latest: input.livermoreStrategy?.asOfDate ?? input.watchDate ?? dataLatestDate,
        date: input.watchDate || dataLatestDate,
        note: "分析仅用",
      },
      {
        key: "livermore-signal",
        source: "Choice Strategy",
        product: "Signal Confluence",
        domain: "Livermore Analytics",
        endpoint: "/ui/market-data/livermore/signal-confluence",
        basis: marketDataBasisLabel(input.livermoreSignalConfluenceMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreSignalConfluenceMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreSignalConfluenceMeta?.fallback_mode),
        latest:
          input.livermoreSignalConfluence?.as_of_date ??
          resultMetaBusinessDate(input.livermoreSignalConfluenceMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreSignalConfluenceIsLoading,
          isError: input.livermoreSignalConfluenceIsError,
          hasData: Boolean(input.livermoreSignalConfluence),
        }),
      },
      {
        key: "livermore-score",
        source: "Choice Strategy",
        product: "Strategy Score",
        domain: "Replay Analytics",
        endpoint: "/ui/market-data/livermore/strategy-score",
        basis: marketDataBasisLabel(input.livermoreStrategyScoreMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreStrategyScoreMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreStrategyScoreMeta?.fallback_mode),
        latest: input.livermoreStrategyScore?.as_of_date ?? resultMetaBusinessDate(input.livermoreStrategyScoreMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreStrategyScoreIsLoading,
          isError: input.livermoreStrategyScoreIsError,
          hasData: Boolean(input.livermoreStrategyScore),
        }),
      },
      {
        key: "livermore-sector-series",
        source: "Choice Strategy",
        product: "Sector Rank Series",
        domain: "Sector Momentum",
        endpoint: "/ui/market-data/livermore/sector-rank-series",
        basis: marketDataBasisLabel(input.livermoreSectorRankSeriesMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreSectorRankSeriesMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreSectorRankSeriesMeta?.fallback_mode),
        latest:
          input.livermoreSectorRankSeries?.as_of_date ??
          resultMetaBusinessDate(input.livermoreSectorRankSeriesMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreSectorRankSeriesIsLoading,
          isError: input.livermoreSectorRankSeriesIsError,
          hasData: Boolean(input.livermoreSectorRankSeries),
        }),
      },
      {
        key: "livermore-candidate-history",
        source: "Choice Strategy",
        product: "Candidate History",
        domain: "Replay Analytics",
        endpoint: "/ui/market-data/livermore/candidate-history",
        basis: marketDataBasisLabel(input.livermoreCandidateHistoryMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreCandidateHistoryMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreCandidateHistoryMeta?.fallback_mode),
        latest: livermoreCandidateHistoryDate,
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreCandidateHistoryIsLoading,
          isError: input.livermoreCandidateHistoryIsError,
          hasData: Boolean(input.livermoreCandidateHistory),
        }),
      },
      {
        key: "livermore-strategy-optimization",
        source: "Choice Strategy",
        product: "Strategy Optimization",
        domain: "Replay Analytics",
        endpoint: "/ui/market-data/livermore/strategy-optimization",
        basis: marketDataBasisLabel(input.livermoreStrategyOptimizationMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreStrategyOptimizationMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreStrategyOptimizationMeta?.fallback_mode),
        latest:
          input.livermoreStrategyOptimization?.snapshot_to ??
          input.livermoreStrategyOptimization?.as_of_date ??
          resultMetaBusinessDate(input.livermoreStrategyOptimizationMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreStrategyOptimizationIsLoading,
          isError: input.livermoreStrategyOptimizationIsError,
          hasData: Boolean(input.livermoreStrategyOptimization),
        }),
      },
      {
        key: "livermore-cycle-proxy-backtest",
        source: "Choice Strategy",
        product: "Cycle Proxy Backtest",
        domain: "Proxy Backtest",
        endpoint: "/ui/market-data/livermore/cycle-proxy-backtest",
        basis: marketDataBasisLabel(input.livermoreCycleProxyBacktestMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermoreCycleProxyBacktestMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermoreCycleProxyBacktestMeta?.fallback_mode),
        latest:
          input.livermoreCycleProxyBacktest?.snapshot_to ??
          resultMetaBusinessDate(input.livermoreCycleProxyBacktestMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermoreCycleProxyBacktestIsLoading,
          isError: input.livermoreCycleProxyBacktestIsError,
          hasData: Boolean(input.livermoreCycleProxyBacktest),
        }),
      },
      {
        key: "livermore-portfolio-backtest",
        source: "Choice Strategy",
        product: "Portfolio Proxy Backtest",
        domain: "Proxy Backtest",
        endpoint: "/ui/market-data/livermore/candidate-history-portfolio-backtest",
        basis: marketDataBasisLabel(input.livermorePortfolioBacktestMeta?.basis),
        formalAllowed: "否",
        quality: resultMetaQualityLabel(input.livermorePortfolioBacktestMeta?.quality_flag),
        fallback: resultMetaFallbackLabel(input.livermorePortfolioBacktestMeta?.fallback_mode),
        latest:
          input.livermorePortfolioBacktest?.snapshot_to ??
          resultMetaBusinessDate(input.livermorePortfolioBacktestMeta),
        date: input.watchDate || dataLatestDate,
        note: endpointStatusLabel({
          isLoading: input.livermorePortfolioBacktestIsLoading,
          isError: input.livermorePortfolioBacktestIsError,
          hasData: Boolean(input.livermorePortfolioBacktest),
        }),
      },
    ],
  };
}
