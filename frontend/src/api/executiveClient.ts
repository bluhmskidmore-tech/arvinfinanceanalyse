/**
 * Executive Dashboard domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import type {
  ApiEnvelope,
  AlertsPayload,
  ContributionPayload,
  GetHomeSnapshotOptions,
  GetHomeMacroReleaseContextOptions,
  HomeIncomeTrendPayload,
  HomeMacroReleaseContextPayload,
  HomeResearchReportsPayload,
  HomeSnapshotPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  ResultMeta,
  RiskOverviewPayload,
  RiskScenarioStressPayload,
  RiskTensorDatesPayload,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  SummaryPayload,
} from "./contracts";
import { fetchHomeSnapshotEnvelope } from "./executiveHomeSnapshotFetch";

export type ExecutiveClientMethods = {
  getOverview: (reportDate?: string) => Promise<ApiEnvelope<OverviewPayload>>;
  getHomeSnapshot: (
    options?: GetHomeSnapshotOptions,
  ) => Promise<ApiEnvelope<HomeSnapshotPayload>>;
  getHomeMacroReleaseContext: (
    options: GetHomeMacroReleaseContextOptions,
  ) => Promise<ApiEnvelope<HomeMacroReleaseContextPayload>>;
  getHomeResearchReports: (
    reportDate: string,
    limit?: number,
  ) => Promise<ApiEnvelope<HomeResearchReportsPayload>>;
  getHomeIncomeTrend: (
    reportDate: string,
    window?: number,
  ) => Promise<ApiEnvelope<HomeIncomeTrendPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getRiskTensorDates: () => Promise<ApiEnvelope<RiskTensorDatesPayload>>;
  getRiskTensor: (reportDate: string) => Promise<ApiEnvelope<RiskTensorPayload>>;
  getRiskTensorHistory: (
    reportDate: string,
    periods?: number,
  ) => Promise<ApiEnvelope<RiskTensorHistoryPayload>>;
  getRiskScenarioStress: (reportDate: string) => Promise<ApiEnvelope<RiskScenarioStressPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
};

type FetchLike = typeof fetch;

export type ExecutiveThinClientMethods = Pick<
  ExecutiveClientMethods,
  | "getOverview"
  | "getHomeSnapshot"
  | "getHomeMacroReleaseContext"
  | "getHomeResearchReports"
  | "getHomeIncomeTrend"
  | "getSummary"
  | "getRiskOverview"
  | "getRiskTensorDates"
  | "getRiskTensor"
  | "getRiskTensorHistory"
  | "getRiskScenarioStress"
  | "getContribution"
  | "getAlerts"
  | "getPlaceholderSnapshot"
>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

export type ExecutiveClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

function buildReadinessPlaceholderEnvelope(key: string): ApiEnvelope<PlaceholderSnapshot> {
  const normalizedKey = key.trim() || "unknown";
  const meta: ResultMeta = {
    trace_id: `readiness_${normalizedKey}`,
    basis: "analytical",
    result_kind: `workbench.${normalizedKey}.readiness`,
    formal_use_allowed: false,
    source_version: "readiness:placeholder",
    vendor_version: "vv_none",
    rule_version: "rv_readiness_placeholder_v1",
    cache_version: "cv_readiness_placeholder_v1",
    quality_flag: "missing",
    vendor_status: "ok",
    fallback_mode: "none",
    source_surface: "workbench_placeholder",
    scenario_flag: false,
    generated_at: "2026-04-09T10:30:00Z",
  };

  return {
    result_meta: meta,
    result: {
      title: normalizedKey === "source-preview" ? "Source Preview" : normalizedKey,
      summary: "",
      highlights: [],
    },
  };
}

export function createRealExecutiveClient(
  options: ExecutiveClientFactoryOptions,
): ExecutiveThinClientMethods {
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getOverview: (reportDate?: string) =>
      requestJson<OverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/overview${reportDate?.trim() ? `?report_date=${encodeURIComponent(reportDate.trim())}` : ""}`,
      ),
    getHomeSnapshot: (options?: GetHomeSnapshotOptions) =>
      fetchHomeSnapshotEnvelope(fetchImpl, baseUrl, options),
    getHomeMacroReleaseContext: (options: GetHomeMacroReleaseContextOptions) => {
      const params = new URLSearchParams({
        start_date: options.startDate,
        end_date: options.endDate,
        history_limit: String(options.historyLimit ?? 8),
      });
      return requestJson<HomeMacroReleaseContextPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/macro-release-context?${params.toString()}`,
      );
    },
    getHomeResearchReports: (reportDate: string, limit = 5) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        limit: String(limit),
      });
      return requestJson<HomeResearchReportsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/research-reports?${params.toString()}`,
      );
    },
    getHomeIncomeTrend: (reportDate: string, window = 7) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        window: String(window),
      });
      return requestJson<HomeIncomeTrendPayload>(
        fetchImpl,
        baseUrl,
        `/ui/home/income-trend?${params.toString()}`,
      );
    },
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
    getRiskOverview: () =>
      requestJson<RiskOverviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/risk/overview",
      ),
    getRiskTensorDates: () =>
      requestJson<RiskTensorDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/risk/tensor/dates",
      ),
    getRiskTensor: (reportDate: string) =>
      requestJson<RiskTensorPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getRiskTensorHistory: (reportDate: string, periods = 24) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        periods: String(periods),
      });
      return requestJson<RiskTensorHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor/history?${params.toString()}`,
      );
    },
    getRiskScenarioStress: (reportDate: string) =>
      requestJson<RiskScenarioStressPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/scenario-stress?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    async getPlaceholderSnapshot(key: string) {
      return buildReadinessPlaceholderEnvelope(key);
    },
  };
}
