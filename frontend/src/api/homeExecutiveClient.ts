import type {
  ApiEnvelope,
  GetHomeSnapshotOptions,
  GetHomeMacroReleaseContextOptions,
  HomeIncomeTrendPayload,
  HomeMacroReleaseContextPayload,
  HomeResearchReportsPayload,
} from "./contracts";
import { fetchHomeSnapshotEnvelope } from "./executiveHomeSnapshotFetch";
import { readHttpJsonDetail } from "./httpResponseError";
import type { ExecutiveClientMethods } from "./executiveClient";

type FetchLike = typeof fetch;

export type HomeExecutiveClientMethods = Pick<
  ExecutiveClientMethods,
  | "getHomeSnapshot"
  | "getHomeMacroReleaseContext"
  | "getHomeResearchReports"
  | "getHomeIncomeTrend"
>;

type HomeExecutiveClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

export function createRealHomeExecutiveClient({
  fetchImpl,
  baseUrl,
}: HomeExecutiveClientFactoryOptions): HomeExecutiveClientMethods {
  return {
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
  };
}
