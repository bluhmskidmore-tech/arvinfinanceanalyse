import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="market-data-echarts-stub" />,
}));

import { MarketDataSeriesCompactTable } from "./MarketDataSeriesCompactTable";

describe("MarketDataSeriesCompactTable", () => {
  it("renders compact rows with stacked value and prior hint", () => {
    render(
      <MarketDataSeriesCompactTable
        testIdPrefix="market-data-series-stable"
        observationDate="2026-06-11"
        series={[
          {
            series_id: "M001",
            series_name: "铝主力期货收盘价",
            trade_date: "2026-06-11",
            value_numeric: 24055,
            unit: "CNY/t",
            latest_change: 150,
            recent_points: [
              { trade_date: "2026-06-09", value_numeric: 23800, vendor_version: "v1" },
              { trade_date: "2026-06-10", value_numeric: 23905, vendor_version: "v1" },
              { trade_date: "2026-06-11", value_numeric: 24055, vendor_version: "v1" },
            ],
          } as never,
        ]}
      />,
    );

    const row = screen.getByTestId("market-data-series-stable-M001");
    expect(screen.getByTestId("market-data-series-stable-compact-table")).toBeInTheDocument();
    expect(row).toHaveTextContent("铝主力期货收盘价");
    expect(row).toHaveTextContent("24,055");
    expect(row).toHaveTextContent("CNY/t");
    expect(row).toHaveTextContent("06-10 23905");
    expect(row).not.toHaveTextContent("2026-06-09 23800 · 2026-06-10 23905");
    // 原始值收进 title，展示值走千分位。
    expect(row.querySelector(".market-data-series-compact-value-stack")).toHaveAttribute(
      "title",
      "24055 CNY/t",
    );

    // 变动列走页面语义 tone 类（up=红/down=绿由 MarketDataPage.css 决定），不再内联色值。
    const delta = row.querySelector(".market-data-terminal-ticker-delta");
    expect(delta).not.toBeNull();
    expect(delta).toHaveTextContent("+150 CNY/t");
    expect(delta).toHaveAttribute("data-tone", "up");
    expect(delta?.getAttribute("style")).toBeNull();
  });

  it("scales 亿元 aggregates to 万亿元 and never signs zero-rounded fx deltas", () => {
    render(
      <MarketDataSeriesCompactTable
        testIdPrefix="market-data-series-stable"
        observationDate="2026-06-12"
        series={[
          {
            series_id: "M2",
            series_name: "货币供应量:M2:期末值",
            display_name: "货币供应量M2",
            trade_date: "2026-05-31",
            value_numeric: 3567108.43,
            unit: "亿元",
            latest_change: 48000,
            recent_points: [],
          } as never,
          {
            series_id: "FX_HKD",
            series_name: "人民币对港元中间价",
            trade_date: "2026-06-11",
            value_numeric: 0.93,
            unit: "HKD",
            latest_change: -0.0001,
            recent_points: [],
          } as never,
        ]}
      />,
    );

    const m2Row = screen.getByTestId("market-data-series-stable-M2");
    // 指标列展示清洗短名，title 保留原始名+编号。
    expect(m2Row).toHaveTextContent("货币供应量M2");
    expect(m2Row.querySelector('[title="货币供应量:M2:期末值 (M2)"]')).not.toBeNull();
    expect(m2Row).toHaveTextContent("356.71");
    expect(m2Row).toHaveTextContent("万亿元");
    expect(m2Row).toHaveTextContent("+4.80 万亿元");
    expect(m2Row.querySelector(".market-data-series-compact-value-stack")).toHaveAttribute(
      "title",
      "3567108.43 亿元",
    );

    // 格式化后为零的变动不得带符号，tone 归 flat。
    const fxRow = screen.getByTestId("market-data-series-stable-FX_HKD");
    const fxDelta = fxRow.querySelector(".market-data-terminal-ticker-delta");
    expect(fxDelta).toHaveTextContent("0 HKD");
    expect(fxDelta).not.toHaveTextContent("-0");
    expect(fxDelta).toHaveAttribute("data-tone", "flat");
  });

  it("expands inline chart when 走势 is clicked", () => {
    render(
      <MarketDataSeriesCompactTable
        testIdPrefix="market-data-series-stable"
        observationDate="2026-06-11"
        series={[
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            trade_date: "2026-06-11",
            value_numeric: 1.75,
            latest_change: 0.001,
            recent_points: [
              { trade_date: "2026-06-09", value_numeric: 1.73, vendor_version: "v1" },
              { trade_date: "2026-06-10", value_numeric: 1.74, vendor_version: "v1" },
              { trade_date: "2026-06-11", value_numeric: 1.75, vendor_version: "v1" },
            ],
          } as never,
        ]}
      />,
    );

    fireEvent.click(screen.getByTestId("market-data-series-stable-chart-toggle-M001"));
    expect(screen.getByTestId("market-data-series-stable-inline-chart-M001")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-stable-time-chart-M001")).toBeInTheDocument();
  });

  it("tiers rows by trade-date age: fades 90-365d rows and folds >365d rows into a historical section", () => {
    render(
      <MarketDataSeriesCompactTable
        testIdPrefix="market-data-series-fallback"
        observationDate="2026-06-11"
        series={[
          {
            series_id: "FRESH",
            series_name: "当日序列",
            trade_date: "2026-06-11",
            value_numeric: 1.75,
            latest_change: 0.001,
            recent_points: [],
          } as never,
          {
            series_id: "STALE",
            series_name: "季度序列",
            trade_date: "2026-01-05",
            value_numeric: 3.2,
            latest_change: null,
            recent_points: [],
          } as never,
          {
            series_id: "LEGACY",
            series_name: "存贷款基准利率",
            trade_date: "2015-10-24",
            value_numeric: 1.5,
            latest_change: null,
            recent_points: [],
          } as never,
        ]}
      />,
    );

    // 90-365 天：留在主表并标记 stale（视觉淡化由 CSS 承担）。
    expect(screen.getByTestId("market-data-series-fallback-FRESH")).toHaveAttribute(
      "data-age",
      "current",
    );
    expect(screen.getByTestId("market-data-series-fallback-STALE")).toHaveAttribute(
      "data-age",
      "stale",
    );

    // >365 天：默认折叠进"历史存量"小节，DOM 常驻（折叠可及，不是隐藏删除）。
    const historical = screen.getByTestId("market-data-series-fallback-historical-section");
    expect(historical).not.toHaveAttribute("open");
    expect(screen.getByTestId("market-data-series-fallback-historical-summary")).toHaveTextContent(
      "历史存量（1 条）",
    );
    const legacyRow = screen.getByTestId("market-data-series-fallback-LEGACY");
    expect(historical).toContainElement(legacyRow);
    expect(legacyRow).toHaveAttribute("data-age", "historical");
    expect(legacyRow).toHaveTextContent("数据截至 2015-10-24");

    // 主表条数只统计非历史行。
    const mainTable = screen.getByTestId("market-data-series-fallback-compact-table");
    expect(mainTable).not.toContainElement(legacyRow);

    fireEvent.click(screen.getByTestId("market-data-series-fallback-historical-summary"));
    expect(historical).toHaveAttribute("open");
  });
});
