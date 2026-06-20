import { describe, expect, it } from "vitest";

import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";
import {
  bondChartMagnitude,
  bondNumericDisplay,
  bondNumericRaw,
  bondNumericRawOrNull,
  returnDecompositionWaterfallDisplayStrings,
  returnDecompositionWaterfallRawSteps,
} from "./bondAnalyticsAdapter";

function num(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 0,
    unit: "yuan",
    display: "0.00",
    precision: 2,
    sign_aware: true,
    ...partial,
  };
}

function rd(overrides: Partial<ReturnDecompositionPayload> = {}): ReturnDecompositionPayload {
  const z = num({ raw: 0, display: "0", unit: "yuan", sign_aware: true });
  const zp = num({ raw: 0, display: "0%", unit: "pct", sign_aware: true });
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    carry: z,
    roll_down: z,
    rate_effect: z,
    spread_effect: z,
    trading: z,
    fx_effect: z,
    convexity_effect: z,
    explained_pnl: z,
    explained_pnl_accounting: z,
    explained_pnl_economic: z,
    oci_reserve_impact: z,
    actual_pnl: z,
    recon_error: z,
    recon_error_pct: { ...zp, unit: "pct", raw: 0, display: "0%" },
    by_asset_class: [],
    by_accounting_class: [],
    bond_details: [],
    bond_count: 0,
    total_market_value: { ...z, unit: "yuan", sign_aware: false },
    warnings: [],
    computed_at: "",
    ...overrides,
  };
}

describe("bondNumericRaw", () => {
  it("reads Numeric.raw", () => {
    expect(bondNumericRaw(num({ raw: 12.5, unit: "ratio" }))).toBe(12.5);
  });

  it("parses legacy string", () => {
    expect(bondNumericRaw("3.25")).toBe(3.25);
  });

  it("returns 0 for null raw", () => {
    expect(bondNumericRaw(num({ raw: null }))).toBe(0);
  });

  it("returns 0 for undefined", () => {
    expect(bondNumericRaw(undefined)).toBe(0);
  });

  it("returns 0 for non-finite string", () => {
    expect(bondNumericRaw("x")).toBe(0);
  });
});

describe("bondNumericRawOrNull", () => {
  it("returns null for empty input", () => {
    expect(bondNumericRawOrNull(undefined)).toBeNull();
  });

  it("returns null for null Numeric raw", () => {
    expect(bondNumericRawOrNull(num({ raw: null }))).toBeNull();
  });

  it("returns number for valid Numeric", () => {
    expect(bondNumericRawOrNull(num({ raw: -1, unit: "bp" }))).toBe(-1);
  });
});

describe("bondNumericDisplay", () => {
  it("uses Numeric.display", () => {
    expect(bondNumericDisplay(num({ display: "+1.2 亿" }))).toBe("+1.2 亿");
  });

  it("maps empty string to dash", () => {
    expect(bondNumericDisplay("")).toBe("—");
  });

  it("maps undefined display strings to dash", () => {
    expect(bondNumericDisplay("undefined")).toBe("—");
    expect(bondNumericDisplay(num({ display: "undefined" }))).toBe("—");
  });
});

describe("bondChartMagnitude", () => {
  it("accepts tensor string", () => {
    expect(bondChartMagnitude("2.5")).toBe(2.5);
  });

  it("accepts Numeric", () => {
    expect(bondChartMagnitude(num({ raw: 4, unit: "ratio" }))).toBe(4);
  });
});

describe("returnDecompositionWaterfall helpers", () => {
  it("builds raw steps including final explained bar", () => {
    const d = rd({
      carry: num({ raw: 1 }),
      roll_down: num({ raw: 2 }),
      rate_effect: num({ raw: 3 }),
      spread_effect: num({ raw: 4 }),
      fx_effect: num({ raw: 5 }),
      convexity_effect: num({ raw: 6 }),
      trading: num({ raw: 7 }),
      explained_pnl: num({ raw: 28 }),
    });
    expect(returnDecompositionWaterfallRawSteps(d)).toEqual([1, 2, 3, 4, 5, 6, 7, 28]);
  });

  it("builds display strings aligned to waterfall categories", () => {
    const d = rd({
      carry: num({ raw: 1, display: "A" }),
      explained_pnl: num({ raw: 0, display: "SUM" }),
    });
    const labels = returnDecompositionWaterfallDisplayStrings(d);
    expect(labels[0]).toBe("A");
    expect(labels[7]).toBe("SUM");
  });
});
