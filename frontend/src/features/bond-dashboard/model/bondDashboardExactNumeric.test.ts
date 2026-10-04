import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import {
  computeFallbackPercentages,
  formatMomChange,
} from "../utils/format";
import { buildDashboardConclusion } from "./bondDashboardPageModel";

function numeric(
  raw: number | null,
  rawText: string | undefined,
  unit: Numeric["unit"] = "ratio",
): Numeric {
  return {
    raw,
    ...(rawText === undefined ? {} : { raw_text: rawText }),
    unit,
    display: raw === null ? "—" : String(raw),
    precision: 8,
    sign_aware: false,
  };
}

function conclusionBody(creditRatio: Numeric): string {
  type Headline = NonNullable<Parameters<typeof buildDashboardConclusion>[0]>;
  type Risk = NonNullable<Parameters<typeof buildDashboardConclusion>[1]>;

  const headline = {
    kpis: {
      total_market_value: numeric(1_000_000_000, "1000000000.00000000", "yuan"),
      weighted_duration: numeric(3.5, "3.50000000", "years"),
    },
  } as Headline;
  const risk = { credit_ratio: creditRatio } as Risk;
  return buildDashboardConclusion(headline, risk).body;
}

describe("bond dashboard exact numeric decisions", () => {
  it("uses raw_text rather than approximate raw at the 30% and 50% boundaries", () => {
    expect(conclusionBody(numeric(0.3, "0.29999999"))).toContain("利率债占比更高");
    expect(conclusionBody(numeric(0.49, "0.50000000"))).toContain("信用仓位偏高");
  });

  it("keeps raw-only legacy threshold behavior", () => {
    expect(conclusionBody(numeric(0.5, undefined))).toContain("信用仓位偏高");
    expect(conclusionBody(numeric(0.3, undefined))).toContain("信用仓位适中");
    expect(conclusionBody(numeric(0.299, undefined))).toContain("利率债占比更高");
  });

  it("uses raw_text for percent, rate-bp, and amount-yi changes", () => {
    expect(
      formatMomChange("percent", numeric(1, "1.10000000"), numeric(1, "1.00000000")),
    ).toBe("+10.00%");
    expect(
      formatMomChange(
        "rateBp",
        numeric(0.02, "0.03100000", "pct"),
        numeric(0.03, "0.03000000", "pct"),
      ),
    ).toBe("+10.0bp");
    expect(
      formatMomChange(
        "amountYi",
        numeric(0, "200000000.00000000", "yuan"),
        numeric(100_000_000, "100000000.00000000", "yuan"),
      ),
    ).toBe("+1.00 亿");
  });

  it("uses Decimal when one side has raw_text and the other is a legacy raw value", () => {
    expect(
      formatMomChange("percent", numeric(1, "1.10000000"), numeric(1, undefined)),
    ).toBe("+10.00%");
  });

  it("returns no percent change when the exact previous value is zero", () => {
    expect(
      formatMomChange("percent", numeric(1, "1.00000000"), numeric(1, "0.00000000")),
    ).toBeNull();
  });

  it("uses explicit half-up rounding for exact percent and amount displays", () => {
    expect(
      formatMomChange("percent", numeric(1, "1.01005"), numeric(1, "1.00000")),
    ).toBe("+1.01%");
    expect(
      formatMomChange(
        "amountYi",
        numeric(0, "100500000.00000000", "yuan"),
        numeric(0, "0.00000000", "yuan"),
      ),
    ).toBe("+1.01 亿");
  });

  it("keeps raw-only legacy month-over-month behavior", () => {
    expect(
      formatMomChange(
        "amountYi",
        numeric(200_000_000, undefined, "yuan"),
        numeric(100_000_000, undefined, "yuan"),
      ),
    ).toBe("+1.00 亿");
  });

  it("collapses an exact near-zero bp decrease instead of rendering negative zero", () => {
    expect(
      formatMomChange(
        "rateBp",
        numeric(0.03, "0.02999999999993", "pct"),
        numeric(0.03, "0.03000000000000", "pct"),
      ),
    ).toBe("0.0bp");
  });

  it("uses exact 1/1/4 weights and assigns the rounding residual to the exact largest item", () => {
    const percentages = computeFallbackPercentages([
      { total_market_value: numeric(1, "1.00000000", "yuan"), percentage: null },
      { total_market_value: numeric(1, "1.00000000", "yuan"), percentage: null },
      { total_market_value: numeric(1, "4.00000000", "yuan"), percentage: null },
    ]);

    expect(percentages).toEqual([16.67, 16.67, 66.66]);
    expect(
      percentages.reduce<number>((sum, value) => sum + (value ?? 0), 0),
    ).toBeCloseTo(100, 10);
    expect(percentages[2]).toBe(66.66);
  });

  it("preserves the legacy zero-total fallback result on the exact path", () => {
    const exact = computeFallbackPercentages([
      { total_market_value: numeric(0, "0.00000000", "yuan"), percentage: null },
      { total_market_value: numeric(0, "0.00000000", "yuan"), percentage: null },
    ]);
    const legacy = computeFallbackPercentages([
      { total_market_value: numeric(0, undefined, "yuan"), percentage: null },
      { total_market_value: numeric(0, undefined, "yuan"), percentage: null },
    ]);

    expect(exact).toEqual(legacy);
  });

  it("foots exact fallback shares to the residual after backend percentages", () => {
    const percentages = computeFallbackPercentages([
      {
        total_market_value: numeric(2, "2.00000000", "yuan"),
        percentage: numeric(0.5, "0.50000000", "pct"),
      },
      { total_market_value: numeric(1, "1.00000000", "yuan"), percentage: null },
      { total_market_value: numeric(1, "1.00000000", "yuan"), percentage: null },
    ]);

    expect(percentages).toEqual([null, 25, 25]);
    expect(
      percentages.reduce<number>((sum, value) => sum + (value ?? 0), 0),
    ).toBe(50);
  });
});
