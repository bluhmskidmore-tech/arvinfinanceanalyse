import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("KpiPerformancePage", () => {
  it("exposes stable local layout hooks for the /kpi governance surface", async () => {
    const mockClient = createApiClient({ mode: "mock" });

    renderWorkbenchApp(["/kpi"], { client: mockClient });

    const page = await screen.findByTestId("kpi-performance-page");

    expect(page).toHaveClass("kpi-performance-page");
    expect(within(page).getByTestId("kpi-performance-header")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-filters")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-filter-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-action-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-main-grid")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-empty-state")).toBeInTheDocument();
  });

  it("keeps populated detail and fetch-result layout surfaces local to /kpi", async () => {
    const user = userEvent.setup();
    const mockClient = createApiClient({ mode: "mock" });

    renderWorkbenchApp(["/kpi"], { client: mockClient });

    const page = await screen.findByTestId("kpi-performance-page");
    await user.click(await screen.findByRole("button", { name: /固定收益部/ }));

    expect(within(page).getByTestId("kpi-performance-detail-header")).toHaveClass(
      "kpi-performance-page__detail-header",
    );

    await user.click(within(page).getByRole("button", { name: /抓取并重算/ }));

    const fetchResult = await within(page).findByText(/共 0 个指标/);
    expect(fetchResult.closest(".kpi-performance-page__fetch-result")).not.toBeNull();
  });
});
