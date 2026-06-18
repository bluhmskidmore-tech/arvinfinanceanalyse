import type { YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { ibTokens } from "../../../../theme/designSystem";
import { marketDataChartTheme } from "./marketDataChartTheme";

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
};

function pctNumericToAxisPercent(value: YieldCurveTermStructureCurvePayload["points"][number]["yield_pct"]) {
  if (!value || value.raw == null) {
    return null;
  }
  if (value.unit !== "pct") {
    return value.raw;
  }
  return Math.abs(value.raw) < 1 ? value.raw * 100 : value.raw;
}

function bpNumericToAxis(value: YieldCurveTermStructureCurvePayload["points"][number]["delta_bp_prev"]) {
  if (!value || value.raw == null) {
    return null;
  }
  return value.raw;
}

export function buildMarketDataTermStructureChartOption(
  curves: YieldCurveTermStructureCurvePayload[],
): EChartsOption | null {
  if (!curves.length) {
    return null;
  }
  const categories = curves[0]?.points.map((point) => point.tenor) ?? [];
  if (!categories.length) {
    return null;
  }

  const palette = [ibTokens.color.accent, "#6f8ab8", ibTokens.color.gold];
  const lineSeries = curves.map((curve, index) => {
    const color = palette[index % palette.length]!;
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;

    return {
      name: `${label} 收益率`,
      type: "line" as const,
      yAxisIndex: 0,
      smooth: false,
      symbol: "circle",
      symbolSize: index === 0 ? 7 : 6,
      connectNulls: true,
      itemStyle: {
        color,
        borderColor: "#ffffff",
        borderWidth: 1.5,
      },
      lineStyle: {
        color,
        width: index === 0 ? 2.4 : 1.8,
        opacity: index === 0 ? 1 : 0.7,
      },
      endLabel: {
        show: true,
        formatter: "{a}",
        color,
        fontSize: 10,
        distance: 8,
      },
      emphasis: { focus: "series" as const },
      data: curve.points.map((point) => pctNumericToAxisPercent(point.yield_pct)),
    };
  });

  const barSeries = curves.map((curve, index) => {
    const color = palette[index % palette.length]!;
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;

    return {
      name: `${label} 日变动(bp)`,
      type: "bar" as const,
      yAxisIndex: 1,
      barGap: "18%",
      barMaxWidth: 10,
      itemStyle: {
        color,
        opacity: 0.18,
        borderRadius: [1, 1, 0, 0],
      },
      emphasis: { disabled: true },
      data: curve.points.map((point) => bpNumericToAxis(point.delta_bp_prev)),
    };
  });

  return {
    color: palette,
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "line",
        lineStyle: { color: ibTokens.color.gold, width: 1, type: "dashed" },
      },
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    },
    legend: {
      bottom: 0,
      type: "scroll",
      itemWidth: 18,
      itemHeight: 8,
      textStyle: marketDataChartTheme.axisLabel,
    },
    grid: { left: 44, right: 42, top: 18, bottom: 54 },
    xAxis: {
      type: "category",
      boundaryGap: true,
      data: categories,
      axisLabel: { ...marketDataChartTheme.axisLabel, fontSize: 11, fontWeight: 600 },
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { alignWithLabel: true, lineStyle: { color: ibTokens.color.hairline } },
    },
    yAxis: [
      {
        type: "value",
        name: "收益率 (%)",
        scale: true,
        nameTextStyle: { ...marketDataChartTheme.axisLabel, align: "left" },
        axisLabel: { ...marketDataChartTheme.axisLabel, formatter: "{value}" },
        splitLine: { lineStyle: { color: ibTokens.color.hairline, width: 1, type: "solid" } },
      },
      {
        type: "value",
        name: "Δ (bp)",
        scale: true,
        nameTextStyle: marketDataChartTheme.axisLabel,
        axisLabel: marketDataChartTheme.axisLabel,
        splitLine: { show: false },
      },
    ],
    series: [...lineSeries, ...barSeries],
  };
}
