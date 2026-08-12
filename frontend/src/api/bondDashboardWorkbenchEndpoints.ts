import type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
import type { BondBusinessTypeMetricsResult } from "./contracts";

type DashboardWorkbenchSamples = typeof import("../fixtures/dashboardCoreWorkbenchSamples");

// Demo-only fixtures load lazily so sample data stays out of the production bundle.
let dashboardWorkbenchSamplesPromise: Promise<DashboardWorkbenchSamples> | null = null;

function ensureDashboardWorkbenchSamples(): Promise<DashboardWorkbenchSamples> {
  dashboardWorkbenchSamplesPromise ??= import("../fixtures/dashboardCoreWorkbenchSamples");
  return dashboardWorkbenchSamplesPromise;
}

type DelayFn = () => Promise<void>;

type BundledEnvelopeFactory = Pick<typeof import("../mocks/mockApiEnvelope"), "buildMockApiEnvelope">;

type EnsureBundle = () => Promise<BundledEnvelopeFactory>;

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

export function bondDashboardDemoEndpoints(
  delay: DelayFn,
  ensureBundle: EnsureBundle,
): BondDashboardWorkbenchEndpoints {
  return {
    async getBondBusinessTypeMetrics({ reportDate }) {
      await delay();
      const { sampleBondBusinessTypeMetricRows } = await ensureDashboardWorkbenchSamples();
      return {
        ...(await ensureBundle()).buildMockApiEnvelope(
          "bond_dashboard.business_type_metrics",
          {
            report_date: reportDate,
            items: sampleBondBusinessTypeMetricRows,
          },
          { basis: "formal", formal_use_allowed: true },
        ),
        data_source: "bond_analytics_facts",
      };
    },
  };
}

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
