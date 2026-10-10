import type {
  CoreMetricsPayload,
  CoreMetricsResult,
  DailyChangesPayload,
  DailyChangesResult,
} from "./contracts";

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
