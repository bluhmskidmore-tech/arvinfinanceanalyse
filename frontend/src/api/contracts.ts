/** Shared API surface: envelope, health, and cross-cutting enums. */
export type ApiBasis = "formal" | "scenario" | "analytical" | "mock";
export type ApiQuality = "ok" | "warning" | "error" | "stale";

export type HealthCheckStatus = {
  ok: boolean;
  detail: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  checks?: Record<string, HealthCheckStatus>;
};

export type ResultMeta = {
  trace_id: string;
  basis: ApiBasis;
  result_kind: string;
  formal_use_allowed: boolean;
  source_version: string;
  vendor_version: string;
  rule_version: string;
  cache_version: string;
  quality_flag: ApiQuality;
  scenario_flag: boolean;
  generated_at: string;
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
};

/** `/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview`, `/ui/home/alerts` payloads. */
export type ExecutiveMetric = {
  id: string;
  label: string;
  value: string;
  delta: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  detail: string;
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
  amount: number;
  display_amount: string;
  tone: "positive" | "neutral" | "negative";
};

export type PnlAttributionPayload = {
  title: string;
  total: string;
  segments: AttributionSegment[];
};

export type FormalPnlDisabledResponse = {
  enabled: false;
  phase: "phase1";
  detail: string;
};

export type RiskSignal = {
  id: string;
  label: string;
  value: string;
  status: "stable" | "watch" | "warning";
  detail: string;
};

export type RiskOverviewPayload = {
  title: string;
  signals: RiskSignal[];
};

export type ContributionRow = {
  id: string;
  name: string;
  owner: string;
  contribution: string;
  completion: number;
  status: string;
};

export type ContributionPayload = {
  title: string;
  rows: ContributionRow[];
};

export type AlertItem = {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  occurred_at: string;
  detail: string;
};

export type AlertsPayload = {
  title: string;
  items: AlertItem[];
};

export type PlaceholderSnapshot = {
  title: string;
  summary: string;
  highlights: string[];
};

/**
 * Source preview (`/ui/preview/source-foundation`) and product-category P&L
 * (`/ui/pnl/product-category*`) contract shapes.
 */
export type SourcePreviewSummary = {
  ingest_batch_id?: string | null;
  batch_created_at?: string | null;
  source_family: string;
  report_date: string | null;
  report_start_date?: string | null;
  report_end_date?: string | null;
  report_granularity?: string | null;
  source_file: string;
  total_rows: number;
  manual_review_count: number;
  source_version: string;
  rule_version: string;
  group_counts: Record<string, number>;
  preview_mode?: string;
};

export type SourcePreviewPayload = {
  sources: SourcePreviewSummary[];
};

export type SourcePreviewHistoryPayload = {
  limit: number;
  offset: number;
  total_rows: number;
  rows: SourcePreviewSummary[];
};

/**
 * Backend source-preview rows are family-dependent dynamic dictionaries from DuckDB `select *`.
 * Frontend callers should treat them as records and only read known keys defensively.
 */
export type SourcePreviewRow = Record<string, unknown>;

export type SourcePreviewColumn = {
  key: string;
  label: string;
  type: "string" | "number" | "boolean";
};

export type SourcePreviewRowsPayload = {
  source_family: string;
  ingest_batch_id?: string | null;
  limit: number;
  offset: number;
  total_rows: number;
  columns: SourcePreviewColumn[];
  rows: SourcePreviewRow[];
};

export type SourcePreviewTraceRow = Record<string, unknown>;

export type SourcePreviewTracesPayload = {
  source_family: string;
  ingest_batch_id?: string | null;
  limit: number;
  offset: number;
  total_rows: number;
  columns: SourcePreviewColumn[];
  rows: SourcePreviewTraceRow[];
};

export type MacroVendorSeries = {
  series_id: string;
  series_name: string;
  vendor_name: string;
  vendor_version: string;
  frequency: string;
  unit: string;
};

export type MacroVendorPayload = {
  read_target: "duckdb";
  series: MacroVendorSeries[];
};

export type ChoiceMacroLatestPoint = {
  series_id: string;
  series_name: string;
  trade_date: string;
  value_numeric: number;
  unit: string;
  source_version: string;
  vendor_version: string;
};

export type ChoiceMacroLatestPayload = {
  read_target: "duckdb";
  series: ChoiceMacroLatestPoint[];
};

export type ChoiceNewsEvent = {
  event_key: string;
  received_at: string;
  group_id: string;
  content_type: string;
  serial_id: number;
  request_id: number;
  error_code: number;
  error_msg: string;
  topic_code: string;
  item_index: number;
  payload_text: string | null;
  payload_json: string | null;
};

export type ChoiceNewsEventsPayload = {
  total_rows: number;
  limit: number;
  offset: number;
  events: ChoiceNewsEvent[];
};

export type DecimalLike = string | number;

export type ProductCategoryPnlRow = {
  category_id: string;
  category_name: string;
  side: string;
  level: number;
  view: string;
  report_date: string;
  baseline_ftp_rate_pct: DecimalLike;
  cnx_scale: DecimalLike;
  cny_scale: DecimalLike;
  foreign_scale: DecimalLike;
  cnx_cash: DecimalLike;
  cny_cash: DecimalLike;
  foreign_cash: DecimalLike;
  cny_ftp: DecimalLike;
  foreign_ftp: DecimalLike;
  cny_net: DecimalLike;
  foreign_net: DecimalLike;
  business_net_income: DecimalLike;
  weighted_yield: DecimalLike | null;
  is_total: boolean;
  children: string[];
  scenario_rate_pct?: DecimalLike | null;
};

export type ProductCategoryDatesPayload = {
  report_dates: string[];
};

export type ProductCategoryPnlPayload = {
  report_date: string;
  view: string;
  available_views: string[];
  scenario_rate_pct: DecimalLike | null;
  rows: ProductCategoryPnlRow[];
  asset_total: ProductCategoryPnlRow;
  liability_total: ProductCategoryPnlRow;
  grand_total: ProductCategoryPnlRow;
};

export type ProductCategoryRefreshPayload = {
  status: string;
  run_id: string;
  job_name: string;
  trigger_mode: string;
  cache_key?: string;
  month_count?: number;
  report_dates?: string[];
  rule_version?: string;
  source_version?: string;
  lock?: string;
  detail?: string | null;
};

export type ProductCategoryManualAdjustmentRequest = {
  report_date: string;
  operator: "ADD" | "DELTA" | "OVERRIDE";
  approval_status: "approved" | "pending" | "rejected";
  account_code: string;
  currency: "CNX" | "CNY";
  account_name?: string;
  beginning_balance?: string | null;
  ending_balance?: string | null;
  monthly_pnl?: string | null;
  daily_avg_balance?: string | null;
  annual_avg_balance?: string | null;
};

export type ProductCategoryManualAdjustmentPayload = {
  adjustment_id: string;
  event_type: string;
  created_at: string;
  stream: string;
  report_date: string;
  operator: string;
  approval_status: string;
  account_code: string;
  currency: string;
  account_name: string;
  beginning_balance?: string | null;
  ending_balance?: string | null;
  monthly_pnl?: string | null;
  daily_avg_balance?: string | null;
  annual_avg_balance?: string | null;
};

export type ProductCategoryManualAdjustmentListPayload = {
  report_date: string;
  adjustment_count: number;
  adjustment_limit: number;
  adjustment_offset: number;
  event_total: number;
  event_limit: number;
  event_offset: number;
  adjustments: ProductCategoryManualAdjustmentPayload[];
  events: ProductCategoryManualAdjustmentPayload[];
};

export type ProductCategoryCurrentSortField =
  | "created_at"
  | "adjustment_id"
  | "approval_status"
  | "account_code";

export type ProductCategoryEventSortField =
  | "created_at"
  | "adjustment_id"
  | "event_type"
  | "approval_status"
  | "account_code";

export type ProductCategorySortDirection = "asc" | "desc";

export type ProductCategoryManualAdjustmentQuery = {
  adjustmentId?: string;
  adjustmentIdExact?: boolean;
  accountCode?: string;
  approvalStatus?: string;
  eventType?: string;
  currentSortField?: ProductCategoryCurrentSortField;
  currentSortDir?: ProductCategorySortDirection;
  eventSortField?: ProductCategoryEventSortField;
  eventSortDir?: ProductCategorySortDirection;
  createdAtFrom?: string;
  createdAtTo?: string;
  adjustmentLimit?: number;
  adjustmentOffset?: number;
  limit?: number;
  offset?: number;
};

export type ProductCategoryManualAdjustmentExportPayload = {
  filename: string;
  content: string;
};

/** Agent / multi-batch tooling contracts (separate from UI envelope-only pages). */
export type AgentQueryRequest = {
  question: string;
  basis: "formal" | "scenario" | "analytical";
  filters: Record<string, unknown>;
  position_scope: string;
  currency_basis: string;
  context: Record<string, unknown>;
};

export type AgentDrill = {
  dimension: string;
  label: string;
};

export type AgentCard = {
  type: string;
  title: string;
  value?: string;
  data?: Record<string, unknown> | Array<Record<string, unknown>>;
  spec?: Record<string, unknown>;
};

export type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  quality_flag: ApiQuality;
};

export type AgentResultMeta = ResultMeta & {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  next_drill: AgentDrill[];
};

export type AgentEnvelope = {
  answer: string;
  cards: AgentCard[];
  evidence: AgentEvidence;
  result_meta: AgentResultMeta;
  next_drill: AgentDrill[];
};

export type AgentDisabledResponse = {
  enabled: false;
  phase: "phase1";
  detail: string;
};
