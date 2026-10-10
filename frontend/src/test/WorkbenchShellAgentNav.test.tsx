import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.stubEnv("VITE_MOSS_AGENT_FRONTEND_ENABLED", "true");

describe("WorkbenchShell agent navigation highlight", () => {
  afterEach(() => {
    vi.resetModules();
  });

  it("highlights only the dedicated MOSS Chat entry on /agent, not its parent group", async () => {
    vi.resetModules();
    const [{ WorkbenchShell }, { renderWorkbenchApp }] = await Promise.all([
      import("../layouts/WorkbenchShell"),
      import("./renderWorkbenchApp"),
    ]);

    renderWorkbenchApp(["/agent"], {
      routes: [
        {
          path: "/",
          element: <WorkbenchShell />,
          children: [{ path: "agent", element: <div>agent body</div> }],
        },
      ],
    });

    expect(await screen.findByText("agent body")).toBeInTheDocument();

    const agentNav = screen.getByTestId("workbench-agent-nav");
    expect(
      within(agentNav).getByRole("link", { name: /MOSS Chat/ }),
    ).toHaveAttribute("data-active", "true");
    expect(within(agentNav).getByText("受控试用")).toBeInTheDocument();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
    expect(screen.queryByText("一期状态")).not.toBeInTheDocument();

    const groupNav = screen.getByTestId("workbench-group-nav");
    for (const link of within(groupNav).getAllByRole("link")) {
      expect(link).toHaveAttribute("data-active", "false");
    }
  });
});
