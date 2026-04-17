import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { createApiClient, type ApiClient, ApiClientProvider } from "../api/client";
import type { ResultMeta } from "../api/contracts";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";
import { routerFuture } from "../router/routerFuture";

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_ledger_route",
    vendor_version: "vv_none",
    rule_version: "rv_ledger_route",
    cache_version: "cv_ledger_route",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-17T08:00:00Z",
  };
}

function buildLedgerClient(): ApiClient {
  const base = createApiClient({ mode: "real" });
  return {
    ...base,
    getLedgerPnlDates: vi.fn(async () => ({
      result_meta: buildMeta("ledger_pnl.dates", "tr_ledger_dates"),
      result: {
        dates: ["2025-12-31", "2025-11-30"],
      },
    })),
    getLedgerPnlSummary: vi.fn(async (reportDate?: string, currency?: string) => {
      const value =
        reportDate === "2025-11-30"
          ? currency === "CNX"
            ? "15.00"
            : "18.00"
          : currency === "CNX"
            ? "35.00"
            : "40.00";
      return {
        result_meta: buildMeta("ledger_pnl.summary", "tr_ledger_summary"),
        result: {
          report_date: reportDate ?? "2025-12-31",
          source_version: "sv_ledger_data",
          ledger_total_assets: { yuan: reportDate === "2025-11-30" ? "900.00" : "1200.00", yi: "0.00", wan: "0.12" },
          ledger_total_liabilities: { yuan: reportDate === "2025-11-30" ? "700.00" : "800.00", yi: "0.00", wan: "0.08" },
          ledger_net_assets: { yuan: reportDate === "2025-11-30" ? "200.00" : "400.00", yi: "0.00", wan: "0.04" },
          ledger_monthly_pnl_core: { yuan: value, yi: "0.00", wan: "0.00" },
          ledger_monthly_pnl_all: { yuan: value, yi: "0.00", wan: "0.01" },
          by_currency: [
            { currency: "CNX", total_pnl: { yuan: reportDate === "2025-11-30" ? "15.00" : "35.00", yi: "0.00", wan: "0.00" } },
            { currency: "CNY", total_pnl: { yuan: reportDate === "2025-11-30" ? "3.00" : "5.00", yi: "0.00", wan: "0.00" } },
          ],
          by_account: [
            {
              account_code: "514100",
              account_name: "利息收入",
              total_pnl: { yuan: reportDate === "2025-11-30" ? "12.00" : "20.00", yi: "0.00", wan: "0.00" },
              count: 2,
            },
          ],
        },
      };
    }),
    getLedgerPnlData: vi.fn(async (reportDate?: string, currency?: string) => ({
      result_meta: buildMeta("ledger_pnl.data", "tr_ledger_data"),
      result: {
        report_date: reportDate ?? "2025-12-31",
        items: [
          {
            account_code: "514100",
            account_name: "利息收入",
            currency: currency ?? "CNX",
            beginning_balance: { yuan: "100.00", yi: "0.00", wan: "0.01" },
            ending_balance: { yuan: "110.00", yi: "0.00", wan: "0.01" },
            monthly_pnl: { yuan: reportDate === "2025-11-30" ? "6.00" : "10.00", yi: "0.00", wan: "0.00" },
            daily_avg_balance: { yuan: "105.00", yi: "0.00", wan: "0.01" },
            days_in_period: 31,
          },
        ],
        summary: {
          total_pnl_cnx: { yuan: reportDate === "2025-11-30" ? "6.00" : "10.00", yi: "0.00", wan: "0.00" },
          total_pnl_cny: { yuan: "0.00", yi: "0.00", wan: "0.00" },
          total_pnl: { yuan: reportDate === "2025-11-30" ? "6.00" : "10.00", yi: "0.00", wan: "0.00" },
          count: 1,
        },
      },
    })),
  };
}

function renderLedgerWithRouter(initialEntry: string, client: ApiClient) {
  const router = createWorkbenchMemoryRouter([initialEntry]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );

  return router;
}

describe("ledger-pnl routed page smoke", () => {
  it("renders the live /ledger-pnl workbench route", async () => {
    renderWorkbenchApp(["/ledger-pnl"], { client: buildLedgerClient() });

    expect(await screen.findByTestId("ledger-pnl-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("ledger-pnl-report-date")).toHaveValue("2025-12-31");
    });
    expect(screen.getByTestId("ledger-pnl-result-meta-panel")).toHaveTextContent("tr_ledger_dates");
    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-summary-cards")).toHaveTextContent("40.00");
      expect(screen.getByTestId("ledger-pnl-detail-table")).toHaveTextContent("514100");
    });
  });

  it("prefers report_date and currency from the query string when provided", async () => {
    renderWorkbenchApp(["/ledger-pnl?report_date=2025-11-30&currency=CNX"], {
      client: buildLedgerClient(),
    });

    await waitFor(() => {
      expect(screen.getByLabelText("ledger-pnl-report-date")).toHaveValue("2025-11-30");
      expect(screen.getByLabelText("ledger-pnl-currency")).toHaveValue("CNX");
    });

    await waitFor(() => {
      expect(screen.getByTestId("ledger-pnl-summary-cards")).toHaveTextContent("15.00");
    });
  });

  it("syncs current filters back into the URL", async () => {
    const user = userEvent.setup();
    renderLedgerWithRouter("/ledger-pnl", buildLedgerClient());

    await waitFor(() => {
      expect(screen.getByLabelText("ledger-pnl-report-date")).toHaveValue("2025-12-31");
    });

    await user.selectOptions(screen.getByLabelText("ledger-pnl-report-date"), "2025-11-30");
    await user.selectOptions(screen.getByLabelText("ledger-pnl-currency"), "CNX");

    await waitFor(() => {
      expect(window.location.search).toBe("?report_date=2025-11-30&currency=CNX");
    });
  });
});
