import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { ApiClientProvider, createApiClient } from "../api/client";
import PnlAttributionPage from "../features/pnl-attribution/pages/PnlAttributionPage";

vi.mock("../lib/echarts", () => ({ default: () => <div /> }));

it.each([
  ["2026-08-31", "2026-07-31"],
  ["2026-04-30", "2026-03-31"],
  ["2026-02-28", "2026-01-31"],
  ["2024-02-29", "2024-01-31"],
  ["2026-01-31", "2025-12-31"],
])("requests the actual monthly Campisi baseline for %s", async (endDate, startDate) => {
  const user = userEvent.setup();
  const client = createApiClient({ mode: "mock" });
  const originalFormalDates = client.getFormalPnlDates;
  const originalProductDates = client.getProductCategoryDates;
  client.getFormalPnlDates = vi.fn(async () => ({
    ...(await originalFormalDates()),
    result: { report_dates: [endDate], formal_fi_report_dates: [endDate], nonstd_bridge_report_dates: [] },
  }));
  client.getProductCategoryDates = vi.fn(async () => ({
    ...(await originalProductDates()), result: { report_dates: [endDate] },
  }));
  const four = vi.spyOn(client, "getPnlCampisiFourEffects");
  const enhanced = vi.spyOn(client, "getPnlCampisiEnhanced");
  const buckets = vi.spyOn(client, "getPnlCampisiMaturityBuckets");
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}><PnlAttributionPage /></ApiClientProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
  await screen.findByTestId("pnl-attribution-current-view-meta");
  await user.click(screen.getByRole("button", { name: "高级归因 + Campisi" }));
  await waitFor(() => {
    for (const read of [four, enhanced, buckets]) {
      expect(read).toHaveBeenCalledWith({ startDate, endDate, lookbackDays: 30 });
    }
  });
});
