import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ApiEnvelope, BondTopHoldingsPayload, ResultMeta } from "../api/contracts";
import { TopHoldingsView } from "../features/bond-analytics/components/TopHoldingsView";
import { formatRawAsNumeric } from "../utils/format";

type GetBondAnalyticsTopHoldings = (
  reportDate: string,
  topN?: number,
) => Promise<ApiEnvelope<BondTopHoldingsPayload>>;

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

function topHoldingsEnvelope(
  topN: number,
  items: BondTopHoldingsPayload["items"] = [],
): ApiEnvelope<BondTopHoldingsPayload> {
  return {
    result_meta: resultMeta(),
    result: {
      report_date: "2026-03-31",
      top_n: topN,
      items,
      total_market_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
      warnings: [],
      computed_at: "2026-04-12T00:00:00Z",
    },
  };
}

function renderView(getTop: GetBondAnalyticsTopHoldings) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const client = { ...createApiClient({ mode: "mock" }), getBondAnalyticsTopHoldings: getTop };
  return render(
    <QueryClientProvider client={qc}>
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <TopHoldingsView reportDate="2026-03-31" />
        </MemoryRouter>
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

  it("renders holding market value and face value in yi yuan", async () => {
    const getTop = vi.fn(async (_d: string, topN?: number) =>
      topHoldingsEnvelope(topN ?? 20, [
        {
          instrument_code: "BOND-1",
          instrument_name: "测试债",
          issuer_name: "发行人A",
          rating: "AAA",
          asset_class: "Rate",
          market_value: formatRawAsNumeric({ raw: 120_000_000, unit: "yuan", sign_aware: false }),
          face_value: formatRawAsNumeric({ raw: 100_000_000, unit: "yuan", sign_aware: false }),
          ytm: formatRawAsNumeric({ raw: 0.025, unit: "pct", sign_aware: false }),
          modified_duration: formatRawAsNumeric({ raw: 3.2, unit: "ratio", sign_aware: false }),
          weight: formatRawAsNumeric({ raw: 0.1, unit: "ratio", sign_aware: false }),
        },
      ]),
    );

    renderView(getTop);

    expect(await screen.findByText("测试债")).toBeInTheDocument();
    expect(screen.getByText("1.20 亿")).toBeInTheDocument();
    expect(screen.getByText("1.00 亿")).toBeInTheDocument();
  });

  it("shows unmodelled fund duration separately from a true matured zero", async () => {
    const getTop = vi.fn(async (_d: string, topN?: number) =>
      topHoldingsEnvelope(topN ?? 20, [
        {
          instrument_code: "SA-FUND",
          instrument_name: "测试基金",
          issuer_name: null,
          rating: null,
          asset_class: "other",
          market_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          face_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          ytm: formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: false }),
          modified_duration: null,
          duration_quality_flag: "maturity_unavailable",
          maturity_category: "fund_no_maturity",
          weight: formatRawAsNumeric({ raw: 0.5, unit: "ratio", sign_aware: false }),
        },
        {
          instrument_code: "BOND-MATURED",
          instrument_name: "已到期债券",
          issuer_name: null,
          rating: null,
          asset_class: "rate",
          market_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          face_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          ytm: formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: false }),
          modified_duration: "0.00000000",
          duration_quality_flag: "no_remaining_term",
          maturity_category: "<=30d",
          weight: formatRawAsNumeric({ raw: 0.5, unit: "ratio", sign_aware: false }),
        },
        {
          instrument_code: "BOND-VALID",
          instrument_name: "正常债券",
          issuer_name: null,
          rating: null,
          asset_class: "rate",
          market_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          face_value: formatRawAsNumeric({ raw: 100, unit: "yuan", sign_aware: false }),
          ytm: formatRawAsNumeric({ raw: 0, unit: "pct", sign_aware: false }),
          modified_duration: "2.50000000",
          duration_quality_flag: "observed",
          maturity_category: "1-3y",
          weight: formatRawAsNumeric({ raw: 0.5, unit: "ratio", sign_aware: false }),
        },
      ]),
    );
    renderView(getTop);

    expect(await screen.findByText("测试基金")).toBeInTheDocument();
    expect(screen.getByText(/基金未列固定到期日，底层久期未覆盖/)).toBeInTheDocument();
    expect(screen.getByText("已到期债券")).toBeInTheDocument();
    expect(screen.getByText("0.00000000")).toBeInTheDocument();
    expect(screen.getByText("2.50000000")).toBeInTheDocument();
  });

  it("links each holding row to the bond trading desk", async () => {
    const getTop = vi.fn(async (_d: string, topN?: number) =>
      topHoldingsEnvelope(topN ?? 20, [
        {
          instrument_code: "BOND-1",
          instrument_name: "测试债",
          issuer_name: "发行人A",
          rating: "AAA",
          asset_class: "Rate",
          market_value: formatRawAsNumeric({ raw: 120_000_000, unit: "yuan", sign_aware: false }),
          face_value: formatRawAsNumeric({ raw: 100_000_000, unit: "yuan", sign_aware: false }),
          ytm: formatRawAsNumeric({ raw: 0.025, unit: "pct", sign_aware: false }),
          modified_duration: formatRawAsNumeric({ raw: 3.2, unit: "ratio", sign_aware: false }),
          weight: formatRawAsNumeric({ raw: 0.1, unit: "ratio", sign_aware: false }),
        },
      ]),
    );

    renderView(getTop);

    const link = await screen.findByTestId("bond-trading-desk-link-BOND-1");
    expect(link).toHaveAttribute(
      "href",
      "/bond-trading-desk?bond_code=BOND-1&report_date=2026-03-31",
    );
  });
});
