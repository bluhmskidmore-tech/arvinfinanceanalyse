import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsFuturePanel } from "../features/bond-analytics/components/BondAnalyticsFuturePanel";
import type { BondAnalyticsFutureVisibilityItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

describe("BondAnalyticsFuturePanel", () => {
  it("renders heading, explanatory copy, and each deferred item", () => {
    const items: BondAnalyticsFutureVisibilityItem[] = [
      {
        key: "a",
        label: "Future A",
        description: "Description A",
        statusLabel: "future-visible",
        statusReason: "Visible for planning",
      },
      {
        key: "b",
        label: "Future B",
        description: "Description B",
        statusLabel: "future-visible",
        statusReason: "Visible for planning",
      },
    ];

    render(<BondAnalyticsFuturePanel futureVisibilityItems={items} />);

    expect(screen.getByTestId("bond-analysis-future-panel")).toBeInTheDocument();
    expect(screen.getByText("Deferred / future")).toBeInTheDocument();
    expect(screen.getByText("Keep the next cockpit layers visible")).toBeInTheDocument();
    expect(
      screen.getByText(
        "These surfaces stay pinned in the top-right rail so users can see what is planned without confusing roadmap visibility with current governed truth.",
      ),
    ).toBeInTheDocument();

    expect(screen.getByText("Future A")).toBeInTheDocument();
    expect(screen.getByText("Description A")).toBeInTheDocument();
    expect(screen.getByText("Future B")).toBeInTheDocument();
    expect(screen.getByText("Description B")).toBeInTheDocument();
  });
});
