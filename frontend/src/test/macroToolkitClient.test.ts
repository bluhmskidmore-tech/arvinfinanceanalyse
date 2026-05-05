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
});
