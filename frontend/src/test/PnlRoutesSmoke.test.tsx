import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, vi } from "vitest";

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
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
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
    as_of_date: "2025-12-31",
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function buildPnlClient(): ApiClient {
  const base = createApiClient({ mode: "real" });
  const mockInsightsClient = createApiClient({ mode: "mock" });
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
      business_count: 3,
      total_pnl: "13.00",
      total_scale_amount: "100000000.00",
      // 与 rows 本地求和刻意不同（rows 514 合计为 15.00 元），用于证明表脚直读 summary。
      interest_income_514: "150000.00",
      fair_value_change_516: "10000.00",
      capital_gain_517: "20000.00",
      manual_adjustment: "0.00",
      pnl_row_count: 6,
      traced_pnl_row_count: 1,
      untraced_pnl_row_count: 5,
      untraced_breakdown: [
        {
          reason_code: "position_absent_before_maturity",
          invest_type_std: "A",
          pnl_row_count: 2,
          total_pnl: "2.00",
          abs_pnl: "2.00",
          interest_income_514: "2.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
        },
        {
          reason_code: "matured_before_or_on_report_date",
          invest_type_std: "T",
          pnl_row_count: 3,
          total_pnl: "3.00",
          abs_pnl: "3.00",
          interest_income_514: "3.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
        },
      ],
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
      {
        report_date: "2025-12-31",
        business_type_primary: "T",
        business_type: "T",
        currency_basis: "CNY",
        interest_income_514: "3.00",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "3.00",
        scale_amount: "0.00",
        yield_pct: null,
        pnl_row_count: 3,
        balance_row_count: 0,
      },
      {
        report_date: "2025-12-31",
        business_type_primary: "A",
        business_type: "A",
        currency_basis: "CNY",
        interest_income_514: "2.00",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "2.00",
        scale_amount: "0.00",
        yield_pct: null,
        pnl_row_count: 2,
        balance_row_count: 0,
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
    coverage_days: 1,
    expected_days: 31,
    sample_filled: true,
    sample_fill_method: "observed_days_scaled_to_calendar",
    classified_parent_total_pnl: "123456.78",
    summary: {
      interest_income: "100000.00",
      fair_value_change: "10000.00",
      capital_gain: "20000.00",
      manual_adjustment: "0.00",
      total_pnl: "130000.00",
      avg_balance: "170000000.00",
      current_balance: "170000000.00",
      annualized_yield_pct: "0.900380",
      ftp_rate_pct: "1.600000",
      ftp_cost: "231013.70",
      ftp_net_pnl: "-101013.70",
      ftp_net_annualized_yield_pct: "-0.699620",
      proportion: "1.000000",
      assets_count: 4,
    },
    unallocated_pnl: "64295.80",
    unallocated_abs_pnl: "64299.08",
    unallocated_row_count: 400,
    reconciliation_delta: "0.00",
    unallocated_breakdown: [
      {
        reason_code: "no_business_rule_match",
        source_kind: "formal_fi",
        invest_type_std: "A",
        accounting_basis: "FVOCI",
        portfolio_name: "FIOA",
        cost_center: "501060",
        pnl_row_count: 8,
        total_pnl: "58139.14",
        abs_pnl: "58139.14",
        sample_instrument_codes: ["260304"],
      },
      {
        reason_code: "no_business_rule_match",
        source_kind: "formal_fi",
        invest_type_std: "T",
        accounting_basis: "FVTPL",
        portfolio_name: "FIOA",
        cost_center: "506030",
        pnl_row_count: 392,
        total_pnl: "6156.66",
        abs_pnl: "6159.94",
        sample_instrument_codes: ["012681483"],
      },
    ],
    unallocated_items: [
      {
        report_date: "2025-12-31",
        reason_code: "no_business_rule_match",
        source_kind: "formal_fi",
        instrument_code: "260304",
        portfolio_name: "FIOA",
        cost_center: "501060",
        invest_type_std: "A",
        accounting_basis: "FVOCI",
        currency_basis: "CNY",
        interest_income_514: "49314.43",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "49314.43",
        abs_pnl: "49314.43",
      },
      {
        report_date: "2025-12-31",
        reason_code: "no_business_rule_match",
        source_kind: "formal_fi",
        instrument_code: "012681483",
        portfolio_name: "FIOA",
        cost_center: "506030",
        invest_type_std: "T",
        accounting_basis: "FVTPL",
        currency_basis: "CNY",
        interest_income_514: "3287.67",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "3287.67",
        abs_pnl: "3287.67",
      },
      {
        report_date: "2025-12-31",
        reason_code: "no_business_rule_match" as const,
        source_kind: "formal_fi",
        instrument_code: "TINYNEG",
        portfolio_name: "FIOA",
        cost_center: "506020",
        invest_type_std: "T",
        accounting_basis: "FVTPL",
        currency_basis: "CNY",
        interest_income_514: "-0.05",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "-0.05",
        abs_pnl: "0.05",
      },
      ...Array.from({ length: 397 }, (_, index) => ({
        report_date: "2025-12-31",
        reason_code: "no_business_rule_match" as const,
        source_kind: "formal_fi",
        instrument_code: `UNALLOCATED-${String(index + 3).padStart(3, "0")}`,
        portfolio_name: "FIOA",
        cost_center: "506020",
        invest_type_std: "T",
        accounting_basis: "FVTPL",
        currency_basis: "CNY",
        interest_income_514: "0.00",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "0.00",
        abs_pnl: "0.00",
      })),
    ],
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
        avg_balance: "100000000.00",
        current_balance: "100000000.00",
        balance_yield_pct: "0.0013",
        annualized_yield_pct: "1.530645",
        ftp_rate_pct: "1.600000",
        ftp_cost: "135890.41",
        ftp_net_pnl: "-5890.41",
        ftp_net_annualized_yield_pct: "-0.069355",
        source_kind: "zqtz",
        source_note: "ZQTZ_ASSET_BOND_ROWS",
        proportion: "1.000000",
        assets_count: 2,
      },
      {
        row_key: "asset_zqtz_credit_bond",
        sort_order: 67,
        business_type: "信用债",
        interest_income: "0.00",
        fair_value_change: "0.00",
        capital_gain: "0.00",
        manual_adjustment: "0.00",
        total_pnl: "0.00",
        avg_balance: "70000000.00",
        current_balance: "70000000.00",
        balance_yield_pct: "0.0000",
        annualized_yield_pct: "0.000000",
        ftp_rate_pct: "1.600000",
        ftp_cost: "95123.29",
        ftp_net_pnl: "-95123.29",
        ftp_net_annualized_yield_pct: "-1.600000",
        source_kind: "zqtz",
        source_note: "ZQTZ_ASSET_BOND_ROWS",
        proportion: "0.000000",
        assets_count: 2,
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
        balance_yield_pct: "0.001",
        annualized_yield_pct: "1.177419",
        ftp_rate_pct: "1.600000",
        ftp_cost: "67945.21",
        ftp_net_pnl: "-17945.21",
        ftp_net_annualized_yield_pct: "-0.422581",
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
    management_change: {
      comparison_basis: "latest_month_vs_previous_calendar_month",
      comparison_scope: "requested_year",
      comparison_status: "data_quality_warning",
      comparison_available: true,
      current_month_key: "2025-12",
      previous_month_key: "2025-11",
      coverage_warning_months: ["2025-12"],
      reconciliation_warning_months: ["2025-12"],
      incomplete_months: [],
      summary: {
        interest_income_delta: "20000.00",
        fair_value_change_delta: "5000.00",
        capital_gain_delta: "7500.00",
        manual_adjustment_delta: "2500.00",
        total_pnl_delta: "35000.00",
        avg_balance_delta: "10000000.00",
        current_balance_delta: "8000000.00",
        annualized_yield_delta_bp: "24.6386",
        ftp_cost_delta: "17534.25",
        ftp_net_pnl_delta: "17465.75",
        ftp_net_annualized_yield_delta_bp: "24.6386",
      },
      rows: [
        {
          row_key: "asset_zqtz_policy_financial_bond",
          sort_order: 66,
          business_type: "政策性金融债",
          comparison_available: true,
          comparison_reason: "available",
          interest_income_delta: "20000.00",
          fair_value_change_delta: "5000.00",
          capital_gain_delta: "7500.00",
          manual_adjustment_delta: "2500.00",
          total_pnl_delta: "35000.00",
          avg_balance_delta: "10000000.00",
          current_balance_delta: "8000000.00",
          annualized_yield_delta_bp: "24.6386",
          ftp_cost_delta: "17534.25",
          ftp_net_pnl_delta: "17465.75",
          ftp_net_annualized_yield_delta_bp: "24.6386",
        },
      ],
    },
    months: [
      {
        month_key: "2025-11",
        period_start_date: "2025-11-01",
        period_end_date: "2025-11-30",
        calendar_days: 30,
        expected_days: 30,
        sample_filled: false,
        sample_fill_method: null,
        source_total_pnl: "95000.00",
        classified_parent_total_pnl: "95000.00",
        unallocated_pnl: "0.00",
        unallocated_abs_pnl: "0.00",
        unallocated_row_count: 0,
        reconciliation_delta: "0.00",
        unallocated_breakdown: [],
        unallocated_items: [],
        unallocated_evidence_complete: true,
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
        coverage_days: 1,
        expected_days: 31,
        sample_filled: true,
        sample_fill_method: "observed_days_scaled_to_calendar",
        source_total_pnl: "180000.00",
        classified_parent_total_pnl: "130000.00",
        unallocated_pnl: "50000.00",
        unallocated_abs_pnl: "90000.00",
        unallocated_row_count: 2,
        reconciliation_delta: "0.00",
        unallocated_breakdown: [
          {
            reason_code: "no_business_rule_match",
            source_kind: "formal_fi",
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            portfolio_name: "Unmapped Desk",
            cost_center: "CC-UNMAPPED",
            pnl_row_count: 2,
            total_pnl: "50000.00",
            abs_pnl: "90000.00",
            sample_instrument_codes: ["MONTHLY-A", "MONTHLY-A-NEG"],
          },
        ],
        unallocated_items: [
          {
            report_date: "2025-12-31",
            reason_code: "no_business_rule_match",
            source_kind: "formal_fi",
            instrument_code: "MONTHLY-A",
            portfolio_name: "Unmapped Desk",
            cost_center: "CC-UNMAPPED",
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            currency_basis: "CNY",
            interest_income_514: "70000.00",
            fair_value_change_516: "0.00",
            capital_gain_517: "0.00",
            manual_adjustment: "0.00",
            total_pnl: "70000.00",
            abs_pnl: "70000.00",
          },
          {
            report_date: "2025-12-31",
            reason_code: "no_business_rule_match",
            source_kind: "formal_fi",
            instrument_code: "MONTHLY-A-NEG",
            portfolio_name: "Unmapped Desk",
            cost_center: "CC-UNMAPPED",
            invest_type_std: "A",
            accounting_basis: "FVOCI",
            currency_basis: "CNY",
            interest_income_514: "-20000.00",
            fair_value_change_516: "0.00",
            capital_gain_517: "0.00",
            manual_adjustment: "0.00",
            total_pnl: "-20000.00",
            abs_pnl: "20000.00",
          },
        ],
        unallocated_evidence_complete: true,
        summary: {
          interest_income: "100000.00",
          fair_value_change: "10000.00",
          capital_gain: "17500.00",
          manual_adjustment: "2500.00",
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
            capital_gain: "17500.00",
            manual_adjustment: "2500.00",
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
        asset_count: 2,
      },
    ],
  };
  const byBusinessCurrencyAnalysis: PnlByBusinessAnalysisPayload = {
    ...byBusinessAnalysis,
    dimension: "currency",
    rows: [
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "CNY",
        dimension_label: "人民币",
        interest_income: "80000.00",
        fair_value_change: "5000.00",
        capital_gain: "15000.00",
        total_pnl: "100000.00",
        avg_balance: "80000000.00",
        current_balance: "80000000.00",
        annualized_yield_pct: "1.471774",
        ftp_cost: "108712.33",
        ftp_net_pnl: "-8712.33",
        ftp_net_annualized_yield_pct: "-0.128228",
        asset_count: 1,
      },
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "USD",
        dimension_label: "美元",
        interest_income: "20000.00",
        fair_value_change: "5000.00",
        capital_gain: "5000.00",
        total_pnl: "30000.00",
        avg_balance: "20000000.00",
        current_balance: "20000000.00",
        annualized_yield_pct: "1.766129",
        ftp_cost: "27178.08",
        ftp_net_pnl: "2821.92",
        ftp_net_annualized_yield_pct: "0.166146",
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
  const byBusinessCreditInstrumentAnalysis: PnlByBusinessAnalysisPayload = {
    ...byBusinessAnalysis,
    business_key: "asset_zqtz_credit_bond",
    dimension: "instrument",
    rows: [
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "240002.IB",
        dimension_label: "240002.IB 信用债贡献券",
        total_pnl: "40000.00",
        avg_balance: "70000000.00",
        current_balance: "70000000.00",
        ftp_cost: "95123.29",
        ftp_net_pnl: "-55123.29",
        ftp_net_annualized_yield_pct: "-0.945000",
      },
      {
        ...byBusinessAnalysis.rows[0],
        dimension_key: "240003.IB",
        dimension_label: "240003.IB 信用债拖累券",
        total_pnl: "-10000.00",
        avg_balance: "30000000.00",
        current_balance: "30000000.00",
        ftp_cost: "40767.12",
        ftp_net_pnl: "-50767.12",
        ftp_net_annualized_yield_pct: "-1.991667",
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
      result_meta: {
        ...buildMeta("pnl.by_business_ytd", "tr_route_business_ytd"),
        basis: "analytical" as const,
        formal_use_allowed: false,
      },
      result: {
        ...byBusinessYtd,
        year,
        period_label: `${year}年${(asOfDate ?? "2025-12-31").slice(5, 7)}月累计`,
        period_start_date: `${year}-${(asOfDate ?? "2025-12-31").slice(5, 7)}-01`,
        period_end_date: asOfDate ?? byBusinessYtd.period_end_date,
      },
    })),
    getPnlByBusinessInsights: vi.fn((year: number, asOfDate: string) =>
      mockInsightsClient.getPnlByBusinessInsights(year, asOfDate),
    ),
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
            : options.dimension === "currency"
              ? byBusinessCurrencyAnalysis
            : options.dimension === "instrument"
              ? options.businessKey === "asset_zqtz_credit_bond"
                ? byBusinessCreditInstrumentAnalysis
                : byBusinessNegativeInstrumentAnalysis
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
        {
          category: "信用债",
          spot_balance: 70_000_000,
          avg_balance: 70_000_000,
          proportion: 70,
          weighted_rate: null,
        },
      ],
      liabilities_breakdown: [],
    })),
  };
}

describe("pnl routed pages smoke", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules(
      "pnl",
      "pnl-bridge",
      "pnl-by-business",
      "pnl-by-business-insights",
    );
  }, 20_000);

  it("renders the real /pnl route surface through workbench routes", async () => {
    const client = buildPnlClient();

    renderWorkbenchApp(["/pnl"], { client });

    expect(await screen.findByTestId("formal-pnl-v1-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "正式损益明细", level: 1 })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-report-date")).toHaveValue("2025-12-31");
    });
    await waitFor(() => {
      expect(client.getFormalPnlOverview).toHaveBeenCalledWith("2025-12-31");
      expect(client.getPnlV1Data).toHaveBeenCalledWith("2025-12-31");
    });
    expect(await screen.findByTestId("pnl-overview-cards")).toHaveTextContent("损益合计");
    expect(await screen.findByTestId("pnl-formal-fi-table")).toBeInTheDocument();
    expect(await screen.findByTestId("pnl-result-meta-panel-overview")).toHaveTextContent(
      "tr_route_overview",
    );
    expect(screen.getByTestId("pnl-result-meta-panel-data")).toHaveTextContent("tr_route_data");
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
    expect(screen.getByRole("link", { name: "全行生息资产利差 →" })).toHaveAttribute(
      "href",
      "/product-category-pnl",
    );
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
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("未读取");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("1 条手工调整");
      expect(screen.getByText("报表月份")).toBeInTheDocument();
      // This fixture carries an approved manual adjustment (+0.25 万元), so the
      // first summary card uses the adjusted-caliber label from the page model.
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("调整后已分类损益");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("含已批准调整 +0.25 万元");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("13 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月报业务种类明细");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2 个月");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-11");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    const leadershipSummary = screen.getByTestId("pnl-by-business-leadership-summary");
    const managementChange = screen.getByTestId("pnl-by-business-management-change");
    const dataStatusStrip = screen.getByTestId("pnl-by-business-data-status-strip");
    const filterTray = screen.getByTestId("pnl-by-business-filter-tray");
    expect(leadershipSummary).toContainElement(managementChange);
    expect(leadershipSummary.compareDocumentPosition(dataStatusStrip) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(dataStatusStrip.compareDocumentPosition(filterTray) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("政策性金融债");
      // Coverage is 1/31 days in this fixture, so FTP columns carry the
      // incomplete-coverage 待核对 caveat.
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP成本（待核对，万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP后收益（待核对，万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).not.toHaveTextContent(
        "其中：本币专户（成本法）",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-detail-table-2025-12")).toHaveTextContent(
        "其中：本币专户（成本法）",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-reconciliation-2025-12")).toHaveTextContent(
        "源损益 18 万元 = 父级 13 万元 + 未分类 5 万元",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-reconciliation-2025-12")).toHaveTextContent(
        "差异 0 万元 · 已闭合",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-unallocated-2025-12-panel")).toHaveTextContent(
        "2 条 · 净额 5 万元 · 绝对金额 9 万元",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-unallocated-2025-12-toggle")).toHaveAttribute(
        "aria-expanded",
        "false",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "政策性金融债 · 2025-12 损益桥",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "补数前损益（对账值）",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("12.75 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("0.25 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("13 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("13.59 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("-0.59 万元");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "月报接口已生效金额",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "当月自然日/365",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent("复核后补录");
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "系统暂无结构化税前额、增值税额或税后净额字段",
      );
    });
    fireEvent.click(screen.getByTestId("pnl-by-business-monthly-unallocated-2025-12-toggle"));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-unallocated-2025-12-breakdown-table")).toHaveTextContent(
        "CC-UNMAPPED",
      );
      expect(screen.getByTestId("pnl-by-business-monthly-unallocated-2025-12-items-table")).toHaveTextContent(
        "MONTHLY-A-NEG",
      );
    });
    fireEvent.click(screen.getByRole("button", { name: /2025-11/ }));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-11")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-monthly-reconciliation-2025-11")).toHaveTextContent(
        "余额覆盖 待返回/30 天",
      );
      expect(screen.queryByTestId("pnl-by-business-monthly-unallocated-2025-11-panel")).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(client.getPnlByBusinessYtd).toHaveBeenCalledWith(2025, "2025-12-31");
    });
    await waitFor(() => {
      expect(client.getPnlByBusinessInsights).toHaveBeenCalledWith(2025, "2025-12-31");
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
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "currency",
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
    expect(screen.getByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent("月度经营环比");
    expect(screen.getByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent("总表分项拆解");
    expect(screen.getByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent("tr_route_business_monthly");
    expect(screen.getByTestId("pnl-by-business-data-status-strip")).toHaveTextContent("tr_route_business_ytd");
    expect(await screen.findByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent("正式结构分析");
    expect(screen.getByTestId("pnl-by-business-insights-leadership-panel")).toHaveTextContent("结构分析待复核");
    expect(screen.getByTestId("pnl-by-business-insights-leadership-detail-link")).toHaveAttribute(
      "href",
      "/pnl-by-business-insights?year=2025&as_of_date=2025-12-31",
    );
    expect(screen.getByRole("link", { name: "业务结构与FTP后收益分析 →" })).toHaveAttribute(
      "href",
      "/pnl-by-business-insights?year=2025&as_of_date=2025-12-31",
    );
    expect(screen.getByTestId("pnl-by-business-state-definition-pending")).toHaveClass(
      "pnl-by-business-state-surface--compact-governance",
    );

    await waitFor(() => {
      expect(screen.getByText("分析截止日")).toBeInTheDocument();
      expect(screen.getAllByText("结果元信息 / 证据").length).toBeGreaterThan(0);
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("领导判断");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("可分析");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("最大拖累");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("FTP 可分析");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent(
        "1 条所选报表日已批准调整",
      );
      expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent("下一步下钻");
      expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent("证券级下钻");
      expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent(
        "看 Top 贡献券、Top 拖累券、FTP 后为负",
      );
      expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent("ADB 已覆盖");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("13 万元");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("合计损益（万元）");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("FTP后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-table")).not.toHaveTextContent("FTP成本（万元）");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("日均(亿元)");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("1.00");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("年化收益率");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("1.53%");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("100.00%");
      expect(screen.getByTestId("pnl-by-business-table")).not.toHaveTextContent("其中：本币专户（成本法）");
      expect(screen.getByTestId("pnl-by-business-detail-table")).toHaveTextContent("其中：本币专户（成本法）");
      expect(screen.getByTestId("pnl-by-business-table-parent-footer")).toHaveTextContent("父级损益（系统汇总）");
      expect(screen.getByTestId("pnl-by-business-table-parent-footer")).toHaveTextContent("13");
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toBeVisible();
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toHaveTextContent("总表分项拆解");
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toHaveTextContent("人民币");
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toHaveTextContent("美元");
      expect(screen.getByTestId("pnl-by-business-main-breakdown")).toHaveTextContent(
        "原币种仅用于拆分，损益、日均、余额及 FTP 金额均为折人民币口径",
      );
      expect(screen.getByLabelText("pnl-by-business-main-breakdown-dimension")).toHaveValue("currency");
      const parentFooterCells = screen
        .getByTestId("pnl-by-business-table-parent-footer")
        .querySelectorAll("td");
      expect(parentFooterCells).toHaveLength(12);
      expect(parentFooterCells[0]).toHaveTextContent("父级损益（系统汇总）");
      expect(parentFooterCells[1]).toHaveTextContent("1.70");
      expect(parentFooterCells[2]).toHaveTextContent("10");
      expect(parentFooterCells[3]).toHaveTextContent("1");
      expect(parentFooterCells[4]).toHaveTextContent("2");
      expect(parentFooterCells[5]).toHaveTextContent("0");
      expect(parentFooterCells[6]).toHaveTextContent("13");
      expect(parentFooterCells[7]).toHaveTextContent("0.90%");
      expect(parentFooterCells[8]).toHaveTextContent("-10.1");
      expect(parentFooterCells[9]).toHaveTextContent("-0.70%");
      expect(parentFooterCells[10]).toHaveTextContent("100.00%");
      expect(parentFooterCells[11]).toHaveTextContent("4");
      const managementChange = screen.getByTestId("pnl-by-business-management-change");
      expect(managementChange).toHaveTextContent("2025-12 较 2025-11");
      // 2025-12 coverage is incomplete in this fixture, so balance/FTP deltas
      // fail closed to 待核对 while the classified parent PnL delta stays numeric.
      expect(managementChange).toHaveTextContent("日均变化");
      expect(managementChange).toHaveTextContent("待核对");
      expect(managementChange).not.toHaveTextContent("+0.10 亿元");
      expect(managementChange).toHaveTextContent("已分类父级损益变化");
      expect(managementChange).toHaveTextContent("+3.50 万元");
      expect(managementChange).toHaveTextContent("FTP净损益变化");
      expect(managementChange).not.toHaveTextContent("+1.75 万元");
      expect(managementChange).toHaveTextContent("FTP后年化变化");
      expect(managementChange).not.toHaveTextContent("+24.64 bp");
      expect(managementChange).toHaveTextContent("数据质量提示");
      expect(managementChange).toHaveTextContent("2025-12 已分类父级损益较上月增加 3.50 万元");
      expect(managementChange).toHaveTextContent("最大波动业务为政策性金融债（增加 3.50 万元）");
      expect(managementChange).toHaveTextContent(
        "日均及 FTP 指标因 2025-12 覆盖不足暂不比较，期末余额增加 0.08 亿元",
      );
      expect(managementChange).toHaveTextContent(
        "日均、FTP 净损益及 FTP 后年化变化在覆盖补齐前已停止用于汇报",
      );
      expect(managementChange).toHaveTextContent("损益构成变化");
      expect(screen.getByTestId("pnl-by-business-management-change-drivers")).toHaveTextContent("政策性金融债");
      const ytdTable = within(screen.getByTestId("pnl-by-business-table")).getByRole("table");
      expect(within(ytdTable).getAllByRole("columnheader")).toHaveLength(12);
      const ytdParentRow = within(ytdTable).getByText("政策性金融债").closest("tr");
      expect(ytdParentRow).not.toBeNull();
      expect(ytdParentRow!.querySelectorAll("td")).toHaveLength(12);
      expect(ytdParentRow!.querySelector('[data-pnl-tone="positive"]')).toHaveTextContent("13");
      expect(ytdParentRow!.querySelector('[data-pnl-tone="negative"]')).toHaveTextContent("-0.59");
      const cnyCurrencyRow = within(ytdTable).getByTestId("pnl-by-business-inline-currency-row-CNY");
      const usdCurrencyRow = within(ytdTable).getByTestId("pnl-by-business-inline-currency-row-USD");
      expect(cnyCurrencyRow).toHaveTextContent("人民币");
      expect(cnyCurrencyRow).toHaveTextContent("父级拆分 · 金额折人民币");
      expect(cnyCurrencyRow.querySelectorAll("td")).toHaveLength(12);
      expect(usdCurrencyRow).toHaveTextContent("美元");
      expect(usdCurrencyRow).toHaveTextContent("父级拆分 · 金额折人民币");
      expect(usdCurrencyRow.querySelectorAll("td")).toHaveLength(12);
      const ytdZeroRow = within(ytdTable).getByText("信用债").closest("tr");
      expect(ytdZeroRow).not.toBeNull();
      const ytdZeroDecisionCells = ytdZeroRow!.querySelectorAll("[data-pnl-tone]");
      expect(ytdZeroDecisionCells).toHaveLength(2);
      expect(ytdZeroDecisionCells[0]).toHaveAttribute("data-pnl-tone", "default");
      expect(ytdZeroDecisionCells[1]).toHaveAttribute("data-pnl-tone", "negative");
      expect(screen.getByTestId("pnl-by-business-table-unallocated-footer")).toHaveTextContent("6.43");
      expect(screen.getByTestId("pnl-by-business-table-unallocated-footer")).toHaveTextContent("400");
      const selectedTrend = screen.getByTestId("pnl-by-business-selected-monthly-trend");
      expect(selectedTrend).toHaveTextContent("政策性金融债");
      expect(selectedTrend).toHaveTextContent("1/1 个月");
      expect(selectedTrend).toHaveTextContent("损益与 FTP 后收益（万元）");
      expect(screen.getByTestId("pnl-by-business-trend-tab-pnl")).toHaveAttribute("aria-pressed", "true");
      expect(within(selectedTrend).getAllByTestId("pnl-routes-echarts-stub")).toHaveLength(1);
      expect(screen.getByTestId("pnl-by-business-deep-dive")).not.toHaveAttribute("open");
      expect(screen.getByTestId("pnl-by-business-unallocated-panel")).toHaveTextContent("查看未分类明细");
      expect(screen.getByTestId("pnl-by-business-unallocated-panel")).toHaveTextContent("400 条");
      expect(screen.getByTestId("pnl-by-business-unallocated-panel")).toHaveTextContent("绝对金额 6.43 万元");
      expect(screen.getByTestId("pnl-by-business-unallocated-toggle")).toHaveAttribute("aria-expanded", "false");
      expect(screen.getByTestId("pnl-by-business-state-coverage-partial")).toBeVisible();
      expect(screen.getByTestId("pnl-by-business-state-unallocated")).toBeVisible();
      expect(screen.getByTestId("pnl-by-business-bond-bucket-analysis")).toHaveTextContent("债券四类统计");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-table")).toHaveTextContent("利率债");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-table")).toHaveTextContent("FTP成本（万元）");
      expect(screen.getByTestId("pnl-by-business-ftp-bridge")).toHaveTextContent("FTP后收益桥");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-monthly")).toHaveTextContent("四类债券月度趋势");
      expect(screen.getByTestId("pnl-by-business-negative-ftp-list")).toHaveTextContent("负FTP后收益清单");
      expect(screen.getByTestId("pnl-by-business-negative-ftp-list")).toHaveTextContent("负FTP资产");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("证券级下钻");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("Top 贡献券");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("Top 拖累券");
      expect(screen.getByTestId("pnl-by-business-selected-ftp-status")).toHaveTextContent("FTP 后转负");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("240001.IB 负FTP资产");
      expect(screen.getByTestId("pnl-by-business-driver-overview")).toHaveTextContent("1.53%");
      expect(screen.getByTestId("pnl-by-business-driver-overview")).not.toHaveTextContent(
        "其中：本币专户（成本法）",
      );
      expect(screen.getByTestId("pnl-by-business-analysis-panel")).toHaveTextContent("2025-12-31");
      expect(screen.getByTestId("pnl-by-business-analysis-table")).toHaveTextContent("1.00");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("未读取");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月报业务种类明细");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    fireEvent.click(screen.getByTestId("pnl-by-business-trend-tab-balance"));
    expect(screen.getByTestId("pnl-by-business-trend-active-panel")).toHaveTextContent("日均与期末余额（亿元）");
    expect(screen.getByTestId("pnl-by-business-trend-tab-balance")).toHaveAttribute("aria-pressed", "true");
    expect(
      within(screen.getByTestId("pnl-by-business-selected-monthly-trend")).getAllByRole("button", {
        pressed: true,
      }),
    ).toHaveLength(1);
    fireEvent.click(screen.getByTestId("pnl-by-business-trend-tab-yield"));
    expect(screen.getByTestId("pnl-by-business-trend-active-panel")).toHaveTextContent("收益率与 FTP（%）");
    expect(screen.getByTestId("pnl-by-business-trend-tab-yield")).toHaveAttribute("aria-pressed", "true");
    expect(
      within(screen.getByTestId("pnl-by-business-selected-monthly-trend")).getAllByRole("button", {
        pressed: true,
      }),
    ).toHaveLength(1);
    expect(screen.getByTestId("pnl-by-business-detail-table")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByTestId("pnl-by-business-detail-table-toggle"));
    expect(screen.getByTestId("pnl-by-business-detail-table")).toHaveAttribute("open");
    fireEvent.click(screen.getByTestId("pnl-by-business-deep-dive-toggle"));
    expect(screen.getByTestId("pnl-by-business-deep-dive")).toHaveAttribute("open");
    expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toBeVisible();
    expect(screen.getByTestId("pnl-by-business-evidence-disclosure")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByTestId("pnl-by-business-evidence-disclosure-toggle"));
    expect(screen.getByTestId("pnl-by-business-evidence-disclosure")).toHaveAttribute("open");
    expect(screen.getByTestId("pnl-by-business-result-meta-panel")).toBeVisible();
    fireEvent.click(screen.getByTestId("pnl-by-business-unallocated-toggle"));
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-unallocated-toggle")).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByTestId("pnl-by-business-unallocated-breakdown-table")).toHaveTextContent("501060");
      expect(screen.getByTestId("pnl-by-business-unallocated-breakdown-table")).toHaveTextContent("A");
      expect(screen.getByTestId("pnl-by-business-unallocated-breakdown-table")).toHaveTextContent("未命中业务分类规则");
      expect(screen.getByTestId("pnl-by-business-unallocated-items-table")).toHaveTextContent("260304");
      expect(screen.getByTestId("pnl-by-business-unallocated-items-table")).toHaveTextContent("4.93");
      expect(screen.getByText("TINYNEG").closest("tr")).not.toHaveTextContent("-0");
      expect(screen.getByTestId("pnl-by-business-unallocated-panel")).toHaveTextContent("Excel 导出包含全部 400 条");
    });
    fireEvent.click(screen.getByRole("button", { name: /信用债/ }));
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_credit_bond",
        dimension: "instrument",
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("信用债");
      expect(screen.getByTestId("pnl-by-business-selected-ftp-status")).toHaveTextContent("FTP 后转负");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("240002.IB 信用债贡献券");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent("240003.IB 信用债拖累券");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).not.toHaveTextContent("240001.IB 负FTP资产");
      expect(screen.getByTestId("pnl-by-business-selected-monthly-trend")).toHaveTextContent("信用债");
      expect(screen.getByTestId("pnl-by-business-selected-monthly-trend")).toHaveTextContent(
        "暂无所选业务月度趋势",
      );
      expect(
        within(screen.getByTestId("pnl-by-business-selected-monthly-trend")).queryAllByTestId(
          "pnl-routes-echarts-stub",
        ),
      ).toHaveLength(0);
    });
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "monthly" } });
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-view-mode")).toHaveValue("monthly");
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2025-12");
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("月报业务种类明细");
      expect(screen.getByTestId("pnl-by-business-monthly-breakdown")).toHaveTextContent("2 个月");
    });
    const monthlyBreakdown = screen.getByTestId("pnl-by-business-monthly-breakdown");
    if (!screen.queryByTestId("pnl-by-business-monthly-table-2025-12")) {
      fireEvent.click(within(monthlyBreakdown).getByRole("button", { name: /2025-12/ }));
    }
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("手工调整（万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("FTP后收益（待核对，万元）");
      expect(screen.getByTestId("pnl-by-business-monthly-table-2025-12")).toHaveTextContent("-0.59");
    });
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-view-mode")).toHaveValue("ytd");
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
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("5 条未追溯");
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("对账证据");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("不与月报/YTD 混加");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("T 3 条 / A 2 条");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("到期后无持仓");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("未到期但报表日无持仓");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("cost_center 已授权放宽");
    });
    expect(await screen.findByTestId("pnl-by-business-formal-table")).toHaveTextContent("政策性金融债");
    expect(screen.getByTestId("pnl-by-business-formal-table")).toHaveTextContent("表内收益率");
    expect(screen.getByTestId("pnl-by-business-formal-table-footer")).toHaveTextContent("全表合计");
    // 表脚直读后端 summary 分列合计：514 合计 150000 元 => 15（万元）；行数取 summary.pnl_row_count。
    // rows 本地求和是 15.00 元（会显示 0），若前端复算则以下断言会失败。
    const formalFooterCells = screen
      .getByTestId("pnl-by-business-formal-table-footer")
      .querySelectorAll("td");
    expect(formalFooterCells[3]).toHaveTextContent("15");
    expect(formalFooterCells[4]).toHaveTextContent("1");
    expect(formalFooterCells[5]).toHaveTextContent("2");
    expect(formalFooterCells[9]).toHaveTextContent("6");
  });

  it("surfaces failed precompute fallback and allows a controlled rebuild", async () => {
    const client = buildPnlClient();
    const getPrecomputeStatus = vi.fn(async () => ({
      year: 2025,
      status: "failed",
      serving_mode: "live_fallback",
      is_current: false,
      run_id: "pnl_by_business_precompute:test-failed",
      report_date: "2025-12-31",
      source_version: "sv_pnl_by_business_failed",
      rule_version: "rv_pnl_by_business_precompute_v6",
      queued_at: "2026-07-15T12:00:00Z",
      started_at: "2026-07-15T12:00:01Z",
      finished_at: "2026-07-15T12:00:02Z",
      generated_at: null,
      record_count: null,
      error_message: "precompute fixture failed",
      failure_category: "materialize_failure",
      trigger_reason: "manual_retry",
      retry_attempt: 4,
      retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
    }));
    const rebuildPrecompute = vi.fn(async () => ({
      year: 2025,
      status: "queued",
      serving_mode: "live_fallback",
      is_current: false,
      run_id: "pnl_by_business_precompute:test-retry",
      report_date: "2025-12-31",
      source_version: "sv_pnl_by_business_precompute_pending",
      rule_version: "rv_pnl_by_business_precompute_v6",
      queued_at: "2026-07-15T12:01:00Z",
      started_at: null,
      finished_at: null,
      generated_at: null,
      record_count: null,
      error_message: null,
      failure_category: null,
      trigger_reason: "manual_retry",
      retry_attempt: 0,
      retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
    }));
    Object.assign(client, {
      getPnlByBusinessPrecomputeStatus: getPrecomputeStatus,
      rebuildPnlByBusinessPrecompute: rebuildPrecompute,
    });

    renderWorkbenchApp(["/pnl-by-business"], { client });

    const statusPanel = await screen.findByTestId("pnl-by-business-precompute-status");
    await waitFor(() => {
      expect(statusPanel).toHaveTextContent("预计算失败，当前使用实时计算");
      expect(statusPanel).toHaveTextContent("2025-12-31");
      expect(statusPanel).toHaveTextContent("precompute fixture failed");
      expect(getPrecomputeStatus).toHaveBeenCalledWith(2025, "2025-12-31");
    });

    await userEvent.setup().click(screen.getByRole("button", { name: "重新生成预计算" }));
    expect(rebuildPrecompute).toHaveBeenCalledWith(2025, "2025-12-31");
    await waitFor(() => {
      expect(getPrecomputeStatus).toHaveBeenCalledTimes(2);
    });
  });

  it("falls back to YTD daily averages when supplemental ADB comparison is forbidden", async () => {
    const client = buildPnlClient();
    vi.mocked(client.getAdbComparison).mockRejectedValue(
      new Error("403: User is not allowed to read adb_analysis."),
    );

    renderWorkbenchApp(["/pnl-by-business"], { client });
    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });

    const fallbackSurface = await screen.findByTestId("pnl-by-business-state-adb-comparison-fallback");
    expect(fallbackSurface).toHaveTextContent("ADB 补充复核不可用，已使用 YTD 日均");
    expect(fallbackSurface).toHaveTextContent("这不代表缺日均");

    await waitFor(() => {
      const insight = screen.getByTestId("pnl-by-business-insight-strip");
      expect(insight).toHaveTextContent("预警/降级");
      expect(insight).toHaveTextContent("FTP 可分析（YTD 日均）");
      expect(insight).not.toHaveTextContent("项缺日均");
    });
    expect(screen.getByTestId("pnl-by-business-drilldown-recommendation")).toHaveTextContent("YTD 日均回退");
    expect(screen.getByTestId("pnl-by-business-driver-overview")).toHaveTextContent(
      "YTD 主端点（ADB 补充复核不可用）",
    );
    expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("1.00");
    expect(screen.getByTestId("pnl-by-business-ftp-bridge")).toHaveTextContent("-0.59 万元");
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "instrument",
      });
    });
  });

  it("scopes FTP status by view and does not block YTD trends on pending ADB evidence", async () => {
    const client = buildPnlClient();
    vi.mocked(client.getAdbComparison).mockImplementation(() => new Promise(() => undefined));

    renderWorkbenchApp(["/pnl-by-business"], { client });
    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    await waitFor(() => {
      const insight = screen.getByTestId("pnl-by-business-insight-strip");
      expect(insight).toHaveTextContent("月度 FTP 可分析");
      expect(insight).not.toHaveTextContent("ADB 复核中");
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    fireEvent.change(screen.getByLabelText("pnl-by-business-report-date"), { target: { value: "2025-11-30" } });

    await waitFor(() => {
      expect(client.getPnlByBusinessMonthly).toHaveBeenCalledWith(2025, "2025-11-30");
    });
    expect(await screen.findByTestId("pnl-by-business-selected-monthly-trend")).toHaveTextContent("1/1 个月");
    expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("FTP 可分析（ADB 复核中）");

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "formal" } });
    await waitFor(() => {
      const insight = screen.getByTestId("pnl-by-business-insight-strip");
      expect(insight).toHaveTextContent("不适用（仅对账）");
      expect(insight).not.toHaveTextContent("缺 FTP 字段");
    });
  });

  it("queries monthly adjustment evidence for the actual fallback bucket date", async () => {
    const client = buildPnlClient();
    const monthlyResponse = await client.getPnlByBusinessMonthly(2025, "2025-12-31");
    vi.mocked(client.getPnlByBusinessMonthly).mockResolvedValue({
      ...monthlyResponse,
      result: {
        ...monthlyResponse.result,
        months: monthlyResponse.result.months.filter((month) => month.period_end_date === "2025-11-30"),
      },
    });
    vi.mocked(client.getPnlByBusinessManualAdjustments).mockClear();

    renderWorkbenchApp(["/pnl-by-business"], { client });

    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-report-date")).toHaveValue("2025-12-31");
      expect(client.getPnlByBusinessManualAdjustments).toHaveBeenCalledWith("2025-11-30");
    });
    expect(screen.getByText(/月报（截至 2025-11）/)).toBeInTheDocument();
  });

  it("surfaces monthly adjustment audit read failures without hiding the booked bridge", async () => {
    const client = buildPnlClient();
    vi.mocked(client.getPnlByBusinessManualAdjustments).mockRejectedValue(new Error("audit unavailable"));

    renderWorkbenchApp(["/pnl-by-business"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "审批记录读取失败，当前仅展示月报已入账金额",
      );
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("手工调整审批数量待核对");
    });

    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-manual-adjustments")).toHaveTextContent(
        "审批记录不可用，未按 0 条处理",
      );
      expect(screen.getByRole("button", { name: "保存调整" })).toBeDisabled();
    });
  });

  it("rejects monthly adjustment evidence whose returned report date does not match the displayed month", async () => {
    const client = buildPnlClient();
    vi.mocked(client.getPnlByBusinessManualAdjustments).mockResolvedValue({
      report_date: "2025-11-30",
      adjustment_count: 0,
      event_total: 0,
      adjustments: [],
      events: [],
    });

    renderWorkbenchApp(["/pnl-by-business"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-monthly-adjustment-bridge")).toHaveTextContent(
        "审批记录报表日 2025-11-30 与实际展示日 2025-12-31 不一致，未采用该审批证据",
      );
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("手工调整审批数量待核对");
    });
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
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket",
      });
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        dimension: "bond_bucket_monthly",
      });
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "monthly",
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
        unallocatedBreakdown: expect.arrayContaining([
          expect.objectContaining({ cost_center: "501060", pnl_row_count: 8 }),
        ]),
        unallocatedItems: expect.arrayContaining([
          expect.objectContaining({ instrument_code: "260304", total_pnl: "49314.43" }),
        ]),
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

  it("shows true-zero ADB as present but zero-denominator limited in /pnl-by-business YTD", async () => {
    const client = buildPnlClient();
    const originalYtd = await client.getPnlByBusinessYtd(2025, "2025-12-31");
    client.getPnlByBusinessYtd = vi.fn(async (year: number, asOfDate?: string) => ({
      ...originalYtd,
      result: {
        ...originalYtd.result,
        year,
        period_end_date: asOfDate ?? originalYtd.result.period_end_date,
        items: originalYtd.result.items.map((item) =>
          item.row_key === "asset_zqtz_policy_financial_bond"
            ? {
                ...item,
                avg_balance: "0.00",
                // 近零真实值：-30 元 = -0.003 万，按两位小数如实四舍五入展示为 0（无 "-0" 噪声、不做阈值折叠）
                fair_value_change: "-30",
                annualized_yield_pct: null,
                ftp_cost: null,
                ftp_net_pnl: null,
                ftp_net_annualized_yield_pct: null,
              }
            : item,
        ),
      },
    }));
    client.getAdbComparison = vi.fn(async (_startDate: string, _endDate: string) => ({
      report_date: _endDate,
      start_date: _startDate,
      end_date: _endDate,
      calendar_days_inclusive: 31,
      adb_denominator_basis: "snapshot_calendar" as const,
      num_days: 31,
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
          avg_balance: 0,
          proportion: 0,
          weighted_rate: null,
        },
      ],
      liabilities_breakdown: [],
    }));

    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });

    await waitFor(() => {
      expect(client.getAdbComparison).toHaveBeenCalledWith(
        "2025-12-01",
        "2025-12-31",
        expect.objectContaining({ topN: 200 }),
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-insight-strip")).toHaveTextContent("日均为0");
      expect(screen.getByTestId("pnl-by-business-insight-strip")).not.toHaveTextContent("1 项缺日均");
      const policyRow = within(screen.getByTestId("pnl-by-business-table"))
        .getByText("政策性金融债")
        .closest("tr");
      expect(policyRow).toHaveTextContent("0.00");
      const policyCells = policyRow?.querySelectorAll("td");
      expect(policyCells).toHaveLength(12);
      // 近零真实值不折叠：-30 元四舍五入为 0，且不出现 "-0"
      expect(policyCells?.[3]?.textContent).toBe("0");
      // 年化收益率 / FTP后收益 缺失时使用 EM_DASH 基元（不再是 "-"）
      expect(policyCells?.[7]).toHaveTextContent("—");
      expect(policyCells?.[8]).toHaveTextContent("—");
      expect(policyCells?.[9]).toHaveTextContent("—");
      expect(screen.getByTestId("pnl-by-business-selected-drilldown")).toHaveTextContent(
        "日均为0，收益率/FTP 暂不计算",
      );
      expect(screen.getByTestId("pnl-by-business-ftp-bridge")).toHaveTextContent("日均为0");
    });
  });

  it("renders ftp bridge copy from backend ftp_rate_pct instead of a hard-coded rate", async () => {
    const client = buildPnlClient();
    const originalYtd = await client.getPnlByBusinessYtd(2025, "2025-12-31");
    client.getPnlByBusinessYtd = vi.fn(async (year: number, asOfDate?: string) => ({
      ...originalYtd,
      result: {
        ...originalYtd.result,
        year,
        period_end_date: asOfDate ?? originalYtd.result.period_end_date,
        items: originalYtd.result.items.map((item) =>
          item.row_key === "asset_zqtz_policy_financial_bond"
            ? {
                ...item,
                ftp_rate_pct: "2.500000",
              }
            : item,
        ),
      },
    }));
    client.getPnlByBusinessAnalysis = vi.fn(
      async (options: {
        year: number;
        asOfDate?: string;
        businessKey?: string;
        dimension: PnlByBusinessAnalysisDimension;
      }) => {
        const payload = await buildPnlClient().getPnlByBusinessAnalysis(options);
        return {
          ...payload,
          result: {
            ...payload.result,
            rows: payload.result.rows.map((row) => ({
              ...row,
              ftp_rate_pct: "2.500000",
            })),
          },
        };
      },
    );

    renderWorkbenchApp(["/pnl-by-business"], { client });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("pnl-by-business-view-mode"), { target: { value: "ytd" } });

    await waitFor(() => {
      const bridge = screen.getByTestId("pnl-by-business-ftp-bridge");
      expect(bridge).toHaveTextContent("2.50%");
      expect(bridge).not.toHaveTextContent("1.6%");
      expect(screen.getByTestId("pnl-by-business-bond-bucket-analysis")).toHaveTextContent("2.50%");
      expect(screen.getByTestId("pnl-by-business-negative-ftp-list")).toHaveTextContent("2.50%");
    });
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
    await waitFor(() => {
      expect(client.getPnlByBusinessAnalysis).toHaveBeenCalledWith({
        year: 2025,
        asOfDate: "2025-12-31",
        businessKey: "asset_zqtz_policy_financial_bond",
        dimension: "instrument",
      });
    });
    const dimensionsBeforeFirstPanelSettles = vi
      .mocked(client.getPnlByBusinessAnalysis)
      .mock.calls.map(([options]) => options.dimension);
    expect(dimensionsBeforeFirstPanelSettles).toEqual(expect.arrayContaining(["bond_bucket", "instrument"]));
    expect(dimensionsBeforeFirstPanelSettles).not.toContain("bond_bucket_monthly");
    expect(dimensionsBeforeFirstPanelSettles).not.toContain("monthly");

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
