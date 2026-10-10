import type {
  LedgerPnlCandidateFinancialIndicatorComponentDetail,
  LedgerPnlCandidateFinancialIndicatorComponentDetailRow,
  LedgerPnlCandidateFinancialIndicatorComponentMetricId,
  LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod,
} from "../../../api/contracts";
import { formatCandidateComparisonAmount } from "./candidatePeriodComparisonModel";

const DECIMAL_PATTERN = /^-?\d+(?:\.\d+)?$/;
const ZERO_DECIMAL_PATTERN = /^-?0+(?:\.0+)?$/;
const REPORT_MONTH_PATTERN = /^\d{4}(?:0[1-9]|1[0-2])$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const ACCOUNT_CODE_PATTERN = /^5\d{10}$/;
const CELL_REF_PATTERN = /^[A-Z]+[1-9]\d*$/;

const COMPONENT_IDENTITIES = {
  "income.interest.loan.total": ["贷款利息收入", 1],
  "expense.interest.deposit.total": ["存款利息支出", -1],
  "income.interest.investment": ["金融投资利息收入", 1],
  "income.interest.interbank_net": ["同业资产负债利息净收入", 1],
} as const satisfies Record<
  LedgerPnlCandidateFinancialIndicatorComponentMetricId,
  readonly [string, -1 | 1]
>;

export type CandidateNetInterestComponentDetailRowStatusFilter =
  | "all"
  | "contributing"
  | "excluded_offset";

export type CandidateNetInterestComponentDetailRowView = {
  backendPosition: number;
  rowStatus: "contributing" | "excluded_offset";
  accountCode: string;
  accountName: string;
  currency: "CNX";
  effectiveComponentWeight: string;
  effectiveNetWeight: string;
  matchedTerms: LedgerPnlCandidateFinancialIndicatorComponentDetailRow["matched_terms"];
  currentEndingYuan: string;
  previousEndingYuan: string;
  twoMonthPriorEndingYuan: string;
  currentValueYi: string;
  previousValueYi: string;
  componentDeltaYi: string;
  contributionToNetDeltaYi: string;
  currentDisplay: string;
  previousDisplay: string;
  componentDeltaDisplay: string;
  contributionDisplay: string;
  sourceEvidence: LedgerPnlCandidateFinancialIndicatorComponentDetailRow["source_evidence"];
};

type AvailableComponentDetailModel = {
  state: "available";
  payload: LedgerPnlCandidateFinancialIndicatorComponentDetail;
  summary: {
    metricName: string;
    unit: "亿元";
    currentDisplay: string;
    previousDisplay: string;
    componentDeltaDisplay: string;
    contributionDisplay: string;
    qualityLabel: "标准候选" | "降级候选";
    footLabel: "勾稽通过";
  };
  rows: CandidateNetInterestComponentDetailRowView[];
};

type ClosedComponentDetailModel = {
  state: "stale_parent" | "not_evaluable" | "failed" | "invalid_contract";
  reason: string;
  rows: [];
};

export type CandidateNetInterestComponentDetailViewModel =
  | AvailableComponentDetailModel
  | ClosedComponentDetailModel;

export function filterCandidateNetInterestComponentDetailRows(
  rows: readonly CandidateNetInterestComponentDetailRowView[],
  filters: {
    query: string;
    status: CandidateNetInterestComponentDetailRowStatusFilter;
  },
): CandidateNetInterestComponentDetailRowView[] {
  const query = filters.query.trim().toLowerCase();
  return rows.filter((row) => (
    (filters.status === "all" || row.rowStatus === filters.status)
    && (
      query.length === 0
      || row.accountCode.toLowerCase().includes(query)
      || row.accountName.toLowerCase().includes(query)
    )
  ));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDecimal(value: unknown): value is string {
  return typeof value === "string" && DECIMAL_PATTERN.test(value);
}

function isZeroDecimal(value: unknown): value is string {
  return typeof value === "string" && ZERO_DECIMAL_PATTERN.test(value);
}

function formatCandidateComponentDetailAmount(value: string): string {
  const display = formatCandidateComparisonAmount(value);
  if (
    !ZERO_DECIMAL_PATTERN.test(value)
    && (display === "0.0000" || display === "\u22120.0000")
  ) return value.startsWith("-") ? ">\u22120.0001" : "<0.0001";
  return display;
}

function isSha256(value: unknown): value is string {
  return typeof value === "string" && SHA256_PATTERN.test(value);
}

function isReasonList(value: unknown, requireReason = false): value is string[] {
  return Array.isArray(value)
    && (!requireReason || value.length > 0)
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

function isSourcePeriod(
  value: unknown,
  expectedMonth: string,
): value is LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod {
  if (!isRecord(value)) return false;
  const lockedSha = value.locked_sha256;
  const lockStatus = value.lock_status;
  return value.month === expectedMonth
    && value.report_date === reportMonthEnd(expectedMonth)
    && value.ledger_file_name === `总账对账${expectedMonth}.xlsx`
    && isSha256(value.ledger_sha256)
    && (lockedSha === null || isSha256(lockedSha))
    && (
      lockedSha === null
        ? lockStatus === "unlocked"
        : lockStatus === "locked_match" && lockedSha === value.ledger_sha256
    );
}

function isMatchedTerm(value: unknown, accountCode: string): boolean {
  if (!isRecord(value)) return false;
  if (
    value.source !== "ledger"
    || !new Set(["l1", "l2", "l3", "full"]).has(String(value.level))
    || typeof value.code !== "string"
    || !/^\d{3,11}$/.test(value.code)
    || !isDecimal(value.weight)
  ) return false;
  const lengths = { l1: 3, l2: 5, l3: 7 } as const;
  return value.level === "full"
    ? value.code === accountCode
    : accountCode.slice(0, lengths[value.level as keyof typeof lengths]) === value.code;
}

function sourcePeriodIdentityMatches(
  evidence: Record<string, unknown>,
  source: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod,
): boolean {
  return evidence.month === source.month
    && evidence.report_date === source.report_date
    && evidence.ledger_file_name === source.ledger_file_name
    && evidence.ledger_sha256 === source.ledger_sha256
    && evidence.locked_sha256 === source.locked_sha256
    && evidence.lock_status === source.lock_status;
}

function isSourceEvidence(
  value: unknown,
  source: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod,
  endingYuan: string,
): boolean {
  if (!isRecord(value)) return false;
  return sourcePeriodIdentityMatches(value, source)
    && value.sheet === "综本"
    && Number.isInteger(value.row)
    && Number(value.row) > 0
    && typeof value.account_code_cell === "string"
    && CELL_REF_PATTERN.test(value.account_code_cell)
    && value.account_code_cell.endsWith(String(value.row))
    && typeof value.ending_cell === "string"
    && CELL_REF_PATTERN.test(value.ending_cell)
    && value.ending_cell.endsWith(String(value.row))
    && value.ending_yuan === endingYuan;
}

function isDetailRow(
  value: unknown,
  sourcePeriods: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[],
): value is LedgerPnlCandidateFinancialIndicatorComponentDetailRow {
  if (!isRecord(value)) return false;
  if (
    !new Set(["contributing", "excluded_offset"]).has(String(value.row_status))
    || typeof value.account_code !== "string"
    || !ACCOUNT_CODE_PATTERN.test(value.account_code)
    || typeof value.account_name !== "string"
    || value.currency !== "CNX"
    || !isDecimal(value.effective_component_weight)
    || !isDecimal(value.effective_net_weight)
    || !Array.isArray(value.matched_terms)
    || value.matched_terms.length === 0
    || !value.matched_terms.every((term) => isMatchedTerm(term, value.account_code as string))
    || !isDecimal(value.current_ending_yuan)
    || !isDecimal(value.previous_ending_yuan)
    || !isDecimal(value.two_month_prior_ending_yuan)
    || !isDecimal(value.current_value_yi)
    || !isDecimal(value.previous_value_yi)
    || !isDecimal(value.component_delta_yi)
    || !isDecimal(value.contribution_to_net_delta_yi)
    || !Array.isArray(value.source_evidence)
    || value.source_evidence.length !== sourcePeriods.length
  ) return false;
  if (
    value.row_status === "excluded_offset"
    && ![
      value.effective_component_weight,
      value.effective_net_weight,
      value.current_value_yi,
      value.previous_value_yi,
      value.component_delta_yi,
      value.contribution_to_net_delta_yi,
    ].every(isZeroDecimal)
  ) return false;
  const endingValues = [
    value.current_ending_yuan,
    value.previous_ending_yuan,
    value.two_month_prior_ending_yuan,
  ] as string[];
  return value.source_evidence.every((evidence, index) => (
    isSourceEvidence(evidence, sourcePeriods[index], endingValues[index])
  ));
}

function summaryValues(value: Record<string, unknown>): unknown[] {
  return [
    value.parent_current_value_yi,
    value.parent_previous_value_yi,
    value.parent_component_delta_yi,
    value.parent_contribution_to_net_delta_yi,
    value.account_current_total_yi,
    value.account_previous_total_yi,
    value.account_component_delta_total_yi,
    value.account_contribution_total_yi,
    value.current_reconciliation_yi,
    value.previous_reconciliation_yi,
    value.component_delta_reconciliation_yi,
    value.contribution_reconciliation_yi,
  ];
}

function hasAvailableSummaryIdentity(value: Record<string, unknown>): boolean {
  return summaryValues(value).every(isDecimal)
    && value.parent_current_value_yi === value.account_current_total_yi
    && value.parent_previous_value_yi === value.account_previous_total_yi
    && value.parent_component_delta_yi === value.account_component_delta_total_yi
    && value.parent_contribution_to_net_delta_yi === value.account_contribution_total_yi
    && [
      value.current_reconciliation_yi,
      value.previous_reconciliation_yi,
      value.component_delta_reconciliation_yi,
      value.contribution_reconciliation_yi,
    ].every(isZeroDecimal);
}

function closedModel(
  state: ClosedComponentDetailModel["state"],
  reason: string,
): ClosedComponentDetailModel {
  return { state, reason, rows: [] };
}

export function buildCandidateNetInterestComponentDetailViewModel(
  value: unknown,
  requestedReportMonth: string,
  requestedMetricId: LedgerPnlCandidateFinancialIndicatorComponentMetricId,
  requestedParentIdempotencyKey: string,
): CandidateNetInterestComponentDetailViewModel {
  const reportMonth = requestedReportMonth.trim();
  const parentKey = requestedParentIdempotencyKey.trim();
  if (!isRecord(value) || !REPORT_MONTH_PATTERN.test(reportMonth)) {
    return closedModel("invalid_contract", "科目穿透响应不符合固定契约。");
  }
  const comparisonMonth = previousMonth(reportMonth);
  const twoMonthPrior = previousMonth(comparisonMonth);
  const identity = COMPONENT_IDENTITIES[requestedMetricId];
  if (!identity) {
    return closedModel("invalid_contract", "科目穿透指标不属于固定净息构成。");
  }
  if (
    value.contract_version !== "candidate-financial-indicator-component-detail-v1"
    || value.analysis_kind !== "accounting_component_account_detail"
    || value.report_month !== reportMonth
    || value.report_date !== reportMonthEnd(reportMonth)
    || value.comparison_month !== comparisonMonth
    || value.two_month_prior !== twoMonthPrior
    || value.metric_id !== requestedMetricId
    || value.metric_name !== identity[0]
    || value.formula_weight !== identity[1]
    || value.currency !== "CNX"
    || value.basis !== "calendar_month_from_cumulative"
    || value.method !== "finance_metric_account_contribution"
    || value.unit !== "亿元"
    || !new Set(["available", "not_evaluable", "stale_parent"]).has(String(value.status))
    || !new Set(["standard_candidate", "degraded_candidate", "not_evaluable"])
      .has(String(value.quality_status))
    || !new Set(["passed", "failed", "not_evaluable"]).has(String(value.foot_status))
    || value.formal_use_allowed !== false
    || value.certification_effect !== "none"
    || value.driver_status !== "unclear"
    || value.rule_version !== "qdb-finance-2026-v1.0.1"
    || !isSha256(value.rule_hash)
    || !isSha256(value.parent_idempotency_key)
    || !isSha256(value.idempotency_key)
    || !isReasonList(value.reasons)
    || !Array.isArray(value.rows)
    || !Array.isArray(value.source_periods)
    || value.source_periods.length !== 3
  ) return closedModel("invalid_contract", "科目穿透响应不符合固定契约。");

  const expectedMonths = [reportMonth, comparisonMonth, twoMonthPrior];
  if (!value.source_periods.every((period, index) => (
    isSourcePeriod(period, expectedMonths[index])
  ))) return closedModel("invalid_contract", "科目穿透来源证据不完整。");
  const sourcePeriods = value.source_periods as LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[];

  if (value.status === "stale_parent") {
    return value.parent_idempotency_key !== parentKey
      && value.quality_status === "not_evaluable"
      && value.foot_status === "not_evaluable"
      && isReasonList(value.reasons, true)
      && value.rows.length === 0
      && summaryValues(value).every((field) => field === null)
      ? closedModel("stale_parent", value.reasons[0])
      : closedModel("invalid_contract", "过期父结果携带了不可消费的科目解释。");
  }

  if (value.parent_idempotency_key !== parentKey) {
    return closedModel("invalid_contract", "科目穿透响应与父级比较结果不匹配。");
  }

  if (value.status === "not_evaluable") {
    if (
      value.quality_status !== "not_evaluable"
      || !isReasonList(value.reasons, true)
      || value.rows.length !== 0
      || value.foot_status === "passed"
    ) return closedModel("invalid_contract", "不可评估状态携带了不可消费的科目解释。");
    const parentValues = summaryValues(value).slice(0, 4);
    const accountTotals = summaryValues(value).slice(4, 8);
    const reconciliations = summaryValues(value).slice(8);
    if (value.foot_status === "not_evaluable") {
      const parentShapeValid = parentValues.every((field) => field === null)
        || parentValues.every(isDecimal);
      return parentShapeValid
        && accountTotals.every((field) => field === null)
        && reconciliations.every((field) => field === null)
        ? closedModel("not_evaluable", value.reasons[0])
        : closedModel("invalid_contract", "不可评估状态携带了部分金额。");
    }
    return value.foot_status === "failed"
      && parentValues.every(isDecimal)
      && accountTotals.every((field) => field === null)
      && reconciliations.every(isDecimal)
      && reconciliations.some((field) => !isZeroDecimal(field))
      ? closedModel("failed", value.reasons[0])
      : closedModel("invalid_contract", "失败勾稽携带了不可消费的科目解释。");
  }

  const expectedQuality = sourcePeriods.every((period) => period.lock_status === "locked_match")
    ? "standard_candidate"
    : "degraded_candidate";
  if (
    value.foot_status !== "passed"
    || value.quality_status !== expectedQuality
    || value.reasons.length !== 0
    || !hasAvailableSummaryIdentity(value)
    || !value.rows.every((row) => isDetailRow(row, sourcePeriods))
  ) return closedModel("invalid_contract", "可用科目穿透未通过后端字符串身份校验。");

  // 上方已逐字段完成契约校验，此处仅做单跳收窄。
  const payload = value as LedgerPnlCandidateFinancialIndicatorComponentDetail;
  return {
    state: "available",
    payload,
    summary: {
      metricName: payload.metric_name,
      unit: payload.unit,
      currentDisplay: formatCandidateComparisonAmount(payload.parent_current_value_yi),
      previousDisplay: formatCandidateComparisonAmount(payload.parent_previous_value_yi),
      componentDeltaDisplay: formatCandidateComparisonAmount(payload.parent_component_delta_yi),
      contributionDisplay: formatCandidateComparisonAmount(
        payload.parent_contribution_to_net_delta_yi,
      ),
      qualityLabel: payload.quality_status === "standard_candidate" ? "标准候选" : "降级候选",
      footLabel: "勾稽通过",
    },
    rows: payload.rows.map((row, index) => ({
      backendPosition: index + 1,
      rowStatus: row.row_status,
      accountCode: row.account_code,
      accountName: row.account_name,
      currency: row.currency,
      effectiveComponentWeight: row.effective_component_weight,
      effectiveNetWeight: row.effective_net_weight,
      matchedTerms: row.matched_terms,
      currentEndingYuan: row.current_ending_yuan,
      previousEndingYuan: row.previous_ending_yuan,
      twoMonthPriorEndingYuan: row.two_month_prior_ending_yuan,
      currentValueYi: row.current_value_yi,
      previousValueYi: row.previous_value_yi,
      componentDeltaYi: row.component_delta_yi,
      contributionToNetDeltaYi: row.contribution_to_net_delta_yi,
      currentDisplay: formatCandidateComponentDetailAmount(row.current_value_yi),
      previousDisplay: formatCandidateComponentDetailAmount(row.previous_value_yi),
      componentDeltaDisplay: formatCandidateComponentDetailAmount(row.component_delta_yi),
      contributionDisplay: formatCandidateComponentDetailAmount(row.contribution_to_net_delta_yi),
      sourceEvidence: row.source_evidence,
    })),
  };
}
