/** Home dashboard / executive overview UI payloads (`/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview`). */
import type { Numeric } from "./core";

/** `/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview`, `/ui/home/alerts` payloads. */
export type ExecutiveMetric = {
  id: string;
  label: string;
  caliber_label?: string | null;
  value: Numeric;
  delta: Numeric;
  tone: "positive" | "neutral" | "warning" | "negative";
  detail: string;
  /** 后端契约字段；旧 mock 可能缺省，由 adapter 归一为 null */
  history?: number[] | null;
};

export type OverviewPayload = {
  title: string;
  metrics: ExecutiveMetric[];
};

export type SummaryPoint = {
  id: string;
  label: string;
  tone: "positive" | "neutral" | "warning";
  text: string;
};

export type SummaryPayload = {
  title: string;
  narrative: string;
  points: SummaryPoint[];
};

export type AttributionSegment = {
  id: string;
  label: string;
  amount: Numeric;
  tone: "positive" | "neutral" | "negative";
};

export type PnlAttributionPayload = {
  title: string;
  total: Numeric;
  segments: AttributionSegment[];
};

export type VerdictReason = {
  label: string;
  value: string;
  detail: string;
  tone: "positive" | "neutral" | "warning" | "negative";
};

export type VerdictSuggestion = { text: string; link: string | null };

export type VerdictPayload = {
  conclusion: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  reasons: VerdictReason[];
  suggestions: VerdictSuggestion[];
};

/** 与 /product-category-pnl「汇总视图」（ytd）页脚口径一致的首屏摘要（后端算、前端只展示）。 */
export type ProductCategoryYtdHeadlinePayload = {
  view: "ytd";
  summary_pnl: Numeric;
  summary_pnl_detail: string;
  operating_income: Numeric;
  operating_income_detail: string;
  intermediate_business_income: Numeric;
  intermediate_business_income_detail: string;
};

/** 与 /product-category-pnl「月度视图」（monthly）页脚口径一致的首屏摘要（后端算、前端只展示）。 */
export type ProductCategoryMonthlyHeadlinePayload = {
  view: "monthly";
  monthly_income: Numeric;
  monthly_income_detail: string;
};

export type HomeSnapshotPayload = {
  report_date: string;
  mode: "strict" | "partial";
  source_surface: "executive_analytical";
  overview: OverviewPayload;
  attribution: PnlAttributionPayload;
  domains_missing: string[];
  domains_effective_date: Record<string, string>;
  verdict?: VerdictPayload | null;
  product_category_ytd?: ProductCategoryYtdHeadlinePayload | null;
  product_category_monthly?: ProductCategoryMonthlyHeadlinePayload | null;
};

export type HomeResearchReportItem = {
  id: string;
  title: string;
  category: string;
  published_at: string;
  link: string | null;
  source: string;
  institution?: string | null;
  source_status: "ready" | "empty" | "stale";
  summary?: string | null;
};

export type HomeResearchReportsPayload = {
  report_date: string;
  source_status: "ready" | "empty" | "stale";
  items: HomeResearchReportItem[];
  warnings: string[];
};

export type HomeIncomeTrendPointSourceStatus = "ready" | "partial";

export type HomeIncomeTrendSourceStatus = HomeIncomeTrendPointSourceStatus | "empty";

export type HomeIncomeTrendPoint = {
  date: string;
  portfolio_pnl: Numeric;
  benchmark_pnl: Numeric;
  excess_pnl: Numeric;
  basis: "product_category_pnl_monthly";
  source_status: HomeIncomeTrendPointSourceStatus;
};

export type HomeIncomeTrendPayload = {
  report_date: string;
  window: number;
  source_status: HomeIncomeTrendSourceStatus;
  points: HomeIncomeTrendPoint[];
  missing_components: string[];
  warnings: string[];
};

export type HomeMacroSourceStatus = "ready" | "partial" | "stale" | "fallback" | "source_pending" | "error";

export type HomeMacroDisplayUnit = "index" | "pct" | "persons";

export type HomeMacroChangeUnit = "index_point" | "pct_point" | "persons" | "bp";

export type HomeMacroDirection = "up" | "down" | "flat" | "unavailable";

export type HomeMacroReleaseContextMetric = {
  metric_key: string;
  label: string;
  actual_value: number | null;
  previous_value: number | null;
  change_value: number | null;
  display_unit: HomeMacroDisplayUnit;
  change_unit: HomeMacroChangeUnit;
  precision: number;
  direction: HomeMacroDirection;
};

export type HomeMacroReleaseContextHistoryItem = {
  indicator_key: string;
  title: string;
  region: "CN" | "US";
  category: "activity" | "inflation" | "growth" | "employment" | "monetary_policy";
  importance: "high" | "medium" | "low";
  observation_date: string | null;
  previous_observation_date: string | null;
  reference_period: string | null;
  previous_reference_period: string | null;
  release_date: string | null;
  source_status: HomeMacroSourceStatus;
  source_name: string | null;
  metrics: HomeMacroReleaseContextMetric[];
  notes: string[];
};

export type HomeMacroReleaseContextCoverage = {
  configured_count: number;
  ready_count: number;
  partial_count: number;
  stale_count: number;
  fallback_count: number;
  source_pending_count: number;
  error_count: number;
};

export type HomeMacroReleaseContextPayload = {
  window_start_date: string;
  window_end_date: string;
  history_items: HomeMacroReleaseContextHistoryItem[];
  coverage: HomeMacroReleaseContextCoverage;
  warnings: string[];
};

export type GetHomeMacroReleaseContextOptions = {
  startDate: string;
  endDate: string;
  historyLimit?: number;
};

export type GetHomeSnapshotOptions = {
  reportDate?: string;
  allowPartial?: boolean;
};

export type FormalPnlRefreshPayload = {
  status: string;
  run_id?: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  report_date?: string;
  source_version?: string;
  vendor_version?: string;
  rule_version?: string;
  lock?: string;
  formal_fi_rows?: number;
  nonstd_bridge_rows?: number;
  detail?: string | null;
  error_message?: string | null;
};
