import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-attribution-echarts-stub" />,
}));

describe("PnlAttributionPage", () => {
  it("mounts and switches tabs", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <PnlAttributionPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("pnl-attribution-page-title")).toHaveTextContent("损益归因分析");
    expect(screen.getByTestId("pnl-attribution-workbench-lead")).toHaveTextContent("归因分析工作台");
    expect(screen.getByTestId("pnl-attribution-workbench-lead")).toHaveTextContent("不在前端补算正式损益");
    expect(screen.getByTestId("pnl-attribution-current-view-lead")).toHaveTextContent("当前归因视图");

    await user.click(screen.getByRole("button", { name: "TPL 市场相关性" }));
    expect(screen.getByRole("button", { name: "TPL 市场相关性" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "损益构成" }));
    await user.click(screen.getByRole("button", { name: "高级归因 + Campisi" }));
    await user.click(screen.getByRole("button", { name: "规模 / 利率效应" }));
  });
});
