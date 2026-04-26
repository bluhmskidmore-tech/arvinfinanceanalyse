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
    expect(screen.getByText("暂缓与后续")).toBeInTheDocument();
    expect(screen.getByText("保留下阶段驾驶舱层级")).toBeInTheDocument();
    expect(
      screen.getByText(
        "这些页面保留在右上侧栏，用户可以看到规划范围，同时不会把路线图可见性误读成当前受治理事实。",
      ),
    ).toBeInTheDocument();

    expect(screen.getByText("Future A")).toBeInTheDocument();
    expect(screen.getByText("Description A")).toBeInTheDocument();
    expect(screen.getByText("Future B")).toBeInTheDocument();
    expect(screen.getByText("Description B")).toBeInTheDocument();
  });
});
