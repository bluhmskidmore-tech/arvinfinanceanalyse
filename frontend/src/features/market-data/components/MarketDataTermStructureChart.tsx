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
      height={height}
      testId={testId}
      emptyMessage="当前筛选下缺少可绘制的期限结构点位。"
    />
  );
}
