import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { ModuleHomeDetailChart } from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

type PortfolioStructureChartProps = {
  chart: ModuleHomeDetailChart;
  height?: number;
};

const CHART_COLORS = ["#35679b", "#2f68b8", "#1850a1", "#6f96c3", "#3f8a6a", "#5a6d86"];

function formatTooltipValue(value: number, unit: string) {
  return `${value.toFixed(2)} ${unit}`;
}

export function PortfolioStructureChart({ chart, height }: PortfolioStructureChartProps) {
  if (chart.categories.length === 0 || chart.values.length === 0) {
    return (
      <div className={styles.structureChartEmpty} data-testid="module-home-structure-chart">
        暂无可视化数据
      </div>
    );
  }

  const horizontal = chart.orientation === "horizontal";

  const option: EChartsOption = horizontal
    ? {
        color: CHART_COLORS,
        grid: { left: 88, right: 24, top: 36, bottom: 24 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          valueFormatter: (value) => formatTooltipValue(Number(value), chart.unit),
        },
        xAxis: {
          type: "value",
          name: chart.unit,
          splitLine: { lineStyle: { type: "dashed", color: "#e4e9f0" } },
          axisLabel: { fontSize: 11, color: "#6b7d95" },
        },
        yAxis: {
          type: "category",
          data: [...chart.categories].reverse(),
          axisLabel: { fontSize: 11, color: "#2c3e5a", width: 64, overflow: "truncate" },
          axisTick: { show: false },
          axisLine: { show: false },
        },
        series: [
          {
            type: "bar",
            data: [...chart.values].reverse(),
            barMaxWidth: 18,
            itemStyle: { borderRadius: [0, 4, 4, 0] },
          },
        ],
      }
    : {
        color: CHART_COLORS,
        grid: { left: 48, right: 20, top: 36, bottom: 40 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          valueFormatter: (value) => formatTooltipValue(Number(value), chart.unit),
        },
        xAxis: {
          type: "category",
          data: chart.categories,
          axisLabel: { rotate: chart.categories.length > 5 ? 24 : 0, fontSize: 11, color: "#2c3e5a" },
          axisTick: { alignWithLabel: true },
        },
        yAxis: {
          type: "value",
          name: chart.unit,
          splitLine: { lineStyle: { type: "dashed", color: "#e4e9f0" } },
          axisLabel: { fontSize: 11, color: "#6b7d95" },
        },
        series: [
          {
            type: "bar",
            data: chart.values,
            barMaxWidth: 42,
            itemStyle: { borderRadius: [4, 4, 0, 0] },
          },
        ],
      };

  return (
    <div className={styles.structureChartWrap} data-testid="module-home-structure-chart">
      <div className={styles.structureChartTitle}>{chart.title}</div>
      <ReactECharts option={option} style={{ height: height ?? (horizontal ? 280 : 260), width: "100%" }} notMerge lazyUpdate />
    </div>
  );
}
