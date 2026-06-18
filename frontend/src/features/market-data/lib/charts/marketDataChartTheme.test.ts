import { describe, expect, it } from "vitest";

import { marketDataChartTheme } from "./marketDataChartTheme";

describe("marketDataChartTheme", () => {
  it("exposes a multi-series palette and axis tokens", () => {
    expect(marketDataChartTheme.multiSeriesPalette.length).toBeGreaterThanOrEqual(3);
    expect(marketDataChartTheme.axisLabel.fontSize).toBe(11);
    expect(marketDataChartTheme.heatmapRange).toHaveLength(2);
  });
});
