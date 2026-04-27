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
  it("mounts and exposes the detailed Campisi drill-down panels", async () => {
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

    expect(await screen.findByTestId("pnl-attribution-page-title")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-workbench-lead")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-current-view-lead")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-attribution-current-view-meta")).toHaveTextContent("当前期间");
    expect(screen.getByTestId("pnl-attribution-current-view-meta")).toHaveTextContent("2026-03");
    expect(screen.getByTestId("pnl-attribution-current-view-meta")).toHaveTextContent("2026-04-09T10:30:00Z");
    expect(screen.getByTestId("pnl-attribution-current-view-meta")).toHaveTextContent("正常");
    expect(screen.getByTestId("pnl-attribution-current-view-meta")).toHaveTextContent("未降级");

    await user.click(screen.getByRole("button", { name: /TPL/i }));
    expect(screen.getByRole("button", { name: /TPL/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Campisi/i }));

    expect(await screen.findByText("Campisi 四效应归因（组合）")).toBeInTheDocument();
    expect(screen.getByText("Campisi 六效应归因（扩展）")).toBeInTheDocument();
    expect(screen.getByText("Campisi 到期桶拆解")).toBeInTheDocument();
    expect(screen.getByTestId("pnl-attribution-advanced-view-meta")).toHaveTextContent("Carry / Roll-down");
    expect(screen.getByTestId("pnl-attribution-advanced-view-meta")).toHaveTextContent("利差归因");
    expect(screen.getByTestId("pnl-attribution-advanced-view-meta")).toHaveTextContent("KRD归因");
    expect(screen.getByTestId("pnl-attribution-advanced-view-meta")).toHaveTextContent("高级摘要");
  });
});
