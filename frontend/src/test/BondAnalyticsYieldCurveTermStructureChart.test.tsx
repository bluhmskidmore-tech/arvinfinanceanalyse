import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => null,
}));

import { ApiClientProvider, createApiClient, useApiClient } from "../api/client";
import { apiQueryKeys } from "../api/queryKeys";
import { BondAnalyticsOverviewMidCharts } from "../features/bond-analytics/components/BondAnalyticsOverviewMidCharts";
import { BondAnalyticsYieldCurveTermStructureChart } from "../features/bond-analytics/components/BondAnalyticsYieldCurveTermStructureChart";
import {
  BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
  useBondAnalyticsCockpitBundleQuery,
} from "../features/bond-analytics/lib/bondAnalyticsCockpitBundleQuery";

/**
 * Stands in for `BondAnalyticsInstitutionalCockpit`'s yield-curve query, which already used
 * `apiQueryKeys.bondAnalyticsYieldCurveTermStructure`. Before the fix, the standalone chart used
 * an ad hoc key for the same endpoint/params, so the two components fired two network requests
 * instead of sharing one cached result.
 */
function SiblingYieldCurveConsumer({ reportDate }: { reportDate: string }) {
  const client = useApiClient();
  useQuery({
    queryKey: apiQueryKeys.bondAnalyticsYieldCurveTermStructure(
      client.mode,
      reportDate,
      BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
    ),
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(reportDate, {
        curveTypes: BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
      }),
    enabled: Boolean(reportDate),
  });
  return null;
}

function SiblingCockpitBundleConsumer({ reportDate }: { reportDate: string }) {
  useBondAnalyticsCockpitBundleQuery(reportDate);
  return null;
}

describe("BondAnalyticsYieldCurveTermStructureChart", () => {
  it("dedupes onto a single request when a sibling reads the same canonical yield-curve queryKey", async () => {
    const base = createApiClient({ mode: "mock" });
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      (reportDate: string, options?: { curveTypes?: string }) =>
        base.getBondAnalyticsYieldCurveTermStructure(reportDate, options),
    );
    const client = { ...base, getBondAnalyticsYieldCurveTermStructure };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondAnalyticsYieldCurveTermStructureChart reportDate="2026-03-31" />
          <SiblingYieldCurveConsumer reportDate="2026-03-31" />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledTimes(1);
    });
    expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalledWith("2026-03-31", {
      curveTypes: "treasury,cdb,aaa_credit",
    });
  });

  it("renders a bundled section without firing the standalone yield-curve endpoint", async () => {
    const base = createApiClient({ mode: "mock" });
    const bundledYieldCurve = await base.getBondAnalyticsYieldCurveTermStructure("2026-03-31", {
      curveTypes: "treasury,cdb",
    });
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      (reportDate: string, options?: { curveTypes?: string }) =>
        base.getBondAnalyticsYieldCurveTermStructure(reportDate, options),
    );
    const client = { ...base, getBondAnalyticsYieldCurveTermStructure };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondAnalyticsYieldCurveTermStructureChart
            reportDate="2026-03-31"
            bundledYieldCurveQuery={{
              data: bundledYieldCurve,
              error: null,
              isError: false,
              isPending: false,
              isLoading: false,
            }}
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(screen.getByTestId("bond-analytics-yield-curve-term-structure")).toBeInTheDocument();
    expect(getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();
  });

  it("shows every resolved curve date when the payload is mixed", async () => {
    const base = createApiClient({ mode: "mock" });
    const bundledYieldCurve = await base.getBondAnalyticsYieldCurveTermStructure("2026-03-31", {
      curveTypes: "treasury,cdb",
    });
    const mixedYieldCurve = {
      ...bundledYieldCurve,
      result: {
        ...bundledYieldCurve.result,
        curves: [
          {
            curve_type: "treasury",
            trade_date_requested: "2026-03-31",
            trade_date_resolved: "2026-03-31",
            points: [],
            source_version: "test",
            rule_version: "test",
            vendor_name: "test",
            vendor_version: "test",
          },
          {
            curve_type: "cdb",
            trade_date_requested: "2026-03-31",
            trade_date_resolved: "2026-03-28",
            points: [],
            source_version: "test",
            rule_version: "test",
            vendor_name: "test",
            vendor_version: "test",
          },
        ],
      },
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={base}>
          <BondAnalyticsYieldCurveTermStructureChart
            reportDate="2026-03-31"
            bundledYieldCurveQuery={{
              data: mixedYieldCurve,
              error: null,
              isError: false,
              isPending: false,
              isLoading: false,
            }}
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    const card = screen.getByTestId("bond-analytics-yield-curve-term-structure");
    expect(card).toHaveTextContent("2026-03-31");
    expect(card).toHaveTextContent("2026-03-28");
  });

  it("uses the cockpit bundle in overview mid charts instead of the standalone yield-curve endpoint", async () => {
    const base = createApiClient({ mode: "mock" });
    const fetchBondDashboardBundle = vi.fn(
      (
        reportDate: Parameters<typeof base.fetchBondDashboardBundle>[0],
        sections: Parameters<typeof base.fetchBondDashboardBundle>[1],
        opts?: Parameters<typeof base.fetchBondDashboardBundle>[2],
      ) =>
        base.fetchBondDashboardBundle(reportDate, sections, opts),
    );
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      (reportDate: string, options?: { curveTypes?: string }) =>
        base.getBondAnalyticsYieldCurveTermStructure(reportDate, options),
    );
    const getBondAnalyticsReturnDecomposition = vi.fn(
      (
        reportDate: string,
        periodType: string,
        options?: { assetClass?: string; accountingClass?: string; detail?: "full" | "summary" },
      ) => base.getBondAnalyticsReturnDecomposition(reportDate, periodType, options),
    );
    const client = {
      ...base,
      fetchBondDashboardBundle,
      getBondAnalyticsYieldCurveTermStructure,
      getBondAnalyticsReturnDecomposition,
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <BondAnalyticsOverviewMidCharts
            reportDate="2026-03-31"
            periodType="MoM"
            assetClass="all"
            accountingClass="all"
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(fetchBondDashboardBundle).toHaveBeenCalledTimes(1);
    });
    expect(fetchBondDashboardBundle.mock.calls[0]?.[2]?.curveTypes).toBe("treasury,cdb,aaa_credit");
    expect(getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalledTimes(1);
    });
    expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalledWith("2026-03-31", "MoM", {
      detail: "summary",
    });
  });

  it("shares one cockpit bundle request when overview cockpit and mid charts mount together", async () => {
    const base = createApiClient({ mode: "mock" });
    const fetchBondDashboardBundle = vi.fn(
      (
        reportDate: Parameters<typeof base.fetchBondDashboardBundle>[0],
        sections: Parameters<typeof base.fetchBondDashboardBundle>[1],
        opts?: Parameters<typeof base.fetchBondDashboardBundle>[2],
      ) =>
        base.fetchBondDashboardBundle(reportDate, sections, opts),
    );
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      (reportDate: string, options?: { curveTypes?: string }) =>
        base.getBondAnalyticsYieldCurveTermStructure(reportDate, options),
    );
    const getBondAnalyticsReturnDecomposition = vi.fn(
      (
        reportDate: string,
        periodType: string,
        options?: { assetClass?: string; accountingClass?: string; detail?: "full" | "summary" },
      ) => base.getBondAnalyticsReturnDecomposition(reportDate, periodType, options),
    );
    const client = {
      ...base,
      fetchBondDashboardBundle,
      getBondAnalyticsYieldCurveTermStructure,
      getBondAnalyticsReturnDecomposition,
    };
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <SiblingCockpitBundleConsumer reportDate="2026-03-31" />
          <BondAnalyticsOverviewMidCharts
            reportDate="2026-03-31"
            periodType="MoM"
            assetClass="all"
            accountingClass="all"
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(fetchBondDashboardBundle).toHaveBeenCalledTimes(1);
    });
    expect(fetchBondDashboardBundle.mock.calls[0]?.[0]).toBe("2026-03-31");
    expect(getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalledTimes(1);
    });
  });
});
