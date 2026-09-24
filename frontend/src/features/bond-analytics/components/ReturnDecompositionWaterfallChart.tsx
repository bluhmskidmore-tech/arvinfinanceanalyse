import { type EChartsOption } from "../../../lib/echarts";
import { BaseChart } from "../../../components/charts/BaseChart";

type Props = {
  option: EChartsOption;
  height: number;
};

export function ReturnDecompositionWaterfallChart({ option, height }: Props) {
  return <BaseChart option={option} height={height} />;
}
