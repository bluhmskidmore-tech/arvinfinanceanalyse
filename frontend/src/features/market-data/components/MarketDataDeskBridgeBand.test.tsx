import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MarketDataDeskBridgeBand } from "./MarketDataDeskBridgeBand";
import type { MarketOverviewMetric } from "../pages/MarketDataHeroSection";

const metric = (key: string, title: string, value: string): MarketOverviewMetric => ({
  testId: `market-data-terminal-kpi-${key}`,
  title,
  value,
  detail: "+1bp · 2026-06-11 · series",
  tone: "default",
});

describe("MarketDataDeskBridgeBand", () => {
  it("renders workbench links, bridge metrics, and basis chip", () => {
    render(
      <MemoryRouter>
        <MarketDataDeskBridgeBand
          basisChipLabel="formal · 正式可用 是 · 观察日 2026-06-11"
          bridgeMetrics={[metric("cgb10y", "10年国债", "1.75%"), metric("dr007", "DR007", "1.44%")]}
          watchDate="2026-06-11"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("market-data-desk-bridge-band")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-bridge-link-overview")).toHaveAttribute("href", "/market-overview");
    expect(screen.getByTestId("market-data-bridge-link-cross-asset")).toHaveAttribute("href", "/cross-asset");
    expect(screen.getByTestId("market-data-bridge-link-macro-toolkit")).toHaveAttribute("href", "/macro-toolkit");
    expect(screen.getByTestId("market-data-terminal-kpi-cgb10y")).toHaveTextContent("1.75%");
    expect(screen.getByTestId("market-data-desk-bridge-basis-chip")).toHaveTextContent("观察日 2026-06-11");
    expect(screen.getByTestId("market-data-desk-bridge-chart-links")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-bridge-chart-linkage")).toHaveAttribute(
      "href",
      "/market-data?date=2026-06-11#market-data-linkage-correlation",
    );
  });

  it("shows empty reason when no bridge metrics are available", () => {
    render(
      <MemoryRouter>
        <MarketDataDeskBridgeBand
          basisChipLabel="unknown · 正式可用 unknown · 观察日 2026-06-11"
          bridgeMetrics={[]}
          emptyReason="正式利率读面暂无 KPI 序列"
          watchDate="2026-06-11"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("market-data-desk-bridge-empty")).toHaveTextContent("正式利率读面暂无 KPI 序列");
  });
});
