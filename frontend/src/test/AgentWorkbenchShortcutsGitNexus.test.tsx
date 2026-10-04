import { act, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_CONVERSATION_LABEL,
  AGENT_FINANCIAL_WORKFLOWS_LABEL,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  AGENT_RESEARCH_SHORTCUTS_LABEL,
  AGENT_RUNTIME_STATUS_LABEL,
  MAX_PINNED_REPO_PATHS,
  PINNED_REPO_PATHS_KEY,
  PROCESS_NAME_LABEL,
  PROCESS_SEARCH_LABEL,
  RECENT_REPO_PATHS_KEY,
  REPO_PATH_LABEL,
  buildDexterResearchResult,
  buildJsonResponse,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  buildResearchRadarResult,
  buildWorkflowExecutionResult,
  findAgentTurnStatus,
  getAgentTurnStatus,
  mockManagedRunResult,
  openGitNexusTools,
  openProcessTools,
  openShortcutDrawer,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 快捷入口与 GitNexus", () => {
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

  it("keeps shortcut cards tucked away until the user opens the drawer", () => {
    render(<AgentWorkbenchPage />);

    const shortcutDrawer = screen.getByText("常用入口").closest("details");
    expect(shortcutDrawer).not.toBeNull();
    expect(shortcutDrawer).not.toHaveAttribute("open");

    openShortcutDrawer();
    const stockResearchButton = screen.getByText("股票研究").closest("button");
    const portfolioReviewButton = screen.getByText("组合复核").closest("button");
    expect(stockResearchButton).not.toBeNull();
    expect(portfolioReviewButton).not.toBeNull();
    expect(stockResearchButton).toBeVisible();
    expect(portfolioReviewButton).toBeVisible();
    expect(screen.getByLabelText(AGENT_RESEARCH_SHORTCUTS_LABEL)).toContainElement(stockResearchButton);
    expect(screen.getByLabelText(AGENT_FINANCIAL_WORKFLOWS_LABEL)).toContainElement(portfolioReviewButton);
  });

  it("renders four financial workflow shortcut buttons", () => {
    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    expect(screen.getByRole("button", { name: /组合复核/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /损益复核/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /风险纪要/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /市场简报/ })).toBeInTheDocument();
  });

  it("focuses the composer after launching a financial workflow", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("renders stock and macro research shortcut buttons", () => {
    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    expect(screen.getByText("数据研究入口")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "已刷新数据复核" })).toBeInTheDocument();
    expect(screen.getByText("先刷新数据")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /股票研究/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /宏观研究/ })).toBeInTheDocument();
  });

  it("focuses the composer after launching a research shortcut", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /股票研究/ }));

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("renders the research radar shortcut in the quick-entry drawer", () => {
    render(<AgentWorkbenchPage />);
    openShortcutDrawer();

    expect(screen.getByRole("button", { name: /研究速读/ })).toBeInTheDocument();
  });

  it("submits the research radar shortcut with explicit local intent context", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildResearchRadarResult()));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /研究速读/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/agent/query",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      question: "研究速读",
      basis: "analytical",
      filters: {},
      context: {
        intent: "research_radar_brief",
        workflow_id: "research_radar_brief",
      },
    });
  });

  it("renders research radar evidence before interpretation with boundary text and next link", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildResearchRadarResult()));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /研究速读/ }));

    const evidenceTitle = await screen.findByText("原始事件证据");
    const interpretation = await screen.findByText("解释：当前事件先看利率与信用线索，再决定是否进入正式风险检查。");
    expect(evidenceTitle.compareDocumentPosition(interpretation) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("跨篇对比")).toBeInTheDocument();
    expect(screen.getByText("候选情景建议")).toBeInTheDocument();
    expect(screen.getByText("human_review_required:")).toBeInTheDocument();
    expect(screen.getAllByText("true").length).toBeGreaterThan(0);
    expect(
      screen.getByText("分析口径 / 非正式指标 / 非投资建议 / 需人工确认后再进入情景测算"),
    ).toBeInTheDocument();
    const newsLink = screen.getByRole("link", { name: "新闻事件" });
    expect(newsLink).toHaveAttribute("href", "/news-events");
    expect(screen.queryByText(/scenario impact/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/PnL estimate/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/DV01 loss/i)).not.toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: /股票研究/ }));

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
    expect(screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL)).toHaveTextContent("Dexter");
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
    await user.click(screen.getByRole("button", { name: /股票研究/ }));
    await waitFor(() =>
      expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent(
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
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("cues research shortcut execution while the request is pending", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /股票研究/ }));

    expect(screen.getByText("正在读取研究上下文 · 可继续输入下一句")).toBeInTheDocument();
  });

  it("cues retry after a research shortcut request fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /股票研究/ }));

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
    await user.click(screen.getByRole("button", { name: /股票研究/ }));
    await waitFor(() =>
      expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent(
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
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("submits the macro research shortcut with the macro research domain filter", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildDexterResearchResult("macro", "Macro research ready.")),
    );

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /宏观研究/ }));

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
    expect(screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL)).toHaveTextContent("Dexter");
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
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));

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
    expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("/risk-memo");
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
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));
    await waitFor(() => expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("/risk-memo"));

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveWorkflow(buildJsonResponse(buildWorkflowExecutionResult()));
      await Promise.resolve();
    });

    expect(await screen.findByText("Workflow Execution Steps")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("shows workflow-local pending copy before the Risk Memo workflow request resolves", async () => {
    const user = userEvent.setup();
    fetchMock.mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));

    const status = await findAgentTurnStatus();
    expect(status).toHaveTextContent("Workflow 执行进行中");
    expect(status).toHaveTextContent("正在准备本地模板");
    expect(status).toHaveTextContent("本地模板正在准备，结果会直接出现在这里。");
    expect(status).not.toHaveTextContent("正在交给托管运行时");
    expect(screen.getByText("正在执行 Workflow · 可继续输入下一句")).toBeInTheDocument();
  });

  it("cues retry after a financial workflow request fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openShortcutDrawer();
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));

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
    await user.click(screen.getByRole("button", { name: /风险纪要/ }));
    await waitFor(() => expect(screen.getByLabelText(AGENT_CONVERSATION_LABEL)).toHaveTextContent("/risk-memo"));

    screen.getByTestId("agent-panel-submit").focus();
    expect(screen.getByTestId("agent-panel-submit")).toHaveFocus();

    await act(async () => {
      resolveWorkflow(buildJsonResponse({}, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
  });

  it("re-enables the load-processes action when a question bumps the process request version", async () => {
    const user = userEvent.setup();
    let resolveProcesses!: (value: Response) => void;
    const processesResponse = new Promise<Response>((resolve) => {
      resolveProcesses = resolve;
    });
    fetchMock
      .mockReturnValueOnce(processesResponse)
      .mockResolvedValueOnce(buildJsonResponse(buildLocalOrdinaryTextResult("local answer while loading processes")));

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    expect(screen.getByRole("button", { name: "读取中..." })).toBeDisabled();

    // 读取流程进行中提问（本地 open chat 直答路径）：会 bump 进程请求版本号。
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "hi");
    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("local answer while loading processes")).toBeInTheDocument();

    await act(async () => {
      resolveProcesses(buildJsonResponse(buildLocalOrdinaryTextResult("stale processes payload")));
      await Promise.resolve();
    });

    // 过期的进程结果被丢弃，但读取按钮必须复位，不能永久卡在"读取中..."。
    openGitNexusTools();
    const loadProcessesButton = await screen.findByRole("button", { name: "读取流程" });
    expect(loadProcessesButton).toBeEnabled();
  });

  it("pins the current repo and shows pinned/recent sections separately", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.clear(screen.getByLabelText(REPO_PATH_LABEL));
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\PINNED-MOSS");
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("固定仓库")).toBeInTheDocument();
    expect(screen.getByText("最近仓库")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\PINNED-MOSS" })).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\PINNED-MOSS",
    ]);
    expect(screen.getByText("已固定 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("cues the repo path requirement when pinning an empty GitNexus repo", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.clear(screen.getByLabelText(REPO_PATH_LABEL));
    await user.click(screen.getByRole("button", { name: "固定当前仓库" }));

    expect(screen.getByText("请先输入 GitNexus 仓库路径 · 再固定仓库")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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
    expect(screen.getByLabelText(REPO_PATH_LABEL)).toHaveValue("F:\\BETA");
    expect(screen.getByText("已切换 GitNexus 仓库 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "上移固定仓库 F:\\GAMMA" }));

    expect(JSON.parse(window.localStorage.getItem(PINNED_REPO_PATHS_KEY) ?? "[]")).toEqual([
      "F:\\ALPHA",
      "F:\\GAMMA",
      "F:\\BETA",
    ]);
    expect(screen.getByText("已调整固定仓库顺序 · 可继续提问")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "取消固定 F:\\PIN-ME" }));

    expect(screen.getByRole("button", { name: "固定仓库 F:\\PIN-ME" })).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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
    fireEvent.change(screen.getByLabelText(REPO_PATH_LABEL), {
      target: { value: "F:\\MOSS-SYSTEM-V1" },
    });

    await new Promise((resolve) => setTimeout(resolve, 450));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cues the repo path requirement when loading GitNexus processes without a repo", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.clear(screen.getByLabelText(REPO_PATH_LABEL));
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    expect(screen.getByText("请先输入 GitNexus 仓库路径 · 再读取流程")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
  });

  it("cues the process selection requirement when viewing without a selected GitNexus process", async () => {
    const user = userEvent.setup();
    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    openProcessTools();
    await user.click(screen.getByRole("button", { name: "查看所选流程" }));

    expect(screen.getByText("请先从流程列表选择一个流程。")).toBeInTheDocument();
    expect(screen.getByText("请先选择 GitNexus 流程 · 再查看")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cues retry after GitNexus process loading fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse({}, 500));

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("读取 GitNexus 流程失败 · 可修改仓库路径后重试")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    screen.getByRole("button", { name: "查看所选流程" }).focus();
    await act(async () => {
      resolveProcessesResponse(processesPayload);
      await Promise.resolve();
    });
    openProcessTools();

    await waitFor(() => {
      const select = screen.getByLabelText(PROCESS_NAME_LABEL) as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => option.value)).toEqual([
        "",
        "CheckoutFlow",
        "AuditFlow",
      ]);
    });
    expect(screen.getByText("已读取 GitNexus 流程 · 可选择流程查看")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
    await waitFor(() => expect(screen.getByRole("option", { name: "CheckoutFlow" })).toBeInTheDocument());

    const processSelect = screen.getByLabelText(PROCESS_NAME_LABEL);
    const viewProcessButton = screen.getByRole("button", { name: "查看所选流程" });
    await waitFor(() => expect(processSelect).toHaveValue("CheckoutFlow"));
    expect(viewProcessButton).not.toBeDisabled();
    await user.click(viewProcessButton);
    screen.getByLabelText(PROCESS_SEARCH_LABEL).focus();

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
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
    await waitFor(() => expect(screen.getByLabelText(PROCESS_NAME_LABEL)).toHaveValue("CheckoutFlow"));

    await user.click(screen.getByRole("button", { name: "查看所选流程" }));
    screen.getByLabelText(PROCESS_SEARCH_LABEL).focus();
    await act(async () => {
      resolveProcessResponse(buildJsonResponse({}, 500));
      await Promise.resolve();
    });

    expect(await screen.findByText("智能体查询失败（500）")).toBeInTheDocument();
    expect(screen.getByText("查看 GitNexus 流程失败 · 可重新选择流程后重试")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus());
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: /读取流程/ }));
    expect(screen.getByText("正在读取 GitNexus 流程 · 可继续输入")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();

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
    await waitFor(() => expect(screen.getByLabelText(PROCESS_NAME_LABEL)).toHaveValue("CheckoutFlow"));
    await user.click(screen.getByRole("button", { name: /查看所选流程/ }));
    expect(screen.getByText("正在查看 GitNexus 流程 · 可继续输入")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();

    await screen.findByText("正在准备快速回答，结果会直接出现在这里。");
    const status = getAgentTurnStatus();
    expect(status).toHaveTextContent("本地查询进行中");
    expect(status).toHaveTextContent("准备本地查询");
    expect(status).toHaveTextContent("正在准备快速回答，结果会直接出现在这里。");
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.click(screen.getByRole("button", { name: "读取流程" }));
    openProcessTools();
    await waitFor(() => expect(screen.getByRole("option", { name: "AuditFlow" })).toBeInTheDocument());

    await user.type(screen.getByLabelText(PROCESS_SEARCH_LABEL), "Audit");

    const select = screen.getByLabelText(PROCESS_NAME_LABEL) as HTMLSelectElement;
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
    fireEvent.change(screen.getByLabelText(REPO_PATH_LABEL), {
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
    let select = screen.getByLabelText(PROCESS_NAME_LABEL) as HTMLSelectElement;
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

    select = screen.getByLabelText(PROCESS_NAME_LABEL) as HTMLSelectElement;
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
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
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
            routing_surface: "standalone_workbench",
          }),
        }),
      );
    });
  });

  it("keeps examples in advanced tools after a conversation starts", async () => {
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

    const quickExamples = openGitNexusTools()!;
    const quickExampleButton = within(quickExamples).getByRole("button", {
      name: "组合概览：规模、损益、久期和信用风险有什么变化？",
    });
    expect(quickExampleButton).toBeVisible();

    await user.click(quickExampleButton);

    const prompt = "组合概览：规模、损益、久期和信用风险有什么变化？";
    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(input).toHaveValue(prompt);
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", prompt.length);
    expect(input).toHaveProperty("selectionEnd", prompt.length);
    expect(screen.getByText("已填入快捷问题 · Enter 发送")).toBeInTheDocument();
  });

  it("loads remembered repo_path from localStorage", () => {
    window.localStorage.setItem(
      RECENT_REPO_PATHS_KEY,
      JSON.stringify(["F:\\MOSS-SYSTEM-V1", "F:\\NEWMOSS"]),
    );

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    expect(screen.getByLabelText(REPO_PATH_LABEL)).toHaveValue("F:\\MOSS-SYSTEM-V1");
    expect(screen.getByRole("button", { name: "F:\\MOSS-SYSTEM-V1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "F:\\NEWMOSS" })).toBeInTheDocument();
  });

  it("persists recent repo_path after query", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        buildManagedRunPayload(
          {
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
          },
          "agent_run:gitnexus-repo-path",
        ),
      ),
    );

    render(<AgentWorkbenchPage />);

    openGitNexusTools();
    await user.type(screen.getByLabelText(REPO_PATH_LABEL), "F:\\MOSS-SYSTEM-V1");
    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "GitNexus context");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem(RECENT_REPO_PATHS_KEY) ?? "[]")).toEqual([
        "F:\\MOSS-SYSTEM-V1",
      ]);
    });
  });
});
