import type {
  LivermoreCandidateHistoryHorizonStats,
  LivermoreStrategyOptimizationPayload,
} from "../../../api/contracts";
import { localizeStockBackendText } from "./stockAnalysisPageModel";
import {
  backtestPendingDateCount,
  backtestSourceGapDateCount,
  backtestUnsupportedDateCount,
  backtestStatsText,
  formatBacktestPercent,
  formatBacktestSignedPercent,
  strategyBacktestHorizonShortLabels,
} from "./stockAnalysisBacktestModel";
import { localizeRankRangeLabel } from "./stockAnalysisPriorityModel";

export type StrategyOptimizationSummary =
  LivermoreStrategyOptimizationPayload["strategy_summaries"][number];
export type StrategyOptimizationSlice = LivermoreStrategyOptimizationPayload["slices"][number];

const strategyOptimizationCoreKinds = [
  "hybrid_fusion",
  "stock_candidate",
  "factor_screen",
  "theme_breakout",
] as const;

export function buildStrategyOptimizationRows(
  payload: LivermoreStrategyOptimizationPayload | null,
): StrategyOptimizationSummary[] {
  if (!payload) return [];
  const coreKinds = new Set<string>(strategyOptimizationCoreKinds);
  const coreRows = payload.strategy_summaries.filter((row) => coreKinds.has(row.signal_kind));
  return (coreRows.length > 0 ? coreRows : payload.strategy_summaries).slice(0, 3);
}

export function strategyOptimizationPrimaryStats(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  payload: LivermoreStrategyOptimizationPayload | null,
): LivermoreCandidateHistoryHorizonStats | undefined {
  const horizon = payload?.primary_horizon ?? "return_5d";
  return row.stats[horizon];
}

function optimizationUnavailableStatsText(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  stats: LivermoreCandidateHistoryHorizonStats | undefined,
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  if (!payload) return "接口未提供";
  if (
    row.sample_status === "insufficient" ||
    row.recommendation.priority_label === "样本不足" ||
    row.recommendation.action === "pending_more_history"
  ) {
    return "样本不足";
  }
  const sourceGapDateCount = backtestSourceGapDateCount(
    payload.backtest_window_summary,
    row.signal_kind,
  );
  if (sourceGapDateCount > 0) return `历史源不足 · ${sourceGapDateCount}日`;
  const pendingDateCount = backtestPendingDateCount(
    payload.backtest_window_summary,
    row.signal_kind,
  );
  if (pendingDateCount > 0) {
    const missingCount = stats?.missing_count ?? 0;
    return missingCount > 0 ? `自然待成熟 · ${missingCount}条` : `自然待成熟 · ${pendingDateCount}日`;
  }
  const unsupportedDateCount = backtestUnsupportedDateCount(
    payload.backtest_window_summary,
    row.signal_kind,
  );
  if (unsupportedDateCount > 0) return `窗口不支持 · ${unsupportedDateCount}日`;
  const pendingRows = payload.pending_summary.pending_rows;
  if (pendingRows > 0) return `全局待成熟 · ${pendingRows}条`;
  return stats ? "成熟度未提供" : "接口未提供";
}

export function strategyOptimizationPrimaryStatsText(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  const stats = strategyOptimizationPrimaryStats(row, payload);
  return stats && stats.available_count > 0
    ? backtestStatsText(stats)
    : optimizationUnavailableStatsText(row, stats, payload);
}

export function strategyOptimizationDateWeightedText(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  const horizon = payload?.primary_horizon ?? "return_5d";
  const stats = row.date_weighted_stats[horizon];
  if (!stats || stats.available_day_count <= 0) {
    return optimizationUnavailableStatsText(row, strategyOptimizationPrimaryStats(row, payload), payload);
  }
  return `${stats.available_day_count}日等权 ${formatBacktestSignedPercent(stats.avg_return)} / 正收益日 ${formatBacktestPercent(
    stats.positive_day_rate,
  )}`;
}

export function strategyOptimizationHorizonLabel(
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  return strategyBacktestHorizonShortLabels[payload?.primary_horizon ?? "return_5d"];
}

export function strategyOptimizationMaturityStatusText(
  payload: LivermoreStrategyOptimizationPayload | null,
): string {
  if (!payload) return "接口未提供";
  const sourceGapDateCount = backtestSourceGapDateCount(payload.backtest_window_summary);
  if (sourceGapDateCount > 0) return "历史源不足";
  const unsupportedDateCount = backtestUnsupportedDateCount(payload.backtest_window_summary);
  if (unsupportedDateCount > 0) return "窗口不支持";
  if (payload.pending_summary.pending_rows > 0) return "待成熟";
  const horizon = payload.primary_horizon;
  if (payload.strategy_summaries.some((row) => (row.stats[horizon]?.available_count ?? 0) > 0)) {
    return "已有成熟样本";
  }
  if (payload.strategy_summaries.length === 0) return "无样本";
  if (payload.strategy_summaries.some((row) => row.sample_status === "insufficient")) return "样本不足";
  return "成熟度未提供";
}

export function strategyOptimizationReasonLabel(
  row: StrategyOptimizationSummary | StrategyOptimizationSlice,
): string {
  return localizeStockBackendText(row.recommendation.reason, row.signal_kind);
}

export function strategyOptimizationSliceLabel(slice: StrategyOptimizationSlice): string {
  const dimension = slice.dimension.trim().toLowerCase();
  const bucket = slice.bucket.trim();
  const normalizedBucket = bucket.toLowerCase().replace(/[\s-]+/g, "_");
  const normalizedLabel = slice.label.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (
    dimension.includes("external_vendor") ||
    dimension.includes("vendor_") ||
    normalizedBucket.includes("external_vendor") ||
    normalizedBucket.includes("vendor_") ||
    normalizedLabel.includes("external_vendor") ||
    normalizedLabel.includes("vendor_")
  ) {
    return "切片待确认";
  }
  if (dimension === "rank" && /^\d+\s*-\s*\d+$/.test(bucket)) {
    return localizeRankRangeLabel(bucket, null, null, "切片待补");
  }
  const rankLabel = localizeRankRangeLabel(slice.label, null, null, "");
  if (rankLabel) return rankLabel;
  return slice.label || "切片待补";
}

export function strategyOptimizationSlicePair(
  payload: LivermoreStrategyOptimizationPayload | null,
): { strongest: StrategyOptimizationSlice | null; weakest: StrategyOptimizationSlice | null } {
  if (!payload) return { strongest: null, weakest: null };
  const matureSlices = payload.slices.filter(
    (slice) => slice.recommendation.action !== "pending_more_history",
  );
  const strongest =
    [...matureSlices]
      .filter((slice) => slice.recommendation.action === "promote")
      .sort((left, right) => (right.recommendation.score ?? -1) - (left.recommendation.score ?? -1))[0] ??
    [...matureSlices].sort((left, right) => (right.recommendation.score ?? -1) - (left.recommendation.score ?? -1))[0] ??
    null;
  const weakest =
    [...matureSlices]
      .filter((slice) => slice.recommendation.action === "downgrade")
      .sort((left, right) => {
        const leftReturn = left.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
        const rightReturn = right.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
        return leftReturn - rightReturn;
      })[0] ??
    [...matureSlices].sort((left, right) => {
      const leftReturn = left.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
      const rightReturn = right.recommendation.avg_return ?? Number.POSITIVE_INFINITY;
      return leftReturn - rightReturn;
    })[0] ??
    null;
  return { strongest, weakest };
}
