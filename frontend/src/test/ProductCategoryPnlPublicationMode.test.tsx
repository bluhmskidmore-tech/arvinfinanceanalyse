import { screen, within } from "@testing-library/react";
import { beforeAll, vi } from "vitest";

import { createApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="product-category-echarts-stub" />,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("product-category-pnl");
}, 60_000);

describe("ProductCategoryPnlPage publication mode", () => {
  it("does not show the publication header on the regular route", async () => {
    renderWorkbenchApp(["/product-category-pnl"]);

    const page = await screen.findByTestId("product-category-page");

    expect(
      within(page).queryByLabelText("论文投稿展示说明"),
    ).not.toBeInTheDocument();
    expect(page).not.toHaveAttribute("data-publication-capture");
    expect(page).not.toHaveAttribute("data-publication-focus");
  });

  it("shows the overview publication header by default", async () => {
    renderWorkbenchApp(["/product-category-pnl?presentation=paper"]);

    const page = await screen.findByTestId("product-category-page");
    const header = within(page).getByLabelText("论文投稿展示说明");

    expect(within(header).getByText("经营结果与利差总览")).toBeInTheDocument();
    expect(page).toHaveAttribute("data-publication-capture", "paper");
    expect(page).toHaveAttribute("data-publication-focus", "overview");
  });

  it("shows the attribution publication header and data attributes", async () => {
    renderWorkbenchApp([
      "/product-category-pnl?presentation=paper&focus=attribution",
    ]);

    const page = await screen.findByTestId("product-category-page");
    const header = within(page).getByLabelText("论文投稿展示说明");

    expect(within(header).getByText("差异归因与证据复核")).toBeInTheDocument();
    expect(page).toHaveAttribute("data-publication-capture", "paper");
    expect(page).toHaveAttribute("data-publication-focus", "attribution");
  });

  it("ignores publication parameters for a real-data client", async () => {
    const realModeClient = {
      ...createApiClient({ mode: "mock" }),
      mode: "real" as const,
    };

    renderWorkbenchApp(["/product-category-pnl?presentation=paper"], {
      client: realModeClient,
    });

    const page = await screen.findByTestId("product-category-page");

    expect(
      within(page).queryByLabelText("论文投稿展示说明"),
    ).not.toBeInTheDocument();
    expect(page).not.toHaveAttribute("data-publication-capture");
    expect(page).not.toHaveAttribute("data-publication-focus");
  });
});
