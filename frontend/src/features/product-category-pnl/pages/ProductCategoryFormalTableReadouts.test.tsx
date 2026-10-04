import { fireEvent, render, screen, within } from "@testing-library/react";
import { it, vi } from "vitest";

import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import {
  ProductCategoryFormalSelectionContext,
  ProductCategoryFormalTableMobileReadout,
} from "./ProductCategoryFormalTableReadouts";

const fixture = buildMockProductCategoryPnlEnvelope({
  reportDate: "2026-02-28",
  view: "monthly",
}).result;
const [firstRow, secondRow] = fixture.rows;

it("focuses the selected business row and passes its id to the evidence action", () => {
  const onOpenAttributionEvidence = vi.fn();
  render(
    <ProductCategoryFormalTableMobileReadout
      reportDate="2026-02-28"
      selectedView="monthly"
      selectedCategoryId={secondRow.category_id}
      grandTotal={fixture.grand_total}
      rows={[firstRow, secondRow]}
      onOpenAttributionEvidence={onOpenAttributionEvidence}
    />,
  );

  const readout = screen.getByTestId("product-category-formal-table-mobile-readout");
  expect(within(readout).getByRole("heading")).toHaveTextContent(secondRow.category_name);
  fireEvent.click(within(readout).getByRole("button"));
  expect(onOpenAttributionEvidence).toHaveBeenCalledExactlyOnceWith(secondRow.category_id);
});

it("falls back to the first business row when the selection is absent or a total", () => {
  const { rerender } = render(
    <ProductCategoryFormalTableMobileReadout
      reportDate="2026-02-28"
      selectedView="monthly"
      selectedCategoryId="missing"
      rows={[fixture.grand_total, firstRow, secondRow]}
    />,
  );
  const heading = within(screen.getByTestId("product-category-formal-table-mobile-readout"))
    .getByRole("heading");
  expect(heading).toHaveTextContent(firstRow.category_name);
  expect(screen.queryByRole("button")).not.toBeInTheDocument();

  rerender(
    <ProductCategoryFormalTableMobileReadout
      reportDate="2026-02-28"
      selectedView="monthly"
      selectedCategoryId={fixture.grand_total.category_id}
      rows={[fixture.grand_total, firstRow, secondRow]}
    />,
  );
  expect(heading).toHaveTextContent(firstRow.category_name);
});

it("uses the first row when only a total exists and handles an empty report", () => {
  const { rerender } = render(
    <ProductCategoryFormalTableMobileReadout
      reportDate="2026-02-28"
      selectedView="monthly"
      selectedCategoryId={null}
      rows={[fixture.grand_total]}
    />,
  );
  const readout = screen.getByTestId("product-category-formal-table-mobile-readout");
  expect(within(readout).getByRole("heading")).toHaveTextContent(
    fixture.grand_total.category_name,
  );

  rerender(
    <ProductCategoryFormalTableMobileReadout
      reportDate=""
      selectedView="monthly"
      selectedCategoryId={null}
      rows={[]}
      onOpenAttributionEvidence={vi.fn()}
    />,
  );
  expect(within(readout).getByRole("heading")).toHaveTextContent("正式报表");
  expect(readout).toHaveTextContent("报告月待选");
  expect(readout).toHaveTextContent("详表暂无业务行");
  expect(within(readout).queryByRole("button")).not.toBeInTheDocument();
});

it("passes the selection context row id to its evidence action", () => {
  const onOpenAttributionEvidence = vi.fn();
  render(
    <ProductCategoryFormalSelectionContext
      reportDate="2026-02-28"
      selectedView="monthly"
      sourceLabel="source"
      row={secondRow}
      onOpenAttributionEvidence={onOpenAttributionEvidence}
    />,
  );

  fireEvent.click(
    within(screen.getByTestId("product-category-formal-selection-context"))
      .getByRole("button"),
  );
  expect(onOpenAttributionEvidence).toHaveBeenCalledExactlyOnceWith(secondRow.category_id);
});
