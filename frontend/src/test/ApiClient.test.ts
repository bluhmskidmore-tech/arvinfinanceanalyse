import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("createApiClient", () => {
  it("uses mock mode by default", async () => {
    const client = createApiClient({ mode: "mock" });

    const payload = await client.getOverview();

    expect(payload.result_meta.basis).toBe("mock");
    expect(payload.result.title).toBe("经营总览");
  });

  it("uses real mode to fetch executive endpoints", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        result_meta: {
          trace_id: "tr_overview",
          basis: "formal",
          result_kind: "executive.overview",
          formal_use_allowed: true,
          source_version: "sv_real",
          vendor_version: "vv_none",
          rule_version: "rv_real",
          cache_version: "cv_real",
          quality_flag: "ok",
          scenario_flag: false,
          generated_at: "2026-04-09T09:00:00Z",
        },
        result: {
          title: "经营总览",
          metrics: [],
        },
      }),
    }));

    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await client.getOverview();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/ui/home/overview",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });
});
