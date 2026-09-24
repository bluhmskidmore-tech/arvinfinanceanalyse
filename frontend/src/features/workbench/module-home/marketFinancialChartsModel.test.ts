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

  it("uses a single-tenor comparison instead of presenting one tenor as a curve", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const sourceRows = rates.series.slice(0, 2);

    expect(sourceRows).toHaveLength(2);
    rates.series = sourceRows.map((series, index) => ({
      ...series,
      series_id: index === 0 ? "single-gov-10y" : "single-cdb-10y",
      series_name:
        index === 0
          ? "中债国债到期收益率:10年"
          : "中债政策性金融债到期收益率(国开行)10年",
      trade_date: "2026-07-30",
      unit: "%",
      value_numeric: index === 0 ? 1.71 : 1.84,
    }));

    const sections = buildMarketFinancialChartSections({ rates });
    const curve = sections.find((section) => section.key === "rates")!.charts[0]!;
    const optionSeries = curve.option!.series as Array<{
      data: number[];
      type: string;
    }>;

    // 期限计数收进结构化 display / 脚注，副标题保持「日期 · 单位」单分隔符（C17）。
    expect(curve.subtitle).toBe("2026-07-30 · 收益率 %");
    expect(curve.footnote).toContain(
      "当前仅返回一个期限，暂不能判断曲线形态。",
    );
    expect(curve.yieldCurveDisplay).toEqual({
      kind: "single-tenor",
      message: "当前仅返回一个期限，暂不能判断曲线形态。",
      rows: [
        {
          curve: "国债",
          tenorLabel: "10Y",
          tradeDate: "2026-07-30",
          unit: "%",
          value: 1.71,
        },
        {
          curve: "国开",
          tenorLabel: "10Y",
          tradeDate: "2026-07-30",
          unit: "%",
          value: 1.84,
        },
      ],
      tenorLabel: "10Y",
      uniqueTenorCount: 1,
    });
    expect(optionSeries).toHaveLength(1);
    expect(optionSeries[0]).toMatchObject({
      data: [1.71, 1.84],
      type: "bar",
    });
  });

  it("keeps one returned quote without claiming a two-curve comparison", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const sourceRow = rates.series[0];

    expect(sourceRow).toBeDefined();
    rates.series = [
      {
        ...sourceRow!,
        series_id: "single-gov-10y",
        series_name: "中债国债到期收益率:10年",
        trade_date: "2026-07-30",
        unit: "%",
        value_numeric: 1.71,
      },
    ];
    const singleQuote = buildMarketFinancialChartSections({ rates }).find(
      (section) => section.key === "rates",
    )!.charts[0]!;

    expect(singleQuote.yieldCurveDisplay).toMatchObject({
      kind: "single-tenor",
      rows: [{ curve: "国债", value: 1.71 }],
    });
    expect(singleQuote.readingGuide).toContain("读取当前期限的已返回收益率");
    expect(singleQuote.readingGuide).not.toContain("国债与国开");
  });

  it("keeps zero quotes as an explicit no-data state", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    rates.series = [];

    const curve = buildMarketFinancialChartSections({ rates }).find(
      (section) => section.key === "rates",
    )!.charts[0]!;

    expect(curve.subtitle).toBe("日期未返回 · 收益率 %");
    expect(curve.yieldCurveDisplay).toBeUndefined();
    expect(curve.option).toBeNull();
    expect(curve.footnote).toBe("后端未返回可用的国债或国开收益率报价。");
    expect(curve.readingGuide).toContain("不补点、不插值");
  });

  it("does not connect sparse tenors that belong to different curves", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const sourceRows = rates.series.slice(0, 2);

    rates.series = sourceRows.map((series, index) => ({
      ...series,
      series_id: index === 0 ? "sparse-gov-2y" : "sparse-cdb-10y",
      series_name:
        index === 0
          ? "中债国债到期收益率:2年"
          : "中债政策性金融债到期收益率(国开行)10年",
      trade_date: "2026-07-30",
      unit: "%",
      value_numeric: index === 0 ? 1.61 : 1.84,
    }));

    const curve = buildMarketFinancialChartSections({ rates }).find(
      (section) => section.key === "rates",
    )!.charts[0]!;
    const optionSeries = curve.option!.series as Array<{ type: string }>;

    expect(curve.yieldCurveDisplay).toMatchObject({
      kind: "sparse-tenors",
      uniqueTenorCount: 2,
    });
    expect(curve.footnote).toContain(
      "当前报价未形成同一条曲线的多个期限",
    );
    expect(optionSeries.every((series) => series.type !== "line")).toBe(true);
  });

  it("discloses the tenor coverage gap when one curve returns fewer points", async () => {
    const client = createApiClient({ mode: "mock" });
    const rates = clonePayload((await client.getMarketDataRates()).result);
    const template = rates.series[0]!;

    const quote = (id: string, name: string, value: number) => ({
      ...template,
      series_id: id,
      series_name: name,
      trade_date: "2026-07-30",
      unit: "%",
      value_numeric: value,
    });
    rates.series = [
      quote("gap-gov-1y", "中债国债到期收益率:1年", 1.35),
      quote("gap-gov-2y", "中债国债到期收益率:2年", 1.45),
      quote("gap-gov-10y", "中债国债到期收益率:10年", 1.71),
      quote("gap-cdb-10y", "中债政策性金融债到期收益率(国开行)10年", 1.84),
    ];

    const curve = buildMarketFinancialChartSections({ rates }).find(
      (section) => section.key === "rates",
    )!.charts[0]!;

    // 覆盖缺口披露（C15）：国开点位少于国债时，读图说明里写明缺口，防止误读为换色/形态信号。
    expect(curve.yieldCurveDisplay).toMatchObject({ kind: "curve" });
    expect(curve.readingGuide).toContain("国开仅返回 10Y 共 1 点");
    expect(curve.readingGuide).toContain("数据缺口");
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
