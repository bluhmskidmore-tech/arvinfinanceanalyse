import { describe, expect, it, vi } from "vitest";

import { PNL_BY_BUSINESS_INSIGHTS_TIMEOUT_MS, createRealPnlBusinessClient } from "./pnlClient";
import { DEFAULT_REQUEST_JSON_TIMEOUT_MS } from "./transport";

/** Mirrors the real backend envelope from contracts/core.ts (ResultMeta). */
const fullResultMeta = {
  trace_id: "tr_test",
  basis: "formal",
  result_kind: "pnl.by_business",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_none",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-08-13T09:00:00Z",
};

/** Mirrors `PnlByBusinessPayload` (see contracts/pnl.ts) with a single row. */
const validPnlByBusinessResult = {
  report_date: "2026-06-30",
  source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
  summary: {
    business_count: 1,
    total_pnl: "100.00",
    total_scale_amount: "1000.00",
    interest_income_514: "50.00",
    fair_value_change_516: "30.00",
    capital_gain_517: "20.00",
    manual_adjustment: "0.00",
    pnl_row_count: 1,
    traced_pnl_row_count: 1,
    untraced_pnl_row_count: 0,
  },
  rows: [
    {
      report_date: "2026-06-30",
      business_type_primary: "invest",
      business_type: "bond",
      currency_basis: "CNY",
      interest_income_514: "50.00",
      fair_value_change_516: "30.00",
      capital_gain_517: "20.00",
      manual_adjustment: "0.00",
      total_pnl: "100.00",
      scale_amount: "1000.00",
      yield_pct: "5.00",
      pnl_row_count: 1,
      balance_row_count: 1,
    },
  ],
};

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  } as unknown as Response;
}

function makeClient(fetchImpl: typeof fetch) {
  return createRealPnlBusinessClient({ fetchImpl, baseUrl: "http://localhost:8000" });
}

describe("createRealPnlBusinessClient.getPnlByBusiness contract validation", () => {
  it("resolves for a well-formed envelope with all sampled key fields present", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ result_meta: fullResultMeta, result: validPnlByBusinessResult }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).resolves.toMatchObject({
      result: { report_date: "2026-06-30" },
    });
  });

  it("rejects into the contract-error channel when a key amount field is missing", async () => {
    const { total_pnl: _total_pnl, ...summaryWithoutTotalPnl } = validPnlByBusinessResult.summary;
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        result_meta: fullResultMeta,
        result: { ...validPnlByBusinessResult, summary: summaryWithoutTotalPnl },
      }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).rejects.toThrow(
      "Invalid ApiEnvelope from http://localhost:8000/api/pnl/by-business?report_date=2026-06-30: missing `result.summary.total_pnl`",
    );
  });

  it("rejects when the report_date field has the wrong type (backend rename/typo case)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        result_meta: fullResultMeta,
        result: { ...validPnlByBusinessResult, report_date: 20260630 },
      }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).rejects.toThrow(
      "`result.report_date` is a number, expected string",
    );
  });

  it("rejects when rows is not an array", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        result_meta: fullResultMeta,
        result: { ...validPnlByBusinessResult, rows: "not-an-array" },
      }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).rejects.toThrow(
      "`result.rows` is a string, expected array",
    );
  });

  it("rejects when summary.pnl_row_count is serialized as a string instead of a number", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        result_meta: fullResultMeta,
        result: {
          ...validPnlByBusinessResult,
          summary: { ...validPnlByBusinessResult.summary, pnl_row_count: "1" },
        },
      }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).rejects.toThrow(
      "`result.summary.pnl_row_count` is a string, expected number",
    );
  });

  it("still rejects an envelope missing result_meta (shell check unaffected)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ result: validPnlByBusinessResult }),
    ) as unknown as typeof fetch;

    await expect(makeClient(fetchImpl).getPnlByBusiness("2026-06-30")).rejects.toThrow(
      "missing `result_meta`",
    );
  });
});

describe("createRealPnlBusinessClient.getPnlByBusinessInsights request timeout", () => {
  const insightsPath = "/api/pnl/by-business-insights?year=2026&as_of_date=2026-07-31";

  it("outlives the 60s transport default and only aborts at the endpoint-specific 180s", async () => {
    expect(PNL_BY_BUSINESS_INSIGHTS_TIMEOUT_MS).toBeGreaterThan(DEFAULT_REQUEST_JSON_TIMEOUT_MS);
    vi.useFakeTimers();
    try {
      // Never resolves on its own; rejects like a real fetch once the transport aborts it.
      const fetchImpl = vi.fn(
        (_url: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
            );
          }),
      ) as unknown as typeof fetch;

      let rejection: unknown = null;
      const request = makeClient(fetchImpl)
        .getPnlByBusinessInsights(2026, "2026-07-31")
        .catch((error: unknown) => {
          rejection = error;
        });

      await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_JSON_TIMEOUT_MS);
      expect(fetchImpl).toHaveBeenCalledWith(
        `http://localhost:8000${insightsPath}`,
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
      expect(rejection).toBeNull();

      await vi.advanceTimersByTimeAsync(
        PNL_BY_BUSINESS_INSIGHTS_TIMEOUT_MS - DEFAULT_REQUEST_JSON_TIMEOUT_MS,
      );
      await request;
      expect(rejection).toBeInstanceOf(Error);
      expect((rejection as Error).message).toBe(`Request timed out: ${insightsPath}`);
    } finally {
      vi.useRealTimers();
    }
  });
});
