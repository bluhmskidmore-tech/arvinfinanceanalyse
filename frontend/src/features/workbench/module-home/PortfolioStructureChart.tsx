import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import type { ModuleHomeDetailChart } from "./moduleHomeModel";
import { useDeferredChartMount } from "./useDeferredChartMount";
import styles from "./portfolioHome.module.css";

type PortfolioStructureChartProps = {
  chart: ModuleHomeDetailChart;
  height?: number;
  hideTitle?: boolean;
};

/* 所有使用方（组合/市场工作台）都是深色终端页；此前取浅色主题 palette，
   深蓝条画在深蓝底上不可见（DESIGN.md §2.2 深色 token 才是这里的正确色源）。 */
const CHART_COLORS = [
  nocturneTokens.color.blue,
  nocturneTokens.color.inkSoft,
  nocturneTokens.color.green,
  nocturneTokens.color.amber,
  nocturneTokens.color.red,
] as const;
const GRID_LINE_COLOR = nocturneTokens.color.lineSoft;
const AXIS_LABEL_COLOR = nocturneTokens.color.inkMuted;
const AXIS_NAME_COLOR = nocturneTokens.color.inkMuted;

function formatTooltipValue(value: unknown, unit: string) {
  if (value === null || value === undefined || value === EM_DASH) {
    return EM_DASH;
  }
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(2)} ${unit}` : EM_DASH;
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
  const maxValue = Math.max(...chart.values.filter((value): value is number => value !== null), 0);

  function barData(values: Array<number | null>) {
    return values.map((value, index) => ({
      value,
      itemStyle: {
        color: CHART_COLORS[index % CHART_COLORS.length],
        opacity: maxValue > 0 ? 0.78 + (Math.max(value ?? 0, 0) / maxValue) * 0.22 : 0.9,
      },
    }));
  }

  const tooltip = {
    trigger: "axis" as const,
    axisPointer: {
      type: "shadow" as const,
      shadowStyle: { color: "rgba(145, 132, 217, 0.08)" },
    },
    backgroundColor: nocturneTokens.color.panel2,
    borderColor: nocturneTokens.color.line,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: {
      color: nocturneTokens.color.ink,
      fontSize: 11,
      fontWeight: 650,
    },
    valueFormatter: (value: unknown) => formatTooltipValue(value, chart.unit),
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
