/**
 * /macro-observation 页面视图模型层：纯函数 + 类型，不引入 React/antd。
 *
 * - 只做映射与展示格式化，不做任何正式金融计算；数值展示统一走
 *   `pageModel` 原语（`LabeledValue` / `EM_DASH` / `fixedOrDash` / `textOrDash`）。
 * - `pickPrimarySignal` / `buildStrategyCounts` / `strategySupplyState` /
 *   `observationRuntimeSummary` 自 `MacroToolkitPage`（mode="observation"）现有
 *   编排逐字迁移，判定式与文案不得漂移；角色 5 完成路由切换前旧页继续原样运行。
 * - 共享判定与锁定文案一律 import `features/macro-toolkit/lib/`（跨 feature 复用
 *   同族 lib 是本次重构既定决策），禁止复制实现。
 * - detail=core 首发时 capability_results 为空数组、a_share_risk 为 null，这是
 *   「延后确认」诚实态而非业务缺失：相应视图给 `deferred` 状态 + 说明 note，
 *   不得渲染成普通空值。
 */
import type { ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitAShareRiskPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitDataHealth,
  MacroToolkitReportBundle,
  MacroToolkitSignalCard,
  MacroToolkitStrategySummariesPayload,
  MacroToolkitStrategySummary,
} from "../../../api/macroToolkitClient";
import {
  EM_DASH,
  fixedOrDash,
  textOrDash,
  type LabeledValue,
  type MetricTone,
} from "../../../pageModel";
import { crisisScoreHistoryFromResult, isCrisisComponent, isRecord } from "../../macro-toolkit/lib/macroToolkitCrisisSupport";
import {
  capabilityHealthDetail,
  compareRepairPriority,
  coverageValue,
  formatDataHealthRepairAction,
  formatDataHealthRepairLabel,
  formatObservationDeferredSectionLabel,
  localizeRepairActionText,
  repairPriorityLabel,
  repairTypeLabel,
} from "../../macro-toolkit/lib/macroToolkitDataHealthSupport";
import {
  formatAnalysisBasisLabel,
  formatObservationEvidence,
  formatObservationRecommendation,
  formatObservationSignalTitle,
  formatQualityFlagLabel,
  formatSize,
  isObservationOutputSignal,
  pickPrimarySignal,
  riskLevelTone,
} from "../../macro-toolkit/lib/macroToolkitDisplayFormat";
import { statusLabel } from "../../macro-toolkit/lib/macroToolkitPanelShared";
import {
  dualFrequencyStatus,
  dualFrequencyStatusText,
  hasCompleteRealStrategyChain,
  hasRealStrategySource,
  shadowPortfolioObservationText,
} from "../../macro-toolkit/lib/macroToolkitStrategyDisplaySupport";

// ---------------------------------------------------------------------------
// 共享常量与 tone 映射
// ---------------------------------------------------------------------------

/** core 首发延后加载数据的统一说明 note（deferred ≠ 业务缺失）。 */
export const MACRO_OBSERVATION_DEFERRED_NOTE = "完整分析后确认";
export const MACRO_OBSERVATION_A_SHARE_EMPTY_NOTE = "暂无A股风险证据";
export const MACRO_OBSERVATION_CRISIS_EMPTY_NOTE = "暂无危机分证据";
export const MACRO_OBSERVATION_CRISIS_COVERAGE_FALLBACK_NOTE = "组件覆盖按返回数组回退";

function uniqueWarningTexts(warnings: readonly string[] | null | undefined): string[] {
  const seen = new Set<string>();
  const texts: string[] = [];
  for (const raw of warnings ?? []) {
    const text = raw.trim();
    if (!text || seen.has(text)) {
      continue;
    }
    seen.add(text);
    texts.push(text);
  }
  return texts;
}

function finiteCount(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

const SIGNAL_TONE_TO_METRIC_TONE: Record<MacroToolkitSignalCard["tone"], MetricTone> = {
  positive: "positive",
  neutral: "neutral",
  negative: "negative",
  missing: "neutral",
};

/** 后端 signal tone（含 "missing"）→ 页面 MetricTone；缺失一律 neutral。 */
export function signalToneToMetricTone(
  tone: MacroToolkitSignalCard["tone"] | null | undefined,
): MetricTone {
  return tone ? SIGNAL_TONE_TO_METRIC_TONE[tone] : "neutral";
}

/**
 * A股风险等级 → MetricTone。与共享 riskLevelTone 的差异仅一处：
 * yellow 在本页 KPI/风险块按「警戒」着琥珀（warning），共享函数为 neutral；
 * 其余等级沿用共享判定（green→positive、unknown→missing→neutral、红档→negative）。
 */
export function aShareRiskMetricTone(
  level: MacroToolkitAShareRiskPayload["risk_level"],
): MetricTone {
  if (level === "yellow") {
    return "warning";
  }
  return signalToneToMetricTone(riskLevelTone(level));
}

/** 模型就绪 degraded_reason 后端 token → 中文；未知 token 原样兜底，空值 EM_DASH。 */
const MODEL_DEGRADED_REASON_TEXT: Record<string, string> = {
  script_unavailable: "脚本不可用",
  missing_expected_outputs: "预期产物缺失",
  stale_expected_outputs: "预期产物陈旧",
  indeterminate_output_dates: "产物日期待判定",
  no_expected_outputs_registered: "未登记预期产物",
  dry_run_not_executed: "干跑未执行",
};

export function modelDegradedReasonText(reason: string | null | undefined): string {
  const normalized = reason?.trim() ?? "";
  if (!normalized) {
    return EM_DASH;
  }
  return MODEL_DEGRADED_REASON_TEXT[normalized] ?? normalized;
}

/** ETF 策略 boundary token → 中文；未知值原样兜底（后端当前固定 observation_only）。 */
const ETF_BOUNDARY_TEXT: Record<string, string> = {
  observation_only: "仅观察，未启用自动执行",
};

export function etfBoundaryText(boundary: string | null | undefined): string {
  const normalized = boundary?.trim() ?? "";
  if (!normalized) {
    return EM_DASH;
  }
  return ETF_BOUNDARY_TEXT[normalized] ?? normalized;
}

/** Hason boundary 后端英文句 → 中文；未知句原样兜底（组件用 title 保留原文）。 */
const HASON_BOUNDARY_TEXT: Record<string, string> = {
  "Analytical macro toolkit display only; not a formal MTR metric, trade order, or portfolio execution engine.":
    "仅分析展示；不构成正式指标、交易指令或组合执行依据。",
};

export function hasonBoundaryText(boundary: string | null | undefined): string {
  const normalized = boundary?.trim() ?? "";
  if (!normalized) {
    return EM_DASH;
  }
  return HASON_BOUNDARY_TEXT[normalized] ?? normalized;
}

// ---------------------------------------------------------------------------
// (a) 自现有编排逐字迁移的判定（MacroToolkitPage.tsx，行为不得漂移）
// ---------------------------------------------------------------------------

/** runtime_status.analysis_scope === "core" 判定（与现页 isCoreAnalysis 一致）。 */
export function isCoreAnalysisScope(analysis: MacroToolkitAnalysisPayload | null | undefined): boolean {
  return analysis?.runtime_status?.analysis_scope === "core";
}

export { pickPrimarySignal };

export type MacroObservationStrategyCounts = {
  /** 全链路真实供数（hasCompleteRealStrategyChain）。 */
  full: number;
  /** 部分真实供数（有真实来源但链路未闭环）。 */
  partial: number;
  /** 有真实来源但 status 非 complete（与 partial 可重叠，口径同现页）。 */
  degraded: number;
  /** 样例展示（status === "sample_only"）。 */
  sample: number;
};

/** 策略供数四计数，判定式与现页 full/partial/degraded/sample 计数逐字一致。 */
export function buildStrategyCounts(
  summaries: MacroToolkitStrategySummary[],
): MacroObservationStrategyCounts {
  return {
    full: summaries.filter((strategy) => hasCompleteRealStrategyChain(strategy)).length,
    partial: summaries.filter(
      (strategy) => hasRealStrategySource(strategy) && !hasCompleteRealStrategyChain(strategy),
    ).length,
    degraded: summaries.filter(
      (strategy) => hasRealStrategySource(strategy) && strategy.status !== "complete",
    ).length,
    sample: summaries.filter((strategy) => strategy.status === "sample_only").length,
  };
}

export type MacroObservationStrategySupplyState = "loading" | "failed" | "loaded";

/** 策略供数三态，与现页 strategySupplyState 判定逐字一致。 */
export function strategySupplyState(
  isFetching: boolean,
  isError: boolean,
  hasLoaded: boolean,
): MacroObservationStrategySupplyState {
  return isFetching && !hasLoaded ? "loading" : isError && !hasLoaded ? "failed" : "loaded";
}

/** 运行时摘要三句，文案与现页 observationRuntimeSummary 逐字一致。 */
export function observationRuntimeSummary(
  isCoreAnalysis: boolean,
  deferredSectionCount: number,
): string {
  return isCoreAnalysis
    ? deferredSectionCount
      ? `${deferredSectionCount} 项证据延后确认`
      : "等待完整分析确认"
    : "证据已完整读取";
}

/** 策略摘要合并顺序与现页一致：strategy-summaries 接口优先，analysis 兜底。 */
export function mergeStrategySummaries(
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined,
  analysis: MacroToolkitAnalysisPayload | undefined,
): MacroToolkitStrategySummary[] {
  return strategyPayload?.strategy_summaries ?? analysis?.strategy_summaries ?? [];
}

/** 与现页一致：capability_results 中按 key 取危机分结果。 */
export function pickCrisisScoreResult(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MacroToolkitCapabilityResult | null {
  return analysis?.capability_results.find((result) => result.key === "crisis_score_cn") ?? null;
}

/** 与现页一致：capability_results 中按 key 取决策摘要结果。 */
export function pickDecisionSummaryResult(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MacroToolkitCapabilityResult | null {
  return analysis?.capability_results.find((result) => result.key === "decision_summary") ?? null;
}

// ---------------------------------------------------------------------------
// 页头工具条
// ---------------------------------------------------------------------------

/**
 * 工具条状态 chips：观察日 / 分析口径（core=首屏读数、full=完整证据）/
 * 来源覆盖（coverageValue，缺 data_health 时「待确认」，同现页
 * dataFreshnessDetail observation 分支语义）/ 证据状态（runtimeSummary 三句）。
 */
export function buildObservationToolbarStatus(
  analysis: MacroToolkitAnalysisPayload | undefined,
  meta: ResultMeta | undefined,
): LabeledValue[] {
  const isCore = isCoreAnalysisScope(analysis);
  const deferredSectionCount = analysis?.runtime_status?.deferred_sections.length ?? 0;
  return [
    {
      key: "as-of-date",
      label: "观察日",
      value: textOrDash(analysis?.as_of_date ?? meta?.as_of_date),
    },
    {
      // core/full 枚举不再作为 note 直出；「首屏读数 / 完整证据」已是口径本身。
      key: "analysis-scope",
      label: "分析口径",
      value: analysis ? (isCore ? "首屏读数" : "完整证据") : EM_DASH,
    },
    {
      key: "source-coverage",
      label: "来源覆盖",
      value: analysis?.data_health ? coverageValue(analysis.data_health.source_coverage) : "待确认",
    },
    {
      key: "runtime-status",
      label: "证据状态",
      value: analysis ? observationRuntimeSummary(isCore, deferredSectionCount) : EM_DASH,
    },
  ];
}

// ---------------------------------------------------------------------------
// 01 当日观察结论：KPI 单框横带 + 结论正文
// ---------------------------------------------------------------------------

/**
 * KPI 格四态：loading（查询未回）/ deferred（core 首发延后，note 说明）/
 * failed（读取失败，仅 analysis 失败与策略供数失败两处显式使用）/ ready。
 */
export type MacroObservationKpiState = "loading" | "deferred" | "ready" | "failed";

/**
 * KPI 格 = LabeledValue 换上四态 status（LabeledValue.status 的 SectionStatus
 * 词表不含 deferred/ready，故仅替换该字段，其余展示字段沿用原语）。
 */
export type MacroObservationKpiItem = Omit<LabeledValue, "status"> & {
  status: MacroObservationKpiState;
};

const MACRO_OBSERVATION_KPI_CELLS = [
  { key: "stance", label: "投研观点" },
  { key: "decision-modules", label: "决策摘要可用模块" },
  { key: "crisis-score", label: "危机分" },
  { key: "a-share-risk", label: "A股风险" },
  { key: "primary-signal", label: "主信号" },
  { key: "strategy-supply", label: "策略供数" },
] as const;

export type MacroObservationKpiBandInput = {
  analysis: MacroToolkitAnalysisPayload | undefined;
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined;
  /** analysis 查询是否仍在读取（无数据时区分 loading / failed）。 */
  analysisLoading: boolean;
  strategySupply: MacroObservationStrategySupplyState;
};

/** 01 区 KPI 单框横带（6 格），缺值一律 EM_DASH，deferred 一律带说明 note。 */
export function buildObservationKpiBand(input: MacroObservationKpiBandInput): MacroObservationKpiItem[] {
  const { analysis, strategyPayload, analysisLoading, strategySupply } = input;
  const [stanceCell, decisionCell, crisisCell, riskCell, signalCell, strategyCell] =
    MACRO_OBSERVATION_KPI_CELLS;

  if (!analysis) {
    const status: MacroObservationKpiState = analysisLoading ? "loading" : "failed";
    return MACRO_OBSERVATION_KPI_CELLS.map((cell) => ({
      key: cell.key,
      label: cell.label,
      value: EM_DASH,
      status,
    }));
  }

  const isCore = isCoreAnalysisScope(analysis);
  const deferredCell = (cell: { key: string; label: string }): MacroObservationKpiItem =>
    isCore
      ? { ...cell, value: EM_DASH, note: MACRO_OBSERVATION_DEFERRED_NOTE, status: "deferred" }
      : { ...cell, value: EM_DASH, status: "ready" };

  // conclusion 在 TS 契约中为必填，但模型对载荷边界保持容错（缺失 → EM_DASH）。
  const conclusion: MacroToolkitAnalysisPayload["conclusion"] | undefined = analysis.conclusion;
  const stanceItem: MacroObservationKpiItem = {
    ...stanceCell,
    value: textOrDash(conclusion?.stance),
    tone: signalToneToMetricTone(conclusion?.tone),
    status: "ready",
  };

  const decisionResult = pickDecisionSummaryResult(analysis);
  let decisionItem: MacroObservationKpiItem;
  if (decisionResult?.primary_metric) {
    decisionItem = {
      ...decisionCell,
      value: `${decisionResult.primary_metric.value}${decisionResult.primary_metric.unit}`,
      note: statusLabel(decisionResult.status),
      status: "ready",
    };
  } else {
    decisionItem = deferredCell(decisionCell);
  }

  const crisisResult = pickCrisisScoreResult(analysis);
  let crisisItem: MacroObservationKpiItem;
  if (crisisResult) {
    const regime = crisisResultRegime(crisisResult);
    crisisItem = {
      ...crisisCell,
      value: fixedOrDash(crisisResultScore(crisisResult), 1),
      ...(regime ? { note: regime } : {}),
      status: "ready",
    };
  } else {
    // core 态 capability_results 为空，但 signal_cards 已带危机分：读数先行，regime 延后。
    const crisisCard = analysis.signal_cards.find((card) => card.key === "crisis_score_cn") ?? null;
    crisisItem = isCore
      ? {
          ...crisisCell,
          value: fixedOrDash(crisisCard?.score, 1),
          note: MACRO_OBSERVATION_DEFERRED_NOTE,
          status: "deferred",
        }
      : { ...crisisCell, value: fixedOrDash(crisisCard?.score, 1), status: "ready" };
  }

  const risk = analysis.a_share_risk ?? null;
  let riskItem: MacroObservationKpiItem;
  if (risk) {
    riskItem = {
      ...riskCell,
      // 与现有观察区一致：risk_score 原样展示，不改精度。
      value: risk.risk_score == null ? EM_DASH : String(risk.risk_score),
      ...(risk.risk_name ? { note: risk.risk_name } : {}),
      tone: aShareRiskMetricTone(risk.risk_level),
      status: "ready",
    };
  } else {
    riskItem = deferredCell(riskCell);
  }

  const primarySignal = pickPrimarySignal(analysis.signal_cards, analysis.primary_signal);
  let signalItem: MacroObservationKpiItem;
  if (primarySignal) {
    signalItem = {
      ...signalCell,
      value: formatObservationSignalTitle(primarySignal),
      ...(primarySignal.stance ? { note: primarySignal.stance } : {}),
      tone: signalToneToMetricTone(primarySignal.tone),
      status: "ready",
    };
  } else if (analysis.primary_signal?.selection_status === "deferred") {
    signalItem = deferredCell(signalCell);
  } else {
    signalItem = { ...signalCell, value: EM_DASH, status: "ready" };
  }

  let strategyItem: MacroObservationKpiItem;
  if (strategySupply === "loading") {
    strategyItem = { ...strategyCell, value: EM_DASH, status: "loading" };
  } else if (strategySupply === "failed") {
    strategyItem = { ...strategyCell, value: EM_DASH, note: "策略摘要读取失败", status: "failed" };
  } else {
    const summaries = mergeStrategySummaries(strategyPayload, analysis);
    if (!summaries.length) {
      strategyItem = {
        ...strategyCell,
        value: EM_DASH,
        note: "暂无策略摘要，完整分析后再确认。",
        status: "deferred",
      };
    } else {
      const counts = buildStrategyCounts(summaries);
      // 主值改短形（KPI 格窄列防折行断词）；部分/降级/样例只在非零时进副行。
      const noteParts = [
        counts.partial ? `部分 ${counts.partial}` : "",
        counts.degraded ? `降级 ${counts.degraded}` : "",
        counts.sample ? `样例 ${counts.sample}` : "",
      ].filter(Boolean);
      strategyItem = {
        ...strategyCell,
        value: `${counts.full}/${summaries.length} 全链路`,
        ...(noteParts.length ? { note: noteParts.join(" / ") } : {}),
        status: "ready",
      };
    }
  }

  return [stanceItem, decisionItem, crisisItem, riskItem, signalItem, strategyItem];
}

export type MacroObservationConclusionView = {
  stance: string;
  tone: MetricTone;
  summary: string;
  /** 复用 formatObservationRecommendation 的锁定归纳文案。 */
  recommendedAction: string;
  /** 分析信封 warnings 原文；来源内稳定去重，不跨来源吞并。 */
  warnings: string[];
};

/** 01 区结论正文视图。 */
export function buildObservationConclusion(
  analysis: MacroToolkitAnalysisPayload | undefined,
): MacroObservationConclusionView {
  const conclusion: MacroToolkitAnalysisPayload["conclusion"] | undefined = analysis?.conclusion;
  return {
    stance: textOrDash(conclusion?.stance),
    tone: signalToneToMetricTone(conclusion?.tone),
    summary: textOrDash(conclusion?.summary),
    recommendedAction: formatObservationRecommendation(conclusion?.recommended_action),
    warnings: uniqueWarningTexts(analysis?.warnings),
  };
}

// ---------------------------------------------------------------------------
// 02 信号与风险对照
// ---------------------------------------------------------------------------

export type MacroObservationSignalCardView = {
  key: string;
  title: string;
  /** 展示名与后端原名不同（如 Crisis Score → 危机分）时携带原名供 title 提示。 */
  rawTitle?: string;
  stance: string;
  scoreText: string;
  evidenceText: string;
  tone: MetricTone;
};

/** 危机分卡与 01 KPI 统一中文名「危机分」；后端英文原名收 title（同物双名收敛）。 */
function observationSignalCardTitle(card: MacroToolkitSignalCard): string {
  if (card.key === "crisis_score_cn") {
    return "危机分";
  }
  return formatObservationSignalTitle(card);
}

/** 信号卡视图：outputs 卡剔除，score 一位小数或 EM_DASH，证据走共享归纳。 */
export function buildSignalCardViews(
  cards: MacroToolkitSignalCard[],
): MacroObservationSignalCardView[] {
  return cards
    .filter((card) => !isObservationOutputSignal(card))
    .map((card) => {
      const title = observationSignalCardTitle(card);
      return {
        key: card.key,
        title,
        ...(card.title && card.title !== title ? { rawTitle: card.title } : {}),
        stance: textOrDash(card.stance),
        scoreText: fixedOrDash(card.score, 1),
        evidenceText: formatObservationEvidence(card.evidence),
        tone: signalToneToMetricTone(card.tone),
      };
    });
}

const A_SHARE_RISK_WATCH_NEXT_LIMIT = 3;

export type MacroObservationAShareRiskView =
  | { state: "deferred"; note: string }
  | { state: "empty"; note: string }
  | {
      state: "ready";
      tradeDate: string;
      statusText: string;
      scoreText: string;
      level: MacroToolkitAShareRiskPayload["risk_level"];
      tone: MetricTone;
      name: string;
      summary: string;
      positionRule: string;
      watchNext: string[];
      /** watch_next 超过 3 条时的「另 N 项」提示；未超出为 null。 */
      watchNextMoreNote: string | null;
      triggeredRuleCount: number;
    };

/** A股风险视图：core 态 null → deferred；full 态 null → empty；非 null → 只读明细。 */
export function buildAShareRiskView(
  risk: MacroToolkitAShareRiskPayload | null | undefined,
  analysisScope?: string | null,
): MacroObservationAShareRiskView {
  if (!risk) {
    return analysisScope === "full"
      ? { state: "empty", note: MACRO_OBSERVATION_A_SHARE_EMPTY_NOTE }
      : { state: "deferred", note: MACRO_OBSERVATION_DEFERRED_NOTE };
  }
  const watchNextAll = risk.watch_next.filter((item) => item.trim());
  // 只折叠 1 项收益为负：隐藏数 ≥2 才截断，否则全量展示（无「另」注）。
  const moreCount = Math.max(0, watchNextAll.length - A_SHARE_RISK_WATCH_NEXT_LIMIT);
  const shouldFold = moreCount >= 2;
  return {
    state: "ready",
    tradeDate: textOrDash(risk.trade_date),
    statusText: statusLabel(risk.status),
    scoreText: risk.risk_score == null ? EM_DASH : String(risk.risk_score),
    level: risk.risk_level,
    tone: aShareRiskMetricTone(risk.risk_level),
    name: textOrDash(risk.risk_name),
    summary: textOrDash(risk.summary),
    positionRule: textOrDash(risk.position_rule),
    watchNext: shouldFold ? watchNextAll.slice(0, A_SHARE_RISK_WATCH_NEXT_LIMIT) : watchNextAll,
    watchNextMoreNote: shouldFold ? `另 ${moreCount} 项` : null,
    triggeredRuleCount: risk.triggered_rules.length,
  };
}

// ---------------------------------------------------------------------------
// 04 危机分证据
// ---------------------------------------------------------------------------

function crisisResultScore(result: MacroToolkitCapabilityResult): number | null {
  const raw = result.result.crisis_score;
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  return typeof result.score === "number" && Number.isFinite(result.score) ? result.score : null;
}

function crisisResultRegime(result: MacroToolkitCapabilityResult): string | null {
  const regime = result.result.regime;
  return typeof regime === "string" && regime.trim() ? regime : null;
}

/** ECharts 折线数据点（date/value 两字段，不做插值不做计算）。 */
export type MacroObservationCrisisHistoryPoint = {
  date: string;
  value: number;
};

export type MacroObservationCrisisEvidenceView =
  | { state: "deferred"; note: string }
  | { state: "empty"; note: string }
  | {
      state: "ready";
      headline: string;
      scoreText: string;
      regime: string;
      recommendation: string;
      percentileText: string;
      /** 可计算分项数；权威字段优先。 */
      availableComponentCount: number;
      /** 权重表分项总数；权威字段优先，旧载荷才回退数组长度。 */
      componentCount: number;
      /** z_score 非有限数的已返回组件计数（缺失贡献，不等于覆盖率分子）。 */
      componentMissingCount: number;
      /** 旧载荷没有权威计数时披露回退；权威路径为 null。 */
      coverageNote: string | null;
      history: MacroObservationCrisisHistoryPoint[];
    };

function crisisComponentCoverage(result: MacroToolkitCapabilityResult["result"]): {
  availableComponentCount: number;
  componentCount: number;
  coverageNote: string | null;
  componentMissingCount: number;
} {
  const components = Array.isArray(result.components)
    ? result.components.filter(isCrisisComponent)
    : [];
  const componentMissingCount = components.filter(
    (component) => typeof component.z_score !== "number" || !Number.isFinite(component.z_score),
  ).length;
  const available = finiteCount(result.available_component_count);
  const total = finiteCount(result.component_count);
  if (available !== null && total !== null) {
    return {
      availableComponentCount: available,
      componentCount: total,
      coverageNote: null,
      componentMissingCount,
    };
  }
  return {
    availableComponentCount: components.length - componentMissingCount,
    componentCount: components.length,
    coverageNote: MACRO_OBSERVATION_CRISIS_COVERAGE_FALLBACK_NOTE,
    componentMissingCount,
  };
}

/** 危机分证据视图：core 态无结果 → deferred；full 态无结果 → empty。 */
export function buildCrisisEvidenceView(
  crisisResult: MacroToolkitCapabilityResult | null | undefined,
  analysisScope?: string | null,
): MacroObservationCrisisEvidenceView {
  if (!crisisResult) {
    return analysisScope === "full"
      ? { state: "empty", note: MACRO_OBSERVATION_CRISIS_EMPTY_NOTE }
      : { state: "deferred", note: MACRO_OBSERVATION_DEFERRED_NOTE };
  }
  const result = crisisResult.result;
  const coverage = crisisComponentCoverage(result);
  const percentile =
    typeof result.percentile === "number" && Number.isFinite(result.percentile)
      ? result.percentile
      : null;
  const recommendation =
    typeof result.recommendation === "string" && result.recommendation.trim()
      ? result.recommendation
      : null;
  return {
    state: "ready",
    headline: textOrDash(crisisResult.headline),
    scoreText: fixedOrDash(crisisResultScore(crisisResult), 1),
    regime: textOrDash(crisisResultRegime(crisisResult)),
    recommendation: textOrDash(recommendation),
    percentileText: percentile === null ? EM_DASH : `${percentile.toFixed(2)}%`,
    availableComponentCount: coverage.availableComponentCount,
    componentCount: coverage.componentCount,
    componentMissingCount: coverage.componentMissingCount,
    coverageNote: coverage.coverageNote,
    history: crisisScoreHistoryFromResult(result).map((point) => ({
      date: point.date,
      value: point.crisis_score,
    })),
  };
}

// ---------------------------------------------------------------------------
// 03 模型与策略证据
// ---------------------------------------------------------------------------

export type MacroObservationStrategyRow = {
  key: string;
  label: string;
  statusText: string;
  tone: MetricTone;
  /** 供数链差异信息；全表同句时收敛到 commonChainNote，行级为 null。 */
  chainNote: string | null;
};

export type MacroObservationStrategyDataStatus = {
  status: string;
  statusText: string;
  reason: string | null;
  summaryCount: number | null;
};

export type MacroObservationShadowPortfolioSummary = {
  label: string;
  value: string;
  detail: string;
  tone: MetricTone;
};

export type MacroObservationEtfStrategySummary = {
  boundary: string;
  dualFrequencyStatusText: string;
};

export type MacroObservationStrategyEvidenceView = {
  rows: MacroObservationStrategyRow[];
  counts: MacroObservationStrategyCounts;
  /** 全表来源链同句时收敛区头一次；行间有差异为 null（差异留在行内）。 */
  commonChainNote: string | null;
  shadowPortfolio: MacroObservationShadowPortfolioSummary;
  /** strategy-summaries 载荷缺失或未携带 ETF 快照时为 null。 */
  etfStrategy: MacroObservationEtfStrategySummary | null;
  /** strategy_data_status 透出；载荷未携带或形状不符时为 null。 */
  dataStatus: MacroObservationStrategyDataStatus | null;
};

/**
 * strategy_data_status 宽松读取：后端 /ui/macro/toolkit/analysis 与
 * /analysis/strategy-summaries 均已返回 `{status, reason?, summary_count}`，
 * 但前端 TS 契约（macroToolkitClient.ts）尚未声明该字段；契约补齐前从载荷
 * 宽松读取，形状不符一律回落 null，不虚构业务含义。
 */
export function looseStrategyDataStatus(payload: unknown): MacroObservationStrategyDataStatus | null {
  if (!isRecord(payload)) {
    return null;
  }
  const raw = payload.strategy_data_status;
  if (!isRecord(raw) || typeof raw.status !== "string" || !raw.status.trim()) {
    return null;
  }
  return {
    status: raw.status,
    statusText: statusLabel(raw.status),
    reason: typeof raw.reason === "string" && raw.reason.trim() ? raw.reason : null,
    summaryCount:
      typeof raw.summary_count === "number" && Number.isFinite(raw.summary_count)
        ? raw.summary_count
        : null,
  };
}

/**
 * 供数链行级差异句：不再前缀状态词（状态列已有）、不再挂「仍仅作观察 /
 * 不作为正式投资信号」尾巴（页级只读边界已声明一次，DESIGN §6 去重）。
 */
export function observationStrategyChainNote(strategy: MacroToolkitStrategySummary): string {
  if (hasCompleteRealStrategyChain(strategy)) {
    return "已接入真实行情或因子快照";
  }
  if (hasRealStrategySource(strategy)) {
    return "部分真实供数，缺口需在完整分析中复核";
  }
  return "仅策略可用性检查，未接入真实供数";
}

/** 03 区策略证据视图：摘要行 + 影子组合摘要 + ETF 摘要 + strategy_data_status。 */
export function buildStrategyEvidenceView(
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined,
  analysis: MacroToolkitAnalysisPayload | undefined,
): MacroObservationStrategyEvidenceView {
  const summaries = mergeStrategySummaries(strategyPayload, analysis);
  const shadowReport =
    strategyPayload?.shadow_portfolio_report ?? analysis?.shadow_portfolio_report ?? null;
  const shadowText = shadowPortfolioObservationText(shadowReport);
  const etf = strategyPayload?.macro_etf_strategy ?? null;
  // 同句逐行重复收敛：全表同句时提升为区头一次（行级置 null，列整体不渲染）。
  const chainNotes = summaries.map(observationStrategyChainNote);
  const commonChainNote =
    summaries.length && new Set(chainNotes).size === 1 ? chainNotes[0]! : null;
  return {
    rows: summaries.map((strategy, index) => ({
      key: strategy.key,
      label: strategy.label,
      statusText: statusLabel(strategy.status),
      tone: signalToneToMetricTone(strategy.tone),
      chainNote: commonChainNote ? null : chainNotes[index]!,
    })),
    counts: buildStrategyCounts(summaries),
    commonChainNote,
    shadowPortfolio: {
      label: shadowText.label,
      value: shadowText.value,
      detail: shadowText.detail,
      tone: signalToneToMetricTone(shadowText.tone),
    },
    etfStrategy: etf
      ? {
          boundary: etfBoundaryText(etf.boundary),
          dualFrequencyStatusText: etf.dual_frequency
            ? dualFrequencyStatusText(dualFrequencyStatus(etf.dual_frequency))
            : etf.data_status?.dual_frequency_status
              ? dualFrequencyStatusText(etf.data_status.dual_frequency_status)
              : EM_DASH,
        }
      : null,
    dataStatus: looseStrategyDataStatus(strategyPayload) ?? looseStrategyDataStatus(analysis),
  };
}

// ---------------------------------------------------------------------------
// 05 数据健康与修复项
// ---------------------------------------------------------------------------

const DATA_HEALTH_REPAIR_LIMIT = 5;

export type MacroObservationRepairRow = {
  key: string;
  label: string;
  typeText: string;
  priorityText: string;
  /** 展示层建议动作：英文错误码译中文短语、状态枚举中文化、去句首事项名。 */
  actionText: string;
  /** 后端原句（含原始错误码），供行级 title 溯源；与展示句一致时为 null。 */
  actionTitle: string | null;
  /** 修复项数据最新日期；后端未给时 EM_DASH。 */
  latestDateText: string;
  /** 滞后天数（如「26 天」）；后端未给时 EM_DASH。 */
  staleDaysText: string;
};

export type MacroObservationDataHealthView = {
  /** 指标覆盖 / 来源覆盖 / 能力结果 三组读数。 */
  coverage: LabeledValue[];
  /** 按优先级排序后的前 5 条只读修复项。 */
  repairItems: MacroObservationRepairRow[];
  /** 超出 5 条时的「另 N 项」提示；未超出为 null。 */
  repairMoreNote: string | null;
  /** deferred_sections 的中文标签（core 首发延后确认项）。 */
  deferredSectionLabels: string[];
  /** 数据健康 warnings 原文；来源内稳定去重。 */
  warnings: string[];
};

/** 05 区数据健康视图；data_health 未返回时为 null（交由分区状态兜底）。 */
export function buildDataHealthView(
  dataHealth: MacroToolkitDataHealth | null | undefined,
): MacroObservationDataHealthView | null {
  if (!dataHealth) {
    return null;
  }
  const sortedRepairItems = [...(dataHealth.repair_items ?? [])].sort(compareRepairPriority);
  const visibleRepairItems = sortedRepairItems.slice(0, DATA_HEALTH_REPAIR_LIMIT);
  const moreCount = sortedRepairItems.length - visibleRepairItems.length;
  return {
    coverage: [
      {
        key: "indicator-coverage",
        label: "指标覆盖",
        value: `${dataHealth.indicator_coverage.hit_count}/${dataHealth.indicator_coverage.total_count}`,
        // 部分命中时补命中率百分比（hit_rate 为 0-1，可空）；全命中保持无 note 的干净形态。
        ...(dataHealth.indicator_coverage.missing_count
          ? {
              note:
                dataHealth.indicator_coverage.hit_rate == null
                  ? `缺失 ${dataHealth.indicator_coverage.missing_count} 项`
                  : `命中率 ${(dataHealth.indicator_coverage.hit_rate * 100).toFixed(1)}% · 缺失 ${dataHealth.indicator_coverage.missing_count} 项`,
            }
          : {}),
      },
      {
        key: "source-coverage",
        label: "来源覆盖",
        value: coverageValue(dataHealth.source_coverage),
        ...(dataHealth.source_coverage.latest_date
          ? { date: dataHealth.source_coverage.latest_date }
          : {}),
      },
      {
        key: "capability-results",
        label: "能力结果",
        value: dataHealth.capability_results.deferred
          ? "延后加载"
          : `${dataHealth.capability_results.complete}/${dataHealth.capability_results.total_count}`,
        note: capabilityHealthDetail(dataHealth),
      },
    ],
    repairItems: visibleRepairItems.map((item, index) => {
      const label = formatDataHealthRepairLabel(item, false);
      const rawAction = formatDataHealthRepairAction(item, false);
      // 英文错误码译中文短语 + 去句首重复事项名；原句收行 title（DESIGN §7）。
      const actionText = rawAction
        ? localizeRepairActionText(rawAction, { mapCodes: true, stripLeadingLabel: label })
        : EM_DASH;
      return {
        key: `repair-${index}-${item.alias ?? item.key ?? item.label ?? item.type ?? "item"}`,
        label,
        typeText: repairTypeLabel(item.type),
        priorityText: repairPriorityLabel(item.priority),
        actionText,
        actionTitle: rawAction && rawAction !== actionText ? rawAction : null,
        latestDateText: textOrDash(item.latest_date),
        staleDaysText: item.stale_days == null ? EM_DASH : `${item.stale_days} 天`,
      };
    }),
    repairMoreNote: moreCount > 0 ? `另 ${moreCount} 项` : null,
    deferredSectionLabels: dataHealth.deferred_sections.map((section) =>
      formatObservationDeferredSectionLabel(section),
    ),
    warnings: uniqueWarningTexts(dataHealth.warnings),
  };
}

// ---------------------------------------------------------------------------
// 06 证据与口径
// ---------------------------------------------------------------------------

const TRACE_ID_DISPLAY_LENGTH = 12;

/** trace_id 截断展示（12 位 + 省略号）；空值 EM_DASH。 */
export function truncateTraceId(traceId: string | null | undefined): string {
  const normalized = traceId?.trim() ?? "";
  if (!normalized) {
    return EM_DASH;
  }
  return normalized.length > TRACE_ID_DISPLAY_LENGTH
    ? `${normalized.slice(0, TRACE_ID_DISPLAY_LENGTH)}…`
    : normalized;
}

/** 分析信封 quality_flag 恒为 warning 的口径说明（不能当数据异常信号）。 */
export const MACRO_OBSERVATION_QUALITY_FLAG_NOTE = "分析口径恒 warning，不代表数据异常";

function buildMetaRows(
  meta: ResultMeta,
  keyPrefix: string,
  options?: { qualityNote?: string },
): LabeledValue[] {
  return [
    { key: `${keyPrefix}-basis`, label: "口径", value: formatAnalysisBasisLabel(meta.basis) },
    {
      key: `${keyPrefix}-formal-use`,
      label: "正式使用",
      value: meta.formal_use_allowed ? "允许正式使用" : "仅观察",
    },
    {
      key: `${keyPrefix}-quality`,
      label: "质量标记",
      value: formatQualityFlagLabel(meta.quality_flag),
      ...(options?.qualityNote ? { note: options.qualityNote } : {}),
    },
    {
      key: `${keyPrefix}-tables`,
      label: "事实表",
      value: meta.tables_used?.length ? `${meta.tables_used.length} 张` : EM_DASH,
    },
    { key: `${keyPrefix}-trace`, label: "trace", value: truncateTraceId(meta.trace_id) },
    { key: `${keyPrefix}-generated-at`, label: "生成时间", value: textOrDash(meta.generated_at) },
  ];
}

export type MacroObservationEvidenceMetaView = {
  analysis: LabeledValue[] | null;
  strategy: LabeledValue[] | null;
};

/**
 * 06 证据卡展示前的信封清洗：空 JSON 筛选 `{}` 与字面量 "none" 缓存版本
 * 统一为缺值（共享面板按 EM_DASH 渲染，DESIGN §6 缺值占位）。仅展示层拷贝，
 * 不改动原信封对象。
 */
export function sanitizeEvidenceMetaForDisplay(
  meta: ResultMeta | undefined,
): ResultMeta | undefined {
  if (!meta) {
    return meta;
  }
  const filtersEmpty = !meta.filters_applied || Object.keys(meta.filters_applied).length === 0;
  const cacheVersionNone =
    typeof meta.cache_version === "string" && meta.cache_version.trim().toLowerCase() === "none";
  if (!filtersEmpty && !cacheVersionNone) {
    return meta;
  }
  return {
    ...meta,
    ...(filtersEmpty ? { filters_applied: undefined } : {}),
    // 契约 cache_version 为必填 string；空串在共享面板按 EM_DASH 渲染。
    ...(cacheVersionNone ? { cache_version: "" } : {}),
  };
}

/** 06 区口径面板：分析信封 + 策略信封各一组读数；未返回的信封为 null。 */
export function buildEvidenceMetaView(
  analysisMeta: ResultMeta | undefined,
  strategyMeta: ResultMeta | undefined,
): MacroObservationEvidenceMetaView {
  return {
    analysis: analysisMeta
      ? buildMetaRows(analysisMeta, "analysis", { qualityNote: MACRO_OBSERVATION_QUALITY_FLAG_NOTE })
      : null,
    strategy: strategyMeta ? buildMetaRows(strategyMeta, "strategy") : null,
  };
}

export type MacroObservationReportArtifact = {
  id: string;
  filename: string;
  label: string;
  kind: string;
  /** KB/MB 一位小数（复用 formatSize）。 */
  sizeText: string;
  downloadHref: string;
};

export type MacroObservationReportBundleView = {
  status: MacroToolkitReportBundle["status"];
  statusText: string;
  /** 与现有面板同一放行判定：ready 且 observation_only 且 !formal_use_allowed。 */
  downloadable: boolean;
  reason: string | null;
  /** 材料日；缺失为 EM_DASH，不得用曲线日/账户日回填。 */
  materialDate: string;
  /** 曲线日；缺失为 EM_DASH，不得用材料日回填。 */
  curveDate: string;
  /** 账户报告日；缺失为 EM_DASH，不得用材料日回填。 */
  accountReportDate: string;
  validationText: string;
  /** 校验未通过条数；bundle 未带 validation 时为 0。 */
  validationFailedCount: number;
  validationScope: string;
  /** 报告包 warnings 原文；来源内稳定去重。 */
  warnings: string[];
  artifacts: MacroObservationReportArtifact[];
};

/** 06 区报告包视图；bundle 未返回按 status="missing" 处理（同现有面板）。 */
export function buildReportBundleView(
  bundle: MacroToolkitReportBundle | null | undefined,
): MacroObservationReportBundleView {
  const status = bundle?.status ?? "missing";
  const downloadable =
    status === "ready" && bundle?.observation_only === true && bundle.formal_use_allowed === false;
  const validation = bundle?.validation;
  return {
    status,
    statusText: downloadable
      ? "可下载"
      : status === "invalid"
        ? "资产校验失败，下载已关闭"
        : "报告资产尚未发布",
    downloadable,
    reason: bundle?.reason ?? null,
    materialDate: textOrDash(bundle?.as_of_date),
    curveDate: textOrDash(bundle?.curve_date),
    accountReportDate: textOrDash(bundle?.account_report_date),
    validationText: validation ? `${validation.passed} 通过 / ${validation.failed} 未通过` : EM_DASH,
    validationFailedCount: validation?.failed ?? 0,
    validationScope: textOrDash(validation?.scope),
    warnings: uniqueWarningTexts(bundle?.warnings),
    artifacts: (bundle?.artifacts ?? []).map((artifact) => ({
      id: artifact.id,
      filename: artifact.filename,
      label: artifact.label,
      kind: artifact.kind,
      sizeText: formatSize(artifact.size_bytes),
      downloadHref: `/ui/macro/toolkit/report-bundle/${encodeURIComponent(artifact.id)}`,
    })),
  };
}

// ---------------------------------------------------------------------------
// 分区状态（data-state 语义对齐 /positions：loading/empty/error/deferred 进分区头，
// ready 返回 null 不渲染）
// ---------------------------------------------------------------------------

export type MacroObservationSectionStateKind = "loading" | "empty" | "error" | "deferred";

export type MacroObservationSectionState = {
  state: MacroObservationSectionStateKind;
  note: string;
} | null;

export type MacroObservationSectionStateMap = {
  signalRisk: MacroObservationSectionState;
  modelStrategy: MacroObservationSectionState;
  crisis: MacroObservationSectionState;
  dataHealth: MacroObservationSectionState;
  evidence: MacroObservationSectionState;
};

export type MacroObservationSectionStatesInput = {
  analysis: MacroToolkitAnalysisPayload | undefined;
  analysisLoading: boolean;
  analysisError: boolean;
  analysisMeta: ResultMeta | undefined;
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined;
  strategySupply: MacroObservationStrategySupplyState;
};

/** 各分区五态判定：loading/empty/error/deferred → 带 note；ready → null。 */
export function buildObservationSectionStates(
  input: MacroObservationSectionStatesInput,
): MacroObservationSectionStateMap {
  const { analysis, analysisLoading, analysisError, analysisMeta, strategyPayload, strategySupply } =
    input;
  const isCore = isCoreAnalysisScope(analysis);

  // analysis 未落地时的公共门：错误 > 加载中 > 空。已有数据时错误横幅由编排层处理。
  const analysisGate: MacroObservationSectionState = !analysis
    ? analysisError
      ? { state: "error", note: "读取核心分析失败" }
      : analysisLoading
        ? { state: "loading", note: "观察证据加载中" }
        : { state: "empty", note: "暂无观察证据" }
    : null;

  const signalRisk: MacroObservationSectionState =
    analysisGate ??
    (analysis && !analysis.signal_cards.filter((card) => !isObservationOutputSignal(card)).length
      ? { state: "empty", note: "暂无信号证据" }
      : analysis && isCore && !analysis.a_share_risk
        ? { state: "deferred", note: `A股风险${MACRO_OBSERVATION_DEFERRED_NOTE}` }
        : null);

  const modelStrategy: MacroObservationSectionState =
    strategySupply === "failed"
      ? { state: "error", note: "策略摘要读取失败，当前不能判断策略供数闭环。" }
      : strategySupply === "loading"
        ? { state: "loading", note: "策略摘要正在生成。" }
        : mergeStrategySummaries(strategyPayload, analysis).length
          ? null
          : isCore
            ? { state: "deferred", note: "暂无策略摘要，完整分析后再确认。" }
            : { state: "empty", note: "暂无策略摘要" };

  const crisis: MacroObservationSectionState =
    analysisGate ??
    (pickCrisisScoreResult(analysis)
      ? null
      : isCore
        ? { state: "deferred", note: `危机分证据${MACRO_OBSERVATION_DEFERRED_NOTE}` }
        : { state: "empty", note: "暂无危机分证据" });

  const dataHealth: MacroObservationSectionState =
    analysisGate ??
    (analysis?.data_health ? null : { state: "empty", note: "暂无数据健康证据" });

  const evidence: MacroObservationSectionState = analysisMeta
    ? null
    : analysisError
      ? { state: "error", note: "读取核心分析失败" }
      : analysisLoading
        ? { state: "loading", note: "观察证据加载中" }
        : { state: "empty", note: "暂无口径证据" };

  return { signalRisk, modelStrategy, crisis, dataHealth, evidence };
}
