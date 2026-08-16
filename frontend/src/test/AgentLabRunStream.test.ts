import { describe, expect, it, vi } from "vitest";

import { streamAgentLabRunEvents } from "../api/agentLabRunStream";
import { AgentRunStreamConnectionError } from "../api/agentRunStream";

function buildEventStreamResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { "Content-Type": "text/event-stream; charset=utf-8" },
    },
  );
}

describe("streamAgentLabRunEvents", () => {
  it("requests lab deltas with after_seq, parses split CRLF frames, and drops duplicate seq", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      buildEventStreamResponse([
        ": keepalive\r\n\r\n",
        "event: run_de",
        "lta\r\ndata: {\"run_id\":\"agent_run:test\",\"seq\":2,\"channel\":\"answer\",",
        "\"text\":\"第一段\",\"created_at\":\"2026-08-15T00:00:02Z\"}\r\n\r\n",
        "event: run_delta\r\n",
        "data: {\"run_id\":\"agent_run:test\",\"seq\":2,\"channel\":\"answer\",\"text\":\"重复\",\"created_at\":\"2026-08-15T00:00:02Z\"}\r\n\r\n",
        "event: run_update\r\n",
        "data: {\"run_id\":\"agent_run:test\",\"status\":\"running\"}\r\n\r\n",
        "event: run_update\n",
        "data: {\"run_id\":\"agent_run:test\",\"status\":\"completed\"}\n\n",
      ]),
    );
    const deltas: string[] = [];
    const updates: unknown[] = [];

    await streamAgentLabRunEvents(
      "agent_run:test",
      {
        onRunDelta: (payload) => {
          deltas.push(payload.text);
        },
        onRunUpdate: (payload) => {
          updates.push(payload);
          return (payload as { status?: string }).status === "completed";
        },
      },
      {
        baseUrl: "http://example.test/root///",
        fetchImpl: fetchImpl as unknown as typeof fetch,
        afterSeq: 1,
      },
    );

    expect(deltas).toEqual(["第一段"]);
    expect(updates).toEqual([
      { run_id: "agent_run:test", status: "running" },
      { run_id: "agent_run:test", status: "completed" },
    ]);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/root/api/agent/runs/agent_run%3Atest/events?include_deltas=true&after_seq=1",
      {
        method: "GET",
        headers: { Accept: "text/event-stream" },
        signal: undefined,
      },
    );
  });

  it("throws a protocol error when delta seq has a gap", async () => {
    const fetchImpl = vi.fn(async () =>
      buildEventStreamResponse([
        "event: run_delta\ndata: {\"run_id\":\"agent_run:test\",\"seq\":1,\"channel\":\"answer\",\"text\":\"第一段\",\"created_at\":\"2026-08-15T00:00:01Z\"}\n\n",
        "event: run_delta\ndata: {\"run_id\":\"agent_run:test\",\"seq\":3,\"channel\":\"answer\",\"text\":\"跳号\",\"created_at\":\"2026-08-15T00:00:03Z\"}\n\n",
      ]),
    );
    const deltas: string[] = [];

    const promise = streamAgentLabRunEvents(
      "agent_run:test",
      {
        onRunDelta: (payload) => {
          deltas.push(payload.text);
        },
        onRunUpdate: () => false,
      },
      { fetchImpl: fetchImpl as unknown as typeof fetch },
    );

    await expect(promise).rejects.toThrow("out of order");
    expect(deltas).toEqual(["第一段"]);
  });

  it("rejects malformed lab event payloads but ignores unknown event types", async () => {
    const fetchImpl = vi.fn(async () =>
      buildEventStreamResponse([
        "event: heartbeat\ndata: {\"ts\":\"2026-08-15T00:00:00Z\"}\n\n",
        "event: run_delta\ndata: {\"run_id\":\"agent_run:test\",\"seq\":\"bad\"}\n\n",
      ]),
    );

    await expect(
      streamAgentLabRunEvents(
        "agent_run:test",
        {
          onRunDelta: () => undefined,
          onRunUpdate: () => false,
        },
        { fetchImpl: fetchImpl as unknown as typeof fetch },
      ),
    ).rejects.toThrow("run_delta payload is invalid");
  });

  it("propagates aborts unchanged", async () => {
    const abortError = new Error("The user aborted a request.");
    abortError.name = "AbortError";
    const controller = new AbortController();
    controller.abort();
    const fetchImpl = vi.fn(async () => {
      throw abortError;
    });

    const promise = streamAgentLabRunEvents(
      "agent_run:test",
      {
        onRunDelta: () => undefined,
        onRunUpdate: () => false,
      },
      {
        fetchImpl: fetchImpl as unknown as typeof fetch,
        signal: controller.signal,
      },
    );

    await expect(promise).rejects.toBe(abortError);
    await expect(promise).rejects.not.toBeInstanceOf(AgentRunStreamConnectionError);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
