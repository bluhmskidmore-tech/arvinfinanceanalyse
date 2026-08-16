import type {
  FactorScreenCandidatesPayload,
  LivermoreDataGap,
  LivermoreMarketGate,
  LivermoreModuleState,
  LivermoreStrategyPayload,
} from "../../../api/contracts";
import { cycleInputLabel, dataGapFamilyLabel } from "./stockAnalysisPageLabels";
import { stockStatusLabel } from "./stockAnalysisPageCopy";
import {
  localizeImplementationStage,
  localizeMarketDataStatus,
  localizeStockBackendText,
} from "./stockAnalysisPageModel";
import { EM_DASH } from "../../../utils/format";

export type StockFirstScreenTone = "positive" | "neutral" | "warning" | "negative";

export type StockFirstScreenKpi = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail?: string;
  tone: StockFirstScreenTone;
};

export type StockFirstScreenHeroModel = {
  headline: string;
  lead: string;
  kpis: StockFirstScreenKpi[];
};

export type StockActiveDataGap = LivermoreDataGap & {
  blocksReview: boolean;
  familyLabel: string;
  shortLabel: string;
  statusLabel: string;
};

export type StockDataGapOverview = {
  activeGaps: StockActiveDataGap[];
  blockingGaps: StockActiveDataGap[];
  missingCount: number;
  partialCount: number;
  countLabel: string;
  primaryGapLabel: string;
  maxStaleAgeDays: number | null;
  maxStaleAgeFamilyLabel: string | null;
};

export type StockMacroCycleLayerRow = {
  key: string;
  label: string;
  weightLabel: string;
  statusLabel: string;
  tone: StockFirstScreenTone;
  evidence: string;
};

export type StockMacroCycleCardModel = {
  statusLabel: string;
  tone: StockFirstScreenTone;
  macroScoreLabel: string;
  cycleStateLabel: string;
  evidence: string;
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

const REQUIRED_WORKBENCH_GAP_FAMILIES = new Set([
  "broad_index_history",
  "breadth",
  "limit_up_quality",
  "sector_strength",
  "stock_universe",
  "position_risk",
]);

type WorkbenchGapInput = LivermoreDataGap & { blocks_review?: boolean };

function gapBlocksReview(gap: WorkbenchGapInput): boolean {
  if (typeof gap.blocks_review === "boolean") {
    return gap.blocks_review;
  }
  return (
    (REQUIRED_WORKBENCH_GAP_FAMILIES.has(gap.input_family) && gap.status !== "ready") ||
    gap.tier === "stale" ||
    gap.tier === "expired" ||
    ["stale", "look_ahead", "blocked", "error", "unsupported"].includes(
      String(gap.status).trim().toLowerCase(),
    ) ||
    (typeof gap.age_days === "number" && gap.age_days < 0)
  );
}

function gapDisplayStatus(gap: WorkbenchGapInput): string {
  return gap.tier === "stale" || gap.tier === "expired" ? "stale" : String(gap.status);
}

/**
 * 缺口行标签：登记过的输入族用中文名；未登记时改用后端数据源字段
 * (gap.input，如系列号/表名)作证据引用，避免多行同文"输入待确认"不可分辨。
 * 未登记且无数据源字段时保持"输入待确认"——原始 input_family(如
 * external_vendor_* 技术 token)不得直出业务叙述位(§7)。
 */
function gapShortLabel(gap: WorkbenchGapInput): string {
  const label = cycleInputLabel(gap.input_family);
  if (label !== "输入待确认") return label;
  return gap.input?.trim() || label;
}

export function buildStockDataGapOverview(gaps: WorkbenchGapInput[]): StockDataGapOverview {
  const activeRaw = gaps.filter(
    (gap) => gap.status !== "ready" || gap.tier === "stale" || gap.tier === "expired",
  );
  const decorated = activeRaw.map((gap) => ({
    ...gap,
    blocksReview: gapBlocksReview(gap),
    familyLabel: dataGapFamilyLabel(gap.input_family),
    shortLabel: gapShortLabel(gap),
    statusLabel: stockStatusLabel(gapDisplayStatus(gap)),
  }));
  const ordered = [...decorated].sort(
    (left, right) =>
      Number(right.blocksReview) - Number(left.blocksReview) ||
      decorated.indexOf(left) - decorated.indexOf(right),
  );
  const blockingGaps = ordered.filter((gap) => gap.blocksReview);
  const missingCount = decorated.filter((gap) =>
    ["missing", "blocked", "error", "unsupported"].includes(String(gap.status)),
  ).length;
  const partialCount = decorated.filter(
    (gap) =>
      ["partial", "stale", "warning", "degraded", "deferred"].includes(String(gap.status)) ||
      gap.tier === "stale" ||
      gap.tier === "expired",
  ).length;
  const countLabel =
    missingCount > 0 && partialCount > 0
      ? `${missingCount}+${partialCount}`
      : `${decorated.length}`;
  const primaryGapLabel =
    ordered
      .slice(0, 3)
      .map((gap) => gap.shortLabel)
      .join(" / ") || "无新增缺口";

  let maxStaleAgeDays: number | null = null;
  let maxStaleAgeFamilyLabel: string | null = null;
  for (const gap of gaps) {
    const isStale = gap.tier === "stale" || gap.tier === "expired" || gap.status === "stale";
    if (!isStale) continue;
    if (typeof gap.age_days !== "number" || !Number.isFinite(gap.age_days) || gap.age_days <= 0) {
      continue;
    }
    if (maxStaleAgeDays == null || gap.age_days > maxStaleAgeDays) {
      maxStaleAgeDays = gap.age_days;
      maxStaleAgeFamilyLabel = cycleInputLabel(gap.input_family);
    }
  }

  return {
    activeGaps: ordered,
    blockingGaps,
    missingCount,
    partialCount,
    countLabel,
    primaryGapLabel,
    maxStaleAgeDays,
    maxStaleAgeFamilyLabel,
  };
}

export function buildStockFirstScreenHero({
  marketGate,
  reviewBlocked,
  reviewQueueCount,
  primaryBlockerLabel,
  factorScreen,
  gapOverview,
}: {
  marketGate: LivermoreMarketGate;
  reviewBlocked: boolean;
  reviewQueueCount: number;
  primaryBlockerLabel: string | null;
  factorScreen: StockFactorScreenCardModel | null;
  gapOverview: StockDataGapOverview;
}): StockFirstScreenHeroModel {
  const availability = `${marketGate.available_conditions}/${marketGate.required_conditions}`;
  const stateLabel = localizeMarketDataStatus(marketGate.state);
  const lagClause =
    gapOverview.maxStaleAgeDays != null ? `，源数据滞后 ${gapOverview.maxStaleAgeDays} 天` : "";

  let headline: string;
  let lead: string;
  if (reviewBlocked) {
    headline = `复核门禁未放行：${marketGate.required_conditions} 项条件仅 ${marketGate.available_conditions} 项可评估${lagClause}`;
    const factorClause =
      factorScreen && factorScreen.candidateCount > 0
        ? `因子初筛 ${factorScreen.candidateCount} 只候选可先行只读观察，截面 ${factorScreen.asOfLabel}。`
        : "观察池暂无可先行浏览的候选。";
    lead = `首要阻断：${primaryBlockerLabel ?? "阻断原因待确认"}。${factorClause}`;
  } else if (reviewQueueCount > 0) {
    headline = `复核可以继续：门禁${stateLabel}，待复核候选 ${reviewQueueCount} 只`;
    lead =
      gapOverview.blockingGaps.length > 0
        ? `仍有 ${gapOverview.blockingGaps.length} 项阻断缺口待补，复核结论仅供观察。`
        : "候选与证据已返回，可按队列顺序只读复核。";
  } else {
    headline = `暂无复核候选：门禁${stateLabel}，等待观察池补充证据`;
    lead =
      factorScreen && factorScreen.candidateCount > 0
        ? `因子初筛 ${factorScreen.candidateCount} 只候选可先行只读观察，截面 ${factorScreen.asOfLabel}。`
        : "各策略观察池均无输出，请关注数据缺口修复进度。";
  }

  const kpis: StockFirstScreenKpi[] = [
    {
      key: "gate-availability",
      label: "可评估条件",
      value: availability,
      detail: `通过 ${marketGate.passed_conditions}/${marketGate.required_conditions}`,
      tone:
        marketGate.available_conditions >= marketGate.required_conditions
          ? marketGate.passed_conditions >= marketGate.required_conditions
            ? "positive"
            : "neutral"
          : "warning",
    },
    {
      key: "factor-candidates",
      label: "因子初筛候选",
      value: factorScreen ? `${factorScreen.candidateCount}` : EM_DASH,
      unit: factorScreen ? "只" : undefined,
      detail: factorScreen ? `截面 ${factorScreen.asOfLabel}` : "接口未提供",
      tone: factorScreen && factorScreen.candidateCount > 0 ? "neutral" : "warning",
    },
    {
      key: "blocking-gaps",
      label: "阻断缺口",
      value: `${gapOverview.blockingGaps.length}`,
      unit: "项",
      detail: gapOverview.primaryGapLabel,
      tone: gapOverview.blockingGaps.length > 0 ? "negative" : "positive",
    },
    {
      key: "source-lag",
      label: "源数据滞后",
      value: gapOverview.maxStaleAgeDays != null ? `${gapOverview.maxStaleAgeDays}` : EM_DASH,
      unit: gapOverview.maxStaleAgeDays != null ? "天" : undefined,
      detail: gapOverview.maxStaleAgeFamilyLabel ?? "无陈旧输入",
      tone: gapOverview.maxStaleAgeDays != null ? "warning" : "positive",
    },
  ];

  return { headline, lead, kpis };
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
  const ready =
    macroLayer?.ready === true || String(macroContext?.status ?? "").toLowerCase() === "ready";

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
