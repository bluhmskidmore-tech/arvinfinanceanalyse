import { createElement, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ApiEnvelope, ResultMeta, SourcePreviewPayload } from "../api/contracts";
import { routerFuture } from "../router/routerFuture";
import OperationsAnalysisPage from "../features/workbench/pages/OperationsAnalysisPage";

vi.mock("../features/workbench/business-analysis/RevenueCostBridge", () => ({
  RevenueCostBridge: () =>
    createElement("div", {
      "data-testid": "operations-revenue-bridge-stub",
    }),
}));

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
  it("keeps source, macro, news, FX, and PnL operations hidden from this workbench", async () => {
    const base = createApiClient({ mode: "mock" });
    const sourcePreviewMeta: ResultMeta = {
      trace_id: "tr_source_hub_test",
      basis: "analytical",
      result_kind: "preview.source-foundation",
      formal_use_allowed: false,
      source_version: "sv_source_hub_test",
      vendor_version: "vv_none",
      rule_version: "rv_source_preview_v1",
      cache_version: "cv_source_preview_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:00:00Z",
    };
    const macroFoundationMeta: ResultMeta = {
      trace_id: "tr_macro_hub_test",
      basis: "analytical",
      result_kind: "preview.macro-foundation",
      formal_use_allowed: false,
      source_version: "sv_macro_hub_test",
      vendor_version: "vv_choice_catalog_v1",
      rule_version: "rv_phase1_macro_vendor_v1",
      cache_version: "cv_phase1_macro_vendor_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:02:00Z",
    };
    const macroLatestMeta: ResultMeta = {
      trace_id: "tr_choice_macro_hub_test",
      basis: "analytical",
      result_kind: "macro.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_macro_hub_test",
      vendor_version: "vv_choice_macro_20260410",
      rule_version: "rv_choice_macro_thin_slice_v1",
      cache_version: "cv_choice_macro_thin_slice_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:03:00Z",
    };
    const choiceNewsMeta: ResultMeta = {
      trace_id: "tr_choice_news_hub_test",
      basis: "analytical",
      result_kind: "news.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_news_hub_test",
      vendor_version: "vv_none",
      rule_version: "rv_choice_news_v1",
      cache_version: "cv_choice_news_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:05:00Z",
    };
    const sourceFoundationPayload: ApiEnvelope<SourcePreviewPayload> = {
      result_meta: sourcePreviewMeta,
      result: {
        sources: [
          {
            ingest_batch_id: "batch-z-1",
            batch_created_at: "2026-04-10T09:00:00Z",
            source_family: "zqtz",
            report_date: "2025-12-31",
            report_start_date: "2025-12-01",
            report_end_date: "2025-12-31",
            report_granularity: "daily",
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
      result_meta: macroFoundationMeta,
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
      result_meta: macroLatestMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "公开市场7天逆回购利率",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            frequency: "daily",
            source_version: "sv_choice_macro_hub_test",
            vendor_version: "vv_choice_macro_20260410",
            quality_flag: "ok" as const,
            refresh_tier: "stable" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "batch" as const,
            policy_note: "thin slice",
            latest_change: -0.05,
            recent_points: [
              {
                trade_date: "2026-04-09",
                value_numeric: 1.8,
                source_version: "sv",
                vendor_version: "vv",
                quality_flag: "ok" as const,
              },
            ],
          },
        ],
      },
    }));
    const getChoiceNewsEvents = vi.fn(async () => ({
      result_meta: choiceNewsMeta,
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
      await screen.findByRole("heading", { name: "经营分析" }),
    ).toBeInTheDocument();
    expect(screen.getByText("范围")).toBeInTheDocument();
    expect(screen.getByText("口径")).toBeInTheDocument();
    expect(screen.getByText("币种")).toBeInTheDocument();
    expect(screen.getByText("周期")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "专题入口：资产负债正式读面" }),
    ).toBeInTheDocument();
    const balanceAnalysisLinks = screen.getAllByRole("link", { name: "进入资产负债分析" });
    expect(balanceAnalysisLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of balanceAnalysisLinks) {
      expect(link).toHaveAttribute("href", "/balance-analysis");
    }
    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-balance-report-date")).toHaveTextContent(
        "2025-12-31",
      );
      expect(screen.getByTestId("operations-entry-balance-amortized")).toHaveTextContent("1,123");
      expect(screen.getByTestId("operations-entry-balance-market-value")).toHaveTextContent("1,202");
    });
    expect(screen.queryByRole("button", { name: /数据源与运维状态/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "数据源预览" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "进入数据源预览" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "宏观观察" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "进入市场数据页" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "新闻事件窗" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "进入新闻事件窗" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "正式 FX 中间价状态" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "PnL 表刷新" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-entry-pnl-refresh-button")).not.toBeInTheDocument();
    expect(screen.queryByText("Macro data release calendar updated.")).not.toBeInTheDocument();
    expect(screen.queryByText("vendor callback timeout")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-entry-source-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-entry-macro-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-entry-news-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-entry-formal-fx-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-source-file")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-source-group-counts")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-source-preview-mode")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-macro-fetch-meta")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-macro-policy-note")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-macro-latest-change")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-macro-recent-points")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-news-meta-evt-001")).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-news-meta-evt-002")).not.toBeInTheDocument();
    expect(screen.queryByText(/区间 2025-12-01/)).not.toBeInTheDocument();
    expect(screen.queryByText(/规则 rv_source_preview_v1/)).not.toBeInTheDocument();
    expect(screen.queryByText(/频率 daily/)).not.toBeInTheDocument();

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

  it("renders a single designed operations cockpit without layout preview controls", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const preview = await screen.findByTestId("operations-layout-preview");
    expect(await screen.findByTestId("operations-business-kpis")).toBeInTheDocument();
    expect(preview).not.toHaveAttribute("data-layout-variant");
    expect(screen.queryByTestId("operations-layout-switcher")).not.toBeInTheDocument();
    expect(screen.getByTestId("operations-business-kpis")).toHaveTextContent("经营净收入");
    expect(screen.getByTestId("operations-business-kpis")).not.toHaveTextContent("总市值");
  });

  it("renders the business-analysis cockpit on the first screen", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByTestId("operations-entry-balance-section");
    expect(await screen.findByTestId("operations-business-kpis")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-conclusion-grid")).toBeInTheDocument();
    const contributionGrid = await screen.findByTestId("operations-contribution-grid");
    expect(contributionGrid).toBeInTheDocument();
    await waitFor(() => {
      expect(within(contributionGrid).getByText("债券投资")).toBeInTheDocument();
      expect(contributionGrid).toHaveTextContent("/ui/pnl/product-category");
      expect(contributionGrid).not.toHaveTextContent("240001.IB");
    });
    expect(await screen.findByTestId("operations-structure-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-entry-recommendation")).toBeInTheDocument();
    const heroProvenance = await screen.findByTestId("operations-hero-provenance");
    expect(heroProvenance).toHaveTextContent("物化/候选对账");
    expect(heroProvenance).toHaveTextContent("静态示例");
    expect(await screen.findByTestId("operations-contribution-table-provenance")).toHaveTextContent("口径 formal");
  });

  it("does not claim evidence is sufficient when critical read surfaces are empty", async () => {
    const base = createApiClient({ mode: "mock" });

    renderPage({
      ...base,
      getSourceFoundation: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_empty_source",
          basis: "analytical" as const,
          result_kind: "preview.source-foundation",
          formal_use_allowed: false,
          source_version: "sv_empty_source",
          vendor_version: "vv_none",
          rule_version: "rv_source_preview_v1",
          cache_version: "cv_source_preview_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: { sources: [] },
      })),
      getMacroFoundation: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_macro_catalog",
          basis: "analytical" as const,
          result_kind: "preview.macro-foundation",
          formal_use_allowed: false,
          source_version: "sv_macro_catalog",
          vendor_version: "vv_catalog",
          rule_version: "rv_phase1_macro_vendor_v1",
          cache_version: "cv_phase1_macro_vendor_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:01:00Z",
        },
        result: { read_target: "duckdb" as const, series: [] },
      })),
      getChoiceMacroLatest: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_macro_latest_empty",
          basis: "analytical" as const,
          result_kind: "macro.choice.latest",
          formal_use_allowed: false,
          source_version: "sv_macro_latest_empty",
          vendor_version: "vv_macro_latest_empty",
          rule_version: "rv_choice_macro_thin_slice_v1",
          cache_version: "cv_choice_macro_thin_slice_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:02:00Z",
        },
        result: { read_target: "duckdb" as const, series: [] },
      })),
      getFxFormalStatus: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_fx_empty",
          basis: "formal" as const,
          result_kind: "fx.formal.status",
          formal_use_allowed: true,
          source_version: "sv_fx_empty",
          vendor_version: "vv_fx_empty",
          rule_version: "rv_fx_formal_mid_v1",
          cache_version: "cv_fx_formal_mid_v1",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:03:00Z",
        },
        result: {
          read_target: "duckdb" as const,
          vendor_priority: ["choice", "akshare", "fail_closed"],
          candidate_count: 0,
          materialized_count: 0,
          latest_trade_date: null,
          carry_forward_count: 0,
          rows: [],
        },
      })),
    });

    expect(await screen.findByText("经营口径证据链不完整")).toBeInTheDocument();
    const recommendation = await screen.findByTestId("operations-entry-recommendation");
    expect(recommendation).not.toHaveTextContent("产品分类经营口径可用于本期判断");
  });
});
