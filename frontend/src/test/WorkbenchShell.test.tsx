import { screen, within } from "@testing-library/react";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  primaryWorkbenchNavigation,
  primaryWorkbenchNavigationGroups,
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
  it("renders shell chrome and grouped workspace navigation", async () => {
    renderShellAt("/");

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(screen.getByText("shell body")).toBeInTheDocument();
  });

  it("renders a smaller set of grouped workspaces than live route entries", async () => {
    renderShellAt("/");

    const navigation = await screen.findByTestId("workbench-group-nav");
    expect(within(navigation).getAllByRole("link")).toHaveLength(
      primaryWorkbenchNavigationGroups.length,
    );
    expect(primaryWorkbenchNavigationGroups.length).toBeLessThan(
      primaryWorkbenchNavigation.length,
    );
    expect(
      within(navigation).queryByRole("link", { name: "Agent Workbench" }),
    ).not.toBeInTheDocument();
  });

  it("shows current-group section links separately from the workspace groups", async () => {
    renderShellAt("/platform-config");

    const subnav = await screen.findByTestId("workbench-section-subnav");
    const hrefs = within(subnav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/platform-config"]);
    expect(hrefs).not.toContain("/cube-query");
    expect(hrefs).not.toContain("/reports");
  });

  it("renders a portfolio-specific decision surface when browsing the portfolio workbench", async () => {
    renderShellAt("/pnl");

    const lead = await screen.findByTestId("portfolio-workbench-lead");
    expect(lead).toHaveTextContent("组合状态先看错配，再看损益，最后定位仓位与归因");
    expect(lead).toHaveTextContent("资产负债分析");

    const flow = screen.getByTestId("portfolio-workbench-flow");
    expect(flow).toHaveTextContent("先看资产负债");
    expect(flow).toHaveTextContent("最后做原因解释");

    const board = screen.getByTestId("portfolio-workbench-board");
    expect(board).toHaveTextContent("状态判断");
    expect(board).toHaveTextContent("仓位与结构");
    expect(board).toHaveTextContent("原因解释");
    expect(board).toHaveTextContent("债券总览");
    expect(board).toHaveTextContent("持仓透视");
    expect(board).toHaveTextContent("损益桥接");
  });

  it("does not render the portfolio decision surface outside the portfolio group", async () => {
    renderShellAt("/platform-config");

    expect(await screen.findByText("platform body")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-lead")).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-workbench-board")).not.toBeInTheDocument();
  });

  it("renders the reserved modules section outside the grouped workspace nav", async () => {
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

  it("treats /dashboard as the dashboard section inside the current group subnav", async () => {
    renderShellAt("/dashboard");

    expect(await screen.findByText("dashboard alias body")).toBeInTheDocument();
    const subnav = screen.getByTestId("workbench-section-subnav");
    const dashLink = within(subnav)
      .getAllByRole("link")
      .find((candidate) => candidate.getAttribute("href") === "/");
    expect(dashLink).toBeDefined();
    expect(dashLink).toHaveAttribute("href", "/");
  });
});
