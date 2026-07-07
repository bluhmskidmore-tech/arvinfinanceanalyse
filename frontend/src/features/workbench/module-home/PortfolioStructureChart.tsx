import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { ibTokens } from "../../../theme/designSystem";
import type { ModuleHomeDetailChart } from "./moduleHomeModel";
import { useDeferredChartMount } from "./useDeferredChartMount";
import styles from "./portfolioHome.module.css";

type PortfolioStructureChartProps = {
  chart: ModuleHomeDetailChart;
  height?: number;
  hideTitle?: boolean;
};

const CHART_COLORS = [
  mossChartCategoricalPalette[0],
  mossChartCategoricalPalette[1],
  mossChartCategoricalPalette[2],
  ibTokens.color.gold,
  ibTokens.color.down,
] as const;
const GRID_LINE_COLOR = ibTokens.color.hairline;
const AXIS_LABEL_COLOR = ibTokens.color.inkMuted;
const AXIS_NAME_COLOR = ibTokens.color.inkMuted;

function formatTooltipValue(value: number, unit: string) {
  return `${value.toFixed(2)} ${unit}`;
}

export function PortfolioStructureChart({ chart, height, hideTitle = false }: PortfolioStructureChartProps) {
  const { containerRef, ready, onChartReady } = useDeferredChartMount<HTMLDivElement>();

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
    backgroundColor: ibTokens.color.surface,
    borderColor: ibTokens.color.hairline,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: {
      color: ibTokens.color.ink,
      fontSize: 11,
      fontWeight: 650,
    },
    valueFormatter: (value: unknown) => formatTooltipValue(Number(value), chart.unit),
  };

  const option: EChartsOption = horizontal
    ? {
        color: [...CHART_COLORS],
        animationDuration: 420,
        grid: { left: 92, right: 32, top: 34, bottom: 28 },
        tooltip,
        xAxis: {
          type: "value",
          name: chart.unit,
          nameTextStyle: { color: AXIS_NAME_COLOR, fontSize: 10, fontWeight: 700 },
          splitLine: { lineStyle: { type: "dashed", color: GRID_LINE_COLOR, opacity: 0.5 } },
          axisLabel: { fontSize: 10, color: AXIS_LABEL_COLOR, fontWeight: 500 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        yAxis: {
          type: "category",
          data: [...chart.categories].reverse(),
          axisLabel: { fontSize: 11, color: AXIS_LABEL_COLOR, fontWeight: 600, width: 76, overflow: "truncate" },
          axisTick: { show: false },
          axisLine: { show: false },
        },
        series: [
          {
            type: "bar",
            data: barData([...chart.values].reverse()),
            barMaxWidth: 12,
            barCategoryGap: "35%",
            itemStyle: { borderRadius: [0, 3, 3, 0] },
            emphasis: {
              focus: "series",
              itemStyle: { shadowBlur: 0, shadowColor: "transparent" },
            },
          },
        ],
      }
    : {
        color: [...CHART_COLORS],
        animationDuration: 420,
        grid: { left: 50, right: 22, top: 34, bottom: 42 },
        tooltip,
        xAxis: {
          type: "category",
          data: chart.categories,
          axisLabel: { fontSize: 11, color: AXIS_LABEL_COLOR, fontWeight: 600, interval: 0, width: 48, overflow: "truncate" },
          axisTick: { show: false },
          axisLine: { show: false },
        },
        yAxis: {
          type: "value",
          name: chart.unit,
          nameTextStyle: { color: AXIS_NAME_COLOR, fontSize: 10, fontWeight: 700 },
          splitLine: { lineStyle: { type: "dashed", color: GRID_LINE_COLOR, opacity: 0.5 } },
          axisLabel: { fontSize: 10, color: AXIS_LABEL_COLOR, fontWeight: 500 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            type: "bar",
            data: barData(chart.values),
            barMaxWidth: 12,
            barCategoryGap: "35%",
            itemStyle: { borderRadius: [3, 3, 0, 0] },
            emphasis: {
              focus: "series",
              itemStyle: { shadowBlur: 0, shadowColor: "transparent" },
            },
          },
        ],
      };

  return (
    <div className={styles.structureChartWrap} ref={containerRef} data-testid="module-home-structure-chart">
      {hideTitle ? null : <div className={styles.structureChartTitle}>{chart.title}</div>}
      {ready ? (
        <ReactECharts
          option={option}
          style={{ height: height ?? (horizontal ? 280 : 260), width: "100%" }}
          notMerge
          lazyUpdate
          onChartReady={onChartReady}
        />
      ) : null}
    </div>
  );
}
