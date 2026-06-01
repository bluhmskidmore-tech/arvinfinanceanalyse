import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BondAnalyticsReadinessMatrix } from "../features/bond-analytics/components/BondAnalyticsReadinessMatrix";
import type { BondAnalyticsReadinessItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createReadinessItem(overrides: Partial<BondAnalyticsReadinessItem> = {}): BondAnalyticsReadinessItem {
  return {
    key: "return-decomposition",
    label: "收益拆解",
    description: "模块说明",
    detailHint: "明细提示",
    statusLabel: "placeholder-blocked",
    statusReason: "Status reason narrative",
    promotionDestination: "readiness-only",
    warnings: [],
    ...overrides,
  };
}

describe("BondAnalyticsReadinessMatrix", () => {
  it("renders readiness rows with promotion attribute, details, warnings, and drill callback", async () => {
    const user = userEvent.setup();
    const onOpenModuleDetail = vi.fn();

    const items: BondAnalyticsReadinessItem[] = [
      createReadinessItem({
        key: "action-attribution",
        label: "动作归因",
        statusLabel: "warning",
        statusReason: "需要复核",
        detailHint: "打开交易下钻",
        promotionDestination: "headline",
        warnings: ["第一条预警"],
      }),
      createReadinessItem({
        key: "credit-spread",
        label: "信用利差",
        statusLabel: "eligible",
        statusReason: "就绪",
        warnings: [],
      }),
    ];

    render(<BondAnalyticsReadinessMatrix readinessItems={items} onOpenModuleDetail={onOpenModuleDetail} />);

    expect(screen.getByTestId("bond-analysis-readiness-matrix")).toBeInTheDocument();
    expect(screen.getByText("2 个总览关联模块")).toBeInTheDocument();

    const row1 = screen.getByTestId("bond-analysis-readiness-action-attribution");
    expect(row1).toHaveAttribute("data-promotion-destination", "headline");
    expect(within(row1).getByText("动作归因")).toBeInTheDocument();
    expect(within(row1).getByText("模块说明")).toBeInTheDocument();
    expect(within(row1).getByText("需要复核")).toBeInTheDocument();
    expect(within(row1).getByText("打开交易下钻")).toBeInTheDocument();
    expect(within(row1).getByText("第一条预警")).toBeInTheDocument();

    const row2 = screen.getByTestId("bond-analysis-readiness-credit-spread");
    expect(row2).toHaveAttribute("data-promotion-destination", "readiness-only");

    await user.click(within(row2).getByRole("button", { name: "打开明细" }));
    expect(onOpenModuleDetail).toHaveBeenCalledWith("credit-spread");
  });
});
