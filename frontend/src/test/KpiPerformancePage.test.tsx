import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const kpiModalSourceFiles = [
  {
    name: "MetricEditModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/MetricEditModal.tsx"),
    rootClass: "kpi-modal-v2--edit",
  },
  {
    name: "BatchPasteModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/BatchPasteModal.tsx"),
    rootClass: "kpi-modal-v2--batch",
  },
  {
    name: "MetricManageModal",
    path: resolve(process.cwd(), "src/features/kpi-performance/components/MetricManageModal.tsx"),
    rootClass: "kpi-modal-v2--manage",
  },
];

describe("KpiPerformancePage", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("kpi");
  }, 20_000);

  it("exposes stable local layout hooks for the /kpi governance surface", async () => {
    const mockClient = createApiClient({ mode: "mock" });

    renderWorkbenchApp(["/kpi"], { client: mockClient });

    const page = await screen.findByTestId("kpi-performance-page");

    expect(page).toHaveClass("kpi-performance-page");
    expect(page).toHaveClass("moss-page-v2-shell");
    expect(within(page).getByTestId("kpi-performance-header")).toHaveClass(
      "moss-page-v2-decision-hero",
    );
    expect(within(page).getByTestId("kpi-performance-data-status")).toHaveClass(
      "moss-page-v2-data-status",
    );
    const filters = within(page).getByTestId("kpi-performance-filters");
    expect(filters.querySelector(".ant-card")).toBeNull();
    expect(within(page).getByTestId("kpi-performance-filter-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-action-row")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-performance-main-grid")).toBeInTheDocument();
    expect(within(page).getByTestId("kpi-owner-list-panel")).toHaveClass(
      "kpi-owner-list-card",
    );
    expect(within(page).getByTestId("kpi-performance-empty-state")).toHaveClass(
      "moss-page-v2-state-surface",
    );
    expect(within(page).getByRole("combobox", { name: "KPI assessment year" })).toBeInTheDocument();
    expect(within(page).getByRole("combobox", { name: "KPI period type" })).toBeInTheDocument();
    expect(within(page).getByLabelText("KPI as-of date")).toBeInTheDocument();
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
    expect(within(page).getByTestId("kpi-performance-detail-header").closest(".kpi-performance-page__detail-card")).not.toBeNull();
    expect(within(page).getByTestId("kpi-metric-table-panel")).toHaveClass(
      "kpi-metric-table-card",
    );

    await user.click(within(page).getByRole("button", { name: /抓取并重算/ }));

    const fetchResult = await within(page).findByText(/共 0 个指标/);
    expect(fetchResult.closest(".kpi-performance-page__fetch-result")).not.toBeNull();
    expect(within(page).getByTestId("kpi-performance-fetch-result")).toHaveClass(
      "moss-page-v2-data-status",
    );
  });

  it("keeps KPI modal visual shells class-based and tokenized", () => {
    const inlineStyleMarker = ["style", "="].join("");
    const privateShadowPattern = new RegExp(
      [
        ["box", "Shadow"].join(""),
        ["box", "-", "shadow"].join(""),
        ["rgba", "\\("].join(""),
      ].join("|"),
    );

    for (const modalFile of kpiModalSourceFiles) {
      const source = readFileSync(modalFile.path, "utf8");

      expect(source, `${modalFile.name} should not add inline style debt`).not.toContain(inlineStyleMarker);
      expect(source, `${modalFile.name} should not hard-code hex colors`).not.toMatch(/#[0-9a-fA-F]{3,8}/);
      expect(source, `${modalFile.name} should not add private shadows`).not.toMatch(privateShadowPattern);
      expect(source).toContain('rootClassName="kpi-modal-v2');
      expect(source).toContain(modalFile.rootClass);
    }
  });
});
