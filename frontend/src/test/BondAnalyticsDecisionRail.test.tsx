import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BondAnalyticsDecisionRail } from "../features/bond-analytics/components/BondAnalyticsDecisionRail";
import type { BondAnalyticsReadinessItem } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createReadinessItem(overrides: Partial<BondAnalyticsReadinessItem> = {}): BondAnalyticsReadinessItem {
  return {
    key: "return-decomposition",
    label: "收益拆解",
    description: "说明",
    detailHint: "提示",
    statusLabel: "placeholder-blocked",
    statusReason: "阻塞原因",
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
      statusReason: "标签上下文就绪原因",
    });

    const watchlistItems: BondAnalyticsReadinessItem[] = [
      createReadinessItem({
        key: "return-decomposition",
        label: "观察一",
        statusReason: "原因一",
      }),
      createReadinessItem({
        key: "benchmark-excess",
        label: "观察二",
        statusReason: "原因二",
      }),
      createReadinessItem({
        key: "credit-spread",
        label: "观察三隐藏",
        statusReason: "不应渲染",
      }),
    ];

    render(
      <BondAnalyticsDecisionRail
        activeModuleContext={{
          key: "action-attribution",
          label: "当前模块",
          description: "当前模块说明。",
          statusLabel: "eligible",
          statusReason: "上下文框中的当前状态原因。",
        }}
        activeReadinessItem={activeReadinessItem}
        watchlistItems={watchlistItems}
        onOpenModuleDetail={onOpenModuleDetail}
      />,
    );

    expect(screen.getByText("当前模块")).toBeInTheDocument();
    expect(screen.getByText("可提升")).toBeInTheDocument();
    expect(screen.getByText("当前模块说明。")).toBeInTheDocument();
    expect(screen.getByText("上下文框中的当前状态原因。")).toBeInTheDocument();

    expect(screen.getByText("观察一")).toBeInTheDocument();
    expect(screen.getByText("原因一")).toBeInTheDocument();
    expect(screen.getByText("观察二")).toBeInTheDocument();
    expect(screen.getByText("原因二")).toBeInTheDocument();
    expect(screen.queryByText("观察三隐藏")).not.toBeInTheDocument();
    expect(screen.queryByText("不应渲染")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开当前下钻" }));
    expect(onOpenModuleDetail).toHaveBeenCalledTimes(1);
    expect(onOpenModuleDetail).toHaveBeenCalledWith("action-attribution");
  });
});
