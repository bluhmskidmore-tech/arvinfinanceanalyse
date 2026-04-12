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
          { path: "pnl", element: <div>pnl body</div> },
          { path: "platform-config", element: <div>platform body</div> },
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
    renderShellAt("/platform-config");

    expect(await screen.findByTestId("workbench-readiness-banner")).toBeInTheDocument();
    expect(screen.getByText("当前页面仍是占位壳层")).toBeInTheDocument();
    expect(screen.getByText("platform body")).toBeInTheDocument();
  });
});
