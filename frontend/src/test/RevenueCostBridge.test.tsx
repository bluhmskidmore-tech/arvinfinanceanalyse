import { createElement } from "react";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { EM_DASH } from "../utils/format";
import { RevenueCostBridge } from "../features/workbench/business-analysis/RevenueCostBridge";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: () =>
    createElement("div", {
      "data-testid": "revenue-cost-bridge-chart-stub",
    }),
}));

describe("RevenueCostBridge", () => {
  it("marks the hard-coded waterfall as sample data instead of a formal reading", () => {
    render(<RevenueCostBridge />);

    expect(screen.getByTestId("revenue-cost-bridge-sample-badge")).toHaveTextContent(
      "示意数据·未接入正式口径",
    );

    const note = screen.getByTestId("revenue-cost-bridge-sample-note");
    expect(note).toHaveTextContent(`正式口径读数：${EM_DASH}（未接入）`);
    expect(note).toHaveTextContent("数值不代表正式读数");

    expect(screen.queryByText(/72\.87/)).not.toBeInTheDocument();
    expect(screen.queryByText(/29\.5bp/)).not.toBeInTheDocument();
  });
});
