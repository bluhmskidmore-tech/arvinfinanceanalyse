import type {
  BalanceMovementPayload,
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
  } = options;
  const residualRatioText =
    explanationClosure?.residualRatioPct === null ||
    explanationClosure?.residualRatioPct === undefined
      ? ""
      : formatPct(explanationClosure.residualRatioPct);
  const csvRows: Array<Array<string | number | boolean | null | undefined>> = [
    ["section", "field", "value", "note"],
    ["meta", "report_date", result.report_date, ""],
    ["meta", "currency_basis", result.currency_basis, ""],
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
    ],
    ...result.rows.map((row) => [
      row.basis_bucket,
      formatYiCell(row.previous_balance),
      formatYiCell(row.current_balance),
      formatSignedYiCell(row.balance_change),
      formatPct(row.contribution_pct),
      row.reconciliation_status,
      row.chain_status ?? "",
      row.position_source_basis ?? "",
    ]),
    [],
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
