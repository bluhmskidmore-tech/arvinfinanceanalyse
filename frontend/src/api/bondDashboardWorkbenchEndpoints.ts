import type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
import type { BondBusinessTypeMetricsResult } from "./contracts";

type FetchJsonDeps = {
  fetchImpl: typeof fetch;
  baseUrl: string;
  requestJson: <T>(
    fetchImpl: typeof fetch,
    baseUrl: string,
    path: string,
  ) => Promise<import("./contracts").ApiEnvelope<T>>;
};

export type BondDashboardWorkbenchEndpoints = Pick<
  BondAnalyticsClientMethods,
  "getBondBusinessTypeMetrics"
>;

export function bondDashboardLiveEndpoints(dep: FetchJsonDeps): BondDashboardWorkbenchEndpoints {
  const { fetchImpl, baseUrl, requestJson } = dep;
  return {
    getBondBusinessTypeMetrics: ({ reportDate }) =>
      requestJson<BondBusinessTypeMetricsResult>(
        fetchImpl,
        baseUrl,
        `/api/bond-dashboard/business-type-metrics?report_date=${encodeURIComponent(reportDate)}`,
      ),
  };
}
