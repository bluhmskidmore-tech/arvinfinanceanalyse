import type { EChartsOption } from "../../../lib/echarts";
import type { ModuleHomeDistributionRow } from "./moduleHomeModel";

export const PORTFOLIO_DIST_CHART_COLORS = ["#1850a1", "#2563eb", "#2d8a5e", "#d97706", "#ef4444"];

export function buildPortfolioPieOption(rows: ModuleHomeDistributionRow[]): EChartsOption {
  return {
    color: PORTFOLIO_DIST_CHART_COLORS,
    animationDuration: 420,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(8, 25, 47, 0.94)",
      borderColor: "rgba(96, 165, 250, 0.42)",
      borderWidth: 1,
      padding: [8, 10],
      textStyle: {
        color: "#f8fafc",
        fontSize: 11,
        fontWeight: 650,
      },
      formatter: (params: unknown) => {
        const item = params as { name: string; percent: number };
        const row = rows.find((entry) => entry.label === item.name);
        return `${item.name}<br/>${item.percent.toFixed(2)}%${row ? `<br/>${row.marketValue}` : ""}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["50%", "82%"],
        center: ["50%", "50%"],
        startAngle: 104,
        minAngle: 4,
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: "#f8fafc",
          borderWidth: 3,
          shadowBlur: 8,
          shadowColor: "rgba(15, 23, 42, 0.12)",
        },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: {
            shadowBlur: 14,
            shadowColor: "rgba(15, 23, 42, 0.22)",
          },
        },
        data: rows.map((row, index) => ({
          name: row.label,
          value: Math.max(row.barPct, 0),
          itemStyle: {
            color: PORTFOLIO_DIST_CHART_COLORS[index % PORTFOLIO_DIST_CHART_COLORS.length],
          },
        })),
      },
    ],
  };
}
