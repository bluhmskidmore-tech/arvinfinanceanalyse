import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  FxAnalyticalPayload,
  FxFormalStatusPayload,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  MarketDataBondFuturesRankingsPayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  MacroVendorPayload,
  ResultMeta,
} from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { ibTokens } from "../../../theme/designSystem";
import type { MarketOverviewMetric } from "./MarketDataHeroSection";
import { RATE_TREND_DEFINITIONS } from "./marketDataMacroConstants";
import {
  buildMarketDataCategoryStore,
  type MarketDataCategoryStore,
} from "../lib/marketDataCategoryStore";
import {
  buildLivermoreStrategyModel,
  type LivermoreStrategyModel,
} from "../lib/livermoreStrategyModel";
import {
  buildMarketDataTerminalModel,
  buildTerminalTickerItems,
  type MarketCreditSegmentFilter,
  type MarketDataTerminalModel,
  type MarketTerminalTickerItem,
} from "../lib/marketDataTerminalModel";

export type SpreadTenorSlot = "3Y" | "5Y" | "10Y";
export type { MarketCreditSegmentFilter };

const SPREAD_TENOR_SLOTS: SpreadTenorSlot[] = ["3Y", "5Y", "10Y"];

export type SpreadSlot = {
  tenor: SpreadTenorSlot;
  point: MacroBondLinkageTopCorrelation | null;
};

export type MarketDataStatusBadges = {
  readinessVerdict: string;
  overviewReadinessLabel: string;
  secondaryLabel: string;
};

export type MarketDataEvidenceLines = {
  formalRates: string;
  macroLatest: string;
  fxFormal: string;
  fxAnalytical: string;
  ncdProxy: string;
  livermore: string;
  linkage: string;
};

export type MarketDataPageModel = MarketDataCategoryStore & {
  catalog: MacroVendorPayload["series"];
  latestSeries: ChoiceMacroLatestPoint[];
  fxAnalyticalGroups: FxAnalyticalPayload["groups"];
  terminalModel: MarketDataTerminalModel;
  coverageSummary: MarketDataCoverageSummaryPayload | null;
  coverageSections: MarketDataCoverageSection[];
  rateTrendChartOption: EChartsOption | null;
  livermoreStrategy: LivermoreStrategyModel | null;
  macroBondLinkage: Partial<MacroBondLinkagePayload>;
  macroBondLinkageMeta: ResultMeta | undefined;
  macroBondLinkageWarnings: string[];
  hasPortfolioImpact: boolean;
  spreadSlots: SpreadSlot[];
  nonSpreadTopCorrelations: MacroBondLinkageTopCorrelation[];
  macroMeta: ResultMeta | undefined;
  formalRatesMeta: ResultMeta | undefined;
  fxFormalStatus: FxFormalStatusPayload | null;
  fxFormalMeta: ResultMeta | undefined;
  fxAnalyticalMeta: ResultMeta | undefined;
  ncdFundingProxyMeta: ResultMeta | undefined;
  rateQuotesSource: MarketDataTerminalModel["rateQuotes"]["source"];
  sourcePendingCount: number;
  isFormalBasis: boolean;
  statusBadges: MarketDataStatusBadges;
  evidenceLines: MarketDataEvidenceLines;
  terminalTickerItems: MarketTerminalTickerItem[];
  terminalKpiMetrics: MarketOverviewMetric[];
  pipelineOverviewMetrics: MarketOverviewMetric[];
};

type BuildMarketDataPageModelInput = {
  catalogEnvelope?: ApiEnvelope<MacroVendorPayload>;
  latestEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  fxAnalyticalEnvelope?: ApiEnvelope<FxAnalyticalPayload>;
  fxFormalStatusEnvelope?: ApiEnvelope<FxFormalStatusPayload>;
  formalRatesEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  bondFuturesRankingsEnvelope?: ApiEnvelope<MarketDataBondFuturesRankingsPayload>;
  coverageSummaryEnvelope?: ApiEnvelope<MarketDataCoverageSummaryPayload>;
  macroBondLinkageEnvelope?: ApiEnvelope<MacroBondLinkagePayload>;
  livermoreStrategyEnvelope?: Parameters<typeof buildLivermoreStrategyModel>[0]["envelope"];
  ncdFundingProxyMeta?: ResultMeta;
};

function recentTimelineForMacroPoint(point: ChoiceMacroLatestPoint | undefined) {
  const map = new Map<string, number>();
  if (!point) {
    return map;
  }
  for (const rp of point.recent_points ?? []) {
    map.set(rp.trade_date, rp.value_numeric);
  }
  return map;
}

export function buildMarketDataRateTrendChartOption(
  series: ChoiceMacroLatestPoint[],
): EChartsOption | null {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const dateSet = new Set<string>();
  const maps = RATE_TREND_DEFINITIONS.map((def) => {
    const timeline = recentTimelineForMacroPoint(byId.get(def.series_id));
    for (const d of timeline.keys()) {
      dateSet.add(d);
    }
    return timeline;
  });
  if (dateSet.size === 0) {
    return null;
  }
  let unit = "";
  for (const def of RATE_TREND_DEFINITIONS) {
    const p = byId.get(def.series_id);
    if (p?.unit) {
      unit = p.unit;
      break;
    }
  }
  const categories = [...dateSet].sort((a, b) => a.localeCompare(b));
  const lineSeries = RATE_TREND_DEFINITIONS.map((def, i) => ({
    name: def.name,
    type: "line" as const,
    smooth: true,
    showSymbol: categories.length <= 36,
    connectNulls: true,
    data: categories.map((d) => maps[i].get(d) ?? null),
  }));
  return {
    color: [ibTokens.color.accent, mossChartCategoricalPalette[2], ibTokens.color.gold],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, textStyle: { color: ibTokens.color.inkMuted } },
    grid: { left: 52, right: 20, top: 28, bottom: 52 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: categories,
      axisLabel: { color: ibTokens.color.inkMuted },
      axisLine: { lineStyle: { color: ibTokens.color.hairline } },
    },
    yAxis: {
      type: "value",
      scale: true,
      name: unit || undefined,
      axisLabel: { formatter: "{value}", color: ibTokens.color.inkMuted },
      splitLine: { lineStyle: { color: ibTokens.color.hairline } },
    },
    series: lineSeries,
  };
}

function correlationStrength(point: MacroBondLinkageTopCorrelation) {
  return Math.max(
    Math.abs(point.correlation_1y ?? 0),
    Math.abs(point.correlation_6m ?? 0),
    Math.abs(point.correlation_3m ?? 0),
  );
}

function creditSegmentMatches(seriesName: string, creditSegment: MarketCreditSegmentFilter): boolean {
  if (creditSegment === "both") {
    return true;
  }
  if (creditSegment === "mtn") {
    return seriesName.includes("中票");
  }
  return seriesName.includes("城投");
}

export function buildSpreadSlots(
  topCorrelations: MacroBondLinkageTopCorrelation[] | undefined,
  creditSegment: MarketCreditSegmentFilter = "both",
  spreadTenorCorrelations?: MacroBondLinkageTopCorrelation[] | undefined,
): SpreadSlot[] {
  const dedicatedPool = (spreadTenorCorrelations ?? []).filter(
    (item) =>
      item.target_family === "credit_spread" && creditSegmentMatches(item.series_name, creditSegment),
  );
  if (dedicatedPool.length > 0) {
    return SPREAD_TENOR_SLOTS.map((tenor) => ({
      tenor,
      point: dedicatedPool.find((item) => item.target_tenor === tenor) ?? null,
    }));
  }

  const spreadPool = (topCorrelations ?? []).filter(
    (item) =>
      item.target_family === "credit_spread" && creditSegmentMatches(item.series_name, creditSegment),
  );

  return SPREAD_TENOR_SLOTS.map((tenor) => ({
    tenor,
    point:
      spreadPool
        .filter((item) => item.target_tenor === tenor)
        .sort((left, right) => correlationStrength(right) - correlationStrength(left))[0] ?? null,
  }));
}

function terminalKpiTone(delta: string): MarketOverviewMetric["tone"] {
  if (delta.startsWith("+")) {
    return "negative";
  }
  if (delta.startsWith("-")) {
    return "positive";
  }
  return "default";
}

export function buildTerminalKpiMetricsFromTickerItems(
  items: MarketTerminalTickerItem[],
): MarketOverviewMetric[] {
  return items.map((item) => ({
    testId: `market-data-terminal-kpi-${item.key}`,
    title: item.label,
    value: item.value,
    detail: `${item.delta} · ${item.tradeDate} · ${item.seriesId}`,
    tone: terminalKpiTone(item.delta),
    valueVariant: "metric",
    sparklineValues: item.sparklineValues,
    sparklineTone: item.tone,
  }));
}

const BRIDGE_KPI_PRIORITY = [
  "market-data-terminal-kpi-cgb10y",
  "market-data-terminal-kpi-dr007",
  "market-data-terminal-kpi-cdb10y",
  "market-data-terminal-kpi-cgb5y",
] as const;

export function buildBridgeKpiMetrics(
  metrics: readonly MarketOverviewMetric[],
  options?: { maxItems?: number },
): MarketOverviewMetric[] {
  const maxItems = options?.maxItems ?? 4;
  const byTestId = new Map(metrics.map((metric) => [metric.testId, metric]));
  const picked: MarketOverviewMetric[] = [];

  for (const testId of BRIDGE_KPI_PRIORITY) {
    const metric = byTestId.get(testId);
    if (metric) {
      picked.push(metric);
    }
    if (picked.length >= maxItems) {
      return picked;
    }
  }

  for (const metric of metrics) {
    if (picked.some((item) => item.testId === metric.testId)) {
      continue;
    }
    picked.push(metric);
    if (picked.length >= maxItems) {
      break;
    }
  }

  return picked;
}

export function pickRailHighlightMetric(
  metrics: readonly MarketOverviewMetric[],
): MarketOverviewMetric | null {
  const dr007 = metrics.find((metric) => metric.testId.includes("dr007"));
  if (dr007) {
    return dr007;
  }
  return metrics[0] ?? null;
}

export function buildMarketDataBasisChipLabel(input: {
  basisLabel: string;
  formalUseAllowedLabel: string;
  formalUseBlocked: boolean;
  watchDate: string;
}): string {
  const allowed = input.formalUseBlocked ? "暂不可正式使用" : input.formalUseAllowedLabel;
  return `${input.basisLabel} · 正式使用 ${allowed} · 观察日 ${input.watchDate}`;
}

function buildTerminalKpiMetrics(terminalModel: MarketDataTerminalModel): MarketOverviewMetric[] {
  return buildTerminalKpiMetricsFromTickerItems(buildTerminalTickerItems(terminalModel));
}

export function buildFxFormalStatusCollapseLabel(input: {
  payload: FxFormalStatusPayload | null | undefined;
  isLoading: boolean;
  isError: boolean;
}): string {
  if (input.isLoading) {
    return "正式外汇中间价（加载中…）";
  }
  if (input.isError) {
    return "正式外汇中间价（加载失败，点击展开）";
  }
  const payload = input.payload;
  if (!payload) {
    return "正式外汇中间价（点击展开）";
  }
  return `正式外汇中间价 · 物化 ${payload.materialized_count}/${payload.candidate_count} · 沿用 ${payload.carry_forward_count}（点击展开）`;
}

function buildPipelineOverviewMetrics(input: {
  catalogCount: number;
  categoryStore: MarketDataCategoryStore;
  fxAnalyticalGroupCount: number;
  fxFormalStatus?: FxFormalStatusPayload | null;
  fxFormalMeta?: ResultMeta;
}): MarketOverviewMetric[] {
  const { categoryStore } = input;
  return [
    {
      testId: "market-data-catalog-count",
      title: "宏观序列目录",
      value: String(input.catalogCount),
      detail: "已登记的宏观序列数量。",
    },
    {
      testId: "market-data-stable-count",
      title: "稳定回收",
      value: `${categoryStore.stableSeries.length} / ${categoryStore.stableCatalogSeries.length}`,
      detail: "稳定主链路已回收 / 目录应有数量。",
      tone: categoryStore.stablePipelineTone,
    },
    {
      testId: "market-data-fallback-count",
      title: "降级可用",
      value: String(categoryStore.fallbackSeries.length),
      detail: "仅取最新 / 单次抓取降级链路中的序列数量。",
      tone: categoryStore.fallbackSeries.length > 0 ? "warning" : "default",
    },
    {
      testId: "market-data-stable-trade-date",
      title: "稳定最新日",
      value: categoryStore.stableLatestTradeDate,
      detail: "稳定主链路中可见序列的最大交易日期。",
      valueVariant: "text",
      tone: categoryStore.stableSeries.length === 0 ? "warning" : "default",
    },
    {
      testId: "market-data-missing-stable-count",
      title: "稳定缺口",
      value: String(categoryStore.missingStableSeries.length),
      detail: "目录中属于稳定主链路但当前尚未回收的序列数量。",
      tone:
        categoryStore.missingStableSeries.length > 5
          ? "error"
          : categoryStore.missingStableSeries.length > 0
            ? "warning"
            : "default",
    },
    {
      testId: "market-data-fx-formal-materialized",
      title: "正式外汇物化",
      value: `${input.fxFormalStatus?.materialized_count ?? 0} / ${input.fxFormalStatus?.candidate_count ?? 0}`,
      detail: `物化/候选对数 · 最新交易日 ${input.fxFormalStatus?.latest_trade_date ?? "—"} · 沿用 ${input.fxFormalStatus?.carry_forward_count ?? 0}`,
      tone:
        input.fxFormalMeta?.formal_use_allowed === false
          ? "warning"
          : (input.fxFormalStatus?.materialized_count ?? 0) === 0
            ? "warning"
            : "default",
    },
    {
      testId: "market-data-fx-analytical-group-count",
      title: "外汇观察分组",
      value: String(input.fxAnalyticalGroupCount),
      detail: "后端返回的分析口径外汇分组数量（与正式外汇状态分离）。",
    },
    {
      testId: "market-data-fx-analytical-series-count",
      title: "外汇观察条目",
      value: String(categoryStore.fxAnalyticalSeriesCount),
      detail: "分析口径外汇序列与事件背景均不进入正式外汇状态。",
    },
    {
      testId: "market-data-linkage-report-date",
      title: "联动报告日",
      value: categoryStore.linkageReportDate || "—",
      detail: "宏观-债市联动分析使用的报告日期。",
      valueVariant: "text",
      tone: categoryStore.linkageReportDate ? "default" : "warning",
    },
  ];
}

function buildEvidenceLines(input: {
  formalRatesMeta?: ResultMeta;
  latestMeta?: ResultMeta;
  fxFormalMeta?: ResultMeta;
  fxAnalyticalMeta?: ResultMeta;
  ncdFundingProxyMeta?: ResultMeta;
  livermoreMeta?: ResultMeta;
  macroBondLinkageMeta?: ResultMeta;
}): MarketDataEvidenceLines {
  return {
    formalRates: metaEvidenceLine("formal rates", input.formalRatesMeta),
    macroLatest: metaEvidenceLine("macro latest", input.latestMeta),
    fxFormal: metaEvidenceLine("FX formal", input.fxFormalMeta),
    fxAnalytical: metaEvidenceLine("FX analytical", input.fxAnalyticalMeta),
    ncdProxy: metaEvidenceLine("NCD proxy", input.ncdFundingProxyMeta),
    livermore: metaEvidenceLine("Livermore", input.livermoreMeta),
    linkage: metaEvidenceLine("macro-bond linkage", input.macroBondLinkageMeta),
  };
}

function buildStatusBadges(input: {
  formalRatesMeta?: ResultMeta;
  hasTerminalRows: boolean;
}): MarketDataStatusBadges {
  const { formalRatesMeta, hasTerminalRows } = input;
  if (!formalRatesMeta) {
    return {
      readinessVerdict: "接入中",
      overviewReadinessLabel: "待确认",
      secondaryLabel: "查看数据诊断",
    };
  }
  if (formalRatesMeta.quality_flag === "error") {
    return {
      readinessVerdict: "不可用",
      overviewReadinessLabel: "技术异常",
      secondaryLabel: "查看数据诊断",
    };
  }
  if (formalRatesMeta.formal_use_allowed === false) {
    return {
      readinessVerdict: "仅分析使用",
      overviewReadinessLabel: "暂不可正式使用",
      secondaryLabel: "不可用于正式决策",
    };
  }
  if (!hasTerminalRows) {
    return {
      readinessVerdict: "部分缺失",
      overviewReadinessLabel: "暂无数据",
      secondaryLabel: "查看数据诊断",
    };
  }
  if (formalRatesMeta.quality_flag === "stale") {
    return {
      readinessVerdict: "数据延迟",
      overviewReadinessLabel: "需刷新",
      secondaryLabel: "不可直接外推",
    };
  }
  if (formalRatesMeta.fallback_mode !== "none" || formalRatesMeta.vendor_status !== "ok") {
    return {
      readinessVerdict: "部分缺失",
      overviewReadinessLabel: "需复核",
      secondaryLabel: "保留来源提示",
    };
  }
  return {
    readinessVerdict: "数据正常",
    overviewReadinessLabel: "数据正常",
    secondaryLabel: "可用于当前观察",
  };
}

export function buildMarketDataPageModel(input: BuildMarketDataPageModelInput): MarketDataPageModel {
  const catalog = input.catalogEnvelope?.result.series ?? [];
  const latestSeries = input.latestEnvelope?.result.series ?? [];
  const fxAnalyticalGroups = input.fxAnalyticalEnvelope?.result.groups ?? [];
  const terminalModel = buildMarketDataTerminalModel({
    ratesEnvelope: input.formalRatesEnvelope,
    latestEnvelope: input.latestEnvelope,
    bondFuturesRankingsEnvelope: input.bondFuturesRankingsEnvelope,
  });
  const categoryStore = buildMarketDataCategoryStore({
    catalog,
    latestSeries,
    fxAnalyticalGroups,
  });
  const macroBondLinkage: Partial<MacroBondLinkagePayload> = input.macroBondLinkageEnvelope?.result ?? {};
  const spreadSlots = buildSpreadSlots(
    macroBondLinkage.top_correlations,
    "both",
    macroBondLinkage.spread_tenor_correlations,
  );
  const formalRatesMeta = input.formalRatesEnvelope?.result_meta;
  const fxFormalStatus = input.fxFormalStatusEnvelope?.result ?? null;
  const fxFormalMeta = input.fxFormalStatusEnvelope?.result_meta;
  const macroMeta =
    formalRatesMeta ?? input.latestEnvelope?.result_meta ?? input.catalogEnvelope?.result_meta;
  const inferredSourcePendingCount = [
    terminalModel.bondFutures.status,
    terminalModel.bondTrades.status,
    terminalModel.creditTrades.status,
  ].filter((status) => status === "source-pending").length;
  const coverageSummary = input.coverageSummaryEnvelope?.result ?? null;
  const coverageSections = coverageSummary?.sections ?? [];
  const sourcePendingCount =
    coverageSummary?.headline.source_pending_count ?? inferredSourcePendingCount;

  return {
    ...categoryStore,
    catalog,
    latestSeries,
    fxAnalyticalGroups,
    terminalModel,
    coverageSummary,
    coverageSections,
    rateTrendChartOption: buildMarketDataRateTrendChartOption(latestSeries),
    livermoreStrategy: input.livermoreStrategyEnvelope
      ? buildLivermoreStrategyModel({ envelope: input.livermoreStrategyEnvelope })
      : null,
    macroBondLinkage,
    macroBondLinkageMeta: input.macroBondLinkageEnvelope?.result_meta,
    macroBondLinkageWarnings: macroBondLinkage.warnings ?? [],
    hasPortfolioImpact: Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0,
    spreadSlots,
    nonSpreadTopCorrelations: (macroBondLinkage.top_correlations ?? []).filter(
      (item) => item.target_family !== "credit_spread",
    ),
    macroMeta,
    formalRatesMeta,
    fxFormalStatus,
    fxFormalMeta,
    fxAnalyticalMeta: input.fxAnalyticalEnvelope?.result_meta,
    ncdFundingProxyMeta: input.ncdFundingProxyMeta,
    rateQuotesSource: terminalModel.rateQuotes.source,
    sourcePendingCount,
    isFormalBasis: formalRatesMeta?.basis === "formal" && formalRatesMeta.formal_use_allowed === true,
    statusBadges: buildStatusBadges({
      formalRatesMeta,
      hasTerminalRows:
        terminalModel.rateQuotes.rows.length > 0 || terminalModel.moneyMarket.rows.length > 0,
    }),
    evidenceLines: buildEvidenceLines({
      formalRatesMeta,
      latestMeta: input.latestEnvelope?.result_meta,
      fxFormalMeta,
      fxAnalyticalMeta: input.fxAnalyticalEnvelope?.result_meta,
      ncdFundingProxyMeta: input.ncdFundingProxyMeta,
      livermoreMeta: input.livermoreStrategyEnvelope?.result_meta,
      macroBondLinkageMeta: input.macroBondLinkageEnvelope?.result_meta,
    }),
    terminalTickerItems: buildTerminalTickerItems(terminalModel),
    terminalKpiMetrics: buildTerminalKpiMetrics(terminalModel),
    pipelineOverviewMetrics: buildPipelineOverviewMetrics({
      catalogCount: catalog.length,
      categoryStore,
      fxAnalyticalGroupCount: fxAnalyticalGroups.length,
      fxFormalStatus,
      fxFormalMeta,
    }),
  };
}

export function metaEvidenceLine(label: string, meta: ResultMeta | undefined) {
  if (!meta) {
    return `${label}: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending`;
  }
  return `${label}: basis=${meta.basis} formal_use_allowed=${meta.formal_use_allowed} quality=${meta.quality_flag} fallback=${meta.fallback_mode} vendor_status=${meta.vendor_status} source=${meta.source_version}`;
}

/** 页头 meta 带来源摘要：避免多路 vendor 版本串成一行撑破布局。 */
export function formatMarketWorkbenchSourceSummary(
  vendorVersions: string[],
  fallback: string,
): { value: string; hint?: string } {
  if (vendorVersions.length === 0) {
    return { value: fallback };
  }
  if (vendorVersions.length === 1) {
    return { value: vendorVersions[0] };
  }
  const full = vendorVersions.join(" / ");
  return {
    value: `${vendorVersions.length} 路供应商版本`,
    hint: full,
  };
}
