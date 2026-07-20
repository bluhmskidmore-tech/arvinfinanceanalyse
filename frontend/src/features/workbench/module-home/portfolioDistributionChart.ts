import type { EChartsOption } from "../../../lib/echarts";
import { dhApiTokens } from "../../../theme/designSystem";
import type { ModuleHomeDistributionRow } from "./moduleHomeModel";

/*
 * Slice colors come from the official dh-api dark terminal tokens
 * (DESIGN.md §2.2); order mirrors the CSS --portfolio-chart-* vars
 * (blue / info / green / amber / red) used by the stacked bars.
 */
export const PORTFOLIO_DIST_CHART_COLORS = [
  dhApiTokens.color.blue,
  dhApiTokens.color.inkSoft,
  dhApiTokens.color.green,
  dhApiTokens.color.amber,
  dhApiTokens.color.red,
];

export function buildPortfolioPieOption(rows: ModuleHomeDistributionRow[]): EChartsOption {
  return {
    color: PORTFOLIO_DIST_CHART_COLORS,
    animationDuration: 180,
    tooltip: {
      trigger: "item",
      backgroundColor: dhApiTokens.color.panel2,
      borderColor: dhApiTokens.color.line,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: {
        color: dhApiTokens.color.ink,
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
          borderColor: dhApiTokens.color.panel,
          borderWidth: 2,
        },
        emphasis: {
          scale: false,
          itemStyle: {
            borderColor: dhApiTokens.color.ink,
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
