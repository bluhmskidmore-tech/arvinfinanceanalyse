// Daily judgment strip, decision summary and market state card for the stock-analysis page model.
import type { LivermoreMarketGateState, LivermoreStrategyPayload } from "../../../api/contracts";
import { buildMarketGateMacroDisclosure, formatMarketGateMacroDisclosureDetail } from "../../market-data/lib/livermoreStrategyModel";
import type { StockDailyJudgmentStrip, StockDecisionSummary, StockMarketStateCard } from "./stockAnalysisPageModel.types";
import { formatPercent, formatRatioAsPercent } from "./stockAnalysisPageModel.format";
import {
  localizeBasisLabel,
  localizeDataGapStatus,
  localizeFallbackMode,
  localizeMarketDataStatus,
  localizeMetaQualityFlag,
  localizeMetaVendorStatus,
  localizeStockBackendText,
  localizeStockDataFamily,
} from "./stockAnalysisPageModel.localize";
import { actionableDiagnostics, actionableUnsupportedOutputs, activeDataGaps } from "./stockAnalysisPageModel.shared";
import { buildCandidateReviewQueue, buildReviewQueueEmptyState } from "./stockAnalysisPageModel.candidates";

function mapGateStateToTone(state: LivermoreMarketGateState): "进攻" | "中性" | "防御" {
  if (state === "HOT" || state === "WARM") return "进攻";
  if (
    state === "OVERHEAT" ||
    state === "OFF" ||
    state === "STALE" ||
    state === "NO_DATA" ||
    state === "PENDING_DATA"
  ) {
    return "防御";
  }
  return "中性";
}

export function buildDailyJudgmentStrip(payload: LivermoreStrategyPayload): StockDailyJudgmentStrip {
  const gate = payload.market_gate;
  const tone = mapGateStateToTone(gate.state);
  const headline = `今日市场状态：${tone} — 通过 ${gate.passed_conditions} / ${gate.required_conditions} 条门控`;
  const gateChip = `门控 ${gate.passed_conditions}/${gate.required_conditions}`;
  const exposureChip = `暴露 ${formatRatioAsPercent(gate.exposure)}`;
  const items = [...(payload.sector_rank?.items ?? [])].sort((a, b) => a.rank - b.rank);
  const strongest = items[0];
  const weakest = items.length ? items[items.length - 1] : undefined;
  return {
    headline,
    gateChip,
    exposureChip,
    strongestSectorChip: strongest
      ? `最强 ${strongest.sector_name} (${formatPercent(strongest.avg_pctchange)})`
      : "最强板块：待补",
    weakestSectorChip: weakest
      ? `最弱 ${weakest.sector_name} (${formatPercent(weakest.avg_pctchange)})`
      : "最弱板块：待补",
  };
}

function countBoundaryItems(payload: LivermoreStrategyPayload): number {
  return (
    actionableDiagnostics(payload).length +
    activeDataGaps(payload).length +
    actionableUnsupportedOutputs(payload).length
  );
}

export function buildDecisionSummary(
  payload: LivermoreStrategyPayload,
  meta: Partial<{
    quality_flag: string;
    vendor_status: string;
    fallback_mode: string;
  }> = {},
): StockDecisionSummary {
  const strip = buildDailyJudgmentStrip(payload);
  const queue = buildCandidateReviewQueue(payload);
  const firstReview = queue[0];
  const qualityFlag = meta.quality_flag ?? "待补";
  const vendorStatus = meta.vendor_status ?? "待补";
  const fallbackMode = meta.fallback_mode ?? "none";
  const isFallback = fallbackMode !== "none";
  const fallbackLabel = isFallback ? ` / ${localizeFallbackMode(fallbackMode)}` : "";
  const dataFreshnessOk = qualityFlag === "ok" && vendorStatus === "ok" && !isFallback;
  const candidateCount = queue.length;
  const boundaryCount = countBoundaryItems(payload);

  return {
    headline: strip.headline,
    gateLabel: strip.gateChip,
    exposureLabel: `观察暴露 ${formatRatioAsPercent(payload.market_gate.exposure)}`,
    strongestSectorLabel: strip.strongestSectorChip,
    weakestSectorLabel: strip.weakestSectorChip,
    candidateCountLabel: `候选 ${candidateCount}`,
    dataFreshnessLabel: `${dataFreshnessOk ? "数据正常" : "数据需复核"} ${localizeMetaQualityFlag(
      qualityFlag,
    )} / ${localizeMetaVendorStatus(vendorStatus)}${fallbackLabel}`,
    boundaryLabel: boundaryCount > 0 ? `${boundaryCount} 条边界` : "边界清晰",
    nextReviewAction: firstReview
      ? `下一步：先复核 ${firstReview.stockName}（${firstReview.stockCode}），${firstReview.sectorName}，距观察位 ${firstReview.distanceToBreakoutPct}。`
      : buildReviewQueueEmptyState(payload).detail,
    basisLabel: localizeBasisLabel(payload.basis),
    asOfLabel: payload.as_of_date ?? "日期待补",
  };
}

/** @deprecated Stage 1.5 — 已由 inline meta + Drawer 替代正文列表；保留给需要纯文本的诊断导出 */
export function buildMarketStateCard(
  payload: LivermoreStrategyPayload,
): StockMarketStateCard {
  const gate = payload.market_gate;
  // 选股页暴露标签统一用百分比（如"观察暴露 40%"），宏观调节行保持同一格式。
  const macroDisclosure = buildMarketGateMacroDisclosure(gate, { exposureFormat: "percent" });
  const warnings = [
    ...payload.diagnostics
      .filter((item) => item.severity !== "info")
      .map((item) => localizeStockBackendText(item.message, item.input_family)),
    ...payload.data_gaps
      .filter((gap) => gap.status !== "ready")
      .map(
        (gap) =>
          `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(
            gap.status,
          )}：${localizeStockBackendText(gap.evidence, gap.input_family)}`,
      ),
  ];

  return {
    title: "市场状态",
    state: localizeMarketDataStatus(gate.state),
    exposureLabel: formatRatioAsPercent(gate.exposure),
    passedLabel: `${gate.passed_conditions} / ${gate.required_conditions} 条件通过`,
    basisLabel: localizeBasisLabel(payload.basis),
    warnings,
    macroDisclosure,
    macroDisclosureDetail: formatMarketGateMacroDisclosureDetail(macroDisclosure),
    conditions: gate.conditions.map((condition) => {
      const unknownVendorCondition = [
        condition.key,
        condition.label,
        condition.evidence,
        condition.source_series_id,
      ].some((value) => value && isTechnicalMarketConditionText(value));
      return {
        key: condition.key,
        label: unknownVendorCondition ? "条件待确认" : localizeMarketConditionLabel(condition.label),
        status: condition.status,
        evidence: unknownVendorCondition ? "说明待确认" : localizeMarketConditionEvidence(condition.evidence),
      };
    }),
  };
}

function localizeMarketConditionLabel(label: string): string {
  const value = label.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactLabels: Record<string, string> = {
    "csi300 close > ma60": "沪深300收盘价 > MA60",
    "csi300 ma20 > ma60": "沪深300 MA20 > MA60",
    "5-day breadth > 0": "5日市场宽度 > 0",
    "limit-up seal/break quality positive": "涨停封板/破板质量为正",
  };
  if (exactLabels[normalized]) {
    return exactLabels[normalized];
  }
  if (isTechnicalMarketConditionText(value)) {
    return "条件待确认";
  }
  return value.replace(/\bCSI300\b/g, "沪深300").replace(/\bclose\b/gi, "收盘价");
}

function localizeMarketConditionEvidence(evidence: string): string {
  const value = evidence.trim();
  const normalized = value.toLowerCase().replace(/\s+/g, " ");
  const exactEvidence: Record<string, string> = {
    "close is above ma60.": "收盘价高于 MA60。",
    "close is below ma60.": "收盘价低于 MA60。",
    "ma20 is above ma60.": "MA20 高于 MA60。",
    "breadth inputs are not landed for the phase 1 slice.": "5日市场宽度输入尚未落地，当前阶段不可用。",
    "limit-up quality inputs are not landed for the phase 1 slice.": "涨停质量输入尚未落地，当前阶段不可用。",
  };
  if (exactEvidence[normalized]) {
    return exactEvidence[normalized];
  }
  if (isTechnicalMarketConditionText(value)) {
    return "说明待确认";
  }
  return value
    .replace(/\b(MA\d+)\s+is\s+above\b/gi, "$1 高于")
    .replace(/\b(MA\d+)\s+is\s+below\b/gi, "$1 低于")
    .replace(/\bclose\s+is\s+above\b/gi, "收盘价高于")
    .replace(/\bclose\s+is\s+below\b/gi, "收盘价低于")
    .replace(/\babove\b/gi, "高于")
    .replace(/\bbelow\b/gi, "低于")
    .replace(/\.$/, "。");
}

function isTechnicalMarketConditionText(value: string): boolean {
  const normalized = value.toLowerCase();
  return (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("choice_stock") ||
    normalized.includes("source_table")
  );
}
