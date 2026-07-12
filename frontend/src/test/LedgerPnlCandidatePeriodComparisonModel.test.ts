import { describe, expect, it } from "vitest";

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

describe("candidate period comparison view model", () => {
  it("uses backend delta and rate strings without deriving them from current and previous values", () => {
    const payload = mutableSyntheticComparison();
    payload.metrics[0] = {
      ...payload.metrics[0],
      current_value_yi: "100.0000",
      previous_value_yi: "10.0000",
      delta_yi: "-1.23456",
      change_rate: "0.777777",
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
    expect(formatCandidateComparisonAmount(null)).toBe("--");
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
      currentDisplay: "--",
      previousDisplay: "--",
      deltaDisplay: "--",
      rateDisplay: "--",
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

  it("explains a null comparable rate when the backend marks a zero denominator", () => {
    const payload = mutableSyntheticComparison();
    payload.metrics[0].change_rate = null;
    payload.metrics[0].rate_reason = "zero_denominator";

    const model = buildCandidatePeriodComparisonViewModel(payload, "202606");

    expect(model.status).toBe("ready");
    if (model.status !== "ready") throw new Error("expected a ready view model");
    expect(model.rows[0]).toMatchObject({
      rateDisplay: "--",
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
