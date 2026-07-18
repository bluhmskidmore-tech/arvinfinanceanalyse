import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  createMemoryRouter,
  Outlet,
  RouterProvider,
  type RouteObject,
} from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { routerFuture } from "../router/routerFuture";
import { workbenchRoutes } from "../router/routes";

vi.mock("../layouts/WorkbenchShell", () => ({
  WorkbenchShell: () => (
    <section data-testid="workbench-shell">
      <Outlet />
    </section>
  ),
}));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../features/pnl/PnlByBusinessPage", () => ({
  default: () => <section data-testid="pnl-by-business-page" />,
}));

vi.mock("../features/pnl-business-insights/PnlByBusinessInsightsPage", () => ({
  default: () => <section data-testid="pnl-by-business-insights-page" />,
}));

vi.mock("../features/workbench/pages/WorkbenchPlaceholderPage", () => ({
  default: () => <section data-testid="workbench-placeholder-page" />,
}));

function getRootChildren(routes: RouteObject[]): RouteObject[] {
  return routes.find((route) => route.path === "/")?.children ?? [];
}

describe("workbench route definitions", () => {
  it("does not register duplicate child paths under the workbench root", () => {
    const paths = getRootChildren(workbenchRoutes)
      .map((route) => route.path)
      .filter((path): path is string => typeof path === "string");
    const duplicatePaths = [
      ...new Set(paths.filter((path, index) => paths.indexOf(path) !== index)),
    ];

    expect(duplicatePaths).toEqual([]);
  });

  it("resolves /pnl-by-business to PnlByBusinessPage instead of the placeholder", async () => {
    const router = createMemoryRouter(workbenchRoutes, {
      initialEntries: ["/pnl-by-business"],
      future: routerFuture,
    });

    render(<RouterProvider router={router} future={routerFuture} />);

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-placeholder-page")).not.toBeInTheDocument();
  });

  it("resolves /pnl-by-business-insights to its real page instead of the placeholder", async () => {
    const router = createMemoryRouter(workbenchRoutes, {
      initialEntries: ["/pnl-by-business-insights"],
      future: routerFuture,
    });

    render(<RouterProvider router={router} future={routerFuture} />);

    expect(await screen.findByTestId("pnl-by-business-insights-page")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-placeholder-page")).not.toBeInTheDocument();
  });
});
