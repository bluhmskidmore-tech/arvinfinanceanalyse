import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { fetchHomeSnapshotEnvelope } from "../api/executiveHomeSnapshotFetch";
import { getSystemReadPublication } from "../api/systemReadGeneration";
import { requestJson, requestPlainJson } from "../api/transport";

afterEach(() => vi.useRealTimers());

describe("bounded home reads", () => {
  it.each([["envelope read", requestJson], ["plain read", requestPlainJson]] as const)(
    "%s times out while the response body is stalled, after headers have arrived",
    async (_name, read) => {
      vi.useFakeTimers();
      let signal: AbortSignal | null | undefined;
      const json = vi.fn(() => new Promise<never>(() => {}));
      const fetchImpl = vi.fn<typeof fetch>(async (_input, init) => {
        signal = init?.signal;
        return { ok: true, json } as unknown as Response;
      });
      const outcome = read(fetchImpl, "", "/ui/slow-body", { timeoutMs: 100 })
        .then(() => "success", (error: unknown) => error);

      await vi.advanceTimersByTimeAsync(100);
      expect(json).toHaveBeenCalledOnce();
      expect(signal?.aborted).toBe(true);
      expect(await outcome).toEqual(new Error("Request timed out: /ui/slow-body"));
      expect(vi.getTimerCount()).toBe(0);
    },
  );

  it("preserves caller cancellation after headers arrive and removes the deadline", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const json = vi.fn(() => new Promise<never>(() => {}));
    const fetchImpl = vi.fn<typeof fetch>(async () => ({ ok: true, json }) as unknown as Response);
    const outcome = requestPlainJson(fetchImpl, "", "/ui/cancel", {
      signal: controller.signal, timeoutMs: 100,
    }).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(0);
    expect(json).toHaveBeenCalledOnce();

    const reason = new Error("page left");
    controller.abort(reason);
    expect(await outcome).toBe(reason);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("bounds reading a stalled error detail too", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn<typeof fetch>(async () => ({
      ok: false, status: 503, json: () => new Promise<never>(() => {}),
    }) as unknown as Response);
    const outcome = requestJson(fetchImpl, "", "/ui/error-body", {
      timeoutMs: 100, errorDetail: "json-detail",
    }).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(100);
    expect(await outcome).toEqual(new Error("Request timed out: /ui/error-body"));
  });

  it("cleans up the timer and caller listener after a successful read", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const remove = vi.spyOn(controller.signal, "removeEventListener");
    const fetchImpl = vi.fn<typeof fetch>(async () => new Response('{"ok":true}'));
    await expect(requestPlainJson(fetchImpl, "", "/ui/ok", {
      signal: controller.signal, timeoutMs: 100,
    })).resolves.toEqual({ ok: true });
    expect(remove).toHaveBeenCalledWith("abort", expect.any(Function));
    expect(vi.getTimerCount()).toBe(0);
  });

  it("bounds the publication handshake even when no response headers arrive", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | null | undefined;
    const fetchImpl = vi.fn<typeof fetch>((_input, init) => {
      signal = init?.signal;
      return new Promise<Response>(() => {});
    });
    const outcome = getSystemReadPublication(createApiClient({ mode: "real", fetchImpl }))
      .catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(15_000);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toEqual(new Error("Request timed out: /api/system-read-publication"));
  });

  it("bounds the home snapshot body and preserves backend error details", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | null | undefined;
    const fetchImpl = vi.fn<typeof fetch>(async (_input, init) => {
      signal = init?.signal;
      return { ok: true, json: () => new Promise<never>(() => {}) } as unknown as Response;
    });
    const outcome = fetchHomeSnapshotEnvelope(fetchImpl, "", { reportDate: "2026-08-31" })
      .catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(signal?.aborted).toBe(true);
    expect(await outcome).toEqual(new Error("Request timed out: /ui/home/snapshot"));

    fetchImpl.mockResolvedValue(new Response('{"detail":"snapshot unavailable"}', { status: 503 }));
    await expect(fetchHomeSnapshotEnvelope(fetchImpl, "")).rejects.toThrow("snapshot unavailable");
  });
});
