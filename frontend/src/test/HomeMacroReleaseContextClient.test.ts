import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { createDeferredApiClient } from "../api/clientContext";
import { createMockHomeExecutiveClient, createRealHomeExecutiveClient } from "../api/homeExecutiveClient";
import type { ApiEnvelope, HomeMacroReleaseContextPayload } from "../api/contracts";

const emptyEnvelope: ApiEnvelope<HomeMacroReleaseContextPayload> = {
  result_meta: {
    trace_id: "tr_home_macro_release_context",
    basis: "analytical",
    result_kind: "home.macro_release_context",
    formal_use_allowed: false,
    source_version: "sv_empty",
    vendor_version: "vv_empty",
    rule_version: "rv_home_macro_release_context_v1",
    cache_version: "cv_home_macro_release_context_v1",
    quality_flag: "warning",
    vendor_status: "vendor_unavailable",
    fallback_mode: "none",
    source_surface: "market_data",
    scenario_flag: false,
    generated_at: "2026-07-16T00:00:00Z",
  },
  result: {
    window_start_date: "2026-07-16",
    window_end_date: "2026-08-30",
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
};

describe("home macro release context client", () => {
  it("serializes the complete natural-date window and preserves the envelope", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(emptyEnvelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createRealHomeExecutiveClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    });

    const result = await client.getHomeMacroReleaseContext({
      startDate: "2026-07-16",
      endDate: "2026-08-30",
      historyLimit: 8,
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/ui/home/macro-release-context?start_date=2026-07-16&end_date=2026-08-30&history_limit=8",
      { headers: { Accept: "application/json" } },
    );
    expect(result).toEqual(emptyEnvelope);
  });

  it("surfaces the backend error detail", async () => {
    const client = createRealHomeExecutiveClient({
      fetchImpl: vi.fn<typeof fetch>(async () =>
        new Response(JSON.stringify({ detail: "macro source unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
      baseUrl: "http://backend.local",
    });

    await expect(
      client.getHomeMacroReleaseContext({
        startDate: "2026-07-16",
        endDate: "2026-08-30",
        historyLimit: 8,
      }),
    ).rejects.toThrow("macro source unavailable");
  });

  it("returns an explicit empty analytical envelope in mock mode", async () => {
    const result = await createMockHomeExecutiveClient().getHomeMacroReleaseContext({
      startDate: "2026-07-16",
      endDate: "2026-08-30",
      historyLimit: 8,
    });

    expect(result.result.history_items).toEqual([]);
    expect(result.result.coverage.ready_count).toBe(0);
    expect(JSON.stringify(result)).not.toContain("latest_value");
    expect(result.result_meta.basis).toBe("analytical");
    expect(result.result_meta.formal_use_allowed).toBe(false);
  });

  it("routes the new method through the lightweight deferred client only", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(emptyEnvelope), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createDeferredApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getHomeMacroReleaseContext({
      startDate: "2026-07-16",
      endDate: "2026-08-30",
      historyLimit: 8,
    });

    const clientSource = readFileSync(resolve(process.cwd(), "src/api/client.ts"), "utf8");
    const contextSource = readFileSync(resolve(process.cwd(), "src/api/clientContext.ts"), "utf8");
    expect(contextSource).toContain('"getHomeMacroReleaseContext"');
    expect(clientSource).not.toContain("/ui/home/macro-release-context");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
