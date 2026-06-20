import type {
  LivermoreCandidateHistoryHorizonKey,
  LivermoreCandidateHistoryPayload,
  LivermoreStrategyScorePayload,
} from "../../../api/contracts";
import type { StockStrategyPanelQueryState } from "./stockAnalysisPageModel";
import { localizeStockBackendText } from "./stockAnalysisPageModel";
import {
  backtestStatsText,
  formatBacktestSignedPercent,
  strategyBacktestHorizonShortLabels,
  strategyDisplayLabel,
} from "./stockAnalysisBacktestModel";

export type StrategyPriorityRow = LivermoreStrategyScorePayload["rows"][number];
export type StrategyMaturity = NonNullable<NonNullable<StrategyPriorityRow["diagnostics"]>["maturity"]>;
export type StrategyTrackedSnapshot = StrategyMaturity["tracked_snapshots"][number];
export type StrategyMaturityCandidate = LivermoreCandidateHistoryPayload["items"][number];

export function formatPriorityScore(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "-" : value.toFixed(1);
}

export function resolvePanelQueryState(input: {
  enabled: boolean;
  isLoading: boolean;
  isError: boolean;
}): StockStrategyPanelQueryState {
  if (!input.enabled) return "idle";
  if (input.isLoading) return "loading";
  if (input.isError) return "error";
  return "ready";
}

export function buildStrategyPriorityHeadline(rows: StrategyPriorityRow[]): string {
  const sufficientRows = rows.filter((row) => row.sample_status === "sufficient");
  if (rows.length === 0 || sufficientRows.length === 0) {
    return "样本不足";
  }
  const priorityCandidates = sufficientRows.filter(
    (row) => row.priority_label === "优先复核" && (row.diagnostics?.risk_flags ?? []).length === 0,
  );
  const priorityRows = priorityCandidates.filter((row) => row.diagnostics?.maturity?.status !== "narrow");
  if (priorityRows.length > 0) {
    return `优先复核：${priorityRows.map((row) => strategyDisplayLabel(row.strategy_label, row.signal_kind)).join("、")}`;
  }
  if (priorityCandidates.length > 0) {
    return `优先观察：${priorityCandidates
      .map((row) => strategyDisplayLabel(row.strategy_label, row.signal_kind))
      .join("、")}`;
  }
  return "当前状态降权观察";
}

export function strategyPrioritySummaryReason(rows: StrategyPriorityRow[]): string {
  const firstPriority = rows.find((row) => row.priority_label === "优先复核");
  if (firstPriority) return strategyPriorityReasonLabel(firstPriority);
  const firstInsufficient = rows.find((row) => row.sample_status === "insufficient");
  if (firstInsufficient) return strategyPriorityReasonLabel(firstInsufficient);
  return rows[0] ? strategyPriorityReasonLabel(rows[0]) : "暂无当前状态策略评分。";
}

export function strategyPriorityReasonLabel(row: StrategyPriorityRow): string {
  return localizeStockBackendText(row.reason, row.signal_kind);
}

export function localizeRankRangeLabel(
  label: string | null | undefined,
  rankFrom?: number | null,
  rankTo?: number | null,
  fallback = "排名待补",
): string {
  if (typeof rankFrom === "number" && Number.isFinite(rankFrom) && typeof rankTo === "number" && Number.isFinite(rankTo)) {
    return `第 ${rankFrom}-${rankTo} 名`;
  }
  const value = label?.trim() ?? "";
  const rankLabel = value.match(/^(?:rank\s*)?(\d+)\s*-\s*(\d+)$/i);
  if (rankLabel) return `第 ${rankLabel[1]}-${rankLabel[2]} 名`;
  return value || fallback;
}

export function strategyPriorityScopeLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "排序范围待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "排序范围待确认";
  }
  return value;
}

export function strategyRiskFlagLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "风险待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const lower = value.toLowerCase();
  const labels: Record<string, string> = {
    long_window_risk: "长窗口风险",
  };
  if (labels[normalized]) return labels[normalized];
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    lower.includes("source table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "风险待确认";
  }
  return value;
}

export function strategyPriorityStatusLabel(label: string | null | undefined) {
  const value = label?.trim();
  if (!value) return "状态待确认";
  const normalized = value.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    优先复核: "优先复核",
    降权观察: "降权观察",
    继续观察: "继续观察",
    样本不足: "样本不足",
  };
  if (labels[value]) return labels[value];
  if (labels[normalized]) return labels[normalized];
  if (normalized.includes("external_vendor") || normalized.includes("vendor_")) return "状态待确认";
  return "状态待确认";
}

export function strategyPriorityDiagnosticLabels(row: StrategyPriorityRow): string[] {
  const diagnostics = row.diagnostics;
  if (!diagnostics) return [];
  const labels: string[] = [];
  if (diagnostics.priority_scope_label) {
    const scopeStats = diagnostics.priority_scope_stats?.return_5d;
    const scopeStatsText = scopeStats ? backtestStatsText(scopeStats) : null;
    const scopeLabel = strategyPriorityScopeLabel(diagnostics.priority_scope_label);
    labels.push(scopeStatsText ? `${scopeLabel} ${scopeStatsText}` : scopeLabel);
  }
  if (diagnostics.maturity?.status === "narrow") {
    labels.push(`${diagnostics.maturity.label} ${localizeStockBackendText(diagnostics.maturity.reason, row.signal_kind)}`);
  }
  for (const bucket of diagnostics.rank_buckets ?? []) {
    const bucketStatusLabel = strategyPriorityStatusLabel(bucket.priority_label);
    if (!bucket.included_in_priority && (bucket.priority_label === "降权观察" || bucketStatusLabel === "状态待确认")) {
      labels.push(`${localizeRankRangeLabel(bucket.label, bucket.rank_from, bucket.rank_to)} ${bucketStatusLabel}`);
    }
  }
  for (const flag of diagnostics.risk_flags ?? []) {
    if (flag.label) {
      labels.push(strategyRiskFlagLabel(flag.label));
    }
  }
  return Array.from(new Set(labels)).slice(0, 4);
}

export function resolveStrategyMaturityRow(rows: StrategyPriorityRow[]): StrategyPriorityRow | null {
  return (
    rows.find(
      (row) =>
        row.diagnostics?.priority_scope === "rank<=10" &&
        (row.diagnostics?.maturity?.tracked_snapshots ?? []).length > 0,
    ) ??
    rows.find((row) => (row.diagnostics?.maturity?.tracked_snapshots ?? []).length > 0) ??
    null
  );
}

export function buildStrategyMaturityWindow(row: StrategyPriorityRow | null): {
  maturity: StrategyMaturity | null;
  snapshots: StrategyTrackedSnapshot[];
  snapshotFrom: string | null;
  snapshotTo: string | null;
} {
  const maturity = row?.diagnostics?.maturity ?? null;
  const snapshots = [...(maturity?.tracked_snapshots ?? [])].slice(-6).reverse();
  return {
    maturity,
    snapshots,
    snapshotFrom: snapshots[snapshots.length - 1]?.snapshot_as_of_date ?? null,
    snapshotTo: snapshots[0]?.snapshot_as_of_date ?? null,
  };
}

export function strategyMaturityRemainingText(maturity: StrategyMaturity): string {
  const remaining = Math.max(maturity.min_mature_snapshot_count - maturity.mature_snapshot_count, 0);
  return remaining > 0 ? `还差 ${remaining} 个成熟快照` : "成熟快照已达标";
}

export function strategyMaturityHorizonText(
  snapshot: StrategyTrackedSnapshot,
  horizon: LivermoreCandidateHistoryHorizonKey,
): string {
  const stats = snapshot.horizons[horizon];
  const label = strategyBacktestHorizonShortLabels[horizon];
  if (!stats || stats.status === "pending" || stats.available_count <= 0) {
    return `${label} 待成熟`;
  }
  const statusText = stats.status === "partial" ? "部分成熟" : "已成熟";
  return `${label} ${statusText} ${backtestStatsText(stats)}`;
}

export function strategyCandidateReturnText(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "待成熟" : formatBacktestSignedPercent(value);
}

export function buildStrategyMaturityCandidates(
  payload: LivermoreCandidateHistoryPayload | null,
  row: StrategyPriorityRow | null,
  snapshots: StrategyTrackedSnapshot[],
): StrategyMaturityCandidate[] {
  if (!payload || !row || snapshots.length === 0) return [];
  const visibleSnapshotDates = new Set(snapshots.map((snapshot) => snapshot.snapshot_as_of_date));
  const maxRank = row.diagnostics?.priority_scope === "rank<=10" ? 10 : null;
  return payload.items
    .filter((item) => visibleSnapshotDates.has(item.snapshot_as_of_date))
    .filter((item) => (item.signal_kind ?? "stock_candidate") === row.signal_kind)
    .filter((item) => maxRank == null || item.candidate_rank <= maxRank)
    .sort((left, right) => {
      const dateOrder = right.snapshot_as_of_date.localeCompare(left.snapshot_as_of_date);
      if (dateOrder !== 0) return dateOrder;
      return left.candidate_rank - right.candidate_rank;
    });
}
