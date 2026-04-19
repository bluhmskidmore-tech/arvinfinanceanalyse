import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ApiEnvelope, BondTopHoldingsPayload, ResultMeta } from "../api/contracts";
import { TopHoldingsView } from "../features/bond-analytics/components/TopHoldingsView";
import { formatRawAsNumeric } from "../utils/format";

const resultMeta = (): ResultMeta => ({
  trace_id: "tr",
  basis: "formal",
  result_kind: "bond_analytics.top_holdings",
  formal_use_allowed: true,
  source_version: "sv",
  vendor_version: "vv",
  rule_version: "rv",
  cache_version: "cv",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-12T00:00:00Z",
});

function topHoldingsEnvelope(topN: number): ApiEnvelope<BondTopHoldingsPayload> {
  return {
    result_meta: resultMeta(),
    result: {
      report_date: "2026-03-31",
      top_n: topN,
      items: [],
      total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
      warnings: [],
      computed_at: "2026-04-12T00:00:00Z",
    },
  };
}

function renderView(getTop: ReturnType<typeof vi.fn>) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const client = { ...createApiClient({ mode: "mock" }), getBondAnalyticsTopHoldings: getTop };
  return render(
    <QueryClientProvider client={qc}>
      <ApiClientProvider client={client}>
        <TopHoldingsView reportDate="2026-03-31" />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("TopHoldingsView", () => {
  it("在 loading 且尚无数据时仍渲染 TopN 工具栏", async () => {
    const pending = new Promise<ApiEnvelope<BondTopHoldingsPayload>>(() => {});
    renderView(vi.fn(() => pending));
    expect(await screen.findByText("展示条数")).toBeInTheDocument();
    expect(screen.getByTestId("bond-analytics-top-holdings-topn")).toBeInTheDocument();
    expect(screen.getByTestId("top-holdings-loading")).toBeInTheDocument();
  });

  it("TopN 默认值为 20", async () => {
    const getTop = vi.fn(async (_d: string, topN?: number) => topHoldingsEnvelope(topN ?? 20));
    renderView(getTop);
    await waitFor(() => expect(getTop).toHaveBeenCalledWith("2026-03-31", 20));
    expect((screen.getByTestId("bond-analytics-top-holdings-topn") as HTMLSelectElement).value).toBe(
      "20",
    );
  });

  it("切换到 50 会再次请求 TopHoldings", async () => {
    const user = userEvent.setup();
    const getTop = vi.fn(async (_d: string, topN?: number) => topHoldingsEnvelope(topN ?? 20));
    renderView(getTop);
    await waitFor(() => expect(getTop).toHaveBeenCalledTimes(1));
    await user.selectOptions(screen.getByTestId("bond-analytics-top-holdings-topn"), "50");
    await waitFor(() => expect(getTop).toHaveBeenCalledTimes(2));
    expect(getTop.mock.calls[0]).toEqual(["2026-03-31", 20]);
    expect(getTop.mock.calls[1]).toEqual(["2026-03-31", 50]);
  });
});
