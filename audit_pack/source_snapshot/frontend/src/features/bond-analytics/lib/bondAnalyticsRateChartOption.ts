import type { EChartsOption } from "../../../lib/echarts";
import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { BOND_ANALYTICS_OVERVIEW_RATE_CHART_SERIES } from "./bondAnalyticsMacroSeries";

const c = designTokens.color;

function recentValueMap(point: ChoiceMacroLatestPoint | undefined) {
  const map = new Map<string, number>();
  if (!point) return map;
  for (const rp of point.recent_points ?? []) {
    map.set(rp.trade_date, rp.value_numeric);
  }
  return map;
}

export function buildBondAnalyticsOverviewRateChartOption(
  series: ChoiceMacroLatestPoint[],
): EChartsOption | null {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const dateSet = new Set<string>();
  const timelines = BOND_ANALYTICS_OVERVIEW_RATE_CHART_SERIES.map((def) => {
    const timeline = recentValueMap(byId.get(def.series_id));
    for (const d of timeline.keys()) {
      dateSet.add(d);
    }
    return timeline;
  });
  if (dateSet.size === 0) {
    return null;
  }
  let unit = "";
  for (const def of BOND_ANALYTICS_OVERVIEW_RATE_CHART_SERIES) {
    const p = byId.get(def.series_id);
    if (p?.unit) {
      unit = p.unit;
      break;
    }
  }
  const categories = [...dateSet].sort((a, b) => a.localeCompare(b));
  const lineSeries = BOND_ANALYTICS_OVERVIEW_RATE_CHART_SERIES.map((def, i) => ({
    name: def.name,
    type: "line" as const,
    smooth: true,
    showSymbol: categories.length <= 36,
    connectNulls: true,
    data: categories.map((d) => timelines[i]!.get(d) ?? null),
  }));
  return {
    color: [c.info[500], c.danger[400], c.primary[500]],
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 52, right: 20, top: 28, bottom: 52 },
    xAxis: { type: "category", boundaryGap: false, data: categories },
    yAxis: {
      type: "value",
      scale: true,
      name: unit || undefined,
      axisLabel: { formatter: "{value}" },
    },
    series: lineSeries,
  };
}
