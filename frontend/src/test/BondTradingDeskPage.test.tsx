import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import BondTradingDeskPage from "../features/bond-trading-desk/pages/BondTradingDeskPage";
import { formatRawAsNumeric } from "../utils/format";

function resultMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
  };
}

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const years = (raw: number) => formatRawAsNumeric({ raw, unit: "years", sign_aware: false });

function renderPage(initialPath = "/bond-trading-desk?bond_code=230210.IB&report_date=2026-04-30") {
  const client = createApiClient({ mode: "mock" });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/bond-trading-desk" element={<BondTradingDeskPage />} />
          </Routes>
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("BondTradingDeskPage", () => {
  it("prompts for bond_code when missing", async () => {
    renderPage("/bond-trading-desk");

    expect(await screen.findByTestId("bond-trading-desk-page")).toBeInTheDocument();
    expect(screen.getByTestId("bond-trading-desk-missing-bond")).toBeInTheDocument();
  });

  it("shows conclusion when top holdings returns matching bond", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBondAnalyticsDates").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    vi.spyOn(client, "getBondAnalyticsTopHoldings").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.top_holdings"),
      result: {
        report_date: "2026-04-30",
        top_n: 500,
        items: [
          {
            instrument_code: "230210.IB",
            instrument_name: "23国开10",
            issuer_name: "国开行",
            rating: "AAA",
            asset_class: "rate",
            market_value: yuan(1_200_000_000),
            face_value: yuan(1_000_000_000),
            ytm: pct(2.45),
            modified_duration: years(4.2),
            weight: pct(3.5),
          },
        ],
        total_market_value: yuan(1_200_000_000),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getPositionsBondsList").mockResolvedValue({
      result_meta: resultMeta("positions.bonds.list"),
      result: { items: [], total: 0, page: 1, page_size: 500 },
    });
    vi.spyOn(client, "getCreditSpreadAnalysisDetail").mockResolvedValue({
      result_meta: resultMeta("credit_spread.analysis.detail"),
      result: {
        report_date: "2026-04-30",
        credit_bond_count: 0,
        total_credit_market_value: "0",
        weighted_avg_spread_bps: "0",
        spread_term_structure: [],
        top_spread_bonds: [],
        bottom_spread_bonds: [],
        historical_context: null,
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getBondAnalyticsPositionChanges").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.position_changes"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        top_n: 100,
        source_status: "empty",
        items: [],
        total_market_value: yuan(0),
        prev_total_market_value: yuan(0),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter
            initialEntries={["/bond-trading-desk?bond_code=230210.IB&report_date=2026-04-30"]}
          >
            <Routes>
              <Route path="/bond-trading-desk" element={<BondTradingDeskPage />} />
            </Routes>
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const conclusion = await screen.findByTestId("bond-trading-desk-conclusion");
    await waitFor(() => {
      expect(conclusion).toHaveTextContent("23国开10");
      expect(conclusion).toHaveTextContent("单券读面结论");
    });
    expect(screen.getByTestId("bond-trading-desk-identity")).toHaveTextContent("230210.IB");
    expect(screen.getByTestId("bond-trading-desk-gaps")).toBeInTheDocument();
  });

  it("shows empty state when bond not found in lookup scope", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBondAnalyticsDates").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    vi.spyOn(client, "getBondAnalyticsTopHoldings").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.top_holdings"),
      result: {
        report_date: "2026-04-30",
        top_n: 500,
        items: [],
        total_market_value: yuan(0),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getPositionsBondsList").mockResolvedValue({
      result_meta: resultMeta("positions.bonds.list"),
      result: { items: [], total: 0, page: 1, page_size: 500 },
    });
    vi.spyOn(client, "getCreditSpreadAnalysisDetail").mockResolvedValue({
      result_meta: resultMeta("credit_spread.analysis.detail"),
      result: {
        report_date: "2026-04-30",
        credit_bond_count: 0,
        total_credit_market_value: "0",
        weighted_avg_spread_bps: "0",
        spread_term_structure: [],
        top_spread_bonds: [],
        bottom_spread_bonds: [],
        historical_context: null,
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getBondAnalyticsPositionChanges").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.position_changes"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        top_n: 100,
        source_status: "empty",
        items: [],
        total_market_value: yuan(0),
        prev_total_market_value: yuan(0),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter
            initialEntries={["/bond-trading-desk?bond_code=999999.IB&report_date=2026-04-30"]}
          >
            <Routes>
              <Route path="/bond-trading-desk" element={<BondTradingDeskPage />} />
            </Routes>
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("bond-trading-desk-conclusion")).toBeInTheDocument();
    expect(screen.getByText("未在当前查找范围命中")).toBeInTheDocument();
    expect(screen.queryByText("待命中债券")).not.toBeInTheDocument();
  });

  it("keeps partial compose when one source fails", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getBondAnalyticsDates").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.dates"),
      result: { report_dates: ["2026-04-30"] },
    });
    vi.spyOn(client, "getPositionsBondsList").mockRejectedValue(new Error("positions down"));
    vi.spyOn(client, "getBondAnalyticsTopHoldings").mockResolvedValue({
      result_meta: {
        ...resultMeta("bond_analytics.top_holdings"),
        quality_flag: "warning",
        fallback_mode: "latest_snapshot",
      },
      result: {
        report_date: "2026-04-30",
        top_n: 500,
        items: [
          {
            instrument_code: "230210.IB",
            instrument_name: "23国开10",
            issuer_name: "国开行",
            rating: "AAA",
            asset_class: "rate",
            market_value: yuan(1_200_000_000),
            face_value: yuan(1_000_000_000),
            ytm: pct(2.45),
            modified_duration: years(4.2),
            weight: pct(3.5),
          },
        ],
        total_market_value: yuan(1_200_000_000),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getCreditSpreadAnalysisDetail").mockResolvedValue({
      result_meta: resultMeta("credit_spread.analysis.detail"),
      result: {
        report_date: "2026-04-30",
        credit_bond_count: 0,
        total_credit_market_value: "0",
        weighted_avg_spread_bps: "0",
        spread_term_structure: [],
        top_spread_bonds: [],
        bottom_spread_bonds: [],
        historical_context: null,
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });
    vi.spyOn(client, "getBondAnalyticsPositionChanges").mockResolvedValue({
      result_meta: resultMeta("bond_analytics.position_changes"),
      result: {
        report_date: "2026-04-30",
        prev_report_date: null,
        top_n: 100,
        source_status: "empty",
        items: [],
        total_market_value: yuan(0),
        prev_total_market_value: yuan(0),
        warnings: [],
        computed_at: "2026-04-30T00:00:00Z",
      },
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter
            initialEntries={["/bond-trading-desk?bond_code=230210.IB&report_date=2026-04-30"]}
          >
            <Routes>
              <Route path="/bond-trading-desk" element={<BondTradingDeskPage />} />
            </Routes>
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("bond-trading-desk-compose-strip")).toBeInTheDocument();
    expect(screen.getByTestId("bond-trading-desk-compose-positions")).toHaveTextContent("失败");
    expect(screen.getByTestId("bond-trading-desk-compose-top_holdings")).toHaveTextContent(
      "quality=warning",
    );
    expect(screen.getByTestId("bond-trading-desk-error")).toHaveTextContent("部分拼装来源失败");
    expect(screen.getByTestId("bond-trading-desk-conclusion")).toHaveTextContent("23国开10");
  });

  it("applies bond_code from input to URL", async () => {
    const user = userEvent.setup();
    renderPage("/bond-trading-desk?report_date=2026-04-30");

    const input = await screen.findByTestId("bond-trading-desk-bond-code");
    await user.clear(input);
    await user.type(input, "149001.SZ");
    await user.click(screen.getByTestId("bond-trading-desk-apply-bond"));

    await waitFor(() => {
      expect(screen.getByTestId("bond-trading-desk-identity")).toHaveTextContent("149001.SZ");
      expect(screen.queryByTestId("bond-trading-desk-missing-bond")).not.toBeInTheDocument();
    });
  });
});
