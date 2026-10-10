import { describe, expect, it } from "vitest";

import type { Numeric } from "../../api/contracts";
import {
  durationExclusionTone,
  liquidityGapLabel,
  liquidityGapTone,
  projectionQualityTone,
  riskTensorExactScaledAmountDisplayOrNull,
  scenarioStressTone,
  selectDominantRiskTensorRow,
} from "./riskTensorPageModel";

function numeric(raw: number, rawText?: string): Numeric {
  return {
    raw,
    ...(rawText === undefined ? {} : { raw_text: rawText }),
    unit: "yuan",
    display: `${raw}`,
    precision: 8,
    sign_aware: true,
  };
}

describe("riskTensorPageModel exact decisions", () => {
  it("uses raw_text for the first-screen liquidity label and tone", () => {
    const value = numeric(1, "-0.00000001");

    expect(liquidityGapLabel(value)).toBe("30 日缺口为负");
    expect(liquidityGapTone(value)).toBe("danger");
    expect(liquidityGapLabel(numeric(1))).toBe("30 日缺口为正");
    expect(liquidityGapTone(numeric(1))).toBe("ok");
  });

  it("uses exact amounts for projection, exclusion, and scenario tones", () => {
    const exactPositive = numeric(0, "0.00000001");
    const exactNegative = numeric(1, "-0.00000001");

    expect(projectionQualityTone(exactPositive, 0, "available")).toBe("warning");
    expect(
      durationExclusionTone({
        duration_excluded_count: 0,
        duration_excluded_market_value: exactPositive,
      }),
    ).toBe("warning");
    expect(scenarioStressTone({ data_status: "available", estimated_impact: exactNegative })).toBe("danger");
  });

  it("selects the dominant tenor by exact magnitude and keeps first-on-tie behavior", () => {
    const rows = [
      { tenor: "5Y", value: numeric(5, "1.00000000") },
      { tenor: "7Y", value: numeric(4, "6.00000000") },
      { tenor: "10Y", value: numeric(3, "6.00000000") },
    ];

    expect(selectDominantRiskTensorRow(rows)?.tenor).toBe("7Y");
    expect(
      selectDominantRiskTensorRow(
        rows.map((row) => ({ ...row, value: numeric(row.value.raw ?? 0) })),
      )?.tenor,
    ).toBe("5Y");
  });

  it("scales formal amount text from raw_text with half-up rounding and exact grouping", () => {
    expect(riskTensorExactScaledAmountDisplayOrNull(numeric(1, "10050"), 10_000)).toBe("1.01");
    expect(riskTensorExactScaledAmountDisplayOrNull(numeric(1, "-10050"), 10_000)).toBe("-1.01");
    expect(
      riskTensorExactScaledAmountDisplayOrNull(
        numeric(9_007_199_254_740_992, "9007199254740993.00"),
        10_000,
        true,
      ),
    ).toBe("+900,719,925,474.10");
    expect(riskTensorExactScaledAmountDisplayOrNull(numeric(1), 10_000)).toBeNull();
  });
});
