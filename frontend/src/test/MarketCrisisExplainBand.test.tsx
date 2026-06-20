import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MarketCrisisExplainBand } from "../features/workbench/module-home/MarketCrisisExplainBand";
import type { MarketCrisisExplainView } from "../features/workbench/module-home/moduleHomeModel";

const baseExplain: MarketCrisisExplainView = {
  crisisScore: -0.57,
  regime: "宽松",
  percentile: 36.21,
  headline: "Crisis Score -0.57: 宽松",
  recommendation: "可适当加仓，风险偏好环境",
  dataStatus: "complete",
  availableComponentCount: 5,
  componentCount: 5,
  scoreDelta: 0.06,
  percentileDelta: 2.21,
  components: [{ key: "equity_vol", label: "HS300 realized volatility", zScore: -0.42, weight: 0.25, rawValue: 12.32 }],
  scoreHistory: [
    { date: "2026-04-03", crisisScore: -0.63, percentile: 34.0 },
    { date: "2026-04-10", crisisScore: -0.57, percentile: 36.21 },
  ],
  warnings: [],
  tone: "ok",
};

describe("MarketCrisisExplainBand", () => {
  it("renders enriched crisis context when backend provides score_history", () => {
    render(
      <MemoryRouter>
        <MarketCrisisExplainBand explain={baseExplain} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("module-home-market-crisis-score-trend")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-market-crisis-percentile-trend")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-market-crisis-stat-chips")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-market-crisis-recommendation")).toHaveTextContent("可适当加仓");
  });

  it("hides score trend when history has fewer than two points", () => {
    render(
      <MemoryRouter>
        <MarketCrisisExplainBand explain={{ ...baseExplain, scoreHistory: [] }} />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("module-home-market-crisis-score-trend")).not.toBeInTheDocument();
  });
});
