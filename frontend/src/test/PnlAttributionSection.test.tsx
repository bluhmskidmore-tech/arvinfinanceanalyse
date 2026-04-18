import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../lib/echarts", () => ({
  default: function MockECharts() {
    return <div data-testid="pnl-attribution-chart-stub" />;
  },
}));

import type { Numeric } from "../api/contracts";
import type { DashboardAdapterOutput } from "../features/executive-dashboard/adapters/executiveDashboardAdapter";
import PnlAttributionSection from "../features/executive-dashboard/components/PnlAttributionSection";

function numeric(raw: number | null, display: string): Numeric {
  return {
    raw,
    unit: "yuan",
    display,
    precision: 2,
    sign_aware: true,
  };
}

function attributionWithSegments(): DashboardAdapterOutput["attribution"] {
  return {
    vm: {
      title: "经营贡献拆解",
      total: numeric(12.3e6, "合计 +12.3M"),
      segments: [
        {
          id: "s1",
          label: "利率",
          amount: numeric(8e6, "+8.0M"),
          tone: "positive",
        },
        {
          id: "s2",
          label: "信用",
          amount: numeric(4.3e6, "+4.3M"),
          tone: "neutral",
        },
      ],
    },
    state: { kind: "ok" },
    meta: null,
  };
}

describe("PnlAttributionSection", () => {
  it("renders total, segment labels and display amounts, and chart placeholder when segments exist", () => {
    const attribution = attributionWithSegments();

    render(
      <PnlAttributionSection
        attribution={attribution}
        onRetry={() => undefined}
      />,
    );

    const totalNodes = screen.getAllByText("合计 +12.3M");
    expect(totalNodes.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("经营贡献拆解")).toBeInTheDocument();

    expect(screen.getByText("利率")).toBeInTheDocument();
    expect(screen.getByText("+8.0M")).toBeInTheDocument();
    expect(screen.getByText("信用")).toBeInTheDocument();
    expect(screen.getByText("+4.3M")).toBeInTheDocument();

    expect(screen.getByTestId("pnl-attribution-chart-stub")).toBeInTheDocument();
  });

  it("renders empty state when segments is empty", () => {
    const attribution: DashboardAdapterOutput["attribution"] = {
      vm: {
        title: "归因",
        total: numeric(0, "合计 0"),
        segments: [],
      },
      state: { kind: "empty" },
      meta: null,
    };

    render(
      <PnlAttributionSection
        attribution={attribution}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
    expect(
      screen.queryByTestId("pnl-attribution-chart-stub"),
    ).not.toBeInTheDocument();
  });
});
