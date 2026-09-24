import { describe, expect, it, vi } from "vitest";

import { fetchPretradeChecklist, PRETRADE_CHECKLIST_PATH } from "./pretradeChecklistClient";

describe("pretradeChecklistClient", () => {
  it("unwraps the envelope result on success", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            result_meta: { basis: "analytical" },
            result: { as_of_date: "2026-08-10", checklist_status: "ok", items: [] },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    ) as unknown as typeof fetch;

    const result = await fetchPretradeChecklist({ fetchImpl, baseUrl: "http://backend.local" });

    expect(result.kind).toBe("ok");
    expect(result.kind === "ok" && result.payload.as_of_date).toBe("2026-08-10");
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local${PRETRADE_CHECKLIST_PATH}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps 404 (capability not available) to missing instead of error", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "not available" }), { status: 404 }),
    ) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toEqual({ kind: "missing" });
  });

  it("maps an explicitly empty envelope result to missing", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ result_meta: {}, result: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toEqual({ kind: "missing" });
  });

  it("maps other non-2xx statuses to error (呈现错误态，不整面隐藏)", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("oops", { status: 503 }),
    ) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toEqual({
      kind: "error",
      reason: "HTTP 503",
    });
  });

  it("maps network failures to error with the failure reason", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("network down");
    }) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toEqual({
      kind: "error",
      reason: "network down",
    });
  });

  it("maps JSON parse failures to error", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("not-json", { status: 200 }),
    ) as unknown as typeof fetch;

    const result = await fetchPretradeChecklist({ fetchImpl });
    expect(result.kind).toBe("error");
  });
});
