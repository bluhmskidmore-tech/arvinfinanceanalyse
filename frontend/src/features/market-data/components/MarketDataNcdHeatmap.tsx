import { useMemo } from "react";

import type { NcdFundingProxyPayload } from "../../../api/contracts";
import { ChartCard } from "../../../components/charts/ChartCard";
import { MARKET_DATA_CHART_ERROR } from "../lib/charts/marketDataChartMessages";
import { buildNcdProxyHeatmapOption } from "../lib/charts/ncdProxyHeatmapChartOption";

type MarketDataNcdHeatmapProps = {
  payload?: NcdFundingProxyPayload;
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
};

export function MarketDataNcdHeatmap({
  payload,
  isLoading = false,
  isError = false,
  onRetry,
}: MarketDataNcdHeatmapProps) {
  const option = useMemo(() => buildNcdProxyHeatmapOption(payload), [payload]);

  return (
    <ChartCard
      flat
      ariaLabel="同业存单代理矩阵"
      option={option}
      height={280}
      legend="none"
      state={isLoading ? "loading" : isError ? "error" : undefined}
      errorMessage={MARKET_DATA_CHART_ERROR}
      onRetry={onRetry}
      testId="market-data-ncd-heatmap"
      emptyMessage="当前未返回可绘制的存单 proxy 矩阵。"
    />
  );
}
