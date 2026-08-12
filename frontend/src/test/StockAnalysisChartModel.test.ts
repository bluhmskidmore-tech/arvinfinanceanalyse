import { describe, expect, it } from "vitest";

import type { StockSectorViewRow } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import { dhApiTokens } from "../theme/designSystem";
import {
  buildCompactBarOption,
  buildEventSummaryOption,
  buildOutputChartRows,
  buildReviewQueueChartRows,
  buildReviewQueueRankingOption,
  buildRiskSupplyChartRows,
  buildSectorChartRows,
  buildSectorSeriesTrendOption,
  buildSectorStrengthBarRows,
  buildSectorStrengthCardModel,
  buildSectorStrengthOption,
  resolveSectorMetricValue,
  sectorViewLabel,
  sectorViewTabs,
  stockChartPalette,
} from "../features/stock-analysis/lib/stockAnalysisChartModel";

type ChartSeries = {
  name?: string;
  data: unknown[];
  itemStyle?: { color?: string };
};

type InspectableChartOption = {
  animation?: boolean;
  xAxis?: { min?: number };
  series: ChartSeries[];
  tooltip?: { formatter?: (params: unknown) => string };
};

function inspectChartOption(option: unknown): InspectableChartOption {
  return option as InspectableChartOption;
}

const sectorRow: StockSectorViewRow = {
  rank: 1,
  sectorCode: "BK001",
  sectorName: "半导体",
  score: "0.82",
  pctChange: "+2.35%",
  turnover: "3.10%",
  amplitude: "5.20%",
  constituentCount: 24,
  scoreValue: 0.82,
  pctChangeValue: 2.35,
  turnoverValue: 3.1,
  amplitudeValue: 5.2,
  scoreNormalized: 1,
  pctChangeBar: 0.76,
  isTop: true,
  isBottom: false,
  metricBarNormalized: 1,
};

describe("stockAnalysisChartModel", () => {
  it("sources the chart palette from canonical Decision Desk tokens", () => {
    expect(stockChartPalette).toEqual({
      ink: dhApiTokens.color.ink,
      muted: dhApiTokens.color.inkMuted,
      grid: dhApiTokens.color.lineSoft,
      track: dhApiTokens.color.line,
      primary: dhApiTokens.color.blue,
      primaryLight: dhApiTokens.color.inkMuted,
      accent: dhApiTokens.color.inkSoft,
      success: dhApiTokens.color.green,
      successLight: dhApiTokens.color.greenSoft,
      danger: dhApiTokens.color.red,
      gold: dhApiTokens.color.amber,
    });
  });

  it("exposes stable sector view labels and metric selectors", () => {
    expect(sectorViewTabs).toEqual([
      { key: "score", label: "综合得分" },
      { key: "pctchange", label: "平均涨跌幅" },
      { key: "turnover", label: "换手活跃度" },
      { key: "amplitude", label: "波动振幅" },
    ]);
    expect(sectorViewLabel("score")).toBe("综合得分");
    expect(sectorViewLabel("pctchange")).toBe("平均涨跌幅");
    expect(resolveSectorMetricValue(sectorRow, "score")).toBe(0.82);
    expect(resolveSectorMetricValue(sectorRow, "pctchange")).toBe(2.35);
    expect(resolveSectorMetricValue(sectorRow, "turnover")).toBe(3.1);
    expect(resolveSectorMetricValue(sectorRow, "amplitude")).toBe(5.2);
  });

  it("builds compact bar and ranking chart options with deterministic labels and colors", () => {
    const compactOption = buildCompactBarOption({
      labels: ["A", "B"],
      values: [1.234, 2],
      color: stockChartPalette.accent,
      valueSuffix: "%",
    });
    const rankingOption = buildReviewQueueRankingOption([
      { key: "000001", label: "#1 Alpha", value: 2, detail: "行业 · 证据 3" },
    ]);
    const compact = inspectChartOption(compactOption);
    const ranking = inspectChartOption(rankingOption);

    expect(compact.animation).toBe(false);
    expect(compact.series[0].data).toEqual([1.234, 2]);
    expect(compact.series[0].itemStyle?.color).toBe(stockChartPalette.accent);
    expect(compact.tooltip?.formatter?.({ dataIndex: 0, value: 1.234 })).toBe("A: 1.23%");
    expect(ranking.series[0].itemStyle?.color).toBe(stockChartPalette.success);
    expect(ranking.tooltip?.formatter?.([{ dataIndex: 0 }])).toBe("#1 Alpha<br/>行业 · 证据 3");
  });

  it("builds review queue chart rows from the visible top six candidates", () => {
    const rows = buildReviewQueueChartRows([
      {
        stockCode: "000001.SZ",
        stockName: "Alpha",
        rank: 1,
        sectorName: "Banking",
        distanceToBreakoutPct: "2.4%",
        primaryEvidence: [{ key: "a", label: "A", value: "1" }],
        supportingEvidence: [{ key: "b", label: "B", value: "2" }],
      },
      {
        stockCode: "000002.SZ",
        stockName: "Beta",
        rank: 2,
        sectorName: "Tech",
        distanceToBreakoutPct: "3.1%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
      {
        stockCode: "000003.SZ",
        stockName: "Gamma",
        rank: 3,
        sectorName: "Energy",
        distanceToBreakoutPct: "4.2%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
      {
        stockCode: "000004.SZ",
        stockName: "Delta",
        rank: 4,
        sectorName: "Retail",
        distanceToBreakoutPct: "5.0%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
      {
        stockCode: "000005.SZ",
        stockName: "Epsilon",
        rank: 5,
        sectorName: "Auto",
        distanceToBreakoutPct: "6.0%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
      {
        stockCode: "000006.SZ",
        stockName: "Zeta",
        rank: 6,
        sectorName: "Broker",
        distanceToBreakoutPct: "7.0%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
      {
        stockCode: "000007.SZ",
        stockName: "Eta",
        rank: 7,
        sectorName: "Media",
        distanceToBreakoutPct: "8.0%",
        primaryEvidence: [],
        supportingEvidence: [],
      },
    ]);

    expect(rows).toHaveLength(6);
    expect(rows[0]).toEqual({
      key: "000001.SZ",
      label: "#1 Alpha",
      value: 6,
      detail: "Banking \u00b7 \u8ddd\u89c2\u5bdf\u4f4d 2.4% \u00b7 \u8bc1\u636e 2",
    });
    expect(rows[5]).toMatchObject({
      key: "000006.SZ",
      value: 1,
    });
  });

  it("builds sector, output, and risk supply chart rows from page view data", () => {
    expect(
      buildSectorChartRows([
        {
          ...sectorRow,
          rank: 2,
          sectorCode: "BK002",
          sectorName: "Banking",
          score: "0.72",
          pctChange: "+1.20%",
          scoreValue: 0.72,
        },
      ]),
    ).toEqual([
      {
        key: "BK002",
        label: "2. Banking",
        value: 0.72,
        detail: "0.72 / +1.20%",
      },
    ]);

    expect(buildOutputChartRows({ supportedCount: 3, unsupportedCount: 1 })).toEqual([
      { key: "supported", label: "\u53ef\u7528", value: 3 },
      { key: "unsupported", label: "\u963b\u65ad", value: 1 },
    ]);

    expect(buildOutputChartRows(null)).toEqual([]);
    expect(buildRiskSupplyChartRows(null)).toEqual([
      { key: "position", label: "\u6301\u4ed3", value: 0 },
      { key: "signal", label: "\u89e6\u53d1", value: 0 },
      { key: "watch", label: "\u89c2\u5bdf", value: 0 },
    ]);
    expect(
      buildRiskSupplyChartRows({
        position_count: 4,
        signal_count: 2,
        watch_items: [{ stock_code: "000001.SZ" }, { stock_code: "000002.SZ" }],
      }),
    ).toEqual([
      { key: "position", label: "\u6301\u4ed3", value: 4 },
      { key: "signal", label: "\u89e6\u53d1", value: 2 },
      { key: "watch", label: "\u89c2\u5bdf", value: 2 },
    ]);
  });

  it("builds event and sector strength chart options without recalculating business metrics", () => {
    const eventOption = buildEventSummaryOption([
      { label: "可用", count: 3 },
      { label: "阻断", count: 1 },
    ]);
    const sectorOption = buildSectorStrengthOption({
      rows: [sectorRow],
      view: "pctchange",
      activeSectorCode: "BK001",
    });
    const event = inspectChartOption(eventOption);
    const sector = inspectChartOption(sectorOption);

    expect(event.series.map((item) => item.name)).toEqual(["可用", "阻断"]);
    expect(event.series.map((item) => item.data[0])).toEqual([3, 1]);
    expect(sector.xAxis?.min).toBeLessThan(0);
    expect(sector.series[0].data[0]).toMatchObject({
      value: 2.35,
      itemStyle: { color: stockChartPalette.primary },
    });
    expect(sector.tooltip?.formatter?.([{ dataIndex: 0 }])).toBe(
      "1. 半导体<br/>平均涨跌幅: +2.35%<br/>成分 24",
    );
  });

  it("builds first-screen SVG bar rows on the same caliber as the ECharts sector option", () => {
    const negativeRow: StockSectorViewRow = {
      ...sectorRow,
      rank: 2,
      sectorCode: "BK002",
      sectorName: "银行",
      pctChange: "-1.10%",
      pctChangeValue: -1.1,
    };

    const scoreBars = buildSectorStrengthBarRows({
      rows: [sectorRow],
      view: "score",
      activeSectorCode: "BK001",
    });
    expect(scoreBars).toHaveLength(1);
    // score 视角 X 轴固定 0..1：跨度即后端归一分值，起点在零轴。
    expect(scoreBars[0]).toMatchObject({
      key: "BK001",
      name: "半导体",
      rank: 1,
      valueLabel: "0.82",
      active: true,
      barStartFraction: 0,
    });
    expect(scoreBars[0].barSpanFraction).toBeCloseTo(0.82, 6);
    expect(scoreBars[0].title).toBe("1. 半导体\n综合得分: 0.82\n成分 24");

    const pctBars = buildSectorStrengthBarRows({
      rows: [sectorRow, negativeRow],
      view: "pctchange",
      activeSectorCode: null,
    });
    // pctchange 视角对称轴：absMax*1.08，正值自零轴向右、负值向左。
    const range = 2 * 2.35 * 1.08;
    expect(pctBars[0].barStartFraction).toBeCloseTo(0.5, 6);
    expect(pctBars[0].barSpanFraction).toBeCloseTo(2.35 / range, 6);
    expect(pctBars[1].barStartFraction).toBeCloseTo(0.5 - 1.1 / range, 6);
    expect(pctBars[1].barSpanFraction).toBeCloseTo(1.1 / range, 6);
    expect(pctBars[1].barStartFraction + pctBars[1].barSpanFraction).toBeCloseTo(0.5, 6);
    expect(pctBars[0].active).toBe(false);
    expect(pctBars[1].valueLabel).toBe("-1.10%");

    // 与 ECharts 版一致：只展示前 10 行。
    const manyRows = Array.from({ length: 12 }, (_, index) => ({
      ...sectorRow,
      rank: index + 1,
      sectorCode: `BK${String(index + 1).padStart(3, "0")}`,
    }));
    expect(
      buildSectorStrengthBarRows({ rows: manyRows, view: "score", activeSectorCode: null }),
    ).toHaveLength(10);
  });

  it("resolves the first-screen sector card state on the page's existing priority", () => {
    const base = {
      view: "score" as const,
      activeSectorCode: null,
      sourceLabel: "策略快照",
      leaderName: "半导体",
      seriesLoading: false,
      seriesErrored: false,
      seriesErrorMessage: null,
    };

    const ready = buildSectorStrengthCardModel({ ...base, rows: [sectorRow] });
    expect(ready.state).toBe("ready");
    expect(ready.bars).toHaveLength(1);
    expect(ready.sectorCount).toBe(1);
    expect(ready.leaderLabel).toBe("半导体");
    expect(ready.emptyReason).toBeNull();
    expect(ready.errorMessage).toBeNull();

    // 有行优先于回退查询状态：即便序列查询在跑，也不回退到 loading。
    expect(
      buildSectorStrengthCardModel({ ...base, rows: [sectorRow], seriesLoading: true }).state,
    ).toBe("ready");

    expect(buildSectorStrengthCardModel({ ...base, rows: [], seriesLoading: true }).state).toBe(
      "loading",
    );

    const errored = buildSectorStrengthCardModel({
      ...base,
      rows: [],
      seriesErrored: true,
      seriesErrorMessage: "读取失败",
    });
    expect(errored.state).toBe("error");
    expect(errored.errorMessage).toBe("读取失败");

    const empty = buildSectorStrengthCardModel({ ...base, rows: [] });
    expect(empty.state).toBe("empty");
    expect(empty.bars).toHaveLength(0);
    expect(empty.emptyReason).toBe("板块强度暂无可用样本，等待快照或支撑序列补全");
  });

  it("builds multi-day sector trend chart options from backend series rows", () => {
    const option = buildSectorSeriesTrendOption([
      {
        sectorCode: "BK001",
        sectorName: "半导体",
        dates: ["2026-04-28", "2026-04-29"],
        scores: [0.7, 0.82],
      },
      {
        sectorCode: "BK002",
        sectorName: "新能源",
        dates: ["2026-04-28", "2026-04-29"],
        scores: [0.5, 0.55],
      },
    ]);
    const chart = inspectChartOption(option);

    expect(chart.animation).toBe(false);
    expect(chart.series).toHaveLength(2);
    expect(chart.series[0].name).toBe("半导体");
    expect(chart.series[0].data).toEqual([0.7, 0.82]);
    expect(chart.series[1].data).toEqual([0.5, 0.55]);
  });
});
