import type {
  GridComponentOption,
  TooltipComponentOption,
  XAXisComponentOption,
  YAXisComponentOption,
} from "echarts";
import type {
  CategoryAxisBaseOption,
  ValueAxisBaseOption,
} from "echarts/types/src/coord/axisCommonTypes.js";
import { COCKPIT_TYPOGRAPHY, COCKPIT_VISUAL } from "./dashboardCockpitVisualTokens";

type CockpitChartTone = "positive" | "negative" | "neutral" | "warning" | string;

export function cockpitChartToneColor(tone: CockpitChartTone): string {
  if (tone === "positive") return COCKPIT_VISUAL.semantic.gain;
  if (tone === "negative") return COCKPIT_VISUAL.semantic.risk;
  if (tone === "warning") return COCKPIT_VISUAL.semantic.warn;
  return COCKPIT_VISUAL.chart.gray;
}

type CockpitCategoryAxisOption = XAXisComponentOption &
  CategoryAxisBaseOption & { type: "category" };
type CockpitValueAxisOption = YAXisComponentOption &
  ValueAxisBaseOption & { type: "value" };

export function buildCockpitChartTooltip(): TooltipComponentOption {
  return {
    trigger: "axis",
    backgroundColor: COCKPIT_VISUAL.surface.card,
    borderColor: COCKPIT_VISUAL.surface.border,
    borderWidth: 1,
    padding: [8, 10],
    extraCssText: "box-shadow: none; border-radius: 6px; font-variant-numeric: tabular-nums;",
    textStyle: {
      color: COCKPIT_VISUAL.text.body,
      fontFamily: COCKPIT_TYPOGRAPHY.fontSans,
      fontSize: COCKPIT_TYPOGRAPHY.size.chartAxis,
    },
  };
}

export function buildCockpitChartGrid(
  overrides: Partial<GridComponentOption> = {},
): GridComponentOption {
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
): CockpitCategoryAxisOption {
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
  overrides: Partial<Omit<CockpitValueAxisOption, "type">> = {},
): CockpitValueAxisOption {
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
