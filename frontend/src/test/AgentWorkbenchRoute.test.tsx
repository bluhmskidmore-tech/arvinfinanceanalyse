import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/agent/AgentWorkbenchPage", () => ({
  default: ({ pageContext }: { pageContext?: unknown }) => (
    <output data-testid="agent-route-page-context">
      {pageContext ? JSON.stringify(pageContext) : "contextless"}
    </output>
  ),
}));

import { AgentWorkbenchRoute } from "../router/AgentWorkbenchRoute";

function renderAgentRoute(state?: unknown) {
  render(
    <MemoryRouter initialEntries={[{ pathname: "/agent", state }]}>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/agent" element={<AgentWorkbenchRoute />} />
        </Routes>
      </Suspense>
    </MemoryRouter>,
  );
}

describe("AgentWorkbenchRoute page-context handoff", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("opens the workbench in production with the explicit release flag", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

    renderAgentRoute();

    expect(await screen.findByTestId("agent-route-page-context")).toHaveTextContent("contextless");
    expect(screen.queryByTestId("workbench-not-found-page")).not.toBeInTheDocument();
  });

  it.each([undefined, "false"])("keeps the production route closed when the flag is %s", async (flag) => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", flag);

    renderAgentRoute();

    expect(await screen.findByTestId("workbench-not-found-page")).toHaveTextContent("/agent");
    expect(screen.queryByTestId("agent-route-page-context")).not.toBeInTheDocument();
  });

  it("passes a validated Dashboard context from router state to the workbench", async () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");
    renderAgentRoute({
      agentPageContext: {
        page_id: "dashboard",
        current_filters: {
          report_date: "2026-08-20",
          allow_partial: false,
          data_status: "formal",
        },
        selected_rows: [],
        context_note: "dashboard-home 组合经营日报观察上下文",
      },
    });

    expect(await screen.findByTestId("agent-route-page-context")).toHaveTextContent(
      '"page_id":"dashboard"',
    );
    expect(screen.getByTestId("agent-route-page-context")).toHaveTextContent(
      '"report_date":"2026-08-20"',
    );
  });

  it.each([
    undefined,
    {},
    { agentPageContext: { page_id: "dashboard" } },
    {
      agentPageContext: {
        page_id: "dashboard",
        current_filters: {},
        selected_rows: ["forged-row"],
      },
    },
  ])("falls back to an explicit contextless workbench for invalid state %#", async (state) => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");
    renderAgentRoute(state);

    expect(await screen.findByTestId("agent-route-page-context")).toHaveTextContent("contextless");
  });
});
