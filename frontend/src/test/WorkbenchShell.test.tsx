import { screen, within } from "@testing-library/react";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import { primaryWorkbenchNavigation } from "../mocks/navigation";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function renderShellAt(path: string) {
  return renderWorkbenchApp([path], {
    routes: [
      {
        path: "/",
        element: <WorkbenchShell />,
        children: [{ index: true, element: <div>shell body</div> }],
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
});
