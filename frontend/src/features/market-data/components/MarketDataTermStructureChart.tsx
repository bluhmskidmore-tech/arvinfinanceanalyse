import { useMemo } from "react";

import { ChartCard } from "../../../components/charts/ChartCard";
import type { ChartCardHeight } from "../../../components/charts/chartCardScale";
import type {
  MarketCurveFilter,
  MarketDataRateQuoteSection,
  MarketSourceFilter,
} from "../lib/marketDataTerminalModel";
import { filterRateQuoteRows } from "../lib/marketDataTerminalModel";
import { adaptRateQuoteRowsToTermStructureCurves } from "../lib/charts/marketDataTermStructureAdapter";
import { buildMarketDataTermStructureChartOption } from "../lib/charts/marketDataTermStructureChartOption";

type MarketDataTermStructureChartProps = {
  model: MarketDataRateQuoteSection;
  curveFilter?: MarketCurveFilter;
  sourceFilter?: MarketSourceFilter;
  catalogVendorNames?: ReadonlyMap<string, string>;
  activeCurve?: "treasury" | "cdb" | "both";
  height?: ChartCardHeight;
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
  height = 220,
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
      <ChartCard
        flat
        title="国债收益率曲线"
        question="中债"
        unit="%"
        option={null}
        height={height}
        legend={variant === "sheet" ? "none" : "bottom-left"}
        legendRows={2}
        emptyMessage={model.emptyReason}
        testId={emptyTestId}
      />
    );
  }

  return (
    <ChartCard
      flat
      title="国债收益率曲线"
      question="中债"
      unit="%"
      option={option}
      height={height}
      legend={variant === "sheet" ? "none" : "bottom-left"}
      legendRows={2}
      testId={testId}
      emptyMessage="当前筛选下缺少可绘制的期限结构点位。"
    />
  );
}
