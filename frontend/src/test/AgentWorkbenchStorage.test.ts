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
  AGENT_COMPOSER_DRAFT_KEY,
  AGENT_CONVERSATION_TURNS_KEY,
  AGENT_QUEUED_QUERIES_KEY,
  LATEST_AGENT_RUN_ID_KEY,
  clearComposerDraft,
  clearLatestAgentRunId,
  clearStoredQueuedQueries,
  getScopedAgentWorkbenchStorageKey,
  loadComposerDraft,
  loadStoredConversationTurns,
  loadLatestAgentRunId,
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

describe("agent workbench storage access resilience", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  const stringLoaders = [
    ["loadLatestAgentRunId", () => loadLatestAgentRunId("user:blocked")],
    ["loadComposerDraft", () => loadComposerDraft("user:blocked")],
  ] as const;

  it.each(stringLoaders)("%s returns an empty value when scoped reads are denied", (_label, load) => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("storage access denied", "SecurityError");
    });

    expect(load()).toBe("");
  });

  it.each(stringLoaders)("%s returns an empty value when a legacy migration read is denied", (_label, load) => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "getItem")
      .mockReturnValueOnce(null)
      .mockImplementation(() => {
        throw new DOMException("legacy storage access denied", "SecurityError");
      });

    expect(load()).toBe("");
  });

  it.each(stringLoaders)("%s returns an empty value when the storage getter is denied", (_label, load) => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("storage getter denied", "SecurityError");
    });

    expect(load()).toBe("");
  });

  const removers = [
    ["clearLatestAgentRunId", () => clearLatestAgentRunId("user:blocked")],
    ["clearComposerDraft", () => clearComposerDraft("user:blocked")],
    ["clearStoredQueuedQueries", () => clearStoredQueuedQueries("user:blocked")],
    ["persistComposerDraft with an empty draft", () => persistComposerDraft("  ", "user:blocked")],
    ["persistQueuedQueries with an empty queue", () => persistQueuedQueries(["  "], "user:blocked")],
  ] as const;

  it.each(removers)("%s skips denied removal without throwing", (_label, remove) => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("storage removal denied", "SecurityError");
    });

    expect(remove).not.toThrow();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it.each(removers)("%s skips removal when the storage getter is denied", (_label, remove) => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("storage getter denied", "SecurityError");
    });

    expect(remove).not.toThrow();
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it("clears only the requested namespace when storage is available", () => {
    for (const storageKey of [LATEST_AGENT_RUN_ID_KEY, AGENT_COMPOSER_DRAFT_KEY, AGENT_QUEUED_QUERIES_KEY]) {
      window.localStorage.setItem(getScopedAgentWorkbenchStorageKey(storageKey, "user:clear"), "synthetic value");
      window.localStorage.setItem(getScopedAgentWorkbenchStorageKey(storageKey, "user:keep"), "synthetic value");
    }

    clearLatestAgentRunId("user:clear");
    clearComposerDraft("user:clear");
    clearStoredQueuedQueries("user:clear");

    for (const storageKey of [LATEST_AGENT_RUN_ID_KEY, AGENT_COMPOSER_DRAFT_KEY, AGENT_QUEUED_QUERIES_KEY]) {
      expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(storageKey, "user:clear"))).toBeNull();
      expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(storageKey, "user:keep"))).toBe("synthetic value");
    }
  });

  it("restores the migrated draft even when deleting the legacy key is denied", () => {
    const draft = "  synthetic draft  ";
    window.localStorage.setItem(AGENT_COMPOSER_DRAFT_KEY, draft);
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("legacy removal denied", "SecurityError");
    });

    expect(loadComposerDraft("user:migration-denied")).toBe(draft);
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe(draft);
    expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(
      AGENT_COMPOSER_DRAFT_KEY,
      "user:migration-denied",
    ))).toBe(draft);
    expect(warnSpy).toHaveBeenCalledTimes(1);
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

    const storedRaw = window.localStorage.getItem(
      getScopedAgentWorkbenchStorageKey(AGENT_CONVERSATION_TURNS_KEY),
    );
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

describe("agent workbench storage namespace and budget", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("isolates latest run ids by stable storage scope", () => {
    persistLatestAgentRunId("agent_run:user-a", "user:a");
    persistLatestAgentRunId("agent_run:user-b", "user:b");

    expect(window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY)).toBeNull();
    expect(loadLatestAgentRunId("user:a")).toBe("agent_run:user-a");
    expect(loadLatestAgentRunId("user:b")).toBe("agent_run:user-b");
  });

  it("shrinks persisted turns by stripping SQL bodies before evicting oldest turns", () => {
    const turns = Array.from({ length: 4 }, (_item, index) =>
      buildCompletedTurn({
        ...buildEnvelope(`answer ${index}`),
        evidence: {
          ...buildEnvelope().evidence,
          sql_executed: [`SELECT ${index} AS marker /* ${"x".repeat(900)} */`],
        },
      }),
    );

    persistStoredConversationTurns(turns, "user:budget", 1_200);

    const storedRaw = window.localStorage.getItem(
      getScopedAgentWorkbenchStorageKey(AGENT_CONVERSATION_TURNS_KEY, "user:budget"),
    );
    expect(storedRaw).toBeTruthy();
    expect(storedRaw).not.toContain("SELECT 0 AS marker");
    expect(storedRaw).not.toContain("SELECT 3 AS marker");
    expect(storedRaw).toContain("answer 3");
    expect(storedRaw).not.toContain("answer 0");
  });

  it("retries once with a shrunken turn payload when localStorage quota is exceeded", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const originalSetItem = Storage.prototype.setItem;
    let attempt = 0;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function setItemOnce(
      this: Storage,
      key: string,
      value: string,
    ) {
      attempt += 1;
      if (attempt === 1) {
        throw new DOMException("quota exceeded", "QuotaExceededError");
      }
      return originalSetItem.call(this, key, value);
    });

    persistStoredConversationTurns(
      [
        buildCompletedTurn({
          ...buildEnvelope("quota retry answer"),
          evidence: {
            ...buildEnvelope().evidence,
            sql_executed: [`SELECT * FROM fact_agent /* ${"x".repeat(20_000)} */`],
          },
        }),
      ],
      "user:quota",
    );

    const storedRaw = window.localStorage.getItem(
      getScopedAgentWorkbenchStorageKey(AGENT_CONVERSATION_TURNS_KEY, "user:quota"),
    );
    expect(attempt).toBe(2);
    expect(warnSpy).not.toHaveBeenCalled();
    expect(storedRaw).toContain("quota retry answer");
    expect(storedRaw).not.toContain("SELECT * FROM fact_agent");
  });

  it("migrates a legacy global key once and removes the old key", () => {
    window.localStorage.setItem(AGENT_CONVERSATION_TURNS_KEY, JSON.stringify([serializeConversationTurn(buildCompletedTurn(buildEnvelope("legacy answer")))]));

    const restoredTurns = loadStoredConversationTurns("user:migrated");

    expect(restoredTurns[0]?.result?.answer).toBe("legacy answer");
    expect(window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY)).toBeNull();
    expect(
      window.localStorage.getItem(
        getScopedAgentWorkbenchStorageKey(AGENT_CONVERSATION_TURNS_KEY, "user:migrated"),
      ),
    ).toContain("legacy answer");

    window.localStorage.setItem(AGENT_CONVERSATION_TURNS_KEY, JSON.stringify([serializeConversationTurn(buildCompletedTurn(buildEnvelope("second legacy answer")))]));
    expect(loadStoredConversationTurns("user:migrated")[0]?.result?.answer).toBe("legacy answer");
  });
});
