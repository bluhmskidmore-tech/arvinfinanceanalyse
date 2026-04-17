import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import AverageBalancePage from "../features/average-balance/pages/AverageBalancePage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="average-balance-echarts-stub" />,
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={createApiClient({ mode: "mock" })}>
        <MemoryRouter>
          <AverageBalancePage />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("AverageBalancePage", () => {
  it("renders the full ADB analytical page directly when exposed as a live route", async () => {
    renderPage();

    expect(await screen.findByTestId("average-balance-page")).toBeInTheDocument();
    expect(screen.getByTestId("average-balance-page-title")).toHaveTextContent("日均管理");
    expect(screen.queryByRole("heading", { name: "ADB Analytical View" })).not.toBeInTheDocument();
  });
});
