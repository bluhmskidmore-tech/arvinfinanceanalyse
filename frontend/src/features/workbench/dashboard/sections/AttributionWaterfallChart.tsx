import { useMemo } from "react";

import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardCockpitWaterfallItem } from "../dashboardCockpitModel";
import { parseCockpitDisplayNumber } from "../dashboardCockpitChartTheme";

type AttributionWaterfallChartProps = {
  items: readonly DashboardCockpitWaterfallItem[];
};

const CHART_W = 330;
const CHART_H = 132;
const BASELINE_Y = 64;
const AXIS_LEFT = 30;
const BAR_W = 34;

function isSegment(item: DashboardCockpitWaterfallItem): boolean {
  const label = item.label.trim();
  return label !== "期初" && label !== "期末" && !label.includes("合计") && item.id !== "total";
}

function barColor(tone: DashboardCockpitWaterfallItem["tone"]): string {
  if (tone === "positive") return "#20a070";
  if (tone === "negative") return "#e34735";
  if (tone === "neutral") return "#0a4285";
  return "#64748b";
}

function labelColor(tone: DashboardCockpitWaterfallItem["tone"]): string {
  if (tone === "positive") return "#197a5a";
  if (tone === "negative") return "#b94743";
  if (tone === "neutral") return "#0a4285";
  return "#334155";
}

export function AttributionWaterfallChart({ items }: AttributionWaterfallChartProps) {
  const segments = useMemo(() => items.filter(isSegment), [items]);

  const layout = useMemo(() => {
    const values = segments
      .map((item) => parseCockpitDisplayNumber(item.value))
      .filter((value): value is number => value != null);
    const maxAbs = values.length > 0 ? Math.max(...values.map(Math.abs)) : 1;
    const scaleMax = Math.max(maxAbs, 1);
    const plotTop = 12;
    const plotBottom = CHART_H - 24;
    const plotHeight = plotBottom - plotTop;

    const plotWidth = CHART_W - AXIS_LEFT - 12;
    const step = segments.length > 0 ? plotWidth / segments.length : plotWidth;

    const bars = segments.map((item, index) => {
      const numeric = parseCockpitDisplayNumber(item.value) ?? 0;
      const barHeight = Math.max(4, (Math.abs(numeric) / scaleMax) * (plotHeight * 0.82));
      const x = AXIS_LEFT + step * index + (step - BAR_W) / 2;
      const y = numeric >= 0 ? BASELINE_Y - barHeight : BASELINE_Y;
      const valueY = numeric >= 0 ? y - 6 : y + barHeight + 12;
      return { item, x, y, barHeight, valueY, numeric };
    });

    return { bars, scaleMax };
  }, [segments]);

  if (segments.length === 0) {
    return null;
  }

  const ticks = [layout.scaleMax, layout.scaleMax / 2, 0, -layout.scaleMax / 2, -layout.scaleMax];

  return (
    <svg
      className="dashboard-terminal-waterfall-chart"
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      role="img"
      aria-label="收益来源拆解瀑布图"
    >
      <line x1={AXIS_LEFT} y1={BASELINE_Y} x2={CHART_W - 10} y2={BASELINE_Y} stroke="#dfe7f0" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <g fill="#64748b" fontSize="9" fontWeight="400" textAnchor="end">
        {ticks.map((tick, index) => {
          const y = 16 + index * ((CHART_H - 32) / (ticks.length - 1));
          const label = tick === 0 ? "0" : `${tick > 0 ? "" : ""}${Math.round(tick)}`;
          return (
            <text key={tick} x={26} y={y}>
              {label}
            </text>
          );
        })}
      </g>
      {layout.bars.map(({ item, x, y, barHeight, valueY }) => (
        <g key={item.id}>
          <rect
            x={x}
            y={y}
            width={BAR_W}
            height={barHeight}
            rx={2}
            fill={barColor(item.tone)}
            stroke="none"
          />
          <text
            x={x + BAR_W / 2}
            y={valueY}
            fill={labelColor(item.tone)}
            fontSize="8"
            fontWeight="700"
            textAnchor="middle"
            style={tabularNumsStyle}
          >
            {item.value}
          </text>
          <text x={x + BAR_W / 2} y={CHART_H - 4} fill="#0f172a" fontSize="8" fontWeight="700" textAnchor="middle">
            {item.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
