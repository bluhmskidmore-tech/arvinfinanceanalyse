import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ApiEnvelope, RatingStatsResponse } from "../api/contracts";
import RatingDistributionCard from "../features/positions/components/RatingDistributionCard";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="positions-echarts-stub" />,
}));

function renderCard(weightedRate: string | null) {
  const client = createApiClient({ mode: "mock" });
  const response: ApiEnvelope<RatingStatsResponse> = {
    result_meta: {
      trace_id: "tr_positions_rating_test",
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_test",
      vendor_version: "vv_test",
      rule_version: "rv_test",
      cache_version: "cv_test",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-01-02T00:00:00Z",
      result_kind: "positions.stats.rating",
    },
    result: {
      start_date: "2026-01-01",
      end_date: "2026-01-02",
      num_days: 2,
      total_amount: "200000000",
      total_avg_daily: "100000000",
      items: [
        {
          rating: "AAA",
          total_amount: "200000000",
          avg_daily_balance: "100000000",
          weighted_rate: weightedRate,
          bond_count: 1,
          percentage: "100.00000000",
        },
      ],
    },
  };
  client.getPositionsStatsRating = vi.fn(async () => response);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RatingDistributionCard startDate="2026-01-01" endDate="2026-01-02" />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("RatingDistributionCard", () => {
  it("renders normalized rating yield as percent", async () => {
    renderCard("0.0325");

    expect(await screen.findByText("评级收益率")).toBeInTheDocument();
    expect(await screen.findByText("2 天 · 利率债默认 AAA")).toBeInTheDocument();
    expect(await screen.findByText("3.25%")).toBeInTheDocument();
  });

  it("keeps missing rating yield visually distinct from zero", async () => {
    renderCard(null);

    expect(await screen.findByText("评级收益率")).toBeInTheDocument();
    expect(await screen.findByText("2 天 · 利率债默认 AAA")).toBeInTheDocument();
    expect(screen.getByText("-")).toBeInTheDocument();
  });
});
