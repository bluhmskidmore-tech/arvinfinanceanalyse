import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  CreditSpreadMigrationPayload,
  ResultMeta,
} from "../api/contracts";
import { apiQueryKeys } from "../api/queryKeys";
import ConcentrationMonitorPage from "../features/concentration-monitor/ConcentrationMonitorPage";
import { routerFuture } from "../router/routerFuture";
import { formatRawAsNumeric } from "../utils/format";

const resultMeta: ResultMeta = {
  trace_id: "test_credit_spread_cache_shape",
  basis: "formal",
  result_kind: "bond_analytics.credit_spread_migration",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-12T10:00:00Z",
};

function creditSpreadEnvelope(
  reportDate: string,
): ApiEnvelope<CreditSpreadMigrationPayload> {
  const ratio = (raw: number) => formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false });
  const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
  const bp = (raw: number) => formatRawAsNumeric({ raw, unit: "bp", sign_aware: false });
  const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });

  return {
    result_meta: resultMeta,
    result: {
      report_date: reportDate,
      credit_bond_count: 10,
      credit_market_value: yuan(100_000_000),
      credit_weight: ratio(0.2),
      rating_aa_and_below_weight: ratio(0.08),
      spread_dv01: dv01(12),
      weighted_avg_spread: bp(90),
      weighted_avg_spread_duration: ratio(3.2),
      spread_scenarios: [],
      migration_scenarios: [],
      concentration_by_issuer: {
        dimension: "issuer",
        hhi: ratio(0.12),
        top5_concentration: ratio(0.3),
        top_items: [
          {
            name: "Issuer A",
            weight: ratio(0.08),
            market_value: yuan(80_000_000),
          },
        ],
      },
      concentration_by_industry: {
        dimension: "industry",
        hhi: ratio(0.1),
        top5_concentration: ratio(0.25),
        top_items: [],
      },
      concentration_by_rating: {
        dimension: "rating",
        hhi: ratio(0.2),
        top5_concentration: ratio(0.4),
        top_items: [],
      },
      concentration_by_tenor: {
        dimension: "tenor",
        hhi: ratio(0.11),
        top5_concentration: ratio(0.28),
        top_items: [],
      },
      oci_credit_exposure: yuan(0),
      oci_spread_dv01: dv01(0),
      oci_sensitivity_25bp: yuan(0),
      warnings: [],
      computed_at: "2026-04-12T00:00:00Z",
    },
  };
}

function renderConcentrationMonitor(client: ApiClient, queryClient: QueryClient) {
  const router = createMemoryRouter(
    [{ path: "/concentration-monitor", element: <ConcentrationMonitorPage /> }],
    {
      initialEntries: ["/concentration-monitor?report_date=2026-03-31"],
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

describe("ConcentrationMonitorPage", () => {
  it("keeps the shared credit-spread query cache as a full API envelope", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: { ...resultMeta, result_kind: "bond_analytics.dates" },
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async (reportDate: string) =>
        creditSpreadEnvelope(reportDate),
      ),
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderConcentrationMonitor(client, queryClient);

    await waitFor(() => {
      expect(client.getBondAnalyticsCreditSpreadMigration).toHaveBeenCalledWith("2026-03-31");
    });

    const cached = queryClient.getQueryData(
      apiQueryKeys.bondAnalyticsCreditSpreadMigration("mock", "2026-03-31"),
    );

    expect(cached).toMatchObject({
      result_meta: expect.objectContaining({
        result_kind: "bond_analytics.credit_spread_migration",
      }),
      result: expect.objectContaining({
        report_date: "2026-03-31",
      }),
    });
  });
});
