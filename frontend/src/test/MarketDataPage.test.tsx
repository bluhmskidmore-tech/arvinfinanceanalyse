import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
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
  it("renders macro catalog plus trend and lineage evidence from the API client contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const foundationMeta: ResultMeta = {
      trace_id: "tr_macro_foundation_test",
      basis: "analytical",
      result_kind: "preview.macro-foundation",
      formal_use_allowed: false,
      source_version: "sv_macro_vendor_test",
      vendor_version: "vv_choice_catalog_v1",
      rule_version: "rv_phase1_macro_vendor_v1",
      cache_version: "cv_phase1_macro_vendor_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:00:00Z",
    };
    const latestMeta: ResultMeta = {
      trace_id: "tr_choice_macro_latest_test",
      basis: "analytical",
      result_kind: "macro.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_macro_latest_test",
      vendor_version: "vv_choice_macro_20260410",
      rule_version: "rv_choice_macro_thin_slice_v1",
      cache_version: "cv_choice_macro_thin_slice_v1",
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:05:00Z",
    };
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: foundationMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
          {
            series_id: "M002",
            series_name: "DR007",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
          },
          {
            series_id: "M003",
            series_name: "RMB Index",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: latestMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
            quality_flag: "ok" as const,
            latest_change: 0.2,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.75,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "ok" as const,
              },
              {
                trade_date: "2026-04-09",
                value_numeric: 1.55,
                source_version: "sv_choice_macro_prev_test",
                vendor_version: "vv_choice_macro_20260409",
                quality_flag: "ok" as const,
              },
            ],
          },
          {
            series_id: "M002",
            series_name: "DR007",
            trade_date: "2026-04-10",
            value_numeric: 1.83,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
            quality_flag: "warning" as const,
            latest_change: null,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.83,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "warning" as const,
              },
            ],
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
    });

    expect(await screen.findAllByText("Open Market 7D Reverse Repo")).toHaveLength(2);
    expect(screen.getAllByText("DR007")).toHaveLength(2);
    expect(screen.getByTestId("market-data-catalog-count")).toHaveTextContent("3");
    expect(screen.getByTestId("market-data-stable-count")).toHaveTextContent("1 / 2");
    expect(screen.getByTestId("market-data-fallback-count")).toHaveTextContent("1");
    expect(screen.getByTestId("market-data-stable-trade-date")).toHaveTextContent(
      "2026-04-10",
    );
    expect(screen.getByTestId("market-data-missing-stable-count")).toHaveTextContent("1");
    expect(screen.getByText("待补齐 stable")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-missing-stable-section")).getByText("RMB Index"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("market-data-result-meta")).toHaveTextContent(
      "tr_choice_macro_latest_test",
    );
    expect(screen.getByText("稳定主链路")).toBeInTheDocument();
    expect(screen.getByText("降级 latest-only")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("tier stable");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("date_slice / batch");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("main refresh date-slice lane");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("+0.20 %");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("2026-04-09");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("tier fallback");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("latest / single");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("low-frequency latest-only lane");

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });
});


