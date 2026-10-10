import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { createDeferredApiClient } from "../api/clientContext";

const reads: Array<[string, (client: ApiClient) => Promise<unknown>]> = [
  ["market overview", (client) => client.getMarketOverviewSnapshot()],
  ["home market ticker", (client) => client.getChoiceMacroLatest()],
];

describe.each([
  ["eager", createApiClient],
  ["deferred", createDeferredApiClient],
])("%s real API data boundary", (_name, createClient) => {
  it.each(reads)("propagates network failure for %s", async (_label, read) => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Network unavailable"));
    const client = createClient({ mode: "real", baseUrl: "http://backend.local", fetchImpl });

    await expect(read(client)).rejects.toThrow("Network unavailable");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(client.mode).toBe("real");
  });

  it.each(reads)("propagates non-success response for %s", async (_label, read) => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Source temporarily unavailable" }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    ));
    const client = createClient({ mode: "real", baseUrl: "http://backend.local", fetchImpl });

    await expect(read(client)).rejects.toThrow("Source temporarily unavailable");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it.each(reads)("preserves a formal empty response for %s", async (_label, read) => {
    const empty = {
      result_meta: { basis: "formal", fallback_mode: "none" },
      result: { series: [] },
    };
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(
      JSON.stringify(empty),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    const client = createClient({ mode: "real", baseUrl: "http://backend.local", fetchImpl });

    await expect(read(client)).resolves.toEqual(empty);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
