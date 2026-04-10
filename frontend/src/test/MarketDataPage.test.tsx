import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import MarketDataPage from "../features/market-data/pages/MarketDataPage";

function renderPage(client: ApiClient) {
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
      <MarketDataPage />
    </Wrapper>,
  );
}

describe("MarketDataPage", () => {
  it("renders macro catalog and latest choice series from the API client contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_macro_foundation_test",
        basis: "analytical" as const,
        result_kind: "preview.macro-foundation",
        formal_use_allowed: false,
        source_version: "sv_macro_vendor_test",
        vendor_version: "vv_choice_catalog_v1",
        rule_version: "rv_phase1_macro_vendor_v1",
        cache_version: "cv_phase1_macro_vendor_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:00:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
          },
          {
            series_id: "M002",
            series_name: "DR007",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_choice_macro_latest_test",
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        source_version: "sv_choice_macro_latest_test",
        vendor_version: "vv_choice_macro_20260410",
        rule_version: "rv_choice_macro_thin_slice_v1",
        cache_version: "cv_choice_macro_thin_slice_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:05:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
          },
          {
            series_id: "M002",
            series_name: "DR007",
            trade_date: "2026-04-10",
            value_numeric: 1.83,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
    });

    expect(
      await screen.findByRole("heading", { name: "市场数据工作台" }),
    ).toBeInTheDocument();
    expect(await screen.findAllByText("公开市场7天逆回购利率")).toHaveLength(2);
    expect(screen.getAllByText("DR007")).toHaveLength(2);
    expect(screen.getByTestId("market-data-catalog-count")).toHaveTextContent("2");
    expect(screen.getByTestId("market-data-latest-count")).toHaveTextContent("2");
    expect(screen.getByTestId("market-data-latest-trade-date")).toHaveTextContent(
      "2026-04-10",
    );
    expect(screen.getByTestId("market-data-result-meta")).toHaveTextContent(
      "tr_choice_macro_latest_test",
    );

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });
});
