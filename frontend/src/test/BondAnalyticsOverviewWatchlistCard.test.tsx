import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsOverviewWatchlistCard } from "../features/bond-analytics/components/BondAnalyticsOverviewWatchlistCard";

describe("BondAnalyticsOverviewWatchlistCard", () => {
  it("lists flagged anomalies when the overview payload reports them", () => {
    const topAnomalies = ["First anomaly body", "Second anomaly body"];

    render(<BondAnalyticsOverviewWatchlistCard topAnomalies={topAnomalies} />);

    expect(screen.getByText("2 flagged signal(s)")).toBeInTheDocument();
    expect(screen.getByText("First anomaly body")).toBeInTheDocument();
    expect(screen.getByText("Second anomaly body")).toBeInTheDocument();
  });

  it("renders calm helper copy when no anomalies are present", () => {
    render(<BondAnalyticsOverviewWatchlistCard topAnomalies={[]} />);

    expect(screen.getByText("No anomaly is currently raised in the overview payload.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The overview payload is currently calm. Use the right-rail decision queue to pick the next drill surface without forcing synthetic top-line metrics.",
      ),
    ).toBeInTheDocument();
  });
});
