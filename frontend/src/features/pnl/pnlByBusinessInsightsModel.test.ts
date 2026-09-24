import { describe, expect, it } from "vitest";

import type { ApiEnvelope, PnlByBusinessInsightsPayload, ResultMeta } from "../../api/contracts";
import { buildPnlByBusinessInsightsLeadershipModel } from "./pnlByBusinessInsightsModel";

const meta: ResultMeta = {
  trace_id: "tr_insights",
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
  tables_used: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
  generated_at: "2026-07-15T00:00:00Z",
};

const payload: PnlByBusinessInsightsPayload = {
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
    rows: [],
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
    eligible_row_count: 12,
    total_avg_balance: "3367.49",
    available: true,
    scale_share_median_pct: "6.38",
    ftp_net_annualized_yield_median_pct: "1.116224",
    rows: [
      {
        row_key: "asset_zqtz_policy_financial_bond",
        business_type: "政策性金融债",
        avg_balance: "659.13",
        scale_share_pct: "19.57",
        ftp_net_annualized_yield_pct: "0.690000",
        quadrant_key: "LARGE_LOW",
      },
    ],
  },
  reconciliation_diagnostics: {
    as_of_date: "2026-06-30",
    lookback_months: 12,
    available: false,
    availability_reason: "no_observations",
    rows: [],
  },
};

function envelope(
  metaOverrides: Partial<ResultMeta> = {},
  resultOverrides: Partial<PnlByBusinessInsightsPayload> = {},
): ApiEnvelope<PnlByBusinessInsightsPayload> {
  return {
    result_meta: { ...meta, ...metaOverrides },
    result: { ...payload, ...resultOverrides },
  };
}

describe("buildPnlByBusinessInsightsLeadershipModel", () => {
  it("keeps upstream warning visible but returns four approved leadership facts", () => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope(),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("ready");
    expect(model.qualityWarning).toBe(true);
    expect(model.items).toHaveLength(4);
    expect(model.items[0].value).toContain("13.42%");
    expect(model.items[0].value).toContain("Top3 50.50%");
    expect(model.items[1].value).toContain("同业存单 91.67%");
    expect(model.items[1].rowKey).toBe("asset_zqtz_interbank_cd");
    expect(model.items[2].value).toContain("公募基金 -3.52pp");
    expect(model.items[3].value).toContain("政策性金融债");
    expect(model.items[3].value).toContain("19.57%");
  });

  it("fails closed when the result is not approved for formal use", () => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope({ basis: "analytical", formal_use_allowed: false }),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
    expect(model.reason).toContain("正式口径");
  });

  it("fails closed on fallback or a cutoff mismatch", () => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope({
        fallback_mode: "latest_snapshot",
        fallback_date: "2026-05-31",
        resolved_report_date: "2026-05-31",
        as_of_date: "2026-05-31",
      }),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
    expect(model.reason).toContain("截止日");
  });

  it.each([
    ["requested cutoff mismatch", { requested_report_date: "2026-05-31" }],
    ["missing resolved cutoff", { resolved_report_date: null }],
  ])("fails closed on %s", (_label, metaOverrides) => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope(metaOverrides),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
  });

  it.each([
    ["error quality", { quality_flag: "error" as const }],
    ["stale quality", { quality_flag: "stale" as const }],
    ["missing quality", { quality_flag: "missing" as const }],
    ["stale vendor", { vendor_status: "vendor_stale" as const }],
    ["unavailable vendor", { vendor_status: "vendor_unavailable" as const }],
  ])("fails closed on %s", (_label, metaOverrides) => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope(metaOverrides),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
  });

  it.each([
    ["legacy version", "v1"],
    ["missing version", undefined],
  ])("fails closed on a %s payload", (_label, resultVersion) => {
    const response = envelope();
    const runtimeResult = { ...response.result } as Record<string, unknown>;
    if (resultVersion === undefined) {
      delete runtimeResult.result_version;
    } else {
      runtimeResult.result_version = resultVersion;
    }

    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: { ...response, result: runtimeResult } as unknown as ApiEnvelope<PnlByBusinessInsightsPayload>,
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
  });

  it.each([
    [
      "baseline fallback",
      {
        baseline_resolved_report_date: "2025-05-31",
        baseline_fallback_mode: "latest_snapshot" as const,
      },
    ],
    [
      "component fallback",
      {
        component_evidence: payload.component_evidence.map((entry, index) =>
          index === 0 ? { ...entry, fallback_mode: "latest_snapshot" as const } : entry,
        ),
      },
    ],
    [
      "stale component",
      {
        component_evidence: payload.component_evidence.map((entry, index) =>
          index === 0 ? { ...entry, quality_flag: "stale" as const } : entry,
        ),
      },
    ],
    [
      "unavailable component vendor",
      {
        component_evidence: payload.component_evidence.map((entry, index) =>
          index === 0 ? { ...entry, vendor_status: "vendor_unavailable" as const } : entry,
        ),
      },
    ],
    [
      "component cutoff mismatch",
      {
        component_evidence: payload.component_evidence.map((entry, index) =>
          index === 0 ? { ...entry, resolved_report_date: "2026-05-31" } : entry,
        ),
      },
    ],
    [
      "unadmitted formal source",
      {
        component_evidence: payload.component_evidence.map((entry, index) =>
          index === 0
            ? {
                ...entry,
                formal_source_admitted: false,
                admission_reason: "nonformal_source_tables" as const,
              }
            : entry,
        ),
      },
    ],
    [
      "current component aligned to the wrong cutoff",
      {
        component_evidence: payload.component_evidence.map((entry) =>
          entry.component === "current_ytd"
            ? {
                ...entry,
                requested_report_date: "2026-05-31",
                resolved_report_date: "2026-05-31",
              }
            : entry,
        ),
      },
    ],
    [
      "baseline component aligned to the wrong cutoff",
      {
        component_evidence: payload.component_evidence.map((entry) =>
          entry.component === "baseline_ytd"
            ? {
                ...entry,
                requested_report_date: "2025-05-31",
                resolved_report_date: "2025-05-31",
              }
            : entry,
        ),
      },
    ],
    ["missing required component", { component_evidence: payload.component_evidence.slice(1) }],
    [
      "missing monthly component",
      {
        component_evidence: payload.component_evidence.filter(
          (entry) => entry.component !== "monthly_2025",
        ),
      },
    ],
  ])("fails closed on %s", (_label, resultOverrides) => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope({}, resultOverrides),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
  });

  it("fails closed without throwing when component evidence is missing at runtime", () => {
    const response = envelope();
    const runtimeResult = { ...response.result } as Record<string, unknown>;
    delete runtimeResult.component_evidence;

    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: { ...response, result: runtimeResult } as unknown as ApiEnvelope<PnlByBusinessInsightsPayload>,
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("review");
    expect(model.items).toEqual([]);
  });

  it("reports insufficient observation instead of claiming there is no negative-FTP warning", () => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: envelope({}, {
        negative_ftp_persistence: {
          ...payload.negative_ftp_persistence,
          months_observed: 2,
          negative_ftp_month_share_pct: null,
          negative_ftp_longest_streak_months: null,
          eligible: false,
          status: "insufficient_observations",
          warning_row_count: 0,
          rows: [
            {
              ...payload.negative_ftp_persistence.rows[0],
              months_observed: 2,
              negative_ftp_month_share_pct: null,
              negative_ftp_longest_streak_months: null,
              warning_triggered: false,
              eligible: false,
              status: "insufficient_observations",
            },
          ],
        },
      }),
      isLoading: false,
      isError: false,
    });

    expect(model.status).toBe("ready");
    expect(model.items[1].value).toContain("观察期不足");
    expect(model.items[1].value).not.toContain("未发现达到预警阈值");
  });

  it("keeps the strictly-positive plus prefix boundary on share-drift pp labels", () => {
    const driftEnvelope = (driftPp: string) =>
      envelope({}, {
        share_drift: {
          ...payload.share_drift,
          rows: [{ ...payload.share_drift.rows[0], drift_pp: driftPp }],
        },
      });

    const positive = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: driftEnvelope("1.25"),
      isLoading: false,
      isError: false,
    });
    expect(positive.status).toBe("ready");
    expect(positive.items[2].value).toContain("公募基金 +1.25pp");

    const zero = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: driftEnvelope("0.00"),
      isLoading: false,
      isError: false,
    });
    expect(zero.items[2].value).toContain("公募基金 0.00pp");
    expect(zero.items[2].value).not.toContain("+");
  });

  it("keeps an insights request failure separate from the main PnL result", () => {
    const model = buildPnlByBusinessInsightsLeadershipModel({
      requestedDate: "2026-06-30",
      envelope: undefined,
      isLoading: false,
      isError: true,
    });

    expect(model.status).toBe("review");
    expect(model.reason).toContain("读取失败");
  });
});
