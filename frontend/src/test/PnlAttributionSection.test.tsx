import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../lib/echarts", () => ({
  default: function MockECharts() {
    return <div data-testid="pnl-attribution-chart-stub" />;
  },
}));

import type { PnlAttributionPayload } from "../api/contracts";
import PnlAttributionSection from "../features/executive-dashboard/components/PnlAttributionSection";

function pnlFixture(): PnlAttributionPayload {
  return {
    title: "归因",
    total: "合计 +12.3M",
    segments: [
      {
        id: "s1",
        label: "利率",
        amount: 8e6,
        display_amount: "+8.0M",
        tone: "positive",
      },
      {
        id: "s2",
        label: "信用",
        amount: 4.3e6,
        display_amount: "+4.3M",
        tone: "neutral",
      },
    ],
  };
}

describe("PnlAttributionSection", () => {
  it("renders total, segment labels and display amounts, and chart placeholder when segments exist", () => {
    const data = pnlFixture();

    render(
      <PnlAttributionSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    const totalNodes = screen.getAllByText("合计 +12.3M");
    expect(totalNodes.length).toBeGreaterThanOrEqual(1);

    expect(screen.getByText("利率")).toBeInTheDocument();
    expect(screen.getByText("+8.0M")).toBeInTheDocument();
    expect(screen.getByText("信用")).toBeInTheDocument();
    expect(screen.getByText("+4.3M")).toBeInTheDocument();

    expect(screen.getByTestId("pnl-attribution-chart-stub")).toBeInTheDocument();
  });

  it("renders empty state when segments is empty", () => {
    const data: PnlAttributionPayload = {
      title: "归因",
      total: "合计 0",
      segments: [],
    };

    render(
      <PnlAttributionSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(
      screen.queryByTestId("pnl-attribution-chart-stub"),
    ).not.toBeInTheDocument();
  });
});
