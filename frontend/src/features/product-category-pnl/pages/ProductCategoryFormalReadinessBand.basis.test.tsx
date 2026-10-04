import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildMockProductCategoryAttributionEnvelope, buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import { ProductCategoryFormalReadinessBand } from "./ProductCategoryFormalReadinessBand";

const baseline = buildMockProductCategoryPnlEnvelope({ reportDate: "2026-08-31", view: "monthly" }).result;
const attribution = buildMockProductCategoryAttributionEnvelope({ reportDate: "2026-08-31", compare: "mom" }).result;
const attributionTotals = attribution.totals!;

describe("product-category headline basis", () => {
  it("identifies scenario totals and formal period comparisons on each headline field", () => {
    const formalAttribution = {
      ...attribution,
      totals: {
        ...attributionTotals,
        grand_total: {
          ...attributionTotals.grand_total,
          prior: { ...attributionTotals.grand_total.prior!, business_net_income: "197176445.80110970" },
          effects: { ...attributionTotals.grand_total.effects, delta_business_net_income: "511749598.32459353" },
        },
      },
    };
    render(<ProductCategoryFormalReadinessBand
      reportDate="2026-08-31" selectedView="monthly" scenarioApplied
      grandTotal={{ ...baseline.grand_total, business_net_income: "634860749.1496290500" }}
      assetTotal={baseline.asset_total} liabilityTotal={baseline.liability_total}
      attribution={formalAttribution}
    />);

    expect(screen.getByTestId("product-category-formal-headline-copy")).toHaveTextContent(
      "本期情景经营净收入 6.35 亿元；正式环比变动 5.12 亿元；正式归因闭合误差",
    );
    const totals = screen.getByTestId("product-category-formal-headline-totals");
    expect(within(totals).getByText("情景FTP后经营净收入（亿元）")).toBeInTheDocument();
    expect(within(totals).getByText("正式环比变动（亿元）").parentElement).toHaveTextContent("正式对比期 1.97");
    expect(within(totals).getByText("情景资产端（亿元）")).toBeInTheDocument();
    expect(within(totals).getByText("情景负债端（亿元）")).toBeInTheDocument();
  });

  it("retains the formal baseline wording and hides monthly comparison values for ytd", () => {
    render(<ProductCategoryFormalReadinessBand
      reportDate="2026-08-31" selectedView="ytd" scenarioApplied={false}
      grandTotal={baseline.grand_total} attribution={attribution}
    />);
    expect(screen.getByTestId("product-category-formal-headline-copy")).toHaveTextContent("本期合计经营净收入");
    expect(screen.getByTestId("product-category-formal-headline-copy")).toHaveTextContent("当前展示正式基线");
    expect(screen.queryByText("正式环比变动（亿元）")).not.toBeInTheDocument();
  });

  it("identifies scenario income when monthly attribution is unavailable", () => {
    render(<ProductCategoryFormalReadinessBand
      reportDate="2026-08-31" selectedView="ytd" scenarioApplied
      grandTotal={baseline.grand_total}
    />);
    expect(screen.getByTestId("product-category-formal-headline-copy")).toHaveTextContent("本期情景经营净收入");
    expect(screen.getByTestId("product-category-formal-driver-readout")).toHaveTextContent("汇总视图继续展示情景FTP后经营净收入");
  });
});
