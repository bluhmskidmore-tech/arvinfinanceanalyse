import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BondAnalyticsHeadlineZone } from "../features/bond-analytics/components/BondAnalyticsHeadlineZone";
import type { BondAnalyticsHeadlineTile, BondAnalyticsReadinessItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createReadinessItem(overrides: Partial<BondAnalyticsReadinessItem> = {}): BondAnalyticsReadinessItem {
  return {
    key: "return-decomposition",
    label: "收益拆解",
    description: "desc",
    detailHint: "hint",
    statusLabel: "placeholder-blocked",
    statusReason: "reason",
    promotionDestination: "readiness-only",
    warnings: [],
    ...overrides,
  };
}

describe("BondAnalyticsHeadlineZone", () => {
  it("renders headline tile, CTA, promoted and warning lists, and routes drill clicks through the headline key", async () => {
    const user = userEvent.setup();
    const onOpenModuleDetail = vi.fn();

    const headlineTile: BondAnalyticsHeadlineTile = {
      key: "action-attribution",
      label: "动作归因",
      value: "12",
      caption: "说明",
      detail: "明细说明",
    };

    const promotedItems = [createReadinessItem({ key: "action-attribution", label: "已提升 A", promotionDestination: "headline" })];
    const warningItems = [createReadinessItem({ key: "credit-spread", label: "预警 B", statusLabel: "warning" })];

    render(
      <BondAnalyticsHeadlineZone
        headlineTile={headlineTile}
        headlineCtaLabel="打开主位"
        promotedItems={promotedItems}
        warningItems={warningItems}
        onOpenModuleDetail={onOpenModuleDetail}
      />,
    );

    expect(screen.getByTestId("bond-analysis-headline-zone")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analysis-open-headline-action-attribution")).toHaveTextContent("打开主位");
    expect(screen.getByTestId("bond-analysis-headline-action-attribution")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();

    expect(screen.getByText("当前主位")).toBeInTheDocument();
    expect(screen.getByText("已提升 A")).toBeInTheDocument();
    expect(screen.getByText("观察风险")).toBeInTheDocument();
    expect(screen.getByText("预警 B")).toBeInTheDocument();

    await user.click(screen.getByTestId("bond-analysis-open-headline-action-attribution"));
    await user.click(screen.getByTestId("bond-analysis-headline-action-attribution"));
    expect(onOpenModuleDetail).toHaveBeenCalledTimes(2);
    expect(onOpenModuleDetail).toHaveBeenNthCalledWith(1, "action-attribution");
    expect(onOpenModuleDetail).toHaveBeenNthCalledWith(2, "action-attribution");
  });

  it("renders the gate empty state when no headline tile is eligible", () => {
    const onOpenModuleDetail = vi.fn();

    render(
      <BondAnalyticsHeadlineZone
        headlineTile={null}
        headlineCtaLabel={null}
        promotedItems={[]}
        warningItems={[]}
        onOpenModuleDetail={onOpenModuleDetail}
      />,
    );

    expect(screen.getByText("暂无模块满足主位分析条件。")).toBeInTheDocument();
    expect(screen.queryByTestId("bond-analysis-open-headline-action-attribution")).not.toBeInTheDocument();
  });
});
