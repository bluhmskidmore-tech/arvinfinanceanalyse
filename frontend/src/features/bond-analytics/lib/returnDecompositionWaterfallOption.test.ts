import { describe, expect, it } from "vitest";

import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";
import {
  buildReturnDecompositionWaterfallOption,
  RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT,
  RETURN_DECOMPOSITION_WATERFALL_CATEGORIES,
} from "./returnDecompositionWaterfallOption";

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

describe("returnDecompositionWaterfallOption", () => {
  it("exports a fixed category list length for tooltip and xAxis", () => {
    expect(RETURN_DECOMPOSITION_WATERFALL_CATEGORIES.length).toBe(RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT);
    expect(RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT).toBe(8);
  });

  it("emits finite series values for missing and non-finite decomposition raw values", () => {
    const option = buildReturnDecompositionWaterfallOption(
      rd({
        carry: num({ raw: null }),
        roll_down: num({ raw: 0 }),
        rate_effect: num({ raw: -3 }),
        spread_effect: num({ raw: Number.NaN }),
        fx_effect: num({ raw: 4 }),
        convexity_effect: num({ raw: null }),
        trading: num({ raw: -2 }),
        explained_pnl: num({ raw: Number.NaN }),
      }),
    );
    const series = option.series as Array<{ data?: unknown[] }>;
    expect(series).toHaveLength(2);

    const helperData = series[0]?.data as number[];
    const effectData = series[1]?.data as Array<{ value: number }>;

    expect(helperData.every(Number.isFinite)).toBe(true);
    expect(effectData.map((item) => item.value)).toEqual([0, 0, 3, 0, 4, 0, 2, 0]);
    expect(effectData.every((item) => Number.isFinite(item.value))).toBe(true);
  });
});
