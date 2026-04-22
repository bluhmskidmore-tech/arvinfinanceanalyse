import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { DashboardMacroSpotSection } from "../features/executive-dashboard/components/DashboardMacroSpotSection";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_dashboard_macro_spot_index_test",
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

describe("DashboardMacroSpotSection index values", () => {
  it("keeps large index values in ratio display instead of guessing count formatting", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: async () => ({
        result_meta: createResultMeta(),
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "EMM01843735",
              series_name: "第一财经研究院中国金融条件指数(日)",
              trade_date: "2026-04-21",
              value_numeric: 3924.5,
              frequency: "daily",
              unit: "index",
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
          ],
        },
      }),
    } satisfies ApiClient;

    renderSection(client);

    const grid = await screen.findByTestId("dashboard-macro-spot-grid");
    const card = grid.querySelector("article") as HTMLElement;
    expect(within(card).getByText("第一财经研究院中国金融条件指数(日)")).toBeInTheDocument();
    expect(within(card).getByText("3924.5 index")).toBeInTheDocument();
  });
});
