import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import AverageBalanceView from "../features/average-balance/components/AverageBalanceView";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="average-balance-echarts-stub" />,
}));

describe("AverageBalanceView", () => {
  it("renders the ADB shell, tabs, and daily KPI cards", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <AverageBalanceView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "日均资产负债（ADB）" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日均分析" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "月度统计" })).toBeInTheDocument();
    expect(await screen.findByText("资产偏离度")).toBeInTheDocument();
    expect(screen.getByText("负债偏离度")).toBeInTheDocument();
    expect(screen.getByText("资产收益率")).toBeInTheDocument();
    expect(screen.getByText("负债付息率")).toBeInTheDocument();
  });
});
