import { createElement, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import OperationsAnalysisPage from "../features/workbench/pages/OperationsAnalysisPage";

vi.mock("../features/workbench/business-analysis/RevenueCostBridge", () => ({
  RevenueCostBridge: () =>
    createElement("div", {
      "data-testid": "operations-revenue-bridge-stub",
    }),
}));

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
      <MemoryRouter future={routerFuture}>
        <OperationsAnalysisPage />
      </MemoryRouter>
    </Wrapper>,
  );
}

describe("OperationsAnalysisPage governed values", () => {
  it("uses governed overview values instead of fixed staged business metrics", async () => {
    const base = createApiClient({ mode: "mock" });

    renderPage({
      ...base,
      getSourceFoundation: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_source_governed",
          basis: "analytical" as const,
          result_kind: "preview.source-foundation",
          formal_use_allowed: false,
          source_version: "sv_source_governed",
          vendor_version: "vv_none",
          rule_version: "rv_source_preview_v1",
          cache_version: "cv_source_preview_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: {
          sources: [
            {
              ingest_batch_id: "batch-1",
              batch_created_at: "2026-04-10T09:00:00Z",
              source_family: "zqtz",
              report_date: "2026-01-31",
              source_file: "ZQTZ-20260131.xls",
              total_rows: 18,
              manual_review_count: 0,
              source_version: "sv_source_governed",
              rule_version: "rv_source_preview_v1",
              group_counts: {},
              preview_mode: "tabular",
            },
            {
              ingest_batch_id: "batch-2",
              batch_created_at: "2026-04-10T09:01:00Z",
              source_family: "tyw",
              report_date: "2026-01-31",
              source_file: "TYW-20260131.xls",
              total_rows: 6,
              manual_review_count: 0,
              source_version: "sv_source_governed",
              rule_version: "rv_source_preview_v1",
              group_counts: {},
              preview_mode: "tabular",
            },
          ],
        },
      })),
      getChoiceMacroLatest: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_macro_governed",
          basis: "analytical" as const,
          result_kind: "macro.choice.latest",
          formal_use_allowed: false,
          source_version: "sv_macro_governed",
          vendor_version: "vv_macro_governed",
          rule_version: "rv_choice_macro_thin_slice_v1",
          cache_version: "cv_choice_macro_thin_slice_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:03:00Z",
        },
        result: {
          read_target: "duckdb" as const,
          series: [
            {
              series_id: "M001",
              series_name: "DR007",
              trade_date: "2026-04-10",
              value_numeric: 1.82,
              unit: "%",
              frequency: "daily",
              source_version: "sv_macro_governed",
              vendor_version: "vv_macro_governed",
              quality_flag: "ok" as const,
            },
            {
              series_id: "M002",
              series_name: "10Y CGB",
              trade_date: "2026-04-10",
              value_numeric: 1.94,
              unit: "%",
              frequency: "daily",
              source_version: "sv_macro_governed",
              vendor_version: "vv_macro_governed",
              quality_flag: "ok" as const,
            },
          ],
        },
      })),
      getChoiceNewsEvents: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_news_governed",
          basis: "analytical" as const,
          result_kind: "news.choice.latest",
          formal_use_allowed: false,
          source_version: "sv_news_governed",
          vendor_version: "vv_none",
          rule_version: "rv_choice_news_v1",
          cache_version: "cv_choice_news_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:05:00Z",
        },
        result: {
          total_rows: 4,
          limit: 3,
          offset: 0,
          events: [],
        },
      })),
      getFxFormalStatus: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_fx_governed",
          basis: "formal" as const,
          result_kind: "fx.formal.status",
          formal_use_allowed: true,
          source_version: "sv_fx_governed",
          vendor_version: "vv_fx_governed",
          rule_version: "rv_fx_formal_mid_v1",
          cache_version: "cv_fx_formal_mid_v1",
          quality_flag: "warning" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:03:00Z",
        },
        result: {
          read_target: "duckdb" as const,
          vendor_priority: ["choice"],
          candidate_count: 5,
          materialized_count: 3,
          latest_trade_date: "2026-04-10",
          carry_forward_count: 1,
          rows: [
            {
              base_currency: "USD",
              quote_currency: "CNY",
              pair_label: "USD/CNY",
              series_id: "FX.USD.CNY",
              series_name: "USD/CNY",
              vendor_series_code: "USD/CNY",
              trade_date: "2026-04-10",
              observed_trade_date: "2026-04-10",
              mid_rate: 7.21,
              source_name: "fx_daily_mid",
              vendor_name: "choice",
              vendor_version: "vv_fx_governed",
              source_version: "sv_fx_governed",
              is_business_day: true,
              is_carry_forward: false,
              status: "ok" as const,
            },
            {
              base_currency: "EUR",
              quote_currency: "CNY",
              pair_label: "EUR/CNY",
              series_id: "FX.EUR.CNY",
              series_name: "EUR/CNY",
              vendor_series_code: "EUR/CNY",
              trade_date: null,
              observed_trade_date: null,
              mid_rate: null,
              source_name: null,
              vendor_name: null,
              vendor_version: null,
              source_version: null,
              is_business_day: null,
              is_carry_forward: null,
              status: "missing" as const,
            },
          ],
        },
      })),
      getBalanceAnalysisDates: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_balance_dates_governed",
          basis: "formal" as const,
          result_kind: "balance-analysis.dates",
          formal_use_allowed: true,
          source_version: "sv_balance_dates_governed",
          vendor_version: "vv_none",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal_materialize_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:07:00Z",
        },
        result: { report_dates: ["2026-01-31"] },
      })),
      getBalanceAnalysisOverview: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_balance_overview_governed",
          basis: "formal" as const,
          result_kind: "balance-analysis.overview",
          formal_use_allowed: true,
          source_version: "sv_balance_overview_governed",
          vendor_version: "vv_none",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal_materialize_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:08:00Z",
        },
        result: {
          report_date: "2026-01-31",
          position_scope: "all" as const,
          currency_basis: "CNY" as const,
          detail_row_count: 11,
          summary_row_count: 4,
          // API 金额为元；此处为「亿」量级的受治理示例值
          total_market_value_amount: (901.25 * 100_000_000).toFixed(2),
          total_amortized_cost_amount: (880.5 * 100_000_000).toFixed(2),
          total_accrued_interest_amount: (12.75 * 100_000_000).toFixed(2),
        },
      })),
      getBalanceAnalysisSummary: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_balance_summary_governed",
          basis: "formal" as const,
          result_kind: "balance-analysis.summary",
          formal_use_allowed: true,
          source_version: "sv_balance_summary_governed",
          vendor_version: "vv_none",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal_materialize_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:09:00Z",
        },
        result: {
          report_date: "2026-01-31",
          position_scope: "all" as const,
          currency_basis: "CNY" as const,
          limit: 6,
          offset: 0,
          total_rows: 1,
          rows: [],
        },
      })),
    });

    const cockpit = await screen.findByTestId("operations-business-kpis");
    await waitFor(() => {
      expect(cockpit).toHaveTextContent("901.25");
      expect(cockpit).toHaveTextContent("880.5");
      expect(cockpit).toHaveTextContent("12.75");
      expect(cockpit).toHaveTextContent("2");
      expect(cockpit).toHaveTextContent("4");
      expect(cockpit).not.toHaveTextContent("3,525.0");
    });

    const conclusionGrid = await screen.findByTestId("operations-conclusion-grid");
    await waitFor(() => {
      expect(conclusionGrid).toHaveTextContent("2026-01-31");
      expect(conclusionGrid).toHaveTextContent("11");
    });
  });
});
