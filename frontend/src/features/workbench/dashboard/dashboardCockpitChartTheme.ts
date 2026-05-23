import type { EChartsOption } from "../../../lib/echarts";
import { COCKPIT_TYPOGRAPHY, COCKPIT_VISUAL } from "./dashboardCockpitVisualTokens";

type CockpitChartTone = "positive" | "negative" | "neutral" | "warning" | string;

export function cockpitChartToneColor(tone: CockpitChartTone): string {
  if (tone === "positive") return COCKPIT_VISUAL.semantic.gain;
  if (tone === "negative") return COCKPIT_VISUAL.semantic.risk;
  if (tone === "warning") return COCKPIT_VISUAL.semantic.warn;
  return COCKPIT_VISUAL.chart.gray;
}

export function buildCockpitChartTooltip(): NonNullable<EChartsOption["tooltip"]> {
  return {
    trigger: "axis",
    backgroundColor: COCKPIT_VISUAL.surface.card,
    borderColor: COCKPIT_VISUAL.surface.border,
    textStyle: {
      color: COCKPIT_VISUAL.text.body,
      fontFamily: COCKPIT_TYPOGRAPHY.fontSans,
      fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
    },
  };
}

export function buildCockpitChartGrid(
  overrides: Partial<NonNullable<EChartsOption["grid"]>> = {},
): NonNullable<EChartsOption["grid"]> {
  return {
    left: 8,
    right: 8,
    top: 18,
    bottom: 24,
    containLabel: true,
    ...overrides,
  };
}

export function buildCockpitCategoryAxis(
  data: readonly string[],
): NonNullable<EChartsOption["xAxis"]> {
  return {
    type: "category",
    data: [...data],
    axisLine: { lineStyle: { color: COCKPIT_VISUAL.surface.divider } },
    axisTick: { show: false },
    axisLabel: {
      color: COCKPIT_VISUAL.text.muted,
      fontFamily: COCKPIT_TYPOGRAPHY.fontSans,
      fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
      interval: 0,
      rotate: 0,
    },
  };
}

export function buildCockpitValueAxis(
  overrides: Partial<Extract<EChartsOption["yAxis"], object>> = {},
): EChartsOption["yAxis"] {
  return {
    type: "value",
    splitLine: { lineStyle: { color: COCKPIT_VISUAL.surface.divider, type: "dashed" } },
    axisLabel: {
      color: COCKPIT_VISUAL.text.weak,
      fontFamily: COCKPIT_TYPOGRAPHY.fontTabular,
      fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
    },
    ...overrides,
  };
}

export function parseCockpitDisplayNumber(value: string): number | null {
  const normalized = value.replace(/,/g, "").replace(/[^\d.-]/g, "");
  if (!normalized || normalized === "-" || normalized === "." || normalized === "-.") {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}
