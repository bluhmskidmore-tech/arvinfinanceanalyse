/**
 * Legacy page-model builders with no current page consumer.
 *
 * These exports were moved verbatim out of `stockAnalysisPageModel.ts` because
 * nothing on the /stock-analysis first screen (or its lazy deep-research
 * subtree) imports them anymore; only `src/test/StockAnalysisPageModel.test.ts`
 * still exercises their contracts. Keeping them here keeps the first-screen
 * model file honest and keeps this code out of the route-entry chunk. If a
 * page surface starts consuming one of these builders again, import it from
 * here (or move it back next to its consumers).
 */
import type {
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../../../api/contracts";
import {
  buildCandidateReviewQueue,
  buildClosedLoopSummary,
  buildDataBoundarySummary,
  buildRiskExitRows,
  buildSectorRows,
  buildSectorViewRows,
  clampRatio,
  formatRatioAsPercent,
  isMetaBoundary,
  localizeBasisLabel,
  localizeDataGapStatus,
  localizeDiagnosticScope,
  localizeFallbackMode,
  localizeMarketDataStatus,
  localizeMetaQualityFlag,
  localizeMetaVendorStatus,
  localizeStockBackendText,
  localizeStockDataFamily,
  sectorRankFormulaGovernanceLabel,
} from "./stockAnalysisPageModel";
import type {
  StockClosedLoopTone,
  StockSectorViewKind,
  StockSectorViewRow,
  StockViewModelMeta,
} from "./stockAnalysisPageModel";

export type StockMetaSegment = {
  key: string;
  text: string;
};

export type StockAnalysisKpiKey =
  | "market-state"
  | "review-queue"
  | "sector-strength"
  | "risk-observation"
  | "closed-loop"
  | "data-boundary";

export type StockAnalysisKpiItem = {
  key: StockAnalysisKpiKey;
  label: string;
  value: string;
  detail: string;
  tone: StockClosedLoopTone;
  gaugeValue?: number;
};

export type StockAnalysisPagePurpose = {
  eyebrow: string;
  title: string;
  subtitle: string;
  asOfLine: string;
  dataStatusLine: string;
};

export function buildStockAnalysisPagePurpose(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockAnalysisPagePurpose {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  const aligned = quality === "ok" && vendor === "ok" && fallback === "none";
  const asOf = payload.as_of_date ?? "日期待补";
  return {
    eyebrow: "趋势策略 · 只读复核台",
    title: "股票策略复核台",
    subtitle: "只读复核，不生成交易指令",
    asOfLine: `观察日 ${asOf}`,
    dataStatusLine: aligned
      ? `数据状态：已对齐（${asOf}）`
      : `数据状态：待复核 · ${localizeMetaQualityFlag(quality)} / ${localizeMetaVendorStatus(vendor)}${
          fallback !== "none" ? ` / ${localizeFallbackMode(fallback)}` : ""
        }`,
  };
}

export function buildInlineMetaSegments(
  payload: LivermoreStrategyPayload,
  extras: Partial<{
    quality_flag: string;
    vendor_status: string;
    source_version: string;
    rule_version: string;
    fallback_mode: string;
  }>,
): StockMetaSegment[] {
  const out: StockMetaSegment[] = [
    { key: "as_of", text: payload.as_of_date ?? "日期待补" },
    { key: "source_version", text: extras.source_version ?? "待补" },
    { key: "rule_version", text: extras.rule_version ?? "待补" },
    { key: "quality_flag", text: extras.quality_flag ? localizeMetaQualityFlag(extras.quality_flag) : "待补" },
    { key: "vendor_status", text: extras.vendor_status ? localizeMetaVendorStatus(extras.vendor_status) : "待补" },
    { key: "fallback_mode", text: extras.fallback_mode ? localizeFallbackMode(extras.fallback_mode) : "待补" },
  ];
  return out;
}

export function buildStockAnalysisKpiStrip(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
  meta: StockViewModelMeta = {},
): StockAnalysisKpiItem[] {
  const queue = buildCandidateReviewQueue(payload);
  const sectors = buildSectorRows(payload);
  const riskRows = buildRiskExitRows(payload, confluence);
  const boundarySummary = buildDataBoundarySummary(payload, meta);
  const closedLoopSummary = buildClosedLoopSummary(payload, confluence, meta);
  const strongest = sectors[0];
  const weakest = sectors.length ? sectors[sectors.length - 1] : null;
  const riskTriggered = riskRows.filter((row) => row.status === "triggered").length;
  const riskWatch = riskRows.filter((row) => row.status === "watch").length;
  const hasBoundary = boundarySummary.boundaryCount > 0 || isMetaBoundary(meta);

  return [
    {
      key: "market-state",
      label: "市场状态",
      value: localizeMarketDataStatus(payload.market_gate.state),
      detail: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
      tone: hasBoundary ? "warning" : "positive",
      gaugeValue: clampRatio(payload.market_gate.exposure),
    },
    {
      key: "review-queue",
      label: "复核队列",
      value: String(queue.length),
      detail: queue[0] ? `优先 ${queue[0].stockName} / ${queue[0].sectorName}` : "候选待补",
      tone: queue.length > 0 ? "positive" : "neutral",
      gaugeValue: clampRatio(queue.length / 6),
    },
    {
      key: "sector-strength",
      label: "板块强弱",
      value: strongest ? strongest.sectorName : "待补",
      detail: weakest ? `弱侧 ${weakest.sectorName} / ${weakest.pctChange}` : "弱侧待补",
      tone: strongest ? "positive" : "warning",
      gaugeValue: clampRatio(strongest?.scoreValue),
    },
    {
      key: "risk-observation",
      label: "风险观察",
      value: String(riskRows.length),
      detail: `触发 ${riskTriggered} / 观察 ${riskWatch}`,
      tone: riskTriggered > 0 ? "negative" : riskWatch > 0 ? "warning" : "positive",
      gaugeValue: clampRatio(riskRows.length / 4),
    },
    {
      key: "closed-loop",
      label: "闭环状态",
      value: closedLoopSummary.referenceRating.label,
      detail: closedLoopSummary.summaryLabel,
      tone: closedLoopSummary.referenceRating.tone,
      gaugeValue: closedLoopSummary.referenceRating.tone === "positive" ? 1 : closedLoopSummary.referenceRating.tone === "warning" ? 0.55 : 0.28,
    },
    {
      key: "data-boundary",
      label: "数据边界",
      value: String(boundarySummary.boundaryCount),
      detail: boundarySummary.detailLabel,
      tone: boundarySummary.boundaryCount > 0 || isMetaBoundary(meta) ? "warning" : "positive",
      gaugeValue: clampRatio(boundarySummary.boundaryCount / 6),
    },
  ];
}

export function buildDataBoundaryNotes(payload: LivermoreStrategyPayload): string[] {
  const notes = [`口径：${localizeBasisLabel(payload.basis)}`, `策略：${payload.strategy_name || "待补"}`];
  for (const diag of payload.diagnostics) {
    const severityLabel = diag.severity === "error" ? "错误" : diag.severity === "warning" ? "预警" : "信息";
    notes.push(
      `${severityLabel} ${localizeDiagnosticScope(diag.input_family)}：${localizeStockBackendText(
        diag.message,
        diag.input_family,
      )}`,
    );
  }
  if (payload.as_of_date) {
    notes.push(`数据日期：${payload.as_of_date}`);
  }
  if (payload.sector_rank?.formula_version) {
    notes.push(`板块强弱公式：${payload.sector_rank.formula_version}`);
    notes.push(`板块强弱规则状态：${sectorRankFormulaGovernanceLabel(payload.sector_rank)}`);
    if (payload.sector_rank.formula_note) {
      notes.push(`板块强弱说明：${localizeStockBackendText(payload.sector_rank.formula_note, "sector_strength")}`);
    }
  }
  if (payload.stock_candidates?.formula_version) {
    notes.push(`趋势候选公式：${payload.stock_candidates.formula_version}`);
  }
  if (payload.hybrid_fusion_candidates?.formula_version) {
    notes.push(`融合池公式：${payload.hybrid_fusion_candidates.formula_version}`);
  }
  if (payload.risk_exit?.formula_version) {
    notes.push(`风险退出公式：${payload.risk_exit.formula_version}`);
  }
  for (const gap of payload.data_gaps) {
    notes.push(
      `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(gap.status)}：${localizeStockBackendText(
        gap.evidence,
        gap.input_family,
      )}`,
    );
  }
  for (const output of payload.unsupported_outputs) {
    notes.push(`${localizeStockDataFamily(output.key)} 阻断：${localizeStockBackendText(output.reason, output.key)}`);
  }
  notes.push(`可用输出：${payload.supported_outputs.map(localizeStockDataFamily).join("、") || "无"}`);
  return notes;
}

export function buildSectorViewModel(
  payload: LivermoreStrategyPayload,
  view: StockSectorViewKind,
): StockSectorViewRow[] {
  return buildSectorViewRows(buildSectorRows(payload), view);
}
