import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { DashboardMacroSpotSection } from "../features/executive-dashboard/components/DashboardMacroSpotSection";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_dashboard_macro_spot_test",
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
    generated_at: "2026-04-21T00:00:00Z",
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

describe("DashboardMacroSpotSection", () => {
  it("hides placeholder and redundant fx units while keeping percent formatting", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta(),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "EMM00058124",
              series_name: "中间价:美元兑人民币",
              trade_date: "2026-04-10",
              value_numeric: 6.8654,
              frequency: "daily",
              unit: "CNY",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "stable" as const,
              fetch_mode: "date_slice" as const,
              fetch_granularity: "batch" as const,
              policy_note: "main refresh",
              quality_flag: "ok" as const,
              latest_change: null,
              recent_points: [],
            },
            {
              series_id: "EMM00008445",
              series_name: "工业增加值:当月同比",
              trade_date: "2025-12-01",
              value_numeric: 5.2,
              frequency: "monthly",
              unit: "%",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "fallback" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "single" as const,
              policy_note: "latest refresh",
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
      expect(grid.querySelectorAll("article")).toHaveLength(2);
    });

    const cards = grid.querySelectorAll("article");
    const fxCard = cards[0] as HTMLElement;
    const growthCard = cards[1] as HTMLElement;

    expect(within(fxCard).getByText("中间价:美元兑人民币")).toBeInTheDocument();
    expect(within(fxCard).getByText("6.865")).toBeInTheDocument();
    expect(within(fxCard).queryByText(/^CNY$/i)).not.toBeInTheDocument();
    expect(within(fxCard).queryByText(/^unknown$/i)).not.toBeInTheDocument();

    expect(within(growthCard).getByText("工业增加值:当月同比")).toBeInTheDocument();
    expect(within(growthCard).getByText("5.20%")).toBeInTheDocument();
  });
});

describe("DashboardMacroSpotSection GDP", () => {
  it("renders China GDP current value in trillion yuan for this card", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta(),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "EMM00000015",
              series_name: "中国:GDP:现价",
              trade_date: "2025-12-01",
              value_numeric: 1401879.2,
              frequency: "quarterly",
              unit: "亿元",
              source_version: "sv_choice_macro_test",
              vendor_version: "vv_choice_macro_test",
              refresh_tier: "fallback" as const,
              fetch_mode: "latest" as const,
              fetch_granularity: "single" as const,
              policy_note: "latest refresh",
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
    const card = grid.querySelector("article") as HTMLElement;
    expect(within(card).getByText("中国:GDP:现价")).toBeInTheDocument();
    expect(within(card).getByText("140.19 万亿元")).toBeInTheDocument();
  });
});
