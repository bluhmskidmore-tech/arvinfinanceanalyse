import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MarketCrossAssetGapBlock } from "../features/workbench/module-home/MarketCrossAssetGapBlock";
import type { MarketCrisisExplainView, ModuleHomeDetailRow } from "../features/workbench/module-home/moduleHomeModel";

const detailRow = (key: string, label: string): ModuleHomeDetailRow => ({
  key,
  label,
  value: "1.00",
  detail: "+1bp",
  tradeDate: "2026-06-12",
  source: "mock",
  tone: "ok",
});

const crisisExplain: MarketCrisisExplainView = {
  crisisScore: -0.57,
  regime: "宽松",
  percentile: 36.21,
  headline: "Crisis Score -0.57: 宽松",
  recommendation: null,
  dataStatus: "complete",
  availableComponentCount: 5,
  componentCount: 5,
  scoreDelta: null,
  percentileDelta: null,
  components: [],
  scoreHistory: [
    { date: "2026-04-03", crisisScore: -0.63, percentile: 34.0 },
    { date: "2026-04-10", crisisScore: -0.57, percentile: 36.21 },
  ],
  warnings: [],
  tone: "ok",
};

describe("MarketCrossAssetGapBlock", () => {
  it("renders missing bucket chips, crisis mini trend, and secondary rows", () => {
    render(
      <MemoryRouter>
        <MarketCrossAssetGapBlock
          allRows={[detailRow("csi300", "沪深300"), detailRow("dxy", "DXY"), detailRow("obscure-pe", "冷门指数市盈率")]}
          crisisExplain={crisisExplain}
          liquidityRow={detailRow("dr007", "DR007")}
          presentBuckets={new Set(["equity", "commod"])}
          primaryKeys={new Set(["csi300"])}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("module-home-cross-asset-gap-block")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-cross-asset-missing-rates")).toHaveTextContent("RATES");
    expect(screen.getByTestId("module-home-cross-asset-missing-rates")).toHaveTextContent("1.00");
    expect(screen.getByTestId("module-home-cross-asset-missing-fx")).toHaveTextContent("FX");
    expect(screen.getByTestId("module-home-cross-asset-missing-fx")).toHaveTextContent("待观察");
    expect(screen.getByTestId("module-home-cross-asset-crisis-mini")).toBeInTheDocument();
    expect(screen.getByTestId("module-home-cross-asset-secondary-dxy")).toBeInTheDocument();
  });

  it("returns null when there is nothing to show", () => {
    const { container } = render(
      <MemoryRouter>
        <MarketCrossAssetGapBlock
          allRows={[detailRow("obscure-pe", "某指数市盈率")]}
          presentBuckets={new Set(["rates", "fx", "equity"])}
          primaryKeys={new Set(["obscure-pe"])}
        />
      </MemoryRouter>,
    );

    expect(container.firstChild).toBeNull();
  });
});
