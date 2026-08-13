import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { ibTokens, nocturneTokens } from "../../../theme/designSystem";

import {
  YIELD_CURVE_TENOR_LABELS,
  buildYieldCurveOption,
  buildYieldCurveSeries,
} from "./crossAssetYieldCurve";

function row(seriesName: string, tradeDate: string, value: number): ChoiceMacroLatestPoint {
  return {
    series_id: seriesName,
    series_name: seriesName,
    trade_date: tradeDate,
    value_numeric: value,
    unit: "%",
    source_version: "sv",
    vendor_version: "vv",
    quality_flag: "ok",
  };
}

const GOV_TENORS = ["3个月", "6个月", "1年", "2年", "3年", "5年", "7年", "10年", "30年"];
/** Real 2026-07-22 report-day sample: 10Y dated 07-22, the rest 07-17. */
const GOV_VALUES = [1.091, 1.0953, 1.1441, 1.2645, 1.2887, 1.4466, 1.5683, 1.7297, 2.2425];

function govRows(): ChoiceMacroLatestPoint[] {
  return GOV_TENORS.map((tenor, i) =>
    row(`中债国债到期收益率:${tenor}`, tenor === "10年" ? "2026-07-22" : "2026-07-17", GOV_VALUES[i]!),
  );
}

describe("buildYieldCurveSeries", () => {
  it("hits all 9 tenors for the gov family in fixed order", () => {
    const result = buildYieldCurveSeries(govRows());

    expect(result.labels).toEqual([...YIELD_CURVE_TENOR_LABELS]);
    expect(result.labels).toEqual(["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]);

    expect(result.families).toHaveLength(1);
    const gov = result.families[0]!;
    expect(gov.key).toBe("gov");
    expect(gov.data).toEqual(GOV_VALUES);
    expect(gov.pointCount).toBe(9);
    expect(gov.dates).toHaveLength(9);
    expect(gov.dates[7]).toBe("2026-07-22");
    expect(gov.dates[0]).toBe("2026-07-17");
  });

  it("fills missing tenors with null (AAA 6 points)", () => {
    const rows = [
      row("中债企业债到期收益率(AAA):3个月", "2026-07-17", 1.7),
      row("中债企业债到期收益率(AAA):1年", "2026-07-17", 1.85),
      row("中债企业债到期收益率(AAA):3年", "2026-07-17", 1.95),
      row("中债企业债到期收益率(AAA):5年", "2026-07-17", 2.1),
      row("中债企业债到期收益率(AAA):10年", "2026-07-22", 2.4),
      row("中债企业债到期收益率(AAA):30年", "2026-07-22", 2.7),
    ];
    const result = buildYieldCurveSeries(rows);

    expect(result.families).toHaveLength(1);
    const aaa = result.families[0]!;
    expect(aaa.key).toBe("aaa");
    expect(aaa.pointCount).toBe(6);
    expect(aaa.data).toEqual([1.7, null, 1.85, null, 1.95, 2.1, null, 2.4, 2.7]);
    expect(aaa.dates[1]).toBe("");
    expect(aaa.dates[6]).toBe("");
  });

  it("matches policy-bank names without a colon and keeps families disjoint", () => {
    const rows = [
      row("中债政策性金融债到期收益率(国开行)3个月", "2026-07-17", 1.6),
      row("中债政策性金融债到期收益率(国开行)1年", "2026-07-17", 1.7),
      row("中债政策性金融债到期收益率(国开行)3年", "2026-07-17", 1.8),
      row("中债政策性金融债到期收益率(国开行)5年", "2026-07-17", 1.9),
      row("中债政策性金融债到期收益率(国开行)7年", "2026-07-17", 2.0),
      row("中债政策性金融债到期收益率(国开行)10年", "2026-07-22", 2.05),
      // AAA / AA share a prefix; exact-name matching must not cross-assign.
      row("中债企业债到期收益率(AAA):10年", "2026-07-22", 2.4),
      row("中债企业债到期收益率(AA):10年", "2026-07-22", 2.9),
      // Colon variant is not the upstream convention and must not match.
      row("中债政策性金融债到期收益率(国开行):2年", "2026-07-17", 9.99),
    ];
    const result = buildYieldCurveSeries(rows);

    const policy = result.families.find((family) => family.key === "policy")!;
    expect(policy.pointCount).toBe(6);
    expect(policy.data).toEqual([1.6, null, 1.7, null, 1.8, 1.9, 2.0, 2.05, null]);

    const aaa = result.families.find((family) => family.key === "aaa")!;
    const aa = result.families.find((family) => family.key === "aa")!;
    expect(aaa.pointCount).toBe(1);
    expect(aaa.data[7]).toBe(2.4);
    expect(aa.pointCount).toBe(1);
    expect(aa.data[7]).toBe(2.9);
  });

  it("flags mixed trade dates and reports the earliest/latest span", () => {
    const mixed = buildYieldCurveSeries(govRows());
    expect(mixed.mixedDates).toBe(true);
    expect(mixed.earliestDate).toBe("2026-07-17");
    expect(mixed.latestDate).toBe("2026-07-22");

    const sameDay = buildYieldCurveSeries([
      row("中债国债到期收益率:1年", "2026-07-22", 1.1441),
      row("中债国债到期收益率:10年", "2026-07-22", 1.7297),
    ]);
    expect(sameDay.mixedDates).toBe(false);
    expect(sameDay.earliestDate).toBe("2026-07-22");
    expect(sameDay.latestDate).toBe("2026-07-22");
  });

  it("returns an empty but well-formed result for empty input", () => {
    const result = buildYieldCurveSeries([]);
    expect(result.labels).toHaveLength(9);
    expect(result.families).toEqual([]);
    expect(result.mixedDates).toBe(false);
    expect(result.latestDate).toBeNull();
    expect(result.earliestDate).toBeNull();
  });
});

describe("buildYieldCurveOption", () => {
  it("returns null when no family has any point", () => {
    expect(buildYieldCurveOption(buildYieldCurveSeries([]))).toBeNull();
  });

  it("draws the gov line thicker and connects nulls", () => {
    const option = buildYieldCurveOption(
      buildYieldCurveSeries([...govRows(), row("中债企业债到期收益率(AA):10年", "2026-07-22", 2.9)]),
    );
    expect(option).not.toBeNull();

    const series = option!.series as Array<{ name: string; connectNulls: boolean; lineStyle: { width: number } }>;
    const gov = series.find((s) => s.name === "国债")!;
    const aa = series.find((s) => s.name === "AA 企业债")!;
    expect(gov.connectNulls).toBe(true);
    expect(gov.lineStyle.width).toBeGreaterThan(aa.lineStyle.width);
  });

  it("keeps the light family colors by default", () => {
    const option = buildYieldCurveOption(buildYieldCurveSeries(govRows()));
    const series = option!.series as Array<{ name: string; lineStyle: { color: string } }>;
    expect(series.find((s) => s.name === "国债")!.lineStyle.color).toBe(ibTokens.color.accent);
  });

  it("resolves family and axis colors from the terminal palette", () => {
    const option = buildYieldCurveOption(
      buildYieldCurveSeries([...govRows(), row("中债企业债到期收益率(AAA):10年", "2026-07-22", 2.4)]),
      "terminal",
    );
    const series = option!.series as Array<{ name: string; lineStyle: { color: string } }>;
    expect(series.find((s) => s.name === "国债")!.lineStyle.color).toBe(nocturneTokens.color.blue);
    expect(series.find((s) => s.name === "AAA 企业债")!.lineStyle.color).toBe(nocturneTokens.color.amber);
    const legend = option!.legend as { textStyle: { color: string } };
    expect(legend.textStyle.color).toBe(nocturneTokens.color.inkSoft);
    const yAxis = option!.yAxis as { splitLine: { lineStyle: { color: string } } };
    expect(yAxis.splitLine.lineStyle.color).toBe(nocturneTokens.color.lineSoft);
  });
});
