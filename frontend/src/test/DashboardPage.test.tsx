import { useState, type ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";

function renderDashboard(client?: ApiClient) {
  if (!client) {
    return renderWorkbenchApp(["/"]);
  }

  const router = createWorkbenchMemoryRouter(["/"]);

  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <RouterProvider router={router} future={routerFuture} />
    </Wrapper>,
  );
}

describe("DashboardPage", () => {
  it("renders dashboard chrome while overview query is unresolved", async () => {
    const base = createApiClient({ mode: "mock" });
    let releaseOverview: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      getOverview: async () => {
        await new Promise<void>((resolve) => {
          releaseOverview = resolve;
        });
        return base.getOverview();
      },
    };

    renderDashboard(slowClient);

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseOverview).toBeDefined();
    });
    releaseOverview?.();
    expect(await screen.findAllByText(/MOSS/i)).not.toHaveLength(0);
  });

  it("renders dashboard shell after queries settle", async () => {
    renderDashboard();

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(await screen.findAllByText(/MOSS/i)).not.toHaveLength(0);
  });
});
