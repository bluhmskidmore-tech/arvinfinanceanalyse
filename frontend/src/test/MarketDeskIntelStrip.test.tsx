import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MarketDeskIntelStrip } from "../features/workbench/module-home/MarketDeskIntelStrip";
import type { MarketDeskIntelView } from "../features/workbench/module-home/moduleHomeModel";

const baseIntel: MarketDeskIntelView = {
  curveShape: "ModerateSteep",
  curveShapeLabel: "中度陡峭",
  curveInterpretation: "收益率曲线中度陡峭，久期不必极端化。",
  spread10y1yBp: 34,
  curvePercentile1y: 62.5,
  indicators: [
    { key: "dr007", label: "DR007", value: "1.82% · -3.70%", group: "流动性", tone: "ok" },
    { key: "hs300", label: "沪深300", value: "4807.31点 · +0.61%", group: "风险资产", tone: "ok" },
  ],
};

describe("MarketDeskIntelStrip", () => {
  it("renders curve shape and indicator highlights", () => {
    render(
      <MemoryRouter>
        <MarketDeskIntelStrip intel={baseIntel} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("module-home-market-desk-intel")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-market-desk-curve-shape")).toHaveTextContent("中度陡峭");
    expect(screen.getByTestId("module-home-market-desk-indicator-dr007")).toBeInTheDocument();
  });
});
