import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { AgentDisabledError } from "../api/agentClient";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { AgentEnvelope } from "../api/contracts";
import { AgentPanel } from "../features/agent/AgentPanel";

function renderAgentPanel(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <AgentPanel pageId="test-page" reportDate="2026-03-31" currentFilters={{ k: 1 }} />
    </Wrapper>,
  );
}

describe("AgentPanel", () => {
  it("renders question input and submit control", () => {
    renderAgentPanel(createApiClient({ mode: "mock" }));
    expect(screen.getByTestId("agent-panel-question")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel-submit")).toBeInTheDocument();
  });

  it("shows answer after submit", async () => {
    renderAgentPanel(createApiClient({ mode: "mock" }));
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "举例问题" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-answer")).toHaveTextContent("Agent 当前为演示模式");
    });
  });

  it("shows evidence quality_flag after response", async () => {
    renderAgentPanel(createApiClient({ mode: "mock" }));
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "q" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-quality-flag")).toHaveTextContent("ok");
    });
  });

  it("renders suggested_actions as passive chips", async () => {
    renderAgentPanel(createApiClient({ mode: "mock" }));
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "q" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-chips")).toHaveTextContent("演示建议动作");
    });
  });

  it("shows friendly message when Agent is disabled (503)", async () => {
    const base = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...base,
      queryAgent: vi.fn(async () => {
        throw new AgentDisabledError("Agent 当前未启用");
      }),
    };
    renderAgentPanel(client);
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "q" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-disabled")).toHaveTextContent("Agent 当前未启用");
    });
  });

  it("shows loading state while query is in flight", async () => {
    const base = createApiClient({ mode: "mock" });
    let release: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      queryAgent: async (req) => {
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        return base.queryAgent(req);
      },
    };
    renderAgentPanel(slowClient);
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "slow" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => {
      expect(screen.getByTestId("agent-panel-loading")).toBeInTheDocument();
    });
    release?.();
    await waitFor(() => {
      expect(screen.queryByTestId("agent-panel-loading")).not.toBeInTheDocument();
    });
  });

  it("passes page_context into queryAgent (no legacy context)", async () => {
    const base = createApiClient({ mode: "mock" });
    const queryAgent = vi.fn(async (): Promise<AgentEnvelope> => base.queryAgent({ question: "noop" }));
    const client: ApiClient = {
      ...base,
      queryAgent,
    };
    renderAgentPanel(client);
    fireEvent.change(screen.getByTestId("agent-panel-question"), {
      target: { value: "ctx-check" },
    });
    fireEvent.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => expect(queryAgent).toHaveBeenCalled());
    const arg = queryAgent.mock.calls[0]?.[0];
    expect(arg?.context).toBeUndefined();
    expect(arg?.page_context).toMatchObject({
      page_id: "test-page",
      current_filters: { k: 1, report_date: "2026-03-31" },
      selected_rows: [],
      context_note: null,
    });
  });
});
