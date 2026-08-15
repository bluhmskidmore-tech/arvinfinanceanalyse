import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { AgentRunPayload } from "../features/agent/lib/agentWorkbenchModel";
import AgentLabPage from "../features/agent-lab/AgentLabPage";

const QUESTION = "组合当前最值得关注的风险是什么？";

const RESULT = {
  answer: "实验回答完成：久期风险值得优先复核。",
  cards: [
    {
      title: "风险摘要",
      type: "metric",
      value: "久期偏高",
    },
  ],
  evidence: {
    tables_used: [],
    filters_applied: {},
    evidence_rows: 0,
    quality_flag: "ok",
  },
  result_meta: {
    basis: "formal",
    formal_use_allowed: false,
  },
  next_drill: [],
  suggested_actions: [],
};

function completedRun(runId = "agent_run:lab_test"): AgentRunPayload {
  return {
    run_id: runId,
    status: "completed",
    provider: "hermes",
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
    result: RESULT,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function renderLab(overrides: Partial<ApiClient> = {}) {
  const client: ApiClient = {
    ...createApiClient({ mode: "mock" }),
    ...overrides,
  };

  return {
    client,
    ...render(
      <MemoryRouter initialEntries={["/agent-lab"]}>
        <ApiClientProvider client={client}>
          <AgentLabPage />
        </ApiClientProvider>
      </MemoryRouter>,
    ),
  };
}

class ResizeObserverMock implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AgentLabPage", () => {
  it("sends through the managed-run API, renders the existing result UI, and stays storage-free", async () => {
    const user = userEvent.setup();
    const createAgentRun = vi.fn().mockResolvedValue(completedRun());
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");

    renderLab({ createAgentRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.keyboard("{Enter}");

    expect(await screen.findByText(RESULT.answer)).toBeInTheDocument();
    expect(screen.getByText("风险摘要")).toBeInTheDocument();
    expect(createAgentRun).toHaveBeenCalledWith(
      expect.objectContaining({ question: QUESTION, basis: "formal" }),
    );
    expect(storageWrite).not.toHaveBeenCalled();
  });

  it("stops immediately and ignores a result that arrives after cancellation", async () => {
    const user = userEvent.setup();
    const deferredRun = createDeferred<AgentRunPayload>();
    const createAgentRun = vi.fn().mockReturnValue(deferredRun.promise);
    const cancelAgentRun = vi.fn().mockResolvedValue({
      run_id: "agent_run:late",
      status: "cancelled",
      result: null,
    });

    renderLab({ createAgentRun, cancelAgentRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(await screen.findByRole("button", { name: "停止当前任务" }));

    expect(await screen.findByText("已停止，本轮不会写入正式对话。" )).toBeInTheDocument();

    deferredRun.resolve(completedRun("agent_run:late"));

    await waitFor(() => expect(cancelAgentRun).toHaveBeenCalledWith("agent_run:late"));
    expect(screen.queryByText(RESULT.answer)).not.toBeInTheDocument();
  });

  it("surfaces managed-run request failures inside the experimental thread", async () => {
    const user = userEvent.setup();
    const createAgentRun = vi.fn().mockRejectedValue(new Error("实验后端暂时不可用"));

    renderLab({ createAgentRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.click(screen.getByRole("button", { name: "发送" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("请求没有送达");
    expect(alert).toHaveTextContent("实验后端暂时不可用");
  });
});
