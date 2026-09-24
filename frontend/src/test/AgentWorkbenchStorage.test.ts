/**
 * Agent 工作台 localStorage 持久化护栏：
 * 1. 配额超限（QuotaExceededError）不得击穿调用链——写入降级为跳过 + console.warn；
 * 2. 会话 turn 序列化对 AgentEnvelope 去重（agentRun.result 与 turn.result 只存一份），
 *    恢复时回填，内存形状与持久化前一致。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AgentConversationTurn,
  AgentQueryResult,
  AgentRunPayload,
} from "../features/agent/lib/agentWorkbenchModel";
import {
  AGENT_CONVERSATION_TURNS_KEY,
  loadStoredConversationTurns,
  persistComposerDraft,
  persistLatestAgentRunId,
  persistQueuedQueries,
  persistRecentRepoPaths,
  persistStoredConversationTurns,
  serializeConversationTurn,
} from "../features/agent/lib/agentWorkbenchStorage";

function buildEnvelope(answer = "去重回程回答。"): AgentQueryResult {
  return {
    answer,
    cards: [],
    evidence: {
      tables_used: ["hermes_cli"],
      filters_applied: { provider: "hermes" },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_storage_roundtrip",
      basis: "formal",
      result_kind: "agent.hermes",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

function buildCompletedTurn(result: AgentQueryResult): AgentConversationTurn {
  const agentRun: AgentRunPayload = {
    run_id: "agent_run:storage-roundtrip",
    status: "completed",
    run_kind: "managed",
    question: "storage roundtrip question",
    provider: "hermes",
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
    result,
  };
  return {
    id: "turn:storage-roundtrip",
    question: "storage roundtrip question",
    retryMode: "ordinary",
    stopped: false,
    runRequestLatencyMs: 120,
    agentRun,
    result,
    error: null,
    activeSuggestedActionPayload: null,
  };
}

describe("agent workbench storage quota resilience", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it.each([
    [
      "persistStoredConversationTurns",
      () => persistStoredConversationTurns([buildCompletedTurn(buildEnvelope())]),
    ],
    ["persistQueuedQueries", () => persistQueuedQueries(["queued question"])],
    ["persistLatestAgentRunId", () => persistLatestAgentRunId("agent_run:x")],
    ["persistComposerDraft", () => persistComposerDraft("draft text")],
    ["persistRecentRepoPaths", () => persistRecentRepoPaths(["F:\\MOSS-SYSTEM-V1"])],
  ])("%s swallows QuotaExceededError and warns instead of throwing", (_label, persist) => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota exceeded", "QuotaExceededError");
    });

    expect(() => persist()).not.toThrow();
    expect(warnSpy).toHaveBeenCalled();
  });
});

describe("agent conversation turn envelope dedupe", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("serializes the envelope once by stripping agentRun.result when turn.result holds it", () => {
    const result = buildEnvelope();
    const serialized = serializeConversationTurn(buildCompletedTurn(result));

    expect(serialized.result).toEqual(result);
    expect(serialized.agentRun?.result).toBeNull();

    const rawJson = JSON.stringify(serialized);
    expect(rawJson.match(/tr_storage_roundtrip/g)).toHaveLength(1);
  });

  it("keeps agentRun.result for a terminal run without a committed turn result", () => {
    const result = buildEnvelope();
    const turn = buildCompletedTurn(result);
    const serialized = serializeConversationTurn({ ...turn, result: null });

    expect(serialized.agentRun?.result).toEqual(result);
  });

  it("restores the in-memory shape by backfilling agentRun.result from turn.result", () => {
    const result = buildEnvelope();
    const turn = buildCompletedTurn(result);
    persistStoredConversationTurns([turn]);

    const storedRaw = window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY);
    expect(storedRaw).toBeTruthy();
    expect(String(storedRaw).match(/tr_storage_roundtrip/g)).toHaveLength(1);

    const restoredTurns = loadStoredConversationTurns();
    expect(restoredTurns).toHaveLength(1);
    const restored = restoredTurns[0];
    expect(restored?.result).toEqual(result);
    expect(restored?.agentRun?.result).toEqual(result);
    expect(restored?.agentRun?.run_id).toBe("agent_run:storage-roundtrip");
    expect(restored?.agentRun?.status).toBe("completed");
    expect(restored?.runRequestLatencyMs).toBe(120);
  });
});
