import { createElement, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ProductCategoryPnlRow } from "../api/contracts";
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
  function productCategoryRow(
    partial: Partial<ProductCategoryPnlRow> &
      Pick<ProductCategoryPnlRow, "category_id" | "category_name" | "side" | "business_net_income">,
  ): ProductCategoryPnlRow {
    return {
      category_id: partial.category_id,
      category_name: partial.category_name,
      side: partial.side,
      level: partial.level ?? 0,
      view: partial.view ?? "monthly",
      report_date: partial.report_date ?? "2026-02-28",
      baseline_ftp_rate_pct: partial.baseline_ftp_rate_pct ?? "1.75",
      cnx_scale: partial.cnx_scale ?? "0",
      cny_scale: partial.cny_scale ?? "0",
      foreign_scale: partial.foreign_scale ?? "0",
      cnx_cash: partial.cnx_cash ?? "0",
      cny_cash: partial.cny_cash ?? "0",
      foreign_cash: partial.foreign_cash ?? "0",
      cny_ftp: partial.cny_ftp ?? "0",
      foreign_ftp: partial.foreign_ftp ?? "0",
      cny_net: partial.cny_net ?? partial.business_net_income,
      foreign_net: partial.foreign_net ?? "0",
      business_net_income: partial.business_net_income,
      weighted_yield: partial.weighted_yield ?? null,
      is_total: partial.is_total ?? false,
      children: partial.children ?? [],
      scenario_rate_pct: partial.scenario_rate_pct ?? null,
    };
  }

  it("uses product-category PnL formal values instead of balance overview values for the operating caliber", async () => {
    const base = createApiClient({ mode: "mock" });
    const assetTotal = productCategoryRow({
      category_id: "asset_total",
      category_name: "资产合计",
      side: "asset",
      business_net_income: "420000000",
      is_total: true,
    });
    const liabilityTotal = productCategoryRow({
      category_id: "liability_total",
      category_name: "负债合计",
      side: "liability",
      business_net_income: "-130000000",
      is_total: true,
    });
    const grandTotal = productCategoryRow({
      category_id: "grand_total",
      category_name: "合计",
      side: "total",
      business_net_income: "290000000",
      is_total: true,
    });
    const bondInvestment = productCategoryRow({
      category_id: "bond_investment",
      category_name: "债券投资",
      side: "asset",
      business_net_income: "260000000",
      cnx_scale: "336178000000",
      cny_cash: "662000000",
      cny_ftp: "444000000",
      cny_net: "218000000",
      foreign_net: "42000000",
      weighted_yield: "2.63",
      children: ["bond_tpl", "bond_ac"],
    });
    const interbankDeposits = productCategoryRow({
      category_id: "interbank_deposits",
      category_name: "同业存放",
      side: "liability",
      business_net_income: "-90000000",
      cnx_scale: "12000000000",
      cny_cash: "-120000000",
      cny_ftp: "30000000",
      cny_net: "-90000000",
      weighted_yield: "1.20",
    });

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
          total_market_value_amount: "90125000000",
          total_amortized_cost_amount: "88050000000",
          total_accrued_interest_amount: "1275000000",
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
      getProductCategoryDates: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_product_dates_governed",
          basis: "formal" as const,
          result_kind: "product-category.dates",
          formal_use_allowed: true,
          source_version: "sv_product_dates_governed",
          vendor_version: "vv_none",
          rule_version: "rv_product_category_pnl_formal_v1",
          cache_version: "cv_product_category_pnl_formal_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:10:00Z",
        },
        result: { report_dates: ["2026-02-28"] },
      })),
      getProductCategoryPnl: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_product_category_governed",
          basis: "formal" as const,
          result_kind: "product-category.pnl",
          formal_use_allowed: true,
          source_version: "sv_product_category_governed",
          vendor_version: "vv_none",
          rule_version: "rv_product_category_pnl_formal_v1",
          cache_version: "cv_product_category_pnl_formal_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:11:00Z",
        },
        result: {
          report_date: "2026-02-28",
          view: "monthly",
          available_views: ["monthly", "qtd", "ytd", "year_to_report_month_end"],
          scenario_rate_pct: null,
          rows: [bondInvestment, interbankDeposits, assetTotal, liabilityTotal, grandTotal],
          asset_total: assetTotal,
          liability_total: liabilityTotal,
          grand_total: grandTotal,
        },
      })),
    });

    const cockpit = await screen.findByTestId("operations-business-kpis");
    await waitFor(() => {
      expect(cockpit).toHaveTextContent("资产净收入");
      expect(cockpit).toHaveTextContent("4.20");
      expect(cockpit).toHaveTextContent("负债净收入");
      expect(cockpit).toHaveTextContent("-1.30");
      expect(cockpit).toHaveTextContent("经营净收入");
      expect(cockpit).toHaveTextContent("2.90");
      expect(cockpit).toHaveTextContent("/ui/pnl/product-category");
      expect(cockpit).not.toHaveTextContent("总市值");
      expect(cockpit).not.toHaveTextContent("摊余成本");
      expect(cockpit).not.toHaveTextContent("3,525.0");
    });

    const conclusionGrid = await screen.findByTestId("operations-conclusion-grid");
    await waitFor(() => {
      expect(conclusionGrid).toHaveTextContent("2026-02-28");
      expect(conclusionGrid).toHaveTextContent("产品分类损益正式读模型");
      expect(conclusionGrid).toHaveTextContent("2.90");
    });

    const contributionGrid = await screen.findByTestId("operations-contribution-grid");
    await waitFor(() => {
      expect(contributionGrid).toHaveTextContent("债券投资");
      expect(contributionGrid).toHaveTextContent("同业存放");
      expect(contributionGrid).toHaveTextContent("2.60");
      expect(contributionGrid).toHaveTextContent("总收益（合计）");
      expect(contributionGrid).toHaveTextContent("全部市场科目 + 投资收益合计：2.90");
      expect(contributionGrid).not.toHaveTextContent("240001.IB");
    });

    const totalSummary = await screen.findByTestId("operations-contribution-total-summary");
    expect(totalSummary).toHaveTextContent("当前场景：1.75%");
    expect(totalSummary).toHaveTextContent("基准场景：1.75%");
    expect(totalSummary).toHaveTextContent("4.20 / -1.30");

    const heroProvenance = await screen.findByTestId("operations-hero-provenance");
    expect(heroProvenance).toHaveTextContent("物化/候选对账");
    expect(heroProvenance).toHaveTextContent("总账对账 + 日均");
    expect(heroProvenance).toHaveTextContent("静态示例");
    const tableProv = await screen.findByTestId("operations-contribution-table-provenance");
    expect(tableProv).toHaveTextContent("口径 正式口径");
  });

  it("labels product-category contribution rows with the resolved payload report date", async () => {
    const base = createApiClient({ mode: "mock" });
    const assetTotal = productCategoryRow({
      category_id: "asset_total",
      category_name: "资产合计",
      side: "asset",
      business_net_income: "120000000",
      is_total: true,
      report_date: "2026-02-27",
    });
    const liabilityTotal = productCategoryRow({
      category_id: "liability_total",
      category_name: "负债合计",
      side: "liability",
      business_net_income: "-20000000",
      is_total: true,
      report_date: "2026-02-27",
    });
    const grandTotal = productCategoryRow({
      category_id: "grand_total",
      category_name: "合计",
      side: "total",
      business_net_income: "100000000",
      is_total: true,
      report_date: "2026-02-27",
    });

    renderPage({
      ...base,
      getProductCategoryDates: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_product_dates_requested",
          basis: "formal" as const,
          result_kind: "product-category.dates",
          formal_use_allowed: true,
          source_version: "sv_product_dates_requested",
          vendor_version: "vv_none",
          rule_version: "rv_product_category_pnl_formal_v1",
          cache_version: "cv_product_category_pnl_formal_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:10:00Z",
        },
        result: { report_dates: ["2026-02-28"] },
      })),
      getProductCategoryPnl: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_product_category_resolved",
          basis: "formal" as const,
          result_kind: "product-category.pnl",
          formal_use_allowed: true,
          source_version: "sv_product_category_resolved",
          vendor_version: "vv_none",
          rule_version: "rv_product_category_pnl_formal_v1",
          cache_version: "cv_product_category_pnl_formal_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:11:00Z",
        },
        result: {
          report_date: "2026-02-27",
          view: "monthly",
          available_views: ["monthly", "qtd", "ytd", "year_to_report_month_end"],
          scenario_rate_pct: null,
          rows: [assetTotal, liabilityTotal, grandTotal],
          asset_total: assetTotal,
          liability_total: liabilityTotal,
          grand_total: grandTotal,
        },
      })),
    });

    const tableProv = await screen.findByTestId("operations-contribution-table-provenance");
    await waitFor(() => {
      expect(tableProv).toHaveTextContent("2026-02-27");
      expect(tableProv).not.toHaveTextContent("2026-02-28");
    });
  });
});
