import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WorkbenchRouteErrorBoundary } from "./WorkbenchRouteStatusPages";

describe("route asset failure recovery", () => {
  it("offers recovery at the same URL after a publication handshake timeout", async () => {
    const router = createMemoryRouter([{
      path: "/",
      loader: () => { throw new Error("Request timed out: /api/system-read-publication"); },
      element: <div>Home</div>,
      errorElement: <WorkbenchRouteErrorBoundary />,
    }], { initialEntries: ["/?report_date=2026-08-31"] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("link", { name: "重新加载当前页" }))
      .toHaveAttribute("href", "/?report_date=2026-08-31");
    expect(screen.getByRole("alert")).toHaveTextContent("页面加载失败");
    const diagnostic = screen.getByText("Request timed out: /api/system-read-publication");
    expect(diagnostic.closest("details")).not.toHaveAttribute("open");
    expect(diagnostic).not.toBeVisible();
    expect(screen.getByText("暂时无法打开页面，请重新加载。若仍未恢复，请联系系统支持。")).toBeVisible();
  });

  it("offers a document reload at the same URL for an obsolete chunk", async () => {
    const router = createMemoryRouter([{
      path: "/market-overview",
      loader: () => { throw new TypeError("Failed to fetch dynamically imported module: /assets/MarketHomePage-old.js"); },
      element: <div>Market</div>,
      errorElement: <WorkbenchRouteErrorBoundary />,
    }], { initialEntries: ["/market-overview?view=full#market-risk-observation"] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("link", { name: "重新加载当前页" }))
      .toHaveAttribute("href", "/market-overview?view=full#market-risk-observation");
    expect(screen.getByRole("alert")).toHaveTextContent("页面加载失败");
    const diagnostic = screen.getByText("Failed to fetch dynamically imported module: /assets/MarketHomePage-old.js");
    expect(diagnostic.closest("details")).not.toHaveAttribute("open");
    expect(diagnostic).not.toBeVisible();
  });
});
