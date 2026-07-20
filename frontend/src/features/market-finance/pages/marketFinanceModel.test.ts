import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  MARKET_FINANCE_REPRESENTATIVE_SERIES,
  pickRepresentativeSeries,
} from "./marketFinanceModel";

function point(
  seriesId: string,
  partial: Partial<ChoiceMacroLatestPoint> = {},
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesId,
    trade_date: "2026-06-30",
    value_numeric: 1.75,
    unit: "%",
    source_version: "source_v1",
    vendor_version: "vendor_v1",
    quality_flag: "ok",
    refresh_tier: "stable",
    latest_change: 0.01,
    ...partial,
  };
}

describe("pickRepresentativeSeries", () => {
  it("selects the four approved market-finance representatives", () => {
    const selected = pickRepresentativeSeries([
      point("CA.CN_GOV_10Y"),
      point("CA.DR007"),
      point("CA.USDCNY"),
      point("CN_CREDIT_AAA_1Y"),
      point("UNCONFIRMED.001", { value_numeric: 9.99 }),
    ]);

    expect(selected.map((item) => [item.key, item.point.series_id])).toEqual([
      ["cn-gov-10y", "CA.CN_GOV_10Y"],
      ["dr007", "CA.DR007"],
      ["usdcny", "CA.USDCNY"],
      ["credit-aaa", "CN_CREDIT_AAA_1Y"],
    ]);
  });

  it("uses vendor fallback ids in declared priority order", () => {
    const selected = pickRepresentativeSeries([
      point("EMM00166466", { value_numeric: 1.72 }),
      point("E1000180", { value_numeric: 1.73 }),
    ]);

    expect(selected[0]?.point.series_id).toBe("E1000180");
  });

  it("excludes isolated points even when their id is approved", () => {
    const selected = pickRepresentativeSeries([
      point("CA.CN_GOV_10Y", { refresh_tier: "isolated" }),
    ]);

    expect(selected).toEqual([]);
  });

  it("does not substitute an unrelated series for a missing representative", () => {
    const selected = pickRepresentativeSeries([
      point("UNCONFIRMED.001", { value_numeric: 9.99 }),
    ]);

    expect(selected).toEqual([]);
  });

  it("keeps source points unchanged", () => {
    const sourcePoint = Object.freeze(point("CA.CN_GOV_10Y"));
    const source = Object.freeze([sourcePoint]);

    const selected = pickRepresentativeSeries(source);

    expect(selected[0]?.point).toBe(sourcePoint);
    expect(sourcePoint.series_name).toBe("CA.CN_GOV_10Y");
    expect(MARKET_FINANCE_REPRESENTATIVE_SERIES[0]?.label).toBe("10年国债");
  });
});
