import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { DashboardMacroSpotSection } from "../features/executive-dashboard/components/DashboardMacroSpotSection";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_dashboard_macro_spot_priority_test",
    basis: "analytical",
    result_kind: "macro.choice.latest",
    formal_use_allowed: false,
    source_version: "sv_choice_macro_test",
    vendor_version: "vv_choice_macro_test",
    rule_version: "rv_choice_macro_test",
    cache_version: "cv_choice_macro_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-22T00:00:00Z",
    ...overrides,
  };
}

function renderSection(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <DashboardMacroSpotSection />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("DashboardMacroSpotSection priorities", () => {
  it("keeps the home-page macro lanes ahead of supplemental cross-asset rows", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta(),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "CA.BRENT",
              series_name: "Brent spot price",
              trade_date: "2026-04-13",
              value_numeric: 123.28,
              frequency: "daily",
              unit: "USD/bbl",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "supplemental lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "CA.DR007",
              series_name: "DR007 fallback",
              trade_date: "2026-04-21",
              value_numeric: 1.32,
              frequency: "daily",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "CA.STEEL",
              series_name: "Steel price",
              trade_date: "2026-04-20",
              value_numeric: 8500,
              frequency: "daily",
              unit: "CNY/t",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "supplemental lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "E1000180",
              series_name: "China 10Y",
              trade_date: "2026-04-20",
              value_numeric: 1.94,
              frequency: "daily",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "EMG00001310",
              series_name: "US 10Y",
              trade_date: "2026-04-20",
              value_numeric: 4.1,
              frequency: "daily",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "EM1",
              series_name: "CN-US 10Y spread",
              trade_date: "2026-04-20",
              value_numeric: -210,
              frequency: "daily",
              unit: "bp",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "M001",
              series_name: "OMO 7D",
              trade_date: "2026-04-21",
              value_numeric: 1.4,
              frequency: "daily",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "M003",
              series_name: "CN Gov 1Y",
              trade_date: "2026-04-21",
              value_numeric: 1.56,
              frequency: "daily",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "batch" as const,
              policy_note: "preferred lane",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
          ],
        },
      }),
    } satisfies ApiClient;

    renderSection(client);

    const grid = await screen.findByTestId("dashboard-macro-spot-grid");
    await waitFor(() => {
      expect(grid.querySelectorAll("article")).toHaveLength(6);
    });

    expect(within(grid).getByText("OMO 7D")).toBeInTheDocument();
    expect(within(grid).getByText("CN Gov 1Y")).toBeInTheDocument();
    expect(within(grid).queryByText("Brent spot price")).not.toBeInTheDocument();
    expect(within(grid).queryByText("Steel price")).not.toBeInTheDocument();
  });
});
