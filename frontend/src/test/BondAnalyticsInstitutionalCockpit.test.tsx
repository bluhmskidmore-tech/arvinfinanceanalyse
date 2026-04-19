import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { BondAnalyticsInstitutionalCockpit } from "../features/bond-analytics/components/BondAnalyticsInstitutionalCockpit";

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_cockpit",
    basis: "formal",
    result_kind: "bond_dashboard.dates",
    formal_use_allowed: true,
    source_version: "sv_cockpit",
    vendor_version: "vv_cockpit",
    rule_version: "rv_cockpit",
    cache_version: "cv_cockpit",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-19T00:00:00Z",
    ...overrides,
  };
}

describe("BondAnalyticsInstitutionalCockpit", () => {
  it("falls back to the latest bond-dashboard report date when the page report date is unsupported", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondDashboardDates = vi.fn(async () => ({
      result_meta: createResultMeta({
        result_kind: "bond_dashboard.dates",
      }),
      result: {
        report_dates: ["2026-02-28"],
      },
    }));
    const getBondDashboardHeadlineKpis = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported dashboard date ${reportDate}`);
      }
      return base.getBondDashboardHeadlineKpis(reportDate);
    });
    const getBondDashboardSpreadAnalysis = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported spread date ${reportDate}`);
      }
      return base.getBondDashboardSpreadAnalysis(reportDate);
    });
    const getBondDashboardMaturityStructure = vi.fn(async (reportDate: string) => {
      if (reportDate !== "2026-02-28") {
        throw new Error(`unsupported maturity date ${reportDate}`);
      }
      return base.getBondDashboardMaturityStructure(reportDate);
    });

    const client = {
      ...base,
      getBondDashboardDates,
      getBondDashboardHeadlineKpis,
      getBondDashboardSpreadAnalysis,
      getBondDashboardMaturityStructure,
    };

    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false, refetchOnWindowFocus: false },
            },
          })
        }
      >
        <ApiClientProvider client={client}>
          <BondAnalyticsInstitutionalCockpit
            reportDate="2026-03-31"
            topAnomalies={[]}
            actionAttribution={null}
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("bond-analysis-phase3-cockpit")).toBeInTheDocument();

    await waitFor(() => {
      expect(getBondDashboardDates).toHaveBeenCalledTimes(1);
      expect(getBondDashboardHeadlineKpis).toHaveBeenCalledWith("2026-02-28");
      expect(getBondDashboardSpreadAnalysis).toHaveBeenCalledWith("2026-02-28");
      expect(getBondDashboardMaturityStructure).toHaveBeenCalledWith("2026-02-28");
    });

    expect(screen.queryByText("部分驾驶舱指标未就绪")).not.toBeInTheDocument();
    expect(screen.getByText("仪表盘快照使用 2026-02-28")).toBeInTheDocument();
  });
});
