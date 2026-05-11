import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage, { AgentPanel } from "../features/agent/AgentWorkbenchPage";

const AGENT_PLACEHOLDER =
  "问一句业务问题，例如：今天损益为什么变动？当前久期风险在哪里？";
const PAGE_CONTEXT_PLACEHOLDER =
  "直接问当前页：主要结论？异常点？下一步复核什么？";
const GITNEXUS_STATUS_BUTTON = "GitNexus 状态";
const GITNEXUS_CONTEXT_BUTTON = "GitNexus 上下文";
const GITNEXUS_PROCESSES_BUTTON = "GitNexus 流程";
const RECENT_REPO_PATHS_KEY = "moss.agent.gitnexus.recentRepoPaths.v1";
const PINNED_REPO_PATHS_KEY = "moss.agent.gitnexus.pinnedRepoPaths.v1";
const LATEST_AGENT_RUN_ID_KEY = "moss.agent.latestRunId.v1";
const AGENT_CONVERSATION_TURNS_KEY = "moss.agent.conversationTurns.v1";
const MAX_PINNED_REPO_PATHS = 5;

function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function buildManagedRunPayload(result: unknown, runId = "agent_run:test", provider = "hermes") {
  return {
    run_id: runId,
    status: "completed",
    provider,
    model: "gpt-5.5",
    transport: "bridge",
    toolsets: "file",
    elapsed_seconds: 1,
    result,
  };
}

function mockManagedRunResult(
  fetchMock: ReturnType<typeof vi.fn>,
  result: unknown,
  runId = "agent_run:test",
  provider = "hermes",
) {
  fetchMock
    .mockResolvedValueOnce(
        buildJsonResponse({
          run_id: runId,
          status: "queued",
          provider,
          model: "gpt-5.5",
          transport: "bridge",
          toolsets: "file",
          queued_at: "2026-05-07T08:00:00Z",
        }),
      )
    .mockResolvedValueOnce(buildJsonResponse(buildManagedRunPayload(result, runId, provider)));
}

function buildWorkflowExecutionResult() {
  return {
    answer:
      "Executed financial workflow 'Risk Memo' (risk_memo) using governed MOSS intents: duration_risk, credit_exposure, risk_tensor. The workflow summary is not a formal financial result.",
    cards: [
      {
        title: "Workflow Execution Steps",
        type: "table",
        data: [
          {
            order: 1,
            intent: "duration_risk",
            status: "completed",
            quality: "ok",
            evidence_rows: 3,
          },
        ],
        spec: {
          columns: ["order", "intent", "status", "quality", "evidence_rows"],
        },
      },
      {
        title: "Mapped Intent Results",
        type: "table",
        data: [
          {
            intent: "duration_risk",
            result_kind: "agent.intent.duration_risk",
            answer: "Duration risk ready.",
            tables: "fact_risk_tensor",
            evidence_rows: 3,
          },
        ],
        spec: {
          columns: ["intent", "result_kind", "answer", "tables", "evidence_rows"],
        },
      },
    ],
    evidence: {
      tables_used: ["fact_risk_tensor"],
      filters_applied: {},
      evidence_rows: 3,
      quality_flag: "warning",
    },
    result_meta: {
      trace_id: "tr_workflow_risk_memo",
      basis: "formal",
      result_kind: "agent.workflow.risk_memo",
      formal_use_allowed: false,
      source_version: "sv_agent_financial_workflow_reference",
      rule_version: "rv_agent_financial_workflow_catalog_v1",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

function buildLocalOrdinaryTextResult(answer = "本地普通问题回答。") {
  return {
    answer,
    cards: [],
    evidence: {
      tables_used: ["agent_query_local"],
      filters_applied: {
        provider: "local",
        transport: "sync",
        model: "default",
        toolsets: "default",
      },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_local_sync_query",
      basis: "formal",
      result_kind: "agent.local",
    },
    next_drill: [],
    suggested_actions: [],
  };
}

function buildDexterResearchResult(domain: "stock" | "macro", answer: string) {
  const tableName = domain === "stock" ? "choice_stock_daily_observation" : "fact_choice_macro_daily";
  return {
    answer,
    cards: [
      {
        title: "Research Summary",
        type: "summary",
        value: `${domain} context ready`,
      },
    ],
    evidence: {
      tables_used: [tableName],
      filters_applied: {
        provider: "dexter",
        transport: "sync",
        model: "gpt-5.5",
        toolsets: "file",
        research_domain: domain,
      },
      evidence_rows: 1,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: `tr_dexter_${domain}`,
      basis: "formal",
      result_kind: "agent.dexter",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [],
  };
}

describe("AgentWorkbenchPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("advertises GitNexus repo graph as a supported query example", () => {
    render(<AgentWorkbenchPage />);

    expect(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
    ).toBeInTheDocument();
  });

  it("keeps the page shell while exposing AgentPanel as the reusable copilot body", () => {
    render(<AgentPanel />);

    expect(screen.queryByRole("heading", { name: "智能体对话" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toBeInTheDocument();
    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
  });

  it("renders explicit repo_path input and GitNexus quick examples", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
    expect(screen.getByLabelText("process-search-input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "固定当前仓库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "读取流程" })).toBeInTheDocument();
    expect(screen.getByLabelText("process-name-select")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "解释当前页面的主要结论和风险点" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /组合概览/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_STATUS_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_CONTEXT_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON })).toBeInTheDocument();
  });

  it("renders four financial workflow shortcut buttons", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("button", { name: /Portfolio Review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /PnL Review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Risk Memo/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Market Brief/ })).toBeInTheDocument();
  });

  it("renders stock and macro research shortcut buttons", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("button", { name: /Stock Research/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Macro Research/ })).toBeInTheDocument();
  });

  it("submits the stock research shortcut with the stock research domain filter", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildDexterResearchResult("stock", "Stock research ready.")),
    );

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "stock-analysis",
          current_filters: { as_of_date: "2026-05-10" },
          selected_rows: [{ stock_code: "000001.SZ" }],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Stock Research/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "Review landed stock research context",
      filters: { research_domain: "stock" },
      page_context: {
        page_id: "stock-analysis",
        current_filters: { as_of_date: "2026-05-10" },
        selected_rows: [{ stock_code: "000001.SZ" }],
      },
    });
    expect(await screen.findByText("Stock research ready.")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("Dexter");
  });

  it("submits the macro research shortcut with the macro research domain filter", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildDexterResearchResult("macro", "Macro research ready.")),
    );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: /Macro Research/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "Review landed macro research context",
      filters: { research_domain: "macro" },
    });
    expect(await screen.findByText("Macro research ready.")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("Dexter");
  });

  it("executes Risk Memo through the local agent query workflow mode", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildWorkflowExecutionResult()));

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "risk-dashboard",
          current_filters: { as_of_date: "2026-04-12" },
          selected_rows: [{ portfolio_id: "core" }],
          context_note: "risk page",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "/risk-memo",
      basis: "formal",
      filters: {},
      position_scope: "all",
      currency_basis: "CNY",
      context: {
        user_id: "web-user",
        workflow_mode: "execute",
      },
      page_context: {
        page_id: "risk-dashboard",
        current_filters: { as_of_date: "2026-04-12" },
        selected_rows: [{ portfolio_id: "core" }],
        context_note: "risk page",
      },
    });
    expect(await screen.findByText("Workflow Execution Steps")).toBeInTheDocument();
    expect(screen.getByText("Mapped Intent Results")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Workflow 执行完成");
    expect(screen.getByRole("status")).not.toHaveTextContent("Hermes 托管任务完成");
    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("/risk-memo");
  });

  it("shows workflow-local pending copy before the Risk Memo workflow request resolves", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Workflow 执行进行中");
    expect(status).toHaveTextContent("准备本地 workflow");
    expect(status).toHaveTextContent("本地 workflow 正在准备，本页会直接显示结果。");
    expect(status).not.toHaveTextContent("正在交给托管运行时");
  });

  it("falls back to local agent query when managed Hermes runs return the provider-gated 400", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          {
            detail: "Agent runs require MOSS_AGENT_PROVIDER=hermes.",
          },
          400,
        ),
      )
      .mockResolvedValueOnce(
        buildJsonResponse(buildLocalOrdinaryTextResult("local ordinary fallback answer")),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ordinary question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("local ordinary fallback answer")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（400）")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/agent/runs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("本地查询完成");
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("local");
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("sync");
  });

  it("falls back to local agent query when managed runs return the generic provider gate", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          {
            detail: "Agent runs require MOSS_AGENT_PROVIDER=hermes or dexter.",
          },
          400,
        ),
      )
      .mockResolvedValueOnce(
        buildJsonResponse(buildLocalOrdinaryTextResult("generic provider gate fallback answer")),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ordinary question");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("generic provider gate fallback answer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
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
    await user.click(screen.getByRole("button", { name: "重试这一轮" }));

    expect(await screen.findByText("retry recovered managed answer")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（500）")).not.toBeInTheDocument();
    expect(screen.getAllByText("ordinary retry question")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    expect(JSON.parse(String(runPostCalls[1]?.[1]?.body))).toMatchObject({
      question: "ordinary retry question",
    });
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    await user.type(screen.getByLabelText("agent-question-input"), "follow-up needs retry");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重试这一轮" }));
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

  it("sends ordinary text directly through local query after Risk Memo workflow completes", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildWorkflowExecutionResult()))
      .mockResolvedValueOnce(
        buildJsonResponse(buildLocalOrdinaryTextResult("post workflow ordinary answer")),
      );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));
    expect(await screen.findByText("Workflow Execution Steps")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "post workflow follow-up");
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
      "/api/agent/query",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/agent/runs")).toBe(false);
  });

  it("pins the current repo and shows pinned/recent sections separately", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    await user.clear(screen.getByLabelText("repo-path-input"));
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\PINNED-MOSS");
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.getByText("最近仓库")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\PINNED-MOSS" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PINNED-MOSS",
    ]);
  });

  it("unpins a pinned repo without removing recent repos", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1"]),
    );
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\MOSS-SYSTEM-V1" }));

    expect(screen.queryByRole("button", { name: "取消固定 F:\\MOSS-SYSTEM-V1" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\MOSS-SYSTEM-V1" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([]);
  });

  it("renders pinned repos even without recent repos and supports pinned ordering", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify(["F:\\ALPHA", "F:\\BETA", "F:\\GAMMA"]),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.queryByText("最近仓库")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "上移固定仓库 F:\\GAMMA" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\ALPHA",
      "F:\\GAMMA",
      "F:\\BETA",
    ]);
  });

  it("pins directly from recent repos, de-duplicates sections, and caps pinned repos", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      PINNED_REPO_PATHS_KEY,
      JSON.stringify([
        "F:\\PINNED-1",
        "F:\\PINNED-2",
        "F:\\PINNED-3",
        "F:\\PINNED-4",
        "F:\\PINNED-5",
      ]),
    );
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\PIN-ME", "F:\\RECENT-2"]),
    );

    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PIN-ME",
      "F:\\PINNED-1",
      "F:\\PINNED-2",
      "F:\\PINNED-3",
      "F:\\PINNED-4",
    ]);
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toHaveLength(
      MAX_PINNED_REPO_PATHS,
    );
    expect(screen.queryByRole("button", { name: "固定仓库 F:\\PIN-ME" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" }));

    expect(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" })).toBeInTheDocument();
  });

  it("does not auto-load GitNexus processes when repo_path changes", async () => {
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes_auto",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByLabelText("repo-path-input"), {
      target: { value: "F:\\MOSS-SYSTEM-V1" },
    });

    await new Promise((resolve) => setTimeout(resolve, 450));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("includes page_context when provided by the mounting page", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(fetchMock, {
        answer: "已使用页面上下文。",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_page_context",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      });

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "risk-dashboard",
          current_filters: { as_of_date: "2026-04-12", portfolio: "core" },
          selected_rows: [{ bond_code: "240001.IB" }],
          context_note: "selected from risk table",
        }}
      />,
    );

    expect(screen.getByText("页面上下文")).toBeInTheDocument();
    expect(screen.getByText(/risk-dashboard/)).toBeInTheDocument();
    expect(screen.getByText(/selected from risk table/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER), "解释当前选择");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      page_context: {
        page_id: "risk-dashboard",
        current_filters: { as_of_date: "2026-04-12", portfolio: "core" },
        selected_rows: [{ bond_code: "240001.IB" }],
        context_note: "selected from risk table",
      },
    });
  });

  it("loads process selector options from GitNexus processes response", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
            ],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 2,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    await waitFor(() => {
      const select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => option.value)).toEqual([
        "",
        "CheckoutFlow",
        "AuditFlow",
      ]);
    });
  });

  it("submits selected process_name when viewing a chosen process", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      .mockResolvedValueOnce(
        buildJsonResponse({
          answer: "GitNexus process ready.",
          cards: [
            {
              title: "GitNexus Process Trace",
              type: "table",
              data: [{ step: 1, symbol: "start_checkout", file: "backend/app/api.py" }],
              spec: { columns: ["step", "symbol", "file"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/process/CheckoutFlow"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_process",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "CheckoutFlow" })).toBeInTheDocument());

    const processSelect = screen.getByLabelText("process-name-select");
    await user.selectOptions(processSelect, "CheckoutFlow");
    await waitFor(() => expect(processSelect).toHaveValue("CheckoutFlow"));
    await user.click(screen.getByRole("button", { name: "查看所选流程" }));

    await waitFor(() => {
      const expectedBody = JSON.stringify({
        question: "请给我看 GitNexus process/CheckoutFlow",
        basis: "formal",
        filters: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
        position_scope: "all",
        currency_basis: "CNY",
        context: {
          user_id: "web-user",
        },
      });
      const matched = fetchMock.mock.calls.some(
        (call) =>
          call[0] === "/api/agent/query" &&
          typeof call[1] === "object" &&
          call[1] !== null &&
          "body" in call[1] &&
          (call[1] as { body?: string }).body === expectedBody,
      );
      expect(matched).toBe(true);
    });
  });

  it("shows local-sync pending copy before the selected GitNexus process request resolves", async () => {
    const user = userEvent.setup();
    let resolveProcesses!: (value: Response) => void;
    const processesResponse = new Promise<Response>((resolve) => {
      resolveProcesses = resolve;
    });
    fetchMock
      .mockReturnValueOnce(processesResponse)
      .mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: /读取流程/ }));

    await act(async () => {
      resolveProcesses(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      );
      await Promise.resolve();
    });

    await waitFor(() => expect(screen.getByLabelText("process-name-select")).toHaveValue("CheckoutFlow"));
    await user.click(screen.getByRole("button", { name: /查看所选流程/ }));

    await screen.findByText("本地同步查询正在准备，本页会直接显示结果。");
    const status = screen.getAllByRole("status").at(-1);
    expect(status).toBeDefined();
    expect(status).toHaveTextContent("本地查询进行中");
    expect(status).toHaveTextContent("准备本地查询");
    expect(status).toHaveTextContent("本地同步查询正在准备，本页会直接显示结果。");
    expect(status).not.toHaveTextContent("正在交给托管运行时");
  });

  it("filters process options by keyword search", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus processes ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
              { name: "BalanceFlow", type: "cross_community", steps: 5 },
            ],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 3,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_processes_filter",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "AuditFlow" })).toBeInTheDocument());

    await user.type(screen.getByLabelText("process-search-input"), "Audit");

    const select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "AuditFlow"]);
  });



  it("ignores a stale query response after a newer manual process load wins", async () => {
    vi.useFakeTimers();
    let resolveQueryResponse!: (value: Response) => void;
    const queryResponse = new Promise<Response>((resolve) => {
      resolveQueryResponse = resolve;
    });
    let resolveManualLoadResponse!: (value: Response) => void;
    const manualLoadResponse = new Promise<Response>((resolve) => {
      resolveManualLoadResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(queryResponse).mockReturnValueOnce(manualLoadResponse);

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByLabelText("repo-path-input"), {
      target: { value: "F:\\MOSS-SYSTEM-V1" },
    });
    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "GitNexus processes" },
    });
    const submitButton = document.querySelector('button[type="submit"]');
    if (!(submitButton instanceof HTMLButtonElement)) {
      throw new Error("query submit button not found");
    }
    fireEvent.click(submitButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const manualProcessButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("读取"));
    if (!(manualProcessButton instanceof HTMLButtonElement)) {
      throw new Error("manual process button not found");
    }
    fireEvent.click(manualProcessButton);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveManualLoadResponse(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "NewestManualFlow", type: "cross_community", steps: 5 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes_manual_current",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      await Promise.resolve()
    });

    let select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(select).toHaveValue("NewestManualFlow");
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "NewestManualFlow"]);

    await act(async () => {
      resolveQueryResponse(
        buildJsonResponse({
          answer: "GitNexus processes ready.",
          cards: [
            {
              title: "GitNexus Processes Table",
              type: "table",
              data: [{ name: "StaleQueryFlow", type: "cross_community", steps: 2 }],
              spec: { columns: ["name", "type", "steps"] },
            },
          ],
          evidence: {
            tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/processes"],
            filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            evidence_rows: 1,
            quality_flag: "ok",
          },
          result_meta: {
            trace_id: "tr_gitnexus_processes_query_old",
            basis: "analytical",
            generated_at: "2026-04-12T09:00:00Z",
          },
          next_drill: [],
        }),
      )
      await Promise.resolve()
    });

    select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
    expect(select).toHaveValue("NewestManualFlow");
    expect(Array.from(select.options).map((option) => option.value)).toEqual(["", "NewestManualFlow"]);
  });

  it("submits explicit repo_path in filters when provided", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus ok",
        cards: [],
        evidence: {
          tables_used: [".gitnexus/meta.json"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.type(
      screen.getByPlaceholderText(AGENT_PLACEHOLDER),
      "请给我看 GitNexus context",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            question: "请给我看 GitNexus context",
            basis: "formal",
            filters: { repo_path: "F:\\MOSS-SYSTEM-V1" },
            position_scope: "all",
            currency_basis: "CNY",
            context: {
              user_id: "web-user",
            },
          }),
        }),
      );
    });
  });

  it("clicking GitNexus quick example fills the query box", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue("请给我看 GitNexus processes");
  });

  it("loads remembered repo_path from localStorage", () => {
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("repo-path-input")).toHaveValue("F:\\MOSS-SYSTEM-V1");
    expect(screen.getByRole("button", { name: "F:\\MOSS-SYSTEM-V1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\NEWMOSS" })).toBeInTheDocument();
  });

  it("persists recent repo_path after query", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus ok",
        cards: [],
        evidence: {
          tables_used: [".gitnexus/meta.json"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus context");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem(RECENT_REPO_PATHS_KEY) ?? "[]")).toEqual([
        "F:\\MOSS-SYSTEM-V1",
      ]);
    });
  });

  it("renders structured table cards instead of flattening them into metrics", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus resources ready.",
        cards: [
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [
              { name: "CheckoutFlow", type: "cross_community", steps: 6 },
              { name: "AuditFlow", type: "intra_community", steps: 3 },
            ],
          },
          {
            title: "GitNexus Context",
            type: "resource",
            value: "gitnexus://repo/MOSS-SYSTEM-V1/context",
            data: [{ label: "project", value: "MOSS-SYSTEM-V1" }],
          },
          {
            title: "GitNexus Tools",
            type: "table",
            data: [{ tool: "query", description: "Process-grouped code intelligence" }],
            spec: { columns: ["tool", "description"] },
          },
          {
            title: "GitNexus Process Trace",
            type: "table",
            data: [
              {
                step: 1,
                symbol: "start_checkout",
                file: "backend/app/api.py",
                module_group: "api",
                edge_label: "api -> services",
              },
              {
                step: 2,
                symbol: "calculate_total",
                file: "backend/app/services/order.py",
                module_group: "services",
                edge_label: "services -> repositories",
              },
              {
                step: 3,
                symbol: "save_order",
                file: "backend/app/repositories/order_repo.py",
                module_group: "repositories",
                edge_label: "",
              },
            ],
            spec: { columns: ["step", "symbol", "file", "module_group", "edge_label"] },
          },
        ],
        evidence: {
          tables_used: [".gitnexus/meta.json"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 2,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_cards",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus context");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("上下文概览")).toBeInTheDocument();
    expect(screen.getByText("执行流程")).toBeInTheDocument();
    expect(screen.getByText("流程图")).toBeInTheDocument();
    expect(screen.getAllByText("CheckoutFlow").length).toBeGreaterThan(0);
    expect(
      screen.getByText((content) => content.includes("cross_community") && content.includes("步骤 6")),
    ).toBeInTheDocument();
    expect(screen.getByText(/api -> services/)).toBeInTheDocument();
    expect(screen.getByText(/services -> repositories/)).toBeInTheDocument();
    expect(screen.getAllByText("api").length).toBeGreaterThan(0);
    expect(screen.getAllByText("services").length).toBeGreaterThan(0);
    expect(screen.getAllByText("repositories").length).toBeGreaterThan(0);
    expect(screen.getByText("gitnexus://repo/MOSS-SYSTEM-V1/context")).toBeInTheDocument();
    expect(screen.getByText("Process-grouped code intelligence")).toBeInTheDocument();
    expect(screen.getByText("start_checkout")).toBeInTheDocument();
    expect(screen.getByText("calculate_total")).toBeInTheDocument();
    expect(screen.getByText("save_order")).toBeInTheDocument();
    expect(screen.getByText("步骤 1")).toBeInTheDocument();
    expect(screen.getByText("步骤 2")).toBeInTheDocument();
    expect(screen.getByText("步骤 3")).toBeInTheDocument();
  });

  it("renders process graph using backend-provided module_group and edge_label", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus process ready.",
        cards: [
          {
            title: "GitNexus Process Trace",
            type: "table",
            data: [
              {
                step: 1,
                symbol: "start_checkout",
                file: "backend/app/api.py",
                module_group: "governance",
                edge_label: "governance -> orchestration",
              },
              {
                step: 2,
                symbol: "calculate_total",
                file: "backend/app/services/order.py",
                module_group: "core",
                edge_label: "core -> persistence",
              },
              {
                step: 3,
                symbol: "save_order",
                file: "backend/app/repositories/order_repo.py",
                module_group: "repositories",
                edge_label: "",
              },
            ],
            spec: { columns: ["step", "symbol", "file", "module_group", "edge_label"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/process/CheckoutFlow"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1", process_name: "CheckoutFlow" },
          evidence_rows: 3,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_process_graph",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus process");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("流程图")).toBeInTheDocument();
    expect(screen.getByText(/governance -> orchestration/)).toBeInTheDocument();
    expect(screen.getByText(/core -> persistence/)).toBeInTheDocument();
    expect(screen.getAllByText("governance").length).toBeGreaterThan(0);
    expect(screen.getAllByText("core").length).toBeGreaterThan(0);
    expect(screen.queryByText(/api -> services/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^api$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^services$/)).not.toBeInTheDocument();
  });

  it("renders GitNexus summary metrics inside the specialized view instead of generic card mixing", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "GitNexus status ready.",
        cards: [
          { title: "Repo", type: "metric", value: "F:\\MOSS-SYSTEM-V1" },
          { title: "Indexed At", type: "metric", value: "2026-04-12T09:00:00Z" },
          { title: "Nodes", type: "metric", value: "8462" },
          { title: "Edges", type: "metric", value: "23878" },
          {
            title: "GitNexus Context",
            type: "resource",
            value: "gitnexus://repo/MOSS-SYSTEM-V1/context",
            data: [{ label: "project", value: "MOSS-SYSTEM-V1" }],
          },
          {
            title: "GitNexus Processes Table",
            type: "table",
            data: [{ name: "CheckoutFlow", type: "cross_community", steps: 6 }],
            spec: { columns: ["name", "type", "steps"] },
          },
        ],
        evidence: {
          tables_used: ["gitnexus://repo/MOSS-SYSTEM-V1/context"],
          filters_applied: { repo_path: "F:\\MOSS-SYSTEM-V1" },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_gitnexus_specialized_summary",
          result_kind: "agent.gitnexus_status",
          basis: "analytical",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus status");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("索引摘要")).toBeInTheDocument();
    expect(screen.getByText("Repo")).toBeInTheDocument();
    expect(screen.getByText("F:\\MOSS-SYSTEM-V1")).toBeInTheDocument();
    expect(screen.getByText("Nodes")).toBeInTheDocument();
    expect(screen.getByText("8462")).toBeInTheDocument();
    expect(screen.getByText("Edges")).toBeInTheDocument();
    expect(screen.getByText("23878")).toBeInTheDocument();
    expect(screen.getByText("执行流程")).toBeInTheDocument();
    expect(screen.getByText("上下文概览")).toBeInTheDocument();
  });

  it("shows validation error when submitting with empty input", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      screen.getByText("请输入查询问题。"),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows disabled banner when backend returns 503 with enabled:false", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          enabled: false,
          phase: "phase1",
          detail: "agent is not enabled",
        },
        503,
      ),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "test",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText(
        "智能体当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。",
      ),
    ).toBeInTheDocument();
  });

  it("shows request error on non-OK response", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("智能体查询失败（500）"),
    ).toBeInTheDocument();
  });

  it("shows request error when fetch throws", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("network down")).toBeInTheDocument();
  });

  it("explains browser fetch failures without showing raw network text", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText(
        "无法连接 Agent 后端。请确认 7888 后端、5888 前端代理和 Hermes 桥接服务正在运行。",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Failed to fetch")).not.toBeInTheDocument();
  });

  it("shows format error when response is 200 but body is not AgentQueryResult", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({ answer: "only answer" }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "q",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("智能体返回结果格式无效。"),
    ).toBeInTheDocument();
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ping");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("Hermes 托管任务完成。")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("agent_run:test");
    expect(screen.getByRole("status")).toHaveTextContent("已完成");
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("gpt-5.5");
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const conversation = await screen.findByLabelText("agent-conversation");
    expect(conversation).toHaveTextContent("帮我判断今天的主要风险");
    expect(conversation).toHaveTextContent("这是更像对话的一次回答。");
    expect(conversation).toHaveTextContent("已完成");
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
    expect(document.activeElement).toBe(screen.getByLabelText("agent-question-input"));
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第一轮回答：主要风险来自久期。")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "那这说明什么？");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("第二轮回答：继续解释上一轮结论。")).toBeInTheDocument();

    const runPostCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs");
    expect(runPostCalls).toHaveLength(2);
    const [, secondOptions] = runPostCalls[1] ?? [];
    expect(JSON.parse(String(secondOptions?.body))).toMatchObject({
      question: "那这说明什么？",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "帮我判断今天的主要风险",
              answer: "第一轮回答：主要风险来自久期。",
              run_id: "agent_run:first",
              trace_id: "tr_first_turn",
            },
          ],
        },
      },
    });
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

    await user.type(screen.getByLabelText("agent-question-input"), "follow-up after refresh");
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
    expect(screen.queryByLabelText("agent-conversation")).not.toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: "重试这一轮" }));
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

  it("shows a local acknowledgement immediately while the managed runtime accepts the run", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    fetchMock.mockReturnValue(new Promise(() => undefined));

    try {
      render(<AgentWorkbenchPage />);

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "先给我一个响应");
      await user.click(screen.getByRole("button", { name: "发送" }));

      const conversation = await screen.findByLabelText("agent-conversation");
      expect(conversation).toHaveTextContent("先给我一个响应");
      expect(conversation).toHaveTextContent("已收到问题");
      expect(conversation).toHaveTextContent("正在交给托管运行时");
      expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
      expect(scrollIntoView).toHaveBeenCalled();
    } finally {
      HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    }
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

  it("shows elapsed managed-runtime wait status while the agent request is still running", async () => {
    vi.useFakeTimers();
    fetchMock.mockReturnValue(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "ping" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("status")).toHaveTextContent("已收到问题");
    expect(screen.getByRole("status")).toHaveTextContent("正在交给托管运行时");
    expect(screen.getByRole("status")).toHaveTextContent("已等待 0 秒");

    act(() => {
      vi.advanceTimersByTime(12_000);
    });

    expect(screen.getByRole("status")).toHaveTextContent("已等待 12 秒");
  });

  it("renders answer, cards, evidence, next_drill, and result_meta on success", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "组合久期风险主要集中在 3Y-5Y。",
        cards: [
          { title: "组合久期", value: "4.27", type: "duration" },
          { title: "DV01", value: "128.5万", type: "risk" },
        ],
        evidence: {
          tables_used: ["fact_risk_tensor", "dim_portfolio"],
          filters_applied: { currency_basis: "CNY" },
          evidence_rows: 42,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_1",
          basis: "formal",
          generated_at: "2026-04-12T09:00:00Z",
        },
        next_drill: [
          { dimension: "portfolio", label: "按组合下钻" },
          { dimension: "tenor_bucket", label: "按期限桶下钻" },
        ],
        suggested_actions: [
          {
            type: "inspect_drill",
            label: "继续下钻期限桶",
            payload: {
              dimension: "tenor_bucket",
              page_context: {
                page_id: "risk-dashboard",
              },
            },
            requires_confirmation: true,
          },
          {
            type: "inspect_lineage",
            label: "查看血缘",
            payload: {
              trace_id: "tr_1",
              tables_used: ["fact_risk_tensor"],
            },
            requires_confirmation: true,
          },
        ],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "久期",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("组合久期风险主要集中在 3Y-5Y。"),
    ).toBeInTheDocument();
    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.27")).toBeInTheDocument();
    expect(screen.getAllByText("久期").length).toBeGreaterThan(0);
    expect(screen.getByText("证据链")).toBeInTheDocument();
    expect(
      screen.getByText(/表：fact_risk_tensor, dim_portfolio/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/筛选：\{"currency_basis":"CNY"\}/),
    ).toBeInTheDocument();
    expect(screen.getByText(/行数：42/)).toBeInTheDocument();
    expect(screen.getByText(/质量：ok/)).toBeInTheDocument();
    expect(screen.getByText("按组合下钻")).toBeInTheDocument();
    expect(screen.getByText("按期限桶下钻")).toBeInTheDocument();
    expect(screen.getByText("建议动作")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续下钻期限桶" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看血缘" })).toBeInTheDocument();
    expect(screen.getAllByText("需确认后执行")).toHaveLength(2);
    expect(screen.getByText(/inspect_drill/)).toBeInTheDocument();
    expect(screen.getByText(/inspect_lineage/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "继续下钻期限桶" }));
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue(
      "请基于当前 evidence 继续下钻：继续下钻期限桶",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("动作载荷 / 血缘信息")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看血缘" }));
    expect(screen.getByText("动作载荷 / 血缘信息")).toBeInTheDocument();
    expect(screen.getAllByText(/fact_risk_tensor/).length).toBeGreaterThanOrEqual(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(screen.getByText("结果元信息")).toBeInTheDocument();
    expect(screen.getByText(/追踪编号: tr_1/)).toBeInTheDocument();
    expect(screen.getByText(/口径: 正式口径/)).toBeInTheDocument();
    expect(screen.getByText(/生成时间: 2026-04-12T09:00:00Z/)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("accepts Hermes cards with nullable data and spec fields", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "pong",
        cards: [
          { title: "Hermes Agent", value: "pong", type: "text", data: null, spec: null },
          { title: "Provider", value: "hermes", type: "metric", data: null, spec: null },
        ],
        evidence: {
          tables_used: ["hermes_cli"],
          filters_applied: { provider: "hermes", model: "default" },
          sql_executed: [],
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_agent_hermes",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "在吗");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await screen.findByText("Hermes Agent");
    expect(screen.getAllByText("pong").length).toBeGreaterThan(0);
    expect(screen.getByText("Hermes Agent")).toBeInTheDocument();
    expect(screen.getByText("Provider")).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "结果类型: agent.hermes")).toBeInTheDocument();
    expect(screen.queryByText("智能体返回结果格式无效。")).not.toBeInTheDocument();
  });

  it("surfaces Hermes runtime status from evidence filters", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "pong",
        cards: [
          { title: "Hermes Agent", value: "pong", type: "text", data: null, spec: null },
        ],
        evidence: {
          tables_used: ["hermes_cli"],
          filters_applied: {
            provider: "hermes",
            model: "gpt-5.5",
            toolsets: "file",
            transport: "bridge",
          },
          sql_executed: [],
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_agent_hermes",
          basis: "formal",
          result_kind: "agent.hermes",
        },
        next_drill: [],
        suggested_actions: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ping{Enter}");

    const runtimeStatus = await screen.findByLabelText("agent-runtime-status");
    expect(runtimeStatus).toHaveTextContent("Hermes");
    expect(runtimeStatus).toHaveTextContent("bridge");
    expect(runtimeStatus).toHaveTextContent("gpt-5.5");
    expect(runtimeStatus).toHaveTextContent("file");
  });

  it("shows Dexter nicely when the managed run and evidence provider are dexter", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(
      fetchMock,
      {
        answer: "Dexter managed run complete.",
        cards: [],
        evidence: {
          tables_used: ["dexter_cli"],
          filters_applied: {
            provider: "dexter",
            model: "gpt-5.5",
            toolsets: "file",
            transport: "bridge",
          },
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: {
          trace_id: "tr_agent_dexter",
          basis: "formal",
          result_kind: "agent.dexter",
        },
        next_drill: [],
        suggested_actions: [],
      },
      "agent_run:dexter",
      "dexter",
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "ping");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("Dexter managed run complete.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Dexter 托管任务完成");
    const runtimeStatus = screen.getByLabelText("agent-runtime-status");
    expect(runtimeStatus).toHaveTextContent("Dexter");
    expect(runtimeStatus).toHaveTextContent("bridge");
    expect(runtimeStatus).toHaveTextContent("gpt-5.5");
    expect(runtimeStatus).toHaveTextContent("file");
  });

  it("shows empty-renderable fallback when payload is valid but nothing to display", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        answer: "   ",
        cards: [],
        evidence: {
          tables_used: [],
          filters_applied: {},
          evidence_rows: 0,
          quality_flag: "",
        },
        result_meta: { trace_id: "tr_empty" },
        next_drill: [],
      }),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "x",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("本次查询未返回可展示结果。请调整问题后重试。"),
    ).toBeInTheDocument();
    expect(screen.getByText(/追踪编号: tr_empty/)).toBeInTheDocument();
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

    const input = screen.getByLabelText("agent-question-input");
    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");
    expect(input).toHaveValue("第一行\n第二行");
    expect(fetchMock).not.toHaveBeenCalled();

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "第一行\n第二行",
    });
  });
});
