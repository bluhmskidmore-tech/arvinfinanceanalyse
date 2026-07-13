import type { LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence } from "../../../api/contracts";
import type {
  CandidateNetInterestComponentDetailRowView,
  CandidateNetInterestComponentDetailViewModel,
} from "./candidateNetInterestComponentDetailModel";

type AvailableComponentDetailModel = Extract<
  CandidateNetInterestComponentDetailViewModel,
  { state: "available" }
>;

export type CandidateNetInterestComponentDetailCsvArtifact = {
  filename: string;
  content: string;
};

const DECIMAL_PATTERN = /^-?\d+(?:\.\d+)?$/;
const FORMULA_PREFIX_PATTERN = /^[\t ]*[=+\-@]/;

function safeCsvValue(value: string | number | boolean | null): string {
  const raw = value === null ? "" : String(value);
  const normalized = raw.replace(/\r?\n/g, "\r\n");
  return !DECIMAL_PATTERN.test(normalized) && FORMULA_PREFIX_PATTERN.test(normalized)
    ? `'${normalized}`
    : normalized;
}

function csvCell(value: string | number | boolean | null): string {
  return `"${safeCsvValue(value).replace(/"/g, '""')}"`;
}

function sourceHeaders(position: number): string[] {
  const prefix = `source_${position}`;
  return [
    `${prefix}_file`,
    `${prefix}_sheet`,
    `${prefix}_ending_cell`,
    `${prefix}_row`,
    `${prefix}_account_code_cell`,
    `${prefix}_month`,
    `${prefix}_report_date`,
    `${prefix}_ending_yuan`,
    `${prefix}_ledger_sha256`,
    `${prefix}_locked_sha256`,
    `${prefix}_lock_status`,
    `${prefix}_locator`,
  ];
}

function sourceValues(
  model: AvailableComponentDetailModel,
  row: CandidateNetInterestComponentDetailRowView,
  evidence: LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence,
): Array<string | number | null> {
  return [
    evidence.ledger_file_name,
    evidence.sheet,
    evidence.ending_cell,
    evidence.row,
    evidence.account_code_cell,
    evidence.month,
    evidence.report_date,
    evidence.ending_yuan,
    evidence.ledger_sha256,
    evidence.locked_sha256,
    evidence.lock_status,
    buildCandidateNetInterestComponentSourceLocator(model, row, evidence),
  ];
}

export function buildCandidateNetInterestComponentSourceLocator(
  model: AvailableComponentDetailModel,
  row: CandidateNetInterestComponentDetailRowView,
  evidence: LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence,
): string {
  return [
    `报告月 ${model.payload.report_month}`,
    `指标 ${model.payload.metric_id} ${model.payload.metric_name}`,
    `后端位置 #${row.backendPosition}`,
    `科目 ${row.accountCode} ${row.accountName}`,
    `证据月 ${evidence.month}`,
    evidence.ledger_file_name,
    `${evidence.sheet}!${evidence.ending_cell}`,
    `行${evidence.row}`,
    `科目格${evidence.account_code_cell}`,
    `SHA256 ${evidence.ledger_sha256}`,
    `锁定哈希 ${evidence.locked_sha256 ?? "未锁定"}`,
    evidence.lock_status,
  ].join(" | ");
}

export function buildCandidateNetInterestComponentDetailCsv(
  model: AvailableComponentDetailModel,
  rows: readonly CandidateNetInterestComponentDetailRowView[],
): CandidateNetInterestComponentDetailCsvArtifact {
  const headers = [
    "backend_position",
    "row_status",
    "account_code",
    "account_name",
    "currency",
    "effective_component_weight",
    "effective_net_weight",
    "matched_terms",
    "current_ending_yuan",
    "previous_ending_yuan",
    "two_month_prior_ending_yuan",
    "current_value_yi",
    "previous_value_yi",
    "component_delta_yi",
    "contribution_to_net_delta_yi",
    ...sourceHeaders(1),
    ...sourceHeaders(2),
    ...sourceHeaders(3),
    "report_month",
    "report_date",
    "metric_id",
    "metric_name",
    "unit",
    "basis",
    "method",
    "contract_version",
    "analysis_kind",
    "status",
    "quality_status",
    "formal_use_allowed",
    "certification_effect",
    "driver_status",
    "foot_status",
    "rule_version",
    "rule_hash",
    "parent_idempotency_key",
    "idempotency_key",
  ];
  const records = rows.map((row) => [
    row.backendPosition,
    row.rowStatus,
    row.accountCode,
    row.accountName,
    row.currency,
    row.effectiveComponentWeight,
    row.effectiveNetWeight,
    row.matchedTerms.map((term) => (
      `${term.source}:${term.level}:${term.code}:${term.weight}`
    )).join(" + "),
    row.currentEndingYuan,
    row.previousEndingYuan,
    row.twoMonthPriorEndingYuan,
    row.currentValueYi,
    row.previousValueYi,
    row.componentDeltaYi,
    row.contributionToNetDeltaYi,
    ...row.sourceEvidence.flatMap((evidence) => sourceValues(model, row, evidence)),
    model.payload.report_month,
    model.payload.report_date,
    model.payload.metric_id,
    model.payload.metric_name,
    model.payload.unit,
    model.payload.basis,
    model.payload.method,
    model.payload.contract_version,
    model.payload.analysis_kind,
    model.payload.status,
    model.payload.quality_status,
    model.payload.formal_use_allowed,
    model.payload.certification_effect,
    model.payload.driver_status,
    model.payload.foot_status,
    model.payload.rule_version,
    model.payload.rule_hash,
    model.payload.parent_idempotency_key,
    model.payload.idempotency_key,
  ]);
  const content = [headers, ...records]
    .map((record) => record.map(csvCell).join(","))
    .join("\r\n");
  const safeMetricId = model.payload.metric_id.replace(/[^a-zA-Z0-9._-]/g, "-");
  const safeReportMonth = model.payload.report_month.replace(/[^0-9]/g, "");
  return {
    filename: `ledger-pnl-net-interest-component-${safeReportMonth}-${safeMetricId}.csv`,
    content: `\uFEFF${content}\r\n`,
  };
}

export function downloadCandidateNetInterestComponentDetailCsv(
  artifact: CandidateNetInterestComponentDetailCsvArtifact,
): void {
  const objectUrl = URL.createObjectURL(new Blob([artifact.content], {
    type: "text/csv;charset=utf-8",
  }));
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = artifact.filename;
  anchor.hidden = true;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }
}
