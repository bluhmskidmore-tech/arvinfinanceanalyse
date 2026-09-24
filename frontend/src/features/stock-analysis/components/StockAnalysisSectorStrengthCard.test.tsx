import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisSectorStrengthCard } from "./StockAnalysisSectorStrengthCard";
import { buildSectorStrengthBarRows } from "../lib/stockAnalysisChartModel";
import type { StockSectorViewRow } from "../lib/stockAnalysisPageModel";

function sectorViewRow(overrides: Partial<StockSectorViewRow>): StockSectorViewRow {
  return {
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
    isTop: false,
    isBottom: false,
    metricBarNormalized: 1,
    ...overrides,
  };
}

const twelveRows = Array.from({ length: 12 }, (_, index) =>
  sectorViewRow({
    rank: index + 1,
    sectorCode: `BK${String(index + 1).padStart(3, "0")}`,
    sectorName: `板块${index + 1}`,
    scoreValue: 1 - index * 0.05,
    score: (1 - index * 0.05).toFixed(2),
  }),
);

describe("StockAnalysisSectorStrengthCard", () => {
  it("renders the top-10 bars as inline SVG rows without any chart canvas", () => {
    const bars = buildSectorStrengthBarRows({
      rows: twelveRows,
      view: "score",
      activeSectorCode: "BK002",
    });
    const { container } = render(
      <StockAnalysisSectorStrengthCard
        state="ready"
        bars={bars}
        sectorCount={12}
        sourceLabel="策略快照"
        leaderLabel="板块1"
      />,
    );

    const chart = screen.getByTestId("stock-analysis-sector-strength-first-screen");
    const rows = within(chart).getAllByRole("listitem");
    expect(rows).toHaveLength(10);
    expect(within(chart).getByText("板块1")).toBeInTheDocument();
    expect(within(chart).getByText("板块10")).toBeInTheDocument();
    expect(within(chart).getByText("0.55")).toBeInTheDocument();

    // ECharts 退役：首屏卡只允许内联 SVG，不得出现 canvas 实例。
    expect(container.querySelector("canvas")).toBeNull();
    expect(chart.querySelectorAll("svg")).toHaveLength(10);

    // 悬停口径沿用 ECharts tooltip 内容，走原生 title。
    expect(rows[0]).toHaveAttribute("title", "1. 板块1\n综合得分: 1.00\n成分 24");

    // active 板块高亮语义保留。
    expect(
      screen.getByTestId("stock-analysis-sector-strength-bar-BK002"),
    ).toHaveAttribute("data-active", "true");
    expect(
      screen.getByTestId("stock-analysis-sector-strength-bar-BK001"),
    ).not.toHaveAttribute("data-active");

    // 底部脚注口径不变。
    expect(screen.getByText("首位 板块1")).toBeInTheDocument();
    expect(screen.getByText("共 12 个板块，展示前 10")).toBeInTheDocument();
    expect(screen.getByText("策略快照")).toBeInTheDocument();
  });

  it("keeps the loading, empty, and error states on their existing test ids", () => {
    const { rerender } = render(
      <StockAnalysisSectorStrengthCard
        state="loading"
        bars={[]}
        sectorCount={0}
        sourceLabel="待补"
        leaderLabel={null}
      />,
    );
    expect(screen.getByTestId("stock-analysis-sector-strength-loading")).toBeInTheDocument();

    rerender(
      <StockAnalysisSectorStrengthCard
        state="empty"
        bars={[]}
        sectorCount={0}
        sourceLabel="待补"
        leaderLabel={null}
        emptyReason="板块强度暂无可用样本，等待快照或支撑序列补全"
      />,
    );
    expect(screen.getByTestId("stock-analysis-sector-strength-empty")).toHaveTextContent(
      "板块强度暂无可用样本",
    );

    rerender(
      <StockAnalysisSectorStrengthCard
        state="error"
        bars={[]}
        sectorCount={0}
        sourceLabel="待补"
        leaderLabel={null}
        errorMessage="读取失败"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("读取失败");
  });
});
