import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentRunDeltaEvent } from "../api/contracts";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import AgentLabPage from "../features/agent-lab/AgentLabPage";
import type { AgentRunPayload } from "../features/agent/lib/agentWorkbenchModel";

const streamAgentLabRunEventsMock = vi.hoisted(() => vi.fn());

vi.mock("../api/agentLabRunStream", () => ({
  streamAgentLabRunEvents: (...args: unknown[]) => streamAgentLabRunEventsMock(...args),
}));

const QUESTION = "组合当前最值得关注的风险是什么？";
const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

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

function queuedRun(runId = "agent_run:lab_test"): AgentRunPayload {
  return {
    run_id: runId,
    status: "queued",
    provider: "hermes",
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
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

function createAbortError(message = "The user aborted a request.") {
  const error = new Error(message);
  error.name = "AbortError";
  return error;
}

function buildDelta(
  seq: number,
  text: string,
  runId = "agent_run:lab_test",
): AgentRunDeltaEvent {
  return {
    run_id: runId,
    seq,
    channel: "answer",
    text,
    created_at: `2026-08-15T00:00:0${seq}Z`,
  };
}

function createManualAnimationFrames() {
  const callbacks = new Map<number, FrameRequestCallback>();
  let nextId = 1;

  const requestSpy = vi
    .spyOn(window, "requestAnimationFrame")
    .mockImplementation((callback: FrameRequestCallback) => {
      const id = nextId;
      nextId += 1;
      callbacks.set(id, callback);
      return id;
    });

  const cancelSpy = vi
    .spyOn(window, "cancelAnimationFrame")
    .mockImplementation((id: number) => {
      callbacks.delete(id);
    });

  const flushOne = () => {
    const nextEntry = callbacks.entries().next();
    if (nextEntry.done) {
      return false;
    }
    const [id, callback] = nextEntry.value;
    callbacks.delete(id);
    callback(performance.now());
    return true;
  };

  const flushAll = () => {
    while (flushOne()) {
      // flush queued frames in order
    }
  };

  return {
    requestSpy,
    cancelSpy,
    flushOne,
    flushAll,
    getPendingCount: () => callbacks.size,
  };
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
  streamAgentLabRunEventsMock.mockReset();
});

afterEach(() => {
  if (originalScrollIntoView) {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: originalScrollIntoView,
    });
  } else {
    Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AgentLabPage", () => {
  it("sends through the lab-only managed-run API and stays storage-free", async () => {
    const user = userEvent.setup();
    const createAgentLabRun = vi.fn().mockResolvedValue(completedRun());
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");

    renderLab({ createAgentLabRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.keyboard("{Enter}");

    expect(await screen.findByText(RESULT.answer)).toBeInTheDocument();
    expect(screen.getByText("风险摘要")).toBeInTheDocument();
    expect(createAgentLabRun).toHaveBeenCalledWith(
      expect.objectContaining({
        question: QUESTION,
        basis: "formal",
        context: expect.objectContaining({
          agent_ui_experiment: "assistant-ui-external-store",
        }),
      }),
    );
    expect(createAgentLabRun.mock.calls[0]?.[0]?.context).not.toHaveProperty(
      "agent_stream_protocol",
    );
    expect(createAgentLabRun.mock.calls[0]?.[0]?.context).not.toHaveProperty(
      "agent_stream_surface",
    );
    expect(streamAgentLabRunEventsMock).not.toHaveBeenCalled();
    expect(storageWrite).not.toHaveBeenCalled();
  });

  it("renders streamed deltas in one rAF batch and reconciles to the final answer", async () => {
    const user = userEvent.setup();
    const finalDeferred = createDeferred<void>();
    const animationFrames = createManualAnimationFrames();

    streamAgentLabRunEventsMock.mockImplementationOnce(
      async (
        runId: string,
        handlers: {
          onRunDelta: (payload: AgentRunDeltaEvent) => void;
          onRunUpdate: (payload: AgentRunPayload) => boolean | void;
        },
      ) => {
        handlers.onRunDelta(buildDelta(1, "第一段判断：", runId));
        handlers.onRunDelta(buildDelta(2, "久期风险偏长。", runId));
        await finalDeferred.promise;
        handlers.onRunUpdate(completedRun(runId));
      },
    );

    renderLab({ createAgentLabRun: vi.fn().mockResolvedValue(queuedRun()) });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.keyboard("{Enter}");

    await waitFor(() => expect(streamAgentLabRunEventsMock).toHaveBeenCalledOnce());
    expect(animationFrames.requestSpy).toHaveBeenCalled();
    expect(screen.queryByText("第一段判断：久期风险偏长。")).not.toBeInTheDocument();

    animationFrames.flushAll();

    expect(await screen.findByText("第一段判断：久期风险偏长。")).toBeInTheDocument();
    expect(screen.queryByText("第一段判断：")).not.toBeInTheDocument();

    finalDeferred.resolve();
    animationFrames.flushAll();

    expect(await screen.findByText(RESULT.answer)).toBeInTheDocument();
    expect(screen.queryByText("第一段判断：久期风险偏长。")).not.toBeInTheDocument();
  });

  it("brings a newly completed answer into view", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    renderLab({ createAgentLabRun: vi.fn().mockResolvedValue(completedRun()) });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.keyboard("{Enter}");

    expect(await screen.findByText(RESULT.answer)).toBeInTheDocument();
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" }),
    );
  });

  it("preserves the viewport when the reader is browsing older turns", async () => {
    const user = userEvent.setup();
    const deferredRun = createDeferred<AgentRunPayload>();
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    renderLab({ createAgentLabRun: vi.fn().mockReturnValue(deferredRun.promise) });
    const viewport = document.querySelector<HTMLElement>(".agent-lab-thread__viewport");
    expect(viewport).not.toBeNull();
    Object.defineProperties(viewport!, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, value: 1_000 },
      scrollTop: { configurable: true, value: 100, writable: true },
    });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.keyboard("{Enter}");
    deferredRun.resolve(completedRun());

    expect(await screen.findByText(RESULT.answer)).toBeInTheDocument();
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("stops immediately and ignores a late delta after cancellation", async () => {
    const user = userEvent.setup();
    const cancelAgentRun = vi.fn().mockResolvedValue({
      run_id: "agent_run:late",
      status: "cancelled",
      result: null,
    });
    let emitLateDelta: ((payload: AgentRunDeltaEvent) => void) | null = null;
    const animationFrames = createManualAnimationFrames();

    streamAgentLabRunEventsMock.mockImplementationOnce(
      async (
        _runId: string,
        handlers: {
          onRunDelta: (payload: AgentRunDeltaEvent) => void;
          onRunUpdate: (payload: AgentRunPayload) => boolean | void;
        },
        options?: { signal?: AbortSignal },
      ) => {
        emitLateDelta = handlers.onRunDelta;
        await new Promise<void>((_resolve, reject) => {
          options?.signal?.addEventListener(
            "abort",
            () => reject(createAbortError()),
            { once: true },
          );
        });
      },
    );

    renderLab({
      createAgentLabRun: vi.fn().mockResolvedValue(queuedRun("agent_run:late")),
      cancelAgentRun,
    });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(streamAgentLabRunEventsMock).toHaveBeenCalledOnce());
    await user.click(await screen.findByRole("button", { name: "停止当前任务" }));

    expect(await screen.findByText("已停止，本轮不会写入正式对话。")).toBeInTheDocument();

    const lateDeltaEmitter = emitLateDelta as ((payload: AgentRunDeltaEvent) => void) | null;
    if (lateDeltaEmitter !== null) {
      lateDeltaEmitter(buildDelta(1, "这段迟到回答不该显示。", "agent_run:late"));
    }
    animationFrames.flushAll();

    expect(screen.queryByText("这段迟到回答不该显示。")).not.toBeInTheDocument();
    await waitFor(() => expect(cancelAgentRun).toHaveBeenCalledWith("agent_run:late"));
  });

  it("stops immediately and ignores a completed result that arrives after cancellation", async () => {
    const user = userEvent.setup();
    const deferredRun = createDeferred<AgentRunPayload>();
    const createAgentLabRun = vi.fn().mockReturnValue(deferredRun.promise);
    const cancelAgentRun = vi.fn().mockResolvedValue({
      run_id: "agent_run:late",
      status: "cancelled",
      result: null,
    });

    renderLab({ createAgentLabRun, cancelAgentRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(await screen.findByRole("button", { name: "停止当前任务" }));

    expect(await screen.findByText("已停止，本轮不会写入正式对话。")).toBeInTheDocument();

    deferredRun.resolve(completedRun("agent_run:late"));

    await waitFor(() => expect(cancelAgentRun).toHaveBeenCalledWith("agent_run:late"));
    expect(streamAgentLabRunEventsMock).not.toHaveBeenCalled();
    expect(screen.queryByText(RESULT.answer)).not.toBeInTheDocument();
  });

  it("surfaces managed-run request failures inside the experimental thread", async () => {
    const user = userEvent.setup();
    const createAgentLabRun = vi.fn().mockRejectedValue(new Error("实验后端暂时不可用"));

    renderLab({ createAgentLabRun });

    await user.type(screen.getByRole("textbox", { name: "向 Agent Lab 提问" }), QUESTION);
    await user.click(screen.getByRole("button", { name: "发送" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("请求没有送达");
    expect(alert).toHaveTextContent("实验后端暂时不可用");
  });
});
