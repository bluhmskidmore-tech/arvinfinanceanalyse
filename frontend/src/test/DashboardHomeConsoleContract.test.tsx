import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => null,
}));

// Agent-eval probe for the `no_console_errors` page gate of
// dashboard_home_contract_001: rendering the `/` dashboard-home route with the
// mock client must not emit console.error. This covers the jsdom render path
// only; real-browser console coverage still needs a scoped Playwright spec.
describe("DashboardHomeConsoleContract", () => {
  it("renders the dashboard-home route first screen and deferred body without console errors", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error");

    renderWorkbenchApp(["/"]);

    await screen.findByTestId("dashboard-home-page");
    await screen.findByTestId("dashboard-home-morning-hero");

    fireEvent.scroll(window);
    await screen.findByTestId("dashboard-home-work-grid");
    await screen.findByTestId("dashboard-home-bottom-grid");

    expect(consoleErrorSpy.mock.calls).toEqual([]);
  });
});
