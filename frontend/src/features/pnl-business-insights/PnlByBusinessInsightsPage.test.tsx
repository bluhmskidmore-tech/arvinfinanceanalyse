import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="pnl-by-business-insights-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../../api/client";
import type {
  ApiEnvelope,
  PnlByBusinessInsightsPayload,
  PnlByBusinessPrecomputeStatus,
  PnlDatesPayload,
  ResultMeta,
} from "../../api/contracts";
import PnlByBusinessInsightsPage from "./PnlByBusinessInsightsPage";

const meta: ResultMeta = {
  trace_id: "tr_pnl_business_insights_test",
  basis: "formal",
  result_kind: "pnl.by_business_insights",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_none",
  rule_version: "rv_pnl_by_business_insights_v1",
  cache_version: "cv_pnl_by_business_insights_v1",
  quality_flag: "warning",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  requested_report_date: "2026-06-30",
  resolved_report_date: "2026-06-30",
  as_of_date: "2026-06-30",
  fallback_date: null,
  date_basis: "formal_report_date_cutoff",
  tables_used: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
  generated_at: "2026-07-15T00:00:00Z",
};

function buildPayload(
  metaOverrides: Partial<ResultMeta> = {},
  resultOverrides: Partial<PnlByBusinessInsightsPayload> = {},
): ApiEnvelope<PnlByBusinessInsightsPayload> {
  const quadrantRows: PnlByBusinessInsightsPayload["scale_yield_quadrant"]["rows"] = Array.from(
    { length: 6 },
    (_, index) => ({
      row_key: `row_${index + 1}`,
      business_type: `业务${index + 1}`,
      avg_balance: String((index + 1) * 100),
      scale_share_pct: String((index + 1) * 5),
      ftp_net_annualized_yield_pct: String(index + 1),
      quadrant_key: index < 3 ? "SMALL_LOW" : "LARGE_HIGH",
    }),
  );
  return {
    result_meta: { ...meta, ...metaOverrides },
    result: {
      result_version: "v2",
      year: 2026,
      as_of_date: "2026-06-30",
      baseline_requested_report_date: "2025-06-30",
      baseline_resolved_report_date: "2025-06-30",
      baseline_fallback_mode: "none",
      component_evidence: [
        {
          component: "current_ytd",
          requested_report_date: "2026-06-30",
          resolved_report_date: "2026-06-30",
          fallback_mode: "none",
          quality_flag: "ok",
          vendor_status: "ok",
          basis: "analytical",
          formal_use_allowed: false,
          result_kind: "pnl.by_business_ytd",
          trace_id: "tr_current",
          source_surface: "formal_pnl",
          source_version: "sv_current",
          rule_version: "rv_ytd",
          cache_version: "cv_ytd",
          tables_used: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          formal_source_admitted: true,
          admission_reason: null,
        },
        {
          component: "baseline_ytd",
          requested_report_date: "2025-06-30",
          resolved_report_date: "2025-06-30",
          fallback_mode: "none",
          quality_flag: "ok",
          vendor_status: "ok",
          basis: "analytical",
          formal_use_allowed: false,
          result_kind: "pnl.by_business_ytd",
          trace_id: "tr_baseline",
          source_surface: "formal_pnl",
          source_version: "sv_baseline",
          rule_version: "rv_ytd",
          cache_version: "cv_ytd",
          tables_used: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          formal_source_admitted: true,
          admission_reason: null,
        },
        {
          component: "monthly_2025",
          requested_report_date: "2025-12-31",
          resolved_report_date: "2025-12-31",
          fallback_mode: "none",
          quality_flag: "ok",
          vendor_status: "ok",
          basis: "analytical",
          formal_use_allowed: false,
          result_kind: "pnl.by_business_monthly",
          trace_id: "tr_monthly_2025",
          source_surface: "formal_pnl",
          source_version: "sv_monthly_2025",
          rule_version: "rv_monthly",
          cache_version: "cv_monthly",
          tables_used: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          formal_source_admitted: true,
          admission_reason: null,
        },
        {
          component: "monthly_2026",
          requested_report_date: "2026-06-30",
          resolved_report_date: "2026-06-30",
          fallback_mode: "none",
          quality_flag: "ok",
          vendor_status: "ok",
          basis: "analytical",
          formal_use_allowed: false,
          result_kind: "pnl.by_business_monthly",
          trace_id: "tr_monthly_2026",
          source_surface: "formal_pnl",
          source_version: "sv_monthly_2026",
          rule_version: "rv_monthly",
          cache_version: "cv_monthly",
          tables_used: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          formal_source_admitted: true,
          admission_reason: null,
        },
      ],
      concentration: {
        year: 2026,
        as_of_date: "2026-06-30",
        currency_basis: "CNY_EQUIVALENT",
        population_basis: "YTD_AVG_BALANCE_PARENT_ROWS",
        total_avg_balance: "3367.49",
        hhi_pct: "13.42",
        top_n: 3,
        top_n_share_pct: "50.50",
        rows: [
          { row_key: "row_6", business_type: "业务6", avg_balance: "600", share_pct: "30.00" },
          { row_key: "row_5", business_type: "业务5", avg_balance: "500", share_pct: "25.00" },
        ],
      },
      negative_ftp_persistence: {
        as_of_date: "2026-06-30",
        lookback_months: 12,
        window_start_month: "2025-07",
        window_end_month: "2026-06",
        months_observed: 12,
        negative_ftp_month_share_pct: "0.00",
        negative_ftp_longest_streak_months: 0,
        warning_threshold_pct: "50.00",
        minimum_observed_months: 6,
        warning_row_count: 1,
        eligible: true,
        status: "eligible",
        rows: [
          {
            row_key: "asset_zqtz_interbank_cd",
            business_type: "同业存单",
            months_observed: 12,
            negative_ftp_month_share_pct: "91.67",
            negative_ftp_longest_streak_months: 9,
            warning_triggered: true,
            eligible: true,
            status: "eligible",
          },
        ],
      },
      share_drift: {
        year: 2026,
        as_of_date: "2026-06-30",
        baseline_year: 2025,
        baseline_as_of_date: "2025-06-30",
        baseline_available: true,
        available: true,
        availability_reason: null,
        comparison_basis: "PRIOR_YEAR_SAME_PERIOD_YTD_AVG_BALANCE_SHARE",
        rows: [
          {
            row_key: "asset_zqtz_interbank_cd",
            business_type: "同业存单",
            current_share_pct: "14.52",
            baseline_share_pct: "7.62",
            drift_pp: "6.90",
            lifecycle_status: "continued",
          },
          {
            row_key: "asset_zqtz_public_fund",
            business_type: "公募基金",
            current_share_pct: "12.00",
            baseline_share_pct: "15.52",
            drift_pp: "-3.52",
            lifecycle_status: "continued",
          },
        ],
      },
      scale_yield_quadrant: {
        year: 2026,
        as_of_date: "2026-06-30",
        currency_basis: "CNY_EQUIVALENT",
        scale_basis: "YTD_AVG_BALANCE_SHARE",
        yield_basis: "FTP_NET_ANNUALIZED_YIELD_PCT",
        minimum_eligible_rows: 6,
        eligible_row_count: 6,
        total_avg_balance: "3367.49",
        available: true,
        scale_share_median_pct: "17.50",
        ftp_net_annualized_yield_median_pct: "3.500000",
        rows: quadrantRows,
      },
      reconciliation_diagnostics: {
        as_of_date: "2026-06-30",
        lookback_months: 12,
        available: true,
        availability_reason: null,
        rows: [
          {
            report_date: "2026-06-30",
            untraced_row_count: 117,
            total_row_count: 1723,
            untraced_share_pct: "6.79",
          },
        ],
      },
      ...resultOverrides,
    },
  };
}

const DEFAULT_REPORT_DATES = ["2026-06-30", "2025-12-31"];

function buildDatesPayload(
  reportDates: string[],
  sourceReportDates: string[] = reportDates,
): ApiEnvelope<PnlDatesPayload> {
  return {
    result_meta: {
      ...meta,
      trace_id: "tr_pnl_dates_test",
      result_kind: "pnl.dates",
      requested_report_date: null,
      resolved_report_date: null,
      as_of_date: null,
      date_basis: null,
    },
    result: {
      report_dates: reportDates,
      formal_fi_report_dates: sourceReportDates,
      nonstd_bridge_report_dates: sourceReportDates,
    },
  };
}

function buildPrecomputeStatus(
  overrides: Partial<PnlByBusinessPrecomputeStatus> = {},
): PnlByBusinessPrecomputeStatus {
  return {
    year: 2026,
    status: "completed",
    serving_mode: "published",
    is_current: true,
    run_id: null,
    report_date: "2026-06-30",
    latest_available_as_of_date: "2026-06-30",
    source_version: "sv_ready",
    rule_version: "rv_ready",
    queued_at: null,
    started_at: null,
    finished_at: "2026-06-30T11:59:00Z",
    generated_at: "2026-06-30T11:59:00Z",
    record_count: 1,
    error_message: null,
    failure_category: null,
    trigger_reason: null,
    retry_attempt: 0,
    retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
    readiness: "ready",
    generation: "gen-ready-1",
    dependencies: [
      {
        key: "current_ytd",
        requested_report_date: "2026-06-30",
        resolved_report_date: "2026-06-30",
        readiness: "ready",
        generation: "gen-ready-1",
        run_id: null,
        last_progress_at: "2026-06-30T11:59:00Z",
        error_message: null,
      },
      {
        key: "baseline_ytd",
        requested_report_date: "2025-06-30",
        resolved_report_date: "2025-06-30",
        readiness: "ready",
        generation: "gen-ready-1",
        run_id: null,
        last_progress_at: "2026-06-30T11:59:00Z",
        error_message: null,
      },
      {
        key: "monthly",
        requested_report_date: "2026-06-30",
        resolved_report_date: "2026-06-30",
        readiness: "ready",
        generation: "gen-ready-1",
        run_id: null,
        last_progress_at: "2026-06-30T11:59:00Z",
        error_message: null,
      },
    ],
    permissions: { can_rebuild: false, reason: "当前账号仅可查看" },
    last_progress_at: "2026-06-30T11:59:00Z",
    worker_stalled: false,
    recovery_hint: null,
    ...overrides,
  };
}

function buildClient(
  getPnlByBusinessInsights: ApiClient["getPnlByBusinessInsights"],
  reportDates: string[] = DEFAULT_REPORT_DATES,
): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    getFormalPnlDates: vi.fn(async () => buildDatesPayload(reportDates)),
    getPnlByBusinessInsights,
  };
}

function renderPage(client: ApiClient, initialEntry = "/pnl-by-business-insights") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter initialEntries={[initialEntry]}>
            <PnlByBusinessInsightsPage />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    ),
  };
}

describe("PnlByBusinessInsightsPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-06-30T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads only the approved insights endpoint and surfaces formal status metadata", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    const client = buildClient(getInsights);
    const candidateSpy = vi.spyOn(client, "getPnlByBusinessCandidateInsights");
    const ytdSpy = vi.spyOn(client, "getPnlByBusinessYtd");
    renderPage(client);

    const status = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { signal: expect.any(AbortSignal) },
    );
    expect(client.getFormalPnlDates).toHaveBeenCalledWith({
      page: "by_business_insights",
    });
    expect(candidateSpy).not.toHaveBeenCalled();
    expect(ytdSpy).not.toHaveBeenCalled();
    expect(status).toHaveTextContent("正式口径");
    expect(status).toHaveTextContent("质量 warning");
    expect(status).toHaveTextContent("降级 none");
    expect(status).toHaveTextContent("tr_pnl_business_insights_test");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-disclaimer"]')).toBeNull();
  });

  it("uses the published page date catalog when per-source date lists are intentionally empty", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    const client = buildClient(getInsights);
    client.getFormalPnlDates = vi.fn(async () =>
      buildDatesPayload(["2026-06-30"], []),
    );
    renderPage(client);

    await waitFor(() => {
      expect(getInsights).toHaveBeenCalledWith(
        2026,
        "2026-06-30",
        { signal: expect.any(AbortSignal) },
      );
    });
    expect(client.getFormalPnlDates).toHaveBeenCalledWith({
      page: "by_business_insights",
    });
  });

  it("uses the real pending task state instead of inferring preparation from a 10s GET timer", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    const client = buildClient(getInsights);
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      status: "running",
      serving_mode: "unavailable",
      is_current: false,
      run_id: "run-pending-1",
      readiness: "pending",
      generation: null,
      finished_at: null,
      generated_at: null,
      dependencies: buildPrecomputeStatus().dependencies?.map((dependency) => ({
        ...dependency,
        readiness: "pending",
        generation: null,
        run_id: "run-pending-1",
      })),
    }));
    renderPage(client);

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]')).toHaveTextContent(
        "整页本期、同期和月度依赖正在后台准备",
      );
    });
    expect(getInsights).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(10_500);
    });

    expect(document.querySelector('[data-testid="pnl-by-business-insights-slow-loading-note"]')).toBeNull();
    expect(client.getPnlByBusinessPrecomputeStatus).toHaveBeenCalledTimes(2);
    expect(getInsights).not.toHaveBeenCalled();
  });

  it("fixes the ready generation before reading and rejects a late response from the prior generation", async () => {
    let firstSignal: AbortSignal | undefined;
    let resolveFirst: ((value: ApiEnvelope<PnlByBusinessInsightsPayload>) => void) | undefined;
    let resolveSecond: ((value: ApiEnvelope<PnlByBusinessInsightsPayload>) => void) | undefined;
    const firstRequest = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((resolve) => {
      resolveFirst = resolve;
    });
    const secondRequest = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((resolve) => {
      resolveSecond = resolve;
    });
    const getInsights = vi.fn((
      _year: number,
      _asOfDate: string,
      options?: { signal?: AbortSignal; generation?: string },
    ) => {
      if (options?.generation === "gen-ready-1") {
        firstSignal = options.signal;
        return firstRequest;
      }
      return secondRequest;
    });
    const client = buildClient(getInsights);
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus());
    const { queryClient } = renderPage(client);

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { signal: expect.any(AbortSignal), generation: "gen-ready-1" },
    ));
    act(() => {
      queryClient.setQueryData(
        ["pnl-by-business-insights", "precompute-status", "mock", 2026, "2026-06-30"],
        buildPrecomputeStatus({ generation: "gen-ready-2" }),
      );
    });

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { signal: expect.any(AbortSignal), generation: "gen-ready-2" },
    ));
    expect(firstSignal?.aborted).toBe(true);
    await act(async () => {
      resolveSecond?.(buildPayload(
        { trace_id: "tr_generation_2" },
        { generation: "gen-ready-2" },
      ));
    });
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
        "tr_generation_2",
      );
    });
    await act(async () => {
      resolveFirst?.(buildPayload(
        { trace_id: "tr_generation_1_late" },
        { generation: "gen-ready-1" },
      ));
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).not.toHaveTextContent(
      "tr_generation_1_late",
    );
  });

  it("keeps stale data fail-closed for viewers and offers rebuild only when authorized", async () => {
    const viewerClient = buildClient(vi.fn(async () => buildPayload()));
    viewerClient.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      status: "completed",
      serving_mode: "unavailable",
      is_current: false,
      readiness: "stale",
      generation: null,
      permissions: { can_rebuild: false, reason: "当前账号仅可查看" },
    }));
    viewerClient.rebuildPnlByBusinessPrecompute = vi.fn(viewerClient.rebuildPnlByBusinessPrecompute);
    const viewerRender = renderPage(viewerClient);

    await waitFor(() => {
      const state = document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]');
      expect(state).toHaveTextContent("结果已过期");
      expect(state).toHaveTextContent("不会沿用旧响应的正式使用结论");
      expect(state).toHaveTextContent("当前账号仅可查看");
    });
    expect(viewerClient.getPnlByBusinessInsights).not.toHaveBeenCalled();
    expect(viewerClient.rebuildPnlByBusinessPrecompute).not.toHaveBeenCalled();
    expect(document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]')).not.toHaveTextContent(
      "请求后台准备",
    );
    viewerRender.unmount();

    const operatorClient = buildClient(vi.fn(async () => buildPayload()));
    operatorClient.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      status: "failed",
      serving_mode: "unavailable",
      is_current: false,
      readiness: "failed",
      generation: null,
      error_message: "materialization failed",
      permissions: { can_rebuild: true, reason: null },
    }));
    operatorClient.rebuildPnlByBusinessPrecompute = vi.fn(async () => buildPrecomputeStatus({
      status: "queued",
      serving_mode: "unavailable",
      is_current: false,
      run_id: "run-rebuild-1",
      readiness: "pending",
      generation: null,
      permissions: { can_rebuild: true, reason: null },
    }));
    renderPage(operatorClient);
    const prepareButton = await waitFor(() => {
      const button = Array.from(document.querySelectorAll("button")).find((node) => node.textContent === "请求后台准备");
      expect(button).toBeDefined();
      return button as HTMLButtonElement;
    });
    fireEvent.click(prepareButton);
    await waitFor(() => expect(operatorClient.rebuildPnlByBusinessPrecompute).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { includePageDependencies: true, scope: "selected" },
    ));
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]')).toHaveTextContent(
        "run-rebuild-1",
      );
    });
  });

  it("does not approve a result whose echoed generation differs from the ready status", async () => {
    const client = buildClient(vi.fn(async () => buildPayload(
      {},
      { generation: "gen-obsolete" },
    )));
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      generation: "gen-ready-2",
    }));
    renderPage(client);

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
      "正式口径 待确认",
    );
    expect(document.querySelector('[data-testid="pnl-by-business-insights-decision-brief"]')).toBeNull();
  });

  it("shows source-missing for the selected cutoff without substituting another date or zero result", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    const client = buildClient(getInsights);
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      status: "idle",
      serving_mode: "unavailable",
      is_current: false,
      readiness: "source_missing",
      generation: null,
      report_date: "2026-06-30",
      dependencies: [
        {
          ...buildPrecomputeStatus().dependencies![0],
          requested_report_date: "2026-06-30",
          resolved_report_date: null,
          readiness: "source_missing",
          generation: null,
        },
      ],
    }));
    renderPage(client);

    await waitFor(() => {
      const state = document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]');
      expect(state).toHaveTextContent("源数据缺失");
      expect(state).toHaveTextContent("2026-06-30");
      expect(state).toHaveTextContent("不会补零或换用其他日期");
    });
    expect(getInsights).not.toHaveBeenCalled();
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toBeNull();
  });

  it("stops polling a stalled worker and shows the server recovery path", async () => {
    const client = buildClient(vi.fn(async () => buildPayload()));
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      status: "running",
      serving_mode: "unavailable",
      is_current: false,
      run_id: "run-stalled-1",
      readiness: "pending",
      generation: null,
      worker_stalled: true,
      recovery_hint: "请在数据更新中心检查损益准备 worker",
    }));
    renderPage(client);

    await waitFor(() => {
      const state = document.querySelector('[data-testid="pnl-by-business-insights-precompute-state"]');
      expect(state).toHaveTextContent("后台准备长时间没有进展");
      expect(state).toHaveTextContent("请在数据更新中心检查损益准备 worker");
    });
    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });
    expect(client.getPnlByBusinessPrecomputeStatus).toHaveBeenCalledTimes(1);
  });

  it("keeps a compatible published result visible when a newer preparation attempt fails", async () => {
    const client = buildClient(vi.fn(async () =>
      buildPayload({}, { generation: "gen-ready-1" }),
    ));
    client.getPnlByBusinessPrecomputeStatus = vi.fn(async () => buildPrecomputeStatus({
      refresh_status: "failed",
      refresh_error_message: "2026-07-31 更新任务失败",
      refresh_failure_category: "worker_error",
    }));
    renderPage(client);

    const warning = await waitFor(() => {
      const node = document.querySelector(
        '[data-testid="pnl-by-business-insights-refresh-failed-serving-published"]',
      );
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(warning).toHaveTextContent("当前显示的正式结果日期为 2026-06-30");
    expect(warning).toHaveTextContent("2026-07-31 更新任务失败");
    expect(warning).toHaveTextContent("未用失败更新尝试的日期替换当前正式结果");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
      "正式口径 已批准",
    );
    expect(document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]')).toHaveTextContent(
      "13.42%",
    );
  });

  it("keeps the current cutoff result visible and identifies a failed refresh", async () => {
    let requestCount = 0;
    let rejectRefresh: ((reason?: unknown) => void) | undefined;
    let resolveRetry: ((value: ApiEnvelope<PnlByBusinessInsightsPayload>) => void) | undefined;
    const pendingRefresh = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((_resolve, reject) => {
      rejectRefresh = reject;
    });
    const pendingRetry = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((resolve) => {
      resolveRetry = resolve;
    });
    const getInsights = vi.fn(() => {
      requestCount += 1;
      if (requestCount === 1) return Promise.resolve(buildPayload());
      return requestCount === 2 ? pendingRefresh : pendingRetry;
    });
    const { queryClient } = renderPage(buildClient(getInsights));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
        "tr_pnl_business_insights_test",
      );
    });

    act(() => {
      void queryClient.invalidateQueries({
        queryKey: ["pnl-by-business-insights", "formal", "mock", 2026, "2026-06-30"],
      });
    });

    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(2));
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
      "tr_pnl_business_insights_test",
    );
    expect(document.querySelector('[data-testid="pnl-by-business-insights-refreshing"]')).toHaveTextContent(
      "正在更新当前截止日的结构分析",
    );

    await act(async () => {
      rejectRefresh?.(new Error("Request failed: /api/pnl/by-business-insights (500)"));
    });
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-refresh-error"]')).toHaveTextContent(
        "当前仍显示该截止日上次成功返回的结果",
      );
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
      "tr_pnl_business_insights_test",
    );

    fireEvent.click(
      document.querySelector('[data-testid="pnl-by-business-insights-refresh-error"] button')!,
    );
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(3));
    expect(document.querySelector('[data-testid="pnl-by-business-insights-refresh-error"]')).toBeNull();
    await act(async () => {
      resolveRetry?.(buildPayload());
    });
  });

  it("keeps the selected cutoff result visible when the report-date directory refresh fails", async () => {
    let dateRequestCount = 0;
    let rejectDatesRefresh: ((reason?: unknown) => void) | undefined;
    let resolveDatesRetry: ((value: ApiEnvelope<PnlDatesPayload>) => void) | undefined;
    const pendingDatesRefresh = new Promise<ApiEnvelope<PnlDatesPayload>>((_resolve, reject) => {
      rejectDatesRefresh = reject;
    });
    const pendingDatesRetry = new Promise<ApiEnvelope<PnlDatesPayload>>((resolve) => {
      resolveDatesRetry = resolve;
    });
    const client = buildClient(vi.fn(async () => buildPayload()));
    client.getFormalPnlDates = vi.fn(() => {
      dateRequestCount += 1;
      if (dateRequestCount === 1) return Promise.resolve(buildDatesPayload(DEFAULT_REPORT_DATES));
      return dateRequestCount === 2 ? pendingDatesRefresh : pendingDatesRetry;
    });
    const { queryClient } = renderPage(client);

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
        "tr_pnl_business_insights_test",
      );
    });

    act(() => {
      void queryClient.invalidateQueries({ queryKey: ["pnl-by-business-insights", "dates", "mock"] });
    });
    await waitFor(() => expect(client.getFormalPnlDates).toHaveBeenCalledTimes(2));

    await act(async () => {
      rejectDatesRefresh?.(new Error("Request failed: /api/pnl/dates (500)"));
    });
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-dates-refresh-error"]')).toHaveTextContent(
        "当前继续使用已成功加载的报告日期目录",
      );
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toHaveTextContent(
      "tr_pnl_business_insights_test",
    );

    fireEvent.click(
      document.querySelector('[data-testid="pnl-by-business-insights-dates-refresh-error"] button')!,
    );
    await waitFor(() => expect(client.getFormalPnlDates).toHaveBeenCalledTimes(3));
    expect(document.querySelector('[data-testid="pnl-by-business-insights-dates-refresh-error"]')).toBeNull();
    await act(async () => {
      resolveDatesRetry?.(buildDatesPayload(DEFAULT_REPORT_DATES));
    });
  });

  it("continues to load a selected cutoff from the retained directory after its refresh fails", async () => {
    let dateRequestCount = 0;
    let rejectDatesRefresh: ((reason?: unknown) => void) | undefined;
    const pendingDatesRefresh = new Promise<ApiEnvelope<PnlDatesPayload>>((_resolve, reject) => {
      rejectDatesRefresh = reject;
    });
    const getInsights = vi.fn((year: number, asOfDate: string) =>
      Promise.resolve(
        buildPayload(
          {
            trace_id: `tr_pnl_business_insights_${year}`,
            requested_report_date: asOfDate,
            resolved_report_date: asOfDate,
            as_of_date: asOfDate,
          },
          { as_of_date: asOfDate },
        ),
      ),
    );
    const client = buildClient(getInsights);
    client.getFormalPnlDates = vi.fn(() => {
      dateRequestCount += 1;
      return dateRequestCount === 1 ? Promise.resolve(buildDatesPayload(DEFAULT_REPORT_DATES)) : pendingDatesRefresh;
    });
    const { queryClient } = renderPage(client);

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { signal: expect.any(AbortSignal) },
    ));
    act(() => {
      void queryClient.invalidateQueries({ queryKey: ["pnl-by-business-insights", "dates", "mock"] });
    });
    await waitFor(() => expect(client.getFormalPnlDates).toHaveBeenCalledTimes(2));
    await act(async () => {
      rejectDatesRefresh?.(new Error("date directory temporarily unavailable"));
    });
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-dates-refresh-error"]')).not.toBeNull();
    });

    fireEvent.change(document.querySelector('[aria-label="pnl-by-business-insights-year"]')!, {
      target: { value: "2025" },
    });
    await waitFor(() => {
      expect(getInsights).toHaveBeenCalledWith(
        2025,
        "2025-12-31",
        { signal: expect.any(AbortSignal) },
      );
      const status = document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]');
      expect(status).toHaveTextContent("2025-12-31");
      expect(status).toHaveTextContent("tr_pnl_business_insights_2025");
    });
  });

  it("stops showing cached formal results and diagnostics after an insights 403", async () => {
    let requestCount = 0;
    let rejectRefresh: ((reason?: unknown) => void) | undefined;
    let resolveRecovery: ((value: ApiEnvelope<PnlByBusinessInsightsPayload>) => void) | undefined;
    const pendingRefresh = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((_resolve, reject) => {
      rejectRefresh = reject;
    });
    const pendingRecovery = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((resolve) => {
      resolveRecovery = resolve;
    });
    const getInsights = vi.fn(() => {
      requestCount += 1;
      if (requestCount === 1) return Promise.resolve(buildPayload());
      return requestCount === 2 ? pendingRefresh : pendingRecovery;
    });
    const { queryClient } = renderPage(buildClient(getInsights));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).not.toBeNull();
      expect(document.querySelector('[data-testid="pnl-by-business-insights-reconciliation-section"]')).not.toBeNull();
    });
    act(() => {
      void queryClient.invalidateQueries({
        queryKey: ["pnl-by-business-insights", "formal", "mock", 2026, "2026-06-30"],
      });
    });
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(2));
    await act(async () => {
      rejectRefresh?.(new Error("Request failed: /api/pnl/by-business-insights (403)"));
    });

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-access-denied"]')).toHaveTextContent(
        "读取权限已变更",
      );
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toBeNull();
    expect(document.querySelector('[data-testid="pnl-by-business-insights-reconciliation-section"]')).toBeNull();

    fireEvent.click(document.querySelector('[data-testid="pnl-by-business-insights-access-denied"] button')!);
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(3));
    expect(document.querySelector('[data-testid="pnl-by-business-insights-access-denied"] button')).toBeDisabled();
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toBeNull();
    await act(async () => {
      resolveRecovery?.(buildPayload());
    });
    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-access-denied"]')).toBeNull();
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).not.toBeNull();
    });
  });

  it("stops using a cached date directory after its refresh returns 401", async () => {
    let dateRequestCount = 0;
    let rejectDatesRefresh: ((reason?: unknown) => void) | undefined;
    const pendingDatesRefresh = new Promise<ApiEnvelope<PnlDatesPayload>>((_resolve, reject) => {
      rejectDatesRefresh = reject;
    });
    const getInsights = vi.fn(async () => buildPayload());
    const client = buildClient(getInsights);
    client.getFormalPnlDates = vi.fn(() => {
      dateRequestCount += 1;
      return dateRequestCount === 1 ? Promise.resolve(buildDatesPayload(DEFAULT_REPORT_DATES)) : pendingDatesRefresh;
    });
    const { queryClient } = renderPage(client);

    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(1));
    act(() => {
      void queryClient.invalidateQueries({ queryKey: ["pnl-by-business-insights", "dates", "mock"] });
    });
    await waitFor(() => expect(client.getFormalPnlDates).toHaveBeenCalledTimes(2));
    await act(async () => {
      rejectDatesRefresh?.(new Error("Request failed: /api/pnl/dates (401)"));
    });

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-access-denied"]')).toHaveTextContent(
        "报告日期目录读取权限已变更",
      );
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]')).toBeNull();
    expect(document.querySelector('[aria-label="pnl-by-business-insights-year"]')).toBeDisabled();
    expect(getInsights).toHaveBeenCalledTimes(1);
  });

  it("cancels the obsolete cutoff request and does not let it replace the selected cutoff", async () => {
    let firstSignal: AbortSignal | undefined;
    let resolveFirst: ((value: ApiEnvelope<PnlByBusinessInsightsPayload>) => void) | undefined;
    const firstRequest = new Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>((resolve) => {
      resolveFirst = resolve;
    });
    const getInsights = vi.fn((year: number, asOfDate: string, options?: { signal?: AbortSignal }) => {
      if (year === 2026 && asOfDate === "2026-06-30") {
        firstSignal = options?.signal;
        return firstRequest;
      }
      return Promise.resolve(
        buildPayload(
          {
            trace_id: "tr_pnl_business_insights_2025",
            requested_report_date: "2025-12-31",
            resolved_report_date: "2025-12-31",
            as_of_date: "2025-12-31",
          },
          { as_of_date: "2025-12-31" },
        ),
      );
    });
    renderPage(buildClient(getInsights));

    await waitFor(() => expect(firstSignal).toBeInstanceOf(AbortSignal));
    fireEvent.change(document.querySelector('[aria-label="pnl-by-business-insights-year"]')!, {
      target: { value: "2025" },
    });

    await waitFor(() => {
      expect(getInsights).toHaveBeenCalledWith(
        2025,
        "2025-12-31",
        { signal: expect.any(AbortSignal) },
      );
    });
    expect(firstSignal?.aborted).toBe(true);

    await act(async () => {
      resolveFirst?.(buildPayload({ trace_id: "tr_obsolete_cutoff" }));
    });
    await waitFor(() => {
      const status = document.querySelector('[data-testid="pnl-by-business-insights-contract-status"]');
      expect(status).toHaveTextContent("2025-12-31");
      expect(status).toHaveTextContent("tr_pnl_business_insights_2025");
      expect(status).not.toHaveTextContent("tr_obsolete_cutoff");
    });
  });

  it("renders the approved concentration, threshold, same-period drift and backend quadrant", async () => {
    renderPage(buildClient(vi.fn(async () => buildPayload())));

    const page = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-page"]');
      expect(node).toHaveTextContent("13.42%");
      return node as HTMLElement;
    });

    expect(page).toHaveTextContent("50.50%");
    expect(page).toHaveTextContent("同业存单");
    expect(page).toHaveTextContent("91.67%");
    expect(page).toHaveTextContent("至少 6 个已观测月份");
    expect(page).toHaveTextContent("2025-06-30");
    expect(page).toHaveTextContent("公募基金");
    expect(page).toHaveTextContent("-3.52pp");
    expect(document.querySelector('[data-testid="capital-efficiency-quadrant-grid"]')).not.toBeNull();
  });

  it("shows source-pending instead of a negative-FTP conclusion or insufficient observations", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, { negative_ftp_persistence: {
      ...result.negative_ftp_persistence, status: "source_pending", eligible: false, warning_row_count: 0,
      balance_quality_issues: [{ issue_id: "pending", report_date: "2025-11-20", status: "pending",
        reason: "源表日期冲突", source_file: "test.xls", source_version: "sv_test" }],
      rows: result.negative_ftp_persistence.rows.map((row) => ({
        ...row, status: "source_pending", eligible: false, warning_triggered: false,
      })),
    } }))));
    await waitFor(() => {
      const brief = document.querySelector('[data-testid="pnl-by-business-insights-decision-brief"]');
      expect(brief).toHaveTextContent("2025-11-20余额来源待核实");
      expect(brief).not.toHaveTextContent("最长连续9个月");
      expect(brief).not.toHaveTextContent("当前没有业务达到");
      const table = document.querySelector('[data-testid="pnl-by-business-insights-negative-ftp-table"]');
      expect(table).toHaveTextContent("余额来源待核实");
      expect(table).not.toHaveTextContent("观察不足");
    });
  });

  it("combines approved structure, negative-FTP and share-drift outputs into a management brief", async () => {
    renderPage(buildClient(vi.fn(async () => buildPayload())));

    const brief = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-decision-brief"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(brief).toHaveTextContent("Top3 占比 50.50%");
    expect(brief).toHaveTextContent("HHI 13.42% 用于观察集中度趋势");
    expect(brief).toHaveTextContent("同业存单：FTP后损益为负月份占比 91.67%，最长连续9个月");
    expect(brief).toHaveTextContent("当前日均份额 14.52%，较上年同期间 +6.90pp");
    expect(brief).toHaveTextContent("当前接口未返回利润影响所需输入，本页不作估算");
  });

  it("states that the negative-FTP warning includes approved manual entries and is not an all-month loss", async () => {
    const result = buildPayload().result;
    const componentEvidence = result.component_evidence.map((item) =>
      item.component === "monthly_2026"
        ? { ...item, tables_used: [...item.tables_used, "pnl_by_business_adjustments"] }
        : item,
    );
    renderPage(buildClient(vi.fn(async () => buildPayload({}, { component_evidence: componentEvidence }))));

    const brief = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-decision-brief"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(brief).toHaveTextContent("FTP后损益为负月份观察");
    expect(brief).toHaveTextContent("滚动月度口径已纳入已批准手工补录");
    expect(brief).toHaveTextContent("不表示每个月均为负，也不表示业务总损益为负");
  });

  it("warns when current and baseline YTD rule versions differ", async () => {
    const result = buildPayload().result;
    const componentEvidence = result.component_evidence.map((item) => {
      if (item.component === "current_ytd") {
        return { ...item, rule_version: "v3" };
      }
      if (item.component === "baseline_ytd") {
        return { ...item, rule_version: "v1" };
      }
      return item;
    });
    renderPage(buildClient(vi.fn(async () => buildPayload({}, { component_evidence: componentEvidence }))));

    const warning = await waitFor(() => {
      const node = document.querySelector(
        '[data-testid="pnl-by-business-insights-cross-period-rule-warning"]',
      );
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(warning).toHaveTextContent("当前 YTD 使用 v3，上年同期间使用 v1");
    expect(warning).toHaveTextContent("统一口径重算后再形成经营判断");
  });

  it("converts concentration average balance from yuan to yi", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      concentration: {
        ...result.concentration,
        total_avg_balance: "100000000",
        rows: [
          {
            row_key: "row_1",
            business_type: "业务1",
            avg_balance: "100000000",
            share_pct: "100.00",
          },
        ],
      },
    }))));

    const concentration = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(concentration).toHaveTextContent("总日均余额");
    expect(concentration).toHaveTextContent("1.00 亿元");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-concentration-table"]')).toHaveTextContent(
      "1.00",
    );

  });

  it("preserves a null concentration balance as unavailable", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      concentration: { ...result.concentration, total_avg_balance: null, rows: [] },
    }))));

    const concentration = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(concentration).toHaveTextContent("总日均余额");
    expect(concentration).toHaveTextContent("— 亿元");
  });

  it.each([
    ["non-formal", { basis: "analytical" as const, formal_use_allowed: false }],
    ["fallback", { fallback_mode: "latest_snapshot" as const, fallback_date: "2026-05-31" }],
    ["stale", { quality_flag: "stale" as const }],
    ["error", { quality_flag: "error" as const }],
    ["missing", { quality_flag: "missing" as const }],
    ["vendor unavailable", { vendor_status: "vendor_unavailable" as const }],
    ["requested cutoff mismatch", { requested_report_date: "2026-05-31" }],
    ["missing resolved cutoff", { resolved_report_date: null }],
  ])("fails closed for %s metadata", async (_label, metaOverrides) => {
    renderPage(buildClient(vi.fn(async () => buildPayload(metaOverrides))));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]')).toBeNull();
    expect(document.querySelector('[data-testid="pnl-by-business-insights-reconciliation-section"]')).toBeNull();
  });

  it("keeps the contract review visible when an unusable response also has no rows", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload(
      { basis: "analytical", formal_use_allowed: false },
      {
        concentration: { ...result.concentration, rows: [] },
        negative_ftp_persistence: { ...result.negative_ftp_persistence, rows: [] },
        share_drift: { ...result.share_drift, rows: [] },
      },
    ))));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
    expect(document.querySelector(".async-section__empty")).toBeNull();
  });

  it.each([
    ["legacy version", "v1"],
    ["missing version", undefined],
  ])("fails closed for a %s payload", async (_label, resultVersion) => {
    renderPage(buildClient(vi.fn(async () => {
      const response = buildPayload();
      const runtimeResult = { ...response.result } as Record<string, unknown>;
      if (resultVersion === undefined) {
        delete runtimeResult.result_version;
      } else {
        runtimeResult.result_version = resultVersion;
      }
      return { ...response, result: runtimeResult } as unknown as ApiEnvelope<PnlByBusinessInsightsPayload>;
    })));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
    expect(document.querySelector('[data-testid="pnl-by-business-insights-concentration-kpis"]')).toBeNull();
  });

  it("fails closed when the baseline used a fallback", async () => {
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      baseline_resolved_report_date: "2025-05-31",
      baseline_fallback_mode: "latest_snapshot",
    }))));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
  });

  it("fails closed when component evidence is stale", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      component_evidence: result.component_evidence.map((entry, index) =>
        index === 0 ? { ...entry, quality_flag: "stale" } : entry,
      ),
    }))));

    await waitFor(() => {
      expect(document.querySelector('[data-testid="pnl-by-business-insights-contract-review"]')).not.toBeNull();
    });
  });

  it("shows insufficient observation instead of formal negative-FTP values", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      negative_ftp_persistence: {
        ...result.negative_ftp_persistence,
        months_observed: 2,
        negative_ftp_month_share_pct: null,
        negative_ftp_longest_streak_months: null,
        eligible: false,
        status: "insufficient_observations",
        warning_row_count: 0,
        rows: [{
          ...result.negative_ftp_persistence.rows[0],
          months_observed: 2,
          negative_ftp_month_share_pct: null,
          negative_ftp_longest_streak_months: null,
          warning_triggered: false,
          eligible: false,
          status: "insufficient_observations",
        }],
      },
    }))));

    const table = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-negative-ftp-table"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(table).toHaveTextContent("观察不足");
    expect(table).not.toHaveTextContent("0.00%");
    expect(table).not.toHaveTextContent("0 个月");
  });

  it("does not render share drift rows when either comparison denominator is unavailable", async () => {
    const result = buildPayload().result;
    renderPage(buildClient(vi.fn(async () => buildPayload({}, {
      share_drift: {
        ...result.share_drift,
        available: false,
        availability_reason: "current_total_non_positive",
      },
    }))));

    const empty = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-share-drift-empty"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });
    expect(empty).toHaveTextContent("日均余额分母不可用");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-share-drift-table"]')).toBeNull();
  });

  it("initializes the request from validated year and cutoff query parameters", async () => {
    const getInsights = vi.fn(async () => buildPayload({}, { year: 2025, as_of_date: "2025-12-31" }));
    renderPage(
      buildClient(getInsights),
      "/pnl-by-business-insights?year=2025&as_of_date=2025-12-31",
    );

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2025,
      "2025-12-31",
      { signal: expect.any(AbortSignal) },
    ));
  });

  it("uses the latest available formal cutoff instead of today's unavailable date", async () => {
    vi.setSystemTime(new Date("2026-08-11T12:00:00Z"));
    const getInsights = vi.fn(async () => buildPayload());

    renderPage(buildClient(getInsights, ["2026-07-31", "2026-06-30"]));

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-07-31",
      { signal: expect.any(AbortSignal) },
    ));
    expect(getInsights).not.toHaveBeenCalledWith(
      2026,
      "2026-08-11",
      { signal: expect.any(AbortSignal) },
    );
  });

  it("rejects non-canonical query parameters instead of sending them to the formal endpoint", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    renderPage(
      buildClient(getInsights),
      "/pnl-by-business-insights?year=02025&as_of_date=2025-12-31",
    );

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(
      2026,
      "2026-06-30",
      { signal: expect.any(AbortSignal) },
    ));
    expect(getInsights).not.toHaveBeenCalledWith(
      2025,
      "2025-12-31",
      { signal: expect.any(AbortSignal) },
    );
  });

  it("keeps untraced history in a separate data-quality diagnostic section", async () => {
    renderPage(buildClient(vi.fn(async () => buildPayload())));

    const section = await waitFor(() => {
      const node = document.querySelector('[data-testid="pnl-by-business-insights-reconciliation-section"]');
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(section).toHaveTextContent("数据链路诊断");
    expect(section).toHaveTextContent("非业务结论");
    expect(section).toHaveTextContent('"data":[6.79]');
  });

  it("shows an explicit unavailable state when the diagnostic source cannot be read", async () => {
    renderPage(
      buildClient(
        vi.fn(async () =>
          buildPayload({}, {
            reconciliation_diagnostics: {
              as_of_date: "2026-06-30",
              lookback_months: 12,
              available: false,
              availability_reason: "source_unavailable",
              rows: [],
            },
          }),
        ),
      ),
    );

    const state = await waitFor(() => {
      const node = document.querySelector(
        '[data-testid="pnl-by-business-insights-reconciliation-unavailable"]',
      );
      expect(node).not.toBeNull();
      return node as HTMLElement;
    });

    expect(state).toHaveTextContent("诊断源暂不可用");
  });
});
