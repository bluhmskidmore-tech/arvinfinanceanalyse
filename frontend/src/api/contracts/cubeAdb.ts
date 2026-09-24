/** Cube query, yield-by-period, cockpit, and ADB (average daily balance) contracts. */
import type { ResultMeta } from "./core";
import type { BalancePageCalibration } from "./balanceLedger";

// --- Cube 多维查询 (`/api/cube`) ---
export type CubeBasis = "formal" | "scenario" | "analytical";

export type CubeQueryRequest = {
  report_date: string;
  fact_table: string;
  measures: string[];
  dimensions?: string[];
  filters?: Record<string, string[]>;
  order_by?: string[];
  limit?: number;
  offset?: number;
  basis?: CubeBasis;
};

export type CubeDrillPath = {
  dimension: string;
  label: string;
  available_values: string[];
  current_filter: string[] | null;
};

export type CubeQueryPayload = {
  report_date: string;
  fact_table: string;
  measures: string[];
  dimensions: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  drill_paths: CubeDrillPath[];
};

export type CubeDimensionsPayload = {
  fact_table: string;
  dimensions: string[];
  measures: string[];
  measure_fields: string[];
};

/** 后端 `CubeQueryResponse`：业务字段与 `result_meta` 同层，非 `ApiEnvelope`。 */
export type CubeQueryResult = CubeQueryPayload & { result_meta: ResultMeta };

// --- 负债结构分析（V1兼容 `/api/risk/buckets` 等原始 JSON，待后端统一 `ApiEnvelope`） ---

/** V1-compatible `/api/analysis/yield-by-period` payload (periods empty when the year has no PnL rollups). */
export type YieldByPeriodSummary = {
  period: string;
  period_type: string;
  start_date: string;
  end_date: string;
  num_days: number;
  total_avg_balance: number;
  total_pnl: number;
  overall_yield: number | null;
  overall_annualized_yield: number | null;
  weighted_portfolio_yield: number | null;
  weighted_portfolio_annualized_yield: number | null;
  items: unknown[];
};

export type YieldByPeriodPayload = {
  period_type: string;
  year: number;
  periods: YieldByPeriodSummary[];
};

export type CockpitWatchItem = {
  id: string;
  label: string;
  level: "watch" | "warning";
  detail: string;
};

export type CockpitAlertEvent = {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  occurred_at: string;
  detail: string;
};

export type CockpitWarningsPayload = {
  report_date: string;
  watch_items: CockpitWatchItem[];
  alert_events: CockpitAlertEvent[];
};

export type ContributionSplitRow = {
  category: string;
  side: "asset" | "liability";
  amount_yi: number | null;
  yield_or_cost: number | null;
  contribution_yi: number | null;
};

export type ContributionSplitPayload = {
  report_date: string;
  contributions: ContributionSplitRow[];
};

/** ADB 日均分析 — 与 V1 `/api/analysis/adb` 对齐 */
export type AdbSummary = {
  total_avg_assets: number;
  total_avg_liabilities: number;
  end_spot_assets: number;
  end_spot_liabilities: number;
};

export type AdbTrendItem = {
  date: string;
  daily_balance: number;
  moving_average_30d: number;
};

export type AdbBreakdownItem = {
  category: string;
  side: "Asset" | "Liability" | string;
  avg_balance: number;
};

export type AdbPayload = {
  summary: AdbSummary;
  trend: AdbTrendItem[];
  breakdown: AdbBreakdownItem[];
};

export type AdbCategoryItem = {
  category: string;
  /** null 表示上游缺数（与 0 语义区分）；渲染层显示 EM_DASH */
  spot_balance: number | null;
  avg_balance: number | null;
  /** null 表示上游缺数（与 0 语义区分）；渲染层显示 EM_DASH */
  proportion: number | null;
  weighted_rate?: number | null;
  rate_coverage_ratio?: number | null;
};

export type AdbAccountingBasisDailyAvgItem = {
  basis_bucket: "AC" | "OCI" | "TPL" | string;
  daily_avg_balance: number | null;
  daily_avg_pct: number | null;
  source_account_patterns: string[];
};

export type AdbAccountingBasisDailyAvg = {
  report_date: string;
  report_month?: string;
  currency_basis: string;
  daily_avg_total: number | null;
  rows: AdbAccountingBasisDailyAvgItem[];
  accounting_controls: string[];
  excluded_controls: string[];
};

export type AdbAccountingBasisDailyAvgTrendItem = AdbAccountingBasisDailyAvg & {
  report_month: string;
};

export type AdbComparisonResponse = {
  result_meta?: ResultMeta;
  report_date: string;
  start_date: string;
  end_date: string;
  /** 用户选择的起止日期对应的日历天数（含首尾），不因 ledger 加权而改变 */
  calendar_days_inclusive: number;
  /**
   * formal_calendar：数据来自 fact_formal_*（CNY 物化）；日均对比分母仍为查询区间日历天数。
   * snapshot_calendar：无 formal 表时回退快照；与页面“7日/30日/年初至今”观察窗口一致。
   * snapshot_distinct_days / ledger_weighted：历史兼容值。
   */
  adb_denominator_basis:
    | "formal_calendar"
    | "snapshot_distinct_days"
    | "snapshot_calendar"
    | "ledger_weighted";
  /** 与区间日均口径一致的分母：有快照时为上述不重复日期数；无数据时为 0 */
  num_days: number;
  /** 正式表中实际覆盖的不重复日期数（可能 < num_days）：资产/负债任一侧含有效余额的不重复观测日并集 */
  coverage_days?: number;
  /** 是否触发了 sample_fill（coverage < calendar 时自动放大） */
  sample_filled?: boolean;
  /** sample_fill 补全方法标识 */
  sample_fill_method?: string;
  simulated: boolean;
  /** null 表示期末时点上游缺数（与 0 语义区分）；渲染层显示 EM_DASH，不参与偏离度计算 */
  total_spot_assets: number | null;
  /** null 表示区间日均不可用（如观测窗口不足/无数据）；渲染层显示 EM_DASH，不参与偏离度计算 */
  total_avg_assets: number | null;
  /** null 表示期末时点上游缺数（与 0 语义区分）；渲染层显示 EM_DASH，不参与偏离度计算 */
  total_spot_liabilities: number | null;
  /** null 表示区间日均不可用（如观测窗口不足/无数据）；渲染层显示 EM_DASH，不参与偏离度计算 */
  total_avg_liabilities: number | null;
  /** total_avg_assets/total_avg_liabilities 为 null 时的原因；未知取值安全归一为 null */
  avg_unavailable_reason?: "insufficient_window" | "no_data" | null;
  /** total_spot_assets/total_spot_liabilities 为 null 时的原因；未知取值安全归一为 null */
  spot_unavailable_reason?: "no_data" | null;
  /** 同业（TYW）区间日均资产（元）；分母与 num_days（快照 distinct 日数）一致 */
  total_avg_interbank_assets: number;
  /** 同业（TYW）区间日均负债（元） */
  total_avg_interbank_liabilities: number;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
  asset_rate_coverage_ratio?: number | null;
  liability_rate_coverage_ratio?: number | null;
  assets_breakdown: AdbCategoryItem[];
  liabilities_breakdown: AdbCategoryItem[];
  accounting_basis_daily_avg?: AdbAccountingBasisDailyAvg;
  /** 区间内每个 report_date 的 AC/OCI/TPL 日均结构（与月度接口中 trend 项结构一致） */
  accounting_basis_daily_avg_trend?: AdbAccountingBasisDailyAvgTrendItem[];
  detail?: string;
  calibration?: BalancePageCalibration | null;
};

export type AdbMonthlyBreakdownItem = {
  category: string;
  avg_balance: number | null;
  proportion?: number | null;
  weighted_rate?: number | null;
  rate_coverage_ratio?: number | null;
};

/** 后端正式口径：月度 NIM（百分点）−50bp 平移；缺 NIM 的月份两字段均为 null */
export type AdbMonthlyNimStress = {
  nim_stressed: number | null;
  delta_bp: number | null;
};

export type AdbMonthlyDataItem = {
  month: string;
  month_label: string;
  num_days: number;
  avg_assets: number | null;
  avg_liabilities: number | null;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
  nim_stress?: AdbMonthlyNimStress | null;
  asset_rate_coverage_ratio?: number | null;
  liability_rate_coverage_ratio?: number | null;
  mom_change_assets: number | null;
  mom_change_pct_assets: number | null;
  mom_change_liabilities: number | null;
  mom_change_pct_liabilities: number | null;
  breakdown_assets: AdbMonthlyBreakdownItem[];
  breakdown_liabilities: AdbMonthlyBreakdownItem[];
};

export type AdbMonthlyResponse = {
  result_meta?: ResultMeta;
  year: number;
  months: AdbMonthlyDataItem[];
  accounting_basis_daily_avg_trend?: AdbAccountingBasisDailyAvgTrendItem[];
  ytd_avg_assets: number | null;
  ytd_avg_liabilities: number | null;
  ytd_asset_yield: number | null;
  ytd_liability_cost: number | null;
  ytd_nim: number | null;
  ytd_asset_rate_coverage_ratio?: number | null;
  ytd_liability_rate_coverage_ratio?: number | null;
  unit?: string;
};

/** `GET /api/analysis/adb/coverage` 只读诊断（快照 vs formal 日期覆盖） */
export type AdbCoverageTableBlock = {
  dates_count: number;
  dates: string[];
  error?: string;
};

export type AdbCoveragePayload = {
  start_date: string;
  end_date: string;
  calendar_days: number;
  snapshot_tables: Record<string, AdbCoverageTableBlock>;
  formal_tables: Record<string, AdbCoverageTableBlock>;
  snapshot_date_count: number;
  formal_date_count: number;
  missing_dates: string[];
  missing_count: number;
  coverage_pct: number;
};

/**
 * `GET /api/analysis/adb/insights` 深度分析（analytical，`formal_use_allowed=false`）。
 * 契约冻结于 docs/plans/2026-08-13-average-balance-deep-analysis-prd.md §5，
 * 字段与 backend/app/core_finance/adb_deep_analytics.py 输出逐字对应；
 * `| null` 表示上游明确不可用（对比期缺数/窗口过短/利率覆盖不足），渲染层必须显示 EM_DASH 或不可用原因，不得用 0 顶替。
 */
export type AdbInsightsWindowReason = "ok" | "no_data";

export type AdbInsightsWindow = {
  start_date: string;
  end_date: string;
  calendar_days_inclusive: number;
  /** 该窗口含有效余额的不重复观测日数 */
  coverage_days: number;
  available: boolean;
  /** 未知取值安全归一为 null（与 comparison 的 unavailable_reason 同一约定） */
  reason: AdbInsightsWindowReason | null;
};

export type AdbScaleContributionRow = {
  category: string;
  side: "asset" | "liability";
  /** 元；对比期缺该类时 prior_avg 为 null（delta 按 0 参与，但此处披露 null） */
  current_avg: number | null;
  prior_avg: number | null;
  delta: number;
  /** 占总变动 |delta_total| 的 %；总变动为 0 时为 null */
  contribution_pct: number | null;
};

export type AdbScaleSideTotals = {
  current_avg: number;
  prior_avg: number;
  delta: number;
  delta_pct: number | null;
};

export type AdbScaleAttribution = {
  side_totals: { assets: AdbScaleSideTotals; liabilities: AdbScaleSideTotals };
  /** 按 |delta| 降序，全量分类 */
  asset_contributions: AdbScaleContributionRow[];
  liability_contributions: AdbScaleContributionRow[];
};

export type AdbNimCategoryEffect = {
  category: string;
  /** 0–1 小数；该期无有利率余额时为 null */
  share_current: number | null;
  share_prior: number | null;
  /** 百分数（2.34 = 2.34%） */
  rate_current: number | null;
  rate_prior: number | null;
  rate_effect_bp: number;
  mix_effect_bp: number;
};

export type AdbNimSideAttribution = {
  /** 该侧加权利率变动（bp） */
  total_effect_bp: number;
  rate_effect_bp: number;
  mix_effect_bp: number;
  /** rate+mix 与总效应的差额，必须原样披露 */
  residual_bp: number;
  by_category: AdbNimCategoryEffect[];
};

export type AdbNimAttribution = {
  basis: "qoq";
  /** % */
  nim_current: number | null;
  nim_prior: number | null;
  nim_delta_bp: number | null;
  asset_side: AdbNimSideAttribution;
  liability_side: AdbNimSideAttribution;
};

/** `nim_attribution` 为 null 时的原因；未知取值安全归一为 null */
export type AdbNimUnavailableReason =
  | "rate_unavailable"
  | "comparison_unavailable"
  | "current_unavailable"
  | "insufficient_window";

export type AdbVolatilitySeries = {
  mean: number;
  /** 样本标准差（n−1） */
  std: number;
  /** std/mean；mean=0 时为 null */
  cv: number | null;
  min: { date: string; value: number };
  max: { date: string; value: number };
  max_daily_change: { date: string; delta: number; pct: number | null } | null;
};

export type AdbAnomalyItem = {
  date: string;
  side: "asset" | "liability";
  value: number;
  delta: number;
  zscore: number;
  direction: "up" | "down";
};

export type AdbMonthEndEffect = {
  uplift_pct: number | null;
  months_observed: number;
  flagged: boolean;
};

export type AdbVolatilityBlock = {
  /** 观测日 <2 → null */
  assets: AdbVolatilitySeries | null;
  liabilities: AdbVolatilitySeries | null;
  anomaly_detection_available: boolean;
  anomalies: AdbAnomalyItem[];
  month_end_effect: { assets: AdbMonthEndEffect; liabilities: AdbMonthEndEffect } | null;
};

export type AdbConcentrationMover = {
  category: string;
  share_start_pct: number;
  share_end_pct: number;
  delta_pp: number;
};

export type AdbConcentrationSide = {
  start_observation_date: string;
  end_observation_date: string;
  /** 0–1，4 位小数 */
  hhi_start: number;
  hhi_end: number;
  top3_share_start: number;
  top3_share_end: number;
  top5_share_start: number;
  top5_share_end: number;
  /** 按 |Δ| 降序，至多 8 条 */
  movers: AdbConcentrationMover[];
};

export type AdbConcentrationBlock = {
  assets: AdbConcentrationSide | null;
  liabilities: AdbConcentrationSide | null;
  /** 首末观测日相同（只有 1 个观测日）→ "single_observation" */
  reason: string | null;
};

export type AdbInsightSeverity = "info" | "notice" | "warning";

export type AdbInsightDimension = "scale" | "nim" | "volatility" | "concentration" | "quality";

export type AdbInsightItem = {
  id: string;
  severity: AdbInsightSeverity;
  dimension: AdbInsightDimension;
  title: string;
  detail: string;
  evidence: Record<string, unknown>;
};

export type AdbInsightsPayload = {
  start_date: string;
  end_date: string;
  calendar_days_inclusive: number;
  /** D<=1 时 true，此时以下分析块全为 null */
  insufficient_window: boolean;
  windows: { current: AdbInsightsWindow; qoq: AdbInsightsWindow; yoy: AdbInsightsWindow };
  scale_attribution: { qoq: AdbScaleAttribution | null; yoy: AdbScaleAttribution | null };
  nim_attribution: AdbNimAttribution | null;
  nim_attribution_unavailable_reason: AdbNimUnavailableReason | null;
  volatility: AdbVolatilityBlock | null;
  concentration: AdbConcentrationBlock | null;
  /** 永不为 null，可为空数组 */
  insights: AdbInsightItem[];
};

export type AdbInsightsResponse = AdbInsightsPayload & { result_meta?: ResultMeta };
