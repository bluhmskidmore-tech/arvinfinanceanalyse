import dayjs from "dayjs";

import type {
  ChoiceMacroLatestPoint,
  FxAnalyticalGroup,
  FxAnalyticalSeriesPoint,
  MacroVendorSeries,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export type MarketObservationPoint = ChoiceMacroLatestPoint | FxAnalyticalSeriesPoint;
type RefreshTier = "stable" | "fallback" | "isolated";

/**
 * 展示层时效分档（仅影响行分组与视觉降级，不改任何数据/口径字段，也不隐藏数据）：
 * - 超过 365 天：多为年度或已停更的存量序列（如 2015 年存贷款基准利率），与当日读数
 *   并排会误导时效感知，归入"历史存量"分档；
 * - 90~365 天：超出月度/季度序列的常规发布间隔上限（约一个季度），保持可见但淡化。
 */
export const SERIES_STALE_AGE_DAYS = 90;
export const SERIES_HISTORICAL_AGE_DAYS = 365;

export type SeriesAgeTier = "current" | "stale" | "historical";

export function seriesAgeTier(
  tradeDate: string | null | undefined,
  observationDate: string,
): SeriesAgeTier {
  if (!tradeDate) {
    return "current";
  }
  const ageDays = dayjs(observationDate).diff(dayjs(tradeDate), "day");
  if (!Number.isFinite(ageDays)) {
    return "current";
  }
  if (ageDays > SERIES_HISTORICAL_AGE_DAYS) {
    return "historical";
  }
  if (ageDays > SERIES_STALE_AGE_DAYS) {
    return "stale";
  }
  return "current";
}

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
  const fxAnalyticalSeriesCount = input.fxAnalyticalGroups.reduce(
    (total, group) => total + group.series.length + (group.events?.length ?? 0),
    0,
  );

  return {
    visibleLatestSeries,
    stableSeries,
    fallbackSeries,
    stableCatalogSeries,
    missingStableSeries,
    stableLatestTradeDate: latestTradeDate(stableSeries, EM_DASH),
    linkageReportDate: latestTradeDate(visibleLatestSeries),
    vendorVersions,
    fxAnalyticalSeriesCount,
    stablePipelineTone: stablePipelineTone(stableSeries.length, stableCatalogSeries.length),
  };
}
