import { describe, expect, it } from "vitest";

import type { StockSectorViewRow } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import { nocturneTokens } from "../theme/designSystem";
import {
  buildSectorSeriesTrendOption,
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
  it("sources the chart palette from canonical Nocturne tokens", () => {
    expect(stockChartPalette).toEqual({
      ink: nocturneTokens.color.ink,
      muted: nocturneTokens.color.inkMuted,
      grid: nocturneTokens.color.lineSoft,
      track: nocturneTokens.color.line,
      primary: nocturneTokens.color.blue,
      primaryLight: nocturneTokens.color.inkMuted,
      accent: nocturneTokens.color.inkSoft,
      success: nocturneTokens.color.green,
      successLight: nocturneTokens.color.greenSoft,
      danger: nocturneTokens.color.red,
      gold: nocturneTokens.color.amber,
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

  it("builds the sector strength chart option without recalculating business metrics", () => {
    const sectorOption = buildSectorStrengthOption({
      rows: [sectorRow],
      view: "pctchange",
      activeSectorCode: "BK001",
    });
    const sector = inspectChartOption(sectorOption);

    expect(sector.xAxis?.min).toBeLessThan(0);
    expect(sector.series[0].data[0]).toMatchObject({
      value: 2.35,
      itemStyle: { color: stockChartPalette.primary },
    });
    expect(sector.tooltip?.formatter?.([{ dataIndex: 0 }])).toBe(
      "1. 半导体<br/>平均涨跌幅: +2.35%<br/>成分 24",
    );
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
