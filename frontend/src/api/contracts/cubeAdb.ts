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
  /** 正式表中实际覆盖的不重复日期数（可能 < num_days）；未覆盖日由 sample_fill 补全 */
  coverage_days?: number;
  /** 是否触发了 sample_fill（coverage < calendar 时自动放大） */
  sample_filled?: boolean;
  /** sample_fill 补全方法标识 */
  sample_fill_method?: string;
  simulated: boolean;
  total_spot_assets: number;
  total_avg_assets: number;
  total_spot_liabilities: number;
  total_avg_liabilities: number;
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

export type AdbMonthlyDataItem = {
  month: string;
  month_label: string;
  num_days: number;
  avg_assets: number | null;
  avg_liabilities: number | null;
  asset_yield: number | null;
  liability_cost: number | null;
  net_interest_margin: number | null;
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
