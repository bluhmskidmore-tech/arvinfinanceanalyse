import { type PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { createApiClient, ApiClientProvider } from "../../../api/client";
import type { MacroVendorPayload, ChoiceMacroLatestPayload } from "../../../api/contracts";
import { buildMockApiEnvelope } from "../../../mocks/mockApiEnvelope";
import { useMarketDataPageData } from "./useMarketDataPageData";

it("does not start linkage reads after unmount during the preceding refresh reads", async () => {
  const client = createApiClient({ mode: "mock" });
  const foundation = buildMockApiEnvelope<MacroVendorPayload>("synthetic.foundation", {
    series: [], read_target: "duckdb",
  });
  vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue(buildMockApiEnvelope<ChoiceMacroLatestPayload>("synthetic.latest", {
    read_target: "duckdb",
    series: [{
      series_id: "test", series_name: "Synthetic", trade_date: "2026-06-30",
      value_numeric: 1, unit: "%", source_version: "synthetic-source",
      vendor_version: "synthetic-vendor", recent_points: [],
    }],
  }));
  let release!: () => void;
  const pending = new Promise<typeof foundation>((resolve) => { release = () => resolve(foundation); });
  const foundationRead = vi.spyOn(client, "getMacroFoundation").mockResolvedValueOnce(foundation).mockReturnValue(pending);
  vi.spyOn(client, "refreshChoiceMacro").mockResolvedValue({ status: "completed", run_id: "macro-complete" });
  const linkage = vi.spyOn(client, "getMacroBondLinkageAnalysis");
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={queryClient}><ApiClientProvider client={client}>{children}</ApiClientProvider></QueryClientProvider>;
  const { result, unmount } = renderHook(() => useMarketDataPageData(), { wrapper });
  await waitFor(() => expect(result.current.catalogQuery.isSuccess).toBe(true));
  let work!: Promise<void>;
  act(() => { work = result.current.handleRefresh(); });
  await waitFor(() => expect(foundationRead).toHaveBeenCalledTimes(2));
  unmount();
  await act(async () => { release(); await work; });
  expect(linkage).not.toHaveBeenCalled();
  queryClient.clear();
});
