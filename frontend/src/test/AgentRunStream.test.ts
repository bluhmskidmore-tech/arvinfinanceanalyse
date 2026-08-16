import { describe, expect, it, vi } from "vitest";

import { AgentRunStreamConnectionError, streamAgentRunEvents } from "../api/agentRunStream";

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

  it("classifies a 4xx response as a connection-phase failure without retrying the request", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "run not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const promise = streamAgentRunEvents("agent_run:test", () => true, {
      baseUrl: "http://example.test",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    await expect(promise).rejects.toBeInstanceOf(AgentRunStreamConnectionError);
    await expect(promise).rejects.toMatchObject({
      name: "AgentRunStreamConnectionError",
      status: 404,
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("classifies rejected fetches and unusable responses as connection-phase failures", async () => {
    const rejectingFetch = vi.fn(async () => {
      throw new TypeError("sse unavailable");
    });
    const rejectedPromise = streamAgentRunEvents("agent_run:test", () => true, {
      fetchImpl: rejectingFetch as unknown as typeof fetch,
    });
    await expect(rejectedPromise).rejects.toBeInstanceOf(AgentRunStreamConnectionError);
    await expect(rejectedPromise).rejects.toThrow("sse unavailable");

    const undefinedResponseFetch = vi.fn(async () => undefined);
    await expect(
      streamAgentRunEvents("agent_run:test", () => true, {
        fetchImpl: undefinedResponseFetch as unknown as typeof fetch,
      }),
    ).rejects.toBeInstanceOf(AgentRunStreamConnectionError);

    const wrongContentTypeFetch = vi.fn(async () =>
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    await expect(
      streamAgentRunEvents("agent_run:test", () => true, {
        fetchImpl: wrongContentTypeFetch as unknown as typeof fetch,
      }),
    ).rejects.toBeInstanceOf(AgentRunStreamConnectionError);
  });

  it("keeps a mid-stream disconnect as a plain reconnectable error after delivering earlier events", async () => {
    const encoder = new TextEncoder();
    // controller.error() 会丢弃未读队列，因此用 pull 保证第一帧先被读走再断流。
    let pullCount = 0;
    const fetchImpl = vi.fn(async () =>
      new Response(
        new ReadableStream<Uint8Array>({
          pull(controller) {
            pullCount += 1;
            if (pullCount === 1) {
              controller.enqueue(
                encoder.encode(
                  'event: run_update\ndata: {"run_id":"agent_run:test","status":"running"}\n\n',
                ),
              );
              return;
            }
            controller.error(new Error("network reset"));
          },
        }),
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      ),
    );
    const updates: unknown[] = [];

    const promise = streamAgentRunEvents(
      "agent_run:test",
      (payload) => {
        updates.push(payload);
        return false;
      },
      { fetchImpl: fetchImpl as unknown as typeof fetch },
    );

    await expect(promise).rejects.toThrow("network reset");
    await expect(promise).rejects.not.toBeInstanceOf(AgentRunStreamConnectionError);
    expect(updates).toEqual([{ run_id: "agent_run:test", status: "running" }]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("propagates aborts unchanged so callers stop without reconnecting", async () => {
    const abortError = new Error("The user aborted a request.");
    abortError.name = "AbortError";
    const controller = new AbortController();
    controller.abort();
    const fetchImpl = vi.fn(async () => {
      throw abortError;
    });

    const promise = streamAgentRunEvents("agent_run:test", () => false, {
      fetchImpl: fetchImpl as unknown as typeof fetch,
      signal: controller.signal,
    });

    await expect(promise).rejects.toBe(abortError);
    await expect(promise).rejects.not.toBeInstanceOf(AgentRunStreamConnectionError);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
