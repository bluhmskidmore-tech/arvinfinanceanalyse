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
};

export function MarketDataTermStructureChart({
  model,
  curveFilter = "both",
  sourceFilter = "all",
  catalogVendorNames,
  activeCurve = "both",
  height = 240,
}: MarketDataTermStructureChartProps) {
  const filteredRows = filterRateQuoteRows(model.rows, curveFilter, sourceFilter, catalogVendorNames);
  const option = useMemo(() => {
    const curves = adaptRateQuoteRowsToTermStructureCurves(filteredRows, model.source, activeCurve);
    return buildMarketDataTermStructureChartOption(curves);
  }, [activeCurve, filteredRows, model.source]);

  if (model.status !== "ready") {
    return (
      <MarketDataChartShell
        option={null}
        emptyMessage={model.emptyReason}
        testId="market-data-term-structure-empty"
      />
    );
  }

  return (
    <MarketDataChartShell
      option={option}
      height={height}
      testId="market-data-term-structure-chart"
      emptyMessage="当前筛选下缺少可绘制的期限结构点位。"
    />
  );
}
