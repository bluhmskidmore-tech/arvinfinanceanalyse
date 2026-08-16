import { describe, expect, expectTypeOf, it } from "vitest";

import { buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison } from "../mocks/ledgerPnlMocks";
import {
  buildCandidatePeriodComparisonViewModel,
  formatCandidateComparisonAmount,
  formatCandidateComparisonRate,
  summarizeCandidateComparisonReasons,
} from "../features/ledger-pnl/models/candidatePeriodComparisonModel";

function mutableSyntheticComparison() {
  return structuredClone(
    buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison("202606"),
  );
}

function syntheticBridgePayload() {
  const payload = mutableSyntheticComparison();
  const record = payload as unknown as Record<string, unknown>;
  record.contract_version = "candidate-financial-indicator-period-comparison-v2";
  record.net_interest_component_bridge = {
    analysis_kind: "accounting_component_bridge",
    status: "available",
    metric_id: "income.interest.net",
    basis: "calendar_month_from_cumulative",
    method: "finance_metric_component_contribution",
    unit: "亿元",
    quality_status: "degraded_candidate",
    foot_status: "passed",
    net_delta_yi: "2.5000",
    component_contribution_total_yi: "2.5000",
    reconciliation_delta_yi: "0.0000",
    reasons: [],
    components: [
      {
        metric_id: "income.interest.loan.total",
        metric_name: "贷款利息收入",
        formula_weight: 1,
        current_metric_status: "ok",
        previous_metric_status: "ok",
        two_month_prior_metric_status: "ok",
        current_value_yi: "11.0000",
        previous_value_yi: "10.0000",
        current_source_value_yi: "50.0000",
        previous_source_value_yi: "39.0000",
        two_month_prior_source_value_yi: "29.0000",
        component_delta_yi: "1.0000",
        contribution_to_net_delta_yi: "1.0000",
        reasons: [],
      },
      {
        metric_id: "expense.interest.deposit.total",
        metric_name: "存款利息支出",
        formula_weight: -1,
        current_metric_status: "ok",
        previous_metric_status: "ok",
        two_month_prior_metric_status: "ok",
        current_value_yi: "6.0000",
        previous_value_yi: "5.5000",
        current_source_value_yi: "30.0000",
        previous_source_value_yi: "24.0000",
        two_month_prior_source_value_yi: "18.5000",
        component_delta_yi: "0.5000",
        contribution_to_net_delta_yi: "-0.5000",
        reasons: [],
      },
      {
        metric_id: "income.interest.investment",
        metric_name: "金融投资利息收入",
        formula_weight: 1,
        current_metric_status: "ok",
        previous_metric_status: "ok",
        two_month_prior_metric_status: "ok",
        current_value_yi: "6.0000",
        previous_value_yi: "4.5000",
        current_source_value_yi: "25.0000",
        previous_source_value_yi: "19.0000",
        two_month_prior_source_value_yi: "14.5000",
        component_delta_yi: "1.5000",
        contribution_to_net_delta_yi: "1.5000",
        reasons: [],
      },
      {
        metric_id: "income.interest.interbank_net",
        metric_name: "同业资产负债利息净收入",
        formula_weight: 1,
        current_metric_status: "ok",
        previous_metric_status: "ok",
        two_month_prior_metric_status: "ok",
        current_value_yi: "1.5000",
        previous_value_yi: "1.0000",
        current_source_value_yi: "10.0000",
        previous_source_value_yi: "8.5000",
        two_month_prior_source_value_yi: "7.5000",
        component_delta_yi: "0.5000",
        contribution_to_net_delta_yi: "0.5000",
        reasons: [],
      },
    ],
  };
  return payload;
}

function bridgeRecord(payload = syntheticBridgePayload()) {
  return (payload as unknown as Record<string, unknown>)
    .net_interest_component_bridge as Record<string, unknown>;
}

describe("candidate period comparison view model", () => {
  it("keeps the frontend comparison contract aligned with the active backend v2 schema", () => {
    const payload = mutableSyntheticComparison();

    expectTypeOf(payload.contract_version).toEqualTypeOf<
      "candidate-financial-indicator-period-comparison-v2"
    >();
    expect(payload.contract_version).toBe(
      "candidate-financial-indicator-period-comparison-v2",
    );
  });

  it("accepts v2 and exposes the backend four-item net-interest bridge without recalculation", () => {
    const payload = syntheticBridgePayload();
    const bridge = bridgeRecord(payload);
    const components = bridge.components as Array<Record<string, unknown>>;
    components[0] = {
      ...components[0],
      current_value_yi: "999.0000",
      previous_value_yi: "1.0000",
      component_delta_yi: "88.8888",
      contribution_to_net_delta_yi: "1.23456",
    };

    const model = buildCandidatePeriodComparisonViewModel(payload, "202606");

    expect(model).toMatchObject({
      status: "ready",
      netInterestBridge: {
        status: "available",
        netDeltaDisplay: "+2.5000",
        footLabel: "勾稽通过",
      },
    });
    if (model.status !== "ready" || model.netInterestBridge.status !== "available") {
      throw new Error("expected an available bridge view model");
    }
    expect(model.netInterestBridge.rows[0]).toMatchObject({
      metricId: "income.interest.loan.total",
      currentDisplay: "999.0000",
      previousDisplay: "1.0000",
      componentDeltaDisplay: "+88.8888",
      contributionDisplay: "+1.2346",
    });
    expect(model.netInterestBridge.rows[1]).toMatchObject({
      metricId: "expense.interest.deposit.total",
      contributionDisplay: "−0.5000",
    });
  });

  it.each([
    ["乱序", (bridge: Record<string, unknown>) => {
      const components = bridge.components as unknown[];
      [components[0], components[1]] = [components[1], components[0]];
    }],
    ["错误权重", (bridge: Record<string, unknown>) => {
      const components = bridge.components as Array<Record<string, unknown>>;
      components[1].formula_weight = 1;
    }],
    ["NaN", (bridge: Record<string, unknown>) => {
      const components = bridge.components as Array<Record<string, unknown>>;
      components[0].contribution_to_net_delta_yi = "NaN";
    }],
    ["错误单位", (bridge: Record<string, unknown>) => {
      bridge.unit = "万元";
    }],
    ["通过但勾稽差额非零", (bridge: Record<string, unknown>) => {
      bridge.reconciliation_delta_yi = "0.0001";
    }],
  ])("fails closed for a malformed bridge: %s", (_caseName, mutate) => {
    const payload = syntheticBridgePayload();
    mutate(bridgeRecord(payload));

    expect(buildCandidatePeriodComparisonViewModel(payload, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });
  });

  it("fails closed when bridge totals contradict the outer net-interest delta", () => {
    const wrongOuterDelta = syntheticBridgePayload();
    bridgeRecord(wrongOuterDelta).net_delta_yi = "2.4000";
    expect(buildCandidatePeriodComparisonViewModel(wrongOuterDelta, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });

    const wrongBridgeTotal = syntheticBridgePayload();
    bridgeRecord(wrongBridgeTotal).component_contribution_total_yi = "2.4000";
    expect(buildCandidatePeriodComparisonViewModel(wrongBridgeTotal, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });
  });

  it("exposes a quiet not-evaluable bridge state without partial contribution rows", () => {
    const payload = syntheticBridgePayload();
    const bridge = bridgeRecord(payload);
    bridge.status = "not_evaluable";
    bridge.quality_status = "not_evaluable";
    bridge.foot_status = "not_evaluable";
    bridge.net_delta_yi = null;
    bridge.component_contribution_total_yi = null;
    bridge.reconciliation_delta_yi = null;
    bridge.reasons = ["component_metric_status_not_ok"];
    bridge.components = (bridge.components as Array<Record<string, unknown>>).map((component) => ({
      ...component,
      current_value_yi: null,
      previous_value_yi: null,
      component_delta_yi: null,
      contribution_to_net_delta_yi: null,
      reasons: ["metric_status_not_ok"],
    }));

    expect(buildCandidatePeriodComparisonViewModel(payload, "202606")).toMatchObject({
      status: "ready",
      netInterestBridge: {
        status: "not_evaluable",
        rows: [],
      },
    });
  });

  it("fails closed when an available bridge contradicts an unavailable outer net-interest metric", () => {
    const payload = syntheticBridgePayload();
    payload.metrics[0] = {
      ...payload.metrics[0],
      comparison_status: "not_comparable",
      current_metric_status: "warning",
      previous_metric_status: "missing",
      two_month_prior_metric_status: "missing",
      current_value_yi: null,
      previous_value_yi: null,
      delta_yi: null,
      change_rate: null,
      rate_reason: "metric_status_not_ok",
      reasons: ["net_interest_metric_status_not_ok"],
      quality_status: "not_comparable",
    };

    expect(buildCandidatePeriodComparisonViewModel(payload, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });
  });

  it("marks a failed backend foot separately and exposes only its reconciliation difference", () => {
    const payload = syntheticBridgePayload();
    const bridge = bridgeRecord(payload);
    bridge.status = "not_evaluable";
    bridge.quality_status = "not_evaluable";
    bridge.foot_status = "failed";
    bridge.component_contribution_total_yi = "1.5000";
    bridge.reconciliation_delta_yi = "1.0000";
    bridge.reasons = ["net_interest_component_reconciliation_failed"];

    expect(buildCandidatePeriodComparisonViewModel(payload, "202606")).toMatchObject({
      status: "ready",
      netInterestBridge: {
        status: "failed",
        reconciliationDisplay: "+1.0000",
        rows: [],
      },
    });
  });

  it("uses backend delta and rate strings without deriving them from current and previous values", () => {
    const payload = mutableSyntheticComparison();
    payload.metrics[0] = {
      ...payload.metrics[0],
      current_value_yi: "100.0000",
      previous_value_yi: "10.0000",
      delta_yi: "-1.23456",
      change_rate: "0.777777",
    };
    payload.net_interest_component_bridge = {
      ...payload.net_interest_component_bridge,
      net_delta_yi: "-1.23456",
      component_contribution_total_yi: "-1.23456",
    };

    const model = buildCandidatePeriodComparisonViewModel(payload, "202606");

    expect(model.status).toBe("ready");
    if (model.status !== "ready") throw new Error("expected a ready view model");
    expect(model.headline).toBe("5项可比、2项暂不可比（降级候选）");
    expect(model.rows[0]).toMatchObject({
      metricId: "income.interest.net",
      currentDisplay: "100.0000",
      previousDisplay: "10.0000",
      deltaDisplay: "−1.2346",
      rateDisplay: "+77.78%",
      basisLabel: "自然月单月环比",
    });
  });

  it("keeps real zero distinct from null and rejects undefined or NaN-like decimal fields", () => {
    expect(formatCandidateComparisonAmount("0", { signed: true })).toBe("0.0000");
    expect(formatCandidateComparisonRate("0")).toBe("0.00%");
    expect(formatCandidateComparisonAmount(null)).toBe("—");
    expect(formatCandidateComparisonAmount(undefined as never)).toBe("契约错误");
    expect(formatCandidateComparisonAmount("NaN" as never)).toBe("契约错误");

    const missingField = mutableSyntheticComparison() as unknown as Record<string, unknown>;
    delete (missingField.metrics as Array<Record<string, unknown>>)[0].delta_yi;
    expect(buildCandidatePeriodComparisonViewModel(missingField, "202606")).toMatchObject({
      status: "invalid_contract",
    });

    const nanField = mutableSyntheticComparison();
    nanField.metrics[0].delta_yi = "NaN";
    expect(buildCandidatePeriodComparisonViewModel(nanField, "202606")).toMatchObject({
      status: "invalid_contract",
    });
  });

  it("rounds Decimal strings across half-up, tiny ratios, negative zero, carry, and huge values", () => {
    expect(formatCandidateComparisonAmount("1.23445")).toBe("1.2345");
    expect(formatCandidateComparisonRate("0.0000001")).toBe("+0.00%");
    expect(formatCandidateComparisonRate("-0.0000001")).toBe("−0.00%");
    expect(formatCandidateComparisonAmount("-0.0000", { signed: true })).toBe("0.0000");
    expect(formatCandidateComparisonRate("-0")).toBe("0.00%");
    expect(formatCandidateComparisonAmount("999.99995")).toBe("1,000.0000");
    expect(formatCandidateComparisonAmount(
      "123456789012345678901234567890.12345",
    )).toBe("123,456,789,012,345,678,901,234,567,890.1235");
  });

  it("fails closed when the response month or fixed metric order does not match the request", () => {
    const wrongMonth = mutableSyntheticComparison();
    wrongMonth.report_month = "202605";
    expect(buildCandidatePeriodComparisonViewModel(wrongMonth, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "wrong_report_month",
    });

    const wrongOrder = mutableSyntheticComparison();
    [wrongOrder.metrics[0], wrongOrder.metrics[1]] = [
      wrongOrder.metrics[1],
      wrongOrder.metrics[0],
    ];
    expect(buildCandidatePeriodComparisonViewModel(wrongOrder, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });
  });

  it("fails closed when a full-scope gap reason conflicts with the envelope reason", () => {
    const payload = mutableSyntheticComparison();
    payload.full_scope_reason_code = "source_parse_error";

    expect(buildCandidatePeriodComparisonViewModel(payload, "202606")).toMatchObject({
      status: "invalid_contract",
      reason: "malformed_payload",
    });
  });

  it("preserves unavailable values as placeholders with backend evidence reasons", () => {
    const model = buildCandidatePeriodComparisonViewModel(
      mutableSyntheticComparison(),
      "202606",
    );

    expect(model.status).toBe("ready");
    if (model.status !== "ready") throw new Error("expected a ready view model");
    expect(model.rows[1]).toMatchObject({
      metricId: "income.noninterest.total",
      comparisonStatus: "not_comparable",
      currentDisplay: "—",
      previousDisplay: "—",
      deltaDisplay: "—",
      rateDisplay: "—",
    });
    expect(model.rows[1].reason).toBe(
      "指标依赖包含待补手工项和缺失总账科目，跨期结果暂不可比。",
    );
    expect(model.fullScopeGaps[0]).toMatchObject({
      month: "202605",
      sourceLabel: "日均源",
      reasonLabel: "缺少工作表：微贷",
    });
    expect(model.hasUnlockedHistoricalSource).toBe(true);
  });

  it("surfaces the backend standard candidate when all three source hashes are locked", () => {
    const payload = mutableSyntheticComparison();
    payload.source_periods = payload.source_periods.map((period) => ({
      ...period,
      locked_sha256: period.ledger_sha256,
      lock_status: "locked_match" as const,
    }));
    payload.metrics = payload.metrics.map((metric) => (
      metric.comparison_status === "comparable"
        ? { ...metric, quality_status: "standard_candidate" as const }
        : metric
    ));
    payload.net_interest_component_bridge = {
      ...payload.net_interest_component_bridge,
      quality_status: "standard_candidate",
    };

    const model = buildCandidatePeriodComparisonViewModel(payload, "202606");

    expect(model.status).toBe("ready");
    if (model.status !== "ready") throw new Error("expected a ready view model");
    expect(model.headline).toBe("5项标准候选、2项暂不可比");
    expect(model.hasUnlockedHistoricalSource).toBe(false);
    expect(model.rows[0].qualityLabel).toBe("标准候选");
  });

  it("explains a null comparable rate when the backend marks a zero denominator", () => {
    const payload = mutableSyntheticComparison();
    payload.metrics[0].change_rate = null;
    payload.metrics[0].rate_reason = "zero_denominator";

    const model = buildCandidatePeriodComparisonViewModel(payload, "202606");

    expect(model.status).toBe("ready");
    if (model.status !== "ready") throw new Error("expected a ready view model");
    expect(model.rows[0]).toMatchObject({
      rateDisplay: "—",
      reason: "上期值为零，环比率不适用。",
    });
  });

  it("summarizes nested backend reason tokens without inventing account or driver detail", () => {
    const both = summarizeCandidateComparisonReasons([
      "current:status=warning",
      "current:manual_required_not_supplied",
      "previous:status=warning",
      "previous:missing_account:main:cumulative:level1:DEMO_ACCOUNT",
      "two_month_prior:status=warning",
    ]);
    expect(both).toBe(
      "指标依赖包含待补手工项和缺失总账科目，跨期结果暂不可比。",
    );
    expect(both).not.toContain("DEMO_ACCOUNT");
    expect(summarizeCandidateComparisonReasons([
      "current:status=warning",
      "current:manual_required_not_supplied",
    ])).toBe("指标依赖包含待补手工项，跨期结果暂不可比。");
    expect(summarizeCandidateComparisonReasons([
      "previous:status=warning",
      "previous:missing_account:main:cumulative:level1:DEMO_ACCOUNT",
    ])).toBe("指标依赖包含缺失总账科目，跨期结果暂不可比。");
    expect(summarizeCandidateComparisonReasons([
      "current:status=warning",
      "current:dependency_status_not_ok",
    ])).toBe("连续月份指标状态未通过，跨期结果暂不可比。");
  });
});
