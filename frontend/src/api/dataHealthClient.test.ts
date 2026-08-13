import { describe, expect, it, vi } from "vitest";

import { DATA_HEALTH_PATH, fetchDataHealth } from "./dataHealthClient";

describe("dataHealthClient", () => {
  it("unwraps the envelope result on success", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            result_meta: { basis: "analytical" },
            result: {
              as_of_date: "2026-08-13",
              overall_status: "warn",
              sections: [{ key: "observation_freshness", status: "ok" }],
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ) as unknown as typeof fetch;

    const payload = await fetchDataHealth({ fetchImpl, baseUrl: "http://backend.local" });

    expect(payload?.overall_status).toBe("warn");
    expect(payload?.sections).toHaveLength(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local${DATA_HEALTH_PATH}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps 404 (overview not available) to null instead of throwing", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "not available" }), { status: 404 }),
    ) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toBeNull();
  });

  it("maps other non-2xx statuses to null (整面隐藏，不抛错)", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("oops", { status: 503 }),
    ) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toBeNull();
  });

  it("maps network failures to null", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("network down");
    }) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toBeNull();
  });
});
