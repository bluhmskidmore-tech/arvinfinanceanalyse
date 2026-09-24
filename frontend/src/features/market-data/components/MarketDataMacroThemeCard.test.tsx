import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./MarketDataChartShell", () => ({
  MarketDataChartShell: ({
    testId,
    emptyMessage,
  }: {
    testId?: string;
    emptyMessage?: string;
  }) => (
    <div data-testid={testId ?? "market-data-chart-shell-mock"}>{emptyMessage ?? "chart-mock"}</div>
  ),
}));

import { MACRO_THEME_CARD_DEFAULT_VISIBLE_COUNT } from "../lib/marketDataMacroThemeGroups";
import { MarketDataMacroThemeCard } from "./MarketDataMacroThemeCard";

describe("MarketDataMacroThemeCard", () => {
  it("renders one theme chart and collapses rows for the rates prototype card", async () => {
    const user = userEvent.setup();

    render(
      <MarketDataMacroThemeCard
        tier="stable"
        showThemeChart
        previewRowCount={MACRO_THEME_CARD_DEFAULT_VISIBLE_COUNT}
        group={{
          key: "rates",
          title: "利率与流动性",
          caption: "国债、回购、政策利率与资金价格。",
          series: [
            {
              series_id: "M001",
              series_name: "DR007",
              trade_date: "2026-06-11",
              value_numeric: 1.75,
              latest_change: 0.001,
              recent_points: [
                { trade_date: "2026-06-09", value_numeric: 1.7 },
                { trade_date: "2026-06-10", value_numeric: 1.72 },
                { trade_date: "2026-06-11", value_numeric: 1.75 },
              ],
            },
            {
              series_id: "M002",
              series_name: "10Y 国债",
              trade_date: "2026-06-11",
              value_numeric: 2.31,
              latest_change: -0.01,
              recent_points: [
                { trade_date: "2026-06-09", value_numeric: 2.33 },
                { trade_date: "2026-06-10", value_numeric: 2.32 },
                { trade_date: "2026-06-11", value_numeric: 2.31 },
              ],
            },
            {
              series_id: "M003",
              series_name: "R007",
              trade_date: "2026-06-11",
              value_numeric: 1.9,
              latest_change: 0.002,
              recent_points: [
                { trade_date: "2026-06-09", value_numeric: 1.88 },
                { trade_date: "2026-06-10", value_numeric: 1.89 },
                { trade_date: "2026-06-11", value_numeric: 1.9 },
              ],
            },
            {
              series_id: "M004",
              series_name: "SHIBOR 3M",
              trade_date: "2026-06-11",
              value_numeric: 1.95,
              latest_change: 0,
              recent_points: [
                { trade_date: "2026-06-09", value_numeric: 1.95 },
                { trade_date: "2026-06-10", value_numeric: 1.95 },
                { trade_date: "2026-06-11", value_numeric: 1.95 },
              ],
            },
          ] as never,
        }}
      />,
    );

    expect(screen.getByTestId("market-data-macro-theme-stable-rates-chart")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-theme-stable-rates-multi-series-chart")).toBeInTheDocument();
    expect(screen.getByText("稳定链路")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-stable-rates-M001")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-stable-rates-M003")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-series-stable-rates-M004")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("market-data-series-stable-rates-expand-all"));
    expect(screen.getByTestId("market-data-series-stable-rates-M004")).toBeInTheDocument();

    await user.click(screen.getByTestId("market-data-series-stable-rates-collapse"));
    expect(screen.queryByTestId("market-data-series-stable-rates-M004")).not.toBeInTheDocument();
  });
});
