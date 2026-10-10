import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import { ProductCategoryLiabilityCurrencyMatrixMobileReadout } from "./ProductCategoryAttributionPanels";
import { buildProductCategoryTrendSnapshot, selectProductCategoryLiabilityDetailMatrix } from "./productCategoryPnlPageModel";

it.each(["cny", "foreign"] as const)("identifies the %s matrix rate as the all-currency composite", (currencyKey) => {
  const { result } = buildMockProductCategoryPnlEnvelope({ reportDate: "2026-08-31", view: "monthly" });
  const matrix = selectProductCategoryLiabilityDetailMatrix([buildProductCategoryTrendSnapshot({
    ...result, liability_total: { ...result.liability_total, weighted_yield: "1.55459650" },
  })]);
  render(<ProductCategoryLiabilityCurrencyMatrixMobileReadout
    matrix={matrix.currencyMatrices.find(item => item.currencyKey === currencyKey)!}
    periods={matrix.periods}
  />);

  expect(screen.getByText("最新综合成本率").parentElement).toHaveTextContent("1.55");
  expect(screen.getByText("综合成本率变动")).toBeInTheDocument();
  expect(screen.queryByText("最新收益率")).not.toBeInTheDocument();
});
