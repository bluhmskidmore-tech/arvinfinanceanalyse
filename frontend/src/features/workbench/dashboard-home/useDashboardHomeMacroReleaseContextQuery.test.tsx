import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import type { ApiEnvelope, HomeMacroReleaseContextPayload } from "../../../api/contracts";
import { useDashboardHomeMacroReleaseContextQuery } from "./useDashboardHomeMacroReleaseContextQuery";

const envelope = {
  result_meta: {
    trace_id: "tr_home_macro_release_context",
    basis: "analytical",
    result_kind: "home.macro_release_context",
    formal_use_allowed: false,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-07-16T00:00:00Z",
  },
  result: {
    window_start_date: "2026-07-16",
    window_end_date: "2026-08-30",
    history_items: [],
    coverage: {
      configured_count: 8,
      ready_count: 3,
      partial_count: 0,
      stale_count: 0,
      fallback_count: 0,
      source_pending_count: 5,
      error_count: 0,
    },
    warnings: [],
  },
} satisfies ApiEnvelope<HomeMacroReleaseContextPayload>;

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function buildClient(
  getHomeMacroReleaseContext: ApiClient["getHomeMacroReleaseContext"],
): ApiClient {
  return {
    ...createApiClient({ mode: "real" }),
    getHomeMacroReleaseContext,
  };
}

describe("useDashboardHomeMacroReleaseContextQuery", () => {
  it("does not request while the deferred event section is disabled", () => {
    const method = vi.fn<ApiClient["getHomeMacroReleaseContext"]>(async () => envelope);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(
      () =>
        useDashboardHomeMacroReleaseContextQuery({
          dataClient: buildClient(method),
          enabled: false,
          getTodayIsoDate: () => "2026-07-16",
        }),
      { wrapper: createWrapper(queryClient) },
    );

    expect(method).not.toHaveBeenCalled();
    expect(result.current.windowStartDate).toBe("2026-07-16");
    expect(result.current.windowEndDate).toBe("2026-08-30");
  });

  it("uses its own today-to-plus-45-day window and a complete cache key", async () => {
    const method = vi.fn<ApiClient["getHomeMacroReleaseContext"]>(async () => envelope);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, refetchOnWindowFocus: false } },
    });

    const { result } = renderHook(
      () =>
        useDashboardHomeMacroReleaseContextQuery({
          dataClient: buildClient(method),
          enabled: true,
          historyLimit: 8,
          getTodayIsoDate: () => "2026-07-16",
        }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.macroReleaseContextQuery.isSuccess).toBe(true));
    expect(method).toHaveBeenCalledOnce();
    expect(method).toHaveBeenCalledWith({
      startDate: "2026-07-16",
      endDate: "2026-08-30",
      historyLimit: 8,
    });
    expect(result.current.windowStartDate).toBe("2026-07-16");
    expect(result.current.windowEndDate).toBe("2026-08-30");
    expect(queryClient.getQueryCache().getAll()[0]?.queryKey).toEqual([
      "home",
      "macro-release-context",
      "real",
      "2026-07-16",
      "2026-08-30",
      8,
    ]);
  });
});
