import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { MARKET_CHART_STATIC_PALETTE } from "./marketChartPalette";
import {
  buildMarketFinancialChartSections,
  DENSE_FIRST_SCREEN_CHART_PICKS,
  innerGapNotes,
  innerGapRanges,
  orphanSymbolSize,
  sharedDateAxis,
} from "./marketFinancialChartsModel";

/** 最近 20 个交易日：与后端 recent_points 每序列取 20 行的窗口长度一致。 */
const CURRENT_TRADE_DATES = [
  "2026-07-28",
  "2026-07-29",
  "2026-07-30",
  "2026-07-31",
  "2026-08-03",
  "2026-08-04",
  "2026-08-05",
  "2026-08-06",
  "2026-08-07",
  "2026-08-10",
  "2026-08-11",
  "2026-08-12",
  "2026-08-13",
  "2026-08-14",
  "2026-08-17",
  "2026-08-18",
  "2026-08-19",
  "2026-08-20",
  "2026-08-21",
  "2026-08-24",
] as const;

/** 停更序列：同样 20 行，但窗口整体偏左，止于 2026-08-10。 */
const STALE_TRADE_DATES = [
  "2026-07-14",
  "2026-07-15",
  "2026-07-16",
  "2026-07-17",
  "2026-07-20",
  "2026-07-21",
  "2026-07-22",
  "2026-07-23",
  "2026-07-24",
  "2026-07-27",
  "2026-07-28",
  "2026-07-29",
  "2026-07-30",
  "2026-07-31",
  "2026-08-03",
  "2026-08-04",
  "2026-08-05",
  "2026-08-06",
  "2026-08-07",
  "2026-08-10",
] as const;

/**
 * 政策操作类序列的真实生产形态：等长窗口向左拉宽，且 2026-08-11–2026-08-20
 * 无操作观测（供应商侧无数据），随后恢复。中段是真实缺口而非停更。
 */
const GAPPED_REPO_TRADE_DATES = [
  ...STALE_TRADE_DATES,
  "2026-08-21",
  "2026-08-24",
] as const;

function ratePoint(
  seriesId: string,
  seriesName: string,
  tradeDates: readonly string[],
  baseValue: number,
): ChoiceMacroLatestPoint {
  const points = tradeDates.map((tradeDate, index) => ({
    trade_date: tradeDate,
    value_numeric: baseValue + index * 0.001,
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    quality_flag: "ok" as const,
  }));
  const latest = points[points.length - 1];
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: latest.trade_date,
    value_numeric: latest.value_numeric,
    unit: "%",
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    recent_points: points,
  };
}

function keyRatePayload(): ChoiceMacroLatestPayload {
  return {
    read_target: "duckdb",
    series: [
      ratePoint(
        "EMM00166466",
        "中债国债到期收益率:10年",
        CURRENT_TRADE_DATES,
        1.68,
      ),
      ratePoint(
        "EMM00588704",
        "中债国债到期收益率:2年",
        CURRENT_TRADE_DATES,
        1.24,
      ),
      ratePoint(
        "CA.DR007",
        "银行间质押式回购加权利率:DR007",
        CURRENT_TRADE_DATES,
        1.42,
      ),
      ratePoint(
        "EMM00088132",
        "公开市场操作:逆回购:7天:中标利率",
        STALE_TRADE_DATES,
        1.4,
      ),
    ],
  };
}

function keyRateChart(rates: ChoiceMacroLatestPayload) {
  const sections = buildMarketFinancialChartSections({ rates });
  const chart = sections
    .flatMap((section) => section.charts)
    .find((candidate) => candidate.key === "key-rate-trend");
  if (!chart) throw new Error("key-rate-trend chart missing");
  return chart;
}

function findChart(
  input: Parameters<typeof buildMarketFinancialChartSections>[0],
  key: string,
) {
  const chart = buildMarketFinancialChartSections(input)
    .flatMap((section) => section.charts)
    .find((candidate) => candidate.key === key);
  if (!chart) throw new Error(`${key} chart missing`);
  return chart;
}

/** 同一交易日的单条收益率报价：期限结构图只读 series 级最新值。 */
function curveQuote(
  seriesId: string,
  seriesName: string,
  value: number,
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: "2026-08-25",
    value_numeric: value,
    unit: "%",
    source_version: "source-v1",
    vendor_version: "vendor-v1",
  };
}

/** 跨资产序列：最新一期变动图取 recent_points 末两点的百分比变化。 */
function crossAssetSeries(
  seriesId: string,
  seriesName: string,
  values: readonly number[],
): ChoiceMacroLatestPoint {
  const points = values.map((value, index) => ({
    trade_date: CURRENT_TRADE_DATES[index],
    value_numeric: value,
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    quality_flag: "ok" as const,
  }));
  const latest = points[points.length - 1];
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: latest.trade_date,
    value_numeric: latest.value_numeric,
    unit: "点",
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    recent_points: points,
  };
}

describe("innerGapNotes", () => {
  const axis = [
    "2026-08-03",
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
  ];

  it("collapses consecutive missing axis dates into one range", () => {
    expect(
      innerGapNotes(
        [{ name: "7D 逆回购", dates: ["2026-08-03", "2026-08-07"] }],
        axis,
      ),
    ).toEqual(["7D 逆回购 2026-08-04–2026-08-06 无观测"]);
  });

  it("lists single-day gaps and separate runs individually", () => {
    expect(
      innerGapNotes(
        [{ name: "DR007", dates: ["2026-08-03", "2026-08-05", "2026-08-07"] }],
        axis,
      ),
    ).toEqual(["DR007 2026-08-04、2026-08-06 无观测"]);
  });

  it("ignores blanks outside the series own first and last observation", () => {
    // 首观测前/末观测后的空白分别由日轴收敛与停更披露处理，不算窗口内缺口。
    expect(
      innerGapNotes(
        [{ name: "SHIBOR 1M", dates: ["2026-08-04", "2026-08-05"] }],
        axis,
      ),
    ).toEqual([]);
    expect(innerGapNotes([{ name: "空序列", dates: [] }], axis)).toEqual([]);
  });

  it("exposes the raw ranges for in-chart gap marking", () => {
    expect(
      innerGapRanges(["2026-08-03", "2026-08-05", "2026-08-07"], axis),
    ).toEqual([
      { start: "2026-08-04", end: "2026-08-04" },
      { start: "2026-08-06", end: "2026-08-06" },
    ]);
    expect(innerGapRanges(["2026-08-03", "2026-08-07"], axis)).toEqual([
      { start: "2026-08-04", end: "2026-08-06" },
    ]);
  });
});

describe("orphanSymbolSize", () => {
  it("sizes only points whose neighbours are both missing", () => {
    const size = orphanSymbolSize([null, 1.4, null, 1.41, 1.42], 5);
    expect(size(1.4, { dataIndex: 1 })).toBe(5);
    expect(size(1.41, { dataIndex: 3 })).toBe(0);
    expect(size(1.42, { dataIndex: 4 })).toBe(0);
    expect(size(null, { dataIndex: 2 })).toBe(0);
  });

  it("treats the window edges as missing neighbours", () => {
    const size = orphanSymbolSize([1.4, null, 1.41], 4);
    expect(size(1.4, { dataIndex: 0 })).toBe(4);
    expect(size(1.41, { dataIndex: 2 })).toBe(4);
  });
});

describe("sharedDateAxis", () => {
  it("crops the axis to the latest common start date", () => {
    expect(
      sharedDateAxis([
        ["2026-08-03", "2026-08-04", "2026-08-05"],
        ["2026-08-04", "2026-08-05"],
      ]),
    ).toEqual(["2026-08-04", "2026-08-05"]);
  });

  it("keeps the full union when cropping would leave a series with one point", () => {
    // 交错的稀疏观测：裁到 2026-08-04 会让第一条序列只剩一个孤点。
    expect(
      sharedDateAxis([
        ["2026-08-03", "2026-08-05"],
        ["2026-08-04", "2026-08-06"],
      ]),
    ).toEqual(["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]);
  });

  it("returns the union for a single series", () => {
    expect(sharedDateAxis([["2026-08-05", "2026-08-03"]])).toEqual([
      "2026-08-03",
      "2026-08-05",
    ]);
  });
});

describe("buildKeyRateTrend", () => {
  it.each([0, 1])("requires eight finite observations instead of eight rows when only %i are observed", (observedCount) => {
    const source = ratePoint("EMM00166466", "中债国债到期收益率:10年", CURRENT_TRADE_DATES.slice(0, 8), 1.68);
    source.recent_points!.slice(observedCount).forEach((point) => { point.value_numeric = null; });
    source.value_numeric = null;
    const chart = keyRateChart({ read_target: "duckdb", series: [source] });

    expect(chart.option).toBeNull();
    expect(chart.footnote).toContain("0 条百分比利率序列");
  });

  it("does not count explicit null tail rows as observations when aligning windows", () => {
    const early = ratePoint("EMM00166466", "中债国债到期收益率:10年", CURRENT_TRADE_DATES.slice(0, 10), 1.68);
    early.recent_points!.slice(-2).forEach((point) => { point.value_numeric = null; });
    early.value_numeric = null;
    const later = ratePoint("CA.DR007", "银行间质押式回购加权利率:DR007", CURRENT_TRADE_DATES.slice(8, 16), 1.42);
    const chart = keyRateChart({ read_target: "duckdb", series: [early, later] });
    const xAxis = Array.isArray(chart.option?.xAxis) ? chart.option.xAxis[0] : chart.option?.xAxis;
    const plottedSeries = Array.isArray(chart.option?.series) ? chart.option.series : [];
    const earlyData = (plottedSeries.find((series) => series?.name === "国债 10Y")?.data ?? []) as (number | null)[];

    expect(xAxis).toMatchObject({ data: CURRENT_TRADE_DATES.slice(0, 16) });
    expect(earlyData.filter((value) => value !== null)).toEqual(
      early.recent_points!.slice(0, 8).map((point) => point.value_numeric),
    );
    expect(chart.footnote).toContain("国债 10Y 最新观测 2026-08-06");
  });

  it.each([null, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("preserves explicit missing date ticks and discloses invalid gap rows %s", (value) => {
    const repo = ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", CURRENT_TRADE_DATES, 1.4);
    repo.recent_points!.slice(10, 18).forEach((point) => { point.value_numeric = value; });
    const dr007 = ratePoint("CA.DR007", "银行间质押式回购加权利率:DR007", CURRENT_TRADE_DATES.filter((_, index) => index < 10 || index >= 18), 1.42);
    const chart = keyRateChart({ read_target: "duckdb", series: [repo, dr007] });
    const xAxis = Array.isArray(chart.option?.xAxis) ? chart.option.xAxis[0] : chart.option?.xAxis;
    const plottedSeries = Array.isArray(chart.option?.series) ? chart.option.series : [];
    const repoSeries = plottedSeries.find((series) => series?.name === "7D 逆回购") as Record<string, unknown> | undefined;
    const repoData = (repoSeries?.data ?? []) as (number | null)[];

    expect(xAxis).toMatchObject({ data: [...CURRENT_TRADE_DATES] });
    expect(repoData.slice(10, 18)).toEqual(Array(8).fill(null));
    expect(chart.footnote).toContain("7D 逆回购 2026-08-11–2026-08-20 无观测");
    expect(repoSeries?.markArea).toMatchObject({
      silent: true,
      itemStyle: { opacity: 0.035 },
      data: [[{ xAxis: "2026-08-11" }, { xAxis: "2026-08-20" }]],
    });
  });

  it("aligns the date axis so a stale series cannot widen it", () => {
    const chart = keyRateChart(keyRatePayload());
    const xAxis = Array.isArray(chart.option?.xAxis)
      ? chart.option.xAxis[0]
      : chart.option?.xAxis;

    expect(xAxis).toMatchObject({ data: [...CURRENT_TRADE_DATES] });
    expect(chart.subtitle).toBe("2026-07-28–2026-08-24 · %");
  });

  it("discloses the stale series instead of leaving an unexplained blank", () => {
    const chart = keyRateChart(keyRatePayload());
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const repoData = (plottedSeries.find(
      (series) => series?.name === "7D 逆回购",
    )?.data ?? []) as (number | null)[];

    expect(repoData.filter((value) => value !== null)).toHaveLength(10);
    expect(repoData.slice(-10).every((value) => value === null)).toBe(true);
    expect(chart.footnote).toContain("7D 逆回购 最新观测 2026-08-10");
    expect(chart.footnote).toContain("日轴对齐到各序列共同起点");
  });

  it("keeps every observation when all series share one window", () => {
    const rates = keyRatePayload();
    rates.series = rates.series.filter(
      (series) => series.series_id !== "EMM00088132",
    );
    const chart = keyRateChart(rates);
    const xAxis = Array.isArray(chart.option?.xAxis)
      ? chart.option.xAxis[0]
      : chart.option?.xAxis;

    expect(xAxis).toMatchObject({ data: [...CURRENT_TRADE_DATES] });
    expect(chart.footnote).not.toContain("最新观测");
    expect(chart.footnote).not.toContain("缺口段留空");
  });

  it("discloses a mid-window gap as a dated range instead of a bare broken line", () => {
    const rates = keyRatePayload();
    rates.series = rates.series.map((series) =>
      series.series_id === "EMM00088132"
        ? ratePoint(
            "EMM00088132",
            "公开市场操作:逆回购:7天:中标利率",
            GAPPED_REPO_TRADE_DATES,
            1.4,
          )
        : series,
    );
    const chart = keyRateChart(rates);
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const repoSeries = plottedSeries.find(
      (series) => series?.name === "7D 逆回购",
    ) as Record<string, unknown> | undefined;
    const repoData = (repoSeries?.data ?? []) as (number | null)[];

    // 轴收敛到共同起点 2026-07-28；缺口段（08-11..08-20，轴索引 10..17）保持为空。
    expect(repoData.slice(10, 18).every((value) => value === null)).toBe(true);
    expect(repoData[9]).not.toBeNull();
    expect(repoData[18]).not.toBeNull();
    expect(chart.footnote).toContain(
      "7D 逆回购 2026-08-11–2026-08-20 无观测，缺口段留空。",
    );
    expect(chart.footnote).not.toContain("最新观测");
    // 缺口段同时有图内纵带标注；无缺口序列不携带 markArea。
    expect(repoSeries?.markArea).toMatchObject({
      silent: true,
      itemStyle: { opacity: 0.035 },
      data: [[{ xAxis: "2026-08-11" }, { xAxis: "2026-08-20" }]],
    });
    const dr007Series = plottedSeries.find(
      (series) => series?.name === "DR007",
    ) as Record<string, unknown> | undefined;
    expect(dr007Series?.markArea).toBeUndefined();
  });

  it("gives the decision-useful rates stronger lines and quiets chart scaffolding", () => {
    const chart = keyRateChart(keyRatePayload());
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const yAxis = Array.isArray(chart.option?.yAxis)
      ? chart.option.yAxis[0]
      : chart.option?.yAxis;
    const seriesByName = (name: string) =>
      plottedSeries.find((series) => series?.name === name) as
        | Record<string, unknown>
        | undefined;

    expect(yAxis).toMatchObject({
      splitNumber: 4,
      splitLine: { lineStyle: { opacity: 0.28 } },
    });
    expect(seriesByName("国债 10Y")?.lineStyle).toMatchObject({
      width: 2.1,
      opacity: 0.96,
    });
    expect(seriesByName("DR007")?.lineStyle).toMatchObject({
      width: 2.1,
      opacity: 0.96,
    });
    expect(seriesByName("国债 2Y")?.lineStyle).toMatchObject({
      width: 1.1,
      opacity: 0.5,
    });
    expect(seriesByName("7D 逆回购")?.lineStyle).toMatchObject({
      width: 1.1,
      opacity: 0.5,
    });
    expect(chart.footnote).toContain("缺口留空，不插值");
  });

  it.each([
    { vendor_name: "public_repo_rate_query", policy_note: null },
    { vendor_name: "public-fallback", policy_note: "public fallback headline lane via repo_rate_query FDR007; not the exact Choice weighted interbank lending 7D series" },
  ])("labels an evidenced FDR007 source in the key-rate legend without changing its observations", (identity) => {
    const rates = keyRatePayload();
    const source = rates.series.find((series) => series.series_id === "CA.DR007")!;
    Object.assign(source, identity);
    const chart = keyRateChart(rates);
    const plottedSeries = Array.isArray(chart.option?.series) ? chart.option.series : [];
    const proxy = plottedSeries.find((series) => series?.name === "FDR007（代理参考）") as Record<string, unknown> | undefined;

    expect(proxy).toBeDefined();
    expect(proxy?.data).toEqual(source.recent_points!.map((point) => point.value_numeric));
    expect(proxy?.lineStyle).toMatchObject({ width: 2.1, opacity: 0.96 });
    expect(plottedSeries.some((series) => series?.name === "DR007")).toBe(false);
    expect(source.series_name).toBe("银行间质押式回购加权利率:DR007");
  });

  it.each([
    { vendor_name: "choice", policy_note: "DR007 weighted rate" },
    { vendor_name: null, policy_note: "proxy; source identity unverified" },
  ])("does not relabel DR007 as FDR007 without an explicit FDR source identity", (identity) => {
    const rates = keyRatePayload();
    Object.assign(rates.series.find((series) => series.series_id === "CA.DR007")!, identity);
    const chart = keyRateChart(rates);
    const plottedSeries = Array.isArray(chart.option?.series) ? chart.option.series : [];

    expect(plottedSeries.some((series) => series?.name === "DR007")).toBe(true);
    expect(plottedSeries.some((series) => series?.name === "FDR007（代理参考）")).toBe(false);
  });
});

describe("buildYieldCurveChart", () => {
  it("discloses the missing CDB curve when only treasury quotes return", () => {
    const chart = findChart(
      {
        rates: {
          read_target: "duckdb",
          series: [
            curveQuote("gov-2y", "中债国债到期收益率:2年", 1.24),
            curveQuote("gov-5y", "中债国债到期收益率:5年", 1.45),
            curveQuote("gov-10y", "中债国债到期收益率:10年", 1.68),
          ],
        },
      },
      "yield-curve",
    );
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];

    // 仍按曲线渲染（单曲线多期限是合法形态），但脚注与导读必须披露缺失方。
    expect(chart.yieldCurveDisplay).toEqual({
      kind: "curve",
      uniqueTenorCount: 3,
    });
    expect(plottedSeries.map((series) => series?.name)).toEqual(["国债"]);
    expect(chart.footnote).toContain("国开未返回本日报价，仅绘制国债曲线");
    expect(chart.readingGuide).toBe(
      "比较同一日期国债各期限的斜率；国开未返回本日报价，不比较两条曲线的相对水平。",
    );
    expect(chart.readingGuide).not.toContain("以及国债与国开的相对水平");
  });

  it("discloses the missing treasury curve symmetrically", () => {
    const chart = findChart(
      {
        rates: {
          read_target: "duckdb",
          series: [
            curveQuote("cdb-2y", "中债政策性金融债到期收益率(国开行)2年", 1.35),
            curveQuote(
              "cdb-10y",
              "中债政策性金融债到期收益率(国开行)10年",
              1.84,
            ),
          ],
        },
      },
      "yield-curve",
    );

    expect(chart.footnote).toContain("国债未返回本日报价，仅绘制国开曲线");
    expect(chart.readingGuide).toContain("国债未返回本日报价");
  });

  it("positions tenors proportionally on a value axis", () => {
    const chart = findChart(
      {
        rates: {
          read_target: "duckdb",
          series: [
            curveQuote("gov-1y", "中债国债到期收益率:1年", 1.1),
            curveQuote("gov-10y", "中债国债到期收益率:10年", 1.68),
            curveQuote("gov-30y", "中债国债到期收益率:30年", 1.95),
            curveQuote("cdb-10y", "中债政策性金融债到期收益率(国开行)10年", 1.84),
          ],
        },
      },
      "yield-curve",
    );
    const option = chart.option as unknown as {
      xAxis: {
        type: string;
        min: number;
        max: number;
        axisLabel: { formatter: (value: number) => string };
      };
      series: { name?: string; data: [number, number | null][] }[];
    };

    // category 等距轴会把 1Y-10Y 与 10Y-30Y 画成等宽，扭曲斜率读数：
    // 横轴必须是数值轴，series 数据为 [期限, 收益率] 数值对。
    expect(option.xAxis.type).toBe("value");
    expect(option.xAxis.min).toBe(0);
    expect(option.xAxis.max).toBe(30);
    expect(option.xAxis.axisLabel.formatter(10)).toBe("10Y");
    expect(
      option.series.find((series) => series.name === "国债")?.data,
    ).toEqual([
      [1, 1.1],
      [10, 1.68],
      [30, 1.95],
    ]);
    // 缺测期限保留 null 断点，不允许跨缺口直连成假斜率。
    expect(
      option.series.find((series) => series.name === "国开")?.data,
    ).toEqual([
      [1, null],
      [10, 1.84],
      [30, null],
    ]);
  });

  it("keeps tenor and yield readable in the value-axis tooltip", () => {
    const chart = findChart(
      {
        rates: {
          read_target: "duckdb",
          series: [
            curveQuote("gov-2y", "中债国债到期收益率:2年", 1.24),
            curveQuote("gov-10y", "中债国债到期收益率:10年", 1.68),
            curveQuote("cdb-2y", "中债政策性金融债到期收益率(国开行)2年", 1.35),
          ],
        },
      },
      "yield-curve",
    );
    const formatter = (
      chart.option as unknown as {
        tooltip: { formatter: (params: unknown) => string };
      }
    ).tooltip.formatter;

    expect(
      formatter([
        { seriesName: "国债", marker: "", value: [2, 1.24] },
        { seriesName: "国开", marker: "", value: [2, 1.35] },
      ]),
    ).toBe(`2Y<br/>国债 1.240%<br/>国开 1.350%`);
    // 缺测期限的 null 观测按 EM_DASH 披露，不冒充 0。
    expect(
      formatter([
        { seriesName: "国债", marker: "", value: [10, 1.68] },
        { seriesName: "国开", marker: "", value: [10, null] },
      ]),
    ).toBe(`10Y<br/>国债 1.680%<br/>国开 ${EM_DASH}`);
  });

  it("keeps the two-curve comparison guide when both curves return", () => {
    const chart = findChart(
      {
        rates: {
          read_target: "duckdb",
          series: [
            curveQuote("gov-2y", "中债国债到期收益率:2年", 1.24),
            curveQuote("gov-10y", "中债国债到期收益率:10年", 1.68),
            curveQuote("cdb-2y", "中债政策性金融债到期收益率(国开行)2年", 1.35),
            curveQuote(
              "cdb-10y",
              "中债政策性金融债到期收益率(国开行)10年",
              1.84,
            ),
          ],
        },
      },
      "yield-curve",
    );

    expect(chart.readingGuide).toBe(
      "比较同一日期各期限的斜率，以及国债与国开的相对水平。",
    );
    expect(chart.footnote).not.toContain("未返回本日报价");
  });
});

describe("buildLatestCrossAssetMove", () => {
  it("keeps homepage originals and topic references on the same two-chart list", () => {
    const sections = buildMarketFinancialChartSections({});
    expect(DENSE_FIRST_SCREEN_CHART_PICKS.map((pick) =>
      sections.find((section) => section.key === pick.sectionKey)?.charts[pick.chartIndex].key,
    )).toEqual(["key-rate-trend", "cross-asset-move"]);
  });

  it("keeps the footnote aligned with the purple/red bar encoding", () => {
    const chart = findChart(
      {
        latest: {
          read_target: "duckdb",
          series: [
            crossAssetSeries("hs300", "沪深300指数收盘价", [
              96, 96.5, 97, 97.5, 98, 99, 100, 102,
            ]),
            crossAssetSeries("cu", "铜主力期货收盘价", [
              103, 102.5, 102, 101.5, 101, 100.5, 100, 97,
            ]),
          ],
        },
      },
      "cross-asset-move",
    );
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const bars = (plottedSeries[0]?.data ?? []) as Array<{
      value: number;
      itemStyle: { color: string };
    }>;

    expect(chart.footnote).toContain(
      "显示变化率而非绝对点差；正值紫色、负值红色，并以零轴区分方向。",
    );
    // 变动值升序排列：首条为负值（红色），末条为正值（紫色），与脚注一致。
    expect(bars[0]?.value).toBeLessThan(0);
    expect(bars[0]?.itemStyle.color).toBe(MARKET_CHART_STATIC_PALETTE.red);
    expect(bars.at(-1)?.value).toBeGreaterThan(0);
    expect(bars.at(-1)?.itemStyle.color).toBe(
      MARKET_CHART_STATIC_PALETTE.accent,
    );
  });

  it("shows each asset's actual two dates without hover and preserves values and ordering", () => {
    const equity = crossAssetSeries("hs300", "沪深300指数收盘价", [96, 96.5, 97, 97.5, 98, 99, 100, 102]);
    const copper = crossAssetSeries("cu", "铜主力期货收盘价", [103, 102.5, 102, 101.5, 101, 100.5, 100, 97]);
    copper.recent_points![6].trade_date = "2026-08-14";
    copper.recent_points![7].trade_date = "2026-08-18";
    // 顶层 trade_date 不是这张图的比较日期来源，不可替代两条原始观测日期。
    copper.trade_date = "2026-08-25";
    copper.recent_points!.reverse();
    const chart = findChart({ latest: { read_target: "duckdb", series: [equity, copper] } }, "cross-asset-move");
    const option = chart.option as unknown as {
      yAxis: { data: string[]; axisLabel: { interval: number } };
      series: { data: { value: number; previousDate: string; latestDate: string }[] }[];
    };

    expect(option.yAxis.data[0]).toContain("\n2026-08-14\n至 2026-08-18");
    expect(option.yAxis.data[1]).toContain("\n2026-08-05\n至 2026-08-06");
    expect(option.yAxis.data.join(" ")).not.toContain("2026-08-25");
    expect(option.yAxis.axisLabel.interval).toBe(0);
    expect(option.series[0].data).toMatchObject([
      { value: -3, previousDate: "2026-08-14", latestDate: "2026-08-18" },
      { value: 2, previousDate: "2026-08-05", latestDate: "2026-08-06" },
    ]);
    expect(chart.footnote).toContain("采用各自相邻两期观测，非同日涨跌排行");
  });

  it.each([
    { values: [100], reason: "不足两个有效观测，无法比较" },
    { values: [100, 102], reason: "历史观测不足 8 期，本图暂不展示" },
    { values: [100, 100, 100, 100, 100, 100, 0, 102], reason: "前值为零，无法计算变化率" },
    { values: [NaN, NaN, NaN, NaN, NaN, NaN, NaN, 102], reason: "不足两个有效观测，无法比较" },
  ])("discloses an unavailable comparison instead of inventing a zero bar: $reason", ({ values, reason }) => {
    const chart = findChart({ latest: { read_target: "duckdb", series: [crossAssetSeries("hs300", "沪深300指数收盘价", values)] } }, "cross-asset-move");
    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("0 类资产");
    expect(chart.footnote).toContain(reason);
  });

  it.each(["", "日期未返回", "2026-13-08", "2026-02-30", "2026-09-31", "2026-02-29"])("does not substitute the page date for an absent or invalid observation date: %s", (invalidDate) => {
    const source = crossAssetSeries("hs300", "沪深300指数收盘价", [96, 96.5, 97, 97.5, 98, 99, 100, 102]);
    source.recent_points![7].trade_date = invalidDate;
    const chart = findChart({ latest: { read_target: "duckdb", series: [source] } }, "cross-asset-move");
    expect(chart.option).toBeNull();
    expect(chart.footnote).toContain("观测日期缺失或格式无效，无法核验比较区间");
  });

  it("accepts a real leap day without changing its observation date or variation", () => {
    const source = crossAssetSeries("hs300", "沪深300指数收盘价", [96, 96.5, 97, 97.5, 98, 99, 100, 102]);
    source.recent_points!.forEach((point, index) => {
      point.trade_date = `2024-02-${22 + index}`;
    });
    const chart = findChart({ latest: { read_target: "duckdb", series: [source] } }, "cross-asset-move");
    const option = chart.option as unknown as {
      yAxis: { data: string[] };
      series: { data: { value: number; previousDate: string; latestDate: string }[] }[];
    };
    expect(option.yAxis.data[0]).toContain("\n2024-02-28\n至 2024-02-29");
    expect(option.series[0].data[0]).toMatchObject({
      value: 2,
      previousDate: "2024-02-28",
      latestDate: "2024-02-29",
    });
    expect(chart.footnote).not.toContain("日期缺失或格式无效");
  });

  it("discloses duplicate latest dates rather than implying two distinct observation periods", () => {
    const source = crossAssetSeries("hs300", "沪深300指数收盘价", [96, 96.5, 97, 97.5, 98, 99, 100, 102]);
    source.recent_points![7].trade_date = source.recent_points![6].trade_date;
    const chart = findChart({ latest: { read_target: "duckdb", series: [source] } }, "cross-asset-move");
    expect(chart.option).toBeNull();
    expect(chart.footnote).toContain("最近两个有效观测日期重复，无法核验两期比较");
  });
});
