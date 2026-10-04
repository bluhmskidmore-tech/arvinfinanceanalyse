// Payload-level helpers used by more than one stockAnalysisPageModel.* domain file.
// Every export here except isActionableLivermoreUnsupportedOutput was a private helper of the
// original stockAnalysisPageModel.ts; the barrel only re-exports isActionableLivermoreUnsupportedOutput.
import type { LivermoreStrategyPayload, LivermoreWalkForwardVerdict } from "../../../api/contracts";
import type { StockStrategyLensVerdict } from "./stockAnalysisPageModel.types";

export function finiteNumber(value: number | null | undefined): number | null {
  return value == null || !Number.isFinite(value) ? null : value;
}

export function normalizeEvidence(evidence: string[] | string | null | undefined): string[] {
  if (Array.isArray(evidence)) {
    return evidence.filter((item) => item.trim().length > 0);
  }
  if (typeof evidence === "string" && evidence.trim()) {
    return [evidence.trim()];
  }
  return [];
}

type StockModuleState = {
  key: LivermoreStrategyPayload["supported_outputs"][number];
  render_mode?: string | null;
  excludes_from_primary?: boolean | null;
  reasons?: readonly string[] | null;
};

type LivermoreStrategyPayloadWithModuleStates = LivermoreStrategyPayload & {
  module_states?: readonly StockModuleState[] | null;
};

export function stockModuleStates(
  payload: LivermoreStrategyPayload | null | undefined,
): readonly StockModuleState[] {
  return ((payload as LivermoreStrategyPayloadWithModuleStates | null | undefined)?.module_states ?? []);
}

export function isActionableLivermoreUnsupportedOutput(
  output: LivermoreStrategyPayload["unsupported_outputs"][number],
): boolean {
  return !isKnownLivermorePolicyPause(output.reason);
}

export function activeDataGaps(payload: LivermoreStrategyPayload) {
  return payload.data_gaps.filter((gap) => gap.status !== "ready");
}

export function actionableDiagnostics(payload: LivermoreStrategyPayload) {
  return payload.diagnostics.filter((item) => item.severity !== "info");
}

export function actionableUnsupportedOutputs(payload: LivermoreStrategyPayload) {
  return payload.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput);
}

function isKnownLivermorePolicyPause(reason: string | null | undefined): boolean {
  const lower = (reason ?? "").trim().toLowerCase();
  return (
    (lower.includes("stock candidate policy") && lower.includes("inactive in overheat")) ||
    lower.includes("mean reversion watchlist is paused") ||
    (lower.includes("theme breakout execution is paused") && lower.includes("overheat")) ||
    (lower.includes("hybrid fusion is observation-only") && lower.includes("warm/hot")) ||
    (lower.includes("uptrend momentum watchlist is paused") && lower.includes("warm or hot"))
  );
}

const WALK_FORWARD_FALLBACK_LABELS: Record<StockStrategyLensVerdict["key"], string> = {
  supported: "样本外支持",
  weakened: "样本外削弱",
  not_assessable: "样本外未检验",
};

export function strategyWalkForwardBadge(
  walkForward: LivermoreWalkForwardVerdict | null | undefined,
): StockStrategyLensVerdict | null {
  if (!walkForward) return null;
  const key: StockStrategyLensVerdict["key"] =
    walkForward.verdict === "supported" || walkForward.verdict === "weakened"
      ? walkForward.verdict
      : "not_assessable";
  const reason = (walkForward.reason || "").trim();
  const judgedAt = (walkForward.judged_at || "").trim();
  return {
    key,
    label: walkForward.verdict_label || WALK_FORWARD_FALLBACK_LABELS[key],
    detail: judgedAt ? `${reason}（${judgedAt} walk-forward 复验）` : reason,
  };
}

export function sectorHeavyweightSourceLabel(source: string) {
  const labels: Record<string, string> = {
    theme_breakout: "题材强势",
    livermore: "趋势候选",
    fresh_trend_watchlist: "新趋势观察",
    factor_screen: "多因子",
    hybrid_fusion: "融合策略",
    mean_reversion: "超跌反弹",
    review_queue: "复核队列",
    sector_constituent: "板块成分",
  };
  return labels[source] ?? "来源待确认";
}
