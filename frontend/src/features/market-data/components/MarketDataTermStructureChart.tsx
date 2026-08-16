import { useMemo } from "react";

import type {
  MarketCurveFilter,
  MarketDataRateQuoteSection,
  MarketSourceFilter,
} from "../lib/marketDataTerminalModel";
import { filterRateQuoteRows } from "../lib/marketDataTerminalModel";
import { adaptRateQuoteRowsToTermStructureCurves } from "../lib/charts/marketDataTermStructureAdapter";
import { buildMarketDataTermStructureChartOption } from "../lib/charts/marketDataTermStructureChartOption";
import { MarketDataChartShell } from "./MarketDataChartShell";

type MarketDataTermStructureChartProps = {
  model: MarketDataRateQuoteSection;
  curveFilter?: MarketCurveFilter;
  sourceFilter?: MarketSourceFilter;
  catalogVendorNames?: ReadonlyMap<string, string>;
  activeCurve?: "treasury" | "cdb" | "both";
  height?: number;
  testId?: string;
  emptyTestId?: string;
  variant?: "default" | "sheet";
};

export function MarketDataTermStructureChart({
  model,
  curveFilter = "both",
  sourceFilter = "all",
  catalogVendorNames,
  activeCurve = "both",
  height = 240,
  testId = "market-data-term-structure-chart",
  emptyTestId = "market-data-term-structure-empty",
  variant = "default",
}: MarketDataTermStructureChartProps) {
  const filteredRows = filterRateQuoteRows(model.rows, curveFilter, sourceFilter, catalogVendorNames);
  // 首屏主图（default 变体）最低 240px，避免调用方传入的紧凑高度压扁曲线与 Δbp 柱；sheet 变体跟随调用方。
  const resolvedHeight = variant === "sheet" ? height : Math.max(height, 240);
  const option = useMemo(() => {
    const curves = adaptRateQuoteRowsToTermStructureCurves(filteredRows, model.source, activeCurve);
    return buildMarketDataTermStructureChartOption(curves, { variant });
  }, [activeCurve, filteredRows, model.source, variant]);

  if (model.status !== "ready") {
    return (
      <MarketDataChartShell
        option={null}
        emptyMessage={model.emptyReason}
        testId={emptyTestId}
      />
    );
  }

  return (
    <MarketDataChartShell
      option={option}
      height={resolvedHeight}
      testId={testId}
      emptyMessage="当前筛选下缺少可绘制的期限结构点位。"
    />
  );
}
