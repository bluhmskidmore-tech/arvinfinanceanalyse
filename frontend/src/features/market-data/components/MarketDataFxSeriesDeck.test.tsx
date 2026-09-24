import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./MarketDataChartShell", () => ({
  MarketDataChartShell: ({ testId }: { testId?: string }) => (
    <div data-testid={testId ?? "market-data-chart-shell-mock"} />
  ),
}));

import { MarketDataFxSeriesDeck } from "./MarketDataFxSeriesDeck";

describe("MarketDataFxSeriesDeck", () => {
  it("renders fx groups, event calendar rows, and index event context", () => {
    render(
      <MarketDataFxSeriesDeck
        groupTitle={(title) => title}
        groups={[
          {
            group_key: "middle_rate",
            title: "Middle rate",
            description: "Major FX middle-rate observations.",
            series: [
              {
                series_id: "FX001",
                series_name: "USD/CNY",
                trade_date: "2026-06-11",
                value_numeric: 7.2,
                latest_change: 0.01,
                recent_points: [
                  { trade_date: "2026-06-09", value_numeric: 7.19 },
                  { trade_date: "2026-06-11", value_numeric: 7.2 },
                ],
              } as never,
              {
                series_id: "FX002",
                series_name: "EUR/CNY",
                trade_date: "2026-06-11",
                value_numeric: 7.8,
                latest_change: -0.01,
                recent_points: [
                  { trade_date: "2026-06-09", value_numeric: 7.81 },
                  { trade_date: "2026-06-11", value_numeric: 7.8 },
                ],
              } as never,
              {
                series_id: "FX003",
                series_name: "JPY/CNY",
                trade_date: "2026-06-11",
                value_numeric: 0.05,
                latest_change: 0,
                recent_points: [
                  { trade_date: "2026-06-09", value_numeric: 0.05 },
                  { trade_date: "2026-06-11", value_numeric: 0.05 },
                ],
              } as never,
              {
                series_id: "FX004",
                series_name: "GBP/CNY",
                trade_date: "2026-06-11",
                value_numeric: 9.1,
                latest_change: 0.02,
                recent_points: [
                  { trade_date: "2026-06-09", value_numeric: 9.08 },
                  { trade_date: "2026-06-11", value_numeric: 9.1 },
                ],
              } as never,
            ],
          },
          {
            group_key: "fx_index",
            title: "Index",
            description:
              "RMB index / estimate index series stay analytical-only and never flow into formal FX.",
            series: [
              {
                series_id: "FX_INDEX",
                series_name: "RMB index",
                trade_date: "2026-06-11",
                value_numeric: 115.48,
                latest_change: null,
                recent_points: [],
              } as never,
            ],
          },
          {
            group_key: "fx_event_calendar",
            title: "Event calendar",
            description:
              "Tushare economic-calendar events for major FX currencies are analytical-only event context.",
            series: [],
            events: [
              {
                group_key: "fx_event_calendar",
                event_id: "eco-cny-trade",
                event_date: "20260612",
                event_time: "10:30",
                currency: "CNY",
                country: "China",
                event: "China trade balance",
                value: "105.43",
                pre_value: "84.8",
                fore_value: "92.1",
                source_version: "sv_tushare_eco",
                vendor_version: "vv_tushare_supplement_v1",
                quality_flag: "ok",
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByTestId("market-data-fx-theme-band")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-group-card-middle_rate")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-group-card-middle_rate-chart")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-series-middle_rate-FX001")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-series-middle_rate-FX004")).toBeInTheDocument();

    const indexInsight = screen.getByTestId("market-data-fx-group-card-fx_index-insight");
    expect(within(indexInsight).getByText("事件背景")).toBeInTheDocument();
    expect(within(indexInsight).getByText("CNY 1")).toBeInTheDocument();
    expect(within(indexInsight).getByText("China trade balance")).toBeInTheDocument();

    expect(screen.getByTestId("market-data-fx-group-card-fx_event_calendar")).toBeInTheDocument();
    const eventList = screen.getByTestId("market-data-fx-group-card-fx_event_calendar-events");
    expect(eventList).toBeInTheDocument();
    expect(within(eventList).getByText("China trade balance")).toBeInTheDocument();
    expect(within(eventList).getByText(/105\.43/)).toBeInTheDocument();
  });
});
