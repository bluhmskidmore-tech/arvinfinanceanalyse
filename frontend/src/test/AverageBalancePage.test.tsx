import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  it("renders a thin analytical entry shell before opening the full ADB view", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole("heading", { name: "ADB Analytical View" })).toBeInTheDocument();
    expect(screen.getByText("ADB 是 balance-analysis 的 analytical 子视图。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "进入正式资产负债分析" })).toHaveAttribute(
      "href",
      "/balance-analysis",
    );
    expect(screen.queryByTestId("average-balance-page")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开完整 ADB analytical 视图" }));

    expect(await screen.findByTestId("average-balance-page")).toBeInTheDocument();
  });
});
