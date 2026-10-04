import { act, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage, { EmbeddedAgentCopilot } from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_CONVERSATION_LABEL,
  AGENT_CONVERSATION_TURNS_KEY,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  AGENT_RUNTIME_STATUS_LABEL,
  LATEST_AGENT_RUN_ID_KEY,
  LOCAL_ANALYSIS_PAGE_CONTEXT,
  PAGE_CONTEXT_PLACEHOLDER,
  REPO_PATH_LABEL,
  buildGovernedPortfolioOverviewResult,
  buildJsonResponse,
  buildLocalAnalysisChatResult,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  buildWorkflowExecutionResult,
  findAgentTurnStatus,
  getAgentTurnStatus,
  getRetryTurnAction,
  getWaitStatusStopAction,
  mockManagedRunResult,
  mockScrollIntoView,
  openGitNexusTools,
  openShortcutDrawer,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";
import type { ScrollIntoViewArg } from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 托管运行与停止", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let globalFetchMock: ReturnType<typeof vi.fn>;

  function render(ui: ReactElement, options?: Parameters<typeof rtlRender>[1]) {
    return renderWithAgentClient(fetchMock, ui, options);
  }

  async function renderInterruptedRun(question: string, runId: string) {
    vi.useFakeTimers();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({
      run_id: runId, status: "running", provider: "hermes", run_kind: "managed",
    }));
    for (let attempt = 0; attempt < 4; attempt += 1) {
      if (attempt % 2 === 0) {
        fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
      } else {
        fetchMock.mockResolvedValueOnce(buildJsonResponse({ detail: "temporarily unavailable" }, 503));
      }
    }
    globalFetchMock.mockImplementation(async () => new Response("", { status: 503 }));
    render(<AgentWorkbenchPage />);
    fireEvent.change(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), { target: { value: question } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("agent-panel-submit"));
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("连接中断")).toBeInTheDocument();
    return screen.getByRole("button", { name: `重新连接：${question}` });
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

  it("routes governed portfolio overview questions directly to local agent query", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "组合概览");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "组合概览",
      basis: "formal",
      filters: {},
      position_scope: "all",
      currency_basis: "CNY",
      context: {
        intent: "portfolio_overview",
      },
    });
    expect(screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL)).toHaveTextContent("local");
  });

  it("routes pnl questions directly to local agent query without model selection", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("损益查询结果")));

    renderWithAgentClient(fetchMock, <AgentWorkbenchPage />, undefined, {
      provider: "openai-codex",
      default_model: "gpt-5.5",
      models: [
        {
          id: "deepseek-v4-pro",
          label: "DeepSeek V4 Pro",
          reasoning_efforts: ["none", "low", "high", "max"],
          default_reasoning_effort: "low",
        },
      ],
      source: "live",
    });

    await waitFor(() =>
      expect(screen.getByLabelText("回答设置")).toHaveTextContent("DeepSeek V4 Pro"),
    );
    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "损益数据呢");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("损益查询结果")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/query");
    const [, options] = fetchMock.mock.calls[0] ?? [];
    const body = JSON.parse(String(options?.body));
    expect(body).toMatchObject({
      question: "损益数据呢",
      context: { intent: "pnl_summary" },
    });
    expect(body).not.toHaveProperty("model");
    expect(body).not.toHaveProperty("reasoning_effort");
  });

  it("keeps greetings on the local fast path when a model is selected", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("我在。")));

    renderWithAgentClient(fetchMock, <AgentWorkbenchPage />, undefined, {
      provider: "hermes",
      default_model: "gpt-5.5",
      models: [
        {
          id: "gpt-5.5",
          label: "gpt-5.5",
          reasoning_efforts: ["low", "medium"],
          default_reasoning_effort: "low",
        },
      ],
      source: "live",
    });

    await waitFor(() => expect(screen.getByLabelText("回答设置")).toHaveTextContent("gpt-5.5"));

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "在吗");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("我在。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).not.toHaveProperty("model");
    expect(JSON.parse(String(options?.body))).not.toHaveProperty("reasoning_effort");
  });

  it("routes standalone workbench explanation questions to a managed run", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(AGENT_PLACEHOLDER),
      "解释当前页面的主要结论和风险点",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/runs");
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "解释当前页面的主要结论和风险点",
      routing_surface: "standalone_workbench",
    });
  });

  it("keeps a contextful workbench explanation on the managed run path", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />);

    await user.type(
      screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER),
      "解释当前页面的主要结论和风险点",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/runs");
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "解释当前页面的主要结论和风险点",
      routing_surface: "standalone_workbench",
      page_context: LOCAL_ANALYSIS_PAGE_CONTEXT,
    });
  });

  it("does not let an earlier local turn downgrade standalone workbench explanations", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()))
      .mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "组合概览");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();

    await user.type(
      screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL),
      "解释当前页面的主要结论和风险点",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/agent/runs");
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "解释当前页面的主要结论和风险点",
      routing_surface: "standalone_workbench",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "组合概览",
              result_kind: "agent.portfolio_overview",
            },
          ],
        },
      },
    });
  });

  it("routes short open chat directly to local agent query without a managed run", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("local open chat answer")));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "hi");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText("local open chat answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/query");
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/agent/runs")).toBe(false);
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "hi",
    });
  });

  it("routes agent query requests through ApiClient instead of global fetch", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("client boundary answer")));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "hi");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText("client boundary answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    expect(
      globalFetchMock.mock.calls.some(([url]) => typeof url === "string" && url.startsWith("/api/agent")),
    ).toBe(false);
  });

  it("streams a follow-up after a greeting and replaces the draft with the final answer", async () => {
    const user = userEvent.setup();
    const runId = "agent_run:chat-stream";
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("我在。")));
    fetchMock.mockResolvedValueOnce(buildJsonResponse({
      run_id: runId, status: "queued", provider: "hermes", model: "test", transport: "cli", toolsets: "",
    }));
    let streamController!: ReadableStreamDefaultController<Uint8Array>;
    globalFetchMock.mockResolvedValueOnce(new Response(new ReadableStream<Uint8Array>({
      start(controller) { streamController = controller; },
    }), { headers: { "Content-Type": "text/event-stream" } }));
    const emit = (event: string, payload: unknown) => streamController.enqueue(
      new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`),
    );

    render(<AgentWorkbenchPage />);
    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), { target: { value: "你好" } });
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("我在。")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), { target: { value: "解释一下彩虹" } });
    await user.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => expect(globalFetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/agent/runs");
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toMatchObject({
      context: { conversation: { recent_turns: [{ question: "你好", answer: "我在。" }] } },
    });
    expect(globalFetchMock.mock.calls[0]?.[0]).toContain("include_deltas=true&after_seq=0");
    act(() => emit("run_delta", { run_id: runId, seq: 1, channel: "answer", text: "光穿过雨滴", created_at: "2026-09-06T00:00:00Z" }));
    expect(await screen.findByLabelText("正在生成的回答")).toHaveTextContent("光穿过雨滴");
    expect(screen.getByTestId("agent-panel-submit")).toHaveTextContent("停止等待");
    act(() => emit("run_update", buildManagedRunPayload(buildLocalOrdinaryTextResult("彩虹来自光的折射和色散。"), runId)));
    expect(await screen.findByText("彩虹来自光的折射和色散。")).toBeInTheDocument();
    expect(screen.queryByLabelText("正在生成的回答")).not.toBeInTheDocument();
  });

  it("executes an analysis-chat suggested governed intent in the same conversation", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(
      <EmbeddedAgentCopilot
        variant="embedded"
        pageContext={{
          page_id: "dashboard",
          current_filters: { report_date: "2026-03-31" },
          selected_rows: [{ portfolio_id: "core" }],
        }}
      />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "组合概览" }));
    expect(screen.getByRole("button", { name: "确认执行：组合概览" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认执行：组合概览" }));

    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("执行建议动作：组合概览");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/agent/query");
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "组合概览",
      context: {
        user_id: "web-user",
        intent: "portfolio_overview",
        suggested_action_confirmation_token: "agent_action:test-token-portfolio-overview",
        suggested_action_requires_confirmation: true,
        suggested_action: {
          type: "execute_intent",
          label: "组合概览",
          payload: { intent: "portfolio_overview" },
          requires_confirmation: true,
          confirmation_token: "agent_action:test-token-portfolio-overview",
        },
        conversation: {
          recent_turns: [
            {
              question: "帮我判断今天的主要风险",
              result_kind: "agent.analysis_chat",
              trace_id: "tr_agent_analysis_chat",
            },
          ],
        },
      },
      page_context: {
        page_id: "dashboard",
        current_filters: { report_date: "2026-03-31" },
        selected_rows: [{ portfolio_id: "core" }],
      },
    });
  });

  it("requires an explicit second click before sending a confirmable suggested action token", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "组合概览" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "确认执行：组合概览" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认执行：组合概览" }));

    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      context: {
        suggested_action_confirmation_token: "agent_action:test-token-portfolio-overview",
        suggested_action_requires_confirmation: true,
      },
    });
  });

  it("keeps a secondary confirmable suggested action visible until the second click executes it", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          ...buildLocalAnalysisChatResult(),
          suggested_actions: [
            {
              type: "execute_intent",
              label: "组合概览",
              payload: { intent: "portfolio_overview" },
              requires_confirmation: true,
              confirmation_token: "agent_action:test-token-portfolio-overview",
            },
            {
              type: "execute_intent",
              label: "久期风险",
              payload: { intent: "duration_risk" },
              requires_confirmation: true,
              confirmation_token: "agent_action:test-token-duration-risk",
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          ...buildGovernedPortfolioOverviewResult(),
          answer: "正式久期风险结果已返回。",
          result_meta: {
            trace_id: "tr_agent_duration_risk",
            basis: "formal",
            result_kind: "agent.duration_risk",
            formal_use_allowed: true,
          },
        }),
      );

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    const moreSuggestedActions = screen.getByText("更多建议 · 1 项").closest("details");
    expect(moreSuggestedActions).not.toBeNull();
    if (!moreSuggestedActions) {
      throw new Error("Expected secondary suggested actions drawer to exist");
    }
    await user.click(screen.getByText("更多建议 · 1 项"));
    expect(moreSuggestedActions).toHaveAttribute("open");
    const secondaryActionDetails = within(moreSuggestedActions).getByText("查看参数").closest("details");
    expect(secondaryActionDetails).not.toBeNull();
    if (!secondaryActionDetails) {
      throw new Error("Expected secondary action parameter details to exist");
    }
    await user.click(within(moreSuggestedActions).getByText("查看参数"));
    expect(secondaryActionDetails).toHaveAttribute("open");

    await user.click(screen.getByRole("button", { name: "久期风险" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(moreSuggestedActions).toHaveAttribute("open");
    expect(secondaryActionDetails).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "确认执行：久期风险" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "确认执行：久期风险" }));

    expect(await screen.findByText("正式久期风险结果已返回。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(moreSuggestedActions).not.toHaveAttribute("open");
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/agent/query");
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "久期风险",
      context: {
        intent: "duration_risk",
        suggested_action_confirmation_token: "agent_action:test-token-duration-risk",
        suggested_action_requires_confirmation: true,
        suggested_action: {
          type: "execute_intent",
          label: "久期风险",
          payload: { intent: "duration_risk" },
          requires_confirmation: true,
          confirmation_token: "agent_action:test-token-duration-risk",
        },
      },
    });
  });

  it("scopes pending suggested-action confirmation to the originating turn", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "第一轮风险判断");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "第二轮风险判断");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(screen.getAllByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toHaveLength(2));
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstTurnAction = screen.getAllByRole("button", { name: "组合概览" })[0];
    expect(firstTurnAction).toBeDefined();
    if (!firstTurnAction) {
      throw new Error("Expected first turn suggested action to exist");
    }
    await user.click(firstTurnAction);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getAllByRole("button", { name: "确认执行：组合概览" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "组合概览" })).toHaveLength(1);

    const secondTurnAction = screen.getByRole("button", { name: "组合概览" });
    expect(secondTurnAction).toBeDefined();
    await user.click(secondTurnAction);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getAllByRole("button", { name: "确认执行：组合概览" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "组合概览" })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "确认执行：组合概览" }));

    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("keeps non-provider managed run errors on the managed path", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          detail: "temporary managed run outage",
        },
        500,
      ),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ordinary question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/runs",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("commits the managed run result when the repo path is edited mid-run", async () => {
    const user = userEvent.setup();
    let resolveRunStatus!: (value: Response) => void;
    const runStatusResponse = new Promise<Response>((resolve) => {
      resolveRunStatus = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:repo-edit-mid-run",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockReturnValueOnce(runStatusResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "repo edit mid run question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await findAgentTurnStatus();

    // run 进行中编辑 GitNexus 仓库路径：不能再丢弃这一轮的终态提交。
    openGitNexusTools();
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\ANOTHER-REPO");

    await act(async () => {
      resolveRunStatus(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "仓库路径编辑后仍提交的回答。",
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
                trace_id: "tr_repo_edit_mid_run",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:repo-edit-mid-run",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("仓库路径编辑后仍提交的回答。")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（500）")).not.toBeInTheDocument();
  });

  it("commits a mid-run managed failure as a turn error after the repo path changes", async () => {
    const user = userEvent.setup();
    let rejectRunStatus!: (value: Response) => void;
    const runStatusResponse = new Promise<Response>((resolve) => {
      rejectRunStatus = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:repo-edit-mid-run-failure",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockReturnValueOnce(runStatusResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "repo edit mid run failure");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await findAgentTurnStatus();

    openGitNexusTools();
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\ANOTHER-REPO");

    await act(async () => {
      rejectRunStatus(
        buildJsonResponse({
          run_id: "agent_run:repo-edit-mid-run-failure",
          status: "failed",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          error_message: "managed run failed mid repo edit",
        }),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("managed run failed mid repo edit")).toBeInTheDocument();
  });

  it("shows the expired-confirmation message when a suggested action hits the 403 confirmation gate", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(
        buildJsonResponse(
          { detail: "Suggested action execution requires a confirmation token." },
          403,
        ),
      );

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "第一轮风险判断");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "组合概览" }));
    await user.click(screen.getByRole("button", { name: "确认执行：组合概览" }));

    expect(
      await screen.findByText(
        "建议动作确认已过期或无效，请重新生成本轮回答后再执行建议动作。（Suggested action execution requires a confirmation token.）",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（403）")).not.toBeInTheDocument();
  });

  it("refocuses the composer when a managed request fails after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed failure focus");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("managed failure focus")).toBeInTheDocument();

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          {
            detail: "temporary managed run outage",
          },
          500,
        ),
      );
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("retries a failed ordinary conversation turn in place", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          detail: "temporary managed run outage",
        },
        500,
      ),
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "retry recovered managed answer",
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
          trace_id: "tr_retry_turn",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:retry",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ordinary retry question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    const retryTurnAction = getRetryTurnAction("ordinary retry question");
    expect(retryTurnAction).toHaveAccessibleName("重试这一轮：ordinary retry question");
    await user.click(retryTurnAction);

    expect(await screen.findByText("retry recovered managed answer")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（500）")).not.toBeInTheDocument();
    expect(screen.getAllByText("ordinary retry question")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    expect(JSON.parse(String(runPostCalls[1]?.[1]?.body))).toMatchObject({
      question: "ordinary retry question",
    });
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("reconnects an interrupted accepted run without creating another managed run", async () => {
    const runId = "agent_run:reconnect-original";
    const reconnect = await renderInterruptedRun("reconnect my accepted question", runId);
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
      buildLocalOrdinaryTextResult("Recovered the original managed answer."), runId,
    )));
    await act(async () => { fireEvent.click(reconnect); });

    expect(screen.getByText("Recovered the original managed answer.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe(`/api/agent/runs/${encodeURIComponent(runId)}`);
    expect(screen.queryByText("连接中断")).not.toBeInTheDocument();
  });

  it.each(["failed", "cancelled", "completed"] as const)("reconnects to the actual %s terminal state without re-executing the task", async (status) => {
    const question = `reconnect terminal ${status}`;
    const runId = `agent_run:reconnect-${status}`;
    const reconnect = await renderInterruptedRun(question, runId);
    fetchMock.mockResolvedValueOnce(buildJsonResponse({
      run_id: runId, status, provider: "hermes", run_kind: "managed",
      error_message: status === "failed" ? "Original provider execution failed." : undefined,
    }));
    await act(async () => { fireEvent.click(reconnect); });

    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: `重新连接：${question}` })).not.toBeInTheDocument();
    if (status === "failed") {
      expect(screen.getByText("任务执行失败")).toBeInTheDocument();
      expect(screen.getByText("Original provider execution failed.")).toBeInTheDocument();
      expect(getRetryTurnAction(question)).toBeEnabled();
    } else if (status === "cancelled") {
      expect(screen.getByText("任务已取消")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: `重新发送：${question}` })).toBeEnabled();
    } else {
      expect(screen.getByText("任务未返回结果")).toBeInTheDocument();
      expect(screen.getByText("智能体任务完成但未返回结果。")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: `重试这一轮：${question}` })).not.toBeInTheDocument();
    }
  });

  it("keeps the original run recoverable when reconnecting encounters another connection failure", async () => {
    const question = "reconnect after another outage";
    const runId = "agent_run:reconnect-again";
    const reconnect = await renderInterruptedRun(question, runId);
    for (let attempt = 0; attempt < 4; attempt += 1) {
      fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    }
    await act(async () => {
      fireEvent.click(reconnect);
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByRole("button", { name: `重新连接：${question}` })).toBeEnabled();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
    expect(fetchMock.mock.calls.slice(1).every(([url]) => url === `/api/agent/runs/${encodeURIComponent(runId)}`)).toBe(true);
  });

  it("deduplicates reconnect clicks and cancels the original run before ignoring a late response in a new conversation", async () => {
    const question = "reconnect then stop original";
    const runId = "agent_run:reconnect-stop";
    const reconnect = await renderInterruptedRun(question, runId);
    let resolveStatus!: (value: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => { resolveStatus = resolve; }));
    await act(async () => {
      fireEvent.click(reconnect);
      fireEvent.click(reconnect);
    });
    expect(globalFetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.filter(([url]) => url === `/api/agent/runs/${encodeURIComponent(runId)}`)).toHaveLength(5);
    expect(screen.getByTestId("agent-panel-submit")).toHaveAccessibleName(`停止等待当前回答：${question}`);

    fetchMock.mockResolvedValueOnce(buildJsonResponse({ run_id: runId, status: "cancelled" }));
    await act(async () => { fireEvent.click(screen.getByTestId("agent-panel-submit")); });
    expect(fetchMock).toHaveBeenLastCalledWith(`/api/agent/runs/${encodeURIComponent(runId)}/cancel`, expect.objectContaining({ method: "POST" }));
    expect(screen.getByRole("button", { name: `重新发送：${question}` })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新对话" }));
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
      buildLocalOrdinaryTextResult("New conversation result."), "agent_run:after-reconnect-stop",
    )));
    fireEvent.change(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), { target: { value: "new conversation question" } });
    await act(async () => { fireEvent.click(screen.getByTestId("agent-panel-submit")); });
    await act(async () => {
      resolveStatus(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("Late original answer."), runId)));
      await Promise.resolve();
    });
    expect(screen.getByText("New conversation result.")).toBeInTheDocument();
    expect(screen.queryByText("Late original answer.")).not.toBeInTheDocument();
    expect(screen.queryByText(question)).not.toBeInTheDocument();
  });

  it("reconnects a saved managed run directly and rejects an older restore after the reconnect is stopped", async () => {
    const question = "组合概览";
    const runId = "agent_run:reconnect-restoring";
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, runId);
    window.localStorage.setItem(AGENT_CONVERSATION_TURNS_KEY, JSON.stringify([{
      id: "turn:reconnect-restoring", question, retryMode: "ordinary", result: null,
      agentRun: { run_id: runId, status: "running", provider: "hermes", run_kind: "managed" },
      error: { kind: "request", message: "Connection interrupted before remount." },
    }]));
    let resolveRestore!: (value: Response) => void;
    let resolveReconnect!: (value: Response) => void;
    fetchMock
      .mockReturnValueOnce(new Promise<Response>((resolve) => { resolveRestore = resolve; }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { resolveReconnect = resolve; }));
    globalFetchMock.mockImplementation(async () => new Response("", { status: 503 }));
    render(<AgentWorkbenchPage />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: `重新连接：${question}` }));
    });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `/api/agent/runs/${encodeURIComponent(runId)}`,
      `/api/agent/runs/${encodeURIComponent(runId)}`,
    ]);

    fetchMock.mockResolvedValueOnce(buildJsonResponse({ run_id: runId, status: "cancelled" }));
    await act(async () => { fireEvent.click(screen.getByTestId("agent-panel-submit")); });
    await act(async () => {
      resolveRestore(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("Obsolete restored answer."), runId)));
      resolveReconnect(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("Obsolete reconnected answer."), runId)));
      await Promise.resolve();
    });
    expect(screen.getByRole("button", { name: `重新发送：${question}` })).toBeInTheDocument();
    expect(screen.queryByText("Obsolete restored answer.")).not.toBeInTheDocument();
    expect(screen.queryByText("Obsolete reconnected answer.")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/agent/query" || url === "/api/agent/runs")).toBe(false);
  });

  it("cues an in-place retry while the retry request is pending", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          {
            detail: "temporary managed run outage",
          },
          500,
        ),
      )
      .mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ordinary retry cue question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    const retryCueAction = getRetryTurnAction("ordinary retry cue question");
    expect(retryCueAction).toHaveAccessibleName("重试这一轮：ordinary retry cue question");
    await user.click(retryCueAction);

    expect(await screen.findByText("正在重试这一轮 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（500）")).not.toBeInTheDocument();
    const retryStopAction = screen.getByTestId("agent-panel-submit");
    expect(retryStopAction).toHaveTextContent("停止");
    expect(retryStopAction).toHaveAccessibleName(/ordinary retry cue question/);
  });

  it("retries a failed follow-up with its captured conversation context", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "first managed answer",
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
          trace_id: "tr_retry_context_first",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:retry-context-first",
    );
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          detail: "temporary managed run outage",
        },
        500,
      ),
    );
    mockManagedRunResult(
      fetchMock,
      {
        answer: "follow-up retry recovered",
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
          trace_id: "tr_retry_context_second",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:retry-context-second",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "first context question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("first managed answer")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "follow-up needs retry");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();

    const followUpRetryAction = getRetryTurnAction("follow-up needs retry");
    expect(followUpRetryAction).toHaveAccessibleName("重试这一轮：follow-up needs retry");
    await user.click(followUpRetryAction);
    expect(await screen.findByText("follow-up retry recovered")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(3);
    const capturedContext = {
      conversation: {
        recent_turns: [
          {
            question: "first context question",
            answer: "first managed answer",
            run_id: "agent_run:retry-context-first",
            trace_id: "tr_retry_context_first",
          },
        ],
      },
    };
    expect(JSON.parse(String(runPostCalls[1]?.[1]?.body))).toMatchObject({
      question: "follow-up needs retry",
      context: capturedContext,
    });
    expect(JSON.parse(String(runPostCalls[2]?.[1]?.body))).toMatchObject({
      question: "follow-up needs retry",
      context: capturedContext,
    });
  });

  it("uses a managed run for ordinary follow-ups after a local workflow", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildWorkflowExecutionResult()))
      .mockResolvedValueOnce(
        buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("post workflow ordinary answer"))),
      );

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));
    expect(await screen.findByText("Workflow Execution Steps")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "post workflow follow-up");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("post workflow ordinary answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agent/runs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/agent/runs")).toBe(true);
  });

  it("starts a managed Hermes run and polls until the result is ready", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:test",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:test",
          status: "running",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
          started_at: "2026-05-07T08:00:01Z",
          elapsed_seconds: 1,
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:test",
          status: "completed",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          elapsed_seconds: 2,
          result: {
            answer: "Hermes 托管任务完成。",
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
              trace_id: "tr_agent_run",
              basis: "formal",
              result_kind: "agent.hermes",
            },
            next_drill: [],
            suggested_actions: [],
          },
        }),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed provider task");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("Hermes 托管任务完成。")).toBeInTheDocument();
    expect(getAgentTurnStatus()).toHaveTextContent("agent_run:test");
    expect(getAgentTurnStatus()).toHaveTextContent("已完成");
    expect(getAgentTurnStatus()).toHaveAccessibleName("回答状态：managed provider task");
    expect(screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL)).toHaveTextContent("gpt-5.5");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/agent/runs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agent/runs/agent_run%3Atest",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("records request-to-run-id latency in runtime details", async () => {
    vi.useFakeTimers();
    let resolveQueuedRun!: (value: Response) => void;
    const queuedRunResponse = new Promise<Response>((resolve) => {
      resolveQueuedRun = resolve;
    });
    fetchMock.mockReturnValueOnce(queuedRunResponse).mockReturnValue(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "measure run connection" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    act(() => {
      vi.advanceTimersByTime(1_200);
    });

    await act(async () => {
      resolveQueuedRun(
        buildJsonResponse({
          run_id: "agent_run:latency",
          status: "running",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      );
    });

    const runtimeDetails = screen.getByText("运行细节").closest("details");
    expect(runtimeDetails).not.toBeNull();
    expect(runtimeDetails).toHaveTextContent("run_id: agent_run:latency");
    expect(runtimeDetails).toHaveTextContent("连接耗时 1.2 秒");
  });

  it("shows visible managed run progress while the answer is still running", async () => {
    const user = userEvent.setup();
    let resolveCompletedRun!: (value: Response) => void;
    const completedRunResponse = new Promise<Response>((resolve) => {
      resolveCompletedRun = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:progress",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:progress",
          status: "running",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
          started_at: "2026-05-07T08:00:01Z",
          elapsed_seconds: 1,
        }),
      )
      .mockReturnValueOnce(completedRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "show progress while running");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const progress = await screen.findByRole("status", { name: "回答状态：show progress while running" });
    expect(progress).toHaveTextContent("秒");
    expect(progress).toBeVisible();
    const runtimeDetailsSummary = screen.getByText("运行细节");
    expect(runtimeDetailsSummary).toHaveAccessibleName("运行细节：show progress while running");
    const runtimeDetails = runtimeDetailsSummary.closest("details");
    expect(runtimeDetails).not.toBeNull();
    expect(runtimeDetails).not.toHaveAttribute("open");
    await waitFor(() => {
      });
    fireEvent.click(runtimeDetailsSummary);
    expect(runtimeDetails).toHaveAttribute("open");
    expect(progress).toBeVisible();
    expect(getAgentTurnStatus()).toHaveTextContent("Hermes 正在分析");

    await act(async () => {
      resolveCompletedRun(
        buildJsonResponse({
          run_id: "agent_run:progress",
          status: "completed",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          elapsed_seconds: 2,
          result: {
            answer: "progress run completed",
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
              trace_id: "tr_agent_progress",
              basis: "formal",
              result_kind: "agent.hermes",
            },
            next_drill: [],
            suggested_actions: [],
          },
        }),
      );
      await Promise.resolve();
    });
    expect(await screen.findByText("progress run completed")).toBeInTheDocument();
  });

  it("keeps the submitted question and Hermes answer together as a chat turn", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(fetchMock, {
      answer: "这是更像对话的一次回答。",
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
        trace_id: "tr_agent_conversation",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed conversation check");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const conversation = await screen.findByLabelText(AGENT_CONVERSATION_LABEL);
    expect(conversation).toHaveTextContent("managed conversation check");
    expect(conversation).toHaveTextContent("这是更像对话的一次回答。");
    expect(conversation).toHaveTextContent("已完成");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("");
    expect(document.activeElement).toBe(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL));
  });

  it("regenerates a completed ordinary answer in the same chat turn", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第一版回答。",
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
          trace_id: "tr_regenerate_first",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:regenerate-first",
    );
    let resolveRegenerateResponse!: (value: Response) => void;
    const regenerateResponse = new Promise<Response>((resolve) => {
      resolveRegenerateResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(regenerateResponse);
    const regeneratePayload = buildJsonResponse(
      buildManagedRunPayload(
        {
          answer: "重新生成后的回答。",
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
            trace_id: "tr_regenerate_second",
            basis: "formal",
            result_kind: "agent.hermes",
          },
          next_drill: [],
          suggested_actions: [],
        },
        "agent_run:regenerate-second",
      ),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "regenerate this");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一版回答。")).toBeInTheDocument();

    const regenerateButton = screen.getByRole("button", { name: /重新生成/ });
    expect(regenerateButton).toHaveAccessibleName(/regenerate this/);
    await user.click(regenerateButton);
    const regenerateStopAction = screen.getByTestId("agent-panel-submit");
    expect(regenerateStopAction).toHaveTextContent("停止");
    expect(regenerateStopAction).toHaveAccessibleName(/regenerate this/);
    regenerateStopAction.focus();
    await act(async () => {
      resolveRegenerateResponse(regeneratePayload);
      await Promise.resolve();
    });

    expect(await screen.findByText("重新生成后的回答。")).toBeInTheDocument();
    expect(screen.queryByText("第一版回答。")).not.toBeInTheDocument();
    expect(screen.getAllByText("regenerate this")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(2);
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("stops a historical regeneration without clearing the newer answer or accepting a late result", async () => {
    const user = userEvent.setup();
    let resolveRegeneration!: (value: Response) => void;
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("First completed answer."), "agent_run:historical-first",
      )))
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Newer completed answer."), "agent_run:historical-second",
      )))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { resolveRegeneration = resolve; }));

    render(<AgentWorkbenchPage />);
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "historical question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("First completed answer.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "newer question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("Newer completed answer.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新生成：historical question" }));
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(screen.getByText("Newer completed answer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新发送：historical question" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新发送：newer question" })).not.toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("historical question");

    await act(async () => {
      resolveRegeneration(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Late historical replacement."), "agent_run:historical-late",
      )));
      await Promise.resolve();
    });
    expect(screen.queryByText("Late historical replacement.")).not.toBeInTheDocument();
    expect(screen.getByText("Newer completed answer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新发送：historical question" })).toBeInTheDocument();
  });

  it("binds pending historical regeneration controls to that question and isolates newer question editing", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Earlier answer to regenerate."), "agent_run:historical-edit-first",
      )))
      .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(
        buildLocalOrdinaryTextResult("Later answer remains available."), "agent_run:historical-edit-second",
      )))
      .mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "earlier editable question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("Earlier answer to regenerate.")).toBeInTheDocument();
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "later preserved question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("Later answer remains available.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新生成：earlier editable question" }));

    expect(screen.getByTestId("agent-panel-submit")).toHaveAccessibleName("停止等待当前回答：earlier editable question");
    expect(screen.getByRole("button", { name: "编辑问题：later preserved question" })).toBeDisabled();
    const earlierEdit = screen.getByRole("button", { name: "编辑问题：earlier editable question" });
    expect(earlierEdit).toBeEnabled();
    await user.click(earlierEdit);
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("earlier editable question");
    expect(screen.getByRole("button", { name: "重新发送：earlier editable question" })).toBeInTheDocument();
    expect(screen.getByText("Later answer remains available.")).toBeInTheDocument();
  });

  it("cues answer regeneration while the regenerate request is pending", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "第一版待重新生成回答。",
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
          trace_id: "tr_regenerate_cue_first",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:regenerate-cue-first",
    );
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "regenerate cue question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一版待重新生成回答。")).toBeInTheDocument();

    const regenerateButton = screen.getByRole("button", { name: /重新生成/ });
    expect(regenerateButton).toHaveAccessibleName(/regenerate cue question/);
    await user.click(regenerateButton);

    expect(await screen.findByText("正在重新生成 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("第一版待重新生成回答。")).not.toBeInTheDocument();
    const regenerateCueStopAction = screen.getByTestId("agent-panel-submit");
    expect(regenerateCueStopAction).toHaveTextContent("停止");
    expect(regenerateCueStopAction).toHaveAccessibleName(/regenerate cue question/);
  });

  it("shows a local acknowledgement immediately while the managed runtime accepts the run", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollOptions: unknown[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement, options?: ScrollIntoViewArg) {
      scrollTargets.push(this);
      scrollOptions.push(options);
    });
    fetchMock.mockReturnValue(new Promise(() => undefined));

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "先给我一个响应");
      await user.click(screen.getByRole("button", { name: "发送" }));

      const conversation = await screen.findByLabelText(AGENT_CONVERSATION_LABEL);
      expect(conversation).toHaveTextContent("先给我一个响应");
      expect(conversation).toHaveTextContent("已收到");
      expect(conversation).toHaveTextContent("我先判断该直接回答，还是先查证据。");
      expect(conversation).toHaveTextContent("已收到问题");
      expect(conversation).toHaveTextContent("正在选择回答路径");
      expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("");
      expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
      const bottomScrollIndex = scrollTargets.findIndex(
        (target) => target.dataset.testid === "agent-conversation-bottom",
      );
      expect(bottomScrollIndex).toBeGreaterThanOrEqual(0);
      expect(scrollOptions[bottomScrollIndex]).toMatchObject({ behavior: "smooth", block: "end" });
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("stops waiting for a pending answer and ignores a late managed result", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "stop this pending answer");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("stop this pending answer")).toBeInTheDocument();

    const waitStopAction = getWaitStatusStopAction();
    expect(waitStopAction).toHaveAccessibleName(/stop this pending answer/);
    await user.click(waitStopAction);

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("stop this pending answer");
    expect(screen.getByText("已恢复到输入框 · 可编辑后重新发送")).toBeInTheDocument();
    const stoppedEditAction = screen.getByRole("button", { name: /编辑这句/ });
    expect(stoppedEditAction).toHaveAccessibleName(/stop this pending answer/);
    await user.click(stoppedEditAction);
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("stop this pending answer");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "迟到的托管结果不应该显示。",
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
                trace_id: "tr_late_after_stop",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-after-stop",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("迟到的托管结果不应该显示。")).not.toBeInTheDocument();
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
  });

  it("keeps the next submitted question loading when a stopped request finishes late", async () => {
    const user = userEvent.setup();
    let resolveStoppedRun!: (value: Response) => void;
    const stoppedRunResponse = new Promise<Response>((resolve) => {
      resolveStoppedRun = resolve;
    });
    fetchMock
      .mockReturnValueOnce(stoppedRunResponse)
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:new-after-stop",
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "old stopped question");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => {
      expect(getWaitStatusStopAction()).toHaveAccessibleName(/old stopped question/);
    });
    await user.click(getWaitStatusStopAction());

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    await user.clear(input);
    await user.type(input, "new question after stop");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("new question after stop")).toBeInTheDocument();

    await act(async () => {
      resolveStoppedRun(buildJsonResponse(buildManagedRunPayload(buildLocalOrdinaryTextResult("late old result"))));
      await Promise.resolve();
    });

    const submitAction = screen.getByTestId("agent-panel-submit");
    expect(submitAction).toHaveTextContent("停止等待");
    expect(submitAction).toHaveAccessibleName(/new question after stop/);
    expect(screen.queryByText("late old result")).not.toBeInTheDocument();
  });

  it("stops a pending answer from the composer action", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "composer stop this answer");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("composer stop this answer")).toBeInTheDocument();
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "draft after stop");

    const composerAction = screen.getByTestId("agent-panel-submit");
    expect(composerAction).toHaveTextContent("停止等待");
    expect(composerAction).toHaveAccessibleName(/停止等待当前回答：composer stop this answer/);
    expect(composerAction).not.toBeDisabled();
    await user.click(composerAction);

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("draft after stop");
    expect(input).toHaveFocus();
    expect(screen.getByText("已停止等待 · 可继续发送当前输入")).toBeInTheDocument();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "late composer stop result should stay hidden",
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
                trace_id: "tr_late_composer_stop",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-composer-stop",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("late composer stop result should stay hidden")).not.toBeInTheDocument();
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
  });

  it("stops a pending answer with Escape and ignores a late managed result", async () => {
    const user = userEvent.setup();
    let resolveCreateRun!: (value: Response) => void;
    const createRunResponse = new Promise<Response>((resolve) => {
      resolveCreateRun = resolve;
    });
    fetchMock.mockReturnValueOnce(createRunResponse);

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "escape should stop this answer");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("escape should stop this answer")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).not.toBeDisabled();
    expect(input).toHaveValue("escape should stop this answer");
    expect(input).toHaveFocus();
    expect(screen.getByText("已恢复到输入框 · 可编辑后重新发送")).toBeInTheDocument();

    await act(async () => {
      resolveCreateRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "late escape result should stay hidden",
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
                trace_id: "tr_late_escape_stop",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-escape-stop",
          ),
        ),
      );
      await Promise.resolve();
    });

    expect(screen.queryByText("late escape result should stay hidden")).not.toBeInTheDocument();
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
  });

  it("does not stop a pending answer when Escape belongs to text composition", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "composition escape should keep running");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("composition escape should keep running")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape", isComposing: true });

    expect(screen.queryByText("已停止等待这次回答。")).not.toBeInTheDocument();
    expect(getWaitStatusStopAction()).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
  });

  it("reruns a stopped ordinary turn from the stopped callout", async () => {
    const user = userEvent.setup();
    let resolveStoppedRun!: (value: Response) => void;
    const stoppedRunResponse = new Promise<Response>((resolve) => {
      resolveStoppedRun = resolve;
    });
    fetchMock
      .mockReturnValueOnce(stoppedRunResponse)
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:stopped-rerun",
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "rerun this stopped answer");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("rerun this stopped answer")).toBeInTheDocument();

    await user.click(getWaitStatusStopAction());
    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();

    const stoppedRerunAction = screen.getByRole("button", { name: /重新发送/ });
    expect(stoppedRerunAction).toHaveAccessibleName(/rerun this stopped answer/);
    await user.click(stoppedRerunAction);

    expect(
      await screen.findByText("正在重新发送已停止等待的回答 · 可继续输入下一句"),
    ).toBeInTheDocument();
    expect(screen.queryByText("已停止等待这次回答。")).not.toBeInTheDocument();
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("");
    expect(document.activeElement).toBe(input);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(2);

    await act(async () => {
      resolveStoppedRun(
        buildJsonResponse(
          buildManagedRunPayload(
            {
              answer: "late stopped run should stay hidden",
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
                trace_id: "tr_late_stopped_rerun",
                basis: "formal",
                result_kind: "agent.hermes",
              },
              next_drill: [],
              suggested_actions: [],
            },
            "agent_run:late-stopped-rerun",
          ),
        ),
      );
      await Promise.resolve();
    });
    expect(screen.queryByText("late stopped run should stay hidden")).not.toBeInTheDocument();
  });

  it("requests backend cancellation when stopping a run with a known run id", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:cancel-me",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockReturnValueOnce(new Promise(() => undefined))
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:cancel-me",
          status: "cancelled",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
        }),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "cancel this pending run");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBe("agent_run:cancel-me");
    });

    await user.click(getWaitStatusStopAction());

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs/agent_run%3Acancel-me/cancel",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("renders a cancelled managed run as a cancelled turn with resend actions", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:cancelled-elsewhere",
          status: "queued",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: "agent_run:cancelled-elsewhere",
          status: "cancelled",
          provider: "hermes",
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          elapsed_seconds: 2,
        }),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "cancelled elsewhere");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("这次回答的任务已取消，不会再返回结果。")).toBeInTheDocument();
    expect(screen.getByText("任务已取消")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新发送：cancelled elsewhere" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑这句：cancelled elsewhere" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows elapsed managed-runtime wait status while the agent request is still running", async () => {
    vi.useFakeTimers();
    fetchMock.mockReturnValue(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "managed provider task" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const waitStatus = getAgentTurnStatus();
    expect(waitStatus).toHaveTextContent("已收到问题");
    expect(waitStatus).toHaveTextContent("已收到");
    expect(waitStatus).toHaveTextContent("我先判断该直接回答，还是先查证据。");

    const runtimeDetails = screen.getByText("运行细节").closest("details");
    expect(runtimeDetails).not.toBeNull();
    expect(runtimeDetails).not.toHaveAttribute("open");
    expect(runtimeDetails).toHaveTextContent("正在选择回答路径");
    expect(runtimeDetails).toHaveTextContent("已等待 0 秒");

    act(() => {
      vi.advanceTimersByTime(6_000);
    });

    expect(waitStatus).toHaveTextContent("连接中");
    expect(waitStatus).toHaveTextContent("还在连接回答通道，页面会继续自动更新。");
    expect(runtimeDetails).toHaveTextContent("已等待 6 秒");
    expect(runtimeDetails).toHaveTextContent("还在连接回答通道；拿到状态后会继续更新。");

    act(() => {
      vi.advanceTimersByTime(6_000);
    });

    expect(waitStatus).toHaveTextContent("还在连接");
    expect(waitStatus).toHaveTextContent("还没拿到运行状态，可以停止等待，或继续输入下一句。");
    expect(runtimeDetails).toHaveTextContent("已等待 12 秒");
    expect(runtimeDetails).toHaveTextContent(
      "还没拿到运行状态，可以停止等待后重试，或继续输入下一句。",
    );
  });
});
