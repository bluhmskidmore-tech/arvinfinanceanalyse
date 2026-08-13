import { describe, expect, it, vi } from "vitest";

import { streamAgentRunEvents } from "../api/agentRunStream";

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

describe("streamAgentRunEvents", () => {
  it("parses split CRLF frames, ignores heartbeat comments, and keeps fetch auth-neutral", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      buildEventStreamResponse([
        ": keepalive\r",
        "\n\r\n",
        "event: run_up",
        "date\r\ndata: {\"run_id\":\"agent_run:test\",\r\n",
        "data: \"status\":\"running\"}\r\n\r\n",
        "event: run_update\n",
        "data: {\"run_id\":\"agent_run:test\",\"status\":\"completed\"}\n\n",
      ]),
    );
    const signal = new AbortController().signal;
    const updates: unknown[] = [];

    await streamAgentRunEvents(
      "agent_run:test",
      (payload) => {
        updates.push(payload);
        return (payload as { status?: string }).status === "completed";
      },
      {
        baseUrl: "http://example.test/root///",
        fetchImpl: fetchImpl as unknown as typeof fetch,
        signal,
      },
    );

    expect(updates).toEqual([
      { run_id: "agent_run:test", status: "running" },
      { run_id: "agent_run:test", status: "completed" },
    ]);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://example.test/root/api/agent/runs/agent_run%3Atest/events",
      {
        method: "GET",
        headers: { Accept: "text/event-stream" },
        signal,
      },
    );
    expect(fetchImpl.mock.calls[0]?.[1]).not.toHaveProperty("credentials");
    expect(fetchImpl.mock.calls[0]?.[1]?.headers).not.toHaveProperty("Authorization");
  });

  it("ignores unknown event types and comment-only blocks without stopping the stream", async () => {
    const fetchImpl = vi.fn(async () =>
      buildEventStreamResponse([
        "event: heartbeat\ndata: {\"ts\":\"2026-08-12T00:00:00Z\"}\n\n",
        ": comment-only heartbeat\n\n",
        "event: totally_unknown\ndata: not json at all\n\n",
        "event: run_update\ndata: {\"run_id\":\"agent_run:test\",\"status\":\"completed\"}\n\n",
      ]),
    );
    const updates: unknown[] = [];

    await streamAgentRunEvents(
      "agent_run:test",
      (payload) => {
        updates.push(payload);
        return true;
      },
      { fetchImpl: fetchImpl as unknown as typeof fetch },
    );

    expect(updates).toEqual([{ run_id: "agent_run:test", status: "completed" }]);
  });
});
