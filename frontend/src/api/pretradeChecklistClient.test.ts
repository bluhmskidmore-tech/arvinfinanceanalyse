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

    const payload = await fetchPretradeChecklist({ fetchImpl, baseUrl: "http://backend.local" });

    expect(payload?.as_of_date).toBe("2026-08-10");
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local${PRETRADE_CHECKLIST_PATH}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("maps 404 (checklist not available) to null instead of throwing", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ detail: "not available" }), { status: 404 }),
    ) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toBeNull();
  });

  it("maps other non-2xx statuses to null (整面隐藏，不抛错)", async () => {
    const fetchImpl = vi.fn(
      async () => new Response("oops", { status: 503 }),
    ) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toBeNull();
  });

  it("maps network failures to null", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("network down");
    }) as unknown as typeof fetch;

    await expect(fetchPretradeChecklist({ fetchImpl })).resolves.toBeNull();
  });
});
