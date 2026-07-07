import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../api/client";
import type { ApiEnvelope, PnlByBusinessCandidateInsightsPayload, ResultMeta } from "../../api/contracts";
import { routerFuture } from "../../router/routerFuture";
import PnlByBusinessInsightsPage from "./PnlByBusinessInsightsPage";

const resultMeta: ResultMeta = {
  trace_id: "tr_pnl_business_insights_test",
  basis: "analytical",
  result_kind: "pnl.by_business_candidate_insights",
  formal_use_allowed: false,
  source_version: "sv_test",
  vendor_version: "vv_none",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  requested_report_date: "2026-02-28",
  resolved_report_date: "2026-02-28",
  as_of_date: "2026-02-28",
  tables_used: ["pnl.by_business_ytd", "pnl.by_business_monthly"],
  generated_at: "2026-06-30T00:00:00Z",
};

function buildPayload(
  overrides?: Partial<PnlByBusinessCandidateInsightsPayload>,
): ApiEnvelope<PnlByBusinessCandidateInsightsPayload> {
  return {
    result_meta: resultMeta,
    result: {
      year: 2026,
      as_of_date: "2026-02-28",
      concentration: {
        year: 2026,
        as_of_date: "2026-02-28",
        total_avg_balance: "1000.00",
        hhi_pct: "53.12",
        top_n: 3,
        top_n_share_pct: "100.00",
        rows: [
          {
            row_key: "asset_zqtz_treasury_bond",
            business_type: "国债",
            avg_balance: "625.00",
            share_pct: "62.50",
          },
          {
            row_key: "asset_zqtz_policy_financial_bond",
            business_type: "政策性金融债",
            avg_balance: "375.00",
            share_pct: "37.50",
          },
        ],
      },
      negative_ftp_persistence: {
        as_of_date: "2026-02-28",
        lookback_months: 12,
        window_start_month: "2025-03",
        window_end_month: "2026-02",
        months_observed: 3,
        negative_ftp_month_share_pct: "0.00",
        negative_ftp_longest_streak_months: 0,
        rows: [
          {
            row_key: "asset_zqtz_treasury_bond",
            business_type: "国债",
            months_observed: 12,
            negative_ftp_month_share_pct: "66.67",
            negative_ftp_longest_streak_months: 5,
          },
          {
            row_key: "asset_zqtz_policy_financial_bond",
            business_type: "政策性金融债",
            months_observed: 12,
            negative_ftp_month_share_pct: "16.67",
            negative_ftp_longest_streak_months: 2,
          },
        ],
      },
      share_drift: {
        year: 2026,
        as_of_date: "2026-02-28",
        baseline_year: 2025,
        baseline_as_of_date: "2025-12-31",
        baseline_available: true,
        rows: [
          {
            row_key: "asset_zqtz_treasury_bond",
            business_type: "国债",
            current_share_pct: "62.50",
            baseline_share_pct: "70.00",
            drift_pp: "-7.50",
          },
          {
            row_key: "asset_zqtz_policy_financial_bond",
            business_type: "政策性金融债",
            current_share_pct: "37.50",
            baseline_share_pct: "30.00",
            drift_pp: "7.50",
          },
        ],
      },
      ...overrides,
    },
  };
}

function renderPage(client: ApiClient, queryClient: QueryClient) {
  const router = createMemoryRouter(
    [{ path: "/pnl-by-business-insights", element: <PnlByBusinessInsightsPage /> }],
    {
      initialEntries: ["/pnl-by-business-insights"],
      future: routerFuture,
    },
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

function buildClient(getPnlByBusinessCandidateInsights: ApiClient["getPnlByBusinessCandidateInsights"]): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return { ...base, getPnlByBusinessCandidateInsights };
}

function buildQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

describe("PnlByBusinessInsightsPage", () => {
  it("surfaces the unapproved candidate contract status", async () => {
    const client = buildClient(vi.fn(async () => buildPayload()));
    renderPage(client, buildQueryClient());

    const statusPanel = await waitFor(() => {
      const panel = document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]');
      expect(panel).not.toBeNull();
      return panel as HTMLElement;
    });

    expect(statusPanel).toHaveTextContent("未审批");
    expect(statusPanel).toHaveTextContent("正式可用: 否");
    expect(statusPanel).toHaveTextContent("口径 analytical");
    expect(statusPanel).toHaveTextContent("数据截至 2026-02-28");
  });

  it("shows the full mandatory candidate disclaimer text verbatim", async () => {
    const client = buildClient(vi.fn(async () => buildPayload()));
    renderPage(client, buildQueryClient());

    const disclaimer = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-disclaimer"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(disclaimer).toHaveTextContent(
      "本页指标为候选分析（status=candidate），仅供内部参考，不构成正式业务结论；最终审批需业务owner确认后方可用于正式汇报。",
    );
  });

  it("renders concentration, negative-FTP persistence, and share-drift sections from mock data", async () => {
    const client = buildClient(vi.fn(async () => buildPayload()));
    renderPage(client, buildQueryClient());

    const kpis = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(kpis).toHaveTextContent("53.12%");
    expect(kpis).toHaveTextContent("100.00%");

    const concentrationTable = document.querySelector(
      '[data-testid="pnl-by-business-insights-concentration-table"]',
    ) as HTMLElement;
    expect(concentrationTable).toHaveTextContent("国债");
    expect(concentrationTable).toHaveTextContent("62.50%");
    expect(concentrationTable).toHaveTextContent("政策性金融债");
    expect(concentrationTable).toHaveTextContent("37.50%");

    const negativeFtpTable = document.querySelector(
      '[data-testid="pnl-by-business-insights-negative-ftp-table"]',
    ) as HTMLElement;
    expect(negativeFtpTable).toHaveTextContent("66.67%");
    expect(negativeFtpTable).toHaveTextContent("16.67%");
    expect(negativeFtpTable).toHaveTextContent("5");
    expect(negativeFtpTable).toHaveTextContent("2");

    const shareDriftTable = document.querySelector(
      '[data-testid="pnl-by-business-insights-share-drift-table"]',
    ) as HTMLElement;
    expect(shareDriftTable).toHaveTextContent("-7.50pp");
    expect(shareDriftTable).toHaveTextContent("+7.50pp");
  });

  it("sorts negative-FTP rows by share descending and highlights rows at or above 50%", async () => {
    const client = buildClient(vi.fn(async () => buildPayload()));
    renderPage(client, buildQueryClient());

    const negativeFtpTable = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-negative-ftp-table"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    const rows = negativeFtpTable.querySelectorAll("tbody tr");
    expect(rows[0]).toHaveTextContent("国债");
    expect(rows[0]).toHaveTextContent("66.67%");
    expect(rows[1]).toHaveTextContent("政策性金融债");
  });

  it("sorts share-drift rows by absolute drift descending, largest first", async () => {
    const payload = buildPayload();
    payload.result.share_drift.rows = [
      {
        row_key: "asset_zqtz_policy_financial_bond",
        business_type: "政策性金融债",
        current_share_pct: "37.50",
        baseline_share_pct: "38.00",
        drift_pp: "-0.50",
      },
      {
        row_key: "asset_zqtz_treasury_bond",
        business_type: "国债",
        current_share_pct: "62.50",
        baseline_share_pct: "70.00",
        drift_pp: "-7.50",
      },
    ];
    const client = buildClient(vi.fn(async () => payload));
    renderPage(client, buildQueryClient());

    const shareDriftTable = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-share-drift-table"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    const rows = shareDriftTable.querySelectorAll("tbody tr");
    expect(rows[0]).toHaveTextContent("国债");
    expect(rows[0]).toHaveTextContent("-7.50pp");
    expect(rows[1]).toHaveTextContent("政策性金融债");
  });

  it("shows an explicit empty state when the prior-year baseline is unavailable", async () => {
    const payload = buildPayload();
    payload.result.share_drift.baseline_available = false;
    payload.result.share_drift.baseline_as_of_date = null;
    payload.result.share_drift.rows = [];
    const client = buildClient(vi.fn(async () => payload));
    renderPage(client, buildQueryClient());

    const emptyState = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-share-drift-empty"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(emptyState).toHaveTextContent("上一年无数据，无法计算漂移");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-share-drift-table"]')).toBeNull();
  });
});
