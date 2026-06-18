import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MacroVendorSeries } from "../../../api/contracts";
import { MarketDataMacroSeriesDeck } from "./MarketDataMacroSeriesDeck";

describe("MarketDataMacroSeriesDeck", () => {
  const catalog: MacroVendorSeries[] = [
    {
      series_id: "M001",
      series_name: "稳定序列",
      vendor_name: "choice",
      vendor_version: "v1",
      frequency: "daily",
      unit: "%",
      theme: "rates",
      tags: ["rates", "liquidity"],
    },
    {
      series_id: "M002",
      series_name: "降级序列",
      vendor_name: "choice",
      vendor_version: "v1",
      frequency: "daily",
      unit: "点",
      theme: "equity",
      tags: ["equity"],
    },
  ];

  it("renders stable charts, expanded fallback cards, and more visible rows by default", () => {
    render(
      <MarketDataMacroSeriesDeck
        stableSeries={[
          {
            series_id: "M001",
            series_name: "DR007",
            trade_date: "2026-06-11",
            value_numeric: 1.75,
            latest_change: 0.001,
            recent_points: [
              { trade_date: "2026-06-09", value_numeric: 1.7 },
              { trade_date: "2026-06-11", value_numeric: 1.75 },
            ],
          } as never,
          {
            series_id: "M003",
            series_name: "R007",
            trade_date: "2026-06-11",
            value_numeric: 1.9,
            latest_change: 0.002,
            recent_points: [
              { trade_date: "2026-06-09", value_numeric: 1.88 },
              { trade_date: "2026-06-11", value_numeric: 1.9 },
            ],
          } as never,
        ]}
        fallbackSeries={[
          {
            series_id: "M002",
            series_name: "降级序列",
            trade_date: "2026-06-11",
            value_numeric: 2.1,
            latest_change: -0.01,
            recent_points: [],
          } as never,
        ]}
        catalog={catalog}
      />,
    );

    expect(screen.getByTestId("market-data-macro-stable-theme-band")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-fallback-theme-band")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-theme-stable-rates-chart")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-theme-fallback-equity")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-stable-rates-M001")).toHaveTextContent("DR007");
    expect(screen.getByTestId("market-data-macro-stable-tier-rail")).toHaveTextContent("稳定链路");
    expect(screen.getByText("稳定链路", { selector: ".market-data-pill-tag" })).toBeInTheDocument();
  });
});
