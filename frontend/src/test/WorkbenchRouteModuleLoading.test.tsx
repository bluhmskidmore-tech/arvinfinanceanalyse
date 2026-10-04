import { act, render, screen, waitFor } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { workbenchRoutes } from "../router/routes";

const loading = vi.hoisted(() => {
  let releaseTheme!: () => void;
  const themePending = new Promise<void>((resolve) => { releaseTheme = resolve; });
  return {
    themePending,
    releaseTheme,
    themeReady: false,
    releasePublication: () => {},
    pageModuleLoaded: vi.fn(),
    pageRendered: vi.fn(),
  };
});

vi.mock("../layouts/WorkbenchShell", () => ({ WorkbenchShell: () => <Outlet /> }));

vi.mock("../app/ThemedRouteBoundary", () => ({
  default: ({ children }: { children: ReactNode }) => {
    if (!loading.themeReady) throw loading.themePending;
    return children;
  },
}));

vi.mock("../router/SystemReadGenerationBoundary", () => ({
  SystemReadGenerationBoundary: ({ children }: { children: ReactNode }) => {
    const [ready, setReady] = useState(false);
    loading.releasePublication = () => setReady(true);
    return ready ? children : <div data-testid="publication-pending" />;
  },
}));

vi.mock("../features/balance-analysis/pages/BalanceAnalysisPage", () => {
  loading.pageModuleLoaded();
  return {
    default: () => {
      loading.pageRendered();
      return <div data-testid="balance-page" />;
    },
  };
});

describe("workbench route module loading", () => {
  it("starts the current page module before theme and publication finish without mounting it", async () => {
    const router = createMemoryRouter(workbenchRoutes, {
      initialEntries: ["/balance-analysis?report_date=2026-09-30"],
    });
    render(<RouterProvider router={router} />);

    await waitFor(() => expect(loading.pageModuleLoaded).toHaveBeenCalledTimes(1));
    expect(loading.pageRendered).not.toHaveBeenCalled();

    await act(async () => {
      loading.themeReady = true;
      loading.releaseTheme();
    });
    expect(await screen.findByTestId("publication-pending")).toBeInTheDocument();
    expect(loading.pageRendered).not.toHaveBeenCalled();

    await act(async () => loading.releasePublication());
    expect(await screen.findByTestId("balance-page")).toBeInTheDocument();
    expect(loading.pageModuleLoaded).toHaveBeenCalledTimes(1);
  });
});
