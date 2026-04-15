import { screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-routes-echarts-stub" />,
}));

import { createApiClient, type ApiClient } from "../api/client";
import type {
  PnlBridgePayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  ResultMeta,
} from "../api/contracts";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

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
  const data: PnlDataPayload = {
    report_date: "2025-12-31",
    formal_fi_rows: [
      {
        report_date: "2025-12-31",
        instrument_code: "240001.IB",
        portfolio_name: "Route FI",
        cost_center: "cc-route",
        invest_type_std: "T",
        accounting_basis: "FVTPL",
        currency_basis: "CNY",
        interest_income_514: "10.00",
        fair_value_change_516: "1.00",
        capital_gain_517: "2.00",
        manual_adjustment: "0.00",
        total_pnl: "13.00",
        source_version: "sv_route_smoke",
        rule_version: "rv_route_smoke",
        ingest_batch_id: "ib-route",
        trace_id: "tr_route_fi",
      },
    ],
    nonstd_bridge_rows: [],
  };
  const bridge: PnlBridgePayload = {
    report_date: "2025-12-31",
    warnings: [],
    summary: {
      row_count: 1,
      ok_count: 1,
      warning_count: 0,
      error_count: 0,
      total_beginning_dirty_mv: "100.00",
      total_ending_dirty_mv: "110.00",
      total_carry: "1.00",
      total_roll_down: "0.00",
      total_treasury_curve: "0.00",
      total_credit_spread: "0.00",
      total_fx_translation: "0.00",
      total_realized_trading: "2.00",
      total_unrealized_fv: "3.00",
      total_manual_adjustment: "0.00",
      total_explained_pnl: "6.00",
      total_actual_pnl: "6.00",
      total_residual: "0.00",
      quality_flag: "ok",
    },
    rows: [
      {
        report_date: "2025-12-31",
        instrument_code: "240001.IB",
        portfolio_name: "Route Bridge",
        accounting_basis: "FVTPL",
        carry: "1.00",
        roll_down: "0.00",
        treasury_curve: "0.00",
        credit_spread: "0.00",
        fx_translation: "0.00",
        realized_trading: "2.00",
        unrealized_fv: "3.00",
        manual_adjustment: "0.00",
        explained_pnl: "6.00",
        actual_pnl: "6.00",
        residual: "0.00",
        residual_ratio: "0.00",
        quality_flag: "ok",
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
    getFormalPnlData: vi.fn(async () => ({
      result_meta: buildMeta("pnl.data", "tr_route_data"),
      result: data,
    })),
    getPnlBridge: vi.fn(async () => ({
      result_meta: buildMeta("pnl.bridge", "tr_route_bridge"),
      result: bridge,
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
    expect(await screen.findByTestId("pnl-result-meta-panel")).toHaveTextContent("tr_route_data");

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
});
