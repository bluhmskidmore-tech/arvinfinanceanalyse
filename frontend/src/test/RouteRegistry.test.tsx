import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { AppProviders } from "../app/providers";
import { workbenchRoutes, workbenchSections } from "../router/routes";

function renderWorkbench(initialEntries: string[]) {
  const router = createMemoryRouter(workbenchRoutes, {
    initialEntries,
  });

  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}

describe("RouteRegistry", () => {
  it("exposes eight primary workbench entries", () => {
    expect(workbenchSections).toHaveLength(8);
  });

  it("renders the dashboard landing page inside the workbench shell", async () => {
    renderWorkbench(["/"]);

    expect(await screen.findByRole("navigation", { name: "主导航" })).toBeInTheDocument();
    expect(screen.getByText("管理层驾驶舱")).toBeInTheDocument();
    expect(await screen.findByText("今日窗口概况")).toBeInTheDocument();
  });

  it("renders a placeholder workbench page for non-dashboard entries", async () => {
    renderWorkbench(["/risk-overview"]);

    expect(
      await screen.findByRole("heading", { name: "风险总览" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("该工作台将在后续阶段接入真实薄页面。"),
    ).toBeInTheDocument();
  });
});
