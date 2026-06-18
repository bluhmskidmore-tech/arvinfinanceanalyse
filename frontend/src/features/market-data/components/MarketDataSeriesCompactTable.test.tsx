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
    expect(row).toHaveTextContent("24055");
    expect(row).toHaveTextContent("CNY/t");
    expect(row).toHaveTextContent("06-10 23905");
    expect(row).not.toHaveTextContent("2026-06-09 23800 · 2026-06-10 23905");
  });

  it("expands inline chart when 走势 is clicked", () => {
    render(
      <MarketDataSeriesCompactTable
        testIdPrefix="market-data-series-stable"
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
});
