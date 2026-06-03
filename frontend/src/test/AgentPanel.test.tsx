import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentPanel } from "../features/agent/AgentPanel";

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
    expect(screen.getByLabelText("agent-question-input")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-question")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-submit")).toBeInTheDocument();
    expect(screen.queryByLabelText("repo-path-input")).not.toBeInTheDocument();
  });

  it("updates and focuses the embedded composer when the default question changes", () => {
    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="explain current page"
      />,
    );

    expect(screen.getByLabelText("agent-question-input")).toHaveValue("explain current page");

    rerender(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="review selected row"
      />,
    );

    const input = screen.getByLabelText("agent-question-input");
    expect(input).toHaveValue("review selected row");
    expect(input).toHaveFocus();
  });

  it("does not replace an edited embedded composer draft when the default question changes", () => {
    const { rerender } = render(
      <AgentPanel
        pageId="test-page"
        defaultQuestion="explain current page"
      />,
    );

    const input = screen.getByLabelText("agent-question-input");
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

    expect(screen.queryByRole("status", { name: "agent-page-context-change" })).not.toBeInTheDocument();

    rerender(
      <AgentPanel
        pageId="test-page"
        reportDate="2026-04-30"
        currentFilters={{ desk: "bond" }}
        selectedRows={[{ instrument_id: "bond-2" }]}
      />,
    );

    const contextNotice = screen.getByRole("status", { name: "agent-page-context-change" });
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

    expect(screen.getAllByRole("status", { name: "agent-page-context-change" })).toHaveLength(1);

    await user.type(screen.getByLabelText("agent-question-input"), "review the updated selection");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByText("Embedded Agent answered.")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "agent-page-context-change" })).not.toBeInTheDocument();
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

    const input = screen.getByLabelText("agent-question-input") as HTMLTextAreaElement;
    Object.defineProperty(input, "scrollHeight", {
      configurable: true,
      value: 168,
    });

    await user.type(input, "line one{Shift>}{Enter}{/Shift}line two{Shift>}{Enter}{/Shift}line three");

    expect(input.style.height).toBe("168px");

    await user.clear(input);

    expect(input.style.height).toBe("");
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
      await user.type(input, "draft to clear in place");
      await user.click(screen.getByRole("button", { name: "清空输入" }));

      expect(input).toHaveValue("");
      expect(document.activeElement).toBe(input);
      expect(scrollTargets.some((target) => target.getAttribute("aria-label") === "agent-question-input")).toBe(true);
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

    await user.type(screen.getByLabelText("agent-question-input"), "please judge current risk");
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

    await user.type(screen.getByLabelText("agent-question-input"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByTestId("agent-panel-answer")).toHaveTextContent(
      "Local analysis fallback answered.",
    );
    expect(screen.getByText("Research Summary")).toBeInTheDocument();
    expect(screen.getByText(/choice_stock_daily_observation/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "\u7ec4\u5408\u6982\u89c8" })).toBeInTheDocument();
  });

  it("keeps suggested governed intent actions in the same embedded conversation", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildAgentResult({
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
      )
      .mockResolvedValueOnce(
        buildJsonResponse(
          buildAgentResult({
            answer: "Formal portfolio overview answered.",
            resultKind: "agent.portfolio_overview",
            qualityFlag: "ok",
          }),
        ),
      );
    renderAgentPanel();

    await user.type(screen.getByLabelText("agent-question-input"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));
    await screen.findByTestId("agent-panel-answer");
    await user.click(screen.getByRole("button", { name: "\u7ec4\u5408\u6982\u89c8" }));

    expect(await screen.findByText("Formal portfolio overview answered.")).toBeInTheDocument();
    expect(screen.getByLabelText("agent-conversation")).toHaveTextContent(
      "\u6267\u884c\u5efa\u8bae\u52a8\u4f5c\uff1a\u7ec4\u5408\u6982\u89c8",
    );
    const [, options] = fetchMock.mock.calls[1] ?? [];
    expect(JSON.parse(String((options as RequestInit | undefined)?.body))).toMatchObject({
      question: "\u7ec4\u5408\u6982\u89c8",
      context: {
        intent: "portfolio_overview",
        conversation: {
          recent_turns: [{ result_kind: "agent.analysis_chat" }],
        },
      },
    });
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

    const input = screen.getByLabelText("agent-question-input");
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

    await user.type(screen.getByLabelText("agent-question-input"), "please judge current risk");
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

    await user.type(screen.getByLabelText("agent-question-input"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    expect(await screen.findByRole("status", { name: "agent-turn-status" })).toHaveTextContent("本地查询");
    expect(screen.getByText("正在回答 · Shift+Enter 换行")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-submit")).toBeDisabled();
    release?.();
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-submit")).toBeDisabled();
    });
    await user.type(screen.getByLabelText("agent-question-input"), "follow-up risk check");
    expect(screen.getByTestId("agent-panel-submit")).not.toBeDisabled();
  });
});
