import type {
  FactorScreenCandidatesPayload,
  LivermoreModuleState,
  LivermoreStrategyPayload,
} from "../../../api/contracts";
import {
  localizeImplementationStage,
  localizeStockBackendText,
} from "./stockAnalysisPageModel";
import type { StockClosedLoopSummary, StockDecisionReferenceRatingCode } from "./stockAnalysisPageModel";
import { EM_DASH } from "../../../utils/format";

export type StockFirstScreenTone = "positive" | "neutral" | "warning" | "negative";

export type StockFirstScreenDecisionStatus =
  | "unresolved"
  | "pretrade_unavailable"
  | "workbench_blocked"
  | StockDecisionReferenceRatingCode
  | "no_valid_candidate";

export type StockFirstScreenDecisionGate = {
  status: StockFirstScreenDecisionStatus;
  statusLabel: string;
  reviewAllowed: boolean;
  candidateProgressionAllowed: boolean;
  executionAllowed: false;
  effectiveCandidateCount: number | null;
  primaryReason: string;
};

export type StockMacroCycleLayerRow = {
  key: string;
  label: string;
  weightLabel: string;
  statusLabel: string;
  tone: StockFirstScreenTone;
  evidence: string;
};

export type StockMacroCycleInputRow = {
  key: "pmi" | "credit_impulse";
  label: string;
  valueLabel: string;
  seriesLabel: string;
  dateLabel: string;
  freshnessLabel: string;
  basisLabel: string;
  tone: StockFirstScreenTone;
};

export type StockMacroCycleCardModel = {
  statusLabel: string;
  tone: StockFirstScreenTone;
  macroScoreLabel: string;
  cycleStateLabel: string;
  evidence: string;
  inputs: StockMacroCycleInputRow[];
  layers: StockMacroCycleLayerRow[];
};

export type StockFactorScreenCardModel = {
  candidateCount: number;
  countLabel: string;
  asOfLabel: string;
  degraded: boolean;
  degradedTitle: string | null;
  observationOnly: boolean;
  coverageLabel: string | null;
};

export function buildStockFirstScreenDecisionGate({
  pretradeQualificationStatus,
  pretradeQualificationReason,
  workbenchReviewAllowed,
  strategyAsOf,
  confluenceAsOf,
  confluenceLoading,
  confluenceError,
  confluenceFreshnessIssue,
  workbenchBlockerReason,
  closedLoopSummary,
  entryObservationCount,
}: {
  pretradeQualificationStatus: "ready" | "ready_empty" | "unavailable" | null;
  pretradeQualificationReason: string | null;
  workbenchReviewAllowed: boolean;
  strategyAsOf: string | null;
  confluenceAsOf: string | null;
  confluenceLoading: boolean;
  confluenceError: boolean;
  confluenceFreshnessIssue: string | null;
  workbenchBlockerReason: string | null;
  closedLoopSummary: StockClosedLoopSummary | null;
  entryObservationCount: number;
}): StockFirstScreenDecisionGate {
  const unresolvedGate = (primaryReason: string): StockFirstScreenDecisionGate =>
    ({
      status: "unresolved",
      statusLabel: "待确认",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: null,
      primaryReason,
    });

  if (pretradeQualificationStatus !== "ready") {
    if (pretradeQualificationStatus === "ready_empty") {
      return {
        status: "no_valid_candidate",
        statusLabel: "资格就绪，无候选",
        reviewAllowed: false,
        candidateProgressionAllowed: false,
        executionAllowed: false,
        effectiveCandidateCount: 0,
        primaryReason: "盘前来源资格已闭合，但本次没有可进入复核的候选",
      };
    }
    return {
      status: "pretrade_unavailable",
      statusLabel: "来源资格未就绪",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: pretradeQualificationReason ?? "盘前来源资格证据未闭合",
    };
  }

  if (confluenceError) {
    return unresolvedGate("信号闭环读取失败");
  }
  if (confluenceLoading || !confluenceAsOf || !closedLoopSummary) {
    return unresolvedGate("结论核对中");
  }
  if (strategyAsOf !== confluenceAsOf) {
    return unresolvedGate(
      `闭环日期不一致（策略 ${strategyAsOf ?? "待确认"} / 闭环 ${confluenceAsOf}）`,
    );
  }
  if (confluenceFreshnessIssue) {
    return {
      status: "insufficient_data",
      statusLabel: "数据不足",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: confluenceFreshnessIssue,
    };
  }

  const resolvedClosedLoopSummary = closedLoopSummary;
  const rating = resolvedClosedLoopSummary.referenceRating;
  if (rating.code !== "reviewable") {
    return {
      status: rating.code,
      statusLabel: rating.label,
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: resolvedClosedLoopSummary.verdict.primaryReason,
    };
  }

  if (!workbenchReviewAllowed) {
    return {
      status: "workbench_blocked",
      statusLabel: "复核门禁未放行",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: workbenchBlockerReason ?? "工作台复核门禁未放行",
    };
  }

  if (entryObservationCount === 0) {
    return {
      status: "no_valid_candidate",
      statusLabel: "无有效候选",
      reviewAllowed: false,
      candidateProgressionAllowed: false,
      executionAllowed: false,
      effectiveCandidateCount: 0,
      primaryReason: "闭环检查已通过，但没有逐项有效的入场观察候选",
    };
  }

  return {
    status: "reviewable",
    statusLabel: "可复核",
    reviewAllowed: true,
    candidateProgressionAllowed: true,
    executionAllowed: false,
    effectiveCandidateCount: entryObservationCount,
    primaryReason: resolvedClosedLoopSummary.verdict.primaryReason,
  };
}

function cycleStateLabel(state: string | null | undefined): string {
  const normalized = (state ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    expansion: "扩张",
    neutral: "中性",
    contraction: "收缩",
    recession: "衰退",
  };
  return labels[normalized] ?? "待确认";
}

function macroLayerTone(status: string): StockFirstScreenTone {
  const normalized = status.trim().toLowerCase();
  if (normalized === "ready" || normalized === "landed") return "positive";
  if (normalized === "missing_inputs" || normalized === "no_data") return "negative";
  return "warning";
}

function macroInputFreshness(
  tier: string | null | undefined,
  ageDays: number | null | undefined,
): Pick<StockMacroCycleInputRow, "freshnessLabel" | "tone"> {
  const normalized = tier?.trim().toLowerCase();
  const ageLabel = typeof ageDays === "number" && Number.isFinite(ageDays) ? ` · ${ageDays} 天` : "";
  if (normalized === "fresh") return { freshnessLabel: `新鲜${ageLabel}`, tone: "positive" };
  if (normalized === "stale") return { freshnessLabel: `陈旧${ageLabel}`, tone: "warning" };
  if (normalized === "expired") return { freshnessLabel: `已过期${ageLabel}`, tone: "negative" };
  if (normalized) return { freshnessLabel: `待确认${ageLabel}`, tone: "warning" };
  return { freshnessLabel: "新鲜度待补", tone: "warning" };
}

function buildMacroInputRow(
  macroContext: LivermoreStrategyPayload["market_gate"]["macro_context"],
  key: StockMacroCycleInputRow["key"],
): StockMacroCycleInputRow {
  const component = macroContext?.components?.find(
    (item) => item.input_family.trim().toLowerCase() === key,
  );
  const freshness = macroInputFreshness(component?.tier, component?.age_days);
  const seriesLabel = component?.input?.trim() || "序列待补";
  const isM2Proxy = key === "credit_impulse" && seriesLabel.toUpperCase() === "M0001385";
  const valueNumeric =
    typeof component?.value_numeric === "number" && Number.isFinite(component.value_numeric)
      ? component.value_numeric
      : null;
  const rawUnit = component?.unit?.trim() || null;
  const unit = rawUnit?.toLowerCase() || null;
  const valueKind = component?.value_kind?.trim().toLowerCase() || null;
  const valueLabel =
    valueNumeric == null
      ? "数值待补"
      : valueKind === "ppt" || unit === "ppt"
        ? `${valueNumeric >= 0 ? "+" : ""}${valueNumeric.toFixed(2)} ppt`
        : valueKind === "index" || unit === "index"
          ? `${valueNumeric.toFixed(1)} index`
          : unit
            ? `${valueNumeric.toFixed(2)} ${rawUnit}`
            : `${valueNumeric.toFixed(2)}`;
  return {
    key,
    label: key === "pmi" ? "PMI" : "信用扩张代理",
    valueLabel,
    seriesLabel,
    dateLabel: component?.business_date?.trim() || "日期待补",
    freshnessLabel: freshness.freshnessLabel,
    basisLabel:
      key === "pmi"
        ? component
          ? "PMI 原序列"
          : "口径待补"
        : !component
          ? "代理口径待补"
          : isM2Proxy
          ? "M2 同比月差代理"
            : "社融存量同比月差代理",
    tone: component ? freshness.tone : "warning",
  };
}

export function buildStockMacroCycleCard(
  payload: LivermoreStrategyPayload,
): StockMacroCycleCardModel | null {
  const macroContext = payload.market_gate.macro_context;
  const framework = payload.cycle_rotation_framework;
  const macroLayer = framework?.macro_layer;
  if (!macroContext && !macroLayer) {
    return null;
  }

  const macroScore = macroContext?.macro_score ?? macroLayer?.macro_score ?? null;
  const layers: StockMacroCycleLayerRow[] = (framework?.layers ?? []).map((layer) => ({
    key: layer.key,
    label: cycleLayerLabel(layer.key, layer.title),
    weightLabel:
      typeof layer.weight === "number" && Number.isFinite(layer.weight)
        ? `${Math.round(layer.weight * 100)}%`
        : EM_DASH,
    statusLabel: localizeImplementationStage(layer.status),
    tone: macroLayerTone(layer.status),
    evidence: localizeStockBackendText(layer.evidence ?? "", layer.key),
  }));
  const inputs: StockMacroCycleInputRow[] = [
    buildMacroInputRow(macroContext, "pmi"),
    buildMacroInputRow(macroContext, "credit_impulse"),
  ];
  const requiredInputsFresh = inputs.every(
    (item) => item.seriesLabel !== "序列待补" && item.tone === "positive",
  );
  const ready =
    String(macroContext?.status ?? "").toLowerCase() === "ready" && requiredInputsFresh;

  return {
    statusLabel: ready ? "已落地" : "部分就绪",
    tone: ready ? "positive" : "warning",
    macroScoreLabel:
      macroScore != null && Number.isFinite(macroScore) ? macroScore.toFixed(2) : EM_DASH,
    cycleStateLabel: cycleStateLabel(macroContext?.cycle_state),
    evidence: localizeStockBackendText(
      macroContext?.evidence ?? macroLayer?.evidence ?? "宏观层证据待补",
      "macro_score",
    ),
    inputs,
    layers,
  };
}

function cycleLayerLabel(key: string, title: string): string {
  const labels: Record<string, string> = {
    macro_direction: "宏观方向",
    industry_cycle: "行业周期",
    market_flow: "市场资金",
    valuation_support: "估值支撑",
    execution_constraints: "执行约束",
  };
  return labels[key] ?? localizeStockBackendText(title, key);
}

export function buildStockFactorScreenCard(
  payload: FactorScreenCandidatesPayload | null | undefined,
  moduleState: LivermoreModuleState | null | undefined,
): StockFactorScreenCardModel | null {
  if (!payload) {
    return null;
  }
  const degraded = moduleState?.state === "degraded";
  const degradedReasons = (moduleState?.reasons ?? [])
    .map((reason) => localizeStockBackendText(reason, "factor_screen_candidates"))
    .filter((reason) => reason.trim().length > 0);
  const lagTitle =
    moduleState?.lag_days != null && moduleState?.threshold_days != null
      ? `因子截面滞后 ${moduleState.lag_days} 天，阈值 ${moduleState.threshold_days} 天`
      : null;
  return {
    candidateCount: payload.candidate_count ?? payload.items.length,
    countLabel: `${payload.candidate_count ?? payload.items.length} 只`,
    asOfLabel: payload.factor_snapshot_as_of_date ?? payload.as_of_date,
    degraded,
    degradedTitle: degraded ? [lagTitle, ...degradedReasons].filter(Boolean).join("；") || null : null,
    observationOnly: payload.observation_only !== false,
    coverageLabel: payload.coverage_note
      ? localizeStockBackendText(payload.coverage_note, "factor_screen_candidates")
      : null,
  };
}
