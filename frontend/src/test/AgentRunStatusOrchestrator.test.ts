import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentRunStreamConnectionError } from "../api/agentRunStream";
import { runManagedAgentPolling } from "../features/agent/hooks/runManagedAgentPolling";
import {
  pollAgentRunUntilTerminal,
  waitForAgentRunTerminal,
} from "../features/agent/hooks/agentRunStatusOrchestrator";
import {
  AGENT_RUN_POLL_NETWORK_RECOVERABLE_MESSAGE,
} from "../features/agent/lib/agentWorkbenchModel";
import type {
  AgentQueryResult,
  AgentRunPayload,
} from "../features/agent/lib/agentWorkbenchModel";

function buildResult(answer: string): AgentQueryResult {
  return {
    answer,
    cards: [],
    evidence: {
      tables_used: [],
      filters_applied: {},
      evidence_rows: 0,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_agent_sse_test",
      basis: "formal",
      result_kind: "agent.hermes",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

function buildRun(
  status: AgentRunPayload["status"],
  overrides: Partial<AgentRunPayload> = {},
): AgentRunPayload {
  return {
    run_id: "agent_run:test",
    status,
    provider: "hermes",
    ...overrides,
  };
}

describe("waitForAgentRunTerminal", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("uses valid SSE snapshots, removes exact duplicates, and returns the terminal payload", async () => {
    const running = buildRun("running", { elapsed_seconds: 1 });
    const completed = buildRun("completed", { result: buildResult("stream result") });
    const streamAgentRunEvents = vi.fn(async (_runId, onEvent) => {
      onEvent(running);
      onEvent({ ...running });
      onEvent(completed);
    });
    const fetchAgentRunStatus = vi.fn();
    const onRunUpdate = vi.fn();

    const payload = await waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate,
    });

    expect(payload).toEqual(completed);
    expect(streamAgentRunEvents).toHaveBeenCalledOnce();
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
    expect(onRunUpdate).toHaveBeenNthCalledWith(1, running);
    expect(onRunUpdate).toHaveBeenNthCalledWith(2, completed);
    expect(onRunUpdate).toHaveBeenCalledTimes(2);
  });

  it("falls back to GET without reconnecting after an invalid SSE payload", async () => {
    // 假计时器下若误入退避睡眠，本用例会因 promise 无法结算而超时失败。
    vi.useFakeTimers();
    const completed = buildRun("completed", { result: buildResult("fallback result") });
    const streamAgentRunEvents = vi.fn(
      async (_runId: string, onEvent: (payload: unknown) => unknown) => {
        onEvent({ run_id: "agent_run:test", status: "unknown" });
      },
    );
    const fetchAgentRunStatus = vi.fn(async () => completed);

    const payload = await waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate: vi.fn(),
    });

    expect(payload).toEqual(completed);
    expect(streamAgentRunEvents).toHaveBeenCalledTimes(1);
    expect(fetchAgentRunStatus).toHaveBeenCalledOnce();
    expect(fetchAgentRunStatus).toHaveBeenCalledWith("agent_run:test");
  });

  it("falls back to GET immediately without reconnecting on a connection-phase SSE failure (4xx)", async () => {
    vi.useFakeTimers();
    const completed = buildRun("completed", { result: buildResult("degraded result") });
    const streamAgentRunEvents = vi.fn(async () => {
      throw new AgentRunStreamConnectionError("Agent run SSE request failed: /events (404)", {
        status: 404,
      });
    });
    const fetchAgentRunStatus = vi.fn(async () => completed);

    const payload = await waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate: vi.fn(),
    });

    expect(payload).toEqual(completed);
    expect(streamAgentRunEvents).toHaveBeenCalledTimes(1);
    expect(fetchAgentRunStatus).toHaveBeenCalledOnce();
  });

  it("reconnects after a mid-stream failure and finishes over SSE without polling", async () => {
    vi.useFakeTimers();
    const running = buildRun("running", { elapsed_seconds: 1 });
    const completed = buildRun("completed", { result: buildResult("reconnected result") });
    let attempt = 0;
    const streamAgentRunEvents = vi.fn(
      async (_runId: string, onEvent: (payload: unknown) => boolean | void) => {
        attempt += 1;
        if (attempt === 1) {
          onEvent(running);
          throw new Error("stream reset");
        }
        // 重连后服务端先重放当前快照，再推进到终态。
        onEvent(running);
        onEvent(completed);
      },
    );
    const fetchAgentRunStatus = vi.fn();
    const onRunUpdate = vi.fn();

    const promise = waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate,
    });
    const settled = expect(promise).resolves.toEqual(completed);
    await vi.advanceTimersByTimeAsync(1000);
    await settled;

    expect(streamAgentRunEvents).toHaveBeenCalledTimes(2);
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
    // 重连重放的 running 快照被去重：running / completed 各只发布一次。
    expect(onRunUpdate).toHaveBeenNthCalledWith(1, running);
    expect(onRunUpdate).toHaveBeenNthCalledWith(2, completed);
    expect(onRunUpdate).toHaveBeenCalledTimes(2);
  });

  it.each([
    [
      "mid-stream failures",
      async () => {
        throw new Error("stream reset");
      },
    ],
    ["EOF before a terminal snapshot", async () => undefined],
  ])("degrades to GET polling after two failed reconnects (%s)", async (_label, streamImpl) => {
    vi.useFakeTimers();
    const completed = buildRun("completed", { result: buildResult("polled result") });
    const streamAgentRunEvents = vi.fn(streamImpl);
    const fetchAgentRunStatus = vi.fn(async () => completed);

    const promise = waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate: vi.fn(),
    });
    const settled = expect(promise).resolves.toEqual(completed);

    await vi.advanceTimersByTimeAsync(1000);
    expect(streamAgentRunEvents).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1000);
    // 第二次退避为 3s：仅推进 2s 时不应触发第三次连接，也不应提前降级轮询。
    expect(streamAgentRunEvents).toHaveBeenCalledTimes(2);
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    await settled;

    expect(streamAgentRunEvents).toHaveBeenCalledTimes(3);
    expect(fetchAgentRunStatus).toHaveBeenCalledOnce();
    expect(fetchAgentRunStatus).toHaveBeenCalledWith("agent_run:test");
  });

  it("does not reconnect once the signal aborts during the reconnect backoff", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const streamAgentRunEvents = vi.fn(async () => {
      throw new Error("stream reset");
    });
    const fetchAgentRunStatus = vi.fn();

    const promise = waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate: vi.fn(),
      signal: controller.signal,
    });
    const settled = expect(promise).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();
    await settled;

    expect(streamAgentRunEvents).toHaveBeenCalledTimes(1);
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
  });

  it("does not publish late SSE snapshots when canCommit is false", async () => {
    const completed = buildRun("completed", { result: buildResult("late result") });
    const streamAgentRunEvents = vi.fn(async (_runId, onEvent) => {
      onEvent(buildRun("running"));
      onEvent(completed);
    });
    const onRunUpdate = vi.fn();

    await waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      streamAgentRunEvents,
      fetchAgentRunStatus: vi.fn(),
      canCommit: () => false,
      onRunUpdate,
    });

    expect(onRunUpdate).not.toHaveBeenCalled();
  });

  it("returns a cancelled terminal payload from GET polling", async () => {
    const cancelledRun = buildRun("cancelled", { error_message: "run cancelled" });
    const fetchAgentRunStatus = vi.fn(async () => cancelledRun);

    const payload = await waitForAgentRunTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("queued"),
      // 连接期失败：不重连，立即降级 GET 轮询。
      streamAgentRunEvents: async () => {
        throw new AgentRunStreamConnectionError("sse unavailable");
      },
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunUpdate: vi.fn(),
    });

    expect(payload).toEqual(cancelledRun);
    expect(fetchAgentRunStatus).toHaveBeenCalledOnce();
  });

  it("passes the abort signal to SSE and rejects before falling back to polling", async () => {
    const controller = new AbortController();
    const streamAgentRunEvents = vi.fn(async (_runId: string, _onEvent: unknown, options?: { signal?: AbortSignal }) => {
      expect(options?.signal).toBe(controller.signal);
      controller.abort();
    });
    const fetchAgentRunStatus = vi.fn();

    await expect(
      waitForAgentRunTerminal({
        runId: "agent_run:test",
        initialPayload: buildRun("queued"),
        streamAgentRunEvents,
        fetchAgentRunStatus,
        canCommit: () => true,
        onRunUpdate: vi.fn(),
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
  });
});

describe("pollAgentRunUntilTerminal", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("retries transient polling errors with backoff and recovers", async () => {
    vi.useFakeTimers();
    const completed = buildRun("completed", { result: buildResult("recovered result") });
    const fetchAgentRunStatus = vi
      .fn<(runId: string) => Promise<AgentRunPayload>>()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(completed);
    const onUpdate = vi.fn();

    const promise = pollAgentRunUntilTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("running"),
      fetchAgentRunStatus,
      onUpdate,
    });
    const settled = expect(promise).resolves.toEqual(completed);
    await vi.advanceTimersByTimeAsync(10_000);
    await settled;

    expect(fetchAgentRunStatus).toHaveBeenCalledTimes(3);
    expect(onUpdate).toHaveBeenLastCalledWith(completed);
  });

  it("fails with a recoverable message once the transient retry budget is exhausted", async () => {
    vi.useFakeTimers();
    const fetchAgentRunStatus = vi
      .fn<(runId: string) => Promise<AgentRunPayload>>()
      .mockRejectedValue(new Error("status endpoint down"));

    const promise = pollAgentRunUntilTerminal({
      runId: "agent_run:test",
      initialPayload: buildRun("running"),
      fetchAgentRunStatus,
    });
    const settled = expect(promise).rejects.toThrow(AGENT_RUN_POLL_NETWORK_RECOVERABLE_MESSAGE);
    await vi.advanceTimersByTimeAsync(30_000);
    await settled;

    expect(fetchAgentRunStatus).toHaveBeenCalledTimes(4);
  });

  it("stops polling with an AbortError when the signal aborts", async () => {
    const controller = new AbortController();
    const running = buildRun("running");
    const fetchAgentRunStatus = vi.fn(async () => running);

    const promise = pollAgentRunUntilTerminal({
      runId: "agent_run:test",
      fetchAgentRunStatus,
      signal: controller.signal,
    });
    const settled = expect(promise).rejects.toMatchObject({ name: "AbortError" });
    await vi.waitFor(() => expect(fetchAgentRunStatus).toHaveBeenCalledTimes(1));
    controller.abort();
    await settled;

    expect(fetchAgentRunStatus).toHaveBeenCalledTimes(1);
  });
});

describe("runManagedAgentPolling", () => {
  it("uses an injected stream handler for lab-only runs", async () => {
    const queued = buildRun("queued");
    const completed = buildRun("completed", { result: buildResult("streamed result") });
    const createAgentRun = vi.fn(async () => queued);
    const fetchAgentRunStatus = vi.fn();
    const streamAgentRunEvents = vi.fn(async (_runId, onEvent) => {
      onEvent(completed);
    });
    const onRunAccepted = vi.fn();
    const onRunUpdate = vi.fn();

    const payload = await runManagedAgentPolling({
      requestBody: { question: "lab stream question" },
      createAgentRun,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunAccepted,
      onRunUpdate,
      streamAgentRunEvents,
    });

    expect(payload).toEqual(completed);
    expect(streamAgentRunEvents).toHaveBeenCalledOnce();
    expect(fetchAgentRunStatus).not.toHaveBeenCalled();
    expect(onRunAccepted).toHaveBeenCalledWith(queued, expect.any(Number));
    expect(onRunUpdate).toHaveBeenCalledWith(completed);
  });

  it("keeps the original polling path when no stream override is provided", async () => {
    const queued = buildRun("queued");
    const completed = buildRun("completed", { result: buildResult("polled result") });
    const createAgentRun = vi.fn(async () => queued);
    const fetchAgentRunStatus = vi.fn(async () => completed);
    const onRunAccepted = vi.fn();
    const onRunUpdate = vi.fn();

    const payload = await runManagedAgentPolling({
      requestBody: { question: "formal path question" },
      createAgentRun,
      fetchAgentRunStatus,
      canCommit: () => true,
      onRunAccepted,
      onRunUpdate,
    });

    expect(payload).toEqual(completed);
    expect(fetchAgentRunStatus).toHaveBeenCalledWith("agent_run:test");
    expect(onRunAccepted).toHaveBeenCalledWith(queued, expect.any(Number));
    expect(onRunUpdate).toHaveBeenCalledWith(completed);
  });
});
