import { describe, expect, it } from "vitest";

import {
  cockpitChartToneColor,
  parseCockpitDisplayNumber,
} from "./dashboardCockpitChartTheme";
import { COCKPIT_VISUAL } from "./dashboardCockpitVisualTokens";

describe("dashboardCockpitChartTheme", () => {
  it("maps cockpit tones to semantic chart colors", () => {
    expect(cockpitChartToneColor("positive")).toBe(COCKPIT_VISUAL.semantic.gain);
    expect(cockpitChartToneColor("negative")).toBe(COCKPIT_VISUAL.semantic.risk);
    expect(cockpitChartToneColor("warning")).toBe(COCKPIT_VISUAL.semantic.warn);
    expect(cockpitChartToneColor("neutral")).toBe(COCKPIT_VISUAL.chart.gray);
  });

  it("parses display numbers for chart adapters", () => {
    expect(parseCockpitDisplayNumber("3,708.10 亿")).toBe(3708.1);
    expect(parseCockpitDisplayNumber("+29.71 亿")).toBe(29.71);
    expect(parseCockpitDisplayNumber("口径待确认")).toBeNull();
  });
});
