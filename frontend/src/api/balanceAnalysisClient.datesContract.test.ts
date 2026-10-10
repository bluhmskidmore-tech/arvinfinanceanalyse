import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";
import { createDeferredApiClient } from "./clientContext";

const baseUrl = "http://balance-dates.test";
const path = "/ui/balance-analysis/dates";

function datesClient(result: unknown, deferred: boolean) {
  const fetchImpl = vi.fn(async () =>
    new Response(JSON.stringify({ result_meta: {}, result }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const options = { mode: "real" as const, baseUrl, fetchImpl };
  return {
    client: deferred ? createDeferredApiClient(options) : createApiClient(options),
    fetchImpl,
  };
}

describe.each([
  ["full client", false],
  ["page deferred client", true],
] as const)("balance analysis dates contract in %s", (_name, deferred) => {
  it.each([
    ["null result", null],
    ["missing report_dates", {}],
    ["non-array report_dates", { report_dates: "2026-02-28" }],
  ])("rejects HTTP 200 with %s at the API boundary", async (_case, result) => {
    const { client, fetchImpl } = datesClient(result, deferred);

    await expect(client.getBalanceAnalysisDates()).rejects.toThrow(
      /Invalid ApiEnvelope.*result\.report_dates/,
    );
    expect(fetchImpl).toHaveBeenCalledWith(
      `${baseUrl}${path}`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("accepts a valid empty date list as no data", async () => {
    const { client } = datesClient({ report_dates: [] }, deferred);

    await expect(client.getBalanceAnalysisDates()).resolves.toMatchObject({
      result: { report_dates: [] },
    });
  });
});
