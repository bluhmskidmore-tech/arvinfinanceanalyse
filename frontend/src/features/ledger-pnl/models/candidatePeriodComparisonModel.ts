import type {
  LedgerPnlCandidateFinancialIndicatorFullScopeGap,
  LedgerPnlCandidateFinancialIndicatorNetInterestComponent,
  LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge,
  LedgerPnlCandidateFinancialIndicatorPeriodComparison,
  LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

const DECIMAL_PATTERN = /^-?\d+(?:\.\d+)?$/;
const REPORT_MONTH_PATTERN = /^\d{4}(?:0[1-9]|1[0-2])$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

const EXPECTED_METRICS = [
  ["income.interest.net", "calendar_month_from_cumulative", "finance_metric_cumulative_mom"],
  ["income.noninterest.total", "calendar_month_from_cumulative", "finance_metric_cumulative_mom"],
  ["income.operating.mother_bank", "calendar_month_from_cumulative", "finance_metric_cumulative_mom"],
  ["balance.deposit.corporate.total::point", "month_end_point", "finance_metric_point_to_point"],
  ["balance.deposit.retail.total::point", "month_end_point", "finance_metric_point_to_point"],
  ["balance.loan.corporate.total::point", "month_end_point", "finance_metric_point_to_point"],
  ["balance.loan.retail.total::point", "month_end_point", "finance_metric_point_to_point"],
] as const;

const EXPECTED_NET_INTEREST_COMPONENTS = [
  ["income.interest.loan.total", "贷款利息收入", 1],
  ["expense.interest.deposit.total", "存款利息支出", -1],
  ["income.interest.investment", "金融投资利息收入", 1],
  ["income.interest.interbank_net", "同业资产负债利息净收入", 1],
] as const;

const METRIC_STATUSES = new Set(["ok", "warning", "manual_default", "error", "missing"]);
const FULL_SCOPE_REASONS = new Set([
  "available",
  "missing_source_file",
  "missing_required_sheet",
  "source_parse_error",
  "full_replay_incomplete",
  "source_evaluation_error",
]);
const GAP_REASONS = new Set([
  "missing_source_file",
  "missing_required_sheet",
  "source_parse_error",
  "full_replay_incomplete",
  "source_evaluation_error",
]);

type FormatAmountOptions = {
  signed?: boolean;
};

type ReadyComparisonRow = {
  metricId: string;
  metricName: string;
  basisLabel: "自然月单月环比" | "月末时点环比";
  unit: "亿元";
  comparisonStatus: "comparable" | "not_comparable";
  currentDisplay: string;
  previousDisplay: string;
  deltaDisplay: string;
  rateDisplay: string;
  reason: string | null;
  qualityLabel: "标准候选" | "降级候选" | "暂不可比";
};

type NetInterestBridgeRow = {
  metricId: string;
  metricName: string;
  currentDisplay: string;
  previousDisplay: string;
  componentDeltaDisplay: string;
  contributionDisplay: string;
};

type NetInterestBridgeViewModel =
  | {
      status: "available";
      netDeltaDisplay: string;
      footLabel: "勾稽通过";
      reconciliationDisplay: "0.0000";
      rows: NetInterestBridgeRow[];
    }
  | {
      status: "not_evaluable";
      rows: [];
    }
  | {
      status: "failed";
      netDeltaDisplay: string;
      reconciliationDisplay: string;
      rows: [];
    };

type ReadyComparisonModel = {
  status: "ready";
  payload: LedgerPnlCandidateFinancialIndicatorPeriodComparison;
  headline: string;
  comparableCount: number;
  notComparableCount: number;
  rows: ReadyComparisonRow[];
  netInterestBridge: NetInterestBridgeViewModel;
  fullScopeGaps: Array<{
    month: string;
    sourceLabel: "总账源" | "日均源";
    reasonLabel: string;
  }>;
  hasUnlockedHistoricalSource: boolean;
};

type InvalidComparisonModel = {
  status: "invalid_contract";
  reason: "wrong_report_month" | "malformed_payload";
  message: string;
};

export type CandidatePeriodComparisonViewModel =
  | ReadyComparisonModel
  | InvalidComparisonModel;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDecimal(value: unknown): value is string {
  return typeof value === "string" && DECIMAL_PATTERN.test(value);
}

function isDecimalOrNull(value: unknown): value is string | null {
  return value === null || isDecimal(value);
}

function isZeroDecimal(value: unknown): value is string {
  return typeof value === "string" && /^-?0+(?:\.0+)?$/.test(value);
}

function isNonEmptyReasonList(value: unknown): value is string[] {
  return Array.isArray(value)
    && value.length > 0
    && value.every((reason) => typeof reason === "string" && reason.length > 0);
}

function isReasonList(value: unknown): value is string[] {
  return Array.isArray(value)
    && value.every((reason) => typeof reason === "string" && reason.length > 0);
}

function previousMonth(reportMonth: string): string {
  const year = Number(reportMonth.slice(0, 4));
  const month = Number(reportMonth.slice(4, 6));
  return month === 1
    ? `${year - 1}12`
    : `${year}${String(month - 1).padStart(2, "0")}`;
}

function reportMonthEnd(reportMonth: string): string {
  const year = Number(reportMonth.slice(0, 4));
  const month = Number(reportMonth.slice(4, 6));
  const day = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return `${reportMonth.slice(0, 4)}-${reportMonth.slice(4, 6)}-${String(day).padStart(2, "0")}`;
}

function fixedDecimal(value: string, precision: number, showPositive: boolean): string {
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [integerPart, fractionPart = ""] = unsigned.split(".");
  const paddedFraction = fractionPart.padEnd(precision + 1, "0");
  const keptFraction = paddedFraction.slice(0, precision);
  const roundingDigit = paddedFraction[precision] ?? "0";
  let scaled = BigInt(`${integerPart}${keptFraction}` || "0");
  if (roundingDigit >= "5") scaled += 1n;
  const scale = 10n ** BigInt(precision);
  const roundedInteger = (scaled / scale).toString();
  const roundedFraction = (scaled % scale).toString().padStart(precision, "0");
  const groupedInteger = roundedInteger.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const inputIsZero = BigInt(`${integerPart}${fractionPart}` || "0") === 0n;
  const sign = negative && !inputIsZero
    ? "−"
    : showPositive && !inputIsZero
      ? "+"
      : "";
  return precision > 0
    ? `${sign}${groupedInteger}.${roundedFraction}`
    : `${sign}${groupedInteger}`;
}

function shiftDecimalRight(value: string, places: number): string {
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [integerPart, fractionPart = ""] = unsigned.split(".");
  const digits = `${integerPart}${fractionPart}`;
  const decimalIndex = integerPart.length + places;
  const shifted = decimalIndex >= digits.length
    ? `${digits.padEnd(decimalIndex, "0")}`
    : `${digits.slice(0, decimalIndex) || "0"}.${digits.slice(decimalIndex)}`;
  return negative ? `-${shifted}` : shifted;
}

export function formatCandidateComparisonAmount(
  value: string | null,
  options: FormatAmountOptions = {},
): string {
  if (value === null) return EM_DASH;
  if (!isDecimal(value)) return "契约错误";
  return fixedDecimal(value, 4, options.signed === true);
}

export function formatCandidateComparisonRate(value: string | null): string {
  if (value === null) return EM_DASH;
  if (!isDecimal(value)) return "契约错误";
  return `${fixedDecimal(shiftDecimalRight(value, 2), 2, true)}%`;
}

export function summarizeCandidateComparisonReasons(reasons: readonly string[]): string {
  const hasManualDependency = reasons.some((reason) => (
    reason === "manual_required_not_supplied"
    || reason.endsWith(":manual_required_not_supplied")
  ));
  const hasMissingAccount = reasons.some((reason) => (
    reason.startsWith("missing_account:")
    || reason.includes(":missing_account:")
  ));
  if (hasManualDependency && hasMissingAccount) {
    return "指标依赖包含待补手工项和缺失总账科目，跨期结果暂不可比。";
  }
  if (hasManualDependency) {
    return "指标依赖包含待补手工项，跨期结果暂不可比。";
  }
  if (hasMissingAccount) {
    return "指标依赖包含缺失总账科目，跨期结果暂不可比。";
  }
  return "连续月份指标状态未通过，跨期结果暂不可比。";
}

function isComparisonSourcePeriod(
  value: unknown,
  expectedMonth: string,
): boolean {
  if (!isRecord(value)) return false;
  if (
    value.month !== expectedMonth
    || value.report_date !== reportMonthEnd(expectedMonth)
    || value.ledger_file_name !== `总账对账${expectedMonth}.xlsx`
    || !isDecimalSha(value.ledger_sha256)
    || !(value.locked_sha256 === null || isDecimalSha(value.locked_sha256))
    || !new Set(["locked_match", "locked_mismatch", "unlocked"]).has(String(value.lock_status))
  ) return false;
  const expectedLockStatus = value.locked_sha256 === null
    ? "unlocked"
    : value.locked_sha256 === value.ledger_sha256
      ? "locked_match"
      : "locked_mismatch";
  return value.lock_status === expectedLockStatus && value.lock_status !== "locked_mismatch";
}

function isDecimalSha(value: unknown): value is string {
  return typeof value === "string" && SHA256_PATTERN.test(value);
}

function isFullScopeGap(value: unknown, comparisonMonth: string): value is LedgerPnlCandidateFinancialIndicatorFullScopeGap {
  if (!isRecord(value)) return false;
  if (
    !GAP_REASONS.has(String(value.reason_code))
    || !new Set(["ledger", "daily"]).has(String(value.source_kind))
    || value.month !== comparisonMonth
  ) return false;
  return value.reason_code === "missing_required_sheet"
    ? typeof value.required_sheet === "string" && value.required_sheet.length > 0
    : value.required_sheet === null;
}

function isComparisonMetric(value: unknown, index: number): value is LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric {
  if (!isRecord(value)) return false;
  const [metricId, basis, method] = EXPECTED_METRICS[index];
  if (
    value.metric_id !== metricId
    || typeof value.metric_name !== "string"
    || value.metric_name.length === 0
    || value.basis !== basis
    || value.method !== method
    || value.unit !== "亿元"
    || !new Set(["comparable", "not_comparable"]).has(String(value.comparison_status))
    || !METRIC_STATUSES.has(String(value.current_metric_status))
    || !METRIC_STATUSES.has(String(value.previous_metric_status))
    || !(value.two_month_prior_metric_status === null || METRIC_STATUSES.has(String(value.two_month_prior_metric_status)))
    || !isDecimalOrNull(value.current_value_yi)
    || !isDecimalOrNull(value.previous_value_yi)
    || !isDecimalOrNull(value.current_source_value_yi)
    || !isDecimalOrNull(value.previous_source_value_yi)
    || !isDecimalOrNull(value.two_month_prior_source_value_yi)
    || !isDecimalOrNull(value.delta_yi)
    || !isDecimalOrNull(value.change_rate)
    || !(value.rate_reason === null || new Set(["zero_denominator", "missing_reference", "metric_status_not_ok"]).has(String(value.rate_reason)))
    || !Array.isArray(value.reasons)
    || !value.reasons.every((reason) => typeof reason === "string" && reason.length > 0)
    || value.driver_status !== "unclear"
    || !new Set(["standard_candidate", "degraded_candidate", "not_comparable"]).has(String(value.quality_status))
  ) return false;

  const cumulative = basis === "calendar_month_from_cumulative";
  if (
    cumulative
      ? value.two_month_prior_metric_status === null
      : value.two_month_prior_metric_status !== null || value.two_month_prior_source_value_yi !== null
  ) return false;

  if (value.comparison_status === "comparable") {
    const sourceStatuses = cumulative
      ? [value.current_metric_status, value.previous_metric_status, value.two_month_prior_metric_status]
      : [value.current_metric_status, value.previous_metric_status];
    return sourceStatuses.every((status) => status === "ok")
      && isDecimal(value.current_value_yi)
      && isDecimal(value.previous_value_yi)
      && isDecimal(value.delta_yi)
      && isDecimal(value.current_source_value_yi)
      && isDecimal(value.previous_source_value_yi)
      && (!cumulative || isDecimal(value.two_month_prior_source_value_yi))
      && (
        isDecimal(value.change_rate) && value.rate_reason === null
        || value.change_rate === null && value.rate_reason === "zero_denominator"
      )
      && value.reasons.length === 0
      && value.quality_status !== "not_comparable";
  }

  return value.current_value_yi === null
    && value.previous_value_yi === null
    && value.delta_yi === null
    && value.change_rate === null
    && new Set(["missing_reference", "metric_status_not_ok"]).has(String(value.rate_reason))
    && value.reasons.length > 0
    && value.quality_status === "not_comparable";
}

function isNetInterestComponent(
  value: unknown,
  index: number,
  computed: boolean,
): value is LedgerPnlCandidateFinancialIndicatorNetInterestComponent {
  if (!isRecord(value)) return false;
  const [metricId, metricName, formulaWeight] = EXPECTED_NET_INTEREST_COMPONENTS[index];
  const computedValues = [
    value.current_value_yi,
    value.previous_value_yi,
    value.component_delta_yi,
    value.contribution_to_net_delta_yi,
  ];
  if (
    value.metric_id !== metricId
    || value.metric_name !== metricName
    || value.formula_weight !== formulaWeight
    || !METRIC_STATUSES.has(String(value.current_metric_status))
    || !METRIC_STATUSES.has(String(value.previous_metric_status))
    || !METRIC_STATUSES.has(String(value.two_month_prior_metric_status))
    || !isDecimalOrNull(value.current_value_yi)
    || !isDecimalOrNull(value.previous_value_yi)
    || !isDecimalOrNull(value.current_source_value_yi)
    || !isDecimalOrNull(value.previous_source_value_yi)
    || !isDecimalOrNull(value.two_month_prior_source_value_yi)
    || !isDecimalOrNull(value.component_delta_yi)
    || !isDecimalOrNull(value.contribution_to_net_delta_yi)
    || !isReasonList(value.reasons)
  ) return false;

  if (computed) {
    return [
      value.current_metric_status,
      value.previous_metric_status,
      value.two_month_prior_metric_status,
    ].every((status) => status === "ok")
      && [
        value.current_source_value_yi,
        value.previous_source_value_yi,
        value.two_month_prior_source_value_yi,
        ...computedValues,
      ].every(isDecimal)
      && value.reasons.length === 0;
  }

  return computedValues.every((field) => field === null)
    && value.reasons.length > 0;
}

function isNetInterestBridge(
  value: unknown,
  expectedQuality: "standard_candidate" | "degraded_candidate",
): value is LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge {
  if (!isRecord(value)) return false;
  if (
    value.analysis_kind !== "accounting_component_bridge"
    || !new Set(["available", "not_evaluable"]).has(String(value.status))
    || value.metric_id !== "income.interest.net"
    || value.basis !== "calendar_month_from_cumulative"
    || value.method !== "finance_metric_component_contribution"
    || value.unit !== "亿元"
    || !new Set(["standard_candidate", "degraded_candidate", "not_evaluable"])
      .has(String(value.quality_status))
    || !new Set(["passed", "failed", "not_evaluable"]).has(String(value.foot_status))
    || !isDecimalOrNull(value.net_delta_yi)
    || !isDecimalOrNull(value.component_contribution_total_yi)
    || !isDecimalOrNull(value.reconciliation_delta_yi)
    || !isReasonList(value.reasons)
    || !Array.isArray(value.components)
    || value.components.length !== EXPECTED_NET_INTEREST_COMPONENTS.length
  ) return false;

  if (value.status === "available") {
    return value.quality_status === expectedQuality
      && value.foot_status === "passed"
      && isDecimal(value.net_delta_yi)
      && isDecimal(value.component_contribution_total_yi)
      && isZeroDecimal(value.reconciliation_delta_yi)
      && value.reasons.length === 0
      && value.components.every((component, index) => (
        isNetInterestComponent(component, index, true)
      ));
  }

  if (value.quality_status !== "not_evaluable" || !isNonEmptyReasonList(value.reasons)) {
    return false;
  }
  if (value.foot_status === "not_evaluable") {
    return value.net_delta_yi === null
      && value.component_contribution_total_yi === null
      && value.reconciliation_delta_yi === null
      && value.components.every((component, index) => (
        isNetInterestComponent(component, index, false)
      ));
  }
  if (value.foot_status !== "failed") return false;
  return isDecimal(value.net_delta_yi)
    && isDecimal(value.component_contribution_total_yi)
    && isDecimal(value.reconciliation_delta_yi)
    && !isZeroDecimal(value.reconciliation_delta_yi)
    && value.components.every((component, index) => (
      isNetInterestComponent(component, index, true)
    ));
}

function parseComparisonPayload(
  value: unknown,
  requestedReportMonth: string,
): InvalidComparisonModel | LedgerPnlCandidateFinancialIndicatorPeriodComparison {
  if (!isRecord(value)) {
    return invalidPayload("malformed_payload");
  }
  if (value.report_month !== requestedReportMonth) {
    return invalidPayload("wrong_report_month");
  }
  if (!REPORT_MONTH_PATTERN.test(requestedReportMonth)) {
    return invalidPayload("malformed_payload");
  }
  const comparisonMonth = previousMonth(requestedReportMonth);
  const twoMonthPrior = previousMonth(comparisonMonth);
  if (
    value.contract_version !== "candidate-financial-indicator-period-comparison-v2"
    || value.report_date !== reportMonthEnd(requestedReportMonth)
    || value.comparison_month !== comparisonMonth
    || value.two_month_prior !== twoMonthPrior
    || value.comparison_scope !== "ledger_only_key_metrics"
    || !new Set(["available", "unavailable"]).has(String(value.full_scope_status))
    || !FULL_SCOPE_REASONS.has(String(value.full_scope_reason_code))
    || typeof value.full_scope_detail !== "string"
    || value.full_scope_detail.length === 0
    || !Array.isArray(value.full_scope_gaps)
    || !value.full_scope_gaps.every((gap) => isFullScopeGap(gap, comparisonMonth))
    || !new Set(["available", "partial", "unavailable"]).has(String(value.overall_status))
    || value.metric_status !== "candidate"
    || value.formal_use_allowed !== false
    || value.certification_effect !== "none"
    || value.driver_status !== "unclear"
    || value.rule_version !== "qdb-finance-2026-v1.0.1"
    || !isDecimalSha(value.rule_hash)
    || !isDecimalSha(value.idempotency_key)
    || !Array.isArray(value.source_periods)
    || value.source_periods.length !== 3
    || !value.source_periods.every((period, index) => isComparisonSourcePeriod(
      period,
      [requestedReportMonth, comparisonMonth, twoMonthPrior][index],
    ))
    || !Array.isArray(value.metrics)
    || value.metrics.length !== EXPECTED_METRICS.length
    || !value.metrics.every(isComparisonMetric)
  ) return invalidPayload("malformed_payload");

  const comparableCount = value.metrics.filter((metric) => (
    isRecord(metric) && metric.comparison_status === "comparable"
  )).length;
  const expectedOverallStatus = comparableCount === EXPECTED_METRICS.length
    ? "available"
    : comparableCount === 0
      ? "unavailable"
      : "partial";
  const availableFullScope = value.full_scope_status === "available";
  if (
    value.overall_status !== expectedOverallStatus
    || (
      availableFullScope
        ? value.full_scope_reason_code !== "available" || value.full_scope_gaps.length !== 0
        : value.full_scope_reason_code === "available"
          || value.full_scope_gaps.length === 0
          || value.full_scope_gaps.some((gap) => (
            isRecord(gap) && gap.reason_code !== value.full_scope_reason_code
          ))
    )
  ) return invalidPayload("malformed_payload");

  const expectedQuality = value.source_periods.every((period) => (
    isRecord(period) && period.lock_status === "locked_match"
  )) ? "standard_candidate" : "degraded_candidate";
  if (value.metrics.some((metric) => (
    isRecord(metric)
    && metric.comparison_status === "comparable"
    && metric.quality_status !== expectedQuality
  ))) {
    return invalidPayload("malformed_payload");
  }
  const netInterestBridge = value.net_interest_component_bridge;
  if (!isNetInterestBridge(netInterestBridge, expectedQuality)) {
    return invalidPayload("malformed_payload");
  }
  const netInterestMetric = value.metrics[0];
  if (
    !isRecord(netInterestMetric)
    || (
      netInterestBridge.net_delta_yi !== null
      && netInterestMetric.delta_yi !== netInterestBridge.net_delta_yi
    )
    || (
      netInterestBridge.status === "available"
      && (
        netInterestMetric.comparison_status !== "comparable"
        || netInterestBridge.component_contribution_total_yi
          !== netInterestBridge.net_delta_yi
      )
    )
  ) return invalidPayload("malformed_payload");

  // 上方已逐字段完成契约校验，此处仅做单跳收窄。
  return value as LedgerPnlCandidateFinancialIndicatorPeriodComparison;
}

function invalidPayload(reason: InvalidComparisonModel["reason"]): InvalidComparisonModel {
  return {
    status: "invalid_contract",
    reason,
    message: reason === "wrong_report_month"
      ? "跨期变化响应月份与当前请求不一致，已阻断展示。"
      : "跨期变化响应不符合固定七项候选契约，已阻断展示。",
  };
}

function fullScopeReasonLabel(gap: LedgerPnlCandidateFinancialIndicatorFullScopeGap): string {
  switch (gap.reason_code) {
    case "missing_required_sheet":
      return `缺少工作表：${gap.required_sheet}`;
    case "missing_source_file":
      return "缺少来源文件";
    case "source_parse_error":
      return "来源解析失败";
    case "full_replay_incomplete":
      return "完整重放未完成";
    case "source_evaluation_error":
      return "来源评估失败";
  }
}

function buildNetInterestBridgeViewModel(
  bridge: LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge,
): NetInterestBridgeViewModel {
  if (bridge.status === "available") {
    return {
      status: "available",
      netDeltaDisplay: formatCandidateComparisonAmount(bridge.net_delta_yi, { signed: true }),
      footLabel: "勾稽通过",
      reconciliationDisplay: "0.0000",
      rows: bridge.components.map((component) => ({
        metricId: component.metric_id,
        metricName: component.metric_name,
        currentDisplay: formatCandidateComparisonAmount(component.current_value_yi),
        previousDisplay: formatCandidateComparisonAmount(component.previous_value_yi),
        componentDeltaDisplay: formatCandidateComparisonAmount(
          component.component_delta_yi,
          { signed: true },
        ),
        contributionDisplay: formatCandidateComparisonAmount(
          component.contribution_to_net_delta_yi,
          { signed: true },
        ),
      })),
    };
  }
  if (bridge.foot_status === "failed") {
    return {
      status: "failed",
      netDeltaDisplay: formatCandidateComparisonAmount(bridge.net_delta_yi, { signed: true }),
      reconciliationDisplay: formatCandidateComparisonAmount(
        bridge.reconciliation_delta_yi,
        { signed: true },
      ),
      rows: [],
    };
  }
  return { status: "not_evaluable", rows: [] };
}

export function buildCandidatePeriodComparisonViewModel(
  value: unknown,
  requestedReportMonth: string,
): CandidatePeriodComparisonViewModel {
  const normalizedReportMonth = requestedReportMonth.trim();
  const parsed = parseComparisonPayload(value, normalizedReportMonth);
  if ("status" in parsed) return parsed;

  const comparableCount = parsed.metrics.filter(
    (metric) => metric.comparison_status === "comparable",
  ).length;
  const notComparableCount = parsed.metrics.length - comparableCount;
  const degraded = parsed.metrics.some((metric) => (
    metric.comparison_status === "comparable"
    && metric.quality_status === "degraded_candidate"
  ));
  const headline = comparableCount === 0
    ? `${comparableCount}项可比、${notComparableCount}项暂不可比（候选）`
    : degraded
      ? `${comparableCount}项可比、${notComparableCount}项暂不可比（降级候选）`
      : `${comparableCount}项标准候选、${notComparableCount}项暂不可比`;
  return {
    status: "ready",
    payload: parsed,
    headline,
    comparableCount,
    notComparableCount,
    netInterestBridge: buildNetInterestBridgeViewModel(
      parsed.net_interest_component_bridge,
    ),
    rows: parsed.metrics.map((metric) => ({
      metricId: metric.metric_id,
      metricName: metric.metric_name,
      basisLabel: metric.basis === "calendar_month_from_cumulative"
        ? "自然月单月环比"
        : "月末时点环比",
      unit: metric.unit,
      comparisonStatus: metric.comparison_status,
      currentDisplay: formatCandidateComparisonAmount(metric.current_value_yi),
      previousDisplay: formatCandidateComparisonAmount(metric.previous_value_yi),
      deltaDisplay: formatCandidateComparisonAmount(metric.delta_yi, { signed: true }),
      rateDisplay: formatCandidateComparisonRate(metric.change_rate),
      reason: metric.rate_reason === "zero_denominator"
        ? "上期值为零，环比率不适用。"
        : metric.comparison_status === "not_comparable"
          ? summarizeCandidateComparisonReasons(metric.reasons)
          : null,
      qualityLabel: metric.quality_status === "standard_candidate"
        ? "标准候选"
        : metric.quality_status === "degraded_candidate"
          ? "降级候选"
          : "暂不可比",
    })),
    fullScopeGaps: parsed.full_scope_gaps.map((gap) => ({
      month: gap.month,
      sourceLabel: gap.source_kind === "daily" ? "日均源" : "总账源",
      reasonLabel: fullScopeReasonLabel(gap),
    })),
    hasUnlockedHistoricalSource: parsed.source_periods
      .slice(1)
      .some((period) => period.lock_status === "unlocked"),
  };
}
