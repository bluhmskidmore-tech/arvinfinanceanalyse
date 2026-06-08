import { describe, expect, it } from "vitest";

import type { StockSectorViewRow } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import {
  buildCompactBarOption,
  buildEventSummaryOption,
  buildOutputChartRows,
  buildReviewQueueChartRows,
  buildReviewQueueRankingOption,
  buildRiskSupplyChartRows,
  buildSectorChartRows,
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
});
