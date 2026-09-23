import { describe, expect, it, vi } from "vitest";

import { createRealBalanceMovementClient } from "./balanceMovementClient";
import { createMockBalanceMovementClient } from "./balanceMovementMockClient";
import { DEFAULT_REQUEST_JSON_TIMEOUT_MS } from "./transport";

const baseUrl = "http://localhost:8000";
const datesPath = "/ui/balance-movement-analysis/dates?currency_basis=CNX";
const detailPath = "/ui/balance-movement-analysis?report_date=2026-06-30&currency_basis=CNX";
const refreshPath = "/ui/balance-movement-analysis/refresh?report_date=2026-06-30&currency_basis=CNX";

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("createRealBalanceMovementClient", () => {
  it.each(["dates", "analysis"] as const)("rejects HTTP 200 with an empty object for %s", async (endpoint) => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
    const request = endpoint === "dates"
      ? client.getBalanceMovementDates()
      : client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });

    await expect(request).rejects.toThrow(
      `Invalid ApiEnvelope from ${baseUrl}${endpoint === "dates" ? datesPath : detailPath}: missing \`result\``,
    );
  });

  it.each(["dates", "analysis"] as const)("rejects missing, null or malformed required fields inside %s envelopes", async (endpoint) => {
    const mockClient = createMockBalanceMovementClient();
    const valid = endpoint === "dates"
      ? await mockClient.getBalanceMovementDates()
      : await mockClient.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const fields = endpoint === "dates"
      ? ["report_dates", "currency_basis"]
      : ["report_date", "currency_basis", "rows", "summary", "trend_months", "business_trend_months", "accounting_controls", "excluded_controls"];
    const malformedResults: unknown[] = [null, {}, []];
    for (const field of fields) {
      const result: Record<string, unknown> = { ...valid.result };
      delete result[field];
      malformedResults.push(result, { ...valid.result, [field]: false });
    }
    for (const result of malformedResults) {
      const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ...valid, result }));
      const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
      const request = endpoint === "dates"
        ? client.getBalanceMovementDates()
        : client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
      await expect(request).rejects.toThrow("Invalid ApiEnvelope");
    }
  });

  it("preserves valid empty arrays and nullable optional detail sections", async () => {
    const mockClient = createMockBalanceMovementClient();
    const dates = await mockClient.getBalanceMovementDates();
    dates.result.report_dates = [];
    const detail = await mockClient.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    Object.assign(detail.result, {
      rows: [], trend_months: [], business_trend_months: [], accounting_controls: [], excluded_controls: [],
      zqtz_calibration_analysis: null, structure_migration_analysis: null, difference_attribution_waterfall: null,
      basis_movement_decomposition: null, zqtz_maturity_structure: null, zqtz_concentration_analysis: null,
    });
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(dates))
      .mockResolvedValueOnce(jsonResponse(detail));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates()).resolves.toEqual(dates);
    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" })).resolves.toEqual(detail);
  });

  it.each([null, {}, 1, "", "  "])("rejects an invalid date list entry %j", async (reportDate) => {
    const dates = await createMockBalanceMovementClient().getBalanceMovementDates();
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...dates,
      result: { ...dates.result, report_dates: [reportDate] },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates()).rejects.toThrow("Invalid ApiEnvelope");
  });

  it("rejects date lists for a different currency basis", async () => {
    const dates = await createMockBalanceMovementClient().getBalanceMovementDates("CNX");
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...dates,
      result: { ...dates.result, currency_basis: "CNY" },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates("CNX")).rejects.toThrow("does not match requested currency_basis");
  });

  it.each([
    ["report_date", "2026-05-31"],
    ["currency_basis", "CNY"],
  ] as const)("rejects detail results with a different %s", async (field, returnedValue) => {
    const detail = await createMockBalanceMovementClient().getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...detail,
      result: { ...detail.result, [field]: returnedValue },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" }))
      .rejects.toThrow(`does not match requested ${field}`);
  });

  it("rejects a detail envelope with an empty summary", async () => {
    const detail = await createMockBalanceMovementClient().getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...detail,
      result: { ...detail.result, summary: {} },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" }))
      .rejects.toThrow("Invalid ApiEnvelope");
  });

  it.each([
    "previous_balance_total", "current_balance_total", "balance_change_total",
    "zqtz_amount_total", "reconciliation_diff_total", "matched_bucket_count", "bucket_count",
  ] as const)("rejects a summary missing %s", async (field) => {
    const detail = await createMockBalanceMovementClient().getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const summary: Record<string, unknown> = { ...detail.result.summary };
    delete summary[field];
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...detail, result: { ...detail.result, summary },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" }))
      .rejects.toThrow("Invalid ApiEnvelope");
  });

  it.each([
    ["balance_change_total", "invalid"],
    ["matched_bucket_count", 1.5],
  ] as const)("rejects malformed summary %s", async (field, value) => {
    const detail = await createMockBalanceMovementClient().getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ...detail, result: { ...detail.result, summary: { ...detail.result.summary, [field]: value } },
    }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" }))
      .rejects.toThrow("Invalid ApiEnvelope");
  });

  it("accepts zero and scientific decimal values in the required summary", async () => {
    const detail = await createMockBalanceMovementClient().getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    detail.result.summary.balance_change_total = 0;
    detail.result.summary.previous_balance_total = "1E+3";
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(detail));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" })).resolves.toEqual(detail);
  });

  it("preserves GET payloads, default currency and encoded query parameters", async () => {
    const mockClient = createMockBalanceMovementClient();
    const dates = await mockClient.getBalanceMovementDates();
    const detail = await mockClient.getBalanceMovementAnalysis({
      reportDate: "2026-06-30 & revision=1", currencyBasis: "CNY/USD",
    });
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(dates))
      .mockResolvedValueOnce(jsonResponse(detail));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates()).resolves.toEqual(dates);
    await expect(client.getBalanceMovementAnalysis({
      reportDate: "2026-06-30 & revision=1",
      currencyBasis: "CNY/USD",
    })).resolves.toEqual(detail);
    expect(fetchImpl).toHaveBeenNthCalledWith(1, `${baseUrl}${datesPath}`, expect.objectContaining({
      headers: { Accept: "application/json" },
      signal: expect.any(AbortSignal),
    }));
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      `${baseUrl}/ui/balance-movement-analysis?report_date=2026-06-30%20%26%20revision%3D1&currency_basis=CNY%2FUSD`,
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("keeps refresh as a POST returning a plain JSON payload", async () => {
    const payload = await createMockBalanceMovementClient().refreshBalanceMovementAnalysis({
      reportDate: "2026-06-30",
    });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.refreshBalanceMovementAnalysis({ reportDate: "2026-06-30" })).resolves.toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledWith(`${baseUrl}${refreshPath}`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });
  });

  it.each(["dates", "analysis", "refresh"] as const)("preserves status-only HTTP errors for %s", async (endpoint) => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({ detail: "backend detail", run_id: "run_test" }, 503),
    );
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
    const request = endpoint === "dates"
      ? client.getBalanceMovementDates()
      : endpoint === "analysis"
        ? client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" })
        : client.refreshBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const path = endpoint === "dates" ? datesPath : endpoint === "analysis" ? detailPath : refreshPath;

    await expect(request).rejects.toMatchObject({
      name: "Error",
      message: `Request failed: ${path} (503)`,
    });
  });

  it("rejects a failed refresh without waiting for its error body", async () => {
    const response = new Response("", { status: 503 });
    const readErrorBody = vi.spyOn(response, "json").mockImplementation(
      () => new Promise<unknown>(() => undefined),
    );
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(response);
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
    let timeoutId!: ReturnType<typeof setTimeout>;
    try {
      const outcome = await Promise.race([
        client.refreshBalanceMovementAnalysis({ reportDate: "2026-06-30" }).then(
          () => "unexpected success",
          (error: unknown) => error,
        ),
        new Promise<string>((resolve) => {
          timeoutId = setTimeout(() => resolve("still waiting for error body"), 250);
        }),
      ]);
      expect(outcome).toMatchObject({
        name: "Error",
        message: `Request failed: ${refreshPath} (503)`,
      });
      expect(readErrorBody).not.toHaveBeenCalled();
    } finally {
      clearTimeout(timeoutId);
    }
  });

  it.each(["fetch", "body"] as const)("aborts a stalled GET %s at the shared deadline", async (phase) => {
    vi.useFakeTimers();
    try {
      const fetchImpl = vi.fn<typeof fetch>((_url, init) => {
        expect(init?.signal).toBeInstanceOf(AbortSignal);
        return phase === "fetch"
          ? new Promise<Response>(() => undefined)
          : Promise.resolve({
              ok: true,
              json: () => new Promise<unknown>(() => undefined),
            } as Response);
      });
      const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
      const pending = expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" }))
        .rejects.toThrow(`Request timed out: ${detailPath}`);

      await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_JSON_TIMEOUT_MS);
      await pending;
      expect(fetchImpl.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each(["dates", "analysis"] as const)("preserves caller cancellation for %s", async (endpoint) => {
    const controller = new AbortController();
    const reason = new DOMException("Query cancelled", "AbortError");
    let resolveFetch!: (response: Response) => void;
    const fetchImpl = vi.fn<typeof fetch>(() => new Promise<Response>((resolve) => { resolveFetch = resolve; }));
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });
    const request = endpoint === "dates"
      ? client.getBalanceMovementDates("CNX", { signal: controller.signal })
      : client.getBalanceMovementAnalysis({ reportDate: "2026-06-30", signal: controller.signal });
    controller.abort(reason);
    resolveFetch(jsonResponse({ result: {}, result_meta: {} }));

    await expect(request).rejects.toBe(reason);
    expect(fetchImpl.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });

  it.each(["api", "home supplemental"] as const)("keeps cancellation through the %s composition entry", async (entry) => {
    const controller = new AbortController();
    const reason = new DOMException("Query cancelled", "AbortError");
    controller.abort(reason);
    const dates = await createMockBalanceMovementClient().getBalanceMovementDates();
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async () => jsonResponse(dates));
    const client = entry === "api"
      ? (await import("./client")).createApiClient({ mode: "real", fetchImpl, baseUrl })
      : (await import("./homeSupplementalClient")).createRealHomeSupplementalClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates("CNX", { signal: controller.signal })).rejects.toBe(reason);
    await expect(client.getBalanceMovementAnalysis({
      reportDate: "2026-06-30",
      signal: controller.signal,
    })).rejects.toBe(reason);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("preserves a refresh network failure without converting it to an HTTP error", async () => {
    const error = new TypeError("Failed to fetch");
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(error);
    const client = createRealBalanceMovementClient({ fetchImpl, baseUrl });

    await expect(client.refreshBalanceMovementAnalysis({ reportDate: "2026-06-30" })).rejects.toBe(error);
  });

  it.each(["api", "home supplemental"] as const)("works through the %s composition entry", async (entry) => {
    const mockClient = createMockBalanceMovementClient();
    const dates = await mockClient.getBalanceMovementDates();
    const detail = await mockClient.getBalanceMovementAnalysis({ reportDate: "2026-06-30" });
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(dates))
      .mockResolvedValueOnce(jsonResponse(detail));
    const client = entry === "api"
      ? (await import("./client")).createApiClient({ mode: "real", fetchImpl, baseUrl })
      : (await import("./homeSupplementalClient")).createRealHomeSupplementalClient({ fetchImpl, baseUrl });

    await expect(client.getBalanceMovementDates()).resolves.toEqual(dates);
    await expect(client.getBalanceMovementAnalysis({ reportDate: "2026-06-30" })).resolves.toEqual(detail);
    expect(fetchImpl.mock.calls.map(([url]) => url)).toEqual([
      `${baseUrl}${datesPath}`,
      `${baseUrl}${detailPath}`,
    ]);
  });
});

describe("createMockBalanceMovementClient", () => {
  it("uses the governed J4 structured-finance broker label", async () => {
    const response = await createMockBalanceMovementClient().getBalanceMovementAnalysis({
      reportDate: "2026-06-30",
      currencyBasis: "CNY",
    });
    const currentMonth = response.result.business_trend_months.find(
      (month) => month.report_date === "2026-06-30",
    );
    const j4Row = currentMonth?.rows.find(
      (row) => row.row_key === "asset_zqtz_detail_structured_finance_broker",
    );

    expect(j4Row?.row_label).toBe("结构化融资（券商）");
  });
});
