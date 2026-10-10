import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/agent/AgentPanel", () => ({
  AgentPanel: () => <div data-testid="mock-agent-panel" />,
}));

import { DashboardHomeAgentDrawer } from "../features/workbench/dashboard-home/DashboardHomeAgentDrawer";

function LocationStateProbe() {
  const location = useLocation();
  return <output data-testid="handoff-location-state">{JSON.stringify(location.state)}</output>;
}

describe("Dashboard Agent context handoff", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("continues in MOSS Chat with the exact Dashboard date and filters", async () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <DashboardHomeAgentDrawer
                open
                reportDate="2026-08-20"
                currentFilters={{ allow_partial: false, data_status: "formal" }}
                onClose={() => undefined}
              />
            }
          />
          <Route path="/agent" element={<LocationStateProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "带当前页面到 MOSS Chat" }));

    expect(await screen.findByTestId("handoff-location-state")).toHaveTextContent(
      '"page_id":"dashboard"',
    );
    expect(screen.getByTestId("handoff-location-state")).toHaveTextContent(
      '"report_date":"2026-08-20"',
    );
    expect(screen.getByTestId("handoff-location-state")).toHaveTextContent(
      '"allow_partial":false',
    );
    expect(screen.getByTestId("handoff-location-state")).toHaveTextContent(
      '"data_status":"formal"',
    );
  });
});
