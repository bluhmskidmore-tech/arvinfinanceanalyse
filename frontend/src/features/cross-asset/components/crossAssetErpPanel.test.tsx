import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ERP_DISPLAY_CALIBER_LABEL, type EquityBondERP } from "../lib/crossAssetAnalytics";
import { EquityBondERPPanel } from "./MomentumAndVolatilityPanels";

function erpFixture(overrides: Partial<EquityBondERP> = {}): EquityBondERP {
  return {
    available: true,
    earningsYieldPct: 6.83,
    bondYieldPct: 1.88,
    erpPct: 4.95,
    verdict: "equity_cheap",
    verdictLabel: "股票偏便宜",
    verdictDescription: "ERP 4.95% ≥ 4.00%：盈利收益率显著高于无风险利率，股票相对债券有吸引力。",
    caliberLabel: ERP_DISPLAY_CALIBER_LABEL,
    verdictColor: "erp-cheap",
    verdictBg: "erp-cheap-bg",
    ...overrides,
  };
}

describe("EquityBondERPPanel", () => {
  it("renders the display-caliber disclosure next to the cheap/expensive verdict", () => {
    render(<EquityBondERPPanel erp={erpFixture()} />);

    const panel = screen.getByTestId("cross-asset-equity-bond-erp");
    const verdict = within(panel).getByTestId("cross-asset-erp-verdict");
    const caliber = within(verdict).getByTestId("cross-asset-erp-caliber");

    expect(verdict).toHaveTextContent("股票偏便宜");
    expect(caliber).toHaveTextContent(ERP_DISPLAY_CALIBER_LABEL);
    expect(caliber.getAttribute("title")).toBeNull();
  });

  it("keeps the same visible caliber next to an expensive verdict", () => {
    render(
      <EquityBondERPPanel
        erp={erpFixture({
          verdict: "equity_expensive",
          verdictLabel: "股票偏贵",
          verdictDescription: "ERP 1.20% ≤ 2.75%：盈利收益率接近无风险利率，股票估值偏高。",
        })}
      />,
    );

    const verdict = screen.getByTestId("cross-asset-erp-verdict");
    expect(verdict).toHaveTextContent("股票偏贵");
    expect(within(verdict).getByTestId("cross-asset-erp-caliber")).toHaveTextContent(ERP_DISPLAY_CALIBER_LABEL);
  });
});
