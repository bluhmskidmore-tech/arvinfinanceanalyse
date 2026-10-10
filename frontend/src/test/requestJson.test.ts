import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("requestJson transport timeout", () => {
  it("aborts when the response does not arrive before the default timeout", async () => {
    vi.useFakeTimers();
    try {
      const fetchImpl = vi.fn(
        (_url: string | URL | Request, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => {
              reject(new DOMException("aborted", "AbortError"));
            });
          }),
      ) as unknown as typeof fetch;
      const client = createApiClient({
        mode: "real",
        baseUrl: "http://localhost:8000",
        fetchImpl,
      });

      const pending = expect(client.getOverview()).rejects.toThrow(
        "Request timed out: /ui/home/overview",
      );
      await vi.advanceTimersByTimeAsync(60_000);
      await pending;
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps successful responses on the normal path", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      return {
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
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-04-09T09:00:00Z",
          },
          result: {
            title: "经营总览",
            metrics: [],
          },
        }),
      };
    }) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://localhost:8000",
      fetchImpl,
    });

    await expect(client.getOverview()).resolves.toEqual(
      expect.objectContaining({
        result: expect.objectContaining({ title: "经营总览" }),
      }),
    );
  });
});
