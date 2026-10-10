import { act, fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_ANSWER_ACTIONS_LABEL,
  AGENT_CONVERSATION_LABEL,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  buildJsonResponse,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  mockManagedRunResult,
  mockNarrowAgentViewport,
  mockScrollIntoView,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";
import type { ScrollIntoViewArg } from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 滚动、焦点与复制", () => {
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

  it("refocuses the composer when a managed answer returns after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed pending focus");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("managed pending focus")).toBeInTheDocument();

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "managed focus answer returned",
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
                trace_id: "tr_managed_refocus_after_controls",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:managed-refocus-after-controls",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("managed focus answer returned")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("copies a completed assistant answer from the chat turn", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockManagedRunResult(fetchMock, {
      answer: "可复制的助手回答，只包含结论文本。",
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
        trace_id: "tr_copy_answer",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "copy this answer");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("可复制的助手回答，只包含结论文本。")).toBeInTheDocument();

    const followUpDraft = "复制后继续问风险细节";
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    await user.type(input, followUpDraft);
    input.setSelectionRange(3, 3);
    const copyButton = screen.getByRole("button", { name: /复制回答/ });
    expect(copyButton).toHaveAccessibleName(/copy this answer/);
    expect(screen.getByLabelText(AGENT_ANSWER_ACTIONS_LABEL)).toContainElement(copyButton);
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("可复制的助手回答，只包含结论文本。");
    expect(await screen.findByText("已复制")).toBeInTheDocument();
    const copyStatus = await screen.findByRole("status", { name: "复制状态" });
    expect(copyStatus).toHaveTextContent("回答已复制");
    expect(copyStatus).toHaveAttribute("aria-live", "polite");
    expect(copyStatus).toHaveAttribute("aria-atomic", "true");
    expect(copyStatus).toBeVisible();
    expect(copyStatus).toHaveClass("agent-copy-feedback");
    const toolbar = copyStatus.closest(".agent-result-toolbar");
    expect(toolbar).not.toBeNull();
    const answerMessage = toolbar?.closest(".agent-answer-message");
    expect(answerMessage).not.toBeNull();
    const answerPanel = answerMessage?.querySelector(".agent-answer-panel");
    expect(answerPanel).not.toBeNull();
    expect(
      (answerPanel?.compareDocumentPosition(toolbar as Element) ?? 0) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(input).toHaveValue(followUpDraft);
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", followUpDraft.length);
    expect(input).toHaveProperty("selectionEnd", followUpDraft.length);
    expect(screen.getByText("已复制回答 · 可以继续追问")).toBeInTheDocument();
  });

  it("returns the copy action to idle after feedback expires", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockManagedRunResult(fetchMock, {
      answer: "复制反馈会自动恢复。",
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
        trace_id: "tr_copy_feedback_reset",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "copy feedback reset check");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("复制反馈会自动恢复。")).toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: /复制回答/ });
    expect(copyButton).toHaveAccessibleName(/copy feedback reset check/);
    await user.click(copyButton);
    expect(await screen.findByRole("button", { name: /已复制/ })).toHaveAccessibleName(/copy feedback reset check/);

    expect(await screen.findByRole("button", { name: /复制回答/ }, { timeout: 2500 })).toHaveAccessibleName(
      /copy feedback reset check/,
    );
  });

  it("shows copy failure feedback without interrupting the chat", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard denied"));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockManagedRunResult(fetchMock, {
      answer: "这段回答暂时复制不了。",
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
        trace_id: "tr_copy_answer_failure",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "copy failure check");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("这段回答暂时复制不了。")).toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: /复制回答/ });
    expect(copyButton).toHaveAccessibleName(/copy failure check/);
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("这段回答暂时复制不了。");
    expect(await screen.findByRole("button", { name: /复制失败/ })).toHaveAccessibleName(/copy failure check/);
    expect(screen.getByText("这段回答暂时复制不了。")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    expect(screen.getByText("复制失败 · 可手动选择回答文本")).toBeInTheDocument();
  });

  it("shows accessible copy failure feedback when clipboard is unavailable", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    mockManagedRunResult(fetchMock, {
      answer: "这段回答需要手动复制。",
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
        trace_id: "tr_copy_unavailable",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "copy unavailable check");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("这段回答需要手动复制。")).toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: /复制回答/ });
    expect(copyButton).toHaveAccessibleName(/copy unavailable check/);
    await user.click(copyButton);

    expect(await screen.findByRole("button", { name: /复制失败/ })).toHaveAccessibleName(/copy unavailable check/);
    const copyStatus = await screen.findByRole("status", { name: "复制状态" });
    expect(copyStatus).toHaveTextContent("复制失败，请手动选择回答文本。");
    expect(copyStatus).toBeVisible();
    expect(copyStatus).toHaveClass("agent-copy-feedback");
    expect(copyStatus.closest(".agent-result-toolbar")).not.toBeNull();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("focuses the composer from the assistant continue input action", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement, options?: ScrollIntoViewArg) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    const originalInnerHeight = window.innerHeight;
    const originalVisualViewport = window.visualViewport;
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 900,
    });
    Object.defineProperty(window, "visualViewport", {
      configurable: true,
      value: {
        offsetTop: 0,
        height: 720,
      },
    });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockNarrowAgentViewport();
    mockManagedRunResult(fetchMock, {
      answer: "回答完成，可以继续追问。",
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
        trace_id: "tr_continue_input",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [
        {
          type: "inspect_lineage",
          label: "查看主线索",
          payload: {
            trace_id: "tr_continue_input",
          },
          requires_confirmation: true,
        },
        {
          type: "inspect_lineage",
          label: "查看次级线索",
          payload: {
            trace_id: "tr_continue_input_secondary",
          },
          requires_confirmation: true,
        },
      ],
    });

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed follow-up check");
      await user.click(screen.getByRole("button", { name: "发送" }));
      expect(await screen.findByText("回答完成，可以继续追问。")).toBeInTheDocument();
      const resultDrawer = screen.getByText("查看依据 · 2 项").closest("details");
      expect(resultDrawer).not.toBeNull();
      if (!resultDrawer) {
        throw new Error("Expected compact result details drawer to exist");
      }
      fireEvent.click(screen.getByText("查看依据 · 2 项"));
      expect(resultDrawer).toHaveAttribute("open");

      const copyButton = screen.getByRole("button", { name: /复制回答/ });
      expect(copyButton).toHaveAccessibleName(/managed follow-up check/);
      await user.click(copyButton);
      const copiedButton = screen.getByRole("button", { name: /已复制/ });
      expect(copiedButton).toHaveAccessibleName(/managed follow-up check/);
      copiedButton.focus();
      expect(document.activeElement).toBe(copiedButton);
      const moreSuggestedActions = screen.getByText("更多建议 · 1 项").closest("details");
      expect(moreSuggestedActions).not.toBeNull();
      if (!moreSuggestedActions) {
        throw new Error("Expected secondary suggested actions drawer to exist");
      }
      fireEvent.click(screen.getByText("更多建议 · 1 项"));
      expect(moreSuggestedActions).toHaveAttribute("open");

      const moreFollowUps = screen.getByText("更多追问");
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
      fireEvent.click(moreFollowUps);
      expect(followUpDetails).toHaveAttribute("open");
      expect(followUpOptions).toBeVisible();

      scrollTargets.length = 0;
      scrollOptions.length = 0;
      const draft = "已有草稿，继续补充";
      const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
      await user.type(input, draft);
      input.setSelectionRange(2, 2);
      expect(input).toHaveProperty("selectionStart", 2);
      Object.defineProperty(input, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 760,
          bottom: 840,
          left: 24,
          right: 360,
          width: 336,
          height: 80,
          x: 24,
          y: 760,
          toJSON: () => ({}),
        }),
      });
      const continueFollowUpChip = screen.getByRole("button", { name: /继续输入/ });
      expect(continueFollowUpChip).toHaveAccessibleName(/managed follow-up check/);
      await user.click(continueFollowUpChip);

      expect(input).toHaveValue(draft);
      expect(document.activeElement).toBe(input);
      expect(input).toHaveProperty("selectionStart", draft.length);
      expect(input).toHaveProperty("selectionEnd", draft.length);
      expect(screen.getByText("可以继续追问 · Enter 发送")).toBeInTheDocument();
      expect(scrollTargets).toContain(input);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "nearest" });
      expect(resultDrawer).not.toHaveAttribute("open");
      expect(moreSuggestedActions).not.toHaveAttribute("open");
      expect(followUpDetails).not.toHaveAttribute("open");
      expect(followUpOptions).not.toBeVisible();
    } finally {
      scrollIntoViewSpy.restore();
      Object.defineProperty(window, "innerHeight", {
        configurable: true,
        value: originalInnerHeight,
      });
      Object.defineProperty(window, "visualViewport", {
        configurable: true,
        value: originalVisualViewport,
      });
    }
  });

  it("keeps historical regeneration visible while streaming and lets the composer locate that turn", async () => {
    const user = userEvent.setup();
    const runId = "agent_run:historical-scroll-stream";
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Earlier completed response."), "agent_run:scroll-first",
      )))
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Later completed response."), "agent_run:scroll-second",
      )))
      .mockResolvedValueOnce(buildJsonResponse({
        run_id: runId, status: "queued", provider: "hermes", model: "test", transport: "cli", toolsets: "",
      }));
    let streamController!: ReadableStreamDefaultController<Uint8Array>;
    globalFetchMock.mockResolvedValueOnce(new Response(new ReadableStream<Uint8Array>({
      start(controller) { streamController = controller; },
    }), { headers: { "Content-Type": "text/event-stream" } }));
    const emit = (event: string, payload: unknown) => streamController.enqueue(
      new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`),
    );
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });

    try {
      render(<AgentWorkbenchPage />);
      fireEvent.change(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), { target: { value: "earlier streamed question" } });
      await user.click(screen.getByTestId("agent-panel-submit"));
      expect(await screen.findByText("Earlier completed response.")).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), { target: { value: "later kept question" } });
      await user.click(screen.getByTestId("agent-panel-submit"));
      expect(await screen.findByText("Later completed response.")).toBeInTheDocument();
      const earlierTurn = screen.getByText("earlier streamed question").closest<HTMLElement>(".agent-turn");

      scrollTargets.length = 0;
      await user.click(screen.getByRole("button", { name: "重新生成：earlier streamed question" }));
      await waitFor(() => expect(globalFetchMock).toHaveBeenCalled());
      expect(screen.getByRole("status", { name: "正在重新回答历史问题" })).toHaveTextContent("earlier streamed question");
      expect(scrollTargets).toContain(earlierTurn);
      scrollTargets.length = 0;

      act(() => emit("run_delta", { run_id: runId, seq: 1, channel: "answer", text: "Historical streamed answer", created_at: "2026-09-22T00:00:00Z" }));
      const partialAnswer = await screen.findByLabelText("正在生成的回答");
      expect(partialAnswer).toHaveTextContent("Historical streamed answer");
      expect(partialAnswer.closest(".agent-turn")).toBe(earlierTurn);
      expect(scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom")).toBe(false);

      await user.click(screen.getByRole("button", { name: "查看正在回答的问题" }));
      expect(scrollTargets.at(-1)).toBe(earlierTurn);
      act(() => emit("run_update", buildManagedRunPayload(buildLocalOrdinaryTextResult("Historical final answer."), runId)));
      expect(await screen.findByText("Historical final answer.")).toBeInTheDocument();
      expect(screen.getByText("Later completed response.")).toBeInTheDocument();
      expect(screen.queryByRole("status", { name: "正在重新回答历史问题" })).not.toBeInTheDocument();
      expect(scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom")).toBe(false);
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("does not force-scroll to the latest turn while the user is reading earlier history", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "read history without jumping");
      await user.click(screen.getByTestId("agent-panel-submit"));

      const conversation = await screen.findByLabelText(AGENT_CONVERSATION_LABEL);
      const conversationBottom = screen.getByTestId("agent-conversation-bottom");
      const composerDock = document.querySelector<HTMLElement>(".agent-composer-dock");
      expect(composerDock).not.toBeNull();
      if (!composerDock) {
        throw new Error("Expected the sticky composer dock to exist");
      }

      // The live page scrolls its document/host ancestor; the conversation itself is not a scroller.
      Object.defineProperty(conversation, "scrollHeight", {
        configurable: true,
        value: 600,
      });
      Object.defineProperty(conversation, "clientHeight", {
        configurable: true,
        value: 600,
      });
      Object.defineProperty(conversation, "scrollTop", {
        configurable: true,
        value: 0,
      });
      Object.defineProperty(conversationBottom, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 1320,
          bottom: 1321,
          left: 0,
          right: 1,
          width: 1,
          height: 1,
          x: 0,
          y: 1320,
          toJSON: () => ({}),
        }),
      });
      Object.defineProperty(composerDock, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 720,
          bottom: 880,
          left: 0,
          right: 400,
          width: 400,
          height: 160,
          x: 0,
          y: 720,
          toJSON: () => ({}),
        }),
      });
      fireEvent.scroll(document);
      scrollTargets.length = 0;

      await act(async () => {
        resolveCreateRun(
          buildJsonResponse(
            buildManagedRunPayload(
              {
                answer: "history read answer returned",
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
                  trace_id: "tr_history_read_no_jump",
                  basis: "formal",
                  result_kind: "agent.hermes",
                },
                next_drill: [],
                suggested_actions: [],
              },
              "agent_run:history-read-no-jump",
            ),
          ),
        );
        await Promise.resolve();
      });

      expect(await screen.findByText("history read answer returned")).toBeInTheDocument();
      expect(scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom")).toBe(false);
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("does not resume following updates after the reader scrolls below the transcript", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "read content below transcript");
      await user.click(screen.getByTestId("agent-panel-submit"));

      const conversationBottom = await screen.findByTestId("agent-conversation-bottom");
      const composerDock = document.querySelector<HTMLElement>(".agent-composer-dock");
      expect(composerDock).not.toBeNull();
      if (!composerDock) {
        throw new Error("Expected the sticky composer dock to exist");
      }

      Object.defineProperty(conversationBottom, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 80,
          bottom: 81,
          left: 0,
          right: 1,
          width: 1,
          height: 1,
          x: 0,
          y: 80,
          toJSON: () => ({}),
        }),
      });
      Object.defineProperty(composerDock, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 720,
          bottom: 880,
          left: 0,
          right: 400,
          width: 400,
          height: 160,
          x: 0,
          y: 720,
          toJSON: () => ({}),
        }),
      });
      fireEvent.scroll(document);
      scrollTargets.length = 0;

      await act(async () => {
        resolveCreateRun(
          buildJsonResponse(
            buildManagedRunPayload(
              buildLocalOrdinaryTextResult("below-transcript update returned"),
              "agent_run:below-transcript-no-jump",
            ),
          ),
        );
        await Promise.resolve();
      });

      expect(await screen.findByText("below-transcript update returned")).toBeInTheDocument();
      expect(
        scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom"),
      ).toBe(false);
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("resumes following updates when the transcript is scrolled back to its bottom", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "resume following near composer");
      await user.click(screen.getByTestId("agent-panel-submit"));

      const conversation = await screen.findByLabelText(AGENT_CONVERSATION_LABEL);
      const conversationBottom = screen.getByTestId("agent-conversation-bottom");
      const composerDock = document.querySelector<HTMLElement>(".agent-composer-dock");
      expect(composerDock).not.toBeNull();
      if (!composerDock) {
        throw new Error("Expected the sticky composer dock to exist");
      }

      Object.defineProperty(conversation, "scrollHeight", {
        configurable: true,
        value: 1800,
      });
      Object.defineProperty(conversation, "clientHeight", {
        configurable: true,
        value: 600,
      });
      Object.defineProperty(conversation, "scrollTop", {
        configurable: true,
        value: 120,
        writable: true,
      });
      let conversationBottomTop = 1320;
      Object.defineProperty(conversationBottom, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: conversationBottomTop,
          bottom: conversationBottomTop + 1,
          left: 0,
          right: 1,
          width: 1,
          height: 1,
          x: 0,
          y: conversationBottomTop,
          toJSON: () => ({}),
        }),
      });
      Object.defineProperty(composerDock, "getBoundingClientRect", {
        configurable: true,
        value: () => ({
          top: 720,
          bottom: 880,
          left: 0,
          right: 400,
          width: 400,
          height: 160,
          x: 0,
          y: 720,
          toJSON: () => ({}),
        }),
      });

      const scrollTo = vi.fn();
      Object.defineProperty(conversation, "scrollTo", { configurable: true, value: scrollTo });
      fireEvent.scroll(conversation);
      expect(screen.getByRole("button", { name: "回到最新回答" })).toBeInTheDocument();
      conversation.scrollTop = 1200;
      conversationBottomTop = 760;
      fireEvent.scroll(conversation);
      scrollTargets.length = 0;

      await act(async () => {
        resolveCreateRun(
          buildJsonResponse(
            buildManagedRunPayload(
              {
                answer: "near-composer update returned",
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
                  trace_id: "tr_resume_following_near_composer",
                  basis: "formal",
                  result_kind: "agent.hermes",
                },
                next_drill: [],
                suggested_actions: [],
              },
              "agent_run:resume-following-near-composer",
            ),
          ),
        );
        await Promise.resolve();
      });

      expect(await screen.findByText("near-composer update returned")).toBeInTheDocument();
      expect(scrollTo).toHaveBeenCalledWith({ top: 1800, behavior: "instant" });
      expect(screen.queryByRole("button", { name: "回到最新回答" })).not.toBeInTheDocument();
    } finally {
      scrollIntoViewSpy.restore();
    }
  });
});
