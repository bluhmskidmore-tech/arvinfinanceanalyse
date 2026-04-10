import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import { createWorkbenchMemoryRouter, renderWorkbenchApp } from "./renderWorkbenchApp";

function createChoiceNewsEnvelope(overrides?: Partial<{
  totalRows: number;
  offset: number;
  events: Array<{
    event_key: string;
    received_at: string;
    group_id: string;
    content_type: string;
    serial_id: number;
    request_id: number;
    error_code: number;
    error_msg: string;
    topic_code: string;
    item_index: number;
    payload_text: string | null;
    payload_json: string | null;
  }>;
}>) {
  return {
    result_meta: {
      trace_id: "tr_choice_news_test",
      basis: "analytical" as const,
      result_kind: "news.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_news_test",
      vendor_version: "vv_none",
      rule_version: "rv_choice_news_v1",
      cache_version: "cv_choice_news_v1",
      quality_flag: "ok" as const,
      scenario_flag: false,
      generated_at: "2026-04-10T09:00:00Z",
    },
    result: {
      total_rows: overrides?.totalRows ?? 1,
      limit: 2,
      offset: overrides?.offset ?? 0,
      events: overrides?.events ?? [
        {
          event_key: "ce_filter_target",
          received_at: "2026-04-10T09:00:00Z",
          group_id: "news_cmd1",
          content_type: "sectornews",
          serial_id: 1001,
          request_id: 500,
          error_code: 0,
          error_msg: "",
          topic_code: "S888010007API",
          item_index: 0,
          payload_text: "Filtered policy update",
          payload_json: null,
        },
      ],
    },
  };
}

function renderWorkbenchAppWithClient(client: ReturnType<typeof createApiClient>) {
  const router = createWorkbenchMemoryRouter(["/agent"]);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        refetchOnWindowFocus: false,
      },
    },
  });

  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} future={routerFuture} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("AgentPlaceholderPage", () => {
  it("renders the hidden agent route as a real Choice news workbench", async () => {
    renderWorkbenchApp(["/agent"]);

    expect(
      await screen.findByRole("heading", { name: "新闻事件工作台" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/analytical read-only/i),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Choice News Topics 2026-04-09 / 经济数据"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("agent-news-event-ce_mock_001")).toHaveTextContent(
      "group_id news_cmd1",
    );
    expect(screen.getByTestId("agent-news-event-ce_mock_001")).toHaveTextContent(
      "topic_code S888010007API",
    );
    expect(screen.getByTestId("agent-news-visible-events")).toHaveTextContent(
      "Visible page rows",
    );
    expect(screen.getByTestId("agent-news-topic-count")).toHaveTextContent(
      "Visible page topics",
    );
    expect(screen.getByTestId("agent-news-error-count")).toHaveTextContent(
      "Visible page error rows",
    );
    expect(screen.getByTestId("agent-news-callback-count")).toHaveTextContent(
      "Visible slice callback envelopes",
    );
    expect(screen.getByTestId("agent-news-error-pane")).toHaveTextContent(
      "No visible slice error events on this page.",
    );
  });

  it("applies filters through the API client contract", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const getChoiceNewsEventsSpy = vi
      .fn()
      .mockResolvedValueOnce(
        createChoiceNewsEnvelope({
          totalRows: 2,
          events: [
            {
              event_key: "ce_first_page",
              received_at: "2026-04-10T09:01:00Z",
              group_id: "news_cmd1",
              content_type: "sectornews",
              serial_id: 1001,
              request_id: 500,
              error_code: 0,
              error_msg: "",
              topic_code: "C000022",
              item_index: 0,
              payload_text: "Initial page event",
              payload_json: null,
            },
          ],
        }),
      )
      .mockResolvedValueOnce(createChoiceNewsEnvelope());

    renderWorkbenchAppWithClient({
      ...baseClient,
      getChoiceNewsEvents: getChoiceNewsEventsSpy,
    });

    await screen.findByRole("heading", { name: "新闻事件工作台" });
    await screen.findByText("Initial page event");

    await user.type(screen.getByLabelText("agent-news-group-id"), "news_cmd1");
    await user.type(screen.getByLabelText("agent-news-topic-code"), "S888010007API");
    await user.click(screen.getByLabelText("agent-news-error-only"));
    await user.click(screen.getByTestId("agent-news-apply-filters"));

    await waitFor(() => {
      expect(getChoiceNewsEventsSpy).toHaveBeenNthCalledWith(2, {
        limit: 2,
        offset: 0,
        groupId: "news_cmd1",
        topicCode: "S888010007API",
        errorOnly: true,
        receivedFrom: undefined,
        receivedTo: undefined,
      });
    });
    expect(getChoiceNewsEventsSpy).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Filtered policy update")).toBeInTheDocument();
    expect(
      screen.getByText("Choice News Topics 2026-04-09 / 经济数据"),
    ).toBeInTheDocument();
  });

  it("paginates through the Choice news event feed", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/agent"]);

    await screen.findByRole("heading", { name: "新闻事件工作台" });
    expect(
      await screen.findByText(
        "Macro data release calendar updated for CPI and industrial production.",
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByTestId("agent-news-next-page"));

    expect(await screen.findByTestId("agent-news-event-ce_mock_003")).toHaveTextContent(
      "vendor callback timeout",
    );
    expect(screen.getByText("ERR 101")).toBeInTheDocument();
    expect(screen.getByTestId("agent-news-event-ce_mock_003")).toHaveTextContent(
      "news_cmd1 / __callback__",
    );
    expect(screen.getByTestId("agent-news-error-pane")).toHaveTextContent("Callback anomaly");
    expect(screen.getByTestId("agent-news-error-pane")).toHaveTextContent(
      "news_cmd1 / __callback__",
    );

    await user.click(screen.getByTestId("agent-news-prev-page"));

    expect(
      await screen.findByText(
        "Macro data release calendar updated for CPI and industrial production.",
      ),
    ).toBeInTheDocument();
  });
});
