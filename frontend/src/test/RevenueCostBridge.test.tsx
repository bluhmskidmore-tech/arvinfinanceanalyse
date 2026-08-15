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

    // 「静态示例」红胶囊声明收敛到经营分析页折叠区 summary
    // （OperationsAnalysisPage 的 revenue-cost-bridge-sample-badge），
    // 组件内只保留一行正式口径缺口说明。
    const note = screen.getByTestId("revenue-cost-bridge-sample-note");
    expect(note).toHaveTextContent(`正式口径读数：${EM_DASH}（未接入）`);
    expect(note).toHaveTextContent("数值不代表正式读数");

    expect(screen.getByTestId("revenue-cost-bridge-chart-stub")).toBeInTheDocument();
    expect(screen.queryByText(/72\.87/)).not.toBeInTheDocument();
    expect(screen.queryByText(/29\.5bp/)).not.toBeInTheDocument();
  });
});
