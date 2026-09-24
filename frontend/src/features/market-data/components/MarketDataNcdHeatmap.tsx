import { useMemo } from "react";

import type { NcdFundingProxyPayload } from "../../../api/contracts";
import { buildNcdProxyHeatmapOption } from "../lib/charts/ncdProxyHeatmapChartOption";
import { MarketDataChartShell } from "./MarketDataChartShell";

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

  const rowCount = payload?.rows?.length ?? 0;
  const heatmapHeight = Math.max(220, rowCount * 36);

  return (
    <MarketDataChartShell
      option={option}
      height={heatmapHeight}
      isLoading={isLoading}
      isError={isError}
      onRetry={onRetry}
      testId="market-data-ncd-heatmap"
      emptyMessage="当前未返回可绘制的存单 proxy 矩阵。"
    />
  );
}
