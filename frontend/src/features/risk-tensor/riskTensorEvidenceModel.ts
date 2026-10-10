import type { BlockedReportDate, ResultMeta, RiskTensorPayload } from "../../api/contracts";
import { EM_DASH } from "../../utils/format";
import { describeRiskTensorWarning, fallbackModeLabel, filtersAppliedLabel } from "./riskTensorPresentation";
import { REQUIRED_DURATION_SCOPE_FIELDS, riskTensorPayloadQualityIssues } from "./riskTensorQuality";

export type RiskTensorQualityEvidenceInput = {
  result: RiskTensorPayload | undefined;
  tensorMeta: ResultMeta | undefined;
  reportDate: string;
  blockedReportDates: BlockedReportDate[];
  highlightedBlockedReportDate: BlockedReportDate | undefined;
};

export function buildRiskTensorQualityEvidence({ result, tensorMeta, reportDate, blockedReportDates, highlightedBlockedReportDate }: RiskTensorQualityEvidenceInput) {
  const fallbackStatus = fallbackModeLabel(tensorMeta?.fallback_mode);

  const blockedReportDateSummary = `${blockedReportDates.length} 个陈旧日期已拦截`;

  const metadataTablesUsed = tensorMeta?.tables_used?.filter(Boolean).join(" / ") ?? "";

  const metadataFiltersApplied = filtersAppliedLabel(tensorMeta?.filters_applied);

  const qualityReviewReasons = [
    tensorMeta?.fallback_date ? `fallback_date ${tensorMeta.fallback_date}` : null,
    blockedReportDates.length > 0 ? blockedReportDateSummary : null,
    result?.warnings[0] ? describeRiskTensorWarning(result.warnings[0]) : null,
  ].filter((item): item is string => Boolean(item));

  const qualityReviewReasonSummary =
    qualityReviewReasons.length > 0 ? qualityReviewReasons.join("；") : "查看质量证据";

  const qualityTraceFallbackDetail = tensorMeta?.fallback_date
    ? `${fallbackStatus}；fallback_date ${tensorMeta.fallback_date}`
    : fallbackStatus;

  const qualityTraceBlockedDetail = highlightedBlockedReportDate
    ? `${blockedReportDateSummary}；${highlightedBlockedReportDate.report_date}${
        highlightedBlockedReportDate.reason ? ` ${highlightedBlockedReportDate.reason}` : ""
      }`
    : blockedReportDateSummary;

  const qualityTraceWarningDetail = result?.warnings.filter(Boolean).join(" / ") || "无预警";

  const qualityTraceMetadataDetail = `trace_id ${tensorMeta?.trace_id ?? EM_DASH}；evidence_rows ${
    typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : EM_DASH
  }；tables_used ${metadataTablesUsed || EM_DASH}；filters_applied ${metadataFiltersApplied || EM_DASH}`;

  const payloadQualityIssues = result ? riskTensorPayloadQualityIssues(result) : [];

  const durationCoverageQualityIssues = payloadQualityIssues.filter((item) =>
    item.key === "duration_excluded_count" || REQUIRED_DURATION_SCOPE_FIELDS.some((field) => field.key === item.key),
  );

  const payloadQualityIssueLabels = payloadQualityIssues.map((item) => `${item.label} ${item.issue}`);

  const payloadQualityIssueSummary = payloadQualityIssueLabels.join(" / ");

  const qualityEvidenceStateKey = [
    `evidence_rows:${typeof tensorMeta?.evidence_rows === "number" ? tensorMeta.evidence_rows : "missing"}`,
    `tables_used:${metadataTablesUsed || "missing"}`,
    `filters_applied:${metadataFiltersApplied || "missing"}`,
  ].join("|");

  const qualityLineageStateKey = [
    `source_version:${tensorMeta?.source_version ?? "missing"}`,
    `rule_version:${tensorMeta?.rule_version ?? "missing"}`,
  ].join("|");

  const qualityFallbackStateKey = [
    `fallback_mode:${tensorMeta?.fallback_mode ?? "missing"}`,
    `fallback_date:${tensorMeta?.fallback_date ?? "missing"}`,
  ].join("|");

  const qualityIssuanceStateKey = [
    `basis:${tensorMeta?.basis ?? "missing"}`,
    `cache_version:${tensorMeta?.cache_version ?? "missing"}`,
    `generated_at:${tensorMeta?.generated_at ?? "missing"}`,
  ].join("|");

  const qualityWarningStateKey = `warning:${qualityTraceWarningDetail}`;

  const qualityBlockedDateStateKey = `blocked:${qualityTraceBlockedDetail}`;

  const qualityFlagStateKey = `quality_flag:${result?.quality_flag ?? tensorMeta?.quality_flag ?? "missing"}`;

  const qualityResultKindStateKey = `result_kind:${tensorMeta?.result_kind ?? "missing"}`;

  const qualityStateKey = `${tensorMeta?.trace_id ?? ""}|${result?.report_date ?? reportDate ?? ""}|${payloadQualityIssueSummary}|${qualityEvidenceStateKey}|${qualityLineageStateKey}|${qualityFallbackStateKey}|${qualityIssuanceStateKey}|${qualityWarningStateKey}|${qualityBlockedDateStateKey}|${qualityFlagStateKey}|${qualityResultKindStateKey}`;

  const qualityEvidenceReviewItems = [
    {
      key: "evidence_rows",
      label: "evidence_rows",
      status: typeof tensorMeta?.evidence_rows === "number" ? "已提供" : "未提供",
    },
    {
      key: "tables_used",
      label: "tables_used",
      status: metadataTablesUsed ? "已提供" : "未提供",
    },
    {
      key: "filters_applied",
      label: "filters_applied",
      status: metadataFiltersApplied ? "已提供" : "未提供",
    },
  ];

  const hasMissingQualityEvidence = qualityEvidenceReviewItems.some((item) => item.status === "未提供");

  const missingQualityEvidenceLabels = qualityEvidenceReviewItems
    .filter((item) => item.status === "未提供")
    .map((item) => item.label);

  const qualityIssuanceCopyLines = [
    `basis ${tensorMeta?.basis ?? "未提供"}`,
    `cache_version ${tensorMeta?.cache_version ?? "未提供"}`,
    `generated_at ${tensorMeta?.generated_at ?? "未提供"}`,
  ];

  return {
    result,
    tensorMeta,
    reportDate,
    blockedReportDates,
    highlightedBlockedReportDate,
    fallbackStatus,
    blockedReportDateSummary,
    metadataTablesUsed,
    metadataFiltersApplied,
    qualityReviewReasonSummary,
    qualityTraceFallbackDetail,
    qualityTraceBlockedDetail,
    qualityTraceWarningDetail,
    qualityTraceMetadataDetail,
    payloadQualityIssues,
    durationCoverageQualityIssues,
    payloadQualityIssueSummary,
    qualityStateKey,
    qualityEvidenceReviewItems,
    hasMissingQualityEvidence,
    missingQualityEvidenceLabels,
    qualityIssuanceCopyLines,
  };
}

export type RiskTensorQualityEvidence = ReturnType<typeof buildRiskTensorQualityEvidence>;

export function buildRiskTensorQualityCopyTexts(evidence: RiskTensorQualityEvidence, qualityReviewStateLabel: string) {
  const {
    result,
    tensorMeta,
    reportDate,
    qualityTraceFallbackDetail,
    qualityTraceBlockedDetail,
    qualityTraceWarningDetail,
    qualityTraceMetadataDetail,
    payloadQualityIssueSummary,
    qualityEvidenceReviewItems,
    missingQualityEvidenceLabels,
    qualityIssuanceCopyLines,
  } = evidence;
  const qualityTraceCopyText = [
    "风险张量质量证据",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `复核状态 ${qualityReviewStateLabel}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `fallback ${qualityTraceFallbackDetail}`,
    `陈旧日期 ${qualityTraceBlockedDetail}`,
    `warning ${qualityTraceWarningDetail}`,
    `主读 payload 字段 ${payloadQualityIssueSummary || "全部可解析"}`,
    `证据范围 ${qualityTraceMetadataDetail}`,
    "证据字段复核",
    ...qualityEvidenceReviewItems.map((item) => `${item.label} ${item.status}`),
  ].join("\n");

  const qualityEvidenceRequestCopyText = [
    "风险张量质量证据补证请求",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `缺失字段 ${missingQualityEvidenceLabels.join(" / ") || "无"}`,
    "请在 result_meta 补充 evidence_rows、tables_used、filters_applied 后重新出具",
  ].join("\n");

  const payloadQualityRequestCopyText = [
    "风险张量主读 payload 补证请求",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `异常字段 ${payloadQualityIssueSummary || "无"}`,
    "后端主读字段缺失或不可解析时，页面只保留后端原始展示/占位，不会在前端补算正式指标",
    "请核对风险张量物化任务、字段序列化、result_meta 证据和来源 lineage 后重新出具",
  ].join("\n");

  const combinedQualityRequestCopyText = [
    "风险张量首屏补证包",
    payloadQualityRequestCopyText,
    "",
    qualityEvidenceRequestCopyText,
  ].join("\n");

  const qualityWarningsCopyText = [
    "风险张量质量预警清单",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    ...(result?.warnings ?? []).map((warning, index) => `warning[${index + 1}] ${warning}`),
  ].join("\n");

  const qualityEvidenceReviewRecordCopyText = [
    "风险张量质量证据确认记录",
    `trace_id ${tensorMeta?.trace_id ?? "未提供"}`,
    `报告日 ${result?.report_date ?? reportDate ?? "未提供"}`,
    "确认状态 业务已确认",
    `result_kind ${tensorMeta?.result_kind ?? "未提供"}`,
    ...qualityIssuanceCopyLines,
    `source_version ${tensorMeta?.source_version ?? "未提供"}`,
    `rule_version ${tensorMeta?.rule_version ?? "未提供"}`,
    `quality_flag ${result?.quality_flag ?? tensorMeta?.quality_flag ?? "未提供"}`,
    `fallback ${qualityTraceFallbackDetail}`,
    `陈旧日期 ${qualityTraceBlockedDetail}`,
    `warning ${qualityTraceWarningDetail}`,
    `证据范围 ${qualityTraceMetadataDetail}`,
    `主读 payload 字段 ${payloadQualityIssueSummary || "全部可解析"}`,
    "证据字段复核",
    ...qualityEvidenceReviewItems.map((item) => `${item.label} ${item.status}`),
  ].join("\n");

  return { qualityTraceCopyText, qualityEvidenceRequestCopyText, payloadQualityRequestCopyText, combinedQualityRequestCopyText, qualityWarningsCopyText, qualityEvidenceReviewRecordCopyText };
}
