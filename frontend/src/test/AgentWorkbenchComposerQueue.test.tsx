import { act, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage, { EmbeddedAgentCopilot } from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_CONVERSATION_LABEL,
  AGENT_CONVERSATION_TURNS_KEY,
  AGENT_FOLLOW_UP_SUGGESTIONS_LABEL,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  AGENT_QUEUED_QUERIES_KEY,
  AGENT_WORKBENCH_CSS_PATH,
  GITNEXUS_PROCESSES_BUTTON,
  LATEST_AGENT_RUN_ID_KEY,
  LOCAL_ANALYSIS_PAGE_CONTEXT,
  buildJsonResponse,
  buildLocalAnalysisChatResult,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  buildWorkflowExecutionResult,
  getQueuedFollowUpStatus,
  getWaitStatusStopAction,
  mockManagedRunResult,
  mockScrollIntoView,
  openGitNexusTools,
  openShortcutDrawer,
  queryQueuedFollowUpStatus,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 输入区与排队", () => {
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

  it("fills the composer with a drill follow-up when a next_drill chip is clicked", async () => {
    const user = userEvent.setup();
    const baseResult = buildLocalAnalysisChatResult();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        ...baseResult,
        next_drill: [{ dimension: "term_bucket", label: "期限桶" }],
      }),
    );

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "继续下钻：期限桶" }));

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue(
      "请基于当前 evidence 继续下钻：期限桶",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("clicking GitNexus quick example fills the query box", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    const prompt = "请给我看 GitNexus processes";
    const input = screen.getByPlaceholderText(AGENT_PLACEHOLDER) as HTMLTextAreaElement;
    expect(input).toHaveValue(prompt);
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", prompt.length);
    expect(input).toHaveProperty("selectionEnd", prompt.length);
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("replaces a queued follow-up when a compact quick example fills the composer", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "quick replacement first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("quick replacement first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued draft should be replaced by quick example");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced by quick example");

    const quickExamples = openGitNexusTools()!;
    await user.click(
      within(quickExamples).getByRole("button", {
        name: "组合概览：规模、损益、久期和信用风险有什么变化？",
      }),
    );

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("组合概览：规模、损益、久期和信用风险有什么变化？");
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(input).toHaveFocus();
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("keeps send disabled until the composer has text", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    const sendButton = screen.getByRole("button", { name: "发送" });
    expect(sendButton).toBeDisabled();
    expect(sendButton).not.toHaveAttribute("style");
    screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL).focus();
    await user.keyboard("{Enter}");

    expect(sendButton).toBeDisabled();
    expect(sendButton).not.toHaveAttribute("style");
    expect(screen.queryByText("请输入查询问题。")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fills a focused follow-up question from assistant quick chips", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(fetchMock, {
      answer: "回答里已经给出主要结论。",
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
        trace_id: "tr_followup_chip",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "need a follow-up chip");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("回答里已经给出主要结论。")).toBeInTheDocument();

    const moreFollowUps = screen.getByText("更多追问");
    expect(screen.getByLabelText(AGENT_FOLLOW_UP_SUGGESTIONS_LABEL)).toContainElement(moreFollowUps);
    const followUpDetails = moreFollowUps.closest("details");
    expect(followUpDetails).not.toBeNull();
    if (!followUpDetails) {
      throw new Error("Expected follow-up details to exist");
    }
    const followUpOptions = followUpDetails.querySelector(".agent-follow-up-chips__options");
    expect(followUpOptions).not.toBeNull();
    if (!followUpOptions) {
      throw new Error("Expected follow-up options to exist");
    }
    expect(followUpDetails).not.toHaveAttribute("open");
    expect(followUpOptions).not.toBeVisible();
    fireEvent.click(moreFollowUps);
    expect(followUpDetails).toHaveAttribute("open");
    expect(followUpOptions).toBeVisible();

    const evidenceFollowUpChip = screen.getByRole("button", { name: /展开依据/ });
    expect(evidenceFollowUpChip).toHaveAccessibleName(/need a follow-up chip/);
    await user.click(evidenceFollowUpChip);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue("请基于上一轮回答展开证据依据和关键假设。");
    expect(document.activeElement).toBe(input);
    expect(input).toHaveProperty("selectionStart", input.value.length);
    expect(input).toHaveProperty("selectionEnd", input.value.length);
    expect(screen.getByText("已填入追问 · Enter 发送")).toBeInTheDocument();
    expect(followUpDetails).not.toHaveAttribute("open");
    expect(followUpOptions).not.toBeVisible();
  });

  it("edits a completed ordinary question into the composer for a revised turn", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第一轮回答用于编辑。",
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
          trace_id: "tr_edit_first",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:edit-first",
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "改写后问题的回答。",
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
          trace_id: "tr_edit_second",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:edit-second",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "edit original question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一轮回答用于编辑。")).toBeInTheDocument();

    const editQuestionButton = screen.getByRole("button", { name: /编辑问题/ });
    expect(editQuestionButton).toHaveAccessibleName(/edit original question/);
    await user.click(editQuestionButton);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue("edit original question");
    expect(document.activeElement).toBe(input);
    expect(input).toHaveProperty("selectionStart", input.value.length);
    expect(input).toHaveProperty("selectionEnd", input.value.length);
    expect(screen.getByText("已放回输入框 · 改完按 Enter 发送")).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "edit revised question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("改写后问题的回答。")).toBeInTheDocument();
    expect(screen.getByText("edit original question")).toBeInTheDocument();
    expect(screen.getByText("edit revised question")).toBeInTheDocument();
    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    const [, secondOptions] = runPostCalls[1] ?? [];
    expect(JSON.parse(String(secondOptions?.body))).toMatchObject({
      question: "edit revised question",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "edit original question",
              answer: "第一轮回答用于编辑。",
              run_id: "agent_run:edit-first",
              trace_id: "tr_edit_first",
            },
          ],
        },
      },
    });
  });

  it("sends recent turn context with the next follow-up question", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第一轮回答：主要风险来自久期。",
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
          trace_id: "tr_first_turn",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:first",
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第二轮回答：继续解释上一轮结论。",
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
          trace_id: "tr_second_turn",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:second",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一轮回答：主要风险来自久期。")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "managed second turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第二轮回答：继续解释上一轮结论。")).toBeInTheDocument();
    expect(screen.getByText("已带入 1 轮上下文")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    const [, secondOptions] = runPostCalls[1] ?? [];
    expect(JSON.parse(String(secondOptions?.body))).toMatchObject({
      question: "managed second turn",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "managed first turn",
              answer: "第一轮回答：主要风险来自久期。",
              run_id: "agent_run:first",
              trace_id: "tr_first_turn",
              result_kind: "agent.hermes",
            },
          ],
        },
      },
    });
  });

  it("starts a fresh conversation without carrying previous turn context", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "old thread answer",
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
          trace_id: "tr_old_thread",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:old-thread",
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "fresh thread answer",
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
          trace_id: "tr_fresh_thread",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:fresh-thread",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "old thread question");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("old thread answer")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新对话" }));
    expect(screen.queryByLabelText(AGENT_CONVERSATION_LABEL)).not.toBeInTheDocument();
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
    expect(window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY)).toBe("[]");
    expect(screen.getByText("已开启新对话 · 可以直接提问")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "fresh thread question");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("fresh thread answer")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    const freshBody = JSON.parse(String(runPostCalls[1]?.[1]?.body));
    expect(freshBody).toMatchObject({
      question: "fresh thread question",
      context: {
        user_id: "web-user",
      },
    });
    expect(freshBody.context.conversation).toBeUndefined();
  });

  it("queues a typed follow-up while the current answer is still running", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    fetchMock.mockReturnValueOnce(firstRunResponse);
    mockManagedRunResult(
      fetchMock,
      {
        answer: "second queued answer",
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
          trace_id: "tr_queued_second",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:queued-second",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "queued first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("queued first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));

    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("下一句");
    expect(queuedPreview).toHaveTextContent("当前回答完成后发送");
    expect(queuedPreview).toHaveTextContent("queued second turn");
    const queuedPreviewActions = within(queuedPreview).getAllByRole("button");
    expect(queuedPreviewActions[0]).toHaveAccessibleName(/queued second turn/);
    expect(queuedPreviewActions[1]).toHaveAccessibleName(/queued second turn/);
    expect(screen.queryByText("已排队：queued second turn")).not.toBeInTheDocument();
    expect(screen.queryByText("当前回答完成后自动发送。")).not.toBeInTheDocument();
    const composerDock = document.querySelector(".agent-composer-dock");
    expect(composerDock).not.toBeNull();
    expect(composerDock).toContainElement(queuedPreview);
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).not.toHaveTextContent("下一句");
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).not.toHaveTextContent("queued second turn");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    expect(screen.getByText("已接住下一句：queued second turn · 回答完自动发送")).toBeInTheDocument();
    await user.click(queuedPreviewActions[0]);
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("queued second turn");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    await user.click(within(getQueuedFollowUpStatus()).getAllByRole("button")[1]);
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);

    await act(async () => {
      resolveFirstRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "first queued answer",
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
                trace_id: "tr_queued_first",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:queued-first",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("queued second turn")).toBeInTheDocument();
    expect(await screen.findByText("first queued answer")).toBeInTheDocument();
    expect(await screen.findByText("second queued answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(2);
    });

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(JSON.parse(String(runPostCalls[1]?.[1]?.body))).toMatchObject({
      question: "queued second turn",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "queued first turn",
              answer: "first queued answer",
              run_id: "agent_run:queued-first",
              trace_id: "tr_queued_first",
            },
          ],
        },
      },
    });
  });

  it("cues queued follow-up dispatch after the active answer completes", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    fetchMock
      .mockReturnValueOnce(firstRunResponse)
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:queued-pending-second",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "queued pending first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("queued pending first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued pending second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(screen.getByText("已接住下一句：queued pending second turn · 回答完自动发送")).toBeInTheDocument();

    await act(async () => {
      resolveFirstRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "queued pending first answer",
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
                trace_id: "tr_queued_pending_first",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:queued-pending-first",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("queued pending second turn")).toBeInTheDocument();
    expect(await screen.findByText("正在发送排队问题 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("已接住下一句：queued pending second turn · 回答完自动发送")).not.toBeInTheDocument();
    expect(screen.queryByText("queued pending second answer")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(2);
    });
  });

  it("refocuses the composer when a queued local answer returns after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    let resolveQueuedRun!: (value: Response) => void;
    const queuedRunResponse = new Promise<Response>((resolve) => {
      resolveQueuedRun = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildWorkflowExecutionResult()))
      .mockReturnValueOnce(firstRunResponse)
      .mockReturnValueOnce(queuedRunResponse);

    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    await user.click(screen.getByRole("button", { name: /风险纪要/ }));
    expect(await screen.findByText("Workflow 执行完成 · 可以继续追问")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "local queued first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("local queued first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "local queued second turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));

    await act(async () => {
      resolveFirstRun(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("local queued first answer"), "agent_run:queued-one")));
      await Promise.resolve();
    });

    expect(await screen.findByText("local queued second turn")).toBeInTheDocument();
    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveQueuedRun(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("local queued second answer"), "agent_run:queued-two")));
      await Promise.resolve();
    });

    expect(await screen.findByText("local queued second answer")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("refocuses the composer when a queued local answer fails after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    let resolveQueuedRun!: (value: Response) => void;
    const queuedRunResponse = new Promise<Response>((resolve) => {
      resolveQueuedRun = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildWorkflowExecutionResult()))
      .mockReturnValueOnce(firstRunResponse)
      .mockReturnValueOnce(queuedRunResponse);

    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    await user.click(screen.getByRole("button", { name: /风险纪要/ }));
    expect(await screen.findByText("Workflow 执行完成 · 可以继续追问")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "local queued fail first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("local queued fail first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "local queued fail second turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));

    await act(async () => {
      resolveFirstRun(buildJsonResponse(buildLocalOrdinaryTextResult("local queued fail first answer")));
      await Promise.resolve();
    });

    expect(await screen.findByText("local queued fail second turn")).toBeInTheDocument();
    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveQueuedRun(buildJsonResponse({ detail: "local query failed" }, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("sends multiple queued follow-ups one by one after the active answer completes", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    fetchMock.mockReturnValueOnce(firstRunResponse);
    mockManagedRunResult(
      fetchMock,
      {
        answer: "multi queue second answer",
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
          trace_id: "tr_multi_queue_second",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:multi-queue-second",
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "multi queue third answer",
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
          trace_id: "tr_multi_queue_third",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:multi-queue-third",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "multi queue first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("multi queue first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "multi queue second turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("multi queue second turn");

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "multi queue third turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("multi queue second turn");
    expect(queuedPreview).toHaveTextContent("multi queue third turn");
    expect(queuedPreview).toHaveTextContent("2 句待发送");
    expect(screen.getByText("2 句已排队 · 刚加入：multi queue third turn")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).not.toHaveTextContent("multi queue third turn");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);

    await act(async () => {
      resolveFirstRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "multi queue first answer",
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
                trace_id: "tr_multi_queue_first",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:multi-queue-first",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("multi queue second turn")).toBeInTheDocument();
    expect(await screen.findByText("multi queue second answer")).toBeInTheDocument();
    expect(await screen.findByText("multi queue third turn")).toBeInTheDocument();
    expect(await screen.findByText("multi queue third answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(3);
    });

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(JSON.parse(String(runPostCalls[1]?.[1]?.body))).toMatchObject({
      question: "multi queue second turn",
    });
    expect(JSON.parse(String(runPostCalls[2]?.[1]?.body))).toMatchObject({
      question: "multi queue third turn",
    });
    expect(window.localStorage.getItem(AGENT_QUEUED_QUERIES_KEY)).toBeNull();
  });

  it("restores queued follow-up drafts after remount", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    const { unmount } = render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "remount queue first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("remount queue first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued draft after remount");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));

    expect(window.localStorage.getItem(AGENT_QUEUED_QUERIES_KEY)).toBe(
      JSON.stringify(["queued draft after remount"]),
    );

    unmount();
    render(<AgentWorkbenchPage />);

    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft after remount");
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).not.toHaveTextContent("queued draft after remount");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("");
  });

  it("keeps the docked composer action slot stable while a follow-up is running", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "stable action slot first answer",
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
          trace_id: "tr_stable_action_slot_first",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:stable-action-slot-first",
    );
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    function getDockActionSlot() {
      const dock = document.querySelector(".agent-composer-dock");
      expect(dock).not.toBeNull();
      const actionSlot = dock?.querySelector(".agent-chat-composer__actions");
      expect(actionSlot).not.toBeNull();
      if (!(actionSlot instanceof HTMLElement)) {
        throw new Error("Expected docked composer action slot to exist");
      }
      return actionSlot;
    }

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "stable action first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("stable action slot first answer")).toBeInTheDocument();

    const idleActionSlot = getDockActionSlot();
    expect(idleActionSlot).not.toHaveClass("agent-chat-composer__actions--running");
    expect(within(idleActionSlot).getByTestId("agent-panel-submit")).toHaveTextContent("发送");

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "stable action second turn");
    await user.click(within(idleActionSlot).getByTestId("agent-panel-submit"));
    expect(await screen.findByText("stable action second turn")).toBeInTheDocument();

    const runningActionSlot = getDockActionSlot();
    expect(runningActionSlot).toHaveClass("agent-chat-composer__actions--running");
    expect(within(runningActionSlot).getByRole("button", { name: "发送下一句" })).toBeDisabled();
    expect(within(runningActionSlot).getByTestId("agent-panel-submit")).toHaveTextContent("停止");
  });

  it("keeps running composer controls full-width on mobile", () => {
    const cssText = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(cssText).toContain(".agent-chat-composer__actions--running");
    expect(cssText).toContain(".agent-chat-composer__actions--running > .agent-chat-composer__queue");
    expect(cssText).toContain(".agent-chat-composer__actions--running > .agent-chat-composer__send");
    expect(cssText).toContain("grid-template-columns: 1fr");
  });

  it("allows contextual composer hints to wrap instead of widening the dock", () => {
    const cssText = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(cssText).toMatch(/\.agent-chat-composer__hint\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(cssText).toMatch(/\.agent-chat-composer__hint\s*\{[^}]*white-space:\s*normal/s);
  });

  it("queues a multiline typed follow-up with Enter while the current answer is still running", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "enter queue first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("enter queue first turn")).toBeInTheDocument();
    expect(screen.getByText("回答中按 Enter 排队下一句 · Shift+Enter 换行")).toBeInTheDocument();

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    await user.type(input, "enter queued second turn{Shift>}{Enter}{/Shift}with extra context");
    await user.keyboard("{Enter}");

    const queuedQuestion = "enter queued second turn\nwith extra context";
    expect(getQueuedFollowUpStatus()).toHaveTextContent("enter queued second turn");
    expect(getQueuedFollowUpStatus()).toHaveTextContent("with extra context");
    expect(screen.queryByText("已排队：enter queued second turn")).not.toBeInTheDocument();
    expect(screen.queryByText("当前回答完成后自动发送。")).not.toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
    expect(window.localStorage.getItem(AGENT_QUEUED_QUERIES_KEY)).toBe(JSON.stringify([queuedQuestion]));
  });

  it("keeps queued follow-up previews formatted for multiline drafts", () => {
    const cssText = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(cssText).toMatch(/\.agent-queued-draft__text\s*\{[^}]*white-space:\s*pre-wrap/s);
    expect(cssText).toMatch(/\.agent-queued-draft__queue li span:last-child\s*\{[^}]*white-space:\s*pre-wrap/s);
  });

  it("keeps a queued follow-up draft anchored to the composer while the active answer is running", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const originalInnerHeight = window.innerHeight;
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "scroll queued first turn");
      await user.click(screen.getByRole("button", { name: "发送" }));
      expect(await screen.findByText("scroll queued first turn")).toBeInTheDocument();
      scrollTargets.length = 0;

      const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
      Object.defineProperty(input, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 1200,
          bottom: 1260,
          left: 24,
          right: 360,
          width: 336,
          height: 60,
          x: 24,
          y: 1200,
          toJSON: () => ({}),
        }),
      });
      await user.type(input, "scroll queued second turn");
      await user.click(screen.getByRole("button", { name: "发送下一句" }));

      expect(getQueuedFollowUpStatus()).toHaveTextContent("scroll queued second turn");
      expect(scrollTargets.some((target) => target.getAttribute("aria-label") === AGENT_QUESTION_INPUT_LABEL)).toBe(true);
      expect(scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom")).toBe(false);
    } finally {
      scrollIntoViewSpy.restore();
      Object.defineProperty(window, "innerHeight", {
        configurable: true,
        value: originalInnerHeight,
      });
    }
  });

  it("cancels a queued follow-up when stopping the active answer", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "queued stop first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("queued stop first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued stop second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued stop second turn");

    await user.click(getWaitStatusStopAction());

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue("queued stop second turn");
    expect(document.activeElement).toBe(input);
    expect(screen.getByText("已恢复到输入框 · 可编辑后重新发送")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
  });

  it("cancels a queued follow-up without sending it after the current answer completes", async () => {
    const user = userEvent.setup();
    let resolveFirstRun!: (value: Response) => void;
    const firstRunResponse = new Promise<Response>((resolve) => {
      resolveFirstRun = resolve;
    });
    fetchMock.mockReturnValueOnce(firstRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "queued cancel first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("queued cancel first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued cancel second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("queued cancel second turn");

    const queuedPreviewActions = within(queuedPreview).getAllByRole("button");
    expect(queuedPreviewActions[1]).toHaveAccessibleName(/queued cancel second turn/);
    await user.click(queuedPreviewActions[1]);
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue("");
    expect(document.activeElement).toBe(input);
    expect(screen.getByText("已取消排队草稿 · 可以继续输入")).toBeInTheDocument();

    await act(async () => {
      resolveFirstRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "cancel first answer",
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
                trace_id: "tr_queued_cancel_first",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:queued-cancel-first",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("cancel first answer")).toBeInTheDocument();
    expect(screen.queryByText("queued cancel second turn")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
  });

  it("moves a queued follow-up back into the composer for editing", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "queued edit first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("queued edit first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued edit second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("queued edit second turn");

    const queuedPreviewActions = within(queuedPreview).getAllByRole("button");
    expect(queuedPreviewActions[0]).toHaveAccessibleName(/queued edit second turn/);
    await user.click(queuedPreviewActions[0]);

    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue("queued edit second turn");
    expect(document.activeElement).toBe(input);
    expect(input).toHaveProperty("selectionStart", input.value.length);
    expect(input).toHaveProperty("selectionEnd", input.value.length);
    expect(screen.getByText("已恢复排队草稿 · Enter 重新排队")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
  });

  it("clears a queued follow-up when editing the active question", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "question to edit while running");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("question to edit while running")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued draft should be replaced");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced");

    await user.click(getWaitStatusStopAction());
    const editQuestionButton = screen.getByRole("button", { name: /编辑问题/ });
    expect(editQuestionButton).toHaveAccessibleName(/question to edit while running/);
    await user.click(editQuestionButton);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("question to edit while running");
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(input).toHaveFocus();
  });

  it("edits the active running question directly and ignores a late managed result", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "question to edit directly");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("question to edit directly")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued draft replaced by direct edit");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft replaced by direct edit");

    const editQuestionButton = screen.getByRole("button", { name: /编辑问题/ });
    expect(editQuestionButton).toHaveAccessibleName(/question to edit directly/);
    await user.click(editQuestionButton);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("question to edit directly");
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(input).toHaveFocus();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "direct edit late result should not show",
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
                trace_id: "tr_late_after_direct_edit",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-after-direct-edit",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("direct edit late result should not show")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
  });

  it("replaces a queued follow-up when an assistant suggested action fills the composer", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第一轮给出下钻建议。",
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
          trace_id: "tr_suggested_action_queue",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [
          {
            type: "inspect_drill",
            label: "继续下钻期限桶",
            payload: { dimension: "tenor_bucket" },
            requires_confirmation: false,
          },
        ],
      },
      "agent_run:suggested-action-source",
    );
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "first suggested action source");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一轮给出下钻建议。")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "running follow-up before suggestion");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("running follow-up before suggestion")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "queued draft should be replaced by suggestion");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced by suggestion");

    await user.click(screen.getByRole("button", { name: "继续下钻期限桶" }));

    const suggestedPrompt = "请基于当前 evidence 继续下钻：继续下钻期限桶";
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue(suggestedPrompt);
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", suggestedPrompt.length);
    expect(input).toHaveProperty("selectionEnd", suggestedPrompt.length);
    expect(screen.getByText("已填入建议追问 · Enter 发送")).toBeInTheDocument();
  });

  it("submits the conversation with Enter and keeps Shift+Enter as a newline", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        answer: "已收到对话问题。",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_enter_submit",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");
    expect(input).toHaveValue("第一行\n第二行");
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(input).toHaveValue("第一行\n第二行");

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "第一行\n第二行",
    });
  });

  it("keeps submitted multiline questions formatted in user bubbles", () => {
    const cssText = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(cssText).toMatch(/\.agent-message--user \.agent-message__body\s*\{[^}]*white-space:\s*pre-wrap/s);
  });
});
