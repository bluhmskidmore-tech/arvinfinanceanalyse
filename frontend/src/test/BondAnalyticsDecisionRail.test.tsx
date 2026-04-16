import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BondAnalyticsDecisionRail } from "../features/bond-analytics/components/BondAnalyticsDecisionRail";
import type { BondAnalyticsReadinessItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createReadinessItem(overrides: Partial<BondAnalyticsReadinessItem> = {}): BondAnalyticsReadinessItem {
  return {
    key: "return-decomposition",
    label: "收益拆解",
    description: "desc",
    detailHint: "hint",
    statusLabel: "placeholder-blocked",
    statusReason: "blocked reason",
    promotionDestination: "readiness-only",
    warnings: [],
    ...overrides,
  };
}

describe("BondAnalyticsDecisionRail", () => {
  it("shows active context, status, and only the first two watchlist rows", async () => {
    const user = userEvent.setup();
    const onOpenModuleDetail = vi.fn();

    const activeReadinessItem = createReadinessItem({
      key: "action-attribution",
      statusLabel: "eligible",
      statusReason: "readiness reason for tag context",
    });

    const watchlistItems: BondAnalyticsReadinessItem[] = [
      createReadinessItem({
        key: "return-decomposition",
        label: "Watch One",
        statusReason: "reason one",
      }),
      createReadinessItem({
        key: "benchmark-excess",
        label: "Watch Two",
        statusReason: "reason two",
      }),
      createReadinessItem({
        key: "credit-spread",
        label: "Watch Three Hidden",
        statusReason: "should not render",
      }),
    ];

    render(
      <BondAnalyticsDecisionRail
        activeModuleContext={{
          key: "action-attribution",
          label: "Active module label",
          description: "Active module description body.",
          statusLabel: "eligible",
          statusReason: "Active status reason in context box.",
        }}
        activeReadinessItem={activeReadinessItem}
        watchlistItems={watchlistItems}
        onOpenModuleDetail={onOpenModuleDetail}
      />,
    );

    expect(screen.getByText("Active module label")).toBeInTheDocument();
    expect(screen.getByText("eligible")).toBeInTheDocument();
    expect(screen.getByText("Active module description body.")).toBeInTheDocument();
    expect(screen.getByText("Active status reason in context box.")).toBeInTheDocument();

    expect(screen.getByText("Watch One")).toBeInTheDocument();
    expect(screen.getByText("reason one")).toBeInTheDocument();
    expect(screen.getByText("Watch Two")).toBeInTheDocument();
    expect(screen.getByText("reason two")).toBeInTheDocument();
    expect(screen.queryByText("Watch Three Hidden")).not.toBeInTheDocument();
    expect(screen.queryByText("should not render")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open current drill" }));
    expect(onOpenModuleDetail).toHaveBeenCalledTimes(1);
    expect(onOpenModuleDetail).toHaveBeenCalledWith("action-attribution");
  });
});
