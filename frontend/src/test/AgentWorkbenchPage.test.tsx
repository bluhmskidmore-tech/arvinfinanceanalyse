import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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
const AGENT_COMPOSER_DRAFT_KEY = "moss.agent.composerDraft.v1";
const AGENT_QUEUED_QUERIES_KEY = "moss.agent.queuedQueries.v1";
const MAX_PINNED_REPO_PATHS = 5;

function openGitNexusTools() {
  const summary = screen.getByText("GitNexus 工具");
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

function openProcessTools() {
  const summary = screen.getByText(/流程筛选与查看/);
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

function openShortcutDrawer() {
  const summary = screen.getByText("快捷入口");
  const details = summary.closest("details");
  if (!details?.hasAttribute("open")) {
    fireEvent.click(summary);
  }
  return details;
}

function mockNarrowAgentViewport() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("max-width: 720px"),
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    })),
  );
}

type ScrollIntoViewArg = boolean | ScrollIntoViewOptions;

function mockScrollIntoView(implementation: (this: HTMLElement, options?: ScrollIntoViewArg) => void) {
  const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
  if (!originalDescriptor || typeof originalDescriptor.value !== "function") {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: () => undefined,
    });
  }

  const spy = vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(implementation);
  return {
    restore() {
      spy.mockRestore();
      if (originalDescriptor) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalDescriptor);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
      }
    },
  };
}

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

function getQueuedFollowUpStatus() {
  return screen.getByRole("status", { name: "待发送的下一句" });
}

function queryQueuedFollowUpStatus() {
  return screen.queryByRole("status", { name: "待发送的下一句" });
}

function getAgentTurnStatus() {
  const status = screen.getAllByRole("status", { name: "agent-turn-status" }).at(-1);
  if (!status) {
    throw new Error("Expected at least one agent turn status");
  }
  return status;
}

async function findAgentTurnStatus() {
  const statuses = await screen.findAllByRole("status", { name: "agent-turn-status" });
  const status = statuses.at(-1);
  if (!status) {
    throw new Error("Expected at least one agent turn status");
  }
  return status;
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

function buildLocalAnalysisChatResult() {
  return {
    answer: "本地分析对话已接住这轮问题，但未运行正式指标查询。",
    cards: [
      {
        type: "status",
        title: "本地分析对话",
        value: "未匹配受治理指标 intent，本地 Agent 未运行正式指标查询。",
      },
      {
        type: "context",
        title: "已捕获上下文",
        data: {
          page_id: "dashboard",
          report_date: "2026-03-31",
        },
      },
    ],
    evidence: {
      tables_used: [],
      filters_applied: {
        page_id: "dashboard",
        report_date: "2026-03-31",
      },
      evidence_rows: 0,
      quality_flag: "warning",
    },
    result_meta: {
      trace_id: "tr_agent_analysis_chat",
      basis: "formal",
      result_kind: "agent.analysis_chat",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [
      {
        type: "execute_intent",
        label: "组合概览",
        payload: { intent: "portfolio_overview" },
        requires_confirmation: true,
      },
    ],
  };
}

function buildGovernedPortfolioOverviewResult() {
  return {
    answer: "正式组合概览结果：资产规模和风险摘要已返回。",
    cards: [
      {
        type: "metric",
        title: "Total Market Value",
        value: "1000",
      },
    ],
    evidence: {
      tables_used: ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
      filters_applied: {
        report_date: "2026-03-31",
      },
      evidence_rows: 3,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_agent_portfolio_overview",
      basis: "formal",
      result_kind: "agent.portfolio_overview",
      formal_use_allowed: true,
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
    openGitNexusTools();
    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
  });

  it("keeps shortcut entry panels collapsed until requested", () => {
    render(<AgentWorkbenchPage />);

    const shortcutDrawer = screen.getByText("快捷入口").closest("details");
    const stockResearchButton = screen.getByText("Stock Research").closest("button");
    const portfolioReviewButton = screen.getByText("Portfolio Review").closest("button");
    expect(shortcutDrawer).not.toBeNull();
    expect(shortcutDrawer).not.toHaveAttribute("open");
    expect(stockResearchButton).not.toBeNull();
    expect(portfolioReviewButton).not.toBeNull();
    expect(stockResearchButton).not.toBeVisible();
    expect(portfolioReviewButton).not.toBeVisible();

    openShortcutDrawer();

    expect(shortcutDrawer).toHaveAttribute("open");
    expect(stockResearchButton).toBeVisible();
    expect(portfolioReviewButton).toBeVisible();
  });

  it("renders explicit repo_path input and GitNexus quick examples", () => {
    render(<AgentWorkbenchPage />);

    const advancedDetails = screen.getByText("GitNexus 工具").closest("details");
    expect(advancedDetails).not.toBeNull();
    expect(advancedDetails).not.toHaveAttribute("open");
    openGitNexusTools();
    expect(advancedDetails).toHaveAttribute("open");
    expect(screen.getByLabelText("repo-path-input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "固定当前仓库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "读取流程" })).toBeInTheDocument();
    const processDetails = screen.getByText("流程筛选与查看").closest("details");
    expect(processDetails).not.toBeNull();
    expect(processDetails).not.toHaveAttribute("open");
    const viewProcessButton = screen.getByText("查看所选流程").closest("button");
    expect(viewProcessButton).not.toBeNull();
    expect(screen.getByLabelText("process-search-input")).not.toBeVisible();
    expect(viewProcessButton).not.toBeVisible();
    openProcessTools();
    expect(processDetails).toHaveAttribute("open");
    expect(screen.getByLabelText("process-search-input")).toBeVisible();
    expect(viewProcessButton).toBeVisible();
    expect(screen.getByLabelText("process-name-select")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "解释当前页面的主要结论和风险点" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /组合概览/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_STATUS_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_CONTEXT_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON })).toBeInTheDocument();
  });

  it("keeps technical runtime details collapsed by default", () => {
    render(<AgentWorkbenchPage />);

    const runtimeStatus = screen.getByLabelText("agent-runtime-status");
    expect(runtimeStatus).toHaveTextContent("待提问");
    expect(within(runtimeStatus).getByText("运行详情")).toBeVisible();
    expect(within(runtimeStatus).getByText("Engine")).not.toBeVisible();
  });

  it("announces runtime status changes without expanding technical details", () => {
    render(<AgentWorkbenchPage />);

    const runtimeStatus = screen.getByRole("status", { name: "agent-runtime-status" });
    expect(runtimeStatus).toHaveAttribute("aria-live", "polite");
    expect(runtimeStatus).toHaveAttribute("aria-atomic", "true");
  });

  it("renders four financial workflow shortcut buttons", () => {
    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    expect(screen.getByRole("button", { name: /Portfolio Review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /PnL Review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Risk Memo/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Market Brief/ })).toBeInTheDocument();
  });

  it("focuses the composer after launching a financial workflow", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));

    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
  });

  it("renders stock and macro research shortcut buttons", () => {
    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    expect(screen.getByRole("button", { name: /Stock Research/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Macro Research/ })).toBeInTheDocument();
  });

  it("focuses the composer after launching a research shortcut", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Stock Research/ }));

    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    openShortcutDrawer();
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
    expect(screen.getByText("研究上下文已返回 · 可以继续追问")).toBeInTheDocument();
  });

  it("refocuses the composer when a research shortcut returns after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveResearch!: (value: Response) => void;
    const researchResponse = new Promise<Response>((resolve) => {
      resolveResearch = resolve;
    });
    fetchMock.mockReturnValueOnce(researchResponse);

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Stock Research/ }));
    await waitFor(() =>
      expect(screen.getByLabelText("agent-conversation")).toHaveTextContent(
        "Review landed stock research context",
      ),
    );

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveResearch(buildJsonResponse(buildDexterResearchResult("stock", "Stock research focus returned.")));
      await Promise.resolve();
    });

    expect(await screen.findByText("Stock research focus returned.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
  });

  it("cues research shortcut execution while the request is pending", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Stock Research/ }));

    expect(screen.getByText("正在读取研究上下文 · 可继续输入下一句")).toBeInTheDocument();
  });

  it("cues retry after a research shortcut request fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Stock Research/ }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("研究快捷入口失败 · 可重新点击或手动提问")).toBeInTheDocument();
  });

  it("refocuses the composer when a research shortcut fails after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveResearch!: (value: Response) => void;
    const researchResponse = new Promise<Response>((resolve) => {
      resolveResearch = resolve;
    });
    fetchMock.mockReturnValueOnce(researchResponse);

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Stock Research/ }));
    await waitFor(() =>
      expect(screen.getByLabelText("agent-conversation")).toHaveTextContent(
        "Review landed stock research context",
      ),
    );

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveResearch(buildJsonResponse({}, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
  });

  it("submits the macro research shortcut with the macro research domain filter", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildDexterResearchResult("macro", "Macro research ready.")),
    );

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
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

    openShortcutDrawer();
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
    expect(getAgentTurnStatus()).toHaveTextContent("Workflow 执行完成");
    expect(getAgentTurnStatus()).not.toHaveTextContent("Hermes 托管任务完成");
    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("/risk-memo");
    expect(screen.getByText("Workflow 执行完成 · 可以继续追问")).toBeInTheDocument();
  });

  it("refocuses the composer when a financial workflow returns after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveWorkflow!: (value: Response) => void;
    const workflowResponse = new Promise<Response>((resolve) => {
      resolveWorkflow = resolve;
    });
    fetchMock.mockReturnValueOnce(workflowResponse);

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));
    await waitFor(() => expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("/risk-memo"));

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveWorkflow(buildJsonResponse(buildWorkflowExecutionResult()));
      await Promise.resolve();
    });

    expect(await screen.findByText("Workflow Execution Steps")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
  });

  it("shows workflow-local pending copy before the Risk Memo workflow request resolves", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));

    const status = await findAgentTurnStatus();
    expect(status).toHaveTextContent("Workflow 执行进行中");
    expect(status).toHaveTextContent("准备本地 workflow");
    expect(status).toHaveTextContent("本地 workflow 正在准备，本页会直接显示结果。");
    expect(status).not.toHaveTextContent("正在交给托管运行时");
    expect(screen.getByText("正在执行 Workflow · 可继续输入下一句")).toBeInTheDocument();
  });

  it("cues retry after a financial workflow request fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("Workflow 执行失败 · 可重新点击或手动提问")).toBeInTheDocument();
  });

  it("refocuses the composer when a financial workflow fails after the user checks controls", async () => {
    const user = userEvent.setup();
    let resolveWorkflow!: (value: Response) => void;
    const workflowResponse = new Promise<Response>((resolve) => {
      resolveWorkflow = resolve;
    });
    fetchMock.mockReturnValueOnce(workflowResponse);

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));
    await waitFor(() => expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("/risk-memo"));

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveWorkflow(buildJsonResponse({}, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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
    expect(getAgentTurnStatus()).toHaveTextContent("本地查询完成");
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("local");
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("sync");
  });

  it("renders the local analysis-chat fallback with evidence and suggested actions", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()));

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "dashboard",
          current_filters: { report_date: "2026-03-31" },
          selected_rows: [{ portfolio_id: "core" }],
        }}
      />,
    );

    await user.type(screen.getByLabelText("agent-question-input"), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();
    expect(screen.getByText("本地分析对话")).toBeInTheDocument();
    expect(screen.getByText("已捕获上下文")).toBeInTheDocument();
    expect(screen.getByText("组合概览")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-runtime-status")).toHaveTextContent("local");
    expect(getAgentTurnStatus()).toHaveTextContent("本地查询完成");
    const resultDetails = screen.getByLabelText("assistant-result-details");
    expect(resultDetails).toHaveClass("agent-result-side");
    expect(resultDetails).toHaveTextContent("回答依据");
    expect(resultDetails).toHaveTextContent("运行信息");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/query");
  });

  it("keeps result evidence collapsed behind a compact drawer on narrow screens", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    mockNarrowAgentViewport();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()));

    try {
      render(
        <AgentWorkbenchPage
          pageContext={{
            page_id: "dashboard",
            current_filters: { report_date: "2026-03-31" },
            selected_rows: [{ portfolio_id: "core" }],
          }}
        />,
      );

      await user.type(screen.getByLabelText("agent-question-input"), "帮我判断今天的主要风险");
      await user.click(screen.getByRole("button", { name: "发送" }));

      expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();
      const resultDrawer = screen.getByText("依据与运行信息 · 2 项").closest("details");
      expect(resultDrawer).not.toBeNull();
      if (!resultDrawer) {
        throw new Error("Expected compact result details drawer to exist");
      }
      const resultDetails = screen.getByLabelText("assistant-result-details");
      expect(resultDrawer).not.toHaveAttribute("open");
      expect(resultDetails).not.toBeVisible();

      scrollTargets.length = 0;
      fireEvent.click(screen.getByText("依据与运行信息 · 2 项"));
      expect(resultDrawer).toHaveAttribute("open");
      expect(resultDetails).toBeVisible();
      expect(resultDetails).toHaveTextContent("回答依据");
      expect(resultDetails).toHaveTextContent("运行信息");
      await waitFor(() => {
        expect(
          scrollTargets.some((target) => target.dataset.testid === "agent-conversation-bottom"),
        ).toBe(true);
      });
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, 0);
      });
      expect(
        scrollTargets.filter((target) => target.dataset.testid === "agent-conversation-bottom"),
      ).toHaveLength(1);
    } finally {
      scrollIntoViewSpy.restore();
    }
  });

  it("executes an analysis-chat suggested governed intent in the same conversation", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()))
      .mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(
      <AgentWorkbenchPage
        pageContext={{
          page_id: "dashboard",
          current_filters: { report_date: "2026-03-31" },
          selected_rows: [{ portfolio_id: "core" }],
        }}
      />,
    );

    await user.type(screen.getByLabelText("agent-question-input"), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "组合概览" }));

    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("执行建议动作：组合概览");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/agent/query");
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "组合概览",
      context: {
        user_id: "web-user",
        intent: "portfolio_overview",
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
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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
    await user.click(screen.getByRole("button", { name: "重试这一轮" }));

    expect(await screen.findByText("正在重试这一轮 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("智能体查询失败（500）")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止" })).toBeInTheDocument();
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

    openShortcutDrawer();
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

    openGitNexusTools();
    await user.clear(screen.getByLabelText("repo-path-input"));
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\PINNED-MOSS");
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.getByText("最近仓库")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\PINNED-MOSS" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PINNED-MOSS",
    ]);
    expect(screen.getByText("已固定 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
  });

  it("cues the repo path requirement when pinning an empty GitNexus repo", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.clear(screen.getByLabelText("repo-path-input"));
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("请先输入 GitNexus 仓库路径 · 再固定仓库")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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
    expect(screen.getByText("已取消固定 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    await user.click(screen.getByRole("button", { name: "F:\\BETA" }));
    expect(screen.getByLabelText("repo-path-input")).toHaveValue("F:\\BETA");
    expect(screen.getByText("已切换 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "上移固定仓库 F:\\GAMMA" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\ALPHA",
      "F:\\GAMMA",
      "F:\\BETA",
    ]);
    expect(screen.getByText("已调整固定仓库顺序 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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
    expect(screen.getByText("已固定 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" }));

    expect(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" })).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    openGitNexusTools();
    expect(fetchMock).not.toHaveBeenCalled();
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

    const pageContextSummary = screen.getByText("上下文 · 4 项");
    const pageContextDetails = pageContextSummary.closest("details");
    expect(pageContextDetails).not.toBeNull();
    expect(pageContextDetails).not.toHaveAttribute("open");
    expect(screen.getByText(/risk-dashboard/)).not.toBeVisible();
    expect(screen.getByText(/selected from risk table/)).not.toBeVisible();
    fireEvent.click(pageContextSummary);
    expect(pageContextDetails).toHaveAttribute("open");
    expect(screen.getByText(/risk-dashboard/)).toBeVisible();
    expect(screen.getByText(/selected from risk table/)).toBeVisible();
    expect(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(PAGE_CONTEXT_PLACEHOLDER), "managed page context check");
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

  it("cues the repo path requirement when loading GitNexus processes without a repo", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.clear(screen.getByLabelText("repo-path-input"));
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    expect(screen.getByText("请先输入 GitNexus 仓库路径 · 再读取流程")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
  });

  it("cues the process selection requirement when viewing without a selected GitNexus process", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    openProcessTools();
    await user.click(screen.getByRole("button", { name: "查看所选流程" }));

    expect(screen.getByText("请先从流程列表选择一个流程。")).toBeInTheDocument();
    expect(screen.getByText("请先选择 GitNexus 流程 · 再查看")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cues retry after GitNexus process loading fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("读取 GitNexus 流程失败 · 可修改仓库路径后重试")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
  });

  it("loads process selector options from GitNexus processes response", async () => {
    const user = userEvent.setup();
    let resolveProcessesResponse!: (value: Response) => void;
    const processesResponse = new Promise<Response>((resolve) => {
      resolveProcessesResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(processesResponse);
    const processesPayload = buildJsonResponse({
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
      });

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    screen.getByRole("button", { name: "查看所选流程" }).focus();
    await act(async () => {
      resolveProcessesResponse(processesPayload);
      await Promise.resolve();
    });
    openProcessTools();

    await waitFor(() => {
      const select = screen.getByLabelText("process-name-select") as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => option.value)).toEqual([
        "",
        "CheckoutFlow",
        "AuditFlow",
      ]);
    });
    expect(screen.getByText("已读取 GitNexus 流程 · 可选择流程查看")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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
      );
    let resolveProcessResponse!: (value: Response) => void;
    const processResponse = new Promise<Response>((resolve) => {
      resolveProcessResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(processResponse);
    const processPayload = buildJsonResponse({
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
    });

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
    await waitFor(() => expect(screen.getByRole("option", { name: "CheckoutFlow" })).toBeInTheDocument());

    const processSelect = screen.getByLabelText("process-name-select");
    const viewProcessButton = screen.getByRole("button", { name: "查看所选流程" });
    await waitFor(() => expect(processSelect).toHaveValue("CheckoutFlow"));
    expect(viewProcessButton).not.toBeDisabled();
    await user.click(viewProcessButton);
    screen.getByLabelText("process-search-input").focus();

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
    await act(async () => {
      resolveProcessResponse(processPayload);
      await Promise.resolve();
    });
    expect(screen.getByText("已查看 GitNexus 流程 · 可继续追问")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
  });

  it("cues retry after viewing a selected GitNexus process fails", async () => {
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
      );
    let resolveProcessResponse!: (value: Response) => void;
    const processResponse = new Promise<Response>((resolve) => {
      resolveProcessResponse = resolve;
    });
    fetchMock.mockReturnValueOnce(processResponse);

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
    await waitFor(() => expect(screen.getByLabelText("process-name-select")).toHaveValue("CheckoutFlow"));

    await user.click(screen.getByRole("button", { name: "查看所选流程" }));
    screen.getByLabelText("process-search-input").focus();
    await act(async () => {
      resolveProcessResponse(buildJsonResponse({}, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("查看 GitNexus 流程失败 · 可重新选择流程后重试")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: /读取流程/ }));
    expect(screen.getByText("正在读取 GitNexus 流程 · 可继续输入")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();

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

    openProcessTools();
    await waitFor(() => expect(screen.getByLabelText("process-name-select")).toHaveValue("CheckoutFlow"));
    await user.click(screen.getByRole("button", { name: /查看所选流程/ }));
    expect(screen.getByText("正在查看 GitNexus 流程 · 可继续输入")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();

    await screen.findByText("本地同步查询正在准备，本页会直接显示结果。");
    const status = getAgentTurnStatus();
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

    openGitNexusTools();
    await user.type(screen.getByLabelText("repo-path-input"), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
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

    openGitNexusTools();
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

    openProcessTools();
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

    openGitNexusTools();
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

    openGitNexusTools();
    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue("请给我看 GitNexus processes");
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("keeps compact quick examples available after a conversation starts", async () => {
    const user = userEvent.setup();
    mockManagedRunResult(fetchMock, {
      answer: "对话已经开始，可以继续轻点追问。",
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
        trace_id: "tr_compact_quick_examples",
        basis: "formal",
        result_kind: "agent.hermes",
      },
      next_drill: [],
      suggested_actions: [],
    });

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "compact quick examples first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("对话已经开始，可以继续轻点追问。")).toBeInTheDocument();

    const quickExamples = screen.getByLabelText("常用问题");
    const quickExampleButton = within(quickExamples).getByRole("button", {
      name: "解释当前页面的主要结论和风险点",
    });
    expect(quickExampleButton).toBeVisible();

    await user.click(quickExampleButton);

    const input = screen.getByLabelText("agent-question-input");
    expect(input).toHaveValue("解释当前页面的主要结论和风险点");
    expect(input).toHaveFocus();
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("replaces a queued follow-up when a compact quick example fills the composer", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "quick replacement first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("quick replacement first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "queued draft should be replaced by quick example");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced by quick example");

    const quickExamples = screen.getByLabelText("常用问题");
    await user.click(
      within(quickExamples).getByRole("button", {
        name: "解释当前页面的主要结论和风险点",
      }),
    );

    const input = screen.getByLabelText("agent-question-input");
    expect(input).toHaveValue("解释当前页面的主要结论和风险点");
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(input).toHaveFocus();
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("loads remembered repo_path from localStorage", () => {
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
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

    openGitNexusTools();
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

  it("keeps send disabled until the composer has text", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    const sendButton = screen.getByRole("button", { name: "发送" });
    expect(sendButton).toBeDisabled();
    expect(sendButton).not.toHaveAttribute("style");
    screen.getByLabelText("agent-question-input").focus();
    await user.keyboard("{Enter}");

    expect(sendButton).toBeDisabled();
    expect(sendButton).not.toHaveAttribute("style");
    expect(screen.queryByText("请输入查询问题。")).not.toBeInTheDocument();
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
    const disabledStatus = screen.getByRole("status", { name: "agent-disabled-status" });
    expect(disabledStatus).toHaveClass("agent-callout", "agent-callout--warning");
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
    await user.click(screen.getByRole("button", { name: "编辑这句" }));
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("q");
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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
    expect(getAgentTurnStatus()).toHaveTextContent("agent_run:test");
    expect(getAgentTurnStatus()).toHaveTextContent("已完成");
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

    const progress = await screen.findByLabelText("agent-run-progress");
    expect(progress).toHaveTextContent("已提交");
    expect(progress).toHaveTextContent("排队中");
    expect(progress).toHaveTextContent("分析中");
    expect(progress).toBeVisible();
    const runtimeDetails = screen.getByText("运行细节").closest("details");
    expect(runtimeDetails).not.toBeNull();
    expect(runtimeDetails).not.toHaveAttribute("open");
    await waitFor(() => {
      expect(progress.querySelector('[data-current="true"]')).toHaveTextContent("分析中");
    });
    fireEvent.click(screen.getByText("运行细节"));
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

    const conversation = await screen.findByLabelText("agent-conversation");
    expect(conversation).toHaveTextContent("managed conversation check");
    expect(conversation).toHaveTextContent("这是更像对话的一次回答。");
    expect(conversation).toHaveTextContent("已完成");
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
    expect(document.activeElement).toBe(screen.getByLabelText("agent-question-input"));
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
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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

    await user.click(screen.getByRole("button", { name: "复制回答" }));

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
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    await user.click(screen.getByRole("button", { name: "复制回答" }));
    expect(await screen.findByRole("button", { name: "已复制" })).toBeInTheDocument();

    expect(await screen.findByRole("button", { name: "复制回答" }, { timeout: 2500 })).toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: "复制回答" }));

    expect(writeText).toHaveBeenCalledWith("这段回答暂时复制不了。");
    expect(await screen.findByRole("button", { name: "复制失败" })).toBeInTheDocument();
    expect(screen.getByText("这段回答暂时复制不了。")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    await user.click(screen.getByRole("button", { name: "复制回答" }));

    expect(await screen.findByRole("button", { name: "复制失败" })).toBeInTheDocument();
    const copyStatus = await screen.findByRole("status", { name: "复制状态" });
    expect(copyStatus).toHaveTextContent("复制失败，请手动选择回答文本。");
    expect(copyStatus).toBeVisible();
    expect(copyStatus).toHaveClass("agent-copy-feedback");
    expect(copyStatus.closest(".agent-result-toolbar")).not.toBeNull();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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

    await user.click(screen.getByRole("button", { name: "展开依据" }));

    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
    expect(input).toHaveValue("请基于上一轮回答展开证据依据和关键假设。");
    expect(document.activeElement).toBe(input);
    expect(input).toHaveProperty("selectionStart", input.value.length);
    expect(input).toHaveProperty("selectionEnd", input.value.length);
    expect(screen.getByText("已填入追问 · Enter 发送")).toBeInTheDocument();
    expect(followUpDetails).not.toHaveAttribute("open");
    expect(followUpOptions).not.toBeVisible();
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

      await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "duration risk follow-up check");
      await user.click(screen.getByRole("button", { name: "发送" }));
      expect(await screen.findByText("回答完成，可以继续追问。")).toBeInTheDocument();
      const resultDrawer = screen.getByText("依据与运行信息 · 2 项").closest("details");
      expect(resultDrawer).not.toBeNull();
      if (!resultDrawer) {
        throw new Error("Expected compact result details drawer to exist");
      }
      fireEvent.click(screen.getByText("依据与运行信息 · 2 项"));
      expect(resultDrawer).toHaveAttribute("open");

      await user.click(screen.getByRole("button", { name: "复制回答" }));
      screen.getByRole("button", { name: "已复制" }).focus();
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "已复制" }));
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
      const input = screen.getByLabelText("agent-question-input");
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
      await user.click(screen.getByRole("button", { name: "继续输入" }));

      expect(input).toHaveValue("");
      expect(document.activeElement).toBe(input);
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

    await user.click(screen.getByRole("button", { name: "重新生成" }));
    screen.getByRole("button", { name: "停止" }).focus();
    await act(async () => {
      resolveRegenerateResponse(regeneratePayload);
      await Promise.resolve();
    });

    expect(await screen.findByText("重新生成后的回答。")).toBeInTheDocument();
    expect(screen.queryByText("第一版回答。")).not.toBeInTheDocument();
    expect(screen.getAllByText("regenerate this")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(2);
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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

    await user.click(screen.getByRole("button", { name: "重新生成" }));

    expect(await screen.findByText("正在重新生成 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("第一版待重新生成回答。")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止" })).toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: "编辑问题" }));

    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
    expect(input).toHaveValue("edit original question");
    expect(document.activeElement).toBe(input);
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

    await user.type(screen.getByLabelText("agent-question-input"), "managed second turn");
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
    expect(screen.queryByLabelText("agent-conversation")).not.toBeInTheDocument();
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));

    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("下一句");
    expect(queuedPreview).toHaveTextContent("当前回答完成后发送");
    expect(queuedPreview).toHaveTextContent("queued second turn");
    expect(screen.queryByText("已排队：queued second turn")).not.toBeInTheDocument();
    expect(screen.queryByText("当前回答完成后自动发送。")).not.toBeInTheDocument();
    const composerDock = document.querySelector(".agent-composer-dock");
    expect(composerDock).not.toBeNull();
    expect(composerDock).toContainElement(queuedPreview);
    expect(screen.getByLabelText("agent-conversation")).not.toHaveTextContent("下一句");
    expect(screen.getByLabelText("agent-conversation")).not.toHaveTextContent("queued second turn");
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    expect(screen.getByText("下一句已排队 · 还可以继续输入")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "编辑草稿" }));
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("queued second turn");
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    await user.click(screen.getByRole("button", { name: "取消草稿" }));
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("agent-question-input"), "queued second turn");
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued pending second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(screen.getByText("下一句已排队 · 还可以继续输入")).toBeInTheDocument();

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
    expect(screen.queryByText("下一句已排队 · 还可以继续输入")).not.toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));
    expect(await screen.findByText("Workflow 执行完成 · 可以继续追问")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "local queued first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("local queued first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "local queued second turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));

    await act(async () => {
      resolveFirstRun(buildJsonResponse(buildLocalOrdinaryTextResult("local queued first answer")));
      await Promise.resolve();
    });

    expect(await screen.findByText("local queued second turn")).toBeInTheDocument();
    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveQueuedRun(buildJsonResponse(buildLocalOrdinaryTextResult("local queued second answer")));
      await Promise.resolve();
    });

    expect(await screen.findByText("local queued second answer")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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

    await user.click(screen.getByRole("button", { name: /Risk Memo/ }));
    expect(await screen.findByText("Workflow 执行完成 · 可以继续追问")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "local queued fail first turn");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("local queued fail first turn")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "local queued fail second turn");
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
    await waitFor(() => expect(screen.getByLabelText("agent-question-input")).toHaveFocus());
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

    await user.type(screen.getByLabelText("agent-question-input"), "multi queue second turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("multi queue second turn");

    await user.type(screen.getByLabelText("agent-question-input"), "multi queue third turn");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));
    const queuedPreview = getQueuedFollowUpStatus();
    expect(queuedPreview).toHaveTextContent("multi queue second turn");
    expect(queuedPreview).toHaveTextContent("multi queue third turn");
    expect(queuedPreview).toHaveTextContent("2 句待发送");
    expect(screen.getByText("2 句已排队 · 还可以继续输入")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-conversation")).not.toHaveTextContent("multi queue third turn");
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued draft after remount");
    await user.click(screen.getByTestId("agent-panel-queue-submit"));

    expect(window.localStorage.getItem(AGENT_QUEUED_QUERIES_KEY)).toBe(
      JSON.stringify(["queued draft after remount"]),
    );

    unmount();
    render(<AgentWorkbenchPage />);

    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft after remount");
    expect(screen.getByLabelText("agent-conversation")).not.toHaveTextContent("queued draft after remount");
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
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

    await user.type(screen.getByLabelText("agent-question-input"), "stable action second turn");
    await user.click(within(idleActionSlot).getByTestId("agent-panel-submit"));
    expect(await screen.findByText("stable action second turn")).toBeInTheDocument();

    const runningActionSlot = getDockActionSlot();
    expect(runningActionSlot).toHaveClass("agent-chat-composer__actions--running");
    expect(within(runningActionSlot).getByRole("button", { name: "发送下一句" })).toBeDisabled();
    expect(within(runningActionSlot).getByTestId("agent-panel-submit")).toHaveTextContent("停止");
  });

  it("keeps running composer controls full-width on mobile", () => {
    const cssText = readFileSync(resolve(process.cwd(), "src/styles/global.css"), "utf8");

    expect(cssText).toContain(".agent-chat-composer__actions--running");
    expect(cssText).toContain(".agent-chat-composer__actions--running > .agent-chat-composer__queue");
    expect(cssText).toContain(".agent-chat-composer__actions--running > .agent-chat-composer__send");
    expect(cssText).toContain("grid-template-columns: 1fr");
  });

  it("queues a typed follow-up with Enter while the current answer is still running", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "enter queue first turn");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("enter queue first turn")).toBeInTheDocument();
    expect(screen.getByText("回答中 · Enter 排队下一句 · Shift+Enter 换行")).toBeInTheDocument();

    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
    await user.type(input, "enter queued second turn");
    await user.keyboard("{Enter}");

    expect(getQueuedFollowUpStatus()).toHaveTextContent("enter queued second turn");
    expect(screen.queryByText("已排队：enter queued second turn")).not.toBeInTheDocument();
    expect(screen.queryByText("当前回答完成后自动发送。")).not.toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs")).toHaveLength(1);
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

      const input = screen.getByLabelText("agent-question-input");
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
      expect(scrollTargets.some((target) => target.getAttribute("aria-label") === "agent-question-input")).toBe(true);
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued stop second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued stop second turn");

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued cancel second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued cancel second turn");

    await user.click(screen.getByRole("button", { name: "取消草稿" }));
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued edit second turn");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued edit second turn");

    await user.click(screen.getByRole("button", { name: "编辑草稿" }));

    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued draft should be replaced");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced");

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));
    await user.click(screen.getByRole("button", { name: "编辑问题" }));

    const input = screen.getByLabelText("agent-question-input");
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

    await user.type(screen.getByLabelText("agent-question-input"), "queued draft replaced by direct edit");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft replaced by direct edit");

    await user.click(screen.getByRole("button", { name: "编辑问题" }));

    const input = screen.getByLabelText("agent-question-input");
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

    await user.type(screen.getByLabelText("agent-question-input"), "running follow-up before suggestion");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("running follow-up before suggestion")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "queued draft should be replaced by suggestion");
    await user.click(screen.getByRole("button", { name: "发送下一句" }));
    expect(getQueuedFollowUpStatus()).toHaveTextContent("queued draft should be replaced by suggestion");

    await user.click(screen.getByRole("button", { name: "继续下钻期限桶" }));

    const input = screen.getByLabelText("agent-question-input");
    expect(input).toHaveValue("请基于当前 evidence 继续下钻：继续下钻期限桶");
    expect(queryQueuedFollowUpStatus()).not.toBeInTheDocument();
    expect(input).toHaveFocus();
    expect(screen.getByText("已填入建议追问 · Enter 发送")).toBeInTheDocument();
  });

  it("restores an unsent composer draft after remount", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "draft question before refresh");
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft question before refresh");

    unmount();
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("agent-question-input")).toHaveValue("draft question before refresh");
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
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
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to submit");

    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("draft submitted answer")).toBeInTheDocument();
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();

    await user.type(screen.getByLabelText("agent-question-input"), "draft to discard");
    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to discard");
    await user.click(screen.getByRole("button", { name: "新对话" }));

    expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBeNull();
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
    await waitFor(() => {
      expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    });
  });

  it("clears a typed composer draft without sending", async () => {
    const user = userEvent.setup();
    const scrollTargets: HTMLElement[] = [];
    const scrollIntoViewSpy = mockScrollIntoView(function (this: HTMLElement) {
      scrollTargets.push(this);
    });
    render(<AgentWorkbenchPage />);

    const input = screen.getByLabelText("agent-question-input");
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
      expect(window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY)).toBe("draft to clear");
      scrollTargets.length = 0;

      await user.click(screen.getByRole("button", { name: "清空输入" }));

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
    expect(screen.queryByLabelText("agent-conversation")).not.toBeInTheDocument();

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
    expect(screen.queryByLabelText("agent-conversation")).not.toBeInTheDocument();
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

      const conversation = await screen.findByLabelText("agent-conversation");
      expect(conversation).toHaveTextContent("先给我一个响应");
      expect(conversation).toHaveTextContent("正在思考");
      expect(conversation).toHaveTextContent("我先接住问题，拿到运行状态后继续更新。");
      expect(conversation).toHaveTextContent("已收到问题");
      expect(conversation).toHaveTextContent("正在交给托管运行时");
      expect(screen.getByLabelText("agent-question-input")).toHaveValue("");
      expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
      const bottomScrollIndex = scrollTargets.findIndex(
        (target) => target.dataset.testid === "agent-conversation-bottom",
      );
      expect(bottomScrollIndex).toBeGreaterThanOrEqual(0);
      expect(scrollOptions[bottomScrollIndex]).toMatchObject({ behavior: "smooth", block: "end" });
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

      const conversation = await screen.findByLabelText("agent-conversation");
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
      });
      fireEvent.scroll(conversation);
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

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("stop this pending answer");
    expect(screen.getByText("已恢复到输入框 · 可编辑后重新发送")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "编辑这句" }));
    expect(screen.getByLabelText("agent-question-input")).toHaveValue("stop this pending answer");
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();

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
    await user.type(screen.getByLabelText("agent-question-input"), "draft after stop");

    const composerAction = screen.getByTestId("agent-panel-submit");
    expect(composerAction).toHaveTextContent("停止");
    expect(composerAction).not.toBeDisabled();
    await user.click(composerAction);

    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();
    const input = screen.getByLabelText("agent-question-input");
    expect(input).toHaveValue("draft after stop");
    expect(input).toHaveFocus();
    expect(screen.getByText("已停止回答 · 可继续发送当前输入")).toBeInTheDocument();

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
    const input = screen.getByLabelText("agent-question-input");
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

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));
    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重新发送" }));

    expect(await screen.findByText("正在重新发送已停止回答 · 可继续输入下一句")).toBeInTheDocument();
    expect(screen.queryByText("已停止等待这次回答。")).not.toBeInTheDocument();
    const input = screen.getByLabelText("agent-question-input");
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

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));

    await waitFor(() => {
      const storedTurns = JSON.parse(window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY) ?? "[]");
      expect(storedTurns[0]).toMatchObject({
        question: "stop and refresh this answer",
        stopped: true,
      });
    });

    unmount();
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("stop and refresh this answer");
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

    await user.click(screen.getByRole("button", { name: "停止当前回答" }));

    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
    expect(await screen.findByText("已停止等待这次回答。")).toBeInTheDocument();

    unmount();
    render(<AgentWorkbenchPage />);

    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent("stop after run id exists");
    expect(screen.getByText("已停止等待这次回答。")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
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
    expect(screen.queryByRole("status", { name: "agent-run-restore-status" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/agent/runs/agent_run%3Arestore-polling")).toHaveLength(
      2,
    );
  });

  it("shows a restore status while reconnecting to the latest run after refresh", () => {
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-pending");
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("status", { name: "agent-run-restore-status" })).toHaveTextContent(
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
      .mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("fresh answer while restore was pending")));

    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("status", { name: "agent-run-restore-status" })).toHaveTextContent(
      "agent_run:restore-pending-fresh-question",
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/runs/agent_run%3Arestore-pending-fresh-question",
        expect.objectContaining({ method: "GET" }),
      ),
    );

    await user.type(screen.getByLabelText("agent-question-input"), "fresh question while restore pending");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("fresh answer while restore was pending")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "agent-run-restore-status" })).not.toBeInTheDocument();

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
      .mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("fresh answer after restore failure")));

    render(<AgentWorkbenchPage />);

    const restoreError = await screen.findByRole("status", { name: "agent-run-restore-error" });
    expect(restoreError).toHaveTextContent("agent_run:restore-failed");
    expect(window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)).toBeNull();
    expect(screen.getByLabelText("agent-question-input")).toBeInTheDocument();

    await user.type(screen.getByLabelText("agent-question-input"), "fresh question after restore failure");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("fresh answer after restore failure")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "agent-run-restore-error" })).not.toBeInTheDocument();
  });

  it("clears restore failure status when a quick example fills the composer", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, "agent_run:restore-failed-quick");
    fetchMock.mockResolvedValueOnce(buildJsonResponse({ detail: "missing run" }, 500));

    render(<AgentWorkbenchPage />);

    const restoreError = await screen.findByRole("status", { name: "agent-run-restore-error" });
    expect(restoreError).toHaveTextContent("agent_run:restore-failed-quick");

    openGitNexusTools();
    await user.click(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON }));

    expect(screen.getByLabelText("agent-question-input")).toHaveValue("请给我看 GitNexus processes");
    expect(screen.queryByRole("status", { name: "agent-run-restore-error" })).not.toBeInTheDocument();
  });

  it("shows elapsed managed-runtime wait status while the agent request is still running", async () => {
    vi.useFakeTimers();
    fetchMock.mockReturnValue(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    fireEvent.change(screen.getByPlaceholderText(AGENT_PLACEHOLDER), {
      target: { value: "ping" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const waitStatus = getAgentTurnStatus();
    expect(waitStatus).toHaveTextContent("已收到问题");

    const runtimeDetails = screen.getByText("运行细节").closest("details");
    expect(runtimeDetails).not.toBeNull();
    expect(runtimeDetails).not.toHaveAttribute("open");
    expect(runtimeDetails).toHaveTextContent("正在交给托管运行时");
    expect(runtimeDetails).toHaveTextContent("已等待 0 秒");

    act(() => {
      vi.advanceTimersByTime(12_000);
    });

    expect(runtimeDetails).toHaveTextContent("已等待 12 秒");
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
          source_version: "sv_agent_test",
          rule_version: "rv_agent_test",
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
    const evidencePanel = screen.getByText("回答依据").closest(".agent-side-panel");
    expect(evidencePanel).not.toBeNull();
    expect(evidencePanel).toHaveTextContent("来源");
    expect(evidencePanel).toHaveTextContent("fact_risk_tensor, dim_portfolio");
    expect(evidencePanel).toHaveTextContent("过滤");
    expect(evidencePanel).toHaveTextContent("currency_basis: CNY");
    expect(evidencePanel).toHaveTextContent("证据行数");
    expect(evidencePanel).toHaveTextContent("42 行");
    expect(evidencePanel).toHaveTextContent("质量");
    expect(evidencePanel).toHaveTextContent("正常");
    expect(screen.getByText("查看筛选参数")).toBeInTheDocument();
    const sidePanelDetails = Array.from(document.querySelectorAll<HTMLDetailsElement>(".agent-side-panel__details"));
    expect(sidePanelDetails.length).toBeGreaterThan(0);
    const firstSidePanelDetails = sidePanelDetails[0];
    const firstSidePanelBody = Array.from(firstSidePanelDetails.children).find(
      (child) => child.tagName.toLowerCase() !== "summary",
    );
    expect(firstSidePanelDetails).not.toHaveAttribute("open");
    expect(firstSidePanelBody).toBeDefined();
    if (!firstSidePanelBody) {
      throw new Error("Expected side panel details body to exist");
    }
    expect(firstSidePanelBody).not.toBeVisible();
    const firstSidePanelSummary = firstSidePanelDetails.querySelector("summary");
    expect(firstSidePanelSummary).not.toBeNull();
    if (!firstSidePanelSummary) {
      throw new Error("Expected side panel details summary to exist");
    }
    fireEvent.click(firstSidePanelSummary);
    expect(firstSidePanelDetails).toHaveAttribute("open");
    expect(firstSidePanelBody).toBeVisible();
    expect(screen.getByText("按组合下钻")).toBeInTheDocument();
    expect(screen.getByText("按期限桶下钻")).toBeInTheDocument();
    expect(screen.getByText("接下来可以做")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续下钻期限桶" })).toBeInTheDocument();
    const moreSuggestedActions = screen.getByText("更多建议 · 1 项").closest("details");
    const lineageActionButton = screen.getByText("查看血缘").closest("button");
    expect(moreSuggestedActions).not.toBeNull();
    expect(moreSuggestedActions).not.toHaveAttribute("open");
    expect(lineageActionButton).not.toBeNull();
    expect(lineageActionButton).not.toBeVisible();
    expect(screen.getAllByText("需确认后执行")).toHaveLength(2);
    expect(screen.getAllByText("查看参数")).toHaveLength(2);
    expect(screen.getByText(/inspect_drill/)).toBeInTheDocument();
    expect(screen.getByText(/inspect_lineage/)).not.toBeVisible();

    fireEvent.click(screen.getByText("更多建议 · 1 项"));
    expect(moreSuggestedActions).toHaveAttribute("open");
    expect(lineageActionButton).toBeVisible();
    if (!moreSuggestedActions) {
      throw new Error("Expected secondary suggested actions drawer to exist");
    }
    const lineageActionDetails = within(moreSuggestedActions).getByText("查看参数").closest("details");
    expect(lineageActionDetails).not.toBeNull();
    expect(lineageActionDetails).not.toHaveAttribute("open");
    expect(screen.getByText(/inspect_lineage/)).not.toBeVisible();

    const primaryActionDetails = screen.getByText(/inspect_drill/).closest("details");
    expect(primaryActionDetails).not.toBeNull();
    const primaryActionSummary = primaryActionDetails?.querySelector("summary");
    expect(primaryActionSummary).not.toBeNull();
    if (!primaryActionSummary) {
      throw new Error("Expected primary action details summary to exist");
    }
    fireEvent.click(primaryActionSummary);
    expect(primaryActionDetails).toHaveAttribute("open");
    await user.click(screen.getByRole("button", { name: "继续下钻期限桶" }));
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toHaveValue(
      "请基于当前 evidence 继续下钻：继续下钻期限桶",
    );
    expect(firstSidePanelDetails).not.toHaveAttribute("open");
    expect(firstSidePanelBody).not.toBeVisible();
    expect(primaryActionDetails).not.toHaveAttribute("open");
    expect(screen.getByText(/inspect_drill/)).not.toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("已选择的参数")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看血缘" }));
    expect(screen.getByText("已选择的参数")).toBeInTheDocument();
    expect(screen.getByText("已选择建议动作 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    expect(screen.getAllByText(/fact_risk_tensor/).length).toBeGreaterThanOrEqual(2);
    expect(moreSuggestedActions).not.toHaveAttribute("open");
    expect(lineageActionButton).not.toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const metaPanel = screen.getByText("运行信息").closest(".agent-side-panel");
    expect(metaPanel).not.toBeNull();
    expect(metaPanel).toHaveTextContent("追踪编号");
    expect(metaPanel).toHaveTextContent("tr_1");
    expect(metaPanel).toHaveTextContent("口径");
    expect(metaPanel).toHaveTextContent("正式口径");
    expect(metaPanel).toHaveTextContent("生成时间");
    expect(metaPanel).toHaveTextContent("2026-04-12T09:00:00Z");
    expect(metaPanel).toHaveTextContent("sv_agent_test");
    expect(metaPanel).toHaveTextContent("rv_agent_test");

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
    fireEvent.click(screen.getByText("查看全部运行信息"));
    expect(screen.getByText("agent.hermes")).toBeVisible();
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
    expect(getAgentTurnStatus()).toHaveTextContent("Dexter 托管任务完成");
    const runtimeStatus = screen.getByLabelText("agent-runtime-status");
    expect(runtimeStatus).toHaveTextContent("Dexter");
    expect(runtimeStatus).toHaveTextContent("bridge");
    expect(runtimeStatus).toHaveTextContent("gpt-5.5");
    expect(runtimeStatus).toHaveTextContent("file");
  });

  it("shows empty-renderable fallback when payload is valid but nothing to display", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
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
      )
      .mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("empty fallback regenerated answer")));

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
    expect(screen.getByRole("status", { name: "空结果状态" })).toHaveTextContent(
      "本次查询未返回可展示结果。请调整问题后重试。",
    );
    const emptyResultSummary = screen.getByText("查看依据 · 1 项");
    const emptyResultDetails = emptyResultSummary.closest("details");
    expect(emptyResultDetails).not.toBeNull();
    expect(emptyResultDetails).not.toHaveAttribute("open");
    expect(screen.getByText("tr_empty")).not.toBeVisible();
    fireEvent.click(emptyResultSummary);
    expect(emptyResultDetails).toHaveAttribute("open");
    expect(screen.getByText("tr_empty")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "继续输入" }));
    expect(screen.getByLabelText("agent-question-input")).toHaveFocus();
    expect(screen.getByText("可以调整问题 · Enter 发送")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新生成" }));
    expect(await screen.findByText("empty fallback regenerated answer")).toBeInTheDocument();
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
