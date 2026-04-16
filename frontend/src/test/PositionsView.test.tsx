import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import PositionsView from "../features/positions/components/PositionsView";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="positions-echarts-stub" />,
}));

describe("PositionsView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders shell, report date control, and bond tab", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByTestId("positions-page-title")).toHaveTextContent("持仓透视");
    expect(screen.getByText("持仓概览")).toBeInTheDocument();
    expect(
      await screen.findByRole("combobox", { name: "positions-report-date" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "债券持仓" })).toBeInTheDocument();
  });
});
