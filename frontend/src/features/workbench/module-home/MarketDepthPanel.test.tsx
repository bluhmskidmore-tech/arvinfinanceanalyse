import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MarketCrisisExplainBand } from "./MarketCrisisExplainBand";
import { MarketDepthPanel } from "./MarketDepthPanel";
import type { ModuleHomeDetailPanel } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

const curvePanel: ModuleHomeDetailPanel = {
  key: "yield-curve-quotes",
  title: "国债与国开曲线",
  meta: "market-data · 2026-06-12",
  stateLabel: "已就绪",
  stateDetail: "曲线报价为空。",
  tone: "ok",
  rows: [
    {
      key: "gov-3y",
      label: "国债 3Y",
      value: "1.82%",
      detail: "+2bp",
      tradeDate: "2026-06-12",
      source: "E-EMM00512345",
      tone: "ok",
    },
  ],
};

describe("MarketDepthPanel compactLadder", () => {
  it("keeps human label visible and hides series_id from the row meta line", () => {
    const { container } = render(
      <MarketDepthPanel compactLadder panel={curvePanel} testId="module-home-yield-curve" />,
    );

    expect(screen.getByText("国债 3Y")).toBeInTheDocument();
    expect(screen.queryByText("E-EMM00512345")).not.toBeInTheDocument();

    const label = screen.getByText("国债 3Y");
    expect(label).toHaveAttribute("title", "国债 3Y · E-EMM00512345");

    const sourceLine = container.querySelector(`.${marketStyles.terminalTableSource}`);
    expect(sourceLine).toHaveAttribute("title", "E-EMM00512345");
    expect(sourceLine?.textContent).toBe("2026-06-12");
  });

  it("hides ladder trade dates when hideLadderDates is set", () => {
    const { container } = render(
      <MarketDepthPanel compactLadder hideLadderDates panel={curvePanel} testId="module-home-yield-curve" />,
    );

    expect(container.querySelector(`.${marketStyles.terminalTableSource}`)).toBeNull();
  });

  it("still renders series_id inline when compactLadder is off", () => {
    render(<MarketDepthPanel panel={curvePanel} testId="module-home-yield-curve" />);

    expect(screen.getByText("2026-06-12 · E-EMM00512345")).toBeInTheDocument();
  });
});

describe("MarketCrisisExplainBand percentile track", () => {
  it("renders API percentile without frontend recalculation", () => {
    render(
      <MemoryRouter>
        <MarketCrisisExplainBand
          explain={{
            crisisScore: -0.57,
            regime: "宽松",
            percentile: 36.21,
            headline: "Crisis Score -0.57: 宽松",
            recommendation: null,
            dataStatus: "complete",
            availableComponentCount: null,
            componentCount: null,
            scoreDelta: null,
            percentileDelta: null,
            components: [],
            scoreHistory: [],
            warnings: [],
            tone: "ok",
          }}
        />
      </MemoryRouter>,
    );

    const track = screen.getByTestId("module-home-market-crisis-percentile");
    expect(track).toHaveTextContent("P36.2");
    expect(track.querySelector(`.${marketStyles.marketCrisisPercentileFill}`)).toHaveStyle({ width: "36.21%" });
  });
});
