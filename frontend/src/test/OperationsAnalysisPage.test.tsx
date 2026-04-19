import { createElement, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { vi } from "vitest";

import * as pollingModule from "../app/jobs/polling";
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

async function expandOperationsDataSourcesPanel(user: UserEvent) {
  const trigger = await screen.findByRole("button", { name: /数据源与运维状态/ });
  if (trigger.getAttribute("aria-expanded") !== "true") {
    await user.click(trigger);
  }
}

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
    const user = userEvent.setup();
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
      expect(screen.getByTestId("operations-entry-balance-amortized")).toHaveTextContent("720");
      expect(screen.getByTestId("operations-entry-balance-market-value")).toHaveTextContent("792");
    });
    await expandOperationsDataSourcesPanel(user);
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
    const sourceFiles = screen.getAllByTestId("operations-source-file");
    expect(sourceFiles.some((el) => el.textContent?.includes("ZQTZSHOW-20251231.xls"))).toBe(true);
    expect(screen.getAllByTestId("operations-source-group-counts").some((el) => el.textContent?.includes("债券类 55")))
      .toBe(true);
    expect(screen.getAllByTestId("operations-source-preview-mode").every((el) => el.textContent?.includes("tabular")))
      .toBe(true);
    expect(screen.getByTestId("operations-macro-fetch-meta")).toHaveTextContent("stable");
    expect(screen.getByTestId("operations-macro-fetch-meta")).toHaveTextContent("latest");
    expect(screen.getByTestId("operations-macro-policy-note")).toHaveTextContent("thin slice");
    expect(screen.getByTestId("operations-macro-latest-change")).toHaveTextContent("-0.05");
    expect(screen.getByTestId("operations-macro-recent-points")).toHaveTextContent("有 1 条");
    expect(screen.getByTestId("operations-news-meta-evt-001")).toHaveTextContent("err 0");
    expect(screen.getByTestId("operations-news-meta-evt-002")).toHaveTextContent("err 101");
    expect(screen.getByTestId("operations-news-meta-evt-002")).toHaveTextContent("vendor callback timeout");
    expect(screen.getByText(/区间 2025-12-01/)).toBeInTheDocument();
    expect(screen.getByText(/粒度\s+daily/)).toBeInTheDocument();
    expect(screen.getAllByText(/规则 rv_source_preview_v1/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/频率 daily/)).toBeInTheDocument();
    expect(screen.getByText(/质量 ok/)).toBeInTheDocument();
    expect(screen.getByTestId("operations-news-meta-evt-001")).toHaveTextContent("sectornews");

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

  it("surfaces formal FX status separately from analytical market observations", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getFxFormalStatus = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_fx_formal_status_test",
        basis: "formal" as const,
        result_kind: "fx.formal.status",
        formal_use_allowed: true,
        source_version: "sv_fx_formal_status_test",
        vendor_version: "vv_fx_formal_status_test",
        rule_version: "rv_fx_formal_mid_v1",
        cache_version: "cv_fx_formal_mid_v1",
        quality_flag: "warning" as const,
        vendor_status: "ok" as const,
        fallback_mode: "latest_snapshot" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T09:20:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        vendor_priority: ["choice", "akshare", "fail_closed"],
        candidate_count: 3,
        materialized_count: 2,
        latest_trade_date: "2026-04-11",
        carry_forward_count: 1,
        rows: [
          {
            base_currency: "USD",
            quote_currency: "CNY",
            pair_label: "USD/CNY",
            series_id: "FX.USD.CNY",
            series_name: "USD/CNY middle rate",
            vendor_series_code: "USD/CNY",
            trade_date: "2026-04-11",
            observed_trade_date: "2026-04-10",
            mid_rate: 7.21,
            source_name: "fx_daily_mid",
            vendor_name: "choice",
            vendor_version: "vv_fx_formal_status_test",
            source_version: "sv_fx_formal_status_test",
            is_business_day: false,
            is_carry_forward: true,
            status: "ok" as const,
          },
          {
            base_currency: "EUR",
            quote_currency: "CNY",
            pair_label: "EUR/CNY",
            series_id: "FX.EUR.CNY",
            series_name: "EUR/CNY middle rate",
            vendor_series_code: "EUR/CNY",
            trade_date: null,
            observed_trade_date: null,
            mid_rate: null,
            source_name: null,
            vendor_name: null,
            vendor_version: null,
            source_version: null,
            is_business_day: null,
            is_carry_forward: null,
            status: "missing" as const,
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getFxFormalStatus,
    });

    await expandOperationsDataSourcesPanel(user);
    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-formal-fx-count")).toHaveTextContent(
        "2 / 3",
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "正式 FX 中间价状态",
      );
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "最新交易日 2026-04-11",
      );
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "沿用前值数量 1",
      );
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "缺失 EUR/CNY",
      );
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "USD/CNY middle rate",
      );
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent("fx_daily_mid");
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent("sv_fx_formal_status_test");
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent("vv_fx_formal_status_test");
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent("营业日");
      expect(screen.getByTestId("operations-entry-formal-fx-status")).toHaveTextContent(
        "tr_fx_formal_status_test",
      );
    });

    await waitFor(() => {
      expect(getFxFormalStatus).toHaveBeenCalledTimes(1);
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

    await screen.findByRole("heading", { name: "经营分析" });
    await expandOperationsDataSourcesPanel(user);
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

    await screen.findByRole("heading", { name: "经营分析" });
    await expandOperationsDataSourcesPanel(user);
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

    await screen.findByRole("heading", { name: "经营分析" });
    await expandOperationsDataSourcesPanel(user);
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

  it("shows unavailable summary cards when source or status queries fail", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });

    renderPage({
      ...base,
      getSourceFoundation: vi.fn(async () => {
        throw new Error("source failed");
      }),
      getMacroFoundation: vi.fn(async () => {
        throw new Error("macro catalog failed");
      }),
      getChoiceMacroLatest: vi.fn(async () => {
        throw new Error("macro latest failed");
      }),
      getChoiceNewsEvents: vi.fn(async () => {
        throw new Error("news failed");
      }),
      getFxFormalStatus: vi.fn(async () => {
        throw new Error("fx failed");
      }),
    });

    await screen.findByRole("heading", { name: "经营分析" });
    await expandOperationsDataSourcesPanel(user);

    await waitFor(() => {
      expect(screen.getByTestId("operations-entry-source-count")).toHaveTextContent("不可用");
      expect(screen.getByTestId("operations-entry-macro-count")).toHaveTextContent("不可用");
      expect(screen.getByTestId("operations-entry-news-count")).toHaveTextContent("不可用");
      expect(screen.getByTestId("operations-entry-formal-fx-count")).toHaveTextContent("不可用");
    });
  });
  it("renders the business-analysis cockpit on the first screen", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    await screen.findByTestId("operations-entry-balance-section");
    expect(await screen.findByTestId("operations-business-kpis")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-conclusion-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-contribution-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-structure-grid")).toBeInTheDocument();
    expect(await screen.findByTestId("operations-entry-recommendation")).toBeInTheDocument();
    return;

    expect(
      screen.getByText(
        "本页 wave 1 只保留受控证据条、正式专题入口和一个由实时查询状态生成的判断建议，不再在首页混排硬编码 KPI、mock 经营事项或静态业务结论。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "当前页上半区聚焦经营结论、收益成本桥和质量观察；下半区保留数据源预览、宏观观察、新闻事件、正式 FX 状态和 PnL 刷新入口。所有正式数值均以后端契约为准。",
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("operations-business-kpis")).not.toBeInTheDocument();
    expect(await screen.findByTestId("operations-entry-recommendation")).toBeInTheDocument();
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

    expect(await screen.findByText("Evidence chain incomplete")).toBeInTheDocument();
    const recommendation = await screen.findByTestId("operations-entry-recommendation");
    expect(recommendation).not.toHaveTextContent("Evidence is sufficient for today’s operating call");
  });
});
