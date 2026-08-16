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

    const result = await fetchDataHealth({ fetchImpl, baseUrl: "http://backend.local" });

    expect(result.kind).toBe("ok");
    expect(result.kind === "ok" && result.payload.overall_status).toBe("warn");
    expect(result.kind === "ok" && result.payload.sections).toHaveLength(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local${DATA_HEALTH_PATH}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps 404 (capability not available) to missing instead of error", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "not available" }), { status: 404 }),
    ) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toEqual({ kind: "missing" });
  });

  it("maps an explicitly empty envelope result to missing", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ result_meta: {}, result: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toEqual({ kind: "missing" });
  });

  it("maps other non-2xx statuses to error (呈现错误态，不整面隐藏)", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("oops", { status: 503 }),
    ) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toEqual({
      kind: "error",
      reason: "HTTP 503",
    });
  });

  it("maps network failures to error with the failure reason", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("network down");
    }) as unknown as typeof fetch;

    await expect(fetchDataHealth({ fetchImpl })).resolves.toEqual({
      kind: "error",
      reason: "network down",
    });
  });

  it("maps JSON parse failures to error", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("not-json", { status: 200 }),
    ) as unknown as typeof fetch;

    const result = await fetchDataHealth({ fetchImpl });
    expect(result.kind).toBe("error");
  });
});
