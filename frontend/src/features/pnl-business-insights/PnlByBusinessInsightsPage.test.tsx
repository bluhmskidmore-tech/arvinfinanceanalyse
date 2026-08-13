import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="pnl-by-business-insights-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../../api/client";
import type { ApiEnvelope, PnlByBusinessInsightsPayload, PnlDatesPayload, ResultMeta } from "../../api/contracts";
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

function buildDatesPayload(reportDates: string[]): ApiEnvelope<PnlDatesPayload> {
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
      formal_fi_report_dates: reportDates,
      nonstd_bridge_report_dates: reportDates,
    },
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
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <PnlByBusinessInsightsPage />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
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

    expect(getInsights).toHaveBeenCalledWith(2026, "2026-06-30");
    expect(candidateSpy).not.toHaveBeenCalled();
    expect(ytdSpy).not.toHaveBeenCalled();
    expect(status).toHaveTextContent("正式口径");
    expect(status).toHaveTextContent("质量 warning");
    expect(status).toHaveTextContent("降级 none");
    expect(status).toHaveTextContent("tr_pnl_business_insights_test");
    expect(document.querySelector('[data-testid="pnl-by-business-insights-disclaimer"]')).toBeNull();
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

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(2025, "2025-12-31"));
  });

  it("uses the latest available formal cutoff instead of today's unavailable date", async () => {
    vi.setSystemTime(new Date("2026-08-11T12:00:00Z"));
    const getInsights = vi.fn(async () => buildPayload());

    renderPage(buildClient(getInsights, ["2026-07-31", "2026-06-30"]));

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(2026, "2026-07-31"));
    expect(getInsights).not.toHaveBeenCalledWith(2026, "2026-08-11");
  });

  it("rejects non-canonical query parameters instead of sending them to the formal endpoint", async () => {
    const getInsights = vi.fn(async () => buildPayload());
    renderPage(
      buildClient(getInsights),
      "/pnl-by-business-insights?year=02025&as_of_date=2025-12-31",
    );

    await waitFor(() => expect(getInsights).toHaveBeenCalledWith(2026, "2026-06-30"));
    expect(getInsights).not.toHaveBeenCalledWith(2025, "2025-12-31");
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
