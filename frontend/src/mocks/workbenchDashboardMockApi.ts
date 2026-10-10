/** Demo-only implementation kept outside the real API clients. */
import type { DashboardClientMethods } from "../api/workbenchDashboardApi";


type DashboardWorkbenchSamples = typeof import("./dashboardCoreWorkbenchSamples");

// Demo-only fixtures load lazily so sample data stays out of the production bundle.
let dashboardWorkbenchSamplesPromise: Promise<DashboardWorkbenchSamples> | null = null;

function ensureDashboardWorkbenchSamples(): Promise<DashboardWorkbenchSamples> {
  dashboardWorkbenchSamplesPromise ??= import("./dashboardCoreWorkbenchSamples");
  return dashboardWorkbenchSamplesPromise;
}

/** ApiClient 延迟函数形状（与 ``client.ts`` 内嵌一致）。 */
type DelayFn = () => Promise<void>;

type BundledEnvelopeFactory = Pick<typeof import("./mockApiEnvelope"), "buildMockApiEnvelope">;

type EnsureBundle = () => Promise<BundledEnvelopeFactory>;

export function dashboardWorkbenchDemoEndpoints(
  delay: DelayFn,
  ensureBundle: EnsureBundle,
): DashboardClientMethods {
  return {
    async getCoreMetrics() {
      await delay();
      const { sampleCoreMetricsResult } = await ensureDashboardWorkbenchSamples();
      return (await ensureBundle()).buildMockApiEnvelope(
        "dashboard.core_metrics",
        sampleCoreMetricsResult(),
      );
    },
    async getDailyChanges() {
      await delay();
      const { sampleDailyChangesResult } = await ensureDashboardWorkbenchSamples();
      return (await ensureBundle()).buildMockApiEnvelope(
        "dashboard.daily_changes",
        sampleDailyChangesResult(),
      );
    },
  };
}
