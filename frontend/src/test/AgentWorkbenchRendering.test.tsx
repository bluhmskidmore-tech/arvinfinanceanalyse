import { fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkbenchPage, { EmbeddedAgentCopilot } from "../features/agent/AgentWorkbenchPage";
import {
  AGENT_DISABLED_STATUS_LABEL,
  AGENT_PLACEHOLDER,
  AGENT_QUESTION_INPUT_LABEL,
  AGENT_RESULT_DETAILS_LABEL,
  AGENT_RUNTIME_STATUS_LABEL,
  AGENT_WORKBENCH_CSS_PATH,
  GITNEXUS_CONTEXT_BUTTON,
  GITNEXUS_PROCESSES_BUTTON,
  GITNEXUS_STATUS_BUTTON,
  LOCAL_ANALYSIS_PAGE_CONTEXT,
  PAGE_CONTEXT_PLACEHOLDER,
  PROCESS_NAME_LABEL,
  PROCESS_SEARCH_LABEL,
  REPO_PATH_LABEL,
  buildGovernedPortfolioOverviewResult,
  buildJsonResponse,
  buildLocalAnalysisChatResult,
  buildLocalOrdinaryTextResult,
  buildManagedRunPayload,
  getAgentTurnStatus,
  mockManagedRunResult,
  mockNarrowAgentViewport,
  mockScrollIntoView,
  openGitNexusTools,
  openProcessTools,
  renderWithAgentClient,
} from "./agentWorkbenchFixtures";

describe("AgentWorkbenchPage · 结果渲染与页面骨架", () => {
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

  it("advertises GitNexus repo graph as a supported query example", () => {
    render(<AgentWorkbenchPage />);

    expect(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
    ).toBeInTheDocument();
  });

  it("keeps the empty agent page chat-first without default technical labels", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByText("MOSS Chat")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "MOSS Chat" })).toBeInTheDocument();
    expect(screen.getByText("常用入口")).toBeInTheDocument();
    expect(screen.queryByText("Agent Workbench")).not.toBeInTheDocument();
    expect(screen.queryByText(/Research \/ MOSS intents/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新对话" })).toBeInTheDocument();
  });

  it("keeps the page shell while exposing EmbeddedAgentCopilot as the reusable copilot body", () => {
    render(<EmbeddedAgentCopilot showHeader={false} />);

    expect(screen.queryByRole("heading", { name: "智能体对话" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(AGENT_PLACEHOLDER)).toBeInTheDocument();
    openGitNexusTools();
    expect(screen.getByLabelText(REPO_PATH_LABEL)).toBeInTheDocument();
  });

  it("renders explicit repo_path input and GitNexus quick examples", () => {
    render(<AgentWorkbenchPage />);

    const advancedDetails = screen.getByLabelText("高级工具", { selector: "summary" }).closest("details");
    expect(advancedDetails).not.toBeNull();
    expect(advancedDetails).not.toHaveAttribute("open");
    openGitNexusTools();
    expect(advancedDetails).toHaveAttribute("open");
    expect(screen.getByRole("textbox", { name: REPO_PATH_LABEL })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "固定当前仓库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "读取流程" })).toBeInTheDocument();
    const processDetails = screen.getByText("流程筛选与查看").closest("details");
    expect(processDetails).not.toBeNull();
    expect(processDetails).not.toHaveAttribute("open");
    const viewProcessButton = screen.getByText("查看所选流程").closest("button");
    expect(viewProcessButton).not.toBeNull();
    expect(screen.getByLabelText(PROCESS_SEARCH_LABEL)).not.toBeVisible();
    expect(viewProcessButton).not.toBeVisible();
    openProcessTools();
    expect(processDetails).toHaveAttribute("open");
    expect(screen.getByRole("textbox", { name: PROCESS_SEARCH_LABEL })).toBeVisible();
    expect(viewProcessButton).toBeVisible();
    expect(screen.getByRole("combobox", { name: PROCESS_NAME_LABEL })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "解释当前页面的主要结论和风险点" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /组合概览/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_STATUS_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_CONTEXT_BUTTON })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: GITNEXUS_PROCESSES_BUTTON })).toBeInTheDocument();
  });

  it("keeps technical runtime details collapsed by default", () => {
    render(<AgentWorkbenchPage />);

    const runtimeStatus = screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL);
    expect(runtimeStatus).toHaveTextContent("待提问");
    expect(within(runtimeStatus).getByText("运行详情")).toBeVisible();
    expect(within(runtimeStatus).getByText("Engine")).not.toBeVisible();
  });

  it("announces runtime status changes without expanding technical details", () => {
    render(<AgentWorkbenchPage />);

    const runtimeStatus = screen.getByRole("status", { name: AGENT_RUNTIME_STATUS_LABEL });
    expect(runtimeStatus).toHaveAttribute("aria-live", "polite");
    expect(runtimeStatus).toHaveAttribute("aria-atomic", "true");
  });

  it("shows that a directly opened workbench has no business-page context", () => {
    render(<AgentWorkbenchPage />);

    expect(screen.getByRole("status", { name: "业务页上下文状态" })).toHaveTextContent(
      "当前为独立对话。解释具体页面时，可从业务页的复核助手带入筛选和选中记录。",
    );
    expect(
      screen.queryByRole("button", { name: "解释当前页面的主要结论和风险点" }),
    ).not.toBeInTheDocument();
  });

  it("renders the local analysis-chat fallback with evidence and suggested actions", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()));

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
    expect(screen.getByText("本地分析对话")).toBeInTheDocument();
    expect(screen.getByText("已捕获上下文")).toBeInTheDocument();
    expect(screen.getByText("组合概览")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL)).toHaveTextContent("local");
    expect(getAgentTurnStatus()).toHaveTextContent("本地查询完成");
    const resultDrawer = screen.getByText("查看依据 · 2 项").closest("details");
    expect(resultDrawer).not.toBeNull();
    expect(resultDrawer).not.toHaveAttribute("open");
    const resultDetails = screen.getByLabelText(AGENT_RESULT_DETAILS_LABEL);
    expect(resultDetails).toHaveClass("agent-result-side");
    expect(resultDetails).not.toBeVisible();
    fireEvent.click(screen.getByText("查看依据 · 2 项"));
    expect(resultDrawer).toHaveAttribute("open");
    expect(resultDetails).toBeVisible();
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
      const resultDrawer = screen.getByText("查看依据 · 2 项").closest("details");
      expect(resultDrawer).not.toBeNull();
      if (!resultDrawer) {
        throw new Error("Expected compact result details drawer to exist");
      }
      const resultDetails = screen.getByLabelText(AGENT_RESULT_DETAILS_LABEL);
      expect(resultDrawer).not.toHaveAttribute("open");
      expect(resultDetails).not.toBeVisible();

      scrollTargets.length = 0;
      fireEvent.click(screen.getByText("查看依据 · 2 项"));
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

  it("surfaces stale, fallback, and non-formal governance signals in a page-level callout", async () => {
    const user = userEvent.setup();
    const baseResult = buildLocalAnalysisChatResult();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        ...baseResult,
        evidence: { ...baseResult.evidence, quality_flag: "stale" },
        result_meta: { ...baseResult.result_meta, fallback_mode: "latest_snapshot" },
      }),
    );

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const callout = await screen.findByRole("status", { name: "数据可信状态提示" });
    expect(callout).toHaveTextContent("数据状态提示");
    expect(callout).toHaveTextContent("证据数据可能陈旧，请核对报告日期后再使用");
    expect(callout).toHaveTextContent("结果使用最新快照降级数据，未命中请求日期");
    expect(callout).toHaveTextContent("本结果不可作为正式口径，仅供分析参考");
  });

  it("shows a single governance callout combining warning quality and non-formal signals", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildLocalAnalysisChatResult()));

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    const callouts = screen.getAllByRole("status", { name: "数据可信状态提示" });
    expect(callouts).toHaveLength(1);
    expect(callouts[0]).toHaveTextContent("证据质量存在预警，结论请人工复核");
    expect(callouts[0]).toHaveTextContent("本结果不可作为正式口径，仅供分析参考");
    expect(callouts[0]).not.toHaveTextContent("降级");
  });

  it("keeps the governance callout hidden when the latest result carries no risk signals", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildGovernedPortfolioOverviewResult()));

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "组合概览");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("正式组合概览结果：资产规模和风险摘要已返回。")).toBeInTheDocument();

    expect(screen.queryByRole("status", { name: "数据可信状态提示" })).not.toBeInTheDocument();
  });

  it("reveals server SQL evidence as a read-only disclosure", async () => {
    const user = userEvent.setup();
    const baseResult = buildLocalAnalysisChatResult();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse({
        ...baseResult,
        evidence: {
          ...baseResult.evidence,
          sql_executed: ["SELECT report_date, market_value FROM fact_formal_zqtz_balance_daily LIMIT 10"],
        },
      }),
    );

    render(
      <EmbeddedAgentCopilot variant="embedded" pageContext={LOCAL_ANALYSIS_PAGE_CONTEXT} />,
    );

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "帮我判断今天的主要风险");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("本地分析对话已接住这轮问题，但未运行正式指标查询。")).toBeInTheDocument();

    fireEvent.click(screen.getByText("查看依据 · 2 项"));
    const sqlDisclosure = screen.getByTestId("agent-evidence-sql");
    expect(sqlDisclosure).toHaveTextContent("查看只读 SQL 披露 · 1 条");
    fireEvent.click(within(sqlDisclosure).getByText("查看只读 SQL 披露 · 1 条"));
    expect(sqlDisclosure).toHaveTextContent(
      "SELECT report_date, market_value FROM fact_formal_zqtz_balance_daily LIMIT 10",
    );
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

  it("renders structured table cards instead of flattening them into metrics", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildManagedRunPayload({
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
      }, "agent_run:gitnexus-cards")),
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
      buildJsonResponse(buildManagedRunPayload({
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
      }, "agent_run:gitnexus-process-graph")),
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
      buildJsonResponse(buildManagedRunPayload({
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
      }, "agent_run:gitnexus-status-summary")),
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
    const disabledStatus = screen.getByRole("status", { name: AGENT_DISABLED_STATUS_LABEL });
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
    const stoppedEditAction = screen.getByRole("button", { name: /编辑这句/ });
    expect(stoppedEditAction).toHaveAccessibleName("编辑这句：q");
    await user.click(stoppedEditAction);
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("q");
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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

  it("keeps the agent page visually conversation-first", () => {
    const cssText = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(cssText).toMatch(/\.agent-workbench-shell:not\(\.agent-workbench-shell--embedded\)\s*\{[^}]*width:\s*min\(100%,\s*840px\)/s);
    expect(cssText).toMatch(/\.agent-workbench-shell:not\(\.agent-workbench-shell--embedded\)\s*>\s*\.agent-chat-composer\s*\{[^}]*order:\s*2/s);
    expect(cssText).toMatch(/\.agent-workbench-shell:not\(\.agent-workbench-shell--embedded\)\s*>\s*\.agent-runtime-strip\s*\{[^}]*clip-path:\s*inset\(50%\)/s);
    expect(cssText).toMatch(/\.agent-workbench-shell:not\(\.agent-workbench-shell--embedded\)\s*>\s*\.agent-conversation\s*\{[^}]*order:\s*5/s);
    expect(cssText).toMatch(/\.agent-workbench-shell:not\(\.agent-workbench-shell--embedded\)\s*>\s*\.agent-composer-dock\s*\{[^}]*order:\s*6/s);
    expect(cssText).toMatch(/\.agent-workbench-header\s*\{[^}]*justify-content:\s*space-between/s);
    expect(cssText).not.toContain("agent-workbench-header__cue");
    expect(cssText).toMatch(/\.agent-quick-entry\s*\{[^}]*border:\s*0/s);
    expect(cssText).toMatch(/\.agent-conversation\s*\{[^}]*border:\s*0/s);
    expect(cssText).toMatch(/\.agent-answer-message\s*\{[^}]*background:\s*transparent/s);
    expect(cssText).toMatch(/\.agent-chat-composer\s*\{[^}]*border-radius:\s*24px/s);
  });

  it("renders answer, cards, evidence, next_drill, and result_meta on success", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildManagedRunPayload({
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
      }, "agent_run:managed-result-detail")),
    );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "managed result detail check",
    );
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(
      await screen.findByText("组合久期风险主要集中在 3Y-5Y。"),
    ).toBeInTheDocument();
    expect(screen.getByText("组合久期")).toBeInTheDocument();
    expect(screen.getByText("4.27")).toBeInTheDocument();
    expect(screen.getAllByText("久期").length).toBeGreaterThan(0);
    const resultDrawer = screen.getByText("查看依据 · 2 项").closest("details");
    expect(resultDrawer).not.toBeNull();
    expect(resultDrawer).not.toHaveAttribute("open");
    const resultDetails = screen.getByLabelText(AGENT_RESULT_DETAILS_LABEL);
    expect(resultDetails).not.toBeVisible();
    fireEvent.click(screen.getByText("查看依据 · 2 项"));
    expect(resultDrawer).toHaveAttribute("open");
    expect(resultDetails).toBeVisible();
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
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
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

  it("renders Hermes chat answers without provider cards or runtime detail panels", async () => {
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

    expect(await screen.findByText("pong")).toBeInTheDocument();
    expect(screen.getAllByText("pong").length).toBeGreaterThan(0);
    expect(screen.queryByText("Hermes Agent")).not.toBeInTheDocument();
    expect(screen.queryByText("Provider")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(AGENT_RESULT_DETAILS_LABEL)).not.toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /回答状态/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/回答进度/)).not.toBeInTheDocument();
    expect(screen.queryByText("收到问题")).not.toBeInTheDocument();
    expect(screen.queryByText("选择路径")).not.toBeInTheDocument();
    expect(screen.queryByText("整理回答")).not.toBeInTheDocument();
    expect(screen.queryByText("运行细节")).not.toBeInTheDocument();
    expect(screen.queryByText("查看全部运行信息")).not.toBeInTheDocument();
    expect(screen.queryByText("agent.hermes")).not.toBeInTheDocument();
    expect(screen.queryByText("智能体返回结果格式无效。")).not.toBeInTheDocument();
  });

  it("surfaces Hermes runtime status from evidence filters", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(buildManagedRunPayload({
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
      }, "agent_run:hermes-runtime-status")),
    );

    render(<AgentWorkbenchPage />);

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed provider task{Enter}");

    const runtimeStatus = await screen.findByLabelText(AGENT_RUNTIME_STATUS_LABEL);
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

    await user.type(screen.getByPlaceholderText(AGENT_PLACEHOLDER), "managed provider task");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("Dexter managed run complete.")).toBeInTheDocument();
    expect(getAgentTurnStatus()).toHaveTextContent("Dexter 托管任务完成");
    const runtimeStatus = screen.getByLabelText(AGENT_RUNTIME_STATUS_LABEL);
    expect(runtimeStatus).toHaveTextContent("Dexter");
    expect(runtimeStatus).toHaveTextContent("bridge");
    expect(runtimeStatus).toHaveTextContent("gpt-5.5");
    expect(runtimeStatus).toHaveTextContent("file");
  });

  it("shows empty-renderable fallback when payload is valid but nothing to display", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildManagedRunPayload(
            {
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
            },
            "agent_run:empty-renderable",
          ),
        ),
      )
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildManagedRunPayload(
            buildLocalOrdinaryTextResult("empty fallback regenerated answer"),
            "agent_run:empty-renderable-regenerated",
          ),
        ),
      );

    render(<AgentWorkbenchPage />);

    await user.type(
      screen.getByPlaceholderText(
        AGENT_PLACEHOLDER,
      ),
      "empty fallback question",
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
    const continueInputButton = screen.getByRole("button", { name: /继续输入/ });
    expect(continueInputButton).toHaveAccessibleName(/empty fallback question/);
    await user.click(continueInputButton);
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveFocus();
    expect(screen.getByText("可以调整问题 · Enter 发送")).toBeInTheDocument();
    const emptyRegenerateButton = screen.getByRole("button", { name: /重新生成/ });
    expect(emptyRegenerateButton).toHaveAccessibleName(/empty fallback question/);
    await user.click(emptyRegenerateButton);
    expect(await screen.findByText("empty fallback regenerated answer")).toBeInTheDocument();
  });
});
