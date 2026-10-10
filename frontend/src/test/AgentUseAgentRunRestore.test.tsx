import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentApiError } from "../api/agentClient";
import { useAgentRunRestore } from "../features/agent/hooks/useAgentRunRestore";
import { latestAgentRunStatusRequests } from "../features/agent/lib/agentWorkbenchModel";
import type {
  AgentConversationTurn,
  AgentRunPayload,
} from "../features/agent/lib/agentWorkbenchModel";
import {
  getScopedAgentWorkbenchStorageKey,
  LATEST_AGENT_RUN_ID_KEY,
} from "../features/agent/lib/agentWorkbenchStorage";

function StrictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{children}</StrictMode>;
}

function buildCompletedRun(runId = "agent_run:restore"): AgentRunPayload {
  return {
    run_id: runId,
    status: "completed",
    provider: "hermes",
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
    result: {
      answer: "restored answer",
      cards: [],
      evidence: {
        tables_used: [],
        filters_applied: {},
        evidence_rows: 0,
        quality_flag: "ok",
      },
      result_meta: {
        trace_id: "tr_restore_hook",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    },
  };
}

function buildOptions(overrides: Partial<Parameters<typeof useAgentRunRestore>[0]> = {}) {
  return {
    shouldPersistConversation: true,
    currentConversationSession: vi.fn(() => 1),
    isCurrentConversationSession: vi.fn(() => true),
    fetchAgentRunStatus: vi.fn(async () => buildCompletedRun()),
    setRestoringRunId: vi.fn(),
    setRestoreErrorRunId: vi.fn(),
    setOrdinaryConversationMode: vi.fn(),
    setAgentRun: vi.fn(),
    setConversationTurns: vi.fn((updater: (turns: AgentConversationTurn[]) => AgentConversationTurn[]) => {
      updater([]);
    }),
    setResult: vi.fn(),
    setError: vi.fn(),
    ...overrides,
  };
}

describe("useAgentRunRestore", () => {
  afterEach(() => {
    latestAgentRunStatusRequests.clear();
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it("deduplicates StrictMode restore fetches and clears terminal latest run id", async () => {
    window.localStorage.setItem(
      getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY),
      "agent_run:restore",
    );
    const fetchAgentRunStatus = vi.fn(async () => buildCompletedRun());
    const options = buildOptions({ fetchAgentRunStatus });

    renderHook(() => useAgentRunRestore(options), { wrapper: StrictWrapper });

    await waitFor(() => {
      expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY))).toBeNull();
    });
    expect(fetchAgentRunStatus).toHaveBeenCalledTimes(1);
    expect(options.setResult).toHaveBeenCalledWith(expect.objectContaining({ answer: "restored answer" }));
  });

  it("does not commit a restored terminal payload after unmount", async () => {
    window.localStorage.setItem(
      getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY),
      "agent_run:restore",
    );
    let resolveFetch!: (payload: AgentRunPayload) => void;
    const fetchAgentRunStatus = vi.fn(
      () =>
        new Promise<AgentRunPayload>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    const setResult = vi.fn();
    const setAgentRun = vi.fn();
    const options = buildOptions({ fetchAgentRunStatus, setResult, setAgentRun });

    const { unmount } = renderHook(() => useAgentRunRestore(options));
    unmount();
    resolveFetch(buildCompletedRun());
    await Promise.resolve();
    await Promise.resolve();

    expect(setResult).not.toHaveBeenCalled();
    expect(setAgentRun).not.toHaveBeenCalled();
  });

  it.each([403, 404])("clears the saved run after a permanent HTTP %s restore error", async (status) => {
    window.localStorage.setItem(
      getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY),
      "agent_run:restore",
    );
    const setRestoreErrorRunId = vi.fn();
    const options = buildOptions({
      fetchAgentRunStatus: vi.fn(async () => {
        throw new AgentApiError("status failed", { status, path: "/api/agent/runs/restore", payload: null });
      }),
      setRestoreErrorRunId,
    });

    renderHook(() => useAgentRunRestore(options));

    await waitFor(() => expect(setRestoreErrorRunId).toHaveBeenCalledWith("agent_run:restore", false));
    expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY))).toBeNull();
  });

  it.each([
    ["network interruption", new TypeError("Failed to fetch")],
    ["service unavailable", new AgentApiError("status failed", {
      status: 503,
      path: "/api/agent/runs/restore",
      payload: null,
    })],
  ])("preserves the saved run after %s and restores it on the next mount", async (_label, error) => {
    const storageKey = getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY);
    window.localStorage.setItem(storageKey, "agent_run:restore");
    const fetchAgentRunStatus = vi.fn<() => Promise<AgentRunPayload>>()
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce(buildCompletedRun());
    const options = buildOptions({ fetchAgentRunStatus });
    const firstMount = renderHook(() => useAgentRunRestore(options));

    await waitFor(() => expect(options.setRestoreErrorRunId).toHaveBeenCalledWith("agent_run:restore", true));
    expect(window.localStorage.getItem(storageKey)).toBe("agent_run:restore");
    firstMount.unmount();
    renderHook(() => useAgentRunRestore(options));

    await waitFor(() => expect(options.setResult).toHaveBeenCalledWith(
      expect.objectContaining({ answer: "restored answer" }),
    ));
    expect(fetchAgentRunStatus).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem(storageKey)).toBeNull();
  });

  it.each(["terminal", "permanent error"])(
    "does not let a %s restore clear a newer run saved by another tab",
    async (outcome) => {
      const storageKey = getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY);
      window.localStorage.setItem(storageKey, "agent_run:restore");
      let resolveFetch!: (payload: AgentRunPayload) => void;
      let rejectFetch!: (error: unknown) => void;
      const options = buildOptions({
        fetchAgentRunStatus: vi.fn(() => new Promise<AgentRunPayload>((resolve, reject) => {
          resolveFetch = resolve;
          rejectFetch = reject;
        })),
      });
      renderHook(() => useAgentRunRestore(options));
      window.localStorage.setItem(storageKey, "agent_run:newer");

      await act(async () => {
        if (outcome === "terminal") {
          resolveFetch(buildCompletedRun());
        } else {
          rejectFetch(new AgentApiError("missing run", {
            status: 404,
            path: "/api/agent/runs/restore",
            payload: null,
          }));
        }
      });

      expect(window.localStorage.getItem(storageKey)).toBe("agent_run:newer");
    },
  );

  it.each([403, 404, 503])("classifies HTTP %s after a running restore starts polling", async (status) => {
    vi.useFakeTimers();
    const storageKey = getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY);
    window.localStorage.setItem(storageKey, "agent_run:restore");
    const fetchAgentRunStatus = vi.fn<() => Promise<AgentRunPayload>>()
      .mockResolvedValueOnce({ ...buildCompletedRun(), status: "running", result: null })
      .mockRejectedValue(new AgentApiError("status failed", {
        status,
        path: "/api/agent/runs/restore",
        payload: null,
      }));
    const options = buildOptions({ fetchAgentRunStatus });
    renderHook(() => useAgentRunRestore(options));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });

    expect(options.setRestoreErrorRunId).toHaveBeenCalledWith("agent_run:restore", status === 503);
    expect(window.localStorage.getItem(storageKey)).toBe(status === 503 ? "agent_run:restore" : null);
  });

  it("ignores a late permanent failure after the conversation session changes", async () => {
    const storageKey = getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY);
    window.localStorage.setItem(storageKey, "agent_run:restore");
    let rejectFetch!: (error: unknown) => void;
    let currentSession = 1;
    const options = buildOptions({
      isCurrentConversationSession: (session) => session === currentSession,
      fetchAgentRunStatus: vi.fn(() => new Promise<AgentRunPayload>((_resolve, reject) => {
        rejectFetch = reject;
      })),
    });
    renderHook(() => useAgentRunRestore(options));
    currentSession = 2;
    window.localStorage.setItem(storageKey, "agent_run:newer");

    await act(async () => rejectFetch(new AgentApiError("forbidden", {
      status: 403,
      path: "/api/agent/runs/restore",
      payload: null,
    })));

    expect(window.localStorage.getItem(storageKey)).toBe("agent_run:newer");
    expect(options.setRestoreErrorRunId).not.toHaveBeenCalled();
    expect(options.setAgentRun).not.toHaveBeenCalled();
  });
});
