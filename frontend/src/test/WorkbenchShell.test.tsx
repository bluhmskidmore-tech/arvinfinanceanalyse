import { screen, within } from "@testing-library/react";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  primaryWorkbenchNavigation,
  secondaryWorkbenchNavigation,
} from "../mocks/navigation";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function renderShellAt(path: string) {
  return renderWorkbenchApp([path], {
    routes: [
      {
        path: "/",
        element: <WorkbenchShell />,
        children: [
          { index: true, element: <div>shell body</div> },
          { path: "dashboard", element: <div>dashboard alias body</div> },
          { path: "pnl", element: <div>pnl body</div> },
          { path: "platform-config", element: <div>platform body</div> },
          { path: "agent", element: <div>agent body</div> },
        ],
      },
    ],
  });
}

describe("WorkbenchShell", () => {
  it("renders shell chrome and primary navigation", async () => {
    renderShellAt("/");

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByText("shell body")).toBeInTheDocument();
  });

  it("keeps the primary navigation aligned with the visible navigation baseline", async () => {
    renderShellAt("/");

    const navigation = await screen.findByRole("navigation");
    expect(within(navigation).getAllByRole("link")).toHaveLength(
      primaryWorkbenchNavigation.length,
    );
    expect(
      within(navigation).queryByRole("link", { name: "Agent Workbench" }),
    ).not.toBeInTheDocument();
  });

  it("renders the reserved modules section outside the primary navigation", async () => {
    renderShellAt("/");

    expect(await screen.findByText("Reserved Modules")).toBeInTheDocument();
    for (const section of secondaryWorkbenchNavigation) {
      const link = screen
        .getAllByRole("link")
        .find((candidate) => candidate.getAttribute("href") === section.path);

      expect(link).toBeDefined();
      expect(link).toHaveTextContent(section.label);
    }
  });

  it("shows a readiness banner for gated routes", async () => {
    renderShellAt("/agent");

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(screen.getByText("当前页面尚未物化真实数据链路")).toBeInTheDocument();
    expect(screen.getByText("agent body")).toBeInTheDocument();
  });

  it("treats /dashboard as the dashboard section for nav highlighting", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    const navigation = screen.getByRole("navigation");
    const dashLink = within(navigation).getByRole("link", { name: /驾驶舱/ });
    expect(dashLink).toHaveAttribute("href", "/");
  });
});
