import { screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-routes-echarts-stub" />,
}));

import { createApiClient, type ApiClient } from "../api/client";
import type {
  Numeric,
  PnlBridgePayload,
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
    report_dates: ["2025-12-31"],
    formal_fi_report_dates: ["2025-12-31"],
    nonstd_bridge_report_dates: ["2025-12-31"],
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
    total_pnl: "13.00",
    source_tables: ["data_input/pnl", "fact_formal_zqtz_balance_daily"],
    items: [
      {
        business_type: "政策性金融债",
        interest_income: "10.00",
        fair_value_change: "1.00",
        capital_gain: "2.00",
        total_pnl: "13.00",
        proportion: "1.000000",
        assets_count: 1,
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
    getPnlByBusinessYtd: vi.fn(async () => ({
      result_meta: buildMeta("pnl.by_business_ytd", "tr_route_business_ytd"),
      result: byBusinessYtd,
    })),
    getPnlYearlyBusinessSummary: vi.fn(async () => ({
      result_meta: buildMeta("pnl.yearly_summary", "tr_route_business_year"),
      result: yearlyBusiness,
    })),
  };
}

describe("pnl routed pages smoke", () => {
  it("renders the real /pnl route surface through workbench routes", async () => {
    renderWorkbenchApp(["/pnl"], { client: buildPnlClient() });

    expect(await screen.findByTestId("pnl-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-report-date")).toHaveValue("2025-12-31");
    });
    expect(await screen.findByTestId("pnl-refresh-button")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent("tr_route_data");
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-overview-cards")).toHaveTextContent("13.00");
      expect(screen.getByTestId("pnl-formal-fi-table")).toHaveTextContent("240001.IB");
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
    renderWorkbenchApp(["/pnl-by-business"], { client: buildPnlClient() });

    expect(await screen.findByTestId("pnl-by-business-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("pnl-by-business-report-date")).toHaveValue("2025-12-31");
    });
    expect(await screen.findByTestId("pnl-by-business-result-meta-panel")).toHaveTextContent("tr_route_business_ytd");

    await waitFor(() => {
      expect(screen.getByTestId("pnl-by-business-summary-cards")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("政策性金融债");
      expect(screen.getByTestId("pnl-by-business-table")).toHaveTextContent("100.00%");
    });
  });
});
