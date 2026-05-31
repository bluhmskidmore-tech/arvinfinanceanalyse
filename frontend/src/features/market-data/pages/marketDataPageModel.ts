import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  FxAnalyticalPayload,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
  MacroVendorPayload,
  ResultMeta,
} from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
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
  type MarketDataTerminalModel,
} from "../lib/marketDataTerminalModel";

export type SpreadTenorSlot = "3Y" | "5Y" | "10Y";

const SPREAD_TENOR_SLOTS: SpreadTenorSlot[] = ["3Y", "5Y", "10Y"];

type SpreadSlot = {
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
  fxAnalyticalMeta: ResultMeta | undefined;
  ncdFundingProxyMeta: ResultMeta | undefined;
  rateQuotesSource: MarketDataTerminalModel["rateQuotes"]["source"];
  sourcePendingCount: number;
  isFormalBasis: boolean;
  statusBadges: MarketDataStatusBadges;
  evidenceLines: MarketDataEvidenceLines;
  overviewMetrics: MarketOverviewMetric[];
};

type BuildMarketDataPageModelInput = {
  catalogEnvelope?: ApiEnvelope<MacroVendorPayload>;
  latestEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
  fxAnalyticalEnvelope?: ApiEnvelope<FxAnalyticalPayload>;
  formalRatesEnvelope?: ApiEnvelope<ChoiceMacroLatestPayload>;
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
    color: [
      designTokens.color.info[500],
      designTokens.color.semantic.up,
      designTokens.color.warning[400],
    ],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 52, right: 20, top: 28, bottom: 52 },
    xAxis: { type: "category", boundaryGap: false, data: categories },
    yAxis: {
      type: "value",
      scale: true,
      name: unit || undefined,
      axisLabel: { formatter: "{value}" },
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

function buildSpreadSlots(
  topCorrelations: MacroBondLinkageTopCorrelation[] | undefined,
): SpreadSlot[] {
  return SPREAD_TENOR_SLOTS.map((tenor) => ({
    tenor,
    point:
      (topCorrelations ?? [])
        .filter((item) => item.target_family === "credit_spread" && item.target_tenor === tenor)
        .sort((left, right) => correlationStrength(right) - correlationStrength(left))[0] ?? null,
  }));
}

function buildOverviewMetrics(input: {
  catalogCount: number;
  categoryStore: MarketDataCategoryStore;
  fxAnalyticalGroupCount: number;
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
      testId: "market-data-fx-analytical-group-count",
      title: "外汇观察分组",
      value: String(input.fxAnalyticalGroupCount),
      detail: "后端返回的分析口径外汇分组数量。",
    },
    {
      testId: "market-data-fx-analytical-series-count",
      title: "外汇观察序列",
      value: String(categoryStore.fxAnalyticalSeriesCount),
      detail: "分析口径外汇观察值与正式外汇状态保持分离。",
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
  fxAnalyticalMeta?: ResultMeta;
  ncdFundingProxyMeta?: ResultMeta;
  livermoreMeta?: ResultMeta;
  macroBondLinkageMeta?: ResultMeta;
}): MarketDataEvidenceLines {
  return {
    formalRates: metaEvidenceLine("formal rates", input.formalRatesMeta),
    macroLatest: metaEvidenceLine("macro latest", input.latestMeta),
    fxAnalytical: metaEvidenceLine("FX analytical", input.fxAnalyticalMeta),
    ncdProxy: metaEvidenceLine("NCD proxy", input.ncdFundingProxyMeta),
    livermore: metaEvidenceLine("Livermore", input.livermoreMeta),
    linkage: metaEvidenceLine("macro-bond linkage", input.macroBondLinkageMeta),
  };
}

export function buildMarketDataPageModel(input: BuildMarketDataPageModelInput): MarketDataPageModel {
  const catalog = input.catalogEnvelope?.result.series ?? [];
  const latestSeries = input.latestEnvelope?.result.series ?? [];
  const fxAnalyticalGroups = input.fxAnalyticalEnvelope?.result.groups ?? [];
  const terminalModel = buildMarketDataTerminalModel({
    ratesEnvelope: input.formalRatesEnvelope,
    latestEnvelope: input.latestEnvelope,
  });
  const categoryStore = buildMarketDataCategoryStore({
    catalog,
    latestSeries,
    fxAnalyticalGroups,
  });
  const macroBondLinkage: Partial<MacroBondLinkagePayload> = input.macroBondLinkageEnvelope?.result ?? {};
  const spreadSlots = buildSpreadSlots(macroBondLinkage.top_correlations);
  const formalRatesMeta = input.formalRatesEnvelope?.result_meta;
  const macroMeta =
    formalRatesMeta ?? input.latestEnvelope?.result_meta ?? input.catalogEnvelope?.result_meta;
  const sourcePendingCount = [
    terminalModel.bondFutures.status,
    terminalModel.bondTrades.status,
    terminalModel.creditTrades.status,
  ].filter((status) => status === "source-pending").length;

  return {
    ...categoryStore,
    catalog,
    latestSeries,
    fxAnalyticalGroups,
    terminalModel,
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
    fxAnalyticalMeta: input.fxAnalyticalEnvelope?.result_meta,
    ncdFundingProxyMeta: input.ncdFundingProxyMeta,
    rateQuotesSource: terminalModel.rateQuotes.source,
    sourcePendingCount,
    isFormalBasis: formalRatesMeta?.basis === "formal" && formalRatesMeta.formal_use_allowed === true,
    statusBadges: {
      readinessVerdict: macroMeta?.quality_flag === "error" ? "读面异常" : "读面就绪",
      overviewReadinessLabel: "读面就绪",
      secondaryLabel: "辅助观察",
    },
    evidenceLines: buildEvidenceLines({
      formalRatesMeta,
      latestMeta: input.latestEnvelope?.result_meta,
      fxAnalyticalMeta: input.fxAnalyticalEnvelope?.result_meta,
      ncdFundingProxyMeta: input.ncdFundingProxyMeta,
      livermoreMeta: input.livermoreStrategyEnvelope?.result_meta,
      macroBondLinkageMeta: input.macroBondLinkageEnvelope?.result_meta,
    }),
    overviewMetrics: buildOverviewMetrics({
      catalogCount: catalog.length,
      categoryStore,
      fxAnalyticalGroupCount: fxAnalyticalGroups.length,
    }),
  };
}

export function metaEvidenceLine(label: string, meta: ResultMeta | undefined) {
  if (!meta) {
    return `${label}: basis=pending formal_use_allowed=pending quality=pending fallback=pending vendor_status=pending source=pending`;
  }
  return `${label}: basis=${meta.basis} formal_use_allowed=${meta.formal_use_allowed} quality=${meta.quality_flag} fallback=${meta.fallback_mode} vendor_status=${meta.vendor_status} source=${meta.source_version}`;
}
