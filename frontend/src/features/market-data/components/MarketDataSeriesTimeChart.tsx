import { useMemo } from "react";

import { buildMarketDataSeriesTimeChartOption } from "../lib/charts/marketDataSeriesTimeChartOption";
import type { MarketDataSeriesTimeInput } from "../lib/charts/marketDataSeriesTimeChartOption";
import { MARKET_DATA_SERIES_TIME_EMPTY } from "../lib/charts/marketDataChartMessages";
import { MarketDataChartShell } from "./MarketDataChartShell";

type MarketDataSeriesTimeChartProps = {
  series: MarketDataSeriesTimeInput;
  height?: number;
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
    <MarketDataChartShell
      option={option}
      height={height}
      testId={testId}
      emptyMessage={MARKET_DATA_SERIES_TIME_EMPTY}
    />
  );
}
