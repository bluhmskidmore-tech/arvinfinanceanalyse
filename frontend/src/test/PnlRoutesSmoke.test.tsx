import { fireEvent, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

const { downloadPnlByBusinessExcelMock } = vi.hoisted(() => ({
  downloadPnlByBusinessExcelMock: vi.fn(),
}));

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-routes-echarts-stub" />,
}));

vi.mock("../features/pnl/pnlByBusinessExport", () => ({
  downloadPnlByBusinessExcel: downloadPnlByBusinessExcelMock,
}));

import { createApiClient, type ApiClient } from "../api/client";
import type {
  Numeric,
  PnlByBusinessAnalysisDimension,
  PnlBridgePayload,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessPayload,
  PnlByBusinessYtdPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  PnlV1DataPayload,
  PnlYearlyBusinessSummaryPayload,
  ResultMeta,
} from "../api/contracts";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const YIELD_ANALYSIS_SOURCE_PATHS = [
  resolve(process.cwd(), "src/features/pnl/YieldAnalysisPage.tsx"),
  resolve(process.cwd(), "src/features/pnl/yieldAnalysis/yieldAnalysis.css"),
];

function bridgeYuan(raw: number, display: string, signAware = true): Numeric {
  return { raw, unit: "yuan", display, precision: 2, sign_aware: signAware };
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_route_smoke",
    vendor_version: "vv_none",
    rule_version: "rv_route_smoke",
    cache_version: "cv_route_smoke",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function buildPnlClient(): ApiClient {
  const base = createApiClient({ mode: "real" });
  const dates: PnlDatesPayload = {
    report_dates: ["2025-12-31", "2025-11-30"],
    formal_fi_report_dates: ["2025-12-31", "2025-11-30"],
    nonstd_bridge_report_dates: ["2025-12-31", "2025-11-30"],
  };
  const overview: PnlOverviewPayload = {
    report_date: "2025-12-31",
    formal_fi_row_count: 1,
    nonstd_bridge_row_count: 1,
    interest_income_514: "10.00",
    fair_value_change_516: "1.00",
    capital_gain_517: "2.00",
    manual_adjustment: "0.00",
    total_pnl: "13.00",
  };
  const data: PnlV1DataPayload = {
    report_date: "2025-12-31",
    source_tables: ["data_input/pnl"],
    rows: [
      {
        report_date: "2025-12-31",
        source: "FI",
        asset_code: "240001.IB",
        bond_name: "Route Bond",
        portfolio: "Route FI",
        asset_type: "T",
        asset_class: "bond",
        market_value: "1000000.00",
        interest_income: "100000.00",
        fair_value_change: "10000.00",
        capital_gain: "20000.00",
        total_pnl: "130000.00",
        source_version: "sv_route_smoke",
        trace_id: "tr_route_fi",
      },
    ],
  };
  const bridge: PnlBridgePayload = {
    report_date: "2025-12-31",
    warnings: [],
    summary: {
      row_count: 1,
      ok_count: 1,
      warning_count: 0,
      error_count: 0,
      total_beginning_dirty_mv: bridgeYuan(100, "100.00", false),
      total_ending_dirty_mv: bridgeYuan(110, "110.00", false),
      total_carry: bridgeYuan(1, "1.00"),
      total_roll_down: bridgeYuan(0, "0.00"),
      total_treasury_curve: bridgeYuan(0, "0.00"),
      total_credit_spread: bridgeYuan(0, "0.00"),
      total_fx_translation: bridgeYuan(0, "0.00"),
      total_realized_trading: bridgeYuan(2, "2.00"),
      total_unrealized_fv: bridgeYuan(3, "3.00"),
      total_manual_adjustment: bridgeYuan(0, "0.00"),
      total_explained_pnl: bridgeYuan(6, "6.00"),
      total_actual_pnl: bridgeYuan(6, "6.00"),
      total_residual: bridgeYuan(0, "0.00"),
      quality_flag: "ok",
    },
    rows: [
      {
        report_date: "2025-12-31",
        instrument_code: "240001.IB",
        portfolio_name: "Route Bridge",
        accounting_basis: "FVTPL",
        carry: bridgeYuan(1, "1.00"),
        roll_down: bridgeYuan(0, "0.00"),
        treasury_curve: bridgeYuan(0, "0.00"),
        credit_spread: bridgeYuan(0, "0.00"),
        fx_translation: bridgeYuan(0, "0.00"),
        realized_trading: bridgeYuan(2, "2.00"),
        unrealized_fv: bridgeYuan(3, "3.00"),
        manual_adjustment: bridgeYuan(0, "0.00"),
        explained_pnl: bridgeYuan(6, "6.00"),
        actual_pnl: bridgeYuan(6, "6.00"),
        residual: bridgeYuan(0, "0.00"),
        residual_ratio: { raw: 0, unit: "ratio", display: "0.00", precision: 2, sign_aware: true },
        quality_flag: "ok",
      },
    ],
  };
  const byBusiness: PnlByBusinessPayload = {
    report_date: "2025-12-31",
    source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
    summary: {
      business_count: 1,
      total_pnl: "13.00",
      total_scale_amount: "100000000.00",
      traced_pnl_row_count: 1,
      untraced_pnl_row_count: 0,
    },
    rows: [
      {
        report_date: "2025-12-31",
        business_type_primary: "政策性金融债",
        business_type: "政策性金融债",
        currency_basis: "CNY",
        interest_income_514: "10.00",
        fair_value_change_516: "1.00",
        capital_gain_517: "2.00",
        manual_adjustment: "0.00",
        total_pnl: "13.00",
        scale_amount: "100000000.00",
        yield_pct: "0.000013",
        pnl_row_count: 1,
        balance_row_count: 1,
      },
    ],
  };
  const byBusinessYtd: PnlByBusinessYtdPayload = {
    year: 2025,
    period_type: "yearly",
    period_label: "2025年12月累计",
    period_start_date: "2025-12-01",
    period_end_date: "2025-12-31",
    total_pnl: "130000.00",
    source_tables: ["data_input/pnl", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
    items: [
      {
        row_key: "asset_zqtz_policy_financial_bond",
        sort_order: 66,
        business_type: "政策性金融债",
        interest_income: "100000.00",
        fair_value_change: "10000.00",
        capital_gain: "20000.00",
        manual_adjustment: "0.00",
        total_pnl: "130000.00",
        current_balance: "100000000.00",
        balance_yield_pct: "0.0013",
        source_kind: "zqtz",
        source_note: "ZQTZ_ASSET_BOND_ROWS",
        proportion: "1.000000",
        assets_count: 1,
      },
      {
        row_key: "asset_zqtz_detail_local_currency_special_account_cost",
        sort_order: 88,
        business_type: "其中：本币专户（成本法）",
        interest_income: "50000.00",
        fair_value_change: "0.00",
        capital_gain: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "50000.00",
        current_balance: "50000000.00",
        balance_yield_pct: "0.001",
        source_kind: "zqtz",
        source_note: "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
        proportion: "0.384615",
        assets_count: 7,
      },
    ],
  };
  const byBusinessMonthly: PnlByBusinessMonthlyPayload = {
    year: 2025,
    as_of_date: "2025-12-31",
    source_tables: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
    months: [
      {
        month_key: "2025-11",
        period_start_date: "2025-11-01",
        period_end_date: "2025-11-30",
        calendar_days: 30,
        summary: {
          interest_income: "80000.00",
          fair_value_change: "5000.00",
          capital_gain: "10000.00",
          manual_adjustment: "0.00",
          total_pnl: "95000.00",
          avg_balance: "90000000.00",
          current_balance: "92000000.00",
          annualized_yield_pct: "1.284259",
          ftp_rate_pct: "1.600000",
          ftp_cost: "118356.16",
          ftp_net_pnl: "-23356.16",
          ftp_net_annualized_yield_pct: "-0.315741",
          asset_count: 1,
        },
        items: [
          {
            row_key: "asset_zqtz_policy_financial_bond",
            sort_order: 66,
            business_type: "政策性金融债",
            interest_income: "80000.00",
            fair_value_change: "5000.00",
            capital_gain: "10000.00",
            manual_adjustment: "0.00",
            total_pnl: "95000.00",
            avg_balance: "90000000.00",
            current_balance: "92000000.00",
            annualized_yield_pct: "1.284259",
            ftp_rate_pct: "1.600000",
            ftp_cost: "118356.16",
            ftp_net_pnl: "-23356.16",
            ftp_net_annualized_yield_pct: "-0.315741",
            proportion: "1.000000",
            asset_count: 1,
            source_note: "ZQTZ_ASSET_BOND_ROWS",
          },
        ],
      },
      {
        month_key: "2025-12",
        period_start_date: "2025-12-01",
        period_end_date: "2025-12-31",
        calendar_days: 31,
        summary: {
          interest_income: "100000.00",
          fair_value_change: "10000.00",
          capital_gain: "20000.00",
          manual_adjustment: "0.00",
          total_pnl: "130000.00",
          avg_balance: "100000000.00",
          current_balance: "100000000.00",
          annualized_yield_pct: "1.530645",
          ftp_rate_pct: "1.600000",
          ftp_cost: "135890.41",
          ftp_net_pnl: "-5890.41",
          ftp_net_annualized_yield_pct: "-0.069355",
          asset_count: 1,
        },
        items: [
          {
            row_key: "asset_zqtz_policy_financial_bond",
            sort_order: 66,
            business_type: "政策性金融债",
            interest_income: "100000.00",
            fair_value_change: "10000.00",
            capital_gain: "20000.00",
            manual_adjustment: "0.00",
            total_pnl: "130000.00",
            avg_balance: "100000000.00",
            current_balance: "100000000.00",
            annualized_yield_pct: "1.530645",
            ftp_rate_pct: "1.600000",
            ftp_cost: "135890.41",
            ftp_net_pnl: "-5890.41",
            ftp_net_annualized_yield_pct: "-0.069355",
            proportion: "1.000000",
            asset_count: 1,
            source_note: "ZQTZ_ASSET_BOND_ROWS",
          },
          {
            row_key: "asset_zqtz_detail_local_currency_special_account_cost",
            sort_order: 88,
            business_type: "其中：本币专户（成本法）",
            interest_income: "50000.00",
            fair_value_change: "0.00",
            capital_gain: "0.00",
            manual_adjustment: "0.00",
            total_pnl: "50000.00",
            avg_balance: "50000000.00",
            current_balance: "50000000.00",
            annualized_yield_pct: "1.177419",
            ftp_rate_pct: "1.600000",
            ftp_cost: "67945.21",
            ftp_net_pnl: "-17945.21",
            ftp_net_annualized_yield_pct: "-0.422581",
            proportion: "0.384615",
            asset_count: 7,
            source_note: "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
          },
        ],
      },
    ],
  };
  const byBusinessAnalysis: PnlByBusinessAnalysisPayload = {
    year: 2025,
    as_of_date: "2025-12-31",
    business_key: "asset_zqtz_policy_financial_bond",
    dimension: "monthly",
    period_start_date: "2025-12-01",
    period_end_date: "2025-12-31",
    source_tables: [
      "fact_formal_pnl_fi",
      "fact_nonstd_pnl_bridge",
      "fact_formal_zqtz_balance_daily",
      "ZQTZ_ASSET_BOND_ROWS",
    ],
    rows: [
      {
        dimension_key: "2025-12-31",
        dimension_label: "2025-12-31",
        interest_income: "100000.00",
        fair_value_change: "10000.00",
        capital_gain: "20000.00",
        manual_adjustment: "0.00",
        total_pnl: "130000.00",
        avg_balance: "100000000.00",
        current_balance: "100000000.00",
        annualized_yield_pct: "1.530645",
        ftp_rate_pct: "1.600000",
        ftp_cost: "135890.41",
        ftp_net_pnl: "-5890.41",
        ftp_net_annualized_yield_pct: "-0.069355",
        asset_count: 1,
      },
    ],
  };
  const byBusinessBondBucketAnalysis: PnlByBusinessAnalysisPayload = {
    ...byBusinessAnalysis,
    business_key: null,
    dimension: "bond_bucket",
    rows: [
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "rate_bond",
        dimension_label: "利率债",
      },
    ],
  };
  const byBusinessBondBucketMonthlyAnalysis: PnlByBusinessAnalysisPayload = {
    ...byBusinessAnalysis,
    business_key: null,
    dimension: "bond_bucket_monthly",
    rows: [
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "2025-12-31::rate_bond",
        dimension_label: "2025-12-31 利率债",
      },
    ],
  };
  const byBusinessNegativeInstrumentAnalysis: PnlByBusinessAnalysisPayload = {
    ...byBusinessAnalysis,
    dimension: "instrument",
    rows: [
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "240001.IB",
        dimension_label: "240001.IB 负FTP资产",
        total_pnl: "130000.00",
        avg_balance: "100000000.00",
        ftp_cost: "135890.41",
        ftp_net_pnl: "-5890.41",
        ftp_net_annualized_yield_pct: "-0.069355",
      },
    ],
  };
  const yearlyBusiness: PnlYearlyBusinessSummaryPayload = {
    year: 2025,
    source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
    rows: [
      {
        year: 2025,
        report_month: "2025-12",
        report_date: "2025-12-31",
        business_type_primary: "政策性金融债",
        business_type: "政策性金融债",
        currency_basis: "CNY",
        total_pnl: "13.00",
        scale_amount: "100000000.00",
        yield_pct: "0.000013",
        pnl_row_count: 1,
      },
    ],
  };

  return {
    ...base,
    getLiabilityYieldMetrics: vi.fn(async () => ({
      report_date: "2025-12-31",
      kpi: {
        asset_yield: null,
        liability_cost: null,
        market_liability_cost: null,
        nim: null,
      },
      history: [],
      scatter: [],
    })),
    getYieldByPeriod: vi.fn(async () => ({
      year: 2025,
      period_type: "monthly",
      periods: [],
    })),
    getFormalPnlDates: vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_route_dates"),
      result: dates,
    })),
    getFormalPnlOverview: vi.fn(async () => ({
      result_meta: buildMeta("pnl.overview", "tr_route_overview"),
      result: overview,
    })),
    getPnlV1Data: vi.fn(async () => ({
      result_meta: buildMeta("pnl.v1_data", "tr_route_data"),
      result: data,
    })),
    getPnlBridge: vi.fn(async () => ({
      result_meta: buildMeta("pnl.bridge", "tr_route_bridge"),
      result: bridge,
    })),
    getPnlByBusiness: vi.fn(async () => ({
      result_meta: buildMeta("pnl.by_business", "tr_route_business"),
      result: byBusiness,
    })),
    getPnlByBusinessYtd: vi.fn(async (year: number, asOfDate?: string) => ({
      result_meta: buildMeta("pnl.by_business_ytd", "tr_route_business_ytd"),
      result: {
        ...byBusinessYtd,
        year,
        period_label: `${year}年${(asOfDate ?? "2025-12-31").slice(5, 7)}月累计`,
        period_start_date: `${year}-${(asOfDate ?? "2025-12-31").slice(5, 7)}-01`,
        period_end_date: asOfDate ?? byBusinessYtd.period_end_date,
      },
    })),
    getPnlByBusinessMonthly: vi.fn(async (year: number, asOfDate?: string) => ({
      result_meta: buildMeta("pnl.by_business_monthly", "tr_route_business_monthly"),
      result: {
        ...byBusinessMonthly,
        year,
        as_of_date: asOfDate ?? "2025-12-31",
        months: byBusinessMonthly.months
          .filter((month) => month.period_end_date <= (asOfDate ?? "2025-12-31"))
          .map((month) => ({
            ...month,
            month_key: `${year}-${month.month_key.slice(5, 7)}`,
            period_start_date: `${year}-${month.month_key.slice(5, 7)}-01`,
          })),
      },
    })),
    getPnlByBusinessAnalysis: vi.fn(
      async (options: {
        year: number;
        asOfDate?: string;
        businessKey?: string;
        dimension: PnlByBusinessAnalysisDimension;
      }) => ({
      result_meta: buildMeta("pnl.by_business_analysis", "tr_route_business_analysis"),
      result: {
        ...(options.dimension === "bond_bucket"
          ? byBusinessBondBucketAnalysis
          : options.dimension === "bond_bucket_monthly"
            ? byBusinessBondBucketMonthlyAnalysis
            : options.dimension === "instrument"
              ? byBusinessNegativeInstrumentAnalysis
              : byBusinessAnalysis),
        year: options.year,
        as_of_date: options.asOfDate ?? "2025-12-31",
        period_start_date: `${options.year}-${(options.asOfDate ?? "2025-12-31").slice(5, 7)}-01`,
        period_end_date: options.asOfDate ?? "2025-12-31",
      },
    })),
    getPnlByBusinessManualAdjustments: vi.fn(async (reportDate: string) => ({
      report_date: reportDate,
      adjustment_count: 1,
      event_total: 2,
      adjustments: [
        {
          adjustment_id: "pba-route-smoke-1",
          event_type: "edited",
          created_at: "2026-04-12T08:30:00Z",
          stream: "pnl_by_business_adjustments",
          report_date: reportDate,
          row_key: "asset_zqtz_policy_financial_bond",
          business_type: "政策性金融债",
          operator: "DELTA",
          approval_status: "approved",
          manual_adjustment: "2500.00",
          reason: "复核后补录",
        },
      ],
      events: [
        {
          adjustment_id: "pba-route-smoke-1",
          event_type: "edited",
          created_at: "2026-04-12T08:30:00Z",
          stream: "pnl_by_business_adjustments",
          report_date: reportDate,
          row_key: "asset_zqtz_policy_financial_bond",
          business_type: "政策性金融债",
          operator: "DELTA",
          approval_status: "approved",
          manual_adjustment: "2500.00",
          reason: "复核后补录",
        },
        {
          adjustment_id: "pba-route-smoke-1",
          event_type: "created",
          created_at: "2026-04-12T08:00:00Z",
          stream: "pnl_by_business_adjustments",
          report_date: reportDate,
          row_key: "asset_zqtz_policy_financial_bond",
          business_type: "政策性金融债",
          operator: "DELTA",
          approval_status: "approved",
          manual_adjustment: "2000.00",
          reason: "初始补录",
        },
      ],
    })),
    createPnlByBusinessManualAdjustment: vi.fn(async (payload) => ({
      adjustment_id: "pba-route-smoke-created",
      event_type: "created",
      created_at: "2026-04-12T09:00:00Z",
      stream: "pnl_by_business_adjustments",
      business_type: payload.business_type ?? "",
      reason: payload.reason ?? "",
      ...payload,
    })),
    updatePnlByBusinessManualAdjustment: vi.fn(async (adjustmentId, payload) => ({
      adjustment_id: adjustmentId,
      event_type: "edited",
      created_at: "2026-04-12T09:00:00Z",
      stream: "pnl_by_business_adjustments",
      business_type: payload.business_type ?? "",
      reason: payload.reason ?? "",
      ...payload,
    })),
    revokePnlByBusinessManualAdjustment: vi.fn(async (adjustmentId) => ({
      adjustment_id: adjustmentId,
      event_type: "revoked",
      created_at: "2026-04-12T09:00:00Z",
      stream: "pnl_by_business_adjustments",
      report_date: "2025-12-31",
      row_key: "asset_zqtz_policy_financial_bond",
      business_type: "政策性金融债",
      operator: "DELTA",
      approval_status: "rejected",
      manual_adjustment: "2500.00",
      reason: "撤销",
    })),
    restorePnlByBusinessManualAdjustment: vi.fn(async (adjustmentId) => ({
      adjustment_id: adjustmentId,
      event_type: "restored",
      created_at: "2026-04-12T09:00:00Z",
      stream: "pnl_by_business_adjustments",
      report_date: "2025-12-31",
      row_key: "asset_zqtz_policy_financial_bond",
      business_type: "政策性金融债",
      operator: "DELTA",
      approval_status: "approved",
      manual_adjustment: "2500.00",
      reason: "恢复",
    })),
    getPnlYearlyBusinessSummary: vi.fn(async () => ({
      result_meta: buildMeta("pnl.yearly_summary", "tr_route_business_year"),
      result: yearlyBusiness,
    })),
    getAdbComparison: vi.fn(async (_startDate: string, _endDate: string) => ({
      report_date: _endDate,
      start_date: _startDate,
      end_date: _endDate,
      calendar_days_inclusive: 365,
      adb_denominator_basis: "snapshot_calendar" as const,
      num_days: 365,
      simulated: false,
      total_spot_assets: 0,
      total_avg_assets: 0,
      total_spot_liabilities: 0,
      total_avg_liabilities: 0,
      total_avg_interbank_assets: 0,
      total_avg_interbank_liabilities: 0,
      asset_yield: null,
      liability_cost: null,
      net_interest_margin: null,
      assets_breakdown: [
        {
          category: "政策性金融债",
          spot_balance: 100_000_000,
          avg_balance: 100_000_000,
          proportion: 100,
          weighted_rate: null,
        },
      ],
      liabilities_breakdown: [],
    })),
  };
}

describe("pnl routed pages smoke", () => {
  it("keeps /pnl yield analysis colors on the homepage blue-gray token family", () => {
    const source = YIELD_ANALYSIS_SOURCE_PATHS.map((path) => readFileSync(path, "utf8")).join("\n");

    expect(source).not.toMatch(/moss-color-warm-|designTokens\.color\.warm/);
    expect(source).not.toMatch(/rgba\((76, 58, 44|255, 253, 249)/);
    expect(source).not.toMatch(/letter-spacing:\s*-/);
    expect(source).toContain("designTokens.color.primary[600]");
    expect(source).toContain("designTokens.color.info[600]");
    expect(source).toContain("designTokens.color.success[600]");
    expect(source).toContain("var(--moss-color-primary-600)");
    expect(source).toContain("var(--moss-color-info-50)");
  });

  it("renders the real /pnl route surface through workbench routes", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/pnl"], { client: buildPnlClient() });

    expect(await screen.findByTestId("yield-analysis-page")).toBeInTheDocument();
    expect(await screen.findByTestId("yield-analysis-pnl-toolbar")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "收益分析", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("Performance")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("选择报表月份")).toHaveValue("2025-12-31");
    });
    await waitFor(() => {
      expect(screen.getByText("按维度排行（点击可筛选）")).toBeInTheDocument();
    });
    const pnlReadout = await screen.findByTestId("yield-analysis-pnl-readout");
    expect(pnlReadout).toHaveTextContent("筛选后合计损益");
    expect(pnlReadout).toHaveTextContent("+13.00 万");
    expect(pnlReadout).toHaveTextContent("主要贡献组合：Route FI");
    expect(pnlReadout).toHaveTextContent("来源结构");
    expect(pnlReadout).toHaveTextContent("1 标准 / 0 非标");
    await waitFor(() => {
      expect(screen.getByText("240001.IB")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: "收益总览" }));

    expect(await screen.findByText("静态资产收益率")).toBeInTheDocument();
    expect(screen.getByText("市场负债成本（NIM 分母）")).toBeInTheDocument();
    expect(screen.getByText("静态 NIM")).toBeInTheDocument();
    expect(screen.getAllByText(/剔除无到期日投资/).length).toBeGreaterThan(0);
    expect(screen.getByText(/日均分析页使用区间日均分母/)).toBeInTheDocument();
  });

  it("renders the real /pnl-bridge route surface through workbench routes", async () => {
    renderWorkbenchApp(["/pnl-bridge"], { client: buildPnlClient() });

    expect(await screen.findByTestId("pnl-bridge-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-bridge-report-date")).toHaveValue("2025-12-31");
    });
    expect(await screen.findByTestId("pnl-bridge-refresh-button")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-bridge-result-meta-panel")).toHaveTextContent("tr_route_bridge");

    await waitFor(() => {
      expect(screen.getByTestId("pnl-bridge-summary-cards")).toHaveTextContent("6.00");
      expect(screen.getByTestId("pnl-bridge-detail-table")).toHaveTextContent("240001.IB");
    });
  });

  it("renders the real /pnl-by-business route surface through workbench routes", async () => {
    const client = buildPnlClient();
    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-report-date")).toHaveValue("2025-12-31");
    });
    expect(screen.getByLabelText("pnl-by-business-view-mode")).toHaveValue("monthly");
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    expect(client.getPnlByBusinessYtd).not.toHaveBeenCalled();
    expect(client.getPnlByBusiness).not.toHaveBeenCalled();
    expect(await screen.findByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent(
      "tr_route_business_monthly",
    );
    expect(screen.getByTestId("pnl-by-business-data-status-strip")).toHaveTextContent(
      "tr_route_business_monthly",
    );
    expect(screen.getByTestId("pnl-by-business-data-status-strip")).toHaveTextContent("2025-12-31");
    await waitFor(() => {
      expect(screen.getByText("报表月份")).toBeInTheDocument();
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("月报合计损益");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("13 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月报业务种类明细");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2 个月");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-11");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).not.toHaveTextContent(
        "其中：本币专户（成本法）",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-detail-table-2025-12")).toHaveTextContent(
        "其中：本币专户（成本法）",
      );
    });
    fireEvent.click(screen.getByRole("button", { name: /2025-11/ }));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-11")).toHaveTextContent("政策性金融债");
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    await waitFor(() => {
      expect(client.getAdbComparison).toHaveBeenCalledWith(
        "2025-12-01",
        "2025-12-31",
        expect.objectContaining({ topN: 200 }),
      );
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "monthly",
      });
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket",
      });
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket_monthly",
      });
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "instrument",
      });
    });
    expect(await screen.findByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent("tr_route_business_ytd");
    expect(screen.getByTestId("pnl-by-business-data-status-strip")).toHaveTextContent("tr_route_business_ytd");

    await waitFor(() => {
      expect(screen.getByText("分析截止日")).toBeInTheDocument();
      expect(screen.getAllByText("结果元信息 / 证据").length).toBeGreaterThan(0);
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("13 万元");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("合计损益（万元）");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("FTP后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("日均(亿元)");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("1.00");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("年化收益率");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("1.53%");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("100.00%");
      expect(screen.getByTestId("pnl-by-business-table")).not.toHaveTextContent("其中：本币专户（成本法）");
      expect(screen.getByTestId("pnl-by-business-detail-table")).toHaveTextContent("其中：本币专户（成本法）");
      expect(screen.getByTestId("pnl-by-business-table-parent-footer")).toHaveTextContent("父级汇总");
      expect(screen.getByTestId("pnl-by-business-table-parent-footer")).toHaveTextContent("13");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-analysis")).toHaveTextContent("债券四类统计");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-table")).toHaveTextContent("利率债");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-table")).toHaveTextContent("FTP成本（万元）");
      expect(screen.getByTestId("pnl-by-business-ftp-bridge")).toHaveTextContent("FTP后收益桥");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-monthly")).toHaveTextContent("四类债券月度趋势");
      expect(screen.getByTestId("pnl-by-business-negative-ftp-list")).toHaveTextContent("负FTP后收益清单");
      expect(screen.getByTestId("pnl-by-business-negative-ftp-list")).toHaveTextContent("负FTP资产");
      expect(screen.getByTestId("pnl-by-business-driver-overview")).toHaveTextContent("1.53%");
      expect(screen.getByTestId("pnl-by-business-analysis-panel")).toHaveTextContent("2025-12-31");
      expect(screen.getByTestId("pnl-by-business-analysis-table")).toHaveTextContent("1.00");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月报业务种类明细");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    fireEvent.click(screen.getByRole("button", { name: /2025-12/ }));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("手工调整（万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("-0.59");
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-report-date"), { target: { value: "2025-11-30" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-11-30");
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-11-30");
    });
    await waitFor(() => {
      expect(client.getAdbComparison).toHaveBeenCalledWith(
        "2025-11-01",
        "2025-11-30",
        expect.objectContaining({ topN: 200 }),
      );
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-11-30");
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-11-30",
        dimension: "bond_bucket",
      });
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-11-30",
        dimension: "bond_bucket_monthly",
      });
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "formal" } });
    await waitFor(() => {
      expect(client.getPnlByBusiness).toHaveBeenCalledWith("2025-11-30");
    });
    expect(await screen.findByTestId("pnl-by-business-formal-table")).toHaveTextContent("政策性金融债");
    expect(screen.getByTestId("pnl-by-business-formal-table")).toHaveTextContent("表内收益率");
    expect(screen.getByTestId("pnl-by-business-formal-table-footer")).toHaveTextContent("全表合计");
  });

  it("passes loaded /pnl-by-business data to the Excel export helper", async () => {
    downloadPnlByBusinessExcelMock.mockResolvedValue(undefined);
    const user = userEvent.setup();
    const client = buildPnlClient();
    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-12-31");
    });

    await user.click(screen.getByLabelText("pnl-by-business-export-excel"));

    await waitFor(() => {
      expect(downloadPnlByBusinessExcelMock).toHaveBeenCalledTimes(1);
    });
    expect(downloadPnlByBusinessExcelMock).toHaveBeenCalledWith(
      expect.objectContaining({
        viewMode: "monthly",
        reportDate: "2025-12-31",
        year: 2025,
        months: expect.arrayContaining([
          expect.objectContaining({ month_key: "2025-11" }),
          expect.objectContaining({ month_key: "2025-12" }),
        ]),
        ytdRows: [],
        formalRows: [],
        adjustments: [],
      }),
    );
  });

  it("passes loaded YTD /pnl-by-business analysis data to the Excel export helper", async () => {
    downloadPnlByBusinessExcelMock.mockResolvedValue(undefined);
    const user = userEvent.setup();
    const client = buildPnlClient();
    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "instrument",
      });
    });

    downloadPnlByBusinessExcelMock.mockClear();
    await user.click(screen.getByLabelText("pnl-by-business-export-excel"));

    await waitFor(() => {
      expect(downloadPnlByBusinessExcelMock).toHaveBeenCalledTimes(1);
    });
    expect(downloadPnlByBusinessExcelMock).toHaveBeenCalledWith(
      expect.objectContaining({
        viewMode: "ytd",
        reportDate: "2025-12-31",
        year: 2025,
        periodStart: "2025-12-01",
        periodEnd: "2025-12-31",
        periodLabel: "2025年12月累计",
        ytdRows: expect.arrayContaining([expect.objectContaining({ business_type: "政策性金融债" })]),
        months: expect.arrayContaining([expect.objectContaining({ month_key: "2025-12" })]),
        adjustments: expect.arrayContaining([expect.objectContaining({ reason: "复核后补录" })]),
        bondBucketRows: expect.arrayContaining([expect.objectContaining({ dimension_label: "利率债" })]),
        negativeFtpRows: expect.arrayContaining([expect.objectContaining({ dimension_label: "240001.IB 负FTP资产" })]),
        analysisDimension: "monthly",
        analysisRows: expect.arrayContaining([expect.objectContaining({ dimension_label: "2025-12-31" })]),
        selectedBusinessLabel: "政策性金融债",
      }),
    );
  });

  it("surfaces Excel export failures on /pnl-by-business", async () => {
    downloadPnlByBusinessExcelMock.mockRejectedValueOnce(new Error("writer failed"));
    const user = userEvent.setup();
    const client = buildPnlClient();
    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-12-31");
    });

    await user.click(screen.getByLabelText("pnl-by-business-export-excel"));

    expect(await screen.findByRole("alert")).toHaveTextContent("writer failed");
  });

  it("records and displays manual adjustment audit history on /pnl-by-business", async () => {
    const user = userEvent.setup();
    const client = buildPnlClient();
    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessManualAdjustments).toHaveBeenCalledWith("2025-12-31");
    });

    const adjustmentPanel = await screen.findByTestId("pnl-by-business-manual-adjustments");
    expect(adjustmentPanel).toHaveTextContent("手工调整");
    expect(adjustmentPanel).toHaveTextContent("复核后补录");
    expect(adjustmentPanel).toHaveTextContent("历史事件");
    expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("手工调整（万元）");

    await user.clear(screen.getByLabelText("pnl-by-business-adjustment-amount"));
    await user.type(screen.getByLabelText("pnl-by-business-adjustment-amount"), "2500");
    await user.type(screen.getByLabelText("pnl-by-business-adjustment-reason"), "补录政策性金融债损益");
    await user.click(screen.getByRole("button", { name: "保存调整" }));

    await waitFor(() => {
      expect(client.createPnlByBusinessManualAdjustment).toHaveBeenCalledWith({
        report_date: "2025-12-31",
        row_key: "asset_zqtz_policy_financial_bond",
        business_type: "政策性金融债",
        operator: "DELTA",
        approval_status: "approved",
        manual_adjustment: "2500",
        reason: "补录政策性金融债损益",
      });
    });
  });

  it("queues heavy /pnl-by-business analysis until base YTD data is ready", async () => {
    const client = buildPnlClient();
    const originalGetYtd = client.getPnlByBusinessYtd;
    const originalGetAnalysis = client.getPnlByBusinessAnalysis;
    let releaseYtd!: () => void;
    const ytdGate = new Promise<void>((resolve) => {
      releaseYtd = resolve;
    });
    let releaseBondBucket!: () => void;
    const bondBucketGate = new Promise<void>((resolve) => {
      releaseBondBucket = resolve;
    });

    client.getPnlByBusinessYtd = vi.fn(async (year, asOfDate) => {
      await ytdGate;
      return originalGetYtd(year, asOfDate);
    });
    client.getPnlByBusinessAnalysis = vi.fn(async (options) => {
      if (options.dimension === "bond_bucket") {
        await bondBucketGate;
      }
      return originalGetAnalysis(options);
    });

    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    expect(client.getAdbComparison).not.toHaveBeenCalled();
    expect(client.getPnlByBusinessAnalysis).not.toHaveBeenCalled();

    releaseYtd();
    await waitFor(() => {
      expect(client.getAdbComparison).toHaveBeenCalledWith(
        "2025-12-01",
        "2025-12-31",
        expect.objectContaining({ topN: 200 }),
      );
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket",
      });
    });
    const dimensionsBeforeFirstPanelSettles = vi
      .mocked(client.getPnlByBusinessAnalysis)
      .mock.calls.map(([options]) => options.dimension);
    expect(dimensionsBeforeFirstPanelSettles).toEqual(["bond_bucket"]);

    releaseBondBucket();
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket_monthly",
      });
    });
  });
});
