import { describe, expect, it, vi } from "vitest";

import { createRealStockAnalysisWorkbenchClient } from "./stockAnalysisWorkbenchClient";
import { createRealMarketDataClient } from "./marketDataClient";

describe("stockAnalysisWorkbenchClient", () => {
  it("preserves the governed workbench query contract", async () => {
    const payload = {
      result_meta: { basis: "analytical" },
      result: { modules: {}, module_states: [], links: {} },
    };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createRealStockAnalysisWorkbenchClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    });

    const result = await client.getStockAnalysisWorkbench({
      asOfDate: " 2026-04-29 ",
      include: [" main ", "", " evidence_summary "],
      sectorWindowDays: 20,
      topK: 10,
    });

    expect(result).toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/ui/market-data/stock-analysis/workbench?as_of_date=2026-04-29&include=main%2Cevidence_summary&sector_window_days=20&top_k=10",
      { headers: { Accept: "application/json" } },
    );
  });

  it("stays query-compatible with the public market-data client", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: { modules: {}, module_states: [], links: {} },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const options = {
      asOfDate: " 2026-04-29 ",
      include: [" main ", "", " evidence_summary "],
      sectorWindowDays: 20,
      topK: 10,
    };

    await createRealStockAnalysisWorkbenchClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    }).getStockAnalysisWorkbench(options);
    await createRealMarketDataClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    }).getStockAnalysisWorkbench(options);

    expect(vi.mocked(fetchImpl).mock.calls.map(([url]) => url)).toEqual([
      "http://backend.local/ui/market-data/stock-analysis/workbench?as_of_date=2026-04-29&include=main%2Cevidence_summary&sector_window_days=20&top_k=10",
      "http://backend.local/ui/market-data/stock-analysis/workbench?as_of_date=2026-04-29&include=main%2Cevidence_summary&sector_window_days=20&top_k=10",
    ]);
  });

  it("surfaces backend error detail", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "workbench unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createRealStockAnalysisWorkbenchClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    });

    await expect(client.getStockAnalysisWorkbench()).rejects.toThrow(
      "workbench unavailable",
    );
  });

  it("falls back to a status-bearing error when the response has no detail", async () => {
    const fetchImpl = vi.fn(async () => new Response("not-json", { status: 502 })) as unknown as typeof fetch;
    const client = createRealStockAnalysisWorkbenchClient({
      fetchImpl,
      baseUrl: "http://backend.local",
    });

    await expect(client.getStockAnalysisWorkbench()).rejects.toThrow(
      "Request failed: /ui/market-data/stock-analysis/workbench (502)",
    );
  });
});
