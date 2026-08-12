import ReactEChartsCoreModule from "echarts-for-react/lib/core";
import type { EChartsReactProps } from "echarts-for-react/lib/types";
import * as echarts from "echarts/core";
import { BarChart, CandlestickChart, HeatmapChart, LineChart, PieChart, RadarChart, ScatterChart } from "echarts/charts";
import {
  AxisPointerComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart,
  CandlestickChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  ScatterChart,
  AxisPointerComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

echarts.registerTheme("moss-dark-hero", {
  color: ["#006FEE", "#17C964", "#F31260", "#F5A524", "#7828C8", "#00C2E6"],
  backgroundColor: "transparent",
  tooltip: {
    backgroundColor: "rgba(24, 24, 27, 0.6)",
    borderColor: "rgba(255, 255, 255, 0.15)",
    textStyle: {
      color: "#fff",
    },
    extraCssText: "backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);",
  },
  categoryAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: {
      show: true,
      lineStyle: {
        color: "rgba(255, 255, 255, 0.05)",
      },
    },
  },
  timeAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
  },
  logAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: {
      show: true,
      lineStyle: {
        color: "rgba(255, 255, 255, 0.05)",
      },
    },
  },
});

export type { EChartsOption } from "echarts";

type ReactEChartsCoreExport = typeof ReactEChartsCoreModule;

// CJS/ESM 互操作：部分打包条件下拿到的是带 default 的命名空间对象，取 default 兜底。
const ReactEChartsCore =
  (ReactEChartsCoreModule as ReactEChartsCoreExport & { default?: ReactEChartsCoreExport })
    .default ?? ReactEChartsCoreModule;

export default function ReactECharts({ theme = "moss-dark-hero", ...props }: EChartsReactProps) {
  return <ReactEChartsCore echarts={echarts} theme={theme} {...props} />;
}
