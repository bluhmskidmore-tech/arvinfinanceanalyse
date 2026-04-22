import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";

import { maxCrossAssetHeadlineTradeDate, resolveCrossAssetKpis } from "./crossAssetKpiModel";

function macroPoint(
  seriesId: string,
  value: number,
  recent: [string, number][],
  extra?: Partial<ChoiceMacroLatestPoint>,
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesId,
    trade_date: recent[recent.length - 1][0],
    value_numeric: value,
    unit: "%",
    source_version: "sv_t",
    vendor_version: "vv_t",
    latest_change: 0.01,
    recent_points: recent.map(([trade_date, value_numeric]) => ({
      trade_date,
      value_numeric,
      source_version: "sv_t",
      vendor_version: "vv_t",
      quality_flag: "ok" as const,
    })),
    ...extra,
  };
}

describe("crossAssetKpiModel", () => {
  it("prefers E1000180 over EMM00166466 for China10Y", () => {
    const series = [
      macroPoint("EMM00166466", 1.94, [
        ["2026-02-28", 1.95],
        ["2026-03-01", 1.94],
      ]),
      macroPoint("E1000180", 1.88, [
        ["2026-02-28", 1.9],
        ["2026-03-01", 1.88],
      ]),
    ];
    const kpis = resolveCrossAssetKpis(series);
    const cn = kpis.find((k) => k.key === "cn_gov_10y");
    expect(cn?.valueLabel).toBe("1.88%");
    expect(cn?.resolvedSeriesId).toBe("E1000180");
  });

  it("prefers E1003238 over EMG for US 10Y", () => {
    const series = [
      macroPoint("EMG00001310", 4.1, [
        ["2026-02-28", 4.08],
        ["2026-03-01", 4.1],
      ]),
      macroPoint("E1003238", 3.95, [
        ["2026-02-28", 3.96],
        ["2026-03-01", 3.95],
      ]),
      macroPoint("CA.US_GOV_10Y", 9.9, [
        ["2026-02-28", 9.9],
        ["2026-03-01", 9.9],
      ]),
    ];
    const us = resolveCrossAssetKpis(series).find((k) => k.key === "us_gov_10y");
    expect(us?.valueLabel).toBe("3.95%");
    expect(us?.resolvedSeriesId).toBe("E1003238");
  });

  it("prefers EM1 precomputed spread over two yield legs", () => {
    const series = [
      macroPoint("EM1", -215, [
        ["2026-02-28", -212],
        ["2026-03-01", -215],
      ], { unit: "bp" }),
      macroPoint("EMM00166466", 2.0, [
        ["2026-02-28", 2.02],
        ["2026-03-01", 2.0],
      ]),
      macroPoint("CA.US_GOV_10Y", 4.0, [
        ["2026-02-28", 3.98],
        ["2026-03-01", 4.0],
      ]),
    ];
    const spread = resolveCrossAssetKpis(series).find((k) => k.key === "gov_spread");
    expect(spread?.label).toBe("中美10Y利差");
    expect(spread?.valueLabel).toBe("-215bp");
    expect(spread?.resolvedSeriesId).toBe("EM1");
    expect(spread?.sparkline.length).toBeGreaterThan(0);
  });

  it("labels CN–US spread when both legs exist", () => {
    const series = [
      macroPoint("EMM00166466", 2.0, [
        ["2026-02-28", 2.02],
        ["2026-03-01", 2.0],
      ]),
      macroPoint("CA.US_GOV_10Y", 4.0, [
        ["2026-02-28", 3.98],
        ["2026-03-01", 4.0],
      ]),
    ];
    const spread = resolveCrossAssetKpis(series).find((k) => k.key === "gov_spread");
    expect(spread?.label).toBe("中美10Y利差");
    expect(spread?.valueLabel).toBe("-200bp");
    expect(spread?.sparkline.length).toBeGreaterThan(0);
  });

  it("falls back to CDB–gov spread when US leg is missing", () => {
    const series = [
      macroPoint("EMM00166466", 2.0, [
        ["2026-02-28", 2.02],
        ["2026-03-01", 2.0],
      ]),
      macroPoint("EMM00166502", 2.35, [
        ["2026-02-28", 2.33],
        ["2026-03-01", 2.35],
      ]),
    ];
    const spread = resolveCrossAssetKpis(series).find((k) => k.key === "gov_spread");
    expect(spread?.label).toBe("国开-国债10Y");
    expect(spread?.valueLabel).toBe("35bp");
  });

  it("maxCrossAssetHeadlineTradeDate picks latest among resolved headline legs", () => {
    const series = [
      macroPoint("EMM00166466", 2.0, [
        ["2026-02-27", 2.01],
        ["2026-03-02", 2.0],
      ]),
      macroPoint("CA.US_GOV_10Y", 4.0, [
        ["2026-02-27", 3.99],
        ["2026-03-02", 4.0],
      ]),
    ];
    expect(maxCrossAssetHeadlineTradeDate(series)).toBe("2026-03-02");
  });

  it("renames money market fallback to DR007 when CA.DR007 is used", () => {
    const series = [
      macroPoint("CA.DR007", 1.82, [
        ["2026-02-28", 1.8],
        ["2026-03-01", 1.82],
      ]),
    ];
    const liquidity = resolveCrossAssetKpis(series).find((k) => k.key === "money_market_7d");
    expect(liquidity?.label).toBe("DR007");
    expect(liquidity?.resolvedSeriesId).toBe("CA.DR007");
  });
});
