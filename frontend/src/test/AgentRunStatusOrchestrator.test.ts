import { describe, expect, it, vi } from "vitest";

import { waitForAgentRunTerminal } from "../features/agent/hooks/agentRunStatusOrchestrator";
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
});
