import type {
  BalanceMovementPayload,
  BalanceMovementBucket,
  ResultMeta,
  BalanceDifferenceAttributionWaterfall,
  BalanceZqtzMaturityStructure,
  BalanceZqtzConcentrationAnalysis,
} from "../../../api/contracts";
import type { BusinessMomMove, BalanceMovementDriver } from "./balanceMovementBusinessModel";
import type {
  BalanceExplanationClosure,
  AnalysisDimensionCard,
  HistoricalAnomalyDiagnostics,
} from "./balanceMovementDiagnostics";
import { SAME_DAY_CLOSURE_NOTE, PERIOD_CLOSURE_NOTE } from "./balanceMovementDiagnostics";
import { counterpartyAmountText } from "./balanceMovementReconciliationModel";
import {
  formatPct,
  formatSignedYiCell,
  sourceNotePreview,
  formatSignedYiNumber,
  formatYiCell,
} from "./balanceMovementPresentation";

function csvCell(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildCsv(rows: Array<Array<string | number | boolean | null | undefined>>) {
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}

export function downloadCsv(filename: string, content: string) {
  const blob = new Blob(["\uFEFF", content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function buildBalanceMovementCsv(options: {
  result: BalanceMovementPayload;
  resultMeta: ResultMeta | null;
  businessTopMove: BusinessMomMove | undefined;
  accountingTopDriver: BalanceMovementDriver | undefined;
  residualComponent: BalanceDifferenceAttributionWaterfall["components"][number] | undefined;
  unsupportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  maturityStructure: BalanceZqtzMaturityStructure | null;
  concentrationAnalysis: BalanceZqtzConcentrationAnalysis | null;
  explanationClosure: BalanceExplanationClosure | null;
  dimensionCards: AnalysisDimensionCard[];
  historicalAnomalyDiagnostics: HistoricalAnomalyDiagnostics;
  selectedBucket?: BalanceMovementBucket | "all";
  requestedReportDate?: string;
  readStatus?: string;
}) {
  const {
    result,
    resultMeta,
    businessTopMove,
    accountingTopDriver,
    residualComponent,
    unsupportedComponents,
    maturityStructure,
    concentrationAnalysis,
    explanationClosure,
    dimensionCards,
    historicalAnomalyDiagnostics,
    selectedBucket = "all",
    requestedReportDate,
    readStatus,
  } = options;
  const selectedRows = result.rows.filter((row) => selectedBucket === "all" || row.basis_bucket === selectedBucket);
  const selectedDecomposition = result.basis_movement_decomposition?.buckets.filter(
    (bucket) => selectedBucket === "all" || bucket.basis_bucket === selectedBucket,
  ) ?? [];
  const residualRatioText =
    explanationClosure?.residualRatioPct === null ||
    explanationClosure?.residualRatioPct === undefined
      ? ""
      : formatPct(explanationClosure.residualRatioPct);
  const csvRows: Array<Array<string | number | boolean | null | undefined>> = [
    ["section", "field", "value", "note"],
    ["meta", "report_date", result.report_date, ""],
    ["meta", "requested_report_date", requestedReportDate || resultMeta?.requested_report_date || result.report_date, ""],
    ["meta", "resolved_report_date", resultMeta?.resolved_report_date || result.report_date, ""],
    ["meta", "currency_basis", result.currency_basis, ""],
    ["meta", "selected_bucket", selectedBucket, "核心对账及会计组件按该桶复核；全资产诊断保持全资产范围"],
    ["meta", "read_status", readStatus ?? "not_recorded", "缓存读取失败不代表已确认新版本"],
    ["meta", "detail_position_currency_basis", result.zqtz_maturity_structure?.meta.zqtz_currency_basis ?? result.zqtz_concentration_analysis?.meta.zqtz_currency_basis, "与主链 position_source_basis 分别核对"],
    ["meta", "accounting_controls", result.accounting_controls.join(";"), ""],
    ["meta", "excluded_controls", result.excluded_controls.join(";"), ""],
    ["meta", "accounting_source_tables", result.basis_movement_decomposition?.meta.source_tables.join(";"), ""],
    ["meta", "accounting_source_scope", result.basis_movement_decomposition?.meta.source_scope, ""],
    ["meta", "accounting_prior_report_date", result.basis_movement_decomposition?.meta.prior_report_date, ""],
    ["meta", "quality_flag", resultMeta?.quality_flag, ""],
    ["meta", "trace_id", resultMeta?.trace_id, ""],
    ["meta", "rule_version", resultMeta?.rule_version, ""],
    ["meta", "source_version", resultMeta?.source_version, ""],
    ["meta", "tables_used", resultMeta?.tables_used?.join(";"), ""],
    ["meta", "evidence_rows", resultMeta?.evidence_rows, ""],
    [
      "dimension",
      "business_top_move",
      businessTopMove
        ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
        : "",
      businessTopMove ? sourceNotePreview(businessTopMove.sourceNote) : "",
    ],
    [
      "dimension",
      "accounting_basis_top_move",
      accountingTopDriver
        ? `${accountingTopDriver.bucket} ${formatSignedYiNumber(accountingTopDriver.balanceChangeYi)} 亿`
        : "",
      accountingTopDriver ? `contribution_pct=${formatPct(accountingTopDriver.contributionPct)}` : "",
    ],
    [
      "dimension",
      "residual_unclassified",
      residualComponent ? `${formatSignedYiCell(residualComponent.amount)} 亿` : "",
      "未分类残差只用于闭合，不反推估值差或外币折算差。",
    ],
    [
      "dimension",
      "unsupported_components",
      unsupportedComponents.map((component) => component.component_label).join(";"),
      "未支持，不反推。",
    ],
    [
      "dimension",
      "maturity_coverage",
      maturityStructure ? formatPct(maturityStructure.meta.coverage_pct) : "",
      maturityStructure?.meta.status ?? "",
    ],
    [
      "dimension",
      "concentration_coverage",
      concentrationAnalysis ? formatPct(concentrationAnalysis.meta.coverage_pct) : "",
      concentrationAnalysis?.meta.status ?? "",
    ],
    [
      "diagnostic",
      "explanation_closure",
      explanationClosure?.headline,
      explanationClosure?.note,
    ],
    [
      "diagnostic",
      "residual_ratio",
      residualRatioText,
      "页面诊断阈值，不是正式指标",
    ],
    ...dimensionCards.flatMap((card) =>
      card.tags.map((tag) => ["diagnostic", `${card.key}_tag`, tag.label, tag.tone]),
    ),
    [
      "historical_anomaly",
      "headline",
      historicalAnomalyDiagnostics.headline,
      "页面诊断提示，不是正式风险指标",
    ],
    [
      "historical_anomaly",
      "sample_count",
      historicalAnomalyDiagnostics.sampleCount,
      historicalAnomalyDiagnostics.baselinePairCount > 0
        ? `baseline_pairs=${historicalAnomalyDiagnostics.baselinePairCount}`
        : "历史样本不足",
    ],
    ...historicalAnomalyDiagnostics.accountingSignals.map((signal) => [
      "historical_anomaly",
      `accounting_${signal.bucket}`,
      `${formatSignedYiCell(signal.currentDelta)} 亿`,
      `${signal.headline}${signal.directionReversal ? "；方向反转" : ""}`,
    ]),
    ...historicalAnomalyDiagnostics.businessSignals.map((signal) => [
      "historical_anomaly",
      "business_move",
      `${signal.label} ${formatSignedYiCell(signal.currentDelta)} 亿`,
      `高于近 ${signal.baselineCount} 期常态`,
    ]),
    [],
    [
      "basis_bucket",
      "previous_balance_yi",
      "current_balance_yi",
      "balance_change_yi",
      "contribution_pct",
      "reconciliation_status",
      "chain_status",
      "position_source_basis",
      "position_amount_yi",
      "accounting_control_amount_yi",
      "diagnostic_difference_yi",
      "source_version",
      "rule_version",
    ],
    ...selectedRows.map((row) => [
      row.basis_bucket,
      formatYiCell(row.previous_balance),
      formatYiCell(row.current_balance),
      formatSignedYiCell(row.balance_change),
      formatPct(row.contribution_pct),
      row.reconciliation_status,
      row.chain_status ?? "",
      row.position_source_basis ?? "",
      counterpartyAmountText(row, formatYiCell(row.zqtz_amount)),
      formatYiCell(row.gl_amount),
      counterpartyAmountText(row, formatSignedYiCell(row.reconciliation_diff)),
      row.source_version,
      row.rule_version,
    ]),
    [],
    ["accounting_component", "basis_bucket", "label", "account_code_pattern", "previous_balance_yi", "current_balance_yi", "balance_change_yi", "source_note", "is_supported"],
    ...selectedDecomposition.flatMap((bucket) => bucket.rows.map((row) => [
      "accounting_component", bucket.basis_bucket, row.component_label, row.account_code_pattern,
      formatYiCell(row.previous_balance), formatYiCell(row.current_balance), formatSignedYiCell(row.balance_change), row.source_note, row.is_supported,
    ])),
    ["period_closure", "basis_bucket", "residual_yi", "closing_check_yi", "note"],
    ...selectedDecomposition.map((bucket) => [
      "period_closure", bucket.basis_bucket, formatSignedYiCell(bucket.residual_amount), formatSignedYiCell(bucket.closing_check), PERIOD_CLOSURE_NOTE,
    ]),
    [],
    ["same_day_closure", "all_buckets", formatSignedYiCell(result.difference_attribution_waterfall?.closing_check), SAME_DAY_CLOSURE_NOTE],
    ["waterfall_component", "label", "value", "note"],
    ...(result.difference_attribution_waterfall?.components ?? []).map((component) => [
      component.component_key,
      component.component_label,
      component.is_supported === false ? "待拆分" : `${formatSignedYiCell(component.amount)} 亿`,
      component.evidence_note,
    ]),
  ];
  return `${buildCsv(csvRows)}\r\n`;
}
