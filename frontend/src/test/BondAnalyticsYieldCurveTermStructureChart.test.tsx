import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  __esModule: true,
  default: () => null,
}));

import { ApiClientProvider, createApiClient, useApiClient } from "../api/client";
import { apiQueryKeys } from "../api/queryKeys";
import { BondAnalyticsYieldCurveTermStructureChart } from "../features/bond-analytics/components/BondAnalyticsYieldCurveTermStructureChart";

/**
 * Stands in for `BondAnalyticsInstitutionalCockpit`'s yield-curve query, which already used
 * `apiQueryKeys.bondAnalyticsYieldCurveTermStructure`. Before the fix, the standalone chart used
 * an ad hoc key for the same endpoint/params, so the two components fired two network requests
 * instead of sharing one cached result.
 */
function SiblingYieldCurveConsumer({ reportDate }: { reportDate: string }) {
  const client = useApiClient();
  useQuery({
    queryKey: apiQueryKeys.bondAnalyticsYieldCurveTermStructure(client.mode, reportDate, "treasury,cdb"),
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(reportDate, { curveTypes: "treasury,cdb" }),
    enabled: Boolean(reportDate),
  });
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
      curveTypes: "treasury,cdb",
    });
  });
});
