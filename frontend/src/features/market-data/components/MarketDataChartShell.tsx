/** Styles for market-data charts are imported only from MarketDataPage.tsx — do not import MarketDataPage.css in chart subcomponents. */
import { Button } from "antd";

import { BaseChart } from "../../../components/charts/BaseChart";
import type { EChartsOption } from "../../../lib/echarts";
import {
  MARKET_DATA_CHART_EMPTY,
  MARKET_DATA_CHART_ERROR,
  MARKET_DATA_CHART_LOADING,
} from "../lib/charts/marketDataChartMessages";

type MarketDataChartShellProps = {
  option: EChartsOption | null;
  height?: number;
  isLoading?: boolean;
  isError?: boolean;
  emptyMessage?: string;
  testId?: string;
  onRetry?: () => void;
};

function isOptionEmpty(option: EChartsOption | null): boolean {
  if (!option) {
    return true;
  }
  const series = option.series;
  if (series == null) {
    return true;
  }
  if (Array.isArray(series)) {
    return series.length === 0;
  }
  return false;
}

export function MarketDataChartShell({
  option,
  height = 240,
  isLoading = false,
  isError = false,
  emptyMessage = MARKET_DATA_CHART_EMPTY,
  testId,
  onRetry,
}: MarketDataChartShellProps) {
  if (isLoading) {
    return (
      <div className="market-data-chart-shell market-data-chart-shell--loading" data-testid={testId}>
        {MARKET_DATA_CHART_LOADING}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="market-data-chart-shell market-data-chart-shell--error" data-testid={testId}>
        <span>{MARKET_DATA_CHART_ERROR}</span>
        {onRetry ? (
          <Button size="small" onClick={onRetry}>
            重试
          </Button>
        ) : null}
      </div>
    );
  }

  if (isOptionEmpty(option)) {
    return (
      <div className="market-data-chart-shell market-data-chart-shell--empty" data-testid={testId}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="market-data-chart-shell" data-testid={testId}>
      <BaseChart option={option!} height={height} loading={false} />
    </div>
  );
}
