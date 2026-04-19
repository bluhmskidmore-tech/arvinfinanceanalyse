import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { DashboardBondHeadlineSection } from "../features/executive-dashboard/components/DashboardBondHeadlineSection";
import { formatRawAsNumeric } from "../utils/format";

describe("DashboardBondHeadlineSection", () => {
  it("renders the KPI grid without leaking a DV01 card", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBondDashboardHeadlineKpis = async () => ({
      result_meta: {
        trace_id: "tr_dashboard_bond_headline_section",
        basis: "formal",
        result_kind: "bond_dashboard.headline",
        formal_use_allowed: true,
        source_version: "sv_headline",
        vendor_version: "vv_headline",
        rule_version: "rv_headline",
        cache_version: "cv_headline",
        quality_flag: "ok",
        vendor_status: "ok",
        fallback_mode: "none",
        scenario_flag: false,
        generated_at: "2026-04-19T00:00:00Z",
      },
      result: {
        report_date: "2026-03-31",
        prev_report_date: null,
        kpis: {
          total_market_value: formatRawAsNumeric({ raw: 32870900000, unit: "yuan", sign_aware: false }),
          unrealized_pnl: formatRawAsNumeric({ raw: 128450000, unit: "yuan", sign_aware: true }),
          weighted_ytm: formatRawAsNumeric({ raw: 0.0321, unit: "pct", sign_aware: false }),
          weighted_duration: formatRawAsNumeric({ raw: 4.27, unit: "ratio", sign_aware: false }),
          weighted_coupon: formatRawAsNumeric({ raw: 0.0285, unit: "pct", sign_aware: false }),
          credit_spread_median: formatRawAsNumeric({ raw: 0.0143, unit: "pct", sign_aware: false }),
          total_dv01: formatRawAsNumeric({ raw: 987654, unit: "dv01", sign_aware: false }),
          bond_count: 248,
        },
        prev_kpis: null,
      },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <DashboardBondHeadlineSection reportDate="2026-03-31" />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getAllByTestId("dashboard-bond-headline-kpi")).toHaveLength(8));
    expect(screen.getByText("利率敏感度合计")).toBeInTheDocument();
    expect(screen.queryByText(/DV01/i)).not.toBeInTheDocument();
  });
});
