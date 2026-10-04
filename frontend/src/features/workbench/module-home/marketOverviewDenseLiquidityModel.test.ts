import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
} from "../../../api/contracts";
import {
  buildDenseLiquidityChartSpec,
  buildDenseLiquiditySeries,
} from "./marketOverviewDenseLiquidityModel";

function ratePoint(
  seriesId: string,
  seriesName: string,
  latestValue: number,
  unit = "%",
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: "2026-07-27",
    value_numeric: latestValue,
    unit,
    source_version: "source-v1",
    vendor_version: "vendor-v1",
    recent_points: [
      {
        trade_date: "2026-07-25",
        value_numeric: latestValue - 0.02,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-07-26",
        value_numeric: latestValue - 0.01,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
    ],
  };
}

/** 最近 20 个交易日：与后端 recent_points 每序列取 20 行的窗口长度一致。 */
const DR007_TRADE_DATES = [
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
const STALE_REPO_TRADE_DATES = [
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

function seriesWithTradeDates(
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

function ratesPayload(): ChoiceMacroLatestPayload {
  return {
    read_target: "duckdb",
    series: [
      ratePoint("CA.DR007", "DR007", 1.42),
      ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4),
      ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41),
      ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43),
    ],
  };
}

describe("marketOverviewDenseLiquidityModel", () => {
  it("selects only the four governed liquidity series in display order", () => {
    const series = buildDenseLiquiditySeries(ratesPayload());

    expect(
      series.map(({ key, role }) => ({ key, role })),
    ).toEqual([
      { key: "dr007", role: "市场资金利率" },
      { key: "repo-7d", role: "政策操作利率" },
      { key: "shibor-1m", role: "期限报价" },
      { key: "shibor-3m", role: "期限报价" },
    ]);
    expect(series[0].points).toEqual([
      { date: "2026-07-25", value: 1.4 },
      { date: "2026-07-26", value: 1.41 },
      { date: "2026-07-27", value: 1.42 },
    ]);
    expect(series[0].readingHint).toBe("观察 DR007 市场资金利率走势");
  });

  it("builds a source-backed chart without inventing a spread series", () => {
    const chart = buildDenseLiquidityChartSpec(ratesPayload());

    expect(chart.key).toBe("liquidity-tenor");
    expect(chart.title).toBe("流动性期限与资金利率");
    // 序列条数明细收进脚注，副标题保持单个 `·` 配额（DESIGN.md §7）。
    expect(chart.footnote).toContain("共 4 条正式序列");
    expect(chart.option).not.toBeNull();
    expect(chart.footnote).toContain("不插值、不派生利差");
    expect(chart.status).toBe("ready");
    expect(chart.readingHint).toContain("DR007 看市场资金利率");
    expect(chart.seriesRoles).toEqual([
      {
        key: "dr007",
        label: "DR007",
        role: "市场资金利率",
        readingHint: "观察 DR007 市场资金利率走势",
        observationCount: 3,
        status: "ready",
      },
      {
        key: "repo-7d",
        label: "7D逆回购",
        role: "政策操作利率",
        readingHint: "观察公开市场操作7天中标利率；中标利率仅产生于操作日",
        observationCount: 3,
        status: "ready",
      },
      {
        key: "shibor-1m",
        label: "SHIBOR 1M",
        role: "期限报价",
        readingHint: "观察1个月期限报价",
        observationCount: 3,
        status: "ready",
      },
      {
        key: "shibor-3m",
        label: "SHIBOR 3M",
        role: "期限报价",
        readingHint: "观察3个月期限报价",
        observationCount: 3,
        status: "ready",
      },
    ]);
  });

  it("reports and omits a singleton series instead of rendering an invisible line", () => {
    const singleton = ratePoint(
      "EMM00088132",
      "公开市场操作:逆回购:7天:中标利率",
      1.4,
    );
    singleton.recent_points = [];
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [ratePoint("CA.DR007", "DR007", 1.42), singleton],
    });
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [chart.option?.series].filter(Boolean);

    expect(chart.status).toBe("partial");
    expect(chart.footnote).toContain("观测不足 1 条");
    expect(chart.seriesRoles[1]).toMatchObject({
      key: "repo-7d",
      observationCount: 1,
      status: "insufficient-observations",
    });
    expect(plottedSeries).toHaveLength(1);
    expect(plottedSeries[0]).toMatchObject({ name: "DR007" });
  });

  it("returns an explicit insufficient state when no series can form a trend", () => {
    const singleton = ratePoint("CA.DR007", "DR007", 1.42);
    singleton.recent_points = [];

    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [singleton],
    });

    expect(chart.status).toBe("insufficient-observations");
    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("观测不足未绘制");
    expect(chart.footnote).toContain("少于 2 个观测");
    expect(chart.footnote).toContain("避免不可见假线");
  });

  it("keeps the date union and visible marks without connecting missing observations", () => {
    const dr007 = ratePoint("CA.DR007", "DR007", 1.42);
    dr007.recent_points = [
      {
        trade_date: "2026-07-25",
        value_numeric: 1.4,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
    ];
    const shibor = ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41);
    shibor.trade_date = "2026-07-26";
    shibor.recent_points = [
      {
        trade_date: "2026-07-24",
        value_numeric: 1.39,
        source_version: "source-v1",
        vendor_version: "vendor-v1",
        quality_flag: "ok",
      },
    ];

    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [dr007, shibor],
    });
    const xAxis = Array.isArray(chart.option?.xAxis)
      ? chart.option.xAxis[0]
      : chart.option?.xAxis;
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];

    expect(xAxis).toMatchObject({
      data: ["2026-07-24", "2026-07-25", "2026-07-26", "2026-07-27"],
    });
    expect(plottedSeries[0]).toMatchObject({
      connectNulls: false,
      showSymbol: true,
      data: [null, 1.4, null, 1.42],
    });
    expect(plottedSeries[1]).toMatchObject({
      connectNulls: false,
      showSymbol: true,
      data: [1.39, null, 1.41, null],
    });
    // 交错稀疏观测全是孤点：每个有值位置都应有可见符号。
    const sizeOf = (plottedSeries[0] as { symbolSize: unknown }).symbolSize as (
      value: unknown,
      params: { dataIndex: number },
    ) => number;
    expect(sizeOf(1.4, { dataIndex: 1 })).toBe(5);
    expect(sizeOf(1.42, { dataIndex: 3 })).toBe(5);
    expect(sizeOf(null, { dataIndex: 0 })).toBe(0);
  });

  it("discloses a mid-window gap as a dated range in the footnote", () => {
    // 政策操作序列真实形态：窗口向左拉宽，08-11..08-20 无操作观测后恢复。
    const gappedRepoDates = [
      ...STALE_REPO_TRADE_DATES,
      "2026-08-21",
      "2026-08-24",
    ];
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        seriesWithTradeDates("CA.DR007", "DR007", DR007_TRADE_DATES, 1.38),
        seriesWithTradeDates(
          "EMM00088132",
          "公开市场操作:逆回购:7天:中标利率",
          gappedRepoDates,
          1.4,
        ),
      ],
    });
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const repoSeries = plottedSeries.find(
      (series) => series?.name === "7D逆回购",
    ) as Record<string, unknown> | undefined;
    const repoData = (repoSeries?.data ?? []) as (number | null)[];

    // 轴收敛到共同起点 2026-07-28；缺口段（08-11..08-20，轴索引 10..17）保持为空。
    expect(repoData.slice(10, 18).every((value) => value === null)).toBe(true);
    expect(repoData[9]).not.toBeNull();
    expect(repoData[18]).not.toBeNull();
    expect(chart.footnote).toContain(
      "7D逆回购 2026-08-11–2026-08-20 无观测，缺口段留空。",
    );
    expect(chart.footnote).not.toContain("最新观测");
    // 缺口段同时有图内纵带标注；无缺口序列不携带 markArea。
    expect(repoSeries?.markArea).toMatchObject({
      silent: true,
      data: [[{ xAxis: "2026-08-11" }, { xAxis: "2026-08-20" }]],
    });
    const dr007Series = plottedSeries.find(
      (series) => series?.name === "DR007",
    ) as Record<string, unknown> | undefined;
    expect(dr007Series?.markArea).toBeUndefined();
  });

  it("aligns the date axis to the common start so a stale series cannot widen it", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        seriesWithTradeDates("CA.DR007", "DR007", DR007_TRADE_DATES, 1.38),
        seriesWithTradeDates(
          "EMM00088132",
          "公开市场操作:逆回购:7天:中标利率",
          STALE_REPO_TRADE_DATES,
          1.4,
        ),
      ],
    });
    const xAxis = Array.isArray(chart.option?.xAxis)
      ? chart.option.xAxis[0]
      : chart.option?.xAxis;
    const plottedSeries = Array.isArray(chart.option?.series)
      ? chart.option.series
      : [];
    const repoSeries = plottedSeries.find(
      (series) => series?.name === "7D逆回购",
    );
    const repoData = (repoSeries?.data ?? []) as (number | null)[];

    // 停更序列的 20 行窗口起点是 2026-07-14，但共同起点是 2026-07-28。
    expect(xAxis).toMatchObject({ data: [...DR007_TRADE_DATES] });
    expect(chart.subtitle).toContain("2026-07-28–2026-08-24");
    expect(repoData.filter((value) => value !== null)).toHaveLength(10);
    expect(repoData.slice(-10).every((value) => value === null)).toBe(true);
    expect(chart.footnote).toContain("7D逆回购 最新观测 2026-08-10");
  });

  it("uses the shared backend unit for axis and tooltip formatting", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "bp"),
        ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4, "bp"),
        ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41, "bp"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "bp"),
      ],
    });

    const yAxis = Array.isArray(chart.option?.yAxis)
      ? chart.option?.yAxis[0]
      : chart.option?.yAxis;
    const tooltip = Array.isArray(chart.option?.tooltip)
      ? chart.option?.tooltip[0]
      : chart.option?.tooltip;
    const formatValue = tooltip?.valueFormatter as
      | ((value: unknown, index: number) => string)
      | undefined;

    expect(chart.option).not.toBeNull();
    expect(chart.subtitle).toContain("· bp");
    expect(yAxis).toMatchObject({
      name: "bp",
    });
    expect(formatValue?.(1.42, 0)).toBe("1.4200bp");
  });

  it("fails closed instead of plotting mixed liquidity units on one axis", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "%"),
        ratePoint("EMM00088132", "公开市场操作:逆回购:7天:中标利率", 1.4, "bp"),
        ratePoint("NCD.SHIBOR.1M", "SHIBOR:1M", 1.41, "%"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "%"),
      ],
    });

    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("单位缺失或不一致未绘制");
    expect(chart.footnote).toContain("不共轴绘制");
  });

  it("fails closed when any selected liquidity series omits its unit", () => {
    const chart = buildDenseLiquidityChartSpec({
      read_target: "duckdb",
      series: [
        ratePoint("CA.DR007", "DR007", 1.42, "%"),
        ratePoint("NCD.SHIBOR.3M", "SHIBOR:3M", 1.43, "unknown"),
      ],
    });

    expect(chart.option).toBeNull();
    expect(chart.subtitle).toContain("单位缺失或不一致未绘制");
  });
});
