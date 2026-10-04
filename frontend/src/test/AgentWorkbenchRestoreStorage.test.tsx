import { act, fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_COMPOSER_DRAFT_KEY,
  AGENT_CONVERSATION_LABEL,
  AGENT_CONVERSATION_TURNS_KEY,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  AGENT_RESTORE_ERROR_LABEL,
  AGENT_RESTORE_STATUS_LABEL,
  GITNEXUS_PROCESSES_BUTTON,
  LATEST_AGENT_RUN_ID_KEY,
  buildJsonResponse,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  getRetryTurnAction,
  getWaitStatusStopAction,
  mockManagedRunResult,
  mockScrollIntoView,
  openGitNexusTools,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 恢复与本地持久化", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let globalFetchMock: ReturnType<typeof vi.fn>;

  function render(ui: ReactElement, options?: Parameters<typeof rtlRender>[1]) {
    return renderWithAgentClient(fetchMock, ui, options);
  }

  beforeEach(() => {
    fetchMock = vi.fn();
    globalFetchMock = vi.fn();
    vi.stubGlobal("fetch", globalFetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("flushes an unsent composer draft when the page unmounts", () => {
    const { unmount } = render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "draft question before refresh" },
    });
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("draft question before refresh");
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();

    unmount();
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft question before refresh");
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("draft question before refresh");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("coalesces rapid composer draft writes while updating the input immediately", () => {
    vi.useFakeTimers();
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    try {
      render(<AgentWorkbenchPage />);

      const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
      fireEvent.change(input, { target: { value: "d" } });
      fireEvent.change(input, { target: { value: "dr" } });
      fireEvent.change(input, { target: { value: "draft" } });

      expect(input).toHaveValue("draft");
      expect(setItemSpy.mock.calls.filter(([key]) => key === AGENT_COMPOSER_DRAFT_KEY)).toHaveLength(0);

      act(() => {
        vi.runOnlyPendingTimers();
      });

      const draftWrites = setItemSpy.mock.calls.filter(([key]) => key === AGENT_COMPOSER_DRAFT_KEY);
      expect(draftWrites).toEqual([[AGENT_COMPOSER_DRAFT_KEY, "draft"]]);
    } finally {
      setItemSpy.mockRestore();
    }
  });

  it("clears the composer draft after send and new conversation", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(fetchMock, {
      answer: "draft submitted answer",
      cards: [],
      evidence: {
        tables_used: ["hermes_cli"],
        filters_applied: {
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
        },
        evidence_rows: 1,
        quality_flag: "ok",
      },
      result_meta: {
        trace_id: "tr_draft_clear",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "draft to submit");
    await waitFor(() => {
      expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to submit");
    });

    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("draft submitted answer")).toBeInTheDocument();
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "draft to discard");
    await waitFor(() => {
      expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to discard");
    });
    await user.click(screen.getByRole("button", { name: "新对话" }));

    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("");
    await waitFor(() => {
      expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    });
  });

  it("clears a typed composer draft without sending", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    render(<AgentWorkbenchPage />);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    Object.defineProperty(input, "getBoundingClientRect", {
      configurable: true,
      value: () => ({
        top: 120,
        bottom: 180,
        left: 24,
        right: 360,
        width: 336,
        height: 60,
        x: 24,
        y: 120,
        toJSON: () => ({}),
      }),
    });

    try {
      await user.type(input, "draft to clear");
      await waitFor(() => {
        expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to clear");
      });
      scrollTargets.length = 0;

      const clearButton = screen.getByRole("button", { name: /清空输入/ });
      expect(clearButton).toHaveAccessibleName(/draft to clear/);
      await user.click(clearButton);

      expect(input).toHaveValue("");
      expect(document.activeElement).toBe(input);
      expect(screen.getByText("已清空输入 · 可以重新输入")).toBeInTheDocument();
      expect(scrollTargets).not.toContain(input);
      expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("does not let a pending restore repopulate a cleared conversation", async () => {
    const user = userEvent.setup();
    let resolveRestore!: (value: Response) => void;
    const restoreResponse = new Promise<Response>((resolve) => {
      resolveRestore = resolve;
    });
    const restoredResult = buildLocalOrdinaryTextResult("late restored answer");
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:late-restore");
    window.localStorage.setItem(
      AGENT_CONVERSATION_TURNS_KEY,
      JSON.stringify([
        {
          id: "turn:restored-before-clear",
          question: "restored before clear",
          retryMode: "ordinary",
          agentRun: buildManagedRunPayload(restoredResult, "agent_run:restored-before-clear"),
          result: restoredResult,
          error: null,
        },
      ]),
    );
    fetchMock.mockReturnValueOnce(restoreResponse);

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("restored before clear")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "新对话" }));
    expect(screen.queryByLabelText(AGENT_CONVERSATION_LABEL)).not.toBeInTheDocument();

    await act(async () => {
      resolveRestore(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "late restored answer",
              cards: [],
              evidence: {
                tables_used: ["hermes_cli"],
                filters_applied: {
                  provider: "hermes",
                  model: "gpt-5.5",
                  transport: "bridge",
                  toolsets: "file",
                },
                evidence_rows: 1,
                quality_flag: "ok",
              },
              result_meta: {
                trace_id: "tr_late_restore",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-restore",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("late restored answer")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(AGENT_CONVERSATION_LABEL)).not.toBeInTheDocument();
  });

  it("restores saved conversation turns and continues with restored context", async () => {
    const user = userEvent.setup();
    const restoredResult = {
      answer: "restored first answer",
      cards: [],
      evidence: {
        tables_used: ["hermes_cli"],
        filters_applied: {
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
        },
        evidence_rows: 1,
        quality_flag: "ok",
      },
      result_meta: {
        trace_id: "tr_restored_first",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    };
    window.localStorage.setItem(
      AGENT_CONVERSATION_TURNS_KEY,
      JSON.stringify([
        {
          id: "turn:restored:first",
          question: "restored first question",
          retryMode: "ordinary",
          agentRun: buildManagedRunPayload(restoredResult, "agent_run:restored-first"),
          result: restoredResult,
          error: null,
        },
      ]),
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "answer after restored context",
        cards: [],
        evidence: {
          tables_used: ["hermes_cli"],
          filters_applied: {
            provider: "hermes",
            model: "gpt-5.5",
            transport: "bridge",
            toolsets: "file",
          },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_restored_follow_up",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:restored-follow-up",
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("restored first question")).toBeInTheDocument();
    expect(screen.getByText("restored first answer")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "follow-up after refresh");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("answer after restored context")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(1);
    expect(JSON.parse(String(runPostCalls[0]?.[1]?.body))).toMatchObject({
      question: "follow-up after refresh",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "restored first question",
              answer: "restored first answer",
              run_id: "agent_run:restored-first",
              trace_id: "tr_restored_first",
              result_kind: "agent.hermes",
            },
          ],
        },
      },
    });
  });

  it("ignores invalid saved conversation cache", () => {
    window.localStorage.setItem(AGENT_CONVERSATION_TURNS_KEY, "{not-json");

    render(<AgentWorkbenchPage />);

    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.queryByLabelText(AGENT_CONVERSATION_LABEL)).not.toBeInTheDocument();
  });

  it("merges a latest-run restore into a saved pending turn and preserves retry context", async () => {
    const user = userEvent.setup();
    const restoredResult = buildLocalOrdinaryTextResult("saved context answer");
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:pending-follow-up");
    window.localStorage.setItem(
      AGENT_CONVERSATION_TURNS_KEY,
      JSON.stringify([
        {
          id: "turn:saved-context",
          question: "saved context question",
          retryMode: "ordinary",
          agentRun: buildManagedRunPayload(restoredResult, "agent_run:saved-context"),
          result: restoredResult,
          error: null,
        },
        {
          id: "turn:pending-follow-up",
          question: "pending follow-up question",
          retryMode: "ordinary",
          conversationContext: {
            recent_turns: [
              {
                question: "saved context question",
                answer: "saved context answer",
                run_id: "agent_run:saved-context",
                trace_id: "tr_local_sync_query",
              },
            ],
          },
          error: null,
        },
      ]),
    );
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        run_id: "agent_run:pending-follow-up",
        status: "failed",
        question: "pending follow-up question",
        provider: "hermes",
        model: "gpt-5.5",
        transport: "bridge",
        toolsets: "file",
        error_message: "restore found failed run",
      }),
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "retry after restore answer",
        cards: [],
        evidence: {
          tables_used: ["hermes_cli"],
          filters_applied: {
            provider: "hermes",
            model: "gpt-5.5",
            transport: "bridge",
            toolsets: "file",
          },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_retry_after_restore",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:retry-after-restore",
    );

    render(<AgentWorkbenchPage />);

    expect(await screen.findByText("restore found failed run")).toBeInTheDocument();
    expect(screen.getAllByText("pending follow-up question")).toHaveLength(1);
    const restoredRetryAction = getRetryTurnAction("pending follow-up question");
    expect(restoredRetryAction).toHaveAccessibleName("重试这一轮：pending follow-up question");
    await user.click(restoredRetryAction);
    expect(await screen.findByText("retry after restore answer")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(1);
    expect(JSON.parse(String(runPostCalls[0]?.[1]?.body))).toMatchObject({
      question: "pending follow-up question",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "saved context question",
              answer: "saved context answer",
              run_id: "agent_run:saved-context",
              trace_id: "tr_local_sync_query",
            },
          ],
        },
      },
    });
  });

  it("restores a stopped pending answer after remount", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    const { unmount } = render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "stop and refresh this answer");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("stop and refresh this answer")).toBeInTheDocument();

    await user.click(getWaitStatusStopAction());

    await waitFor(() => {
      const storedTurns = JSON.parse(window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY) ?? "[]");
      expect(storedTurns[0]).toMatchObject({
        question: "stop and refresh this answer",
        stopped: true,
      });
    });

    unmount();
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("stop and refresh this answer");
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "late answer after stopped remount",
              cards: [],
              evidence: {
                tables_used: ["hermes_cli"],
                filters_applied: {
                  provider: "hermes",
                  model: "gpt-5.5",
                  transport: "bridge",
                  toolsets: "file",
                },
                evidence_rows: 1,
                quality_flag: "ok",
              },
              result_meta: {
                trace_id: "tr_late_after_stopped_remount",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-after-stopped-remount",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("late answer after stopped remount")).not.toBeInTheDocument();
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
  });

  it("does not restore a managed run after stopping it once the run id is known", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:known-before-stop",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockReturnValueOnce(new Promise(() => undefined));

    const { unmount } = render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "stop after run id exists");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBe("agent_run:known-before-stop");
    });

    await user.click(getWaitStatusStopAction());

    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();

    unmount();
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("stop after run id exists");
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
    // 停止后除去建 run 与首次轮询，只允许追加一次后端 cancel 请求，不得继续轮询。
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/agent/runs/agent_run%3Aknown-before-stop/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("restores the latest managed Hermes run after a refresh", async () => {
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore");
    const olderResult = buildLocalOrdinaryTextResult("older saved answer");
    window.localStorage.setItem(
      AGENT_CONVERSATION_TURNS_KEY,
      JSON.stringify([
        {
          id: "turn:older-saved",
          question: "older saved question",
          retryMode: "ordinary",
          agentRun: buildManagedRunPayload(olderResult, "agent_run:older-saved"),
          result: olderResult,
          error: null,
        },
      ]),
    );
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        buildManagedRunPayload(
          {
            answer: "刷新后恢复的 Hermes 结果。",
            cards: [],
            evidence: {
              tables_used: ["hermes_cli"],
              filters_applied: {
                provider: "hermes",
                model: "gpt-5.5",
                transport: "bridge",
                toolsets: "file",
              },
              evidence_rows: 1,
              quality_flag: "ok",
            },
            result_meta: {
              trace_id: "tr_agent_restore",
              basis: "formal",
              result_kind: "agent.hermes",
            },
            next_drill: [],
            suggested_actions: [],
          },
          "agent_run:restore",
        ),
      ),
    );

    render(<AgentWorkbenchPage />);

    expect(await screen.findByText("刷新后恢复的 Hermes 结果。")).toBeInTheDocument();
    expect(screen.getByText("older saved answer")).toBeInTheDocument();
    expect(screen.getByText(/agent_run:restore/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/runs/agent_run%3Arestore",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("continues polling a restored managed run until it completes after refresh", async () => {
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-polling");
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:restore-polling",
          status: "queued",
          run_kind: "sync",
          question: "restore polling question",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
          result: null,
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "restored polling final answer",
              cards: [],
              evidence: {
                tables_used: ["hermes_cli"],
                filters_applied: {
                  provider: "hermes",
                  model: "gpt-5.5",
                  transport: "bridge",
                  toolsets: "file",
                },
                evidence_rows: 1,
                quality_flag: "ok",
              },
              result_meta: {
                trace_id: "tr_restore_polling_final",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:restore-polling",
          ),
        ),
      );

    render(<AgentWorkbenchPage />);

    expect(await screen.findByText("restored polling final answer")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: AGENT_RESTORE_STATUS_LABEL })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs/agent_run%3Arestore-polling")).toHaveLength(
      2,
    );
  });

  it("shows a restore status while reconnecting to the latest run after refresh", () => {
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-pending");
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("status", { name: AGENT_RESTORE_STATUS_LABEL })).toHaveTextContent(
      "agent_run:restore-pending",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/runs/agent_run%3Arestore-pending",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("clears restore status when a fresh question starts after refresh", async () => {
    const user = userEvent.setup();
    let resolveRestore!: (value: Response) => void;
    const restoreResponse = new Promise<Response>((resolve) => {
      resolveRestore = resolve;
    });
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-pending-fresh-question");
    fetchMock
      .mockReturnValueOnce(restoreResponse)
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildManagedRunPayload(
            buildLocalOrdinaryTextResult("fresh answer while restore was pending"),
            "agent_run:fresh-question-while-restore",
          ),
        ),
      );

    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("status", { name: AGENT_RESTORE_STATUS_LABEL })).toHaveTextContent(
      "agent_run:restore-pending-fresh-question",
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs/agent_run%3Arestore-pending-fresh-question",
        expect.objectContaining({ method: "GET" }),
      ),
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "fresh question while restore pending");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("fresh answer while restore was pending")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: AGENT_RESTORE_STATUS_LABEL })).not.toBeInTheDocument();

    await act(async () => {
      resolveRestore(
        buildJsonResponse(
          buildManagedRunPayload(
            buildLocalOrdinaryTextResult("late restored answer after fresh question"),
            "agent_run:restore-pending-fresh-question",
          ),
        ),
      );
    });

    expect(screen.queryByText("late restored answer after fresh question")).not.toBeInTheDocument();
  });

  it("clears restore failure status after the next successful question", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-failed");
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse({ detail: "missing run" }, 500))
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildManagedRunPayload(
            buildLocalOrdinaryTextResult("fresh answer after restore failure"),
            "agent_run:fresh-after-restore-failure",
          ),
        ),
      );

    render(<AgentWorkbenchPage />);

    const restoreError = await screen.findByRole("status", { name: AGENT_RESTORE_ERROR_LABEL });
    expect(restoreError).toHaveTextContent("agent_run:restore-failed");
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBe("agent_run:restore-failed");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "fresh question after restore failure");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("fresh answer after restore failure")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: AGENT_RESTORE_ERROR_LABEL })).not.toBeInTheDocument();
  });

  it.each(["network", "503"])("restores the same run after a temporary %s failure and remount", async (failure) => {
    const runId = "agent_run:temporary-restore-failure";
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, runId);
    if (failure === "network") {
      fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    } else {
      fetchMock.mockResolvedValueOnce(buildJsonResponse({ detail: "temporarily unavailable" }, 503));
    }
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
      buildLocalOrdinaryTextResult("recovered original answer"),
      runId,
    )));

    const firstMount = render(<AgentWorkbenchPage />);
    const restoreError = await screen.findByRole("status", { name: AGENT_RESTORE_ERROR_LABEL });
    expect(restoreError).toHaveTextContent(runId);
    expect(restoreError).toHaveTextContent("已保留上次运行");
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBe(runId);
    firstMount.unmount();
    render(<AgentWorkbenchPage />);

    expect(await screen.findByText("recovered original answer")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === `/api/agent/runs/${encodeURIComponent(runId)}`)).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/agent/runs")).toBe(false);
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
  });

  it.each([403, 404])("removes an unrecoverable run marker after HTTP %s", async (status) => {
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:unavailable");
    fetchMock.mockResolvedValueOnce(buildJsonResponse({ detail: "run unavailable" }, status));

    render(<AgentWorkbenchPage />);

    const restoreError = await screen.findByRole("status", { name: AGENT_RESTORE_ERROR_LABEL });
    expect(restoreError).toHaveTextContent("agent_run:unavailable");
    expect(restoreError).toHaveTextContent("上次运行已不存在或当前无权访问");
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
  });

  it("clears restore failure status when a quick example fills the composer", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-failed-quick");
    fetchMock.mockResolvedValueOnce(buildJsonResponse({ detail: "missing run" }, 500));

    render(<AgentWorkbenchPage />);

    const restoreError = await screen.findByRole("status", { name: AGENT_RESTORE_ERROR_LABEL });
    expect(restoreError).toHaveTextContent("agent_run:restore-failed-quick");

    openGitNexusTools();
    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("请给我看 GitNexus processes");
    expect(screen.queryByRole("status", { name: AGENT_RESTORE_ERROR_LABEL })).not.toBeInTheDocument();
  });
});
