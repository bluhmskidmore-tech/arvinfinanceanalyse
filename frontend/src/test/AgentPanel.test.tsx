import type { ReactElement } from "react";
import { fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider } from "../api/clientContext";
import { AgentPanel } from "../features/agent/AgentPanel";

vi.mock("../mocks/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../mocks/navigation")>()),
  isAgentFrontendEnabled: () => true,
}));

const AGENT_PAGE_CONTEXT_CHANGE_LABEL = "页面上下文已更新";
const AGENT_QUESTION_INPUT_LABEL = "向 Agent 提问";
const REPO_PATH_LABEL = "GitNexus 仓库路径";

function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function buildAgentResult({
  answer = "Embedded Agent answered.",
  resultKind = "agent.analysis_chat",
  qualityFlag = "warning",
  suggestedActions = [],
}: {
  answer?: string;
  resultKind?: string;
  qualityFlag?: "ok" | "warning" | "error" | "stale" | "missing";
  suggestedActions?: Array<{
    type: string;
    label: string;
    payload: Record<string, unknown>;
    requires_confirmation: boolean;
  }>;
} = {}) {
  return {
    answer,
    cards: [{ type: "metric", title: "Research Summary", value: "Alpha momentum is strong." }],
    evidence: {
      tables_used: ["choice_stock_daily_observation"],
      filters_applied: {
        provider: "local",
        transport: "sync",
        research_domain: "stock",
      },
      evidence_rows: 2,
      quality_flag: qualityFlag,
    },
    result_meta: {
      trace_id: `tr_${resultKind.replaceAll(".", "_")}`,
      basis: "formal",
      result_kind: resultKind,
      formal_use_allowed: resultKind !== "agent.analysis_chat",
    },
    next_drill: [],
    suggested_actions: suggestedActions,
  };
}

function renderAgentPanel() {
  return render(
    <AgentPanel
      pageId="test-page"
      reportDate="2026-03-31"
      currentFilters={{ k: 1 }}
      defaultFilters={{ research_domain: "stock" }}
    />,
  );
}

function render(ui: ReactElement) {
  return rtlRender(ui, { wrapper: ApiClientProvider });
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

describe("AgentPanel", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the embedded Copilot controls through the legacy AgentPanel entry", () => {
    renderAgentPanel();

    expect(screen.getByTestId("agent-panel")).toBeInTheDocument();
    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-question")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-submit")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "输入提示" })).toHaveTextContent("Enter");
    expect(screen.queryByLabelText(REPO_PATH_LABEL)).not.toBeInTheDocument();
  });

  it("updates and focuses the embedded composer when the default question changes", () => {
    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="explain current page"
      />,
    );

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue("explain current page");

    rerender(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="review selected row"
      />,
    );

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("review selected row");
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", "review selected row".length);
    expect(input).toHaveProperty("selectionEnd", "review selected row".length);
  });

  it("does not replace an edited embedded composer draft when the default question changes", () => {
    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="explain current page"
      />,
    );

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    input.focus();
    fireEvent.change(input, { target: { value: "my manual follow-up" } });

    rerender(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="review selected row"
      />,
    );

    expect(input).toHaveValue("my manual follow-up");
    expect(input).toHaveFocus();
  });

  it("announces page context changes in the embedded panel", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildAgentResult()));
    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        reportDate="2026-03-31"
        currentFilters={{ desk: "bond" }}
        selectedRows={[{ instrument_id: "bond-1" }]}
      />,
    );

    expect(screen.queryByRole("status", { name: AGENT_PAGE_CONTEXT_CHANGE_LABEL })).not.toBeInTheDocument();

    rerender(
      <AgentPanel
        pageId="test-page"
        reportDate="2026-04-30"
        currentFilters={{ desk: "bond" }}
        selectedRows={[{ instrument_id: "bond-2" }]}
      />,
    );

    const contextNotice = screen.getByRole("status", { name: AGENT_PAGE_CONTEXT_CHANGE_LABEL });
    expect(contextNotice).toHaveTextContent("页面上下文已更新");
    expect(contextNotice).toHaveTextContent("下一问将使用当前页面选择");

    rerender(
      <AgentPanel
        pageId="test-page"
        reportDate="2026-04-30"
        currentFilters={{ desk: "bond" }}
        selectedRows={[{ instrument_id: "bond-2" }]}
      />,
    );

    expect(screen.getAllByRole("status", { name: AGENT_PAGE_CONTEXT_CHANGE_LABEL })).toHaveLength(1);

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "review the updated selection");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText("Embedded Agent answered.")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: AGENT_PAGE_CONTEXT_CHANGE_LABEL })).not.toBeInTheDocument();
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(JSON.parse(String((options as RequestInit | undefined)?.body))).toMatchObject({
      question: "review the updated selection",
      page_context: {
        current_filters: {
          report_date: "2026-04-30",
        },
        selected_rows: [{ instrument_id: "bond-2" }],
      },
    });
  });

  it("auto-expands and resets the composer textarea height as draft length changes", async () => {
    const user = userEvent.setup();
    renderAgentPanel();

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    Object.defineProperty(input, "scrollHeight", {
      configurable: true,
      value: 168,
    });

    await user.type(input, "line one{Shift>}{Enter}{/Shift}line two{Shift>}{Enter}{/Shift}line three");

    expect(input.style.height).toBe("168px");

    await user.clear(input);

    expect(input.style.height).toBe("");
  });

  it("resets the expanded composer height after submitting a multiline draft", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildAgentResult()));
    renderAgentPanel();

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    Object.defineProperty(input, "scrollHeight", {
      configurable: true,
      value: 168,
    });

    await user.type(input, "line one{Shift>}{Enter}{/Shift}line two{Shift>}{Enter}{/Shift}line three");
    expect(input.style.height).toBe("168px");

    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText("Embedded Agent answered.")).toBeInTheDocument();
    const dockedInput = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL) as HTMLTextAreaElement;
    expect(dockedInput).toHaveValue("");
    expect(dockedInput.style.height).toBe("");
    expect(dockedInput).toHaveFocus();
  });

  it("keeps the composer in view after clearing a typed draft", async () => {
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

    try {
      renderAgentPanel();

      const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
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
      await user.type(input, "draft to clear in place");
      const clearButton = screen.getByRole("button", { name: /清空输入/ });
      expect(clearButton).toHaveAccessibleName(/draft to clear in place/);
      await user.click(clearButton);

      expect(input).toHaveValue("");
      expect(document.activeElement).toBe(input);
      expect(scrollTargets.some((target) => target.getAttribute("aria-label") === AGENT_QUESTION_INPUT_LABEL)).toBe(true);
      expect(scrollOptions.at(-1)).toMatchObject({ behavior: "smooth", block: "nearest" });
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

  it("submits page_context and default filters through the embedded request body", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildAgentResult()));
    renderAgentPanel();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/agent/query");
    expect(JSON.parse(String((options as RequestInit | undefined)?.body))).toMatchObject({
      question: "please judge current risk",
      page_context: {
        page_id: "test-page",
        current_filters: {
          k: 1,
          research_domain: "stock",
          report_date: "2026-03-31",
        },
        selected_rows: [],
        context_note: null,
      },
    });
  });

  it("renders answer, cards, evidence, and suggested actions after submit", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        buildAgentResult({
          answer: "Local analysis fallback answered.",
          suggestedActions: [
            {
              type: "execute_intent",
              label: "\u7ec4\u5408\u6982\u89c8",
              payload: { intent: "portfolio_overview" },
              requires_confirmation: true,
            },
          ],
        }),
      ),
    );
    renderAgentPanel();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByTestId("agent-panel-answer")).toHaveTextContent(
      "Local analysis fallback answered.",
    );
    expect(screen.getByText("Research Summary")).toBeInTheDocument();
    expect(screen.getByText(/choice_stock_daily_observation/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "\u7ec4\u5408\u6982\u89c8" })).toBeInTheDocument();
  });

  it("keeps execute_intent suggestions display-only in the read-only embedded panel", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        buildAgentResult({
          suggestedActions: [
            {
              type: "execute_intent",
              label: "组合概览",
              payload: { intent: "portfolio_overview" },
              requires_confirmation: true,
            },
            {
              type: "inspect_drill",
              label: "期限桶",
              payload: { dimension: "term_bucket" },
              requires_confirmation: false,
            },
          ],
        }),
      ),
    );
    renderAgentPanel();

    expect(screen.getByText("只读")).toBeInTheDocument();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));
    await screen.findByTestId("agent-panel-answer");

    const executeButton = screen.getByRole("button", { name: "组合概览" });
    expect(executeButton).toBeDisabled();
    expect(screen.getByText("只读 · 仅展示")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认执行：组合概览" })).not.toBeInTheDocument();

    await user.click(screen.getByText("更多建议 · 1 项"));
    await user.click(screen.getByRole("button", { name: "期限桶" }));

    expect(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL)).toHaveValue(
      "请基于当前 evidence 继续下钻：期限桶",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("surfaces governance signals in the embedded copilot result", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(buildJsonResponse(buildAgentResult()));
    renderAgentPanel();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));
    await screen.findByTestId("agent-panel-answer");

    const callout = screen.getByRole("status", { name: "数据可信状态提示" });
    expect(callout).toHaveTextContent("证据质量存在预警，结论请人工复核");
    expect(callout).toHaveTextContent("本结果不可作为正式口径，仅供分析参考");
  });

  it("keeps embedded conversation context when default question changes after an answer", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildAgentResult({
            answer: "First embedded answer.",
          }),
        ),
      )
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildAgentResult({
            answer: "Second embedded answer.",
          }),
        ),
      );

    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="first embedded question"
      />,
    );

    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("First embedded answer.")).toBeInTheDocument();

    rerender(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="second embedded question"
      />,
    );

    const input = screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL);
    expect(input).toHaveValue("second embedded question");
    expect(screen.getByText("First embedded answer.")).toBeInTheDocument();

    await user.click(screen.getByTestId("agent-panel-submit"));
    expect(await screen.findByText("Second embedded answer.")).toBeInTheDocument();

    const [, secondOptions] = fetchMock.mock.calls[1] ?? [];
    expect(JSON.parse(String((secondOptions as RequestInit | undefined)?.body))).toMatchObject({
      question: "second embedded question",
      context: {
        conversation: {
          recent_turns: [
            {
              question: "first embedded question",
              answer: "First embedded answer.",
              result_kind: "agent.analysis_chat",
            },
          ],
        },
      },
    });
  });

  it("shows a disabled message when the backend returns the disabled contract", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      buildJsonResponse(
        {
          enabled: false,
          phase: "phase1",
          detail: "Agent currently disabled.",
        },
        503,
      ),
    );
    renderAgentPanel();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText(/未启用|disabled/i)).toBeInTheDocument();
  });

  it("shows an in-flight local sync status while the request is pending", async () => {
    const user = userEvent.setup();
    let release: (() => void) | undefined;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(buildJsonResponse(buildAgentResult()));
        }),
    );
    renderAgentPanel();

    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    const turnStatus = await screen.findByRole("status", { name: "回答状态：please judge current risk" });
    expect(turnStatus).toHaveTextContent("本地查询");
    expect(screen.getByText("正在回答 · Shift+Enter 换行")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-submit")).toBeDisabled();
    release?.();
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-submit")).toBeDisabled();
    });
    await user.type(screen.getByLabelText(AGENT_QUESTION_INPUT_LABEL), "follow-up risk check");
    expect(screen.getByTestId("agent-panel-submit")).not.toBeDisabled();
  });
});
