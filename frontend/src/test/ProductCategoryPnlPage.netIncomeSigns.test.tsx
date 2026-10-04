import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { buildMockProductCategoryPnlEnvelope } from "../mocks/productCategoryPnl";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({ default: () => null }));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 60_000);

it("keeps liability net-income signs through the formal table, colors and selection readouts", async () => {
  const user = userEvent.setup();
  const client = createApiClient({ mode: "mock" });
  window.localStorage.setItem("moss.product-category-pnl.trend-workspace-open", "0");
  renderWorkbenchApp(["/product-category-pnl"], {
    client: {
      ...client,
      getProductCategoryAttribution: vi.fn(async (options) => {
        const envelope = await client.getProductCategoryAttribution(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: [
              ...envelope.result.rows,
              {
                ...envelope.result.rows[0],
                category_id: "credit_linked_notes",
                category_name: "信用联结票据",
                side: "liability",
              },
            ],
          },
        };
      }),
      getProductCategoryPnl: vi.fn(async (options) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            liability_total: {
              ...envelope.result.liability_total,
              business_net_income: "-200000000",
            },
            rows: envelope.result.rows.map((row) => {
              if (row.category_id === "credit_linked_notes") {
                return {
                  ...row,
                  cnx_scale: "-3000000000",
                  cny_net: "-200000000",
                  foreign_net: "50000000",
                  business_net_income: "-150000000",
                };
              }
              if (row.category_id === "interbank_borrowings") {
                return {
                  ...row,
                  cny_net: "25000000",
                  foreign_net: "-75000000",
                  business_net_income: "-50000000",
                };
              }
              return row;
            }),
          },
        };
      }),
    },
  });

  const table = await screen.findByTestId("product-category-table");
  const clnRow = within(table).getByText("信用联结票据").closest("tr")!;
  const borrowingRow = within(table).getByText("同业拆入").closest("tr")!;
  const clnCells = within(clnRow).getAllByRole("cell");
  expect(clnCells.map((cell) => cell.textContent).slice(1, 5)).toEqual([
    "30.00",
    "-2.00",
    "0.50",
    "-1.50",
  ]);
  expect(clnCells[2]).toHaveClass("product-category-formal-table__cell--negative");
  expect(clnCells[3]).toHaveClass("product-category-formal-table__cell--positive");
  expect(clnCells[4]).toHaveClass("product-category-formal-table__cell--negative");
  expect(within(borrowingRow).getAllByRole("cell")[3]).toHaveTextContent("-0.75");
  expect(within(borrowingRow).getAllByRole("cell")[3]).toHaveClass(
    "product-category-formal-table__cell--negative",
  );
  const totals = screen.getByTestId("product-category-formal-headline-totals");
  expect(within(totals).getByText("负债端（亿元）").parentElement).toHaveTextContent(
    "-2.00",
  );

  await user.click(await within(clnRow).findByRole("button", {
    name: "查看 信用联结票据 归因证据",
  }));
  const mobileReadout = screen.getByTestId("product-category-formal-table-mobile-readout");
  const selection = screen.getByTestId("product-category-formal-selection-context");
  for (const [label, value] of [
    ["人民币净收入", "-2.00"],
    ["外币净收入", "0.50"],
    ["营业净收入", "-1.50"],
  ]) {
    expect(within(mobileReadout).getByText(label, { selector: "span" }).parentElement)
      .toHaveTextContent(value);
    expect(within(selection).getByText(label, { selector: "dt" }).parentElement)
      .toHaveTextContent(value);
  }

  await user.click(screen.getByRole("button", { name: "完整口径" }));
  const fullCells = within(clnRow).getAllByRole("cell");
  expect(fullCells[7]).toHaveTextContent("-2.00");
  expect(fullCells[10]).toHaveTextContent("0.50");
  expect(fullCells[11]).toHaveTextContent("-1.50");
});
