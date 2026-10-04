import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgentApiError } from "../api/agentClient";
import type { ApiClient } from "../api/client";
import type { AgentEnvelope, AgentQueryRequest } from "../api/contracts";
import { useManagedAgentRun } from "../features/agent/hooks/useManagedAgentRun";

function buildApiClient(overrides: Partial<ApiClient>): ApiClient {
  return {
    queryAgent: vi.fn(),
    createAgentRun: vi.fn(),
    getAgentRun: vi.fn(),
    cancelAgentRun: vi.fn(),
    ...overrides,
  } as unknown as ApiClient;
}

describe("useManagedAgentRun", () => {
  it.each([403, 404, 503])("preserves HTTP %s metadata when a status request fails", async (status) => {
    const path = "/api/agent/runs/agent_run%3Arestore";
    const payload = { detail: "status unavailable" };
    const getAgentRun = vi.fn().mockRejectedValue(new AgentApiError("Request failed", {
      status,
      path,
      payload,
    }));
    const { result } = renderHook(() => useManagedAgentRun(buildApiClient({ getAgentRun })));

    const failure = result.current.fetchAgentRunStatus("agent_run:restore");

    await expect(failure).rejects.toBeInstanceOf(AgentApiError);
    await expect(failure).rejects.toMatchObject({
      status,
      path,
      payload,
      message: `智能体任务状态获取失败（${status}）`,
    });
  });

  it("passes the turn gate signal to local sync queries and normalizes results", async () => {
    const signal = new AbortController().signal;
    const queryAgent = vi.fn(async () => ({
      answer: "managed answer",
      cards: [],
      evidence: {
        tables_used: [],
        filters_applied: {},
        evidence_rows: 0,
        quality_flag: "ok",
      },
      result_meta: {
        trace_id: "tr_managed_hook",
        basis: "formal",
        result_kind: "agent.local",
      },
      next_drill: [],
    }) as unknown as AgentEnvelope);
    const { result } = renderHook(() => useManagedAgentRun(buildApiClient({ queryAgent })));
    const requestBody: AgentQueryRequest = { question: "hello" };

    const payload = await result.current.queryAgentResult(requestBody, {
      version: 1,
      controller: new AbortController(),
      signal,
      isCurrent: () => true,
    });

    expect(queryAgent).toHaveBeenCalledWith(requestBody, { signal });
    expect(payload.suggested_actions).toEqual([]);
  });

  it("only releases the active managed run that it owns", () => {
    const { result } = renderHook(() => useManagedAgentRun(buildApiClient({})));

    result.current.trackActiveManagedRun("agent_run:first");
    result.current.trackActiveManagedRun("agent_run:second");
    result.current.releaseActiveManagedRun("agent_run:first");

    expect(result.current.takeActiveManagedRunId()).toBe("agent_run:second");
    expect(result.current.takeActiveManagedRunId()).toBe("");
  });

  it("swallows backend cancellation failures because the local turn is already invalidated", async () => {
    const cancelAgentRun = vi.fn(async () => {
      throw new Error("cancel failed");
    });
    const { result } = renderHook(() => useManagedAgentRun(buildApiClient({ cancelAgentRun })));

    expect(() => result.current.requestBackendRunCancel("agent_run:cancel")).not.toThrow();
    await vi.waitFor(() => expect(cancelAgentRun).toHaveBeenCalledWith("agent_run:cancel"));
  });
});
