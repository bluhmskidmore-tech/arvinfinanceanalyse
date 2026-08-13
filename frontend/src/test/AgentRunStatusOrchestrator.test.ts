import { afterEach, describe, expect, it, vi } from "vitest";

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

  it.each([
    ["invalid payload", async (_runId: string, onEvent: (payload: unknown) => unknown) => {
      onEvent({ run_id: "agent_run:test", status: "unknown" });
    }],
    ["premature EOF", async () => undefined],
  ])("falls back to GET after SSE %s", async (_label, streamAgentRunEvents) => {
    const completed = buildRun("completed", { result: buildResult("fallback result") });
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
    expect(fetchAgentRunStatus).toHaveBeenCalledOnce();
    expect(fetchAgentRunStatus).toHaveBeenCalledWith("agent_run:test");
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
      streamAgentRunEvents: async () => undefined,
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
