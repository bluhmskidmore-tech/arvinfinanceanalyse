import { describe, expect, it } from "vitest";

import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";
import { nocturneTokens } from "../../../theme/designSystem";
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

  // 缺失 ≠ 0（2026-08 假零修复）：缺失/非有限效应柱保留 null 断开，不再补 0 画假柱；
  // 累计 helper 跳过缺失项继续，真实 0 与负值照常成柱。
  it("breaks bars (null) for missing and non-finite decomposition raw values", () => {
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

    const helperData = series[0]?.data as Array<number | null>;
    const effectData = series[1]?.data as Array<{ value: number | null }>;

    expect(helperData.every((item) => item === null || Number.isFinite(item))).toBe(true);
    expect(effectData.map((item) => item.value)).toEqual([null, 0, 3, null, 4, null, 2, null]);
    // 累计 helper 跳过缺失项；正值柱底 = 加柱前的累计（-3 之后 +4 的柱底为 -3），负值柱底 = 累计+v。
    expect(helperData).toEqual([null, 0, -3, null, -3, null, -1, 0]);
  });

  it("colors positive contribution bars green and negative bars red (2026-08-11 决议)", () => {
    const option = buildReturnDecompositionWaterfallOption(
      rd({
        carry: num({ raw: 5 }),
        roll_down: num({ raw: -2 }),
        rate_effect: num({ raw: 1 }),
        spread_effect: num({ raw: 1 }),
        fx_effect: num({ raw: 1 }),
        convexity_effect: num({ raw: 1 }),
        trading: num({ raw: 1 }),
        explained_pnl: num({ raw: 8 }),
      }),
    );
    const series = option.series as Array<{ data?: Array<{ itemStyle?: { color?: string } }> }>;
    const effectData = series[1]?.data ?? [];
    expect(effectData[0]?.itemStyle?.color).toBe(nocturneTokens.color.green);
    expect(effectData[1]?.itemStyle?.color).toBe(nocturneTokens.color.red);
  });
});
