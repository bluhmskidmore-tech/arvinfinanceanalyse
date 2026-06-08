import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisCycleRuleSummary } from "../features/stock-analysis/components/StockAnalysisCycleRuleSummary";
import type { LivermoreCycleRotationFramework } from "../api/contracts";

const cycleFramework: Pick<
  LivermoreCycleRotationFramework,
  "layers" | "observation_only" | "rebalance_cadence"
> = {
  observation_only: true,
  rebalance_cadence: "monthly_core_weekly_tracking",
  layers: [
    {
      key: "macro_direction",
      title: "Macro",
      weight: 0.6,
      status: "ready",
      evidence: "Macro evidence",
      available_inputs: [],
      missing_inputs: [],
    },
    {
      key: "industry_cycle",
      title: "Industry",
      weight: 0.4,
      status: "ready",
      evidence: "Industry evidence",
      available_inputs: [],
      missing_inputs: [],
    },
    {
      key: "execution_constraints",
      title: "Boundary",
      weight: null,
      status: "pending",
      evidence: "Boundary evidence",
      available_inputs: [],
      missing_inputs: [],
    },
  ],
};

describe("StockAnalysisCycleRuleSummary", () => {
  it("renders rule weights, observation-only copy, and cadence using the stock analysis classes", () => {
    render(<StockAnalysisCycleRuleSummary framework={cycleFramework} />);

    const summary = screen.getByTestId("stock-analysis-cycle-rule-summary");

    expect(summary).toHaveClass("stock-analysis-page__cycle-formulas");
    expect(summary).toHaveTextContent("轮动规则");
    expect(summary).toHaveTextContent("60%");
    expect(summary).toHaveTextContent("40%");
    expect(summary).toHaveTextContent("只读观察，不生成交易指令");
    expect(summary.querySelectorAll("small")).toHaveLength(2);
  });

  it("omits the observation-only copy when the framework can generate downstream actions", () => {
    render(
      <StockAnalysisCycleRuleSummary
        framework={{
          ...cycleFramework,
          observation_only: false,
        }}
      />,
    );

    expect(screen.getByTestId("stock-analysis-cycle-rule-summary")).not.toHaveTextContent(
      "只读观察，不生成交易指令",
    );
    expect(screen.getByTestId("stock-analysis-cycle-rule-summary").querySelectorAll("small")).toHaveLength(1);
  });
});
