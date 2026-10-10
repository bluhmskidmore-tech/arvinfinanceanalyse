import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, useApiClient } from "../api/clientContext";
import {
  createGenerationScopedApiClient,
  SYSTEM_READ_GENERATION_HEADER,
} from "../api/systemReadGeneration";

// A real overview read must not load the full client or the balance demo fixtures.
vi.mock("../api/client", () => {
  throw new Error("Overview startup loaded the full API client");
});
vi.mock("../api/balanceAnalysisClient", () => {
  throw new Error("Overview startup loaded the full balance client");
});

const overviewOptions = {
  reportDate: "2026-08-31",
  positionScope: "all" as const,
  currencyBasis: "CNY" as const,
};
const overviewPath = "/ui/balance-analysis/overview?report_date=2026-08-31&position_scope=all&currency_basis=CNY";
const baseUrl = "https://moss.test/base";
const envelope = {
  result: {
    report_date: "2026-08-30",
    position_scope: "all",
    currency_basis: "CNY",
    total_market_value_amount: "123456789.01234567",
    asset_total_amortized_cost_amount: "0.00",
    liability_total_accrued_interest_amount: null,
  },
  result_meta: {
    basis: "formal",
    as_of_date: "2026-08-30",
    requested_report_date: "2026-08-31",
    resolved_report_date: "2026-08-30",
    fallback_mode: "latest_snapshot",
    quality_flag: "stale",
  },
  calibration: { amount_currency_basis: "CNY" },
};

function jsonResponse(payload: unknown, generation?: string, status = 200) {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (generation) headers.set(SYSTEM_READ_GENERATION_HEADER, generation);
  return new Response(JSON.stringify(payload), { status, headers });
}

function defaultProviderClient(fetchImpl: typeof fetch) {
  vi.stubGlobal("fetch", fetchImpl);
  return renderHook(() => useApiClient(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <ApiClientProvider>{children}</ApiClientProvider>
    ),
  }).result.current;
}

beforeEach(() => {
  vi.stubEnv("VITE_DATA_SOURCE", "real");
  vi.stubEnv("VITE_API_BASE_URL", `${baseUrl}/`);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("balance overview through the default deferred provider", () => {
  it("keeps lazy loading, encoded publication filters and the complete response unchanged", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(envelope));
    const client = defaultProviderClient(fetchImpl);
    expect(fetchImpl).not.toHaveBeenCalled();

    const result = await client.getBalanceAnalysisOverview({
      ...overviewOptions,
      generation: "balance/generation + 1",
    });

    expect(fetchImpl).toHaveBeenCalledExactlyOnceWith(
      `${baseUrl}${overviewPath}&generation=balance%2Fgeneration+%2B+1`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
    expect(result).toEqual(envelope);
  });

  it.each([undefined, ""])("omits an unset publication generation (%s)", async (generation) => {
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(envelope));
    await defaultProviderClient(fetchImpl).getBalanceAnalysisOverview({ ...overviewOptions, generation });
    expect(fetchImpl.mock.calls[0][0]).toBe(`${baseUrl}${overviewPath}`);
  });

  it.each([
    { name: "missing metadata", payload: { result: envelope.result } },
    { name: "null metadata", payload: { result: envelope.result, result_meta: null } },
    { name: "missing result", payload: { result_meta: envelope.result_meta } },
    { name: "array response", payload: [] },
  ])("rejects an invalid governed envelope: $name", async ({ payload }) => {
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(payload));
    await expect(defaultProviderClient(fetchImpl).getBalanceAnalysisOverview(overviewOptions))
      .rejects.toThrow("Invalid ApiEnvelope");
  });

  it("preserves null results for the existing no-data handling", async () => {
    const noData = { result: null, result_meta: { basis: "formal", as_of_date: null } };
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(noData));
    await expect(defaultProviderClient(fetchImpl).getBalanceAnalysisOverview(overviewOptions))
      .resolves.toEqual(noData);
  });

  it("retains read-generation headers separately from the overview publication generation", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(envelope, "system-generation"));
    const client = createGenerationScopedApiClient(defaultProviderClient(fetchImpl), "system-generation");
    await expect(client.getBalanceAnalysisOverview({ ...overviewOptions, generation: "balance-generation" }))
      .resolves.toEqual(envelope);

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(`${baseUrl}${overviewPath}&generation=balance-generation`);
    const headers = new Headers(init?.headers);
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get(SYSTEM_READ_GENERATION_HEADER)).toBe("system-generation");
  });

  it.each([undefined, "another-generation"])("still rejects mismatched response generations (%s)", async (generation) => {
    const fetchImpl = vi.fn<typeof fetch>(async () => jsonResponse(envelope, generation));
    const client = createGenerationScopedApiClient(defaultProviderClient(fetchImpl), "system-generation");
    await expect(client.getBalanceAnalysisOverview(overviewOptions)).rejects.toThrow("generation mismatch");
  });

  it("preserves backend error details on the deferred path", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "Selected publication is unavailable" }, undefined, 503),
    );
    await expect(defaultProviderClient(fetchImpl).getBalanceAnalysisOverview(overviewOptions))
      .rejects.toThrow("Selected publication is unavailable");
  });

  it("aborts a stalled overview request at the shared 60 second deadline", async () => {
    await import("../api/homeSupplementalClient");
    vi.useFakeTimers();
    const fetchImpl = vi.fn<typeof fetch>(() => new Promise(() => {}));
    const request = defaultProviderClient(fetchImpl).getBalanceAnalysisOverview(overviewOptions);
    // Observe rejection immediately so the timer does not produce an unhandled rejection.
    const outcome = request.then(() => null, (error: unknown) => error);
    await vi.dynamicImportSettled();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const signal = fetchImpl.mock.calls[0][1]?.signal;
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(59_999);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toEqual(new Error(`Request timed out: ${overviewPath}`));
  });
});
