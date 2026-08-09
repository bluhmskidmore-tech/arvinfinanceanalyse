import { describe, expect, it } from "vitest";

import { createApiClient } from "../../../api/client";
import type { ChoiceMacroLatestPayload } from "../../../api/contracts";
import { buildMarketFinancialChartSections } from "./marketFinancialChartsModel";

function clonePayload(payload: ChoiceMacroLatestPayload): ChoiceMacroLatestPayload {
  return {
    ...payload,
    series: payload.series.map((series) => ({
      ...series,
      recent_points: series.recent_points?.map((point) => ({ ...point })),
    })),
  };
}

describe("marketFinancialChartsModel", () => {
  it("keeps missing trade dates as null gaps instead of connecting the line", async () => {
    const client = createApiClient({ mode: "mock" });
    const latest = clonePayload((await client.getChoiceMacroLatest()).result);
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const dr007 = latest.series.find((series) => series.series_id === "M002");

    expect(dr007?.recent_points).toBeDefined();
    dr007!.recent_points = [
      {
        trade_date: "2026-04-03",
        value_numeric: 1.8,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-04",
        value_numeric: 1.81,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-05",
        value_numeric: 1.82,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-07",
        value_numeric: 1.83,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-08",
        value_numeric: 1.84,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-09",
        value_numeric: 1.85,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-10",
        value_numeric: 1.86,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-04-11",
        value_numeric: 1.87,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
    ];

    const sections = buildMarketFinancialChartSections({ latest, rates });
    const trend = sections.find((section) => section.key === "rates")!.charts[1]!;
    const option = trend.option!;
    const xAxis = option.xAxis as { data: string[] };
    const optionSeries = option.series as Array<{
      name: string;
      connectNulls: boolean;
      data: Array<number | null>;
    }>;
    const dr007Line = optionSeries.find((item) => item.name === "DR007");
    const gapIndex = xAxis.data.indexOf("2026-04-06");

    expect(dr007Line?.connectNulls).toBe(false);
    expect(gapIndex).toBeGreaterThanOrEqual(0);
    expect(dr007Line?.data[gapIndex]).toBeNull();
  });

  it("uses one coherent trade date for the yield curve instead of mixing tenor dates", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const oneYear = rates.series.find((series) => series.series_id === "M003");
    const twoYear = rates.series.find(
      (series) => series.series_id === "EMM00588704",
    );
    const tenYear = rates.series.find(
      (series) => series.series_id === "EMM00166466",
    );

    expect(oneYear).toBeDefined();
    expect(twoYear).toBeDefined();
    expect(tenYear).toBeDefined();

    oneYear!.trade_date = "2026-07-29";
    oneYear!.value_numeric = 1.55;
    twoYear!.trade_date = "2026-07-29";
    twoYear!.value_numeric = 1.65;
    tenYear!.trade_date = "2026-07-30";
    tenYear!.value_numeric = 1.85;

    const sections = buildMarketFinancialChartSections({ rates });
    const curve = sections.find((section) => section.key === "rates")!.charts[0]!;
    const option = curve.option!;
    const xAxis = option.xAxis as { data: string[] };
    const optionSeries = option.series as Array<{
      connectNulls: boolean;
      data: Array<number | null>;
    }>;

    expect(curve.subtitle).toContain("2026-07-29");
    expect(curve.subtitle).toContain("2");
    expect(xAxis.data).toEqual(["1Y", "2Y"]);
    expect(optionSeries.every((item) => item.connectNulls === false)).toBe(true);
  });

  it("keeps the cross-asset normalization transparent and starts each series at 100", async () => {
    const client = createApiClient({ mode: "mock" });
    const latest = clonePayload((await client.getChoiceMacroLatest()).result);

    const sections = buildMarketFinancialChartSections({ latest });
    const cross = sections.find((section) => section.key === "cross")!;
    const option = cross.charts[0]!.option!;
    const lineSeries = option.series as Array<{ data: Array<number | null> }>;

    expect(cross.charts[0]!.subtitle).toContain("100");
    expect(
      lineSeries.map((item) => item.data.find((value) => value !== null)),
    ).toEqual(Array(lineSeries.length).fill(100));
  });
});
