import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../api/contracts";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "./choiceMacroFormat";

function macroPoint(overrides: Partial<ChoiceMacroLatestPoint>): ChoiceMacroLatestPoint {
  return {
    series_id: "TEST",
    series_name: "test series",
    trade_date: "2026-05-29",
    value_numeric: 0,
    frequency: "daily",
    unit: "",
    source_version: "sv_test",
    vendor_version: "vv_test",
    ...overrides,
  };
}

describe("choiceMacroFormat", () => {
  it("renders index series values without appending the index unit label", () => {
    const point = macroPoint({ unit: "index", value_numeric: 4892.12 });
    expect(formatChoiceMacroValue(point)).toBe("4892.12");
    expect(formatChoiceMacroValue(point, { spaceBeforeUnit: false })).toBe("4892.12");
  });

  it("renders index series deltas as signed raw points without unit suffix", () => {
    const point = macroPoint({ unit: "index", value_numeric: 4892.12, latest_change: -22.09 });
    expect(formatChoiceMacroDelta(point)).toBe("-22.09");
    expect(formatChoiceMacroDelta(point, { spaceBeforeUnit: false })).toBe("-22.09");
  });

  it("renders valuation multiples without appending the x unit label", () => {
    const point = macroPoint({ unit: "x", value_numeric: 14.64, latest_change: 0.22 });
    expect(formatChoiceMacroValue(point)).toBe("14.64");
    expect(formatChoiceMacroDelta(point)).toBe("+0.22");
  });

  it("uses the canonical em dash when the latest change is missing", () => {
    const point = macroPoint({ latest_change: undefined });
    expect(formatChoiceMacroDelta(point)).toBe("—");
    expect(formatChoiceMacroDelta(point, { emptyDisplay: "无前值" })).toBe("无前值");
  });
});
