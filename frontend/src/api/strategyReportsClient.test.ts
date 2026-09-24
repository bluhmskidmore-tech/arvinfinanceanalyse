import { describe, expect, it, vi } from "vitest";

import { fetchWalkForwardReport, WALK_FORWARD_REPORT_PATH } from "./strategyReportsClient";

describe("strategyReportsClient", () => {
  it("unwraps the envelope result on success", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            result_meta: { basis: "analytical" },
            result: { engine_version: "wf-2026.08", schedules: [] },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ) as unknown as typeof fetch;

    const payload = await fetchWalkForwardReport({ fetchImpl, baseUrl: "http://backend.local" });

    expect(payload?.engine_version).toBe("wf-2026.08");
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local${WALK_FORWARD_REPORT_PATH}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps 404 (report not generated) to null instead of throwing", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "not available" }), { status: 404 }),
    ) as unknown as typeof fetch;

    await expect(fetchWalkForwardReport({ fetchImpl })).resolves.toBeNull();
  });

  it("throws on other non-2xx statuses", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("oops", { status: 503 }),
    ) as unknown as typeof fetch;

    await expect(fetchWalkForwardReport({ fetchImpl })).rejects.toThrow(
      "walk-forward report request failed (503)",
    );
  });
});
