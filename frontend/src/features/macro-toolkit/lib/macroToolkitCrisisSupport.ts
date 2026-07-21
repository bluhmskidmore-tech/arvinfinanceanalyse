import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitCapabilityResult,
  MacroToolkitCommodityFuturesRefreshRun,
  MacroToolkitDataHealth,
  MacroToolkitInputEvidence,
} from "../../../api/macroToolkitClient";
import { formatPercent } from "./macroToolkitPanelShared";

type MacroToolkitRepairItem = NonNullable<MacroToolkitDataHealth["repair_items"]>[number];

export const MACRO_COMMODITY_SHADOW_RULE_VERSION = "shadow_rule_v1";
export const MACRO_COMMODITY_SHADOW_MIN_SAMPLES = 20;
export const MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES = 5;
export const MACRO_COMMODITY_SHADOW_MIN_CORRELATION = 0.2;
export const MACRO_COMMODITY_SUGGESTED_REFRESH_LOOKBACK_DAYS = 45;
export const MACRO_COMMODITY_PRODUCT_OPTIONS = [
  { value: "RB", label: "螺纹钢", description: "黑色链条" },
  { value: "I", label: "铁矿石", description: "黑色链条" },
  { value: "CU", label: "铜", description: "有色金属" },
  { value: "AL", label: "铝", description: "有色金属" },
  { value: "SC", label: "原油", description: "能源" },
  { value: "AU", label: "黄金", description: "避险资产" },
  { value: "NHCI", label: "南华指数", description: "Crisis Score 输入" },
] as const;
export const MACRO_COMMODITY_FIELD_TO_PRODUCT: Record<string, string> = {
  rebar: "RB",
  iron_ore: "I",
  copper: "CU",
  aluminum: "AL",
  crude_oil: "SC",
  gold: "AU",
};
export const NANHUA_COMMODITY_PRODUCT_CODE = "NHCI";
export const NANHUA_CRISIS_ALIAS = "NH0100.NHF";
export const NANHUA_SYSTEM_SERIES_ID = "NHCI.NH";

const MACRO_SOURCE_BACKFILL_ALIASES = new Set(["M0041813"]);

export type CommodityRefreshProductRow = {
  key: string;
  productCode: string;
  productName: string;
  seriesId: string;
  status: "estimated" | "written" | "missing";
  estimatedRows: number | null;
  rowCount: number | null;
  rowCountLabel: string;
  latestDate: string;
  latestValue: number | null;
  vendor: string;
  table: string;
  isNanhua: boolean;
};

export type CrisisComponent = {
  key: string;
  label: string;
  raw_value: number | null;
  z_score: number | null;
  weight: number | null;
};

export type CrisisCommodityCoverageItem = {
  field: string;
  label: string;
  aliases: string[];
  matched_alias: string | null;
  role: string;
  used_in_formula: boolean;
  available: boolean;
  row_count: number | null;
  latest_date: string | null;
  report_date: string | null;
  date_alignment_status: string | null;
  series_id: string | null;
  source: string | null;
  value: number | null;
  candidate_decision: CrisisCommodityCandidateDecision | null;
  shadow_evaluation: CrisisCommodityShadowEvaluation | null;
};

export type CrisisCommodityCandidateDecision = {
  status: string;
  label: string;
  reason: string;
  next_step: string;
};

export type CrisisCommodityCandidateSummary = {
  shadow_review_ready_count: number;
  needs_current_data_count: number;
  missing_data_count: number;
  shadow_evaluation_ready_count: number;
  shadow_evaluation_short_count: number;
  shadow_evaluation_status_counts: Record<string, number>;
  shadow_evaluation_short_items: CrisisCommodityShadowShortItem[];
  suggested_refresh_products: string[];
  shadow_evaluation_next_step: string;
  formula_change_required: boolean;
  approval_required: boolean;
  next_step: string;
};

export type CrisisCommodityShadowShortItem = {
  field: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  latest_date: string | null;
};

export type CrisisCommodityShadowEvaluation = {
  status: string;
  label: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  sample_gap: number | null;
  window_start: string | null;
  window_end: string | null;
  target: string;
  candidate_metric: string;
  same_day_correlation: number | null;
  lead_1d_correlation: number | null;
  lag_1d_correlation: number | null;
  crisis_hit_rate: number | null;
  crisis_sample_count: number | null;
  summary: string;
  next_step: string;
};

export type CrisisCommodityCoverage = {
  role: string;
  tracked_count: number;
  available_count: number;
  used_in_crisis_score: string[];
  candidate_summary: CrisisCommodityCandidateSummary | null;
  items: CrisisCommodityCoverageItem[];
};

export type CrisisCommodityShadowContribution = {
  field: string;
  label: string;
  series_id: string | null;
  source: string | null;
  latest_date: string | null;
  sample_count: number | null;
  candidate_metric: string;
  candidate_value: number | null;
  weight: number | null;
  contribution: number | null;
  used_in_official_score: boolean;
  status: string;
};

export type CrisisCommodityShadowImpact = {
  formula_version: string;
  scope: string;
  current_score: number | null;
  shadow_score: number | null;
  delta: number | null;
  direction: string;
  included_candidates: string[];
  candidate_count: number;
  candidate_contributions: CrisisCommodityShadowContribution[];
  weights: Record<string, number>;
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
  next_step: string;
};

export type CrisisCommodityAdmissionDecision = "recommend_include" | "watch" | "do_not_include";

export type CrisisCommodityAdmissionItem = {
  field: string;
  label: string;
  decision: CrisisCommodityAdmissionDecision;
  decision_label: string;
  reason: string;
  next_step: string;
  sample_count: number | null;
  minimum_sample_count: number | null;
  crisis_sample_count: number | null;
  minimum_crisis_sample_count: number | null;
  crisis_hit_rate: number | null;
  max_abs_correlation: number | null;
  correlation_threshold: number | null;
  latest_date: string | null;
  series_id: string | null;
  source: string | null;
  used_in_official_score: boolean;
};

export type CrisisCommodityAdmission = {
  rule_version: string;
  scope: string;
  decision_counts: Record<CrisisCommodityAdmissionDecision, number>;
  items: CrisisCommodityAdmissionItem[];
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
  next_step: string;
};

export type CrisisCommodityApprovalPack = {
  pack_version: string;
  scope: string;
  source_rule_version: string;
  shadow_formula_version: string;
  decision_counts: Record<CrisisCommodityAdmissionDecision, number>;
  recommended_fields: string[];
  watch_fields: string[];
  rejected_fields: string[];
  summary: string;
  copy_text: string;
  warnings: string[];
  approval_required: boolean;
  official_score_unchanged: boolean;
};

export type MacroToolkitInputEvidenceItem = NonNullable<MacroToolkitInputEvidence["inputs"]>[number];
export type CrisisGapGroupKey = "equity" | "liquidity" | "commodity" | "curve_credit" | "fx" | "other";
export type CrisisGapItem = {
  label: string;
  warning: string;
  detail: string;
  identifiers: string[];
};
export type CrisisGapGroup = {
  key: CrisisGapGroupKey;
  label: string;
  items: CrisisGapItem[];
};

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isCrisisComponent(value: unknown): value is CrisisComponent {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.key === "string" && typeof value.label === "string";
}

export function normalizeCommodityCoverage(value: unknown): CrisisCommodityCoverage | null {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return null;
  }
  const items = value.items.map(normalizeCommodityCoverageItem).filter((item) => item !== null);
  if (!items.length) {
    return null;
  }
  return {
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    tracked_count: typeof value.tracked_count === "number" ? value.tracked_count : items.length,
    available_count:
      typeof value.available_count === "number" ? value.available_count : items.filter((item) => item.available).length,
    used_in_crisis_score: Array.isArray(value.used_in_crisis_score)
      ? value.used_in_crisis_score.map((item) => String(item)).filter(Boolean)
      : [],
    candidate_summary: normalizeCommodityCandidateSummary(value.candidate_summary),
    items,
  };
}

export function normalizeCommodityCandidateSummary(value: unknown): CrisisCommodityCandidateSummary | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    shadow_review_ready_count:
      typeof value.shadow_review_ready_count === "number" ? value.shadow_review_ready_count : 0,
    needs_current_data_count:
      typeof value.needs_current_data_count === "number" ? value.needs_current_data_count : 0,
    missing_data_count: typeof value.missing_data_count === "number" ? value.missing_data_count : 0,
    shadow_evaluation_ready_count:
      typeof value.shadow_evaluation_ready_count === "number" ? value.shadow_evaluation_ready_count : 0,
    shadow_evaluation_short_count:
      typeof value.shadow_evaluation_short_count === "number" ? value.shadow_evaluation_short_count : 0,
    shadow_evaluation_status_counts: normalizeNumberRecord(value.shadow_evaluation_status_counts),
    shadow_evaluation_short_items: Array.isArray(value.shadow_evaluation_short_items)
      ? value.shadow_evaluation_short_items.map(normalizeCommodityShadowShortItem).filter((item) => item !== null)
      : [],
    suggested_refresh_products: Array.isArray(value.suggested_refresh_products)
      ? value.suggested_refresh_products.map((item) => String(item).trim()).filter(Boolean)
      : [],
    shadow_evaluation_next_step:
      typeof value.shadow_evaluation_next_step === "string" ? value.shadow_evaluation_next_step : "",
    formula_change_required: value.formula_change_required === true,
    approval_required: value.approval_required === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "",
  };
}

export function normalizeCommodityShadowShortItem(value: unknown): CrisisCommodityShadowShortItem | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
  };
}

export function normalizeNumberRecord(value: unknown) {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number")
      .map(([key, count]) => [key, count]),
  );
}

export function normalizeCommodityCoverageItem(value: unknown): CrisisCommodityCoverageItem | null {
  if (!isRecord(value) || typeof value.field !== "string" || typeof value.label !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: value.label,
    aliases: Array.isArray(value.aliases) ? value.aliases.map((item) => String(item)).filter(Boolean) : [],
    matched_alias: typeof value.matched_alias === "string" ? value.matched_alias : null,
    role: typeof value.role === "string" ? value.role : "supplemental_observation",
    used_in_formula: value.used_in_formula === true,
    available: value.available === true,
    row_count: typeof value.row_count === "number" ? value.row_count : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    report_date: typeof value.report_date === "string" ? value.report_date : null,
    date_alignment_status: typeof value.date_alignment_status === "string" ? value.date_alignment_status : null,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    value: typeof value.value === "number" ? value.value : null,
    candidate_decision: normalizeCommodityCandidateDecision(value.candidate_decision),
    shadow_evaluation: normalizeCommodityShadowEvaluation(value.shadow_evaluation),
  };
}

export function normalizeCommodityCandidateDecision(value: unknown): CrisisCommodityCandidateDecision | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "候选状态待确认",
    reason: typeof value.reason === "string" ? value.reason : "候选原因待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

export function normalizeCommodityShadowEvaluation(value: unknown): CrisisCommodityShadowEvaluation | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    status: typeof value.status === "string" ? value.status : "unknown",
    label: typeof value.label === "string" ? value.label : "影子评估待确认",
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    sample_gap: typeof value.sample_gap === "number" ? value.sample_gap : null,
    window_start: typeof value.window_start === "string" ? value.window_start : null,
    window_end: typeof value.window_end === "string" ? value.window_end : null,
    target: typeof value.target === "string" ? value.target : "crisis_score",
    candidate_metric: typeof value.candidate_metric === "string" ? value.candidate_metric : "daily_return",
    same_day_correlation: typeof value.same_day_correlation === "number" ? value.same_day_correlation : null,
    lead_1d_correlation: typeof value.lead_1d_correlation === "number" ? value.lead_1d_correlation : null,
    lag_1d_correlation: typeof value.lag_1d_correlation === "number" ? value.lag_1d_correlation : null,
    crisis_hit_rate: typeof value.crisis_hit_rate === "number" ? value.crisis_hit_rate : null,
    crisis_sample_count: typeof value.crisis_sample_count === "number" ? value.crisis_sample_count : null,
    summary: typeof value.summary === "string" ? value.summary : "影子评估摘要待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

export function normalizeCommodityShadowImpact(value: unknown): CrisisCommodityShadowImpact | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    formula_version: typeof value.formula_version === "string" ? value.formula_version : "formula missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    current_score: typeof value.current_score === "number" ? value.current_score : null,
    shadow_score: typeof value.shadow_score === "number" ? value.shadow_score : null,
    delta: typeof value.delta === "number" ? value.delta : null,
    direction: typeof value.direction === "string" ? value.direction : "unknown",
    included_candidates: Array.isArray(value.included_candidates)
      ? value.included_candidates.map((item) => String(item)).filter(Boolean)
      : [],
    candidate_count: typeof value.candidate_count === "number" ? value.candidate_count : 0,
    candidate_contributions: Array.isArray(value.candidate_contributions)
      ? value.candidate_contributions.map(normalizeCommodityShadowContribution).filter((item) => item !== null)
      : [],
    weights: normalizeNumberRecord(value.weights),
    warnings: Array.isArray(value.warnings) ? value.warnings.map((item) => String(item)).filter(Boolean) : [],
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

export function normalizeCommodityShadowContribution(value: unknown): CrisisCommodityShadowContribution | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    candidate_metric: typeof value.candidate_metric === "string" ? value.candidate_metric : "metric missing",
    candidate_value: typeof value.candidate_value === "number" ? value.candidate_value : null,
    weight: typeof value.weight === "number" ? value.weight : null,
    contribution: typeof value.contribution === "number" ? value.contribution : null,
    used_in_official_score: value.used_in_official_score === true,
    status: typeof value.status === "string" ? value.status : "status missing",
  };
}

export function normalizeCommodityAdmission(value: unknown): CrisisCommodityAdmission | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    rule_version: typeof value.rule_version === "string" ? value.rule_version : "rule missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    decision_counts: normalizeCommodityAdmissionDecisionCounts(value.decision_counts),
    items: Array.isArray(value.items)
      ? value.items.map(normalizeCommodityAdmissionItem).filter((item) => item !== null)
      : [],
    warnings: Array.isArray(value.warnings) ? value.warnings.map((item) => String(item)).filter(Boolean) : [],
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
  };
}

export function normalizeCommodityAdmissionDecisionCounts(value: unknown): Record<CrisisCommodityAdmissionDecision, number> {
  const record = isRecord(value) ? value : {};
  return {
    recommend_include: typeof record.recommend_include === "number" ? record.recommend_include : 0,
    watch: typeof record.watch === "number" ? record.watch : 0,
    do_not_include: typeof record.do_not_include === "number" ? record.do_not_include : 0,
  };
}

export function normalizeCommodityAdmissionItem(value: unknown): CrisisCommodityAdmissionItem | null {
  if (!isRecord(value) || typeof value.field !== "string") {
    return null;
  }
  return {
    field: value.field,
    label: typeof value.label === "string" ? value.label : value.field,
    decision: normalizeCommodityAdmissionDecision(value.decision),
    decision_label: typeof value.decision_label === "string" ? value.decision_label : "准入结论待确认",
    reason: typeof value.reason === "string" ? value.reason : "准入原因待确认",
    next_step: typeof value.next_step === "string" ? value.next_step : "下一步待确认",
    sample_count: typeof value.sample_count === "number" ? value.sample_count : null,
    minimum_sample_count: typeof value.minimum_sample_count === "number" ? value.minimum_sample_count : null,
    crisis_sample_count: typeof value.crisis_sample_count === "number" ? value.crisis_sample_count : null,
    minimum_crisis_sample_count:
      typeof value.minimum_crisis_sample_count === "number" ? value.minimum_crisis_sample_count : null,
    crisis_hit_rate: typeof value.crisis_hit_rate === "number" ? value.crisis_hit_rate : null,
    max_abs_correlation: typeof value.max_abs_correlation === "number" ? value.max_abs_correlation : null,
    correlation_threshold: typeof value.correlation_threshold === "number" ? value.correlation_threshold : null,
    latest_date: typeof value.latest_date === "string" ? value.latest_date : null,
    series_id: typeof value.series_id === "string" ? value.series_id : null,
    source: typeof value.source === "string" ? value.source : null,
    used_in_official_score: value.used_in_official_score === true,
  };
}

export function normalizeCommodityAdmissionDecision(value: unknown): CrisisCommodityAdmissionDecision {
  if (value === "recommend_include" || value === "watch" || value === "do_not_include") {
    return value;
  }
  return "do_not_include";
}

export function normalizeCommodityApprovalPack(value: unknown): CrisisCommodityApprovalPack | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    pack_version: typeof value.pack_version === "string" ? value.pack_version : "pack missing",
    scope: typeof value.scope === "string" ? value.scope : "scope missing",
    source_rule_version:
      typeof value.source_rule_version === "string" ? value.source_rule_version : "source rule missing",
    shadow_formula_version:
      typeof value.shadow_formula_version === "string" ? value.shadow_formula_version : "shadow formula missing",
    decision_counts: normalizeCommodityAdmissionDecisionCounts(value.decision_counts),
    recommended_fields: normalizeStringList(value.recommended_fields),
    watch_fields: normalizeStringList(value.watch_fields),
    rejected_fields: normalizeStringList(value.rejected_fields),
    summary: typeof value.summary === "string" ? value.summary : "审批材料摘要待确认",
    copy_text: typeof value.copy_text === "string" ? value.copy_text : "",
    warnings: normalizeStringList(value.warnings),
    approval_required: value.approval_required === true,
    official_score_unchanged: value.official_score_unchanged === true,
  };
}

export function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

export function toDisplayNumber(value: unknown) {
  return typeof value === "number" || typeof value === "string" ? value : "缺失";
}

export function formatCrisisWeight(key: string, weights: Record<string, unknown>) {
  const weight = weights[key];
  return typeof weight === "number" ? formatPercent(weight) : "缺失";
}

export function formatCrisisRowCount(rowCount: number | null | undefined) {
  return typeof rowCount === "number" ? `${rowCount} rows` : "行数缺失";
}

export function formatCommodityCoverageDateStatus(status: string | null | undefined) {
  if (status === "aligned") {
    return "同日";
  }
  if (status === "lagging") {
    return "滞后";
  }
  if (status === "missing") {
    return "日期缺失";
  }
  return "对齐状态缺失";
}

export function formatCommodityCandidateSummaryDetail(summary: CrisisCommodityCandidateSummary) {
  return `影子评估就绪 ${summary.shadow_review_ready_count}，待补当日 ${summary.needs_current_data_count}，缺失 ${summary.missing_data_count}`;
}

export function formatCommodityShadowSummary(coverage: CrisisCommodityCoverage) {
  const firstReady = coverage.items.find((item) => item.shadow_evaluation?.status === "review_ready")?.shadow_evaluation;
  const summary = coverage.candidate_summary;
  if (!firstReady) {
    return summary?.shadow_evaluation_next_step || "影子评估样本不足";
  }
  const shortText = summary?.shadow_evaluation_short_count
    ? `${summary.shadow_evaluation_short_count} 个样本不足`
    : "样本不足 0";
  return [
    `${summary?.shadow_evaluation_ready_count ?? 0} 个可读`,
    shortText,
    formatCommodityShadowDetail(firstReady),
    summary?.shadow_evaluation_next_step,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function formatCommodityShadowDetail(evaluation: CrisisCommodityShadowEvaluation) {
  const parts = [
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `危机期命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
  ];
  if (evaluation.status === "history_short" && typeof evaluation.minimum_sample_count === "number") {
    parts.push(`最低样本 ${evaluation.minimum_sample_count}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.sample_gap === "number") {
    parts.push(`还差 ${evaluation.sample_gap}`);
  }
  return parts.join(" · ");
}

export function formatCommodityShadowDecisionMetrics(evaluation: CrisisCommodityShadowEvaluation) {
  const parts = [
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `领先相关 ${formatSignedDecimal(evaluation.lead_1d_correlation)}`,
    `滞后相关 ${formatSignedDecimal(evaluation.lag_1d_correlation)}`,
    `危机期命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `危机样本 ${evaluation.crisis_sample_count ?? "缺失"}`,
  ];
  if (evaluation.window_start || evaluation.window_end) {
    parts.push(`窗口 ${evaluation.window_start ?? "缺失"} -> ${evaluation.window_end ?? "缺失"}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.minimum_sample_count === "number") {
    parts.push(`最低样本 ${evaluation.minimum_sample_count}`);
  }
  if (evaluation.status === "history_short" && typeof evaluation.sample_gap === "number") {
    parts.push(`还差 ${evaluation.sample_gap}`);
  }
  return parts.join(" · ");
}

export type CommodityPromotionRuleStatus = "ready_for_review" | "manual_review" | "not_recommended";
export type CommodityPromotionRuleCheck = {
  name: string;
  status: CommodityPromotionRuleStatus;
  value: string;
};
export type CommodityPromotionRuleItem = {
  field: string;
  label: string;
  status: CommodityPromotionRuleStatus;
  reason: string;
  checks: CommodityPromotionRuleCheck[];
};

export function commodityPromotionRuleItem(item: CrisisCommodityCoverageItem): CommodityPromotionRuleItem {
  const evaluation = item.shadow_evaluation;
  if (!evaluation || evaluation.status !== "review_ready") {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "not_recommended",
      reason: "样本不足，先补齐历史数据",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  const hasEnoughSamples =
    (evaluation.sample_count ?? 0) >= (evaluation.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES);
  const hasCrisisSamples = (evaluation.crisis_sample_count ?? 0) >= MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES;
  const correlation = Math.max(
    Math.abs(evaluation.same_day_correlation ?? 0),
    Math.abs(evaluation.lead_1d_correlation ?? 0),
    Math.abs(evaluation.lag_1d_correlation ?? 0),
  );
  const hasReadableMetrics = evaluation.crisis_hit_rate != null && correlation > 0;
  if (!hasEnoughSamples || !hasCrisisSamples || evaluation.crisis_hit_rate == null) {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "not_recommended",
      reason: "准入样本或危机期指标不足",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  if (!hasReadableMetrics || correlation < MACRO_COMMODITY_SHADOW_MIN_CORRELATION) {
    return {
      field: item.field,
      label: item.label || item.field,
      status: "manual_review",
      reason: "相关性偏弱，需人工复核",
      checks: commodityPromotionRuleChecks(evaluation),
    };
  }
  return {
    field: item.field,
    label: item.label || item.field,
    status: "ready_for_review",
    reason: "影子指标满足准入检查，仍需审批确认",
    checks: commodityPromotionRuleChecks(evaluation),
  };
}

export function commodityPromotionRuleChecks(
  evaluation: CrisisCommodityShadowEvaluation | null,
): CommodityPromotionRuleCheck[] {
  const isReviewReady = evaluation?.status === "review_ready";
  const sampleCount = evaluation?.sample_count ?? null;
  const minimumSampleCount = evaluation?.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES;
  const crisisSampleCount = isReviewReady ? (evaluation.crisis_sample_count ?? null) : null;
  const correlation = isReviewReady
    ? Math.max(
        Math.abs(evaluation.same_day_correlation ?? 0),
        Math.abs(evaluation.lead_1d_correlation ?? 0),
        Math.abs(evaluation.lag_1d_correlation ?? 0),
      )
    : null;
  return [
    {
      name: "样本检查",
      status:
        typeof sampleCount === "number" && sampleCount >= minimumSampleCount
          ? "ready_for_review"
          : "not_recommended",
      value: `${sampleCount ?? "缺失"}/${minimumSampleCount}`,
    },
    {
      name: "危机样本检查",
      status:
        typeof crisisSampleCount === "number" && crisisSampleCount >= MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES
          ? "ready_for_review"
          : "not_recommended",
      value: `${crisisSampleCount ?? "缺失"}/${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES}`,
    },
    {
      name: "相关性检查",
      status:
        correlation == null
          ? "not_recommended"
          : correlation >= MACRO_COMMODITY_SHADOW_MIN_CORRELATION
            ? "ready_for_review"
            : "manual_review",
      value: typeof correlation === "number" ? formatSignedDecimal(correlation) : "缺失",
    },
    {
      name: "命中率检查",
      status: evaluation?.crisis_hit_rate == null ? "not_recommended" : "ready_for_review",
      value: formatPercent(evaluation?.crisis_hit_rate),
    },
  ];
}

export function commodityPromotionRuleStatusLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "通过";
  }
  if (status === "manual_review") {
    return "待人工判断";
  }
  return "不建议进入公式";
}

export function commodityPromotionRuleCheckStatusLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "通过";
  }
  if (status === "manual_review") {
    return "待人工判断";
  }
  return "未通过";
}

export function commodityReviewConclusionLabel(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "可进入人工复核";
  }
  if (status === "manual_review") {
    return "继续观察";
  }
  return "不建议纳入";
}

export function commodityReviewConclusionColor(status: CommodityPromotionRuleStatus) {
  if (status === "ready_for_review") {
    return "green";
  }
  if (status === "manual_review") {
    return "gold";
  }
  return "red";
}

export function commodityAdmissionDecisionColor(decision: CrisisCommodityAdmissionDecision) {
  if (decision === "recommend_include") {
    return "green";
  }
  if (decision === "watch") {
    return "gold";
  }
  return "red";
}

export function formatCommodityAdmissionMetrics(item: CrisisCommodityAdmissionItem) {
  const sampleText =
    item.decision === "do_not_include" || item.sample_count == null
      ? `样本 ${item.sample_count ?? "缺失"}/${item.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES}`
      : `样本 ${item.sample_count}`;
  return [
    sampleText,
    `危机样本 ${item.crisis_sample_count ?? "缺失"}`,
    `命中率 ${formatPercent(item.crisis_hit_rate)}`,
    `最大相关 ${formatSignedDecimal(item.max_abs_correlation)}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
    item.source ? `来源 ${item.source}` : null,
    item.series_id ? `series ${item.series_id}` : null,
    item.used_in_official_score ? "已纳入正式 Crisis Score" : "审批前不改变正式 Crisis Score",
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

export function formatCommodityAdmissionNextStep(item: CrisisCommodityAdmissionItem) {
  if (item.decision === "recommend_include") {
    return "提交人工复核与权重审批";
  }
  if (item.decision === "watch") {
    return "复核相关性与危机期命中率";
  }
  return item.next_step;
}

export function formatCommodityApprovalPackFields(fields: string[]) {
  return fields.length ? fields.join(" / ") : "无";
}

export function formatSignedDeltaFromPack(copyText: string) {
  const match = copyText.match(/shadow delta\s+([+-]?\d+(?:\.\d+)?)/);
  return match?.[1] ?? "缺失";
}

export function formatCommodityReviewConclusionMetrics(item: CrisisCommodityCoverageItem) {
  const evaluation = item.shadow_evaluation;
  if (!evaluation) {
    return "影子评估缺失";
  }
  const minimumSampleCount = evaluation.minimum_sample_count ?? MACRO_COMMODITY_SHADOW_MIN_SAMPLES;
  const sampleText =
    evaluation.status === "history_short" || evaluation.sample_count == null
      ? `样本 ${evaluation.sample_count ?? "缺失"}/${minimumSampleCount}`
      : `样本 ${evaluation.sample_count}`;
  return [
    sampleText,
    `危机样本 ${evaluation.crisis_sample_count ?? "缺失"}`,
    `命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

export function formatCommodityReviewConclusionNextStep(
  status: CommodityPromotionRuleStatus,
  item: CrisisCommodityCoverageItem,
) {
  if (status === "ready_for_review") {
    return "下一步：提交人工复核与权重审批";
  }
  if (status === "manual_review") {
    return "下一步：复核相关性与危机期命中率";
  }
  const sampleGap = item.shadow_evaluation?.sample_gap;
  return typeof sampleGap === "number"
    ? `下一步：先补齐历史数据，还差 ${sampleGap} 个样本`
    : "下一步：先补齐历史数据";
}

export function formatCommodityShadowImpactDirectionDetail(items: CrisisCommodityCoverageItem[]) {
  if (!items.length) {
    return "暂无可复核商品候选";
  }
  return `${formatCommodityActionQueueLabels(items)} 需要 v2 权重后确认方向`;
}

export function formatCommodityShadowImpactDriverDetail(item: CrisisCommodityCoverageItem) {
  const evaluation = item.shadow_evaluation;
  if (!evaluation) {
    return "影子评估缺失";
  }
  return [
    `命中率 ${formatPercent(evaluation.crisis_hit_rate)}`,
    `同日相关 ${formatSignedDecimal(evaluation.same_day_correlation)}`,
    `样本 ${evaluation.sample_count ?? "缺失"}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

export function commodityShadowImpactDirectionLabel(direction: string) {
  if (direction === "higher_stress") {
    return "压力上行";
  }
  if (direction === "lower_stress") {
    return "压力下行";
  }
  if (direction === "unchanged") {
    return "基本不变";
  }
  return "待确认";
}

export function formatSignedDelta(value: number | null | undefined, digits = 2) {
  if (value == null) {
    return "缺失";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function formatCommodityShadowImpactWarnings(shadowImpact: CrisisCommodityShadowImpact) {
  return shadowImpact.warnings.length ? shadowImpact.warnings.join(" / ") : "warnings missing";
}

export function formatCommodityShadowContributionDetail(item: CrisisCommodityShadowContribution) {
  return [
    `${item.candidate_metric} ${formatSignedDelta(item.candidate_value, 2)}`,
    `贡献 ${formatSignedDelta(item.contribution, 4)}`,
    `权重 ${formatPercent(item.weight)}`,
    `样本 ${item.sample_count ?? "缺失"}`,
    item.latest_date ? `最新 ${item.latest_date}` : null,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");
}

export function buildCommodityPromotionAuditPackCopyText(
  promotionItems: CommodityPromotionRuleItem[],
  counts: {
    manualCount: number;
    rejectedCount: number;
    analysisMeta?: ResultMeta | null;
    analysisAsOfDate?: string | null;
    reviewQueueItems: CrisisCommodityCoverageItem[];
    shortQueueItems: CrisisCommodityCoverageItem[];
    coverageItems: CrisisCommodityCoverageItem[];
    commodityInput: MacroToolkitInputEvidenceItem | null;
    summary: CrisisCommodityCandidateSummary | null;
  },
) {
  const reviewQueueText = formatCommodityActionQueueLabels(counts.reviewQueueItems);
  const shortQueueText = formatCommodityActionQueueLabels(counts.shortQueueItems);
  const nextStepText = counts.summary
    ? formatCommodityActionQueueNextStep(counts.reviewQueueItems, counts.shortQueueItems, counts.summary)
    : "下一步待确认";
  return [
    "Crisis Score 商品候选审计包",
    `分析日期 ${counts.analysisMeta?.as_of_date ?? counts.analysisAsOfDate ?? "缺失"}`,
    `source_version ${counts.analysisMeta?.source_version ?? "缺失"}`,
    `vendor_version ${counts.analysisMeta?.vendor_version ?? "缺失"}`,
    `rule_version ${counts.analysisMeta?.rule_version ?? "缺失"}`,
    `cache_version ${counts.analysisMeta?.cache_version ?? "缺失"}`,
    `规则版本 ${MACRO_COMMODITY_SHADOW_RULE_VERSION}`,
    "用途：商品候选进入公式前的影子复核",
    "边界：不写入 Crisis Score，不改变权重",
    "审批：历史回测、相关性检验、权重审批、版本记录齐备后再提交",
    `准入检查：样本>=${MACRO_COMMODITY_SHADOW_MIN_SAMPLES} / 危机样本>=${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} / 相关性可读 / 命中率可读`,
    `样本阈值 >=${MACRO_COMMODITY_SHADOW_MIN_SAMPLES} 个重叠样本`,
    `危机样本阈值 >=${MACRO_COMMODITY_SHADOW_MIN_CRISIS_SAMPLES} 个高 Crisis Score 样本`,
    `相关性阈值 |corr|>=${MACRO_COMMODITY_SHADOW_MIN_CORRELATION.toFixed(2)} 才可直接通过`,
    `人工复核队列 ${reviewQueueText}`,
    `补历史样本队列 ${shortQueueText}`,
    `处理顺序 ${nextStepText}`,
    formatOfficialCommodityInputAuditLine(counts.commodityInput),
    `待人工判断 ${counts.manualCount}`,
    `不建议进入公式 ${counts.rejectedCount}`,
    ...counts.coverageItems.map(formatCommodityAuditSourceLine),
    ...promotionItems.flatMap((item) => [
      `${item.label} · ${commodityPromotionRuleStatusLabel(item.status)} · ${item.reason}`,
      ...item.checks.map(
        (check) =>
          `${item.label} · ${check.name} ${commodityPromotionRuleCheckStatusLabel(check.status)} ${check.value}`,
      ),
    ]),
  ].join("\n");
}

export function commodityShadowStatusColor(status: string | null | undefined) {
  if (status === "review_ready") {
    return "green";
  }
  if (status === "history_short") {
    return "orange";
  }
  return "default";
}

export function formatCommodityAuditSourceLine(item: CrisisCommodityCoverageItem) {
  const formulaText = item.used_in_formula ? "已纳入公式" : "当前未计入 Crisis Score";
  return [
    `候选来源 ${item.label || item.field}`,
    item.series_id ?? "series 缺失",
    `aliases ${item.aliases.length ? item.aliases.join(" / ") : "缺失"}`,
    `matched ${item.matched_alias ?? "缺失"}`,
    item.source ?? "source 缺失",
    `latest ${item.latest_date ?? "缺失"}`,
    `report ${item.report_date ?? "缺失"}`,
    formatCommodityCoverageDateStatus(item.date_alignment_status),
    `rows ${item.row_count ?? "缺失"}`,
    formulaText,
  ].join(" · ");
}

export function formatOfficialCommodityInputAuditLine(input: MacroToolkitInputEvidenceItem | null) {
  if (!input) {
    return "正式商品输入 缺失 · 已纳入 Crisis Score 公式的南华输入未命中";
  }
  return [
    `正式商品输入 ${input.label || input.field}`,
    formatCrisisInputIdentifiers(input),
    `source ${input.source ?? "缺失"}`,
    `latest ${input.latest_date ?? "缺失"}`,
    `rows ${input.row_count ?? "缺失"}`,
    `value ${formatValue(input.value ?? null, "")}`,
    "已纳入 Crisis Score 公式",
  ].join(" · ");
}

export function isCommodityShadowReviewReady(item: CrisisCommodityCoverageItem) {
  return item.shadow_evaluation?.status === "review_ready";
}

export function isCommodityShadowHistoryShort(item: CrisisCommodityCoverageItem) {
  return item.shadow_evaluation?.status === "history_short";
}

export function formatCommodityActionQueueLabels(items: CrisisCommodityCoverageItem[]) {
  if (!items.length) {
    return "无";
  }
  return items.map((item) => item.label || item.field).join(" / ");
}

export function formatCommodityActionQueueNextStep(
  reviewItems: CrisisCommodityCoverageItem[],
  shortItems: CrisisCommodityCoverageItem[],
  summary: CrisisCommodityCandidateSummary,
) {
  if (shortItems.length && reviewItems.length) {
    return `下一步：先补齐样本不足品种，再复核${formatCommodityActionQueueShortNames(reviewItems)}的相关性与命中率`;
  }
  if (shortItems.length) {
    return "下一步：先补齐样本不足品种，再重新运行完整分析";
  }
  if (reviewItems.length) {
    return `下一步：复核${formatCommodityActionQueueShortNames(reviewItems)}的相关性与命中率`;
  }
  return summary.shadow_evaluation_next_step || "下一步待确认";
}

export function formatCommodityActionQueueShortNames(items: CrisisCommodityCoverageItem[]) {
  return items.map((item) => commodityChineseShortName(item.label || item.field)).join("、");
}

export function commodityChineseShortName(label: string) {
  const normalized = label.toLowerCase();
  if (normalized.includes("copper")) {
    return "铜";
  }
  if (normalized.includes("crude")) {
    return "原油";
  }
  if (normalized.includes("aluminum")) {
    return "铝";
  }
  if (normalized.includes("gold")) {
    return "黄金";
  }
  if (normalized.includes("rebar")) {
    return "螺纹钢";
  }
  if (normalized.includes("iron")) {
    return "铁矿石";
  }
  return label;
}

export function formatCommodityShadowShortfallList(summary: CrisisCommodityCandidateSummary) {
  const items = summary.shadow_evaluation_short_items.map((item) => {
    const sampleText =
      typeof item.sample_count === "number" && typeof item.minimum_sample_count === "number"
        ? `${item.sample_count}/${item.minimum_sample_count}`
        : "样本缺失";
    const gapText = typeof item.sample_gap === "number" ? `还差 ${item.sample_gap}` : "缺口待确认";
    const dateText = item.latest_date ? `，最新 ${item.latest_date}` : "";
    return `${item.label || item.field} ${sampleText}，${gapText}${dateText}`;
  });
  return `样本不足：${items.join("；")}`;
}

export function crisisCommodityShortItemsFromResult(
  result: MacroToolkitCapabilityResult | null | undefined,
): CrisisCommodityShadowShortItem[] {
  if (!result) {
    return [];
  }
  const coverage = normalizeCommodityCoverage(
    (result as { commodity_coverage?: unknown }).commodity_coverage ?? result.result.commodity_coverage,
  );
  return coverage?.candidate_summary?.shadow_evaluation_short_items ?? [];
}

export function suggestedCommodityRefreshStartDate(result: MacroToolkitCapabilityResult | null | undefined) {
  const latestDates = crisisCommodityShortItemsFromResult(result)
    .map((item) => item.latest_date)
    .filter((date): date is string => Boolean(date));
  if (!latestDates.length) {
    return undefined;
  }
  const earliestLatestDate = latestDates.sort()[0];
  const parsed = new Date(`${earliestLatestDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  parsed.setUTCDate(parsed.getUTCDate() - MACRO_COMMODITY_SUGGESTED_REFRESH_LOOKBACK_DAYS);
  return parsed.toISOString().slice(0, 10);
}

export function crisisCommodityShortItemsFromEnvelope(
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null | undefined,
): CrisisCommodityShadowShortItem[] {
  const result = envelope?.result.capability_results.find((item) => item.key === "crisis_score_cn") ?? null;
  return crisisCommodityShortItemsFromResult(result);
}

export function formatCommodityShortfallChanges(
  beforeItems: CrisisCommodityShadowShortItem[],
  afterItems: CrisisCommodityShadowShortItem[],
): CommodityShortfallChange[] {
  const afterByField = new Map(afterItems.map((item) => [item.field, item]));
  return beforeItems
    .map((before) => {
      if (before.sample_count == null || before.minimum_sample_count == null) {
        return null;
      }
      const after = afterByField.get(before.field);
      const afterSample = after?.sample_count ?? before.minimum_sample_count;
      const afterMinimum = after?.minimum_sample_count ?? before.minimum_sample_count;
      const remainingGap = Math.max(0, afterMinimum - afterSample);
      return {
        field: before.field,
        label: before.label || before.field,
        before: `${before.sample_count}/${before.minimum_sample_count}`,
        after: `${afterSample}/${afterMinimum}`,
        remainingGap,
        resolved: remainingGap === 0,
      };
    })
    .filter((item): item is CommodityShortfallChange => item !== null);
}

export function formatCommodityShortfallChangeList(changes: CommodityShortfallChange[]) {
  return changes.map((item) => `${item.label} ${item.before} -> ${item.after}`).join("；");
}

export function formatCommodityShortfallEstimates(
  beforeItems: CrisisCommodityShadowShortItem[],
  refresh: MacroToolkitCommodityFuturesRefreshRun,
): CommodityShortfallEstimate[] {
  const rowsByProduct = new Map(
    normalizeCommodityRefreshRows(refresh).map((row) => [row.productCode, row.estimatedRows ?? row.rowCount ?? 0]),
  );
  return beforeItems
    .map((item) => {
      if (item.sample_count == null || item.minimum_sample_count == null) {
        return null;
      }
      const product = MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field];
      const estimatedRows = product ? rowsByProduct.get(product) ?? 0 : 0;
      const afterSample = Math.min(item.minimum_sample_count, item.sample_count + estimatedRows);
      return {
        field: item.field,
        label: item.label || item.field,
        before: `${item.sample_count}/${item.minimum_sample_count}`,
        after: `${afterSample}/${item.minimum_sample_count}`,
        estimatedRows,
        canFill: afterSample >= item.minimum_sample_count,
      };
    })
    .filter((item): item is CommodityShortfallEstimate => item !== null && item.estimatedRows > 0);
}

export function formatCommodityShortfallEstimateList(estimates: CommodityShortfallEstimate[]) {
  const canFillAll = estimates.every((item) => item.canFill);
  const prefix = canFillAll
    ? "预计可补齐最低样本，建议刷新商品期货"
    : "预计仍有样本缺口，刷新后仍不会闭环";
  const items = estimates.map((item) => {
    const remainingGap = item.canFill ? 0 : commodityShortfallRemainingGap(item.after);
    const conclusion = item.canFill
      ? `可补齐至 ${item.after}`
      : `预计到 ${item.after}${remainingGap == null ? "" : `，还差 ${remainingGap}`}`;
    return `${item.label} ${item.before}，预计 +${item.estimatedRows}，${conclusion}`;
  });
  return `${prefix}：${items.join("；")}`;
}

export function formatCommodityRefreshActionLabel(estimates: CommodityShortfallEstimate[]) {
  if (!estimates.length) {
    return "刷新商品期货";
  }
  return estimates.every((item) => item.canFill)
    ? "刷新商品期货：刷新并重算证据"
    : "刷新商品期货：仍有缺口，谨慎刷新";
}

export function commodityShortfallRemainingGap(sampleText: string) {
  const match = /^(\d+)\/(\d+)$/.exec(sampleText);
  if (!match) {
    return null;
  }
  return Math.max(0, Number(match[2]) - Number(match[1]));
}

export function commodityShadowRefreshProducts(summary: CrisisCommodityCandidateSummary) {
  const backendSuggestions = summary.suggested_refresh_products.filter(
    (item, index, array) => array.indexOf(item) === index,
  );
  if (backendSuggestions.length) {
    return backendSuggestions;
  }
  return summary.shadow_evaluation_short_items
    .map((item) => MACRO_COMMODITY_FIELD_TO_PRODUCT[item.field])
    .filter((item, index, array): item is string => Boolean(item) && array.indexOf(item) === index);
}

export function formatCommodityShadowRefreshHint(products: string[]) {
  return products.length ? `建议刷新品种：${products.join(" / ")}` : "";
}

export function formatCommodityProducts(products: string[]) {
  return products.length ? `品种 ${products.join(" / ")}` : "品种待选择";
}

export function formatCommodityProductsInline(products: string[]) {
  return products.length ? products.join(" / ") : "待确认";
}

export function commodityRefreshRunProducts(refresh: MacroToolkitCommodityFuturesRefreshRun) {
  return normalizeCommodityRefreshRows(refresh)
    .map((row) => row.productCode)
    .filter((item, index, array) => Boolean(item) && array.indexOf(item) === index);
}

export function formatSignedDecimal(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(2) : "缺失";
}

export const CRISIS_GAP_GROUP_LABELS: Record<CrisisGapGroupKey, string> = {
  equity: "股票风险输入",
  liquidity: "利率与流动性输入",
  commodity: "商品期货输入",
  curve_credit: "曲线与信用输入",
  fx: "汇率输入",
  other: "其他输入",
};

export function normalizeInputEvidence(result: MacroToolkitCapabilityResult) {
  const raw = result.input_evidence ?? result.result.input_evidence;
  if (!raw) {
    return null;
  }
  const inputs = raw.inputs ?? [];
  const missingInputs = raw.missing_inputs ?? [];
  const sources = raw.sources ?? [];
  const latestDates = raw.latest_dates ?? [];
  if (!inputs.length && !missingInputs.length && !sources.length && !latestDates.length) {
    return null;
  }
  return { inputs, missingInputs, sources, latestDates };
}

export function uniqueDisplayParts(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map((value) => value?.trim()).filter((value): value is string => Boolean(value))));
}

export function buildCrisisGapGroups(
  inputEvidence: MacroToolkitInputEvidenceItem[],
  warnings: string[],
  commodityCoverage?: CrisisCommodityCoverage | null,
): CrisisGapGroup[] {
  const warningSet = new Set(warnings);
  const itemsByGroup = new Map<CrisisGapGroupKey, CrisisGapItem[]>();
  const pushItem = (groupKey: CrisisGapGroupKey, item: CrisisGapItem) => {
    const items = itemsByGroup.get(groupKey) ?? [];
    if (!items.some((candidate) => candidate.warning === item.warning && candidate.label === item.label)) {
      items.push(item);
    }
    itemsByGroup.set(groupKey, items);
  };

  for (const input of inputEvidence) {
    const warning = input.warning;
    const isMissing = input.available === false || (warning ? warningSet.has(warning) : false);
    if (!isMissing || !warning) {
      continue;
    }
    pushItem(crisisGapGroupKey(input.field, warning), {
      label: input.label || input.field,
      warning,
      detail: crisisGapInputDetail(input),
      identifiers: crisisGapInputIdentifiers(input),
    });
    warningSet.delete(warning);
  }

  for (const warning of warningSet) {
    pushItem(crisisGapGroupKey("", warning), {
      label: warning.replace(/_MISSING$/, "").toLowerCase(),
      warning,
      detail: "输入证据缺失，缺失不按 0 处理",
      identifiers: [warning],
    });
  }

  for (const item of commodityCoverage?.candidate_summary?.shadow_evaluation_short_items ?? []) {
    pushItem("commodity", {
      label: item.label || item.field,
      warning: "COMMODITY_SAMPLE_SHORT",
      detail: formatCommodityShortfallGapDetail(item),
      identifiers: uniqueDisplayParts([item.field, item.label, "COMMODITY_SAMPLE_SHORT"]),
    });
  }

  return (["equity", "liquidity", "commodity", "curve_credit", "fx", "other"] as CrisisGapGroupKey[])
    .map((key) => ({ key, label: CRISIS_GAP_GROUP_LABELS[key], items: itemsByGroup.get(key) ?? [] }))
    .filter((group) => group.items.length);
}

export function formatCrisisGapSummaryDetail(groups: CrisisGapGroup[]) {
  if (!groups.length) {
    return "无缺失输入";
  }
  return groups
    .map((group) => `${group.label}: ${uniqueDisplayParts(group.items.map((item) => item.warning)).join(" / ")}`)
    .join("；");
}

export function buildCrisisGapRepairFeedback(
  previousGroup: CrisisGapGroup,
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload> | null,
  actionMessage: string,
): CrisisGapRepairFeedback {
  if (!envelope) {
    return {
      groupKey: previousGroup.key,
      groupLabel: previousGroup.label,
      status: "failed",
      message: "完整分析重读失败",
      detail: actionMessage,
    };
  }
  const currentGroup = crisisGapGroupFromEnvelope(envelope, previousGroup.key);
  if (!currentGroup) {
    return {
      groupKey: previousGroup.key,
      groupLabel: previousGroup.label,
      status: "resolved",
      message: "已补齐，完整分析已重读",
      detail: actionMessage,
    };
  }
  return {
    groupKey: previousGroup.key,
    groupLabel: previousGroup.label,
    status: "partial",
    message: "完整分析已重读，仍有缺口",
    detail: currentGroup.items.map((item) => item.warning).join(" / ") || actionMessage,
  };
}

export function crisisGapGroupFromEnvelope(
  envelope: ApiEnvelope<MacroToolkitAnalysisPayload>,
  groupKey: CrisisGapGroupKey,
) {
  const result = envelope.result.capability_results.find((item) => item.key === "crisis_score_cn");
  return crisisGapGroupFromResult(result, groupKey);
}

export function crisisGapGroupFromResult(
  result: MacroToolkitCapabilityResult | null | undefined,
  groupKey: CrisisGapGroupKey,
) {
  if (!result) {
    return null;
  }
  const normalizedEvidence = normalizeInputEvidence(result);
  const inputEvidence = normalizedEvidence?.inputs ?? [];
  const warnings = uniqueDisplayParts([...(result.warnings ?? []), ...(normalizedEvidence?.missingInputs ?? [])]);
  const commodityCoverage = normalizeCommodityCoverage(
    (result as { commodity_coverage?: unknown }).commodity_coverage ?? result.result.commodity_coverage,
  );
  return buildCrisisGapGroups(inputEvidence, warnings, commodityCoverage).find((group) => group.key === groupKey) ?? null;
}

export function crisisGapGroupKey(field: string, warning: string): CrisisGapGroupKey {
  const token = `${field} ${warning}`.toUpperCase();
  if (token.includes("HS300") || token.includes("EQUITY") || token.includes("STOCK")) {
    return "equity";
  }
  if (token.includes("DR007") || token.includes("REVERSE_REPO") || token.includes("LIQUIDITY")) {
    return "liquidity";
  }
  if (token.includes("NANHUA") || token.includes("COMMODITY")) {
    return "commodity";
  }
  if (token.includes("AA_") || token.includes("GOV_") || token.includes("CREDIT") || token.includes("CURVE")) {
    return "curve_credit";
  }
  if (token.includes("USDCNY") || token.includes("FX")) {
    return "fx";
  }
  return "other";
}

export function crisisGapInputDetail(input: MacroToolkitInputEvidenceItem) {
  const rowText = formatCrisisRowCount(input.row_count);
  const dateText = input.latest_date ?? "日期缺失";
  const sourceText = input.source ?? "source missing";
  return `${rowText} · ${dateText} · ${sourceText} · 缺失不按 0 处理`;
}

export function crisisGapInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  return uniqueDisplayParts([input.field, input.warning, ...(input.aliases ?? []), input.series_id]);
}

export function formatCommodityShortfallGapDetail(item: CrisisCommodityShadowShortItem) {
  const sampleText =
    item.sample_count == null || item.minimum_sample_count == null
      ? "样本缺失"
      : `${item.sample_count}/${item.minimum_sample_count}`;
  const gapText = item.sample_gap == null ? "缺口待确认" : `还差 ${item.sample_gap}`;
  const dateText = item.latest_date ? `最新 ${item.latest_date}` : "日期缺失";
  return `${sampleText} · ${gapText} · ${dateText} · 缺失不按 0 处理`;
}

export function findCrisisGapRepairItem(group: CrisisGapGroup, repairItems: MacroToolkitRepairItem[]) {
  const groupIdentifiers = new Set(
    group.items.flatMap((item) => item.identifiers).map((identifier) => identifier.toUpperCase()),
  );
  return repairItems.find((item) => {
    if (!canRefreshMacroSourceBackfill(item)) {
      return false;
    }
    const itemIdentifiers = uniqueDisplayParts([item.alias, item.key, item.label]).map((identifier) =>
      identifier.toUpperCase(),
    );
    return itemIdentifiers.some((identifier) => groupIdentifiers.has(identifier));
  });
}

export function isNanhuaCrisisInput(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([input.field, ...(input.aliases ?? []), input.series_id]).map((item) =>
    item.toUpperCase(),
  );
  return (
    identifiers.includes("NANHUA") ||
    identifiers.includes(NANHUA_CRISIS_ALIAS) ||
    identifiers.includes(NANHUA_SYSTEM_SERIES_ID)
  );
}

export function formatCrisisInputIdentifiers(input: MacroToolkitInputEvidenceItem) {
  const identifiers = uniqueDisplayParts([
    ...(input.aliases ?? []),
    ...(isNanhuaCrisisInput(input) ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    input.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

export function formatCommodityCoverageIdentifiers(item: CrisisCommodityCoverageItem) {
  const identifiers = uniqueDisplayParts([
    ...item.aliases,
    item.matched_alias,
    ...(item.field === "nanhua" || item.used_in_formula ? [NANHUA_CRISIS_ALIAS, NANHUA_SYSTEM_SERIES_ID] : []),
    item.series_id,
  ]);
  return identifiers.join(" / ") || "alias missing";
}

export function formatCrisisInputDetail(input: MacroToolkitInputEvidenceItem | undefined) {
  if (!input) {
    return "Nanhua commodity index / NH0100.NHF 未命中";
  }
  return `${input.label || input.field} · ${formatCrisisInputIdentifiers(input)} · ${
    input.latest_date ?? "日期缺失"
  }`;
}


export function normalizeCommodityRefreshRows(refresh: MacroToolkitCommodityFuturesRefreshRun): CommodityRefreshProductRow[] {
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  const table = refresh.table ?? "fact_commodity_futures_daily";
  return (refresh.products ?? []).map((rawItem, index) => {
    const item = isRecord(rawItem) ? rawItem : { product_code: rawItem };
    const rawProductCode = commodityRefreshProductCode(item.product_code, index);
    const rawSeriesId = commodityRefreshString(item.series_id);
    const productCode = normalizeCommodityRefreshProductCode(rawProductCode, rawSeriesId);
    const option = MACRO_COMMODITY_PRODUCT_OPTIONS.find((candidate) => candidate.value === productCode);
    const productName = commodityRefreshString(item.name_zh) || option?.label || productCode;
    const estimatedRows = commodityRefreshNumber(item.estimated_rows);
    const writtenRows = commodityRefreshNumber(item.row_count);
    const rowCount = isDryRun ? estimatedRows ?? writtenRows : writtenRows ?? estimatedRows;
    const seriesId = rawSeriesId || commodityRefreshSeriesId(productCode);
    const latestDate = commodityRefreshString(item.latest_date) || (isDryRun ? refresh.end_date ?? "待刷新" : refresh.end_date ?? "缺失");
    const latestValue = commodityRefreshNumber(item.latest_value);
    const status = commodityRefreshProductStatus({ isDryRun, rowCount });
    return {
      key: `${productCode}-${index}`,
      productCode,
      productName,
      seriesId,
      status,
      estimatedRows,
      rowCount,
      rowCountLabel: rowCount == null ? "缺失" : `${isDryRun ? "预计 " : ""}${rowCount} 行`,
      latestDate,
      latestValue,
      vendor: commodityRefreshString(item.vendor) || (isDryRun ? "estimate_only" : "缺失"),
      table,
      isNanhua: isNanhuaCommodityRefreshRow(productCode, seriesId),
    };
  });
}

export function commodityRefreshProductCode(value: unknown, index: number) {
  const code = commodityRefreshString(value);
  if (!code) {
    return `#${index + 1}`;
  }
  const normalized = code.toUpperCase();
  return normalized === NANHUA_CRISIS_ALIAS ? NANHUA_COMMODITY_PRODUCT_CODE : normalized;
}

export function normalizeCommodityRefreshProductCode(productCode: string, seriesId: string | null) {
  const candidates = [productCode, seriesId ?? ""].map((item) => item.trim().toUpperCase()).filter(Boolean);
  for (const candidate of candidates) {
    if (candidate === NANHUA_CRISIS_ALIAS || candidate === NANHUA_SYSTEM_SERIES_ID) {
      return NANHUA_COMMODITY_PRODUCT_CODE;
    }
    if (candidate === "CA.COPPER") {
      return "CU";
    }
    if (candidate === "CA.ALUMINUM") {
      return "AL";
    }
    if (candidate.startsWith("COMMODITY.")) {
      const code = candidate.slice("COMMODITY.".length);
      if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === code)) {
        return code;
      }
    }
    if (MACRO_COMMODITY_PRODUCT_OPTIONS.some((option) => option.value === candidate)) {
      return candidate;
    }
  }
  return productCode;
}

export function commodityRefreshString(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function commodityRefreshNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

export function commodityRefreshSeriesId(productCode: string) {
  const normalized = productCode.trim().toUpperCase();
  if (normalized === NANHUA_COMMODITY_PRODUCT_CODE || normalized === NANHUA_CRISIS_ALIAS) {
    return NANHUA_SYSTEM_SERIES_ID;
  }
  if (normalized === "NHII") {
    return "NHII.NH";
  }
  if (normalized === "CU") {
    return "CA.COPPER";
  }
  if (normalized === "AL") {
    return "CA.ALUMINUM";
  }
  return normalized.startsWith("#") ? "缺失" : `COMMODITY.${normalized}`;
}

export function isNanhuaCommodityRefreshRow(productCode: string, seriesId: string) {
  const normalizedProductCode = productCode.trim().toUpperCase();
  const normalizedSeriesId = seriesId.trim().toUpperCase();
  return (
    normalizedProductCode === NANHUA_COMMODITY_PRODUCT_CODE ||
    normalizedProductCode === NANHUA_CRISIS_ALIAS ||
    normalizedSeriesId === NANHUA_SYSTEM_SERIES_ID ||
    normalizedSeriesId === NANHUA_CRISIS_ALIAS
  );
}

export function commodityRefreshIdentifierText(row: CommodityRefreshProductRow) {
  const identifiers = row.isNanhua
    ? [row.productCode, NANHUA_CRISIS_ALIAS, row.seriesId]
    : [row.productCode, row.seriesId];
  return Array.from(new Set(identifiers.filter(Boolean))).join(" / ");
}

export function commodityRefreshProductStatus({
  isDryRun,
  rowCount,
}: {
  isDryRun: boolean;
  rowCount: number | null;
}): CommodityRefreshProductRow["status"] {
  if (rowCount == null || rowCount <= 0) {
    return "missing";
  }
  return isDryRun ? "estimated" : "written";
}

export function commodityRefreshStatusText(status: CommodityRefreshProductRow["status"]) {
  if (status === "estimated") {
    return "预计可写";
  }
  if (status === "written") {
    return "已写入";
  }
  return "未命中";
}

export function commodityRefreshStatusColor(status: CommodityRefreshProductRow["status"]) {
  if (status === "missing") {
    return "red";
  }
  return status === "written" ? "green" : "blue";
}

export function formatCommodityRefreshResult(refresh: MacroToolkitCommodityFuturesRefreshRun) {
  const productCount = refresh.product_count ?? refresh.products?.length ?? 0;
  const isDryRun = refresh.status === "dry_run" || refresh.dry_run === true;
  if (refresh.status === "queued") {
    return `商品期货刷新已排队，${productCount} 个品种，等待后台任务完成`;
  }
  const rowCount = isDryRun
    ? refresh.estimated_total_rows ?? refresh.row_count ?? 0
    : refresh.row_count ?? refresh.estimated_total_rows ?? 0;
  const action = isDryRun ? "预估完成" : "刷新完成";
  const tradingDays = isDryRun && refresh.estimated_trading_days ? `，约 ${refresh.estimated_trading_days} 个交易日` : "";
  return `商品期货${action}：${productCount} 个品种，${rowCount} 行${tradingDays}`;
}

export function commodityRefreshRowDeltaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshNullableNumberText(summary.row_count_before);
  const after = commodityRefreshNullableNumberText(summary.row_count_after);
  const delta = summary.row_count_delta == null ? "变化缺失" : `${summary.row_count_delta >= 0 ? "+" : ""}${summary.row_count_delta}`;
  return `行数 ${before} → ${after}（${delta}）`;
}

export function commodityRefreshLatestDateText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.latest_trade_date_before ?? "缺失";
  const after = summary.latest_trade_date_after ?? "缺失";
  return `最新日期 ${before} → ${after}`;
}

export function commodityRefreshCoverageText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = commodityRefreshCountPair(summary.available_product_count_before, summary.target_product_count);
  const after = commodityRefreshCountPair(summary.available_product_count_after, summary.target_product_count);
  const newlyAvailable = summary.newly_available_products.length
    ? `新增 ${summary.newly_available_products.join(" / ")}`
    : "新增 无";
  const missing = summary.missing_products_after.length ? `缺失 ${summary.missing_products_after.join(" / ")}` : "缺失 无";
  return `覆盖 ${before} → ${after}，${newlyAvailable}，${missing}`;
}

export function commodityRefreshNanhuaText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const before = summary.nanhua_latest_date_before ?? "缺失";
  const after = summary.nanhua_latest_date_after ?? "缺失";
  const value = formatNumberValue(summary.nanhua_latest_value_after, 2);
  return `南华 ${before} → ${after}，${value}`;
}

export function commodityRefreshSourceText(summary: NonNullable<MacroToolkitCommodityFuturesRefreshRun["summary"]>) {
  const source = summary.source_vendors_after.length ? summary.source_vendors_after.join(" / ") : "缺失";
  return `来源 ${source}`;
}

export function commodityRefreshNullableNumberText(value: number | null) {
  return value == null ? "缺失" : String(value);
}

export function commodityRefreshCountPair(value: number | null, total: number | null) {
  return value == null || total == null ? "缺失" : `${value}/${total}`;
}

export function normalizeMacroSourceBackfillAlias(alias: string | null | undefined) {
  return alias?.trim().toUpperCase() ?? "";
}

export function canRefreshMacroSourceBackfill(item: MacroToolkitRepairItem) {
  return (
    item.action?.kind === "source_backfill_required" &&
    MACRO_SOURCE_BACKFILL_ALIASES.has(normalizeMacroSourceBackfillAlias(item.alias))
  );
}

export function formatValue(value: number | null, unit = "") {
  if (value === null) {
    return "缺失";
  }
  const digits = Math.abs(value) >= 100 ? 2 : 4;
  return `${value.toFixed(digits)}${unit}`;
}

export function formatNumberValue(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) {
    return "缺失";
  }
  return value.toFixed(digits);
}

export type CommodityShortfallChange = {
  field: string;
  label: string;
  before: string;
  after: string;
  remainingGap: number;
  resolved: boolean;
};
export type CommodityShortfallEstimate = CommodityShortfallChange & {
  estimatedRows: number;
  canFill: boolean;
};
export type CommodityRefreshEvidenceChain = {
  suggestedProducts: string[];
  refreshedProducts: string[];
  fullReloaded: boolean;
};
export type CrisisGapRepairFeedback = {
  groupKey: CrisisGapGroupKey;
  groupLabel: string;
  status: "pending" | "resolved" | "partial" | "failed";
  message: string;
  detail: string;
};
