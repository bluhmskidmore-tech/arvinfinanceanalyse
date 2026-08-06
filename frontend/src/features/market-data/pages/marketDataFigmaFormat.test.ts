import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  formatMarketDataFigmaDelta,
  formatMarketDataFigmaValue,
} from "./marketDataFigmaFormat";

function point(
  overrides: Partial<ChoiceMacroLatestPoint>,
): ChoiceMacroLatestPoint {
  return {
    series_id: "fixture",
    series_name: "fixture",
    trade_date: "2026-07-28",
    value_numeric: 1,
    unit: "%",
    source_version: "sv_fixture",
    vendor_version: "vv_fixture",
    latest_change: null,
    ...overrides,
  };
}

describe("marketDataFigmaFormat", () => {
  it("preserves four decimal places and separates FX values from their unit", () => {
    const fx = point({
      series_id: "EMM00058124",
      value_numeric: 6.7939,
      unit: "CNY/USD",
      latest_change: 0.0033,
    });

    expect(formatMarketDataFigmaValue(fx)).toBe("6.7939 CNY/USD");
    expect(formatMarketDataFigmaDelta(fx)).toBe("+0.0033 CNY/USD");
  });

  it("keeps one decimal place for fractional basis-point changes and trims exact integers", () => {
    expect(formatMarketDataFigmaDelta(point({ latest_change: 0.035 }))).toBe("+3.5bp");
    expect(formatMarketDataFigmaDelta(point({ latest_change: 0.04 }))).toBe("+4bp");
  });

  it("separates non-percent values and changes from their display unit", () => {
    const commodity = point({
      value_numeric: 96.995,
      unit: "USD/bbl",
      latest_change: 1.988,
    });

    expect(formatMarketDataFigmaValue(commodity)).toBe("97 USD/bbl");
    expect(formatMarketDataFigmaDelta(commodity)).toBe("+1.99 USD/bbl");
  });
});
