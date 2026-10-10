import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import {
  buildMockProductCategoryAttributionEnvelope,
  buildMockProductCategoryPnlEnvelope,
} from "../mocks/productCategoryPnl";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({ default: () => <div /> }));

const REPORT_DATE = "2026-02-28";
const SAMPLE_NAME = "口径核对样本";

function clientFixture() {
  const client = createApiClient({ mode: "mock" });
  return {
    ...client,
    getProductCategoryDates: vi.fn(async () =>
      buildMockApiEnvelope("product_category_pnl.dates", {
        report_dates: [REPORT_DATE],
      }),
    ),
    getProductCategoryPnl: vi.fn(
      async (options: Parameters<typeof client.getProductCategoryPnl>[0]) => {
        const envelope = buildMockProductCategoryPnlEnvelope(options);
        const income = options.scenarioRatePct
          ? "-100000000"
          : options.view === "monthly"
            ? "100000000"
            : "500000000";
        envelope.result.rows = [{
          ...envelope.result.rows[0]!,
          category_name: SAMPLE_NAME,
          business_net_income: income,
          cnx_scale: "10000000000",
          weighted_yield: "3.00",
        }];
        envelope.result.grand_total = {
          ...envelope.result.grand_total,
          business_net_income: income,
        };
        return envelope;
      },
    ),
    getProductCategoryAttribution: vi.fn(
      async (options: Parameters<typeof client.getProductCategoryAttribution>[0]) => {
        const envelope = buildMockProductCategoryAttributionEnvelope(options);
        const delta = options.compare === "yoy" ? "900000000" : "100000000";
        const row = {
          ...envelope.result.rows[0]!,
          category_name: SAMPLE_NAME,
          effects: {
            day_effect: "0",
            scale_effect: "0",
            rate_effect: "0",
            ftp_effect: "0",
            direct_effect: delta,
            unexplained_effect: "0",
            explained_effect: delta,
            delta_business_net_income: delta,
            closure_error: "0",
          },
        };
        envelope.result.rows = [row];
        envelope.result.totals!.grand_total = {
          ...row,
          category_id: "grand_total",
          category_name: "grand_total",
          side: "all",
        };
        return envelope;
      },
    ),
  } satisfies typeof client;
}

beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 60_000);

beforeEach(() => {
  window.localStorage.setItem("moss.product-category-pnl.trend-workspace-open", "0");
});

describe("operating analysis uses a consistent formal period", () => {
  it("keeps formal income and month-on-month movement after applying a scenario and selecting year-on-year attribution", async () => {
    const client = clientFixture();
    const user = userEvent.setup();
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-operating-workspace").querySelector("summary")!);
    const analysis = screen.getByTestId("product-category-operating-analysis");
    const movement = screen.getByTestId("product-category-operating-movement");
    await waitFor(() => expect(movement).toHaveTextContent("+1.00"));

    await user.selectOptions(screen.getByLabelText("FTP 场景"), "2.00");
    await user.click(screen.getByTestId("product-category-apply-scenario-button"));
    await screen.findByTestId("product-category-result-meta-scenario");
    expect(screen.getByTestId("product-category-table")).toHaveTextContent("-1.00");
    expect(analysis).toHaveTextContent("全表净营收 1.00 亿元");

    await user.click(screen.getByRole("button", { name: "同比" }));
    await waitFor(() => expect(client.getProductCategoryAttribution).toHaveBeenCalledWith({
      reportDate: REPORT_DATE,
      compare: "yoy",
    }));
    await waitFor(() => expect(movement).toHaveTextContent("+1.00"));
    expect(movement).not.toHaveTextContent("+9.00");
  });

  it("removes cached monthly drivers when displaying cumulative formal income", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/product-category-pnl"], { client: clientFixture() });
    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-operating-workspace").querySelector("summary")!);
    const movement = screen.getByTestId("product-category-operating-movement");
    await waitFor(() => expect(movement).toHaveTextContent(SAMPLE_NAME));

    await user.click(screen.getByRole("button", { name: "汇总视图" }));
    await waitFor(() => expect(screen.getByTestId("product-category-operating-analysis")).toHaveTextContent("全表净营收 5.00 亿元"));
    expect(screen.getByTestId("product-category-operating-movement")).not.toHaveTextContent(SAMPLE_NAME);
    expect(screen.getByTestId("product-category-operating-analysis")).toHaveTextContent("累计");
  });

  it("keeps decision-focus cards on formal month-on-month evidence and clears them for cumulative views", async () => {
    const client = clientFixture();
    const attribution = client.getProductCategoryAttribution;
    client.getProductCategoryAttribution = vi.fn(async (options) => {
      const envelope = await attribution(options);
      const effects = envelope.result.rows[0]!.effects;
      effects.delta_business_net_income = options.compare === "yoy" ? "-900000000" : "-100000000";
      effects.direct_effect = effects.delta_business_net_income;
      return envelope;
    });
    const user = userEvent.setup();
    renderWorkbenchApp(["/product-category-pnl"], { client });
    await screen.findByTestId("product-category-table");
    await user.click(screen.getByTestId("product-category-financial-workspace").querySelector("summary")!);
    await waitFor(() => expect(screen.getByTestId("product-category-decision-focus")).toHaveTextContent("-1.00"));

    await user.click(screen.getByRole("button", { name: "同比" }));
    await waitFor(() => expect(client.getProductCategoryAttribution).toHaveBeenCalledWith({ reportDate: REPORT_DATE, compare: "yoy" }));
    expect(screen.getByTestId("product-category-decision-focus")).toHaveTextContent("-1.00");
    expect(screen.getByTestId("product-category-decision-focus")).not.toHaveTextContent("-9.00");

    await user.click(screen.getByRole("button", { name: "汇总视图" }));
    await screen.findByTestId("product-category-attribution-ineligible");
    expect(screen.getByTestId("product-category-decision-focus")).not.toHaveTextContent("环比恶化最大");
  });
});
