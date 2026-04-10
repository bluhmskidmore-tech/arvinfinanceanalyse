import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

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
});
