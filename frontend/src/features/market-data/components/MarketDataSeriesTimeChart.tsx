import { useMemo } from "react";

import { ChartCard } from "../../../components/charts/ChartCard";
import type { ChartCardHeight } from "../../../components/charts/chartCardScale";
import { buildMarketDataSeriesTimeChartOption } from "../lib/charts/marketDataSeriesTimeChartOption";
import type { MarketDataSeriesTimeInput } from "../lib/charts/marketDataSeriesTimeChartOption";
import { MARKET_DATA_SERIES_TIME_EMPTY } from "../lib/charts/marketDataChartMessages";

type MarketDataSeriesTimeChartProps = {
  series: MarketDataSeriesTimeInput;
  height?: ChartCardHeight;
  testId?: string;
  variant?: "default" | "sheet";
};

export function MarketDataSeriesTimeChart({
  series,
  height = 220,
  testId = "market-data-series-time-chart",
  variant = "default",
}: MarketDataSeriesTimeChartProps) {
  const option = useMemo(() => buildMarketDataSeriesTimeChartOption(series, { variant }), [series, variant]);

  return (
    <ChartCard
      flat
      ariaLabel={`${series.display_name ?? series.series_name ?? series.series_id}走势`}
      unit={series.unit ?? undefined}
      option={option}
      height={height}
      legend="none"
      testId={testId}
      emptyMessage={MARKET_DATA_SERIES_TIME_EMPTY}
    />
  );
}
