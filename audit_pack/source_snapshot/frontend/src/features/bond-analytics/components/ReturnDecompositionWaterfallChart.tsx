import ReactECharts, { type EChartsOption } from "../../../lib/echarts";

type Props = {
  option: EChartsOption;
  height: number;
};

export function ReturnDecompositionWaterfallChart({ option, height }: Props) {
  return <ReactECharts option={option} style={{ height, width: "100%" }} opts={{ renderer: "canvas" }} />;
}
