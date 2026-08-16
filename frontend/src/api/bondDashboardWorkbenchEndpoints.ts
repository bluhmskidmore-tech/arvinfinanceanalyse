import type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
import type { BondBusinessTypeMetricsResult } from "./contracts";

type DashboardWorkbenchSamples = typeof import("../fixtures/dashboardCoreWorkbenchSamples");

const BOND_DASHBOARD_NULL_CURRENCY_META = {
  amount_currency_basis: null,
  amount_currency_basis_note: null,
} as const;

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
      const {
        SAMPLE_BOND_DASHBOARD_EVIDENCE_ROWS,
        sampleBondBusinessTypeMetricRows,
      } = await ensureDashboardWorkbenchSamples();
      return {
        ...(await ensureBundle()).buildMockApiEnvelope(
          "bond_dashboard.business_type_metrics",
          {
            report_date: reportDate,
            items: sampleBondBusinessTypeMetricRows,
          },
          {
            ...BOND_DASHBOARD_NULL_CURRENCY_META,
            basis: "analytical",
            formal_use_allowed: false,
            cache_key: null,
            quality_flag: sampleBondBusinessTypeMetricRows.length > 0 ? "ok" : "warning",
            requested_report_date: reportDate,
            resolved_report_date: reportDate,
            as_of_date: reportDate,
            date_basis: "bond_dashboard_report_date",
            fallback_date: null,
            filters_applied: { report_date: reportDate },
            tables_used: ["fact_formal_bond_analytics_daily"],
            evidence_rows: SAMPLE_BOND_DASHBOARD_EVIDENCE_ROWS,
            next_drill: [],
          },
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
