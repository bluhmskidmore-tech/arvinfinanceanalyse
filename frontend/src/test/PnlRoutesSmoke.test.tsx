import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-routes-echarts-stub" />,
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
        total_pnl: "130000.00",
        current_balance: "100000000.00",
        balance_yield_pct: "0.0013",
        source_kind: "zqtz",
        source_note: "ZQTZ_ASSET_BOND_ROWS",
        proportion: "1.000000",
        assets_count: 1,
      },
    ],
  };
  const byBusinessMonthly: PnlByBusinessMonthlyPayload = {
    year: 2025,
    as_of_date: "2025-12-31",
    source_tables: ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
    months: [
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
        months: byBusinessMonthly.months.map((month) => ({
          ...month,
          month_key: `${year}-${(asOfDate ?? "2025-12-31").slice(5, 7)}`,
          period_start_date: `${year}-${(asOfDate ?? "2025-12-31").slice(5, 7)}-01`,
          period_end_date: asOfDate ?? month.period_end_date,
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
  it("renders the real /pnl route surface through workbench routes", async () => {
    renderWorkbenchApp(["/pnl"], { client: buildPnlClient() });

    expect(await screen.findByTestId("yield-analysis-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "收益分析", level: 1 })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("选择报表月份")).toHaveValue("2025-12-31");
    });
    await waitFor(() => {
      expect(screen.getByText("损益表归因分析")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("240001.IB")).toBeInTheDocument();
    });
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
    await waitFor(() => {
      expect(client.getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    expect(client.getPnlByBusiness).not.toHaveBeenCalled();
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

    await waitFor(() => {
      expect(screen.getByText("分析截止日")).toBeInTheDocument();
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
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月度业务种类拆解");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    fireEvent.click(screen.getByRole("button", { name: /2025-12/ }));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("-0.59");
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-report-date"), { target: { value: "2025-11-30" } });
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
