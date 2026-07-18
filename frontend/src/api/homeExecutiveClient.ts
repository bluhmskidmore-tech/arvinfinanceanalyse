import type {
  ApiEnvelope,
  GetHomeSnapshotOptions,
  GetHomeMacroReleaseContextOptions,
  HomeIncomeTrendPayload,
  HomeMacroReleaseContextPayload,
  HomeResearchReportsPayload,
  HomeSnapshotPayload,
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

type HomeExecutiveMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  Pick<typeof import("../mocks/workbench"), "mockHomeSnapshot">;

let mockBundlePromise: Promise<HomeExecutiveMockBundle> | null = null;

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

async function loadMockBundle(): Promise<HomeExecutiveMockBundle> {
  if (!mockBundlePromise) {
    mockBundlePromise = Promise.all([
      import("../mocks/mockApiEnvelope"),
      import("../mocks/workbench"),
    ]).then(([apiEnvelopeModule, workbench]) => ({
      buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
      mockHomeSnapshot: workbench.mockHomeSnapshot,
    }));
  }
  return mockBundlePromise;
}

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

export function createMockHomeExecutiveClient(): HomeExecutiveClientMethods {
  return {
    async getHomeSnapshot(_options?: GetHomeSnapshotOptions) {
      await delay();
      const bundle = await loadMockBundle();
      return bundle.buildMockApiEnvelope<HomeSnapshotPayload>(
        "home.snapshot",
        bundle.mockHomeSnapshot,
      );
    },
    async getHomeMacroReleaseContext(options: GetHomeMacroReleaseContextOptions) {
      await delay();
      const bundle = await loadMockBundle();
      return bundle.buildMockApiEnvelope<HomeMacroReleaseContextPayload>(
        "home.macro_release_context",
        {
          window_start_date: options.startDate,
          window_end_date: options.endDate,
          history_items: [],
          coverage: {
            configured_count: 8,
            ready_count: 0,
            partial_count: 0,
            stale_count: 0,
            fallback_count: 0,
            source_pending_count: 8,
            error_count: 0,
          },
          warnings: [],
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
        },
      );
    },
    async getHomeResearchReports(reportDate: string, limit = 5) {
      await delay();
      void limit;
      const bundle = await loadMockBundle();
      return bundle.buildMockApiEnvelope<HomeResearchReportsPayload>(
        "home.research_reports",
        {
          report_date: reportDate,
          source_status: "empty",
          items: [],
          warnings: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getHomeIncomeTrend(reportDate: string, window = 7) {
      await delay();
      const bundle = await loadMockBundle();
      return bundle.buildMockApiEnvelope<HomeIncomeTrendPayload>(
        "home.income_trend",
        {
          report_date: reportDate,
          window,
          source_status: "empty",
          points: [],
          missing_components: [],
          warnings: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
  };
}
