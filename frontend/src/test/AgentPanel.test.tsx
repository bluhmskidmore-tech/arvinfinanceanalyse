import { render, screen, waitFor } from "@testing-library/react";
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

    expect(await screen.findByRole("status")).toHaveTextContent("本地查询");
    expect(screen.getByTestId("agent-panel-submit")).toBeDisabled();
    release?.();
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-submit")).not.toBeDisabled();
    });
  });
});
