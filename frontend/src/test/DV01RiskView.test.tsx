import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  DV01ActionPlanPayload,
  DV01LimitConfigStatusPayload,
  DV01MovementPayload,
  DV01ReconciliationPayload,
  DV01RiskPayload,
  Numeric,
  ResultMeta,
} from "../api/contracts";
import { DV01RiskView } from "../features/bond-analytics/components/DV01RiskView";
import { formatRawAsNumeric } from "../utils/format";

type GetBondAnalyticsDv01Risk = (
  reportDate: string,
  options?: { accountingClass?: string; topN?: number; shockBps?: string },
) => Promise<ApiEnvelope<DV01RiskPayload>>;

type GetBondAnalyticsDv01Reconciliation = (
  reportDate: string,
  options?: { accountingClass?: string },
) => Promise<ApiEnvelope<DV01ReconciliationPayload>>;

type GetBondAnalyticsDv01Movement = (
  reportDate: string,
  options?: { accountingClass?: string; topN?: number },
) => Promise<ApiEnvelope<DV01MovementPayload>>;

type GetBondAnalyticsDv01ActionPlan = (
  reportDate: string,
  options?: { accountingClass?: string; topN?: number },
) => Promise<ApiEnvelope<DV01ActionPlanPayload>>;

type GetBondAnalyticsDv01LimitConfigStatus = (
  reportDate: string,
) => Promise<ApiEnvelope<DV01LimitConfigStatusPayload>>;

const yuan = (raw: number, signAware = false) =>
  formatRawAsNumeric({ raw, unit: "yuan", sign_aware: signAware });
const ratio = (raw: number, precision = 2) =>
  formatRawAsNumeric({ raw, unit: "ratio", sign_aware: false, precision });
const dv01 = (raw: number) => formatRawAsNumeric({ raw, unit: "dv01", sign_aware: false });
const bp = (raw: number) => formatRawAsNumeric({ raw, unit: "bp", sign_aware: true });

function resultMeta(): ResultMeta {
  return {
    trace_id: "tr_dv01",
    basis: "formal",
    result_kind: "bond_analytics.dv01_risk",
    formal_use_allowed: true,
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    cache_version: "cv",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

function reconciliationMeta(): ResultMeta {
  return {
    ...resultMeta(),
    trace_id: "tr_dv01_reconciliation",
    result_kind: "bond_analytics.dv01_reconciliation",
  };
}

function movementMeta(): ResultMeta {
  return {
    ...resultMeta(),
    trace_id: "tr_dv01_movement",
    result_kind: "bond_analytics.dv01_movement",
  };
}

function actionPlanMeta(): ResultMeta {
  return {
    ...resultMeta(),
    trace_id: "tr_dv01_action_plan",
    result_kind: "bond_analytics.dv01_action_plan",
  };
}

function limitConfigStatusMeta(): ResultMeta {
  return {
    ...resultMeta(),
    trace_id: "tr_dv01_limit_config_status",
    result_kind: "bond_analytics.dv01_limit_config_status",
  };
}

function payload(overrides: Partial<DV01RiskPayload> = {}): DV01RiskPayload {
  return {
    report_date: "2026-03-31",
    accounting_class: "OCI",
    total_face_value: yuan(10_000_000_000),
    total_market_value: yuan(10_500_000_000),
    face_weighted_modified_duration: ratio(3.43),
    total_dv01: dv01(3_546_830),
    position_count: 574,
    shock_scenarios: [
      {
        scenario_name: "rate_up_10bp",
        shock_bp: bp(10),
        estimated_pnl: yuan(-35_468_300, true),
      },
      {
        scenario_name: "rate_down_10bp",
        shock_bp: bp(-10),
        estimated_pnl: yuan(35_468_300, true),
      },
    ],
    tenor_buckets: [
      {
        tenor_bucket: "3-5Y",
        face_value: yuan(6_000_000_000),
        market_value: yuan(6_200_000_000),
        face_weighted_modified_duration: ratio(3.8),
        dv01: dv01(2_100_000),
        dv01_share: ratio(0.5921, 4),
        position_count: 210,
      },
    ],
    top_bonds: [
      {
        instrument_code: "BOND-1",
        instrument_name: "测试债 01",
        issuer_name: "发行人A",
        rating: "AAA",
        tenor_bucket: "3-5Y",
        accounting_class: "OCI",
        face_value: yuan(1_000_000_000),
        market_value: yuan(1_050_000_000),
        modified_duration: ratio(3.7),
        dv01: dv01(390_000),
        dv01_share: ratio(0.10996, 4),
      },
    ],
    top_issuers: [
      {
        issuer_name: "发行人A",
        face_value: yuan(1_500_000_000),
        market_value: yuan(1_560_000_000),
        face_weighted_modified_duration: ratio(3.65),
        dv01: dv01(580_000),
        dv01_share: ratio(0.1635, 4),
        position_count: 3,
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function reconciliationPayload(
  overrides: Partial<DV01ReconciliationPayload> = {},
): DV01ReconciliationPayload {
  return {
    report_date: "2026-03-31",
    accounting_class: "OCI",
    total_face_value: yuan(3_000_000_000),
    total_market_value: yuan(3_080_000_000),
    face_weighted_modified_duration: ratio(3.2),
    total_dv01: dv01(880_000),
    position_count: 2,
    rows: [
      {
        report_date: "2026-03-31",
        instrument_code: "BOND-1",
        instrument_name: "测试债 01",
        accounting_class: "OCI",
        issuer_name: "发行人A",
        rating: "AAA",
        tenor_bucket: "3-5Y",
        face_value: yuan(1_000_000_000),
        market_value: yuan(1_050_000_000),
        modified_duration: ratio(3.7),
        dv01: dv01(390_000),
        dv01_share: ratio(0.44318, 4),
        source_version: "sv_bond_1",
        rule_version: "rv_bond_1",
        trace_id: "trace_bond_1",
      },
      {
        report_date: "2026-03-31",
        instrument_code: "BOND-2",
        instrument_name: "Beta 对账债",
        accounting_class: "OCI",
        issuer_name: "发行人B",
        rating: "AA+",
        tenor_bucket: "5-7Y",
        face_value: yuan(2_000_000_000),
        market_value: yuan(2_030_000_000),
        modified_duration: ratio(4.1),
        dv01: dv01(490_000),
        dv01_share: ratio(0.55682, 4),
        source_version: "sv_bond_2",
        rule_version: "rv_bond_2",
        trace_id: "trace_bond_2",
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function movementPayload(overrides: Partial<DV01MovementPayload> = {}): DV01MovementPayload {
  return {
    report_date: "2026-03-31",
    previous_report_date: "2026-02-28",
    accounting_class: "OCI",
    source_status: "ready",
    current_total_face_value: yuan(3_000_000_000),
    previous_total_face_value: yuan(2_700_000_000),
    current_total_market_value: yuan(3_080_000_000),
    previous_total_market_value: yuan(2_760_000_000),
    current_face_weighted_modified_duration: ratio(3.2),
    previous_face_weighted_modified_duration: ratio(2.9),
    current_total_dv01: dv01(880_000),
    previous_total_dv01: dv01(760_000),
    delta_dv01: formatRawAsNumeric({ raw: 120_000, unit: "dv01", sign_aware: true }),
    current_position_count: 2,
    previous_position_count: 2,
    attribution: [
      {
        driver_key: "new_position",
        driver_label: "new position",
        dv01_delta: formatRawAsNumeric({ raw: 80_000, unit: "dv01", sign_aware: true }),
        dv01_delta_share: formatRawAsNumeric({ raw: 0.6667, unit: "ratio", sign_aware: true, precision: 4 }),
        position_count: 1,
      },
      {
        driver_key: "duration_change",
        driver_label: "duration change",
        dv01_delta: formatRawAsNumeric({ raw: 40_000, unit: "dv01", sign_aware: true }),
        dv01_delta_share: formatRawAsNumeric({ raw: 0.3333, unit: "ratio", sign_aware: true, precision: 4 }),
        position_count: 1,
      },
    ],
    anomaly_bonds: [
      {
        instrument_code: "BOND-2",
        instrument_name: "Beta reconciliation bond",
        issuer_name: "Issuer B",
        rating: "AA+",
        tenor_bucket: "5-7Y",
        previous_accounting_class: "OCI",
        current_accounting_class: "OCI",
        previous_face_value: yuan(1_500_000_000),
        current_face_value: yuan(2_000_000_000),
        previous_modified_duration: ratio(3.9),
        current_modified_duration: ratio(4.1),
        previous_dv01: dv01(420_000),
        current_dv01: dv01(490_000),
        dv01_delta: formatRawAsNumeric({ raw: 70_000, unit: "dv01", sign_aware: true }),
        estimated_dv01_from_face_duration: dv01(820_000),
        dv01_estimate_gap: formatRawAsNumeric({ raw: -330_000, unit: "dv01", sign_aware: true }),
        reason_label: "face and duration changed",
      },
    ],
    methodology_checks: [
      {
        instrument_code: "BOND-1",
        instrument_name: "Test bond 01",
        issuer_name: "Issuer A",
        rating: "AAA",
        tenor_bucket: "3-5Y",
        previous_accounting_class: "OCI",
        current_accounting_class: "OCI",
        previous_face_value: yuan(900_000_000),
        current_face_value: yuan(1_000_000_000),
        previous_modified_duration: ratio(3.6),
        current_modified_duration: ratio(3.7),
        previous_dv01: dv01(360_000),
        current_dv01: dv01(390_000),
        dv01_delta: formatRawAsNumeric({ raw: 30_000, unit: "dv01", sign_aware: true }),
        estimated_dv01_from_face_duration: dv01(370_000),
        dv01_estimate_gap: formatRawAsNumeric({ raw: 20_000, unit: "dv01", sign_aware: true }),
        reason_label: "methodology gap",
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function actionPlanPayload(overrides: Partial<DV01ActionPlanPayload> = {}): DV01ActionPlanPayload {
  return {
    report_date: "2026-03-31",
    accounting_class: "OCI",
    risk_level: "breach",
    policy_basis: "page_threshold",
    threshold_note: "页面预警阈值，不代表正式限额。",
    limit_source: "page_threshold",
    limit_source_version: "unconfigured",
    limit_rule_version: "rv_dv01_page_threshold_v3",
    limit_effective_date: null,
    total_dv01: dv01(1_150_000),
    limit_dv01: dv01(1_000_000),
    warning_dv01: dv01(900_000),
    limit_usage: ratio(1.15, 2),
    remaining_limit_dv01: formatRawAsNumeric({ raw: -150_000, unit: "dv01", sign_aware: true }),
    dv01_to_reduce: formatRawAsNumeric({ raw: 250_000, unit: "dv01", sign_aware: true }),
    hedge_instrument_label: "DV01 hedge unit",
    hedge_instrument_dv01: dv01(50_000),
    suggested_hedge_units: ratio(5, 2),
    position_count: 12,
    breach_count: 3,
    scenario_breaches: [
      {
        scenario_name: "rate_up_10bp",
        shock_bp: bp(10),
        estimated_loss: yuan(11_500_000, false),
        loss_threshold: yuan(10_000_000, false),
        risk_level: "watch",
      },
      {
        scenario_name: "rate_up_25bp",
        shock_bp: bp(25),
        estimated_loss: yuan(28_750_000, false),
        loss_threshold: yuan(25_000_000, false),
        risk_level: "breach",
      },
    ],
    tenor_actions: [
      {
        tenor_bucket: "7-10Y",
        dv01: dv01(900_000),
        dv01_share: ratio(0.7826, 4),
        suggested_reduction_dv01: formatRawAsNumeric({ raw: 250_000, unit: "dv01", sign_aware: true }),
        position_count: 8,
      },
    ],
    issuer_actions: [
      {
        issuer_name: "发行人A",
        dv01: dv01(700_000),
        dv01_share: ratio(0.6087, 4),
        suggested_reduction_dv01: formatRawAsNumeric({ raw: 250_000, unit: "dv01", sign_aware: true }),
        position_count: 3,
      },
    ],
    bond_actions: [
      {
        instrument_code: "BOND-1",
        instrument_name: "测试债 01",
        issuer_name: "发行人A",
        rating: "AAA",
        tenor_bucket: "7-10Y",
        accounting_class: "OCI",
        face_value: yuan(1_000_000_000),
        market_value: yuan(1_050_000_000),
        modified_duration: ratio(7.2),
        dv01: dv01(390_000),
        dv01_share: ratio(0.3391, 4),
        suggested_reduction_dv01: formatRawAsNumeric({ raw: 135_000, unit: "dv01", sign_aware: true }),
      },
    ],
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function limitConfigStatusPayload(
  overrides: Partial<DV01LimitConfigStatusPayload> = {},
): DV01LimitConfigStatusPayload {
  return {
    report_date: "2026-03-31",
    overall_status: "incomplete",
    acceptance_status: "blocked",
    acceptance_message: "正式 DV01 限额配置验收未通过；待补分类：AC, TPL, all。",
    next_action:
      "请在 bond_dv01_limit_config 治理流补齐 AC, TPL, all 的 accounting_class、limit_dv01、warning_dv01、hedge_target_dv01、limit_source、limit_source_version、limit_rule_version、limit_effective_date。",
    configured_count: 1,
    missing_count: 3,
    invalid_count: 0,
    config_stream: "bond_dv01_limit_config",
    required_accounting_classes: ["AC", "OCI", "TPL", "all"],
    required_fields: [
      "accounting_class",
      "limit_dv01",
      "warning_dv01",
      "hedge_target_dv01",
      "limit_source",
      "limit_source_version",
      "limit_rule_version",
      "limit_effective_date",
    ],
    configured_accounting_classes: ["OCI"],
    missing_accounting_classes: ["AC", "TPL", "all"],
    invalid_accounting_classes: [],
    missing_business_fields_by_class: {
      AC: [
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
      ],
      TPL: [
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
      ],
      all: [
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
      ],
    },
    review_package_command:
      "python -m backend.app.tasks.bond_dv01_limit_config_import --review-package-dir .tmp\\bond_dv01_limit_config_review_package --report-date 2026-03-31",
    dry_run_command:
      "python -m backend.app.tasks.bond_dv01_limit_config_import --config-path .tmp\\bond_dv01_limit_config_review_package\\bond_dv01_limit_config_review_2026-03-31.csv --report-date 2026-03-31 --dry-run",
    rows: [
      {
        accounting_class: "AC",
        status: "missing",
        limit_dv01: dv01(0),
        warning_dv01: dv01(0),
        hedge_target_dv01: dv01(0),
        limit_source: "unconfigured",
        limit_source_version: "unconfigured",
        limit_rule_version: "unconfigured",
        limit_effective_date: null,
        message: "未找到正式 DV01 限额配置。",
      },
      {
        accounting_class: "OCI",
        status: "ready",
        limit_dv01: dv01(1_200_000),
        warning_dv01: dv01(1_000_000),
        hedge_target_dv01: dv01(1_000_000),
        limit_source: "risk_committee_minutes",
        limit_source_version: "risk_minutes_2026_03",
        limit_rule_version: "rv_dv01_limit_policy_v1",
        limit_effective_date: "2026-03-01",
        message: "已接入正式 DV01 限额。",
      },
      {
        accounting_class: "TPL",
        status: "missing",
        limit_dv01: dv01(0),
        warning_dv01: dv01(0),
        hedge_target_dv01: dv01(0),
        limit_source: "unconfigured",
        limit_source_version: "unconfigured",
        limit_rule_version: "unconfigured",
        limit_effective_date: null,
        message: "未找到正式 DV01 限额配置。",
      },
      {
        accounting_class: "all",
        status: "missing",
        limit_dv01: dv01(0),
        warning_dv01: dv01(0),
        hedge_target_dv01: dv01(0),
        limit_source: "unconfigured",
        limit_source_version: "unconfigured",
        limit_rule_version: "unconfigured",
        limit_effective_date: null,
        message: "未找到正式 DV01 限额配置。",
      },
    ],
    warnings: ["部分会计分类未配置正式 DV01 限额。"],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function renderView(
  getDv01Risk: GetBondAnalyticsDv01Risk,
  getDv01Reconciliation: GetBondAnalyticsDv01Reconciliation = vi.fn(async () => ({
    result_meta: reconciliationMeta(),
    result: reconciliationPayload(),
  })),
  getDv01Movement: GetBondAnalyticsDv01Movement = vi.fn(async () => ({
    result_meta: movementMeta(),
    result: movementPayload(),
  })),
  getDv01ActionPlan: GetBondAnalyticsDv01ActionPlan = vi.fn(async () => ({
    result_meta: actionPlanMeta(),
    result: actionPlanPayload(),
  })),
  getDv01LimitConfigStatus: GetBondAnalyticsDv01LimitConfigStatus = vi.fn(async () => ({
    result_meta: limitConfigStatusMeta(),
    result: limitConfigStatusPayload(),
  })),
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const client = {
    ...createApiClient({ mode: "mock" }),
    getBondAnalyticsDv01Risk: getDv01Risk,
    getBondAnalyticsDv01Reconciliation: getDv01Reconciliation,
    getBondAnalyticsDv01Movement: getDv01Movement,
    getBondAnalyticsDv01ActionPlan: getDv01ActionPlan,
    getBondAnalyticsDv01LimitConfigStatus: getDv01LimitConfigStatus,
  };
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <DV01RiskView reportDate="2026-03-31" />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("DV01RiskView", () => {
  it("defaults to OCI and renders KPI, shock, tenor, bond, and issuer sections", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));

    renderView(getDv01Risk);

    await waitFor(() =>
      expect(getDv01Risk).toHaveBeenCalledWith("2026-03-31", {
        accountingClass: "OCI",
        topN: 20,
        shockBps: "1,10,25,50",
      }),
    );

    expect(await screen.findByTestId("dv01-risk-view")).toBeInTheDocument();
    expect(screen.getByTestId("dv01-risk-accounting-class")).toHaveTextContent("OCI");
    expect(screen.getByText("总面值")).toBeInTheDocument();
    expect(screen.getByText("100.00 亿")).toBeInTheDocument();
    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("105.00 亿")).toBeInTheDocument();
    expect(screen.getByText("面值加权修正久期")).toBeInTheDocument();
    expect(screen.getByText("3.43 年")).toBeInTheDocument();
    expect(screen.getByText("总 DV01")).toBeInTheDocument();
    expect(screen.getByText("3,546,830")).toBeInTheDocument();
    expect(screen.getAllByText("持仓数").length).toBeGreaterThan(0);
    expect(screen.getByText("574")).toBeInTheDocument();

    const shockTable = screen.getByTestId("dv01-risk-shocks-table");
    expect(within(shockTable).getByText("rate_up_10bp")).toBeInTheDocument();
    expect(within(shockTable).getByText("-0.35 亿")).toBeInTheDocument();
    expect(within(shockTable).getByText("+0.35 亿")).toBeInTheDocument();

    expect(screen.getByText("期限桶 DV01")).toBeInTheDocument();
    const tenorTable = screen.getByTestId("dv01-risk-tenor-table");
    expect(within(tenorTable).getByText("3-5Y")).toBeInTheDocument();
    expect(within(tenorTable).getByText("3.80 年")).toBeInTheDocument();
    expect(within(tenorTable).getByText("59.21%")).toBeInTheDocument();
    expect(screen.getByText("Top 债券")).toBeInTheDocument();
    const topBondsTable = screen.getByTestId("dv01-risk-top-bonds-table");
    expect(within(topBondsTable).getByText("测试债 01")).toBeInTheDocument();
    expect(within(topBondsTable).getByText("3.70 年")).toBeInTheDocument();
    expect(screen.getByText("Top 发行人")).toBeInTheDocument();
    expect(within(screen.getByTestId("dv01-risk-top-issuers-table")).getByText("发行人A")).toBeInTheDocument();
    expect(within(screen.getByTestId("dv01-risk-top-issuers-table")).getByText("3.65 年")).toBeInTheDocument();
  });

  it("refetches when accounting class or Top N changes", async () => {
    const user = userEvent.setup();
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01Reconciliation = vi.fn(async (_reportDate: string, options?: { accountingClass?: string }) => ({
      result_meta: reconciliationMeta(),
      result: reconciliationPayload({ accounting_class: options?.accountingClass ?? "OCI" }),
    }));
    const getDv01Movement = vi.fn(async (_reportDate: string, options?: { accountingClass?: string }) => ({
      result_meta: movementMeta(),
      result: movementPayload({ accounting_class: options?.accountingClass ?? "OCI" }),
    }));
    const getDv01ActionPlan = vi.fn(async (_reportDate: string, options?: { accountingClass?: string }) => ({
      result_meta: actionPlanMeta(),
      result: actionPlanPayload({ accounting_class: options?.accountingClass ?? "OCI" }),
    }));

    renderView(getDv01Risk, getDv01Reconciliation, getDv01Movement, getDv01ActionPlan);
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDv01Reconciliation).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDv01Movement).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDv01ActionPlan).toHaveBeenCalledTimes(1));

    await user.click(within(screen.getByTestId("dv01-risk-accounting-class")).getByText("全部"));
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(2));
    expect(getDv01Risk.mock.calls[1]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 20, shockBps: "1,10,25,50" },
    ]);
    await waitFor(() => expect(getDv01Reconciliation).toHaveBeenCalledTimes(2));
    expect(getDv01Reconciliation.mock.calls[1]).toEqual([
      "2026-03-31",
      { accountingClass: "all" },
    ]);
    await waitFor(() => expect(getDv01Movement).toHaveBeenCalledTimes(2));
    expect(getDv01Movement.mock.calls[1]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 20 },
    ]);
    await waitFor(() => expect(getDv01ActionPlan).toHaveBeenCalledTimes(2));
    expect(getDv01ActionPlan.mock.calls[1]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 20 },
    ]);

    await user.selectOptions(screen.getByTestId("dv01-risk-topn"), "50");
    await waitFor(() => expect(getDv01Risk).toHaveBeenCalledTimes(3));
    expect(getDv01Risk.mock.calls[2]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 50, shockBps: "1,10,25,50" },
    ]);
    expect(getDv01Reconciliation).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(getDv01Movement).toHaveBeenCalledTimes(3));
    expect(getDv01Movement.mock.calls[2]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 50 },
    ]);
    await waitFor(() => expect(getDv01ActionPlan).toHaveBeenCalledTimes(3));
    expect(getDv01ActionPlan.mock.calls[2]).toEqual([
      "2026-03-31",
      { accountingClass: "all", topN: 50 },
    ]);
  });

  it("renders DV01 action plan risk alerts and hedge sizing", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01ActionPlan = vi.fn(async () => ({
      result_meta: actionPlanMeta(),
      result: actionPlanPayload(),
    }));

    renderView(getDv01Risk, undefined, undefined, getDv01ActionPlan);

    await waitFor(() =>
      expect(getDv01ActionPlan).toHaveBeenCalledWith("2026-03-31", {
        accountingClass: "OCI",
        topN: 20,
      }),
    );
    const panel = await screen.findByTestId("dv01-action-plan-panel");
    expect(panel).toHaveTextContent("DV01 风险动作");
    expect(panel).toHaveTextContent("超限");
    expect(panel).toHaveTextContent("需压降 DV01");
    expect(panel).toHaveTextContent("250,000");
    expect(panel).toHaveTextContent("限额来源");
    expect(panel).toHaveTextContent("page_threshold");
    expect(panel).toHaveTextContent("使用率");
    expect(panel).toHaveTextContent("1.15");
    expect(panel).toHaveTextContent("剩余额度");
    expect(panel).toHaveTextContent("-150,000");
    expect(panel).toHaveTextContent("建议对冲手数");
    expect(panel).toHaveTextContent("5.00");
    expect(within(panel).getByTestId("dv01-action-plan-scenarios-table")).toHaveTextContent("rate_up_25bp");
    expect(within(panel).getByTestId("dv01-action-plan-tenors-table")).toHaveTextContent("7-10Y");
    expect(within(panel).getByTestId("dv01-action-plan-issuers-table")).toHaveTextContent("发行人A");
    expect(within(panel).getByTestId("dv01-action-plan-bonds-table")).toHaveTextContent("BOND-1");
  });

  it("renders DV01 formal limit configuration status for the selected accounting class", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01LimitConfigStatus = vi.fn(async () => ({
      result_meta: limitConfigStatusMeta(),
      result: limitConfigStatusPayload(),
    }));

    renderView(getDv01Risk, undefined, undefined, undefined, getDv01LimitConfigStatus);

    await waitFor(() => expect(getDv01LimitConfigStatus).toHaveBeenCalledWith("2026-03-31"));
    const panel = await screen.findByTestId("dv01-limit-config-status-panel");
    expect(panel).toHaveTextContent("限额配置状态");
    expect(panel).toHaveTextContent("整体未完成");
    expect(panel).toHaveTextContent("OCI");
    expect(panel).toHaveTextContent("已配置");
    expect(panel).toHaveTextContent("risk_committee_minutes");
    expect(panel).toHaveTextContent("risk_minutes_2026_03");
    expect(panel).toHaveTextContent("1,200,000");
    expect(panel).toHaveTextContent("正式配置流");
    expect(panel).toHaveTextContent("bond_dv01_limit_config");
    expect(panel).toHaveTextContent("待补分类");
    expect(panel).toHaveTextContent("AC、TPL、all");
    expect(panel).toHaveTextContent("必填字段");
    expect(panel).toHaveTextContent("limit_dv01");
    expect(panel).toHaveTextContent("验收结论");
    expect(panel).toHaveTextContent("未通过");
    expect(panel).toHaveTextContent("已接入分类");
    expect(panel).toHaveTextContent("验收说明");
    expect(panel).toHaveTextContent("下一步动作");
    expect(panel).toHaveTextContent("limit_effective_date");
    expect(panel).toHaveTextContent("业务验收清单");
    expect(panel).toHaveTextContent("填写业务文件");
    expect(panel).toHaveTextContent("不要导入 sample_do_not_import.csv");
    expect(panel).toHaveTextContent("bond_dv01_limit_config_review_2026-03-31_sample_do_not_import.csv");
    expect(panel).toHaveTextContent("业务批准后再填写正式限额字段");
    expect(panel).toHaveTextContent("补齐分类 AC、TPL、all");
    expect(panel).toHaveTextContent("accounting_class 只允许 AC、OCI、TPL、all");
    expect(panel).toHaveTextContent("补齐字段 limit_dv01");
    expect(panel).toHaveTextContent("limit_dv01、warning_dv01、hedge_target_dv01 必须大于 0");
    expect(panel).toHaveTextContent("阈值顺序 hedge_target_dv01 <= warning_dv01 <= limit_dv01");
    expect(panel).toHaveTextContent("limit_effective_date 使用 ISO 日期");
    expect(panel).toHaveTextContent("先执行 dry-run");
    expect(panel).toHaveTextContent("期望 status=validated");
    expect(panel).toHaveTextContent("import_readiness_status=ready_for_import");
    expect(panel).toHaveTextContent("validation_errors 为空");
    expect(panel).toHaveTextContent("records_written=0");
    expect(panel).toHaveTextContent("复核 limit_utilization_preview.summary.highest_severity_status");
    expect(panel).toHaveTextContent("missing_business_fields_by_class");
    expect(panel).toHaveTextContent("AC: limit_dv01");
    expect(panel).toHaveTextContent("review_package_command");
    expect(panel).toHaveTextContent("--review-package-dir");
    expect(panel).toHaveTextContent("dry_run_command");
    expect(panel).toHaveTextContent("业务填写文件");
    expect(panel).toHaveTextContent("bond_dv01_limit_config_review_2026-03-31.csv");
    expect(panel).toHaveTextContent("--dry-run");
    expect(panel).toHaveTextContent("check_status_command");
    expect(panel).toHaveTextContent("--check-status");
  });

  it("renders fallback business review commands for legacy DV01 limit status payloads", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const {
      acceptance_status: _acceptanceStatus,
      acceptance_message: _acceptanceMessage,
      next_action: _nextAction,
      configured_accounting_classes: _configuredAccountingClasses,
      missing_business_fields_by_class: _missingBusinessFieldsByClass,
      review_package_command: _reviewPackageCommand,
      dry_run_command: _dryRunCommand,
      ...legacyLimitStatus
    } = limitConfigStatusPayload({
      configured_count: 0,
      missing_count: 4,
      missing_accounting_classes: ["AC", "OCI", "TPL", "all"],
      rows: ["AC", "OCI", "TPL", "all"].map((accountingClass) => ({
        accounting_class: accountingClass,
        status: "missing" as const,
        limit_dv01: dv01(0),
        warning_dv01: dv01(0),
        hedge_target_dv01: dv01(0),
        limit_source: "unconfigured",
        limit_source_version: "unconfigured",
        limit_rule_version: "unconfigured",
        limit_effective_date: null,
        message: "未找到正式 DV01 限额配置。",
      })),
    });
    const getDv01LimitConfigStatus = vi.fn(async () => ({
      result_meta: limitConfigStatusMeta(),
      result: legacyLimitStatus as unknown as DV01LimitConfigStatusPayload,
    }));

    renderView(getDv01Risk, undefined, undefined, undefined, getDv01LimitConfigStatus);

    const panel = await screen.findByTestId("dv01-limit-config-status-panel");
    expect(panel).toHaveTextContent("未通过");
    expect(panel).toHaveTextContent("AC: accounting_class");
    expect(panel).toHaveTextContent("review_package_command");
    expect(panel).toHaveTextContent("--review-package-dir");
    expect(panel).toHaveTextContent("dry_run_command");
    expect(panel).toHaveTextContent("业务填写文件");
    expect(panel).toHaveTextContent("bond_dv01_limit_config_review_2026-03-31.csv");
    expect(panel).toHaveTextContent("--dry-run");
    expect(panel).toHaveTextContent("check_status_command");
    expect(panel).toHaveTextContent("--check-status");
  });

  it("renders DV01 formal limit acceptance as ready when all classes are configured", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01LimitConfigStatus = vi.fn(async () => ({
      result_meta: limitConfigStatusMeta(),
      result: limitConfigStatusPayload({
        overall_status: "ready",
        acceptance_status: "ready",
        acceptance_message: "正式 DV01 限额配置验收通过。",
        next_action: "无需补充配置；动作计划将按正式限额口径计算。",
        configured_count: 4,
        missing_count: 0,
        invalid_count: 0,
        configured_accounting_classes: ["AC", "OCI", "TPL", "all"],
        missing_accounting_classes: [],
        invalid_accounting_classes: [],
        missing_business_fields_by_class: {},
        review_package_command: "",
        dry_run_command: "",
        warnings: [],
        rows: ["AC", "OCI", "TPL", "all"].map((accountingClass) => ({
          accounting_class: accountingClass,
          status: "ready" as const,
          limit_dv01: dv01(1_200_000),
          warning_dv01: dv01(1_000_000),
          hedge_target_dv01: dv01(1_000_000),
          limit_source: "risk_committee_minutes",
          limit_source_version: `risk_minutes_2026_03_${accountingClass}`,
          limit_rule_version: "rv_dv01_limit_policy_v1",
          limit_effective_date: "2026-03-01",
          message: "已接入正式 DV01 限额。",
        })),
      }),
    }));

    renderView(getDv01Risk, undefined, undefined, undefined, getDv01LimitConfigStatus);

    const panel = await screen.findByTestId("dv01-limit-config-status-panel");
    expect(panel).toHaveTextContent("验收结论");
    expect(panel).toHaveTextContent("已通过");
    expect(panel).toHaveTextContent("验收说明");
    expect(panel).toHaveTextContent("无需补充配置");
    expect(panel).toHaveTextContent("待补分类");
    expect(panel).toHaveTextContent("无");
    expect(panel).toHaveTextContent("AC、OCI、TPL、all");
  });

  it("renders formal DV01 limit source version and effective date", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01ActionPlan = vi.fn(async () => ({
      result_meta: actionPlanMeta(),
      result: actionPlanPayload({
        policy_basis: "formal_limit",
        threshold_note: "已接入正式 DV01 限额。",
        limit_source: "risk_committee_minutes",
        limit_source_version: "risk_minutes_2026_03",
        limit_rule_version: "rv_dv01_limit_policy_v1",
        limit_effective_date: "2026-03-01",
        limit_usage: ratio(0.64, 2),
        remaining_limit_dv01: formatRawAsNumeric({ raw: 650_000, unit: "dv01", sign_aware: true }),
      }),
    }));

    renderView(getDv01Risk, undefined, undefined, getDv01ActionPlan);

    const panel = await screen.findByTestId("dv01-action-plan-panel");
    expect(panel).toHaveTextContent("已接入正式 DV01 限额");
    expect(panel).toHaveTextContent("risk_committee_minutes");
    expect(panel).toHaveTextContent("risk_minutes_2026_03");
    expect(panel).toHaveTextContent("rv_dv01_limit_policy_v1");
    expect(panel).toHaveTextContent("2026-03-01");
    expect(panel).toHaveTextContent("0.64");
    expect(panel).toHaveTextContent("650,000");
  });

  it("keeps DV01 action plan limit metadata visible when there are no action rows", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01ActionPlan = vi.fn(async () => ({
      result_meta: actionPlanMeta(),
      result: actionPlanPayload({
        risk_level: "no_data",
        breach_count: 0,
        position_count: 0,
        total_dv01: dv01(0),
        limit_usage: ratio(0, 2),
        remaining_limit_dv01: formatRawAsNumeric({ raw: 1_000_000, unit: "dv01", sign_aware: true }),
        scenario_breaches: [],
        tenor_actions: [],
        issuer_actions: [],
        bond_actions: [],
      }),
    }));

    renderView(getDv01Risk, undefined, undefined, getDv01ActionPlan);

    const panel = await screen.findByTestId("dv01-action-plan-panel");
    expect(panel).toHaveTextContent("该报告日/分类暂无债券 DV01 风险动作数据");
    expect(panel).toHaveTextContent("限额来源");
    expect(panel).toHaveTextContent("page_threshold");
    expect(panel).toHaveTextContent("使用率");
    expect(panel).toHaveTextContent("0.00");
    expect(panel).toHaveTextContent("剩余额度");
    expect(panel).toHaveTextContent("1,000,000");
  });

  it("renders movement attribution, anomaly bonds, and methodology checks", async () => {
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01Reconciliation = vi.fn(async () => ({
      result_meta: reconciliationMeta(),
      result: reconciliationPayload(),
    }));
    const getDv01Movement = vi.fn(async () => ({
      result_meta: movementMeta(),
      result: movementPayload(),
    }));

    renderView(getDv01Risk, getDv01Reconciliation, getDv01Movement);

    await waitFor(() =>
      expect(getDv01Movement).toHaveBeenCalledWith("2026-03-31", {
        accountingClass: "OCI",
        topN: 20,
      }),
    );
    const panel = await screen.findByTestId("dv01-movement-panel");
    expect(within(panel).getByTestId("dv01-movement-attribution-table")).toHaveTextContent("new position");
    expect(within(panel).getByTestId("dv01-movement-attribution-table")).toHaveTextContent("80,000");
    expect(within(panel).getByTestId("dv01-movement-anomaly-table")).toHaveTextContent("BOND-2");
    expect(within(panel).getByTestId("dv01-movement-anomaly-table")).toHaveTextContent("70,000");
    expect(within(panel).getByTestId("dv01-methodology-check-table")).toHaveTextContent("BOND-1");
    expect(within(panel).getByTestId("dv01-methodology-check-table")).toHaveTextContent("370,000");
  });

  it("renders bond-level reconciliation and filters rows on the frontend", async () => {
    const user = userEvent.setup();
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload(),
    }));
    const getDv01Reconciliation = vi.fn(async () => ({
      result_meta: reconciliationMeta(),
      result: reconciliationPayload(),
    }));

    renderView(getDv01Risk, getDv01Reconciliation);

    await waitFor(() =>
      expect(getDv01Reconciliation).toHaveBeenCalledWith("2026-03-31", {
        accountingClass: "OCI",
      }),
    );
    const panel = await screen.findByTestId("dv01-reconciliation-panel");
    expect(panel).toHaveTextContent("单券明细对账");
    expect(panel).toHaveTextContent("后端合计");
    expect(panel).toHaveTextContent("当前筛选 2 / 2");
    const table = within(panel).getByTestId("dv01-reconciliation-table");
    expect(within(table).getByText("BOND-1")).toBeInTheDocument();
    expect(within(table).getByText("BOND-2")).toBeInTheDocument();
    expect(within(table).getByText("trace_bond_1")).toBeInTheDocument();

    await user.type(screen.getByTestId("dv01-reconciliation-search"), "Beta");

    await waitFor(() => expect(panel).toHaveTextContent("当前筛选 1 / 2"));
    expect(within(table).getByText("BOND-2")).toBeInTheDocument();
    expect(within(table).queryByText("BOND-1")).not.toBeInTheDocument();
  });

  it("shows the governed empty state without deriving frontend metrics", async () => {
    const zero = (unit: Numeric["unit"]) =>
      formatRawAsNumeric({ raw: 0, unit, sign_aware: false });
    const getDv01Risk = vi.fn(async () => ({
      result_meta: resultMeta(),
      result: payload({
        total_face_value: zero("yuan"),
        total_market_value: zero("yuan"),
        face_weighted_modified_duration: zero("ratio"),
        total_dv01: zero("dv01"),
        position_count: 0,
        shock_scenarios: [],
        tenor_buckets: [],
        top_bonds: [],
        top_issuers: [],
        warnings: ["no formal bond analytics rows"],
      }),
    }));
    const getDv01Reconciliation = vi.fn(async () => ({
      result_meta: reconciliationMeta(),
      result: reconciliationPayload({
        total_face_value: zero("yuan"),
        total_market_value: zero("yuan"),
        face_weighted_modified_duration: zero("ratio"),
        total_dv01: zero("dv01"),
        position_count: 0,
        rows: [],
        warnings: ["no formal bond analytics rows"],
      }),
    }));

    renderView(getDv01Risk, getDv01Reconciliation);

    expect(await screen.findByText("该报告日/分类暂无债券 DV01 数据")).toBeInTheDocument();
    expect(screen.queryByTestId("dv01-risk-shocks-table")).not.toBeInTheDocument();
    expect(await screen.findByText("该报告日/分类暂无债券 DV01 明细数据")).toBeInTheDocument();
  });
});
