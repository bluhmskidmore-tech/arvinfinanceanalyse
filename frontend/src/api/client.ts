import type {
  ApiEnvelope,
  DashboardSnapshot,
  HealthResponse,
  PlaceholderSnapshot,
} from "./contracts";
import {
  dashboardSnapshot,
  placeholderSnapshots,
} from "../mocks/workbench";

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

const buildMeta = (resultKind: string) => ({
  trace_id: `mock_${resultKind}`,
  basis: "mock" as const,
  result_kind: resultKind,
  scenario_flag: false,
  source_version: "sv_mock_shell_v1",
  rule_version: "rv_shell_placeholder_v1",
  cache_version: "cv_shell_placeholder_v1",
  quality_flag: "ok" as const,
  generated_at: "2026-04-09T08:30:00Z",
});

export const apiClient = {
  async getHealth(): Promise<HealthResponse> {
    await delay();

    return {
      service: "moss-frontend-shell",
      status: "ok",
      checkedAt: "2026-04-09T08:30:00Z",
    };
  },

  async getDashboardSnapshot(): Promise<ApiEnvelope<DashboardSnapshot>> {
    await delay();

    return {
      result_meta: buildMeta("workbench_shell.dashboard"),
      result: dashboardSnapshot,
    };
  },

  async getPlaceholderSnapshot(
    key: string,
  ): Promise<ApiEnvelope<PlaceholderSnapshot>> {
    await delay();

    return {
      result_meta: buildMeta(`workbench_shell.${key}`),
      result:
        placeholderSnapshots[key] ??
        placeholderSnapshots["dashboard"],
    };
  },
};
