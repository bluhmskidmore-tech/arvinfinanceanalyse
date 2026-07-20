import { describe, expect, it, vi } from "vitest";

import { createRealMacroToolkitClient } from "../api/macroToolkitClient";
import { createMockMacroToolkitClient } from "../api/macroToolkitMockClient";

describe("macroToolkitClient", () => {
  it("keeps the M9 mock capability aligned with Choice credit history", async () => {
    const envelope = await createMockMacroToolkitClient().getMacroToolkitScripts();
    const capability = envelope.result.capabilities.find((item) => item.key === "credit_spread_risk");

    expect(capability).toMatchObject({
      data_status: "ready",
      data_hit_count: 3,
      data_required_count: 3,
    });
    expect(capability?.evidence.map((item) => item.series_id)).toEqual([
      "EMM00166659",
      "EMM00166462",
      "EMM00166683",
    ]);
  });

  it("keeps the M7 mock policy rate aligned with fresh Choice history", async () => {
    const envelope = await createMockMacroToolkitClient().getMacroToolkitAnalysis();
    const capability = envelope.result.capability_results.find(
      (item) => item.key === "monetary_policy_stance",
    );
    const policyRate = capability?.input_evidence?.inputs.find(
      (item) => item.field === "policy_rate_7d",
    );

    expect(policyRate).toMatchObject({
      available: true,
      stale: false,
      row_count: 706,
      latest_date: "2026-07-20",
      series_id: "EMM00088132",
      source: "choice",
      value: 1.4,
    });
    expect(capability?.warnings).not.toContain("POLICY_RATE_7D_STALE");
  });

  it("surfaces a timeout when toolkit read endpoints do not answer", async () => {
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
      const client = createRealMacroToolkitClient({
        fetchImpl,
        baseUrl: "http://localhost:8000",
      });

      const pending = expect(client.getMacroToolkitAnalysis()).rejects.toThrow(
        "Macro toolkit request timed out: /ui/macro/toolkit/analysis",
      );
      await vi.advanceTimersByTimeAsync(90_000);
      await pending;
    } finally {
      vi.useRealTimers();
    }
  });

  it("aborts strategy summary reads when the caller signal is canceled", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(
      (_url: string | URL | Request, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    const pending = client.getMacroToolkitStrategySummaries({ signal: controller.signal });
    controller.abort();

    await expect(pending).rejects.toThrow("aborted");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/ui/macro/toolkit/analysis/strategy-summaries",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

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
            choice_stock_refresh: {
              permission: {
                mode: "scoped_refresh",
                allowed: true,
                resource: "macro_toolkit.choice_stock",
                actions: ["history", "factor_snapshot"],
              },
            },
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

  it("posts source backfill refresh requests to the toolkit route", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: {
            refresh: {
              status: "completed",
              alias: "M0041813",
              series_ids: ["NCD.SHIBOR.3M"],
              total_added: 42,
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    await client.refreshMacroSourceBackfill({
      alias: "M0041813",
      startDate: "2026-04-01",
      endDate: "2026-04-30",
      sources: ["tushare_macro"],
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/ui/macro/toolkit/source-backfill/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          alias: "M0041813",
          start_date: "2026-04-01",
          end_date: "2026-04-30",
          sources: ["tushare_macro"],
        }),
      }),
    );
  });

  it("posts commodity futures refresh requests to the toolkit route", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: {
            refresh: {
              status: "dry_run",
              dry_run: true,
              product_count: 2,
              row_count: 0,
              products: [{ product_code: "RB" }, { product_code: "CU" }],
              table: "fact_commodity_futures_daily",
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    await client.refreshCommodityFutures({
      startDate: "2026-05-01",
      endDate: "2026-06-01",
      products: ["RB", "CU"],
      dryRun: true,
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/ui/macro/toolkit/commodity-futures/refresh",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          start_date: "2026-05-01",
          end_date: "2026-06-01",
          products: ["RB", "CU"],
          dry_run: true,
        }),
      }),
    );
  });

  it("requests core analysis first and reads deferred strategy summaries separately", async () => {
    const fetchImpl = vi.fn(async (url: string | URL | Request) =>
      new Response(
        JSON.stringify({
          result_meta: { basis: "analytical" },
          result: String(url).includes("strategy-summaries")
            ? { strategy_summaries: [], choice_stock_refresh: { status: "ready" } }
            : { runtime_status: { analysis_scope: "core" } },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const client = createRealMacroToolkitClient({
      fetchImpl,
      baseUrl: "http://localhost:8000",
    });

    await client.getMacroToolkitAnalysis({ detail: "core" });
    await client.getMacroToolkitStrategySummaries();

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/ui/macro/toolkit/analysis?detail=core",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/ui/macro/toolkit/analysis/strategy-summaries",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });
});
