import { type EChartsOption } from "../../../lib/echarts";
import { ChartCard } from "../../../components/charts/ChartCard";
import type { ChartCardHeight } from "../../../components/charts/chartCardScale";

type Props = {
  option: EChartsOption;
  height: ChartCardHeight;
};

export function ReturnDecompositionWaterfallChart({ option, height }: Props) {
  return (
    <ChartCard
      flat
      ariaLabel="收益效应分解"
      unit="万元"
      option={option}
      height={height}
      legend="none"
    />
  );
}
