import { describe, expect, it, vi } from "vitest";

import {
  assertApiEnvelopeShape,
  assertShape,
  requestJson,
  requestPlainJson,
  type ShapeFieldSpec,
} from "../api/transport";

/** Mirrors the real backend envelope from contracts/core.ts (ResultMeta). */
const fullResultMeta = {
  trace_id: "tr_test",
  basis: "formal",
  result_kind: "executive.overview",
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

const okJsonResponse = (payload: unknown) =>
  ({
    ok: true,
    json: async () => payload,
  }) as unknown as Response;

describe("assertApiEnvelopeShape", () => {
  it("accepts a full real-contract envelope (as_of_date string)", () => {
    const payload = {
      result_meta: { ...fullResultMeta, as_of_date: "2026-07-31" },
      result: { title: "经营总览", metrics: [] },
    };
    expect(() => assertApiEnvelopeShape(payload, "/ui/home/overview")).not.toThrow();
  });

  it("accepts optional/nullable meta fields per contract (as_of_date null or absent)", () => {
    expect(() =>
      assertApiEnvelopeShape(
        { result_meta: { ...fullResultMeta, as_of_date: null }, result: [] },
        "/ui/x",
      ),
    ).not.toThrow();
    expect(() =>
      assertApiEnvelopeShape({ result_meta: fullResultMeta, result: {} }, "/ui/x"),
    ).not.toThrow();
  });

  it("accepts result: null and a minimal result_meta object (lenient by design)", () => {
    expect(() =>
      assertApiEnvelopeShape({ result_meta: fullResultMeta, result: null }, "/ui/x"),
    ).not.toThrow();
    expect(() => assertApiEnvelopeShape({ result_meta: {}, result: 1 }, "/ui/x")).not.toThrow();
  });

  it("rejects non-object payloads with URL context", () => {
    expect(() => assertApiEnvelopeShape(null, "/ui/a")).toThrow(
      "Invalid ApiEnvelope from /ui/a: response is null, expected { result, result_meta }",
    );
    expect(() => assertApiEnvelopeShape([1, 2], "/ui/b")).toThrow(
      "Invalid ApiEnvelope from /ui/b: response is an array, expected { result, result_meta }",
    );
    expect(() => assertApiEnvelopeShape("oops", "/ui/c")).toThrow(
      "Invalid ApiEnvelope from /ui/c: response is a string, expected { result, result_meta }",
    );
  });

  it("rejects a missing result or result_meta", () => {
    expect(() =>
      assertApiEnvelopeShape({ result_meta: fullResultMeta }, "/ui/x"),
    ).toThrow("Invalid ApiEnvelope from /ui/x: missing `result`");
    expect(() => assertApiEnvelopeShape({ result: {} }, "/ui/x")).toThrow(
      "Invalid ApiEnvelope from /ui/x: missing `result_meta`",
    );
  });

  it("rejects a non-object result_meta", () => {
    expect(() =>
      assertApiEnvelopeShape({ result_meta: "formal", result: {} }, "/ui/x"),
    ).toThrow("Invalid ApiEnvelope from /ui/x: `result_meta` is a string, expected an object");
    expect(() =>
      assertApiEnvelopeShape({ result_meta: [1], result: {} }, "/ui/x"),
    ).toThrow("Invalid ApiEnvelope from /ui/x: `result_meta` is an array, expected an object");
  });

  it("rejects wrongly typed basis / as_of_date", () => {
    expect(() =>
      assertApiEnvelopeShape(
        { result_meta: { ...fullResultMeta, basis: 42 }, result: {} },
        "/ui/x",
      ),
    ).toThrow("Invalid ApiEnvelope from /ui/x: `result_meta.basis` must be a string when present");
    expect(() =>
      assertApiEnvelopeShape(
        { result_meta: { ...fullResultMeta, as_of_date: 20260731 }, result: {} },
        "/ui/x",
      ),
    ).toThrow(
      "Invalid ApiEnvelope from /ui/x: `result_meta.as_of_date` must be a string or null when present",
    );
  });
});

describe("assertShape", () => {
  const fields: ShapeFieldSpec[] = [
    { path: "report_date", type: "string" },
    { path: "rows", type: "array" },
    { path: "summary", type: "object" },
    { path: "summary.total_pnl", type: "string" },
    { path: "summary.pnl_row_count", type: "number" },
    { path: "summary.note", type: "string", optional: true },
  ];

  const validValue = {
    report_date: "2026-06-30",
    rows: [],
    summary: { total_pnl: "100.00", pnl_row_count: 1 },
  };

  it("passes for a well-formed value (optional field absent)", () => {
    expect(() => assertShape(validValue, "/ui/x", fields)).not.toThrow();
  });

  it("passes when an optional field is present with the right type", () => {
    const value = { ...validValue, summary: { ...validValue.summary, note: "ok" } };
    expect(() => assertShape(value, "/ui/x", fields)).not.toThrow();
  });

  it("throws on a missing required field, naming the dotted path", () => {
    const { rows: _rows, ...withoutRows } = validValue;
    expect(() => assertShape(withoutRows, "/ui/x", fields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: missing `rows`",
    );
  });

  it("throws on a missing required nested field", () => {
    const value = { ...validValue, summary: { pnl_row_count: 1 } };
    expect(() => assertShape(value, "/ui/x", fields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: missing `summary.total_pnl`",
    );
  });

  it("throws on a null required field", () => {
    const value = { ...validValue, report_date: null };
    expect(() => assertShape(value, "/ui/x", fields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: `report_date` is null, expected string",
    );
  });

  it("does not throw when an optional field is null", () => {
    const value = { ...validValue, summary: { ...validValue.summary, note: null } };
    expect(() => assertShape(value, "/ui/x", fields)).not.toThrow();
  });

  it("throws on a wrong-typed field (amount serialized as number instead of string)", () => {
    const value = { ...validValue, summary: { ...validValue.summary, total_pnl: 100 } };
    expect(() => assertShape(value, "/ui/x", fields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: `summary.total_pnl` is a number, expected string",
    );
  });

  it("throws on a wrong-typed array field", () => {
    const value = { ...validValue, rows: "not-an-array" };
    expect(() => assertShape(value, "/ui/x", fields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: `rows` is a string, expected array",
    );
  });

  it("supports a path prefix for error messages (used by assertApiEnvelopeShape)", () => {
    const { rows: _rows, ...withoutRows } = validValue;
    expect(() => assertShape(withoutRows, "/ui/x", fields, "result.")).toThrow(
      "Invalid ApiEnvelope from /ui/x: missing `result.rows`",
    );
  });
});

describe("assertApiEnvelopeShape with resultFields", () => {
  const resultFields: ShapeFieldSpec[] = [
    { path: "total_pnl", type: "string" },
    { path: "as_of", type: "string" },
  ];

  it("passes shell + field checks together", () => {
    const payload = {
      result_meta: { ...fullResultMeta, as_of_date: "2026-06-30" },
      result: { total_pnl: "100.00", as_of: "2026-06-30" },
    };
    expect(() => assertApiEnvelopeShape(payload, "/ui/x", resultFields)).not.toThrow();
  });

  it("keeps shell-only behavior when resultFields is omitted (backward compatible)", () => {
    const payload = {
      result_meta: fullResultMeta,
      result: { unrelated: true },
    };
    expect(() => assertApiEnvelopeShape(payload, "/ui/x")).not.toThrow();
  });

  it("fails with a `result.`-prefixed path when a key field is missing", () => {
    const payload = {
      result_meta: fullResultMeta,
      result: { total_pnl: "100.00" },
    };
    expect(() => assertApiEnvelopeShape(payload, "/ui/x", resultFields)).toThrow(
      "Invalid ApiEnvelope from /ui/x: missing `result.as_of`",
    );
  });
});

describe("requestJson (transport)", () => {
  it("returns a valid envelope and sends Accept + abort signal", async () => {
    const envelope = { result_meta: fullResultMeta, result: { value: 1 } };
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.headers).toEqual({ Accept: "application/json" });
      expect(init?.signal).toBeInstanceOf(AbortSignal);
      return okJsonResponse(envelope);
    }) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "http://localhost:8000", "/ui/home/overview"),
    ).resolves.toEqual(envelope);
  });

  it("rejects loudly (with URL context) when the payload is not an envelope", async () => {
    const fetchImpl = vi.fn(async () =>
      okJsonResponse({ rows: [] }),
    ) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "http://localhost:8000", "/ui/home/overview"),
    ).rejects.toThrow(
      "Invalid ApiEnvelope from http://localhost:8000/ui/home/overview: missing `result`",
    );
  });

  it("keeps status-only error messages by default", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => ({ detail: "backend detail should stay hidden" }),
    })) as unknown as typeof fetch;

    await expect(requestJson(fetchImpl, "", "/ui/x")).rejects.toThrow(
      "Request failed: /ui/x (500)",
    );
  });

  it("surfaces FastAPI detail in json-detail mode (marketData semantics)", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "Choice vendor unavailable" }),
    })) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "", "/ui/market-data/rates", {
        timeoutMs: null,
        errorDetail: "json-detail",
      }),
    ).rejects.toThrow("Choice vendor unavailable");
  });

  it("does not attach a signal when timeoutMs is null (legacy no-timeout semantics)", async () => {
    const envelope = { result_meta: fullResultMeta, result: {} };
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.signal).toBeUndefined();
      return okJsonResponse(envelope);
    }) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "", "/ui/x", { timeoutMs: null }),
    ).resolves.toEqual(envelope);
  });

  it("keeps caller cancellation active while reading the JSON body", async () => {
    const controller = new AbortController();
    const reason = new Error("superseded balance request");
    let bodyStarted = () => {};
    const reading = new Promise<void>((resolve) => { bodyStarted = resolve; });
    let resolveBody!: (value: unknown) => void;
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: () => new Promise((resolve) => {
        resolveBody = resolve;
        bodyStarted();
      }),
    })) as unknown as typeof fetch;

    const request = requestJson(fetchImpl, "", "/ui/balance", { signal: controller.signal });
    await reading;
    controller.abort(reason);
    resolveBody({ invalid: true });

    await expect(request).rejects.toBe(reason);
  });

  it("cancels a fetch that ignores AbortSignal", async () => {
    const controller = new AbortController();
    const reason = new Error("balance date changed");
    const fetchImpl = vi.fn(() => new Promise<Response>(() => {})) as unknown as typeof fetch;

    const request = requestPlainJson(fetchImpl, "", "/ui/balance", {
      signal: controller.signal,
    });
    controller.abort(reason);

    await expect(request).rejects.toBe(reason);
  });

  it.each([requestJson, requestPlainJson])(
    "times out when the response JSON body never finishes",
    async (read) => {
      vi.useFakeTimers();
      try {
        const fetchImpl = vi.fn(async () => ({
          ok: true,
          json: () => new Promise<never>(() => {}),
        })) as unknown as typeof fetch;
        const request = read(fetchImpl, "", "/ui/slow-body", { timeoutMs: 100 });
        const outcome = expect(request).rejects.toThrow("Request timed out: /ui/slow-body");

        await vi.advanceTimersByTimeAsync(100);
        await outcome;
      } finally {
        vi.useRealTimers();
      }
    },
  );

  it("does not dispatch a request with an already aborted caller signal", async () => {
    const controller = new AbortController();
    const reason = new Error("balance date changed");
    controller.abort(reason);
    const fetchImpl = vi.fn() as unknown as typeof fetch;

    await expect(requestJson(fetchImpl, "", "/ui/balance", {
      signal: controller.signal,
    })).rejects.toBe(reason);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("aborts with a timeout error when a custom timeoutMs elapses", async () => {
    vi.useFakeTimers();
    try {
      const fetchImpl = vi.fn(
        (_url: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => {
              reject(new DOMException("aborted", "AbortError"));
            });
          }),
      ) as unknown as typeof fetch;

      const pending = expect(
        requestJson(fetchImpl, "", "/ui/slow", { timeoutMs: 5_000 }),
      ).rejects.toThrow("Request timed out: /ui/slow");
      await vi.advanceTimersByTimeAsync(5_000);
      await pending;
    } finally {
      vi.useRealTimers();
    }
  });

  it("accepts a well-formed payload when keyFields is supplied", async () => {
    const envelope = {
      result_meta: fullResultMeta,
      result: { total_pnl: "100.00", as_of: "2026-06-30" },
    };
    const fetchImpl = vi.fn(async () => okJsonResponse(envelope)) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "", "/ui/pnl", {
        keyFields: [
          { path: "total_pnl", type: "string" },
          { path: "as_of", type: "string" },
        ],
      }),
    ).resolves.toEqual(envelope);
  });

  it("rejects a payload missing a keyFields-declared business field", async () => {
    const envelope = { result_meta: fullResultMeta, result: { total_pnl: "100.00" } };
    const fetchImpl = vi.fn(async () => okJsonResponse(envelope)) as unknown as typeof fetch;

    await expect(
      requestJson(fetchImpl, "http://localhost:8000", "/ui/pnl", {
        keyFields: [
          { path: "total_pnl", type: "string" },
          { path: "as_of", type: "string" },
        ],
      }),
    ).rejects.toThrow(
      "Invalid ApiEnvelope from http://localhost:8000/ui/pnl: missing `result.as_of`",
    );
  });
});

describe("requestPlainJson (transport)", () => {
  it("returns plain payloads without envelope validation (health semantics)", async () => {
    const fetchImpl = vi.fn(async () =>
      okJsonResponse({ status: "ok" }),
    ) as unknown as typeof fetch;

    await expect(requestPlainJson(fetchImpl, "", "/health/live")).resolves.toEqual({
      status: "ok",
    });
  });

  it("forwards the caller signal when no timeout is requested", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.signal).toBe(controller.signal);
      return okJsonResponse({ status: "ok" });
    }) as unknown as typeof fetch;

    await expect(requestPlainJson(fetchImpl, "", "/health/live", {
      timeoutMs: null,
      signal: controller.signal,
    })).resolves.toEqual({ status: "ok" });
  });

  it("cancels a stalled body without a deadline even when it ignores the signal", async () => {
    const controller = new AbortController();
    const reason = new Error("balance panel left");
    let bodyStarted = () => {};
    const reading = new Promise<void>((resolve) => { bodyStarted = resolve; });
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: () => {
        bodyStarted();
        return new Promise<never>(() => {});
      },
    })) as unknown as typeof fetch;

    const request = requestPlainJson(fetchImpl, "", "/ui/balance", {
      timeoutMs: null,
      signal: controller.signal,
    });
    await reading;
    controller.abort(reason);

    await expect(request).rejects.toBe(reason);
  });

  it("keeps status-only error messages by default even without a JSON body", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 503,
    })) as unknown as typeof fetch;

    await expect(requestPlainJson(fetchImpl, "", "/health/live")).rejects.toThrow(
      "Request failed: /health/live (503)",
    );
  });

  it("surfaces FastAPI detail in json-detail mode", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ detail: "watermark ledger busy" }),
    })) as unknown as typeof fetch;

    await expect(
      requestPlainJson(fetchImpl, "", "/api/external-data/watermarks", {
        timeoutMs: null,
        errorDetail: "json-detail",
      }),
    ).rejects.toThrow("watermark ledger busy");
  });
});
