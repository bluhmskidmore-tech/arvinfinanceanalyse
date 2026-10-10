import { describe, expect, it, vi } from "vitest";

import { createRealBalanceAnalysisClient } from "./balanceAnalysisClient";
import { requestActionJson, requestBlob, requestJson, requestText } from "./transport";

describe("balance overview domain composition", () => {
  it.each([
    ["getBalanceAnalysisOverview", "overview"],
    ["getBalanceAnalysisSummaryByBasis", "summary-by-basis"],
  ] as const)("preserves generation through the domain %s request wrapper", async (method, endpoint) => {
    const response = { result: { report_date: "2026-08-31" }, result_meta: { basis: "formal" } };
    const fetchImpl = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(response)));
    const requestSpy = vi.fn();
    const client = createRealBalanceAnalysisClient({
      fetchImpl,
      baseUrl: "https://moss.test",
      requestJson: <T>(fetchImpl: typeof fetch, baseUrl: string, path: string) => {
        requestSpy(fetchImpl, baseUrl, path);
        return requestJson<T>(fetchImpl, baseUrl, path);
      },
      requestActionJson,
      requestBlob,
      requestText,
    });

    await expect(client[method]({
      reportDate: "2026-08-31",
      positionScope: "liability",
      currencyBasis: "native",
      generation: "balance/generation + 1",
    })).resolves.toEqual(response);

    expect(requestSpy).toHaveBeenCalledExactlyOnceWith(
      fetchImpl,
      "https://moss.test",
      `/ui/balance-analysis/${endpoint}?report_date=2026-08-31&position_scope=liability&currency_basis=native&generation=balance%2Fgeneration+%2B+1`,
    );
  });
});
