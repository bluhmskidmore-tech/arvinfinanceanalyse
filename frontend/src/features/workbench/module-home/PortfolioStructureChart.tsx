import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type { ModuleHomeDetailChart } from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

type PortfolioStructureChartProps = {
  chart: ModuleHomeDetailChart;
  height?: number;
};

const CHART_COLORS = ["#1850a1", "#2563eb", "#2d8a5e", "#d97706", "#ef4444"];
const GRID_LINE_COLOR = "#dbe5f0";
const AXIS_LABEL_COLOR = "#40506a";
const AXIS_NAME_COLOR = "#667085";

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
  const maxValue = Math.max(...chart.values, 0);

  function barData(values: number[]) {
    return values.map((value, index) => ({
      value,
      itemStyle: {
        color: CHART_COLORS[index % CHART_COLORS.length],
        opacity: maxValue > 0 ? 0.78 + (Math.max(value, 0) / maxValue) * 0.22 : 0.9,
      },
    }));
  }

  const tooltip = {
    trigger: "axis" as const,
    axisPointer: {
      type: "shadow" as const,
      shadowStyle: { color: "rgba(24, 80, 161, 0.08)" },
    },
    backgroundColor: "rgba(8, 25, 47, 0.94)",
    borderColor: "rgba(96, 165, 250, 0.42)",
    borderWidth: 1,
    padding: [8, 10],
    textStyle: {
      color: "#f8fafc",
      fontSize: 11,
      fontWeight: 650,
    },
    valueFormatter: (value: unknown) => formatTooltipValue(Number(value), chart.unit),
  };

  const option: EChartsOption = horizontal
    ? {
        color: CHART_COLORS,
        animationDuration: 420,
        grid: { left: 92, right: 24, top: 34, bottom: 28 },
        tooltip,
        xAxis: {
          type: "value",
          name: chart.unit,
          nameTextStyle: { color: AXIS_NAME_COLOR, fontSize: 10, fontWeight: 700 },
          splitLine: { lineStyle: { type: "dashed", color: GRID_LINE_COLOR } },
          axisLabel: { fontSize: 11, color: AXIS_LABEL_COLOR, fontWeight: 650 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        yAxis: {
          type: "category",
          data: [...chart.categories].reverse(),
          axisLabel: { fontSize: 11, color: "#17212f", fontWeight: 750, width: 72, overflow: "truncate" },
          axisTick: { show: false },
          axisLine: { show: false },
        },
        series: [
          {
            type: "bar",
            data: barData([...chart.values].reverse()),
            barMaxWidth: 20,
            itemStyle: { borderRadius: [0, 5, 5, 0] },
            emphasis: {
              focus: "series",
              itemStyle: { shadowBlur: 12, shadowColor: "rgba(15, 23, 42, 0.2)" },
            },
          },
        ],
      }
    : {
        color: CHART_COLORS,
        animationDuration: 420,
        grid: { left: 50, right: 22, top: 34, bottom: 42 },
        tooltip,
        xAxis: {
          type: "category",
          data: chart.categories,
          axisLabel: {
            rotate: chart.categories.length > 5 ? 24 : 0,
            fontSize: 11,
            color: "#17212f",
            fontWeight: 750,
          },
          axisTick: { alignWithLabel: true, lineStyle: { color: "#b9c6d6" } },
          axisLine: { lineStyle: { color: "#b9c6d6" } },
        },
        yAxis: {
          type: "value",
          name: chart.unit,
          nameTextStyle: { color: AXIS_NAME_COLOR, fontSize: 10, fontWeight: 700 },
          splitLine: { lineStyle: { type: "dashed", color: GRID_LINE_COLOR } },
          axisLabel: { fontSize: 11, color: AXIS_LABEL_COLOR, fontWeight: 650 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            type: "bar",
            data: barData(chart.values),
            barMaxWidth: 44,
            itemStyle: { borderRadius: [5, 5, 0, 0] },
            emphasis: {
              focus: "series",
              itemStyle: { shadowBlur: 12, shadowColor: "rgba(15, 23, 42, 0.2)" },
            },
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
