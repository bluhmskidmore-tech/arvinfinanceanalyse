import type { EChartsOption } from "../../../lib/echarts";
import type { ModuleHomeDistributionRow } from "./moduleHomeModel";

export const PORTFOLIO_DIST_CHART_COLORS = ["#9fb4c7", "#688bb2", "#7d9a7f", "#b09261", "#aa7778"];

export function buildPortfolioPieOption(rows: ModuleHomeDistributionRow[]): EChartsOption {
  return {
    color: PORTFOLIO_DIST_CHART_COLORS,
    animationDuration: 180,
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
        radius: ["58%", "84%"],
        center: ["50%", "50%"],
        startAngle: 104,
        minAngle: 4,
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: "#0b1728",
          borderWidth: 2,
        },
        emphasis: {
          scale: false,
          itemStyle: {
            borderColor: "#d7e3f5",
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
