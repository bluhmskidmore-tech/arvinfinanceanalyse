import type { GetHomeSnapshotOptions, GetHomeMacroReleaseContextOptions, HomeMacroReleaseContextPayload, HomeResearchReportsPayload, HomeIncomeTrendPayload, HomeSnapshotPayload } from "../api/contracts";
import type { HomeExecutiveClientMethods } from "../api/homeExecutiveClient";
type HomeExecutiveMockBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  Pick<typeof import("./workbench"), "mockHomeSnapshot">;

let mockBundlePromise: Promise<HomeExecutiveMockBundle> | null = null;

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

async function loadMockBundle(): Promise<HomeExecutiveMockBundle> {
  if (!mockBundlePromise) {
    mockBundlePromise = Promise.all([
      import("./mockApiEnvelope"),
      import("./workbench"),
    ]).then(([apiEnvelopeModule, workbench]) => ({
      buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
      mockHomeSnapshot: workbench.mockHomeSnapshot,
    }));
  }
  return mockBundlePromise;
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
