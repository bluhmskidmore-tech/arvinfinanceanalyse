import type {
  CoreMetricsPayload,
  CoreMetricsResult,
  DailyChangesPayload,
  DailyChangesResult,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { sampleCoreMetricsResult, sampleDailyChangesResult } from "../fixtures/dashboardCoreWorkbenchSamples";

/** ApiClient 延迟函数形状（与 ``client.ts`` 内嵌一致）。 */
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

export type DashboardClientMethods = {
  getCoreMetrics: (params?: { reportDate?: string }) => Promise<CoreMetricsPayload>;
  getDailyChanges: (params?: { reportDate?: string }) => Promise<DailyChangesPayload>;
};

export function dashboardWorkbenchDemoEndpoints(
  delay: DelayFn,
  ensureBundle: EnsureBundle,
): DashboardClientMethods {
  return {
    async getCoreMetrics() {
      await delay();
      return (await ensureBundle()).buildMockApiEnvelope(
        "dashboard.core_metrics",
        sampleCoreMetricsResult(),
      );
    },
    async getDailyChanges() {
      await delay();
      return (await ensureBundle()).buildMockApiEnvelope(
        "dashboard.daily_changes",
        sampleDailyChangesResult(),
      );
    },
  };
}

export function dashboardWorkbenchLiveEndpoints(dep: FetchJsonDeps): DashboardClientMethods {
  const { fetchImpl, baseUrl, requestJson } = dep;
  return {
    getCoreMetrics: ({ reportDate } = {}) => {
      const suffix = reportDate?.trim()
        ? `?report_date=${encodeURIComponent(reportDate.trim())}`
        : "";
      return requestJson<CoreMetricsResult>(
        fetchImpl,
        baseUrl,
        `/api/dashboard/core_metrics${suffix}`,
      );
    },
    getDailyChanges: ({ reportDate } = {}) => {
      const suffix = reportDate?.trim()
        ? `?report_date=${encodeURIComponent(reportDate.trim())}`
        : "";
      return requestJson<DailyChangesResult>(
        fetchImpl,
        baseUrl,
        `/api/dashboard/daily-changes${suffix}`,
      );
    },
  };
}
