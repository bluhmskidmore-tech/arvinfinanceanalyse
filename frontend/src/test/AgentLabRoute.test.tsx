import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentLabRoute } from "../router/AgentLabRoute";

vi.mock("../features/agent-lab/AgentLabPage", () => ({
  default: () => <section data-testid="agent-lab-page">Agent Lab</section>,
}));

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/agent-lab"]}>
      <Suspense fallback={<span>loading</span>}>
        <AgentLabRoute />
      </Suspense>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("AgentLabRoute", () => {
  it("keeps the hidden lab closed without the Agent development opt-in", async () => {
    renderRoute();

    expect(await screen.findByTestId("workbench-not-found-page")).toHaveTextContent("/agent-lab");
    expect(screen.queryByTestId("agent-lab-page")).not.toBeInTheDocument();
  });

  it("opens the hidden lab with the explicit development opt-in", async () => {
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

    renderRoute();

    expect(await screen.findByTestId("agent-lab-page")).toBeInTheDocument();
  });

  it("keeps the lab closed in production even when the flag is set", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

    renderRoute();

    expect(await screen.findByTestId("workbench-not-found-page")).toHaveTextContent("/agent-lab");
    expect(screen.queryByTestId("agent-lab-page")).not.toBeInTheDocument();
  });
});
