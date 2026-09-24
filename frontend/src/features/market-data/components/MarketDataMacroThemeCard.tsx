import { useMemo } from "react";

import { buildMarketDataMultiSeriesTimeChartOption } from "../lib/charts/marketDataSeriesTimeChartOption";
import {
  MACRO_THEME_CHART_MAX_SERIES,
  type MacroThemeGroupBucket,
} from "../lib/marketDataMacroThemeGroups";
import { MarketDataChartShell } from "./MarketDataChartShell";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";
import { MarketDataSeriesCompactTable } from "./MarketDataSeriesCompactTable";

type MarketDataMacroThemeCardProps = {
  group: MacroThemeGroupBucket;
  tier: "stable" | "fallback";
  showThemeChart?: boolean;
  previewRowCount?: number;
};

export function MarketDataMacroThemeCard({
  group,
  tier,
  showThemeChart = false,
  previewRowCount,
}: MarketDataMacroThemeCardProps) {
  const chartOption = useMemo(
    () =>
      showThemeChart
        ? buildMarketDataMultiSeriesTimeChartOption(group.series.slice(0, MACRO_THEME_CHART_MAX_SERIES))
        : null,
    [group.series, showThemeChart],
  );
  const testId = `market-data-macro-theme-${tier}-${group.key}`;

  return (
    <MarketDataSeriesCategoryCard
      title={group.title}
      caption={group.caption}
      count={group.series.length}
      tone={tier}
      showLinkTierTag
      testId={testId}
    >
      {showThemeChart ? (
        <div className="market-data-macro-theme-card__chart" data-testid={`${testId}-chart`}>
          <MarketDataChartShell
            option={chartOption}
            height={180}
            testId={`${testId}-multi-series-chart`}
            emptyMessage="该主题暂无可绘制的近期走势。"
          />
        </div>
      ) : null}
      <MarketDataSeriesCompactTable
        series={group.series}
        testIdPrefix={`market-data-series-${tier}-${group.key}`}
        initialVisibleCount={previewRowCount}
        compactSparseColumns
      />
    </MarketDataSeriesCategoryCard>
  );
}
