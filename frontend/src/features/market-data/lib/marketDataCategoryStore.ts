import type {
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  FxAnalyticalSeriesPoint,
  MacroVendorSeries,
} from "../../../api/contracts";

export type MarketObservationPoint = ChoiceMacroLatestPoint | FxAnalyticalSeriesPoint;
type RefreshTier = "stable" | "fallback" | "isolated";

export type MarketDataCategoryStore = {
  visibleLatestSeries: ChoiceMacroLatestPoint[];
  stableSeries: ChoiceMacroLatestPoint[];
  fallbackSeries: ChoiceMacroLatestPoint[];
  stableCatalogSeries: MacroVendorSeries[];
  missingStableSeries: MacroVendorSeries[];
  stableLatestTradeDate: string;
  linkageReportDate: string;
  vendorVersions: string[];
  fxAnalyticalSeriesCount: number;
  stablePipelineTone: "default" | "warning" | "error";
};

export function marketSeriesRefreshTier(point: MarketObservationPoint): RefreshTier {
  return point.refresh_tier ?? "stable";
}

export function marketCatalogRefreshTier(series: MacroVendorSeries): RefreshTier {
  return series.refresh_tier ?? "stable";
}

function latestTradeDate(series: ChoiceMacroLatestPoint[], emptyDisplay = "") {
  if (series.length === 0) {
    return emptyDisplay;
  }
  return series.map((point) => point.trade_date).sort((left, right) => right.localeCompare(left))[0];
}

function stablePipelineTone(stableSeriesCount: number, stableCatalogCount: number): MarketDataCategoryStore["stablePipelineTone"] {
  if (stableCatalogCount === 0) {
    return "default";
  }
  if (stableSeriesCount === 0) {
    return "error";
  }
  if (stableSeriesCount < stableCatalogCount) {
    return "warning";
  }
  return "default";
}

export function buildMarketDataCategoryStore(input: {
  catalog: MacroVendorSeries[];
  latestSeries: ChoiceMacroLatestPoint[];
  fxAnalyticalGroups: FxAnalyticalGroup[];
}): MarketDataCategoryStore {
  const visibleLatestSeries = input.latestSeries.filter((point) => marketSeriesRefreshTier(point) !== "isolated");
  const stableSeries = visibleLatestSeries.filter((point) => marketSeriesRefreshTier(point) !== "fallback");
  const fallbackSeries = visibleLatestSeries.filter((point) => marketSeriesRefreshTier(point) === "fallback");
  const stableCatalogSeries = input.catalog.filter((series) => marketCatalogRefreshTier(series) === "stable");
  const visibleStableIds = new Set(stableSeries.map((point) => point.series_id));
  const missingStableSeries = stableCatalogSeries.filter((series) => !visibleStableIds.has(series.series_id));
  const vendorVersions = [...new Set(visibleLatestSeries.map((point) => point.vendor_version))];
  const fxAnalyticalSeriesCount = input.fxAnalyticalGroups.reduce((total, group) => total + group.series.length, 0);

  return {
    visibleLatestSeries,
    stableSeries,
    fallbackSeries,
    stableCatalogSeries,
    missingStableSeries,
    stableLatestTradeDate: latestTradeDate(stableSeries, "—"),
    linkageReportDate: latestTradeDate(visibleLatestSeries),
    vendorVersions,
    fxAnalyticalSeriesCount,
    stablePipelineTone: stablePipelineTone(stableSeries.length, stableCatalogSeries.length),
  };
}
