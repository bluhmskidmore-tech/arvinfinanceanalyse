import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import * as pollingModule from "../app/jobs/polling";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ApiEnvelope, SourcePreviewPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import OperationsAnalysisPage from "../features/workbench/pages/OperationsAnalysisPage";

function renderPage(client: ApiClient) {
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
        <MemoryRouter future={routerFuture}>
          <OperationsAnalysisPage />
        </MemoryRouter>
      </Wrapper>,
    );
  }

describe("OperationsAnalysisPage", () => {
  it("consolidates source preview, macro, and news into a single read-only workbench entry", async () => {
    const base = createApiClient({ mode: "mock" });
    const sourceFoundationPayload: ApiEnvelope<SourcePreviewPayload> = {
      result_meta: {
        trace_id: "tr_source_hub_test",
        basis: "analytical" as const,
        result_kind: "preview.source-foundation",
        formal_use_allowed: false,
        source_version: "sv_source_hub_test",
        vendor_version: "vv_none",
        rule_version: "rv_source_preview_v1",
        cache_version: "cv_source_preview_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:00:00Z",
      },
      result: {
        sources: [
          {
            ingest_batch_id: "batch-z-1",
            batch_created_at: "2026-04-10T09:00:00Z",
            source_family: "zqtz",
            report_date: "2025-12-31",
            source_file: "ZQTZSHOW-20251231.xls",
            total_rows: 55,
            manual_review_count: 1,
            source_version: "sv_source_hub_test",
            rule_version: "rv_source_preview_v1",
            group_counts: { 债券类: 55 },
            preview_mode: "tabular",
          },
          {
            ingest_batch_id: "batch-t-1",
            batch_created_at: "2026-04-10T08:00:00Z",
            source_family: "tyw",
            report_date: "2025-12-31",
            source_file: "TYWLSHOW-20251231.xls",
            total_rows: 14,
            manual_review_count: 0,
            source_version: "sv_source_hub_test",
            rule_version: "rv_source_preview_v1",
            group_counts: { 拆借类: 14 },
            preview_mode: "tabular",
          },
        ],
      },
    };
    const getSourceFoundation = vi.fn(async () => sourceFoundationPayload);
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_macro_hub_test",
        basis: "analytical" as const,
        result_kind: "preview.macro-foundation",
        formal_use_allowed: false,
        source_version: "sv_macro_hub_test",
        vendor_version: "vv_choice_catalog_v1",
        rule_version: "rv_phase1_macro_vendor_v1",
        cache_version: "cv_phase1_macro_vendor_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:02:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_choice_macro_hub_test",
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        source_version: "sv_choice_macro_hub_test",
        vendor_version: "vv_choice_macro_20260410",
        rule_version: "rv_choice_macro_thin_slice_v1",
        cache_version: "cv_choice_macro_thin_slice_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:03:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            source_version: "sv_choice_macro_hub_test",
            vendor_version: "vv_choice_macro_20260410",
          },
        ],
      },
    }));
    const getChoiceNewsEvents = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_choice_news_hub_test",
        basis: "analytical" as const,
        result_kind: "news.choice.latest",
        formal_use_allowed: false,
        source_version: "sv_choice_news_hub_test",
        vendor_version: "vv_none",
        rule_version: "rv_choice_news_v1",
        cache_version: "cv_choice_news_v1",
        quality_flag: "ok" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:05:00Z",
      },
      result: {
        total_rows: 2,
        limit: 3,
        offset: 0,
        events: [
          {
            event_key: "evt-001",
            received_at: "2026-04-10T09:05:00Z",
            group_id: "news_cmd1",
            content_type: "sectornews",
            serial_id: 1001,
            request_id: 500,
            error_code: 0,
            error_msg: "",
            topic_code: "S888010007API",
            item_index: 0,
            payload_text: "Macro data release calendar updated.",
            payload_json: null,
          },
          {
            event_key: "evt-002",
            received_at: "2026-04-10T09:00:00Z",
            group_id: "news_cmd1",
            content_type: "sectornews",
            serial_id: 1002,
            request_id: 501,
            error_code: 101,
            error_msg: "vendor callback timeout",
            topic_code: "__callback__",
            item_index: -1,
            payload_text: null,
            payload_json: null,
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getSourceFoundation,
      getMacroFoundation,
      getChoiceMacroLatest,
      getChoiceNewsEvents,
    });

    expect(
      await screen.findByRole("heading", { name: "经营分析入口" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-source-count")).toHaveTextContent("2");
      expect(screen.getByTestId("operations-entry-macro-count")).toHaveTextContent("1");
      expect(screen.getByTestId("operations-entry-news-count")).toHaveTextContent("2");
    });
    expect(screen.getByRole("link", { name: "进入数据源预览" })).toHaveAttribute(
      "href",
      "/source-preview",
    );
    expect(screen.getByRole("link", { name: "进入市场数据页" })).toHaveAttribute(
      "href",
      "/market-data",
    );
    expect(screen.getByRole("link", { name: "进入新闻事件窗" })).toHaveAttribute(
      "href",
      "/news-events",
    );
    expect(screen.getByText("Macro data release calendar updated.")).toBeInTheDocument();
    expect(screen.getByText("vendor callback timeout")).toBeInTheDocument();

    await waitFor(() => {
      expect(getSourceFoundation).toHaveBeenCalledTimes(1);
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getChoiceNewsEvents).toHaveBeenCalledWith({
        limit: 3,
        offset: 0,
      });
    });
  });

  it("polls formal pnl refresh status and shows the latest run id", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "pnl_materialize:test-run",
      job_name: "pnl_materialize",
      trigger_mode: "async",
      cache_key: "pnl:phase2:materialize:formal",
      report_date: "2026-02-28",
    }));
    const statusSpy = vi
      .fn()
      .mockResolvedValueOnce({
        status: "running",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
      })
      .mockResolvedValueOnce({
        status: "completed",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "terminal",
        cache_key: "pnl:phase2:materialize:formal",
        source_version: "sv_pnl_test",
      });

    renderPage({
      ...base,
      refreshFormalPnl: refreshSpy,
      getFormalPnlImportStatus: statusSpy,
    });

    await screen.findByRole("heading", { name: "经营分析入口" });
    await user.click(screen.getByTestId("operations-entry-pnl-refresh-button"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledTimes(1);
      expect(statusSpy).toHaveBeenCalledWith("pnl_materialize:test-run");
      expect(screen.getByTestId("operations-entry-pnl-refresh-run-id")).toHaveTextContent(
        "pnl_materialize:test-run",
      );
      expect(screen.getByTestId("operations-entry-pnl-refresh-status")).toHaveTextContent(
        /最近结果：completed/,
      );
    });
  });

  it("shows backend failure detail and preserves the run id when pnl refresh fails", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async () => ({
      status: "queued",
      run_id: "pnl_materialize:failed-run",
      job_name: "pnl_materialize",
      trigger_mode: "async",
      cache_key: "pnl:phase2:materialize:formal",
    }));
    const statusSpy = vi.fn(async () => ({
      status: "failed",
      run_id: "pnl_materialize:failed-run",
      job_name: "pnl_materialize",
      trigger_mode: "terminal",
      cache_key: "pnl:phase2:materialize:formal",
      error_message: "Pnl refresh worker failed.",
    }));

    renderPage({
      ...base,
      refreshFormalPnl: refreshSpy,
      getFormalPnlImportStatus: statusSpy,
    });

    await screen.findByRole("heading", { name: "经营分析入口" });
    await user.click(screen.getByTestId("operations-entry-pnl-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-pnl-refresh-run-id")).toHaveTextContent(
        "pnl_materialize:failed-run",
      );
      expect(screen.getByTestId("operations-entry-pnl-refresh-status")).toHaveTextContent(
        "最近结果：failed",
      );
      expect(screen.getByText(/Pnl refresh worker failed\./)).toBeInTheDocument();
    });
  });

  it("preserves the last known pnl refresh state when polling times out", async () => {
    const user = userEvent.setup();
    const pollingSpy = vi
      .spyOn(pollingModule, "runPollingTask")
      .mockImplementation(async (options) => {
        options.onUpdate?.({
          status: "running",
          run_id: "pnl_materialize:timeout-run",
        } as never);
        throw new Error("任务轮询超时");
      });

    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByRole("heading", { name: "经营分析入口" });
    await user.click(screen.getByTestId("operations-entry-pnl-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-pnl-refresh-run-id")).toHaveTextContent(
        "pnl_materialize:timeout-run",
      );
      expect(screen.getByTestId("operations-entry-pnl-refresh-status")).toHaveTextContent(
        "最近结果：running",
      );
      expect(screen.getByText(/任务轮询超时/)).toBeInTheDocument();
    });

    pollingSpy.mockRestore();
  });
});
