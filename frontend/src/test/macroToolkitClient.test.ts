import { describe, expect, it, vi } from "vitest";

import { createRealMacroToolkitClient } from "../api/macroToolkitClient";

describe("macroToolkitClient", () => {
  it("posts CFFEX member-rank refresh requests to the backend route", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: {
            refresh: { row_count: 2 },
            cffex_member_rank: { status: "ok", row_count: 2 },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    await client.refreshCffexMemberRank({
      tradeDate: "2026-04-30",
      contracts: ["T.CFE"],
      sources: ["choice"],
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/ui/macro/toolkit/cffex-member-rank/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          trade_date: "2026-04-30",
          contracts: ["T.CFE"],
          sources: ["choice"],
        }),
      }),
    );
  });

  it("posts Choice stock refresh requests and reads refresh status", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: {
            refresh: { status: "queued", run_id: "choice_stock_refresh:test" },
            choice_stock_refresh: { permission: { mode: "identity_only" } },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    await client.refreshChoiceStock({
      asOfDate: "2026-04-30",
      refreshHistory: true,
      refreshFactors: true,
      factorMaxStockCount: null,
    });
    await client.getChoiceStockRefreshStatus("choice_stock_refresh:test");

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/macro/toolkit/choice-stock/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          as_of_date: "2026-04-30",
          refresh_history: true,
          refresh_factors: true,
          factor_max_stock_count: null,
        }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/macro/toolkit/choice-stock/refresh-status?run_id=choice_stock_refresh%3Atest",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });
});
