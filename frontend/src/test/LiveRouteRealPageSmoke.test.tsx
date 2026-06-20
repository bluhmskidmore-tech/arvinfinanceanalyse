import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="live-route-echarts-stub" />,
}));

const routeSmokeCases = [
  {
    route: "/bond-dashboard",
    anchor: "bond-dashboard-page",
  },
  {
    route: "/cashflow-projection",
    anchor: "cashflow-projection-page",
  },
  {
    route: "/concentration-monitor",
    anchor: "concentration-monitor-kpi-grid",
  },
  {
    route: "/average-balance",
    anchor: "average-balance-page",
  },
  {
    route: "/team-performance",
    anchor: "team-performance-page",
  },
  {
    route: "/platform-config",
    anchor: "platform-config-page-title",
  },
  {
    route: "/pnl-attribution",
    anchor: "pnl-attribution-page-title",
  },
] as const;

describe("live route real page smoke", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules(
      "average-balance",
      "bond-dashboard",
      "cashflow-projection",
      "concentration-monitor",
      "platform-config",
      "pnl-attribution",
      "team-performance",
    );
  }, 20_000);

  it.each(routeSmokeCases)("renders the real page surface for $route", async ({ route, anchor }) => {
    renderWorkbenchApp([route], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId(anchor, {}, { timeout: 10_000 })).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
    expect(screen.queryByText("\u9875\u9762\u52a0\u8f7d\u4e2d")).not.toBeInTheDocument();
    expect(screen.queryByText("Unexpected Application Error!")).not.toBeInTheDocument();
  });
});
