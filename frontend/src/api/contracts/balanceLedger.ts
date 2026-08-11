/** Balance analysis, QDB GL monthly analysis, and general-ledger PnL (`Ledger*`) contracts. */
import type { ResultMeta, ResultNextDrill } from "./core";
import type { DecimalLike } from "./pnl";

export type BalanceMovementBucket = "AC" | "OCI" | "TPL";

export type BalanceMovementReconciliationStatus =
  | "matched"
  | "mismatch"
  | "gl_only"
  | "zqtz_only";

export type BalanceMovementRow = {
  report_date: string;
  report_month: string;
  currency_basis: string;
  sort_order: number;
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  previous_balance_pct: DecimalLike | null;
  current_balance_pct: DecimalLike | null;
  balance_change: DecimalLike;
  change_pct: DecimalLike | null;
  contribution_pct: DecimalLike | null;
  zqtz_amount: DecimalLike;
  gl_amount: DecimalLike;
  reconciliation_diff: DecimalLike;
  reconciliation_status: BalanceMovementReconciliationStatus;
  source_version: string;
  rule_version: string;
};

export type BalanceMovementSummary = {
  previous_balance_total: DecimalLike;
  current_balance_total: DecimalLike;
  balance_change_total: DecimalLike;
  zqtz_amount_total: DecimalLike;
  reconciliation_diff_total: DecimalLike;
  matched_bucket_count: number;
  bucket_count: number;
};

export type BalanceMovementTrendMonth = {
  report_date: string;
  report_month: string;
  current_balance_total: DecimalLike;
  balance_change_total: DecimalLike;
  rows: BalanceMovementRow[];
};

export type BalanceBusinessMovementRow = {
  report_date: string;
  report_month: string;
  currency_basis: string;
  side: "asset" | "liability";
  sort_order: number;
  row_key: string;
  row_label: string;
  current_balance: DecimalLike;
  source_kind: "ledger" | "zqtz";
  source_note: string;
  source_version: string;
  rule_version: string;
};

export type BalanceBusinessMovementTrendMonth = {
  report_date: string;
  report_month: string;
  asset_balance_total: DecimalLike;
  liability_balance_total: DecimalLike;
  net_balance_total: DecimalLike;
  rows: BalanceBusinessMovementRow[];
};

export type BalanceZqtzCalibrationItem = {
  row_key: string;
  row_label: string;
  system_amount: DecimalLike;
  reference_amount: DecimalLike;
  diff_amount: DecimalLike;
  status: "matched" | "watch";
  note: string;
};

export type BalanceZqtzCalibrationAnalysis = {
  source_file: string;
  conclusion: string;
  root_cause: string;
  remediation: string;
  items: BalanceZqtzCalibrationItem[];
  residual_risks: string[];
};

export type BalanceStructureMigrationBucket = {
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_delta: DecimalLike;
  previous_share_pct: DecimalLike | null;
  current_share_pct: DecimalLike | null;
  share_delta_pp: DecimalLike | null;
};

export type BalanceStructureMigrationPair = {
  previous_report_date: string;
  current_report_date: string;
  previous_report_month: string;
  current_report_month: string;
  total_balance_delta: DecimalLike;
  dominant_share_increase_bucket: BalanceMovementBucket | null;
  fvtpl_volatility_signal: string;
  oci_valuation_signal: string;
  buckets: BalanceStructureMigrationBucket[];
};

export type BalanceStructureMigrationAnalysis = {
  summary: string;
  caveat: string;
  pairs: BalanceStructureMigrationPair[];
};

export type BalanceDifferenceAttributionComponent = {
  component_key: string;
  component_label: string;
  amount: DecimalLike;
  source_kind: "ledger" | "zqtz" | "derived" | "residual";
  evidence_note: string;
  is_residual: boolean;
  is_supported: boolean;
};

export type BalanceDifferenceAttributionWaterfall = {
  reference_label: string;
  reference_total: DecimalLike;
  target_label: string;
  target_total: DecimalLike;
  net_difference: DecimalLike;
  components: BalanceDifferenceAttributionComponent[];
  closing_check: DecimalLike;
  caveat: string;
};

export type BalanceMovementDrilldownStatus =
  | "supported"
  | "unsupported_missing_columns"
  | "unsupported_low_coverage"
  | "no_data";

export type BalanceMovementDrilldownMeta = {
  source_tables: string[];
  source_scope: string;
  report_date: string;
  prior_report_date: string | null;
  currency_basis: string;
  zqtz_currency_basis?: string | null;
  unit: "yuan";
  eligible_total: DecimalLike;
  covered_total: DecimalLike | null;
  unknown_total: DecimalLike | null;
  coverage_pct: DecimalLike | null;
  status: BalanceMovementDrilldownStatus;
  caveat: string;
};

export type BalanceBasisMovementComponent = {
  component_key: string;
  component_label: string;
  account_code_pattern: string;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_change: DecimalLike;
  contribution_pct: DecimalLike | null;
  source_note: string;
  is_supported: boolean;
};

export type BalanceBasisMovementBucket = {
  basis_bucket: BalanceMovementBucket;
  previous_balance: DecimalLike;
  current_balance: DecimalLike;
  balance_change: DecimalLike;
  rows: BalanceBasisMovementComponent[];
  residual_amount: DecimalLike;
  closing_check: DecimalLike;
};

export type BalanceBasisMovementDecomposition = {
  meta: BalanceMovementDrilldownMeta;
  buckets: BalanceBasisMovementBucket[];
};

export type BalanceZqtzMaturityBucketKey =
  | "overdue_or_matured"
  | "<=30d"
  | "31-90d"
  | "91d-1y"
  | "1-3y"
  | "3-5y"
  | ">5y"
  | "unknown";

export type BalanceZqtzMaturityBucket = {
  maturity_bucket: BalanceZqtzMaturityBucketKey;
  bucket_label: string;
  current_amount: DecimalLike;
  prior_amount: DecimalLike;
  delta_amount: DecimalLike;
  item_count: number;
  share_pct: DecimalLike | null;
};

export type BalanceZqtzMaturityStructure = {
  meta: BalanceMovementDrilldownMeta;
  buckets: BalanceZqtzMaturityBucket[];
};

export type BalanceZqtzConcentrationDimensionKey =
  | "issuer_name"
  | "rating"
  | "industry_name";

export type BalanceZqtzConcentrationItem = {
  rank: number;
  dimension_value: string;
  current_amount: DecimalLike;
  prior_amount: DecimalLike | null;
  delta_amount: DecimalLike | null;
  share_pct: DecimalLike | null;
  item_count: number;
  item_kind: "top" | "other" | "unknown";
};

export type BalanceZqtzConcentrationDimension = {
  dimension: BalanceZqtzConcentrationDimensionKey;
  status: BalanceMovementDrilldownStatus;
  eligible_total: DecimalLike;
  covered_total: DecimalLike;
  unknown_total: DecimalLike;
  coverage_pct: DecimalLike | null;
  prior_coverage_pct: DecimalLike | null;
  top_n: number;
  hhi: DecimalLike | null;
  top5_share_pct: DecimalLike | null;
  items: BalanceZqtzConcentrationItem[];
  caveat: string;
};

export type BalanceZqtzConcentrationAnalysis = {
  meta: BalanceMovementDrilldownMeta;
  dimensions: BalanceZqtzConcentrationDimension[];
};

/** 余额类页面可选返回的口径说明快照（后端未部署时字段可缺失）。 */
export type BalancePageCalibration = {
  position_scope: string;
  currency_basis: string;
  source_families: string[];
  tyw_amount_semantics?: string;
  data_basis: string;
  calibration_note: string;
};

export type BalanceMovementPayload = {
  report_date: string;
  currency_basis: string;
  rows: BalanceMovementRow[];
  summary: BalanceMovementSummary;
  trend_months: BalanceMovementTrendMonth[];
  business_trend_months: BalanceBusinessMovementTrendMonth[];
  zqtz_calibration_analysis: BalanceZqtzCalibrationAnalysis | null;
  structure_migration_analysis: BalanceStructureMigrationAnalysis | null;
  difference_attribution_waterfall: BalanceDifferenceAttributionWaterfall | null;
  basis_movement_decomposition?: BalanceBasisMovementDecomposition | null;
  zqtz_maturity_structure?: BalanceZqtzMaturityStructure | null;
  zqtz_concentration_analysis?: BalanceZqtzConcentrationAnalysis | null;
  accounting_controls: string[];
  excluded_controls: string[];
  calibration?: BalancePageCalibration | null;
};

export type BalanceMovementDatesPayload = {
  report_dates: string[];
  currency_basis: string;
  latest_read_model_report_date?: string | null;
  latest_upstream_control_report_date?: string | null;
  freshness_status?:
    | "fresh"
    | "read_model_lagging"
    | "read_model_empty"
    | "upstream_empty";
};

export type BalanceMovementRefreshPayload = {
  status: string;
  cache_key: string;
  report_date: string;
  currency_basis: string;
  run_id?: string | null;
  job_name?: string | null;
  trigger_mode?: string | null;
  row_count?: number | null;
  source_version?: string | null;
  rule_version: string;
  product_category_refreshed_dates?: string[];
  formal_balance_refreshed_dates?: string[];
  movement_refreshed_dates?: string[];
};

export type BalanceAnalysisDatesPayload = {
  report_dates: string[];
};

export type BalancePositionScope = "asset" | "liability" | "all";

export type BalanceCurrencyBasis = "native" | "CNY";

export type BalanceAnalysisDetailRow = {
  source_family: "zqtz" | "tyw";
  report_date: string;
  row_key: string;
  display_name: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  invest_type_std: string;
  accounting_basis: string;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
  is_issuance_like: boolean | null;
};

export type BalanceAnalysisSummaryRow = {
  source_family: "zqtz" | "tyw" | "combined";
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisMetricDefinition = {
  key: string;
  label: string;
  source_field: string;
  raw_unit: "yuan";
  display_unit: "yi_yuan";
  basis: "formal";
  source_surface: "formal_balance";
  applies_to: Array<"overview" | "summary" | "detail">;
  description: string;
};

export type BalanceAnalysisOverviewPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  detail_row_count: number;
  summary_row_count: number;
  /** 当前 filters 下 ZQTZ+TYW 合计；`position_scope === "all"` 时为资产+负债加总。 */
  total_market_value_amount: DecimalLike;
  total_amortized_cost_amount: DecimalLike;
  total_accrued_interest_amount: DecimalLike;
  /** 正式事实表 `position_scope = asset` 侧加总（元）。`position_scope` 为单端时非零的一端为有效值。 */
  asset_total_market_value_amount: DecimalLike;
  liability_total_market_value_amount: DecimalLike;
  asset_total_amortized_cost_amount: DecimalLike;
  liability_total_amortized_cost_amount: DecimalLike;
  asset_total_accrued_interest_amount: DecimalLike;
  liability_total_accrued_interest_amount: DecimalLike;
  metric_definitions?: BalanceAnalysisMetricDefinition[];
  calibration?: BalancePageCalibration | null;
};

export type BalanceAnalysisTableRow = {
  row_key: string;
  source_family: "zqtz" | "tyw";
  display_name: string;
  owner_name: string;
  category_name: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  invest_type_std: string;
  accounting_basis: string;
  detail_row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisSummaryTablePayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  limit: number;
  offset: number;
  total_rows: number;
  rows: BalanceAnalysisTableRow[];
};

export type BalanceAnalysisPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  details: BalanceAnalysisDetailRow[];
  summary: BalanceAnalysisSummaryRow[];
};

export type BalanceAnalysisBasisBreakdownRow = {
  source_family: "zqtz" | "tyw";
  invest_type_std: string;
  accounting_basis: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  detail_row_count: number;
  market_value_amount: DecimalLike;
  amortized_cost_amount: DecimalLike;
  accrued_interest_amount: DecimalLike;
};

export type BalanceAnalysisBasisBreakdownPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  rows: BalanceAnalysisBasisBreakdownRow[];
};

export type BalanceAnalysisAdvancedAttributionBundlePayload = {
  report_date: string;
  mode: "analytical" | "scenario";
  scenario_name: string | null;
  scenario_inputs: Record<string, number>;
  upstream_summaries: Record<string, Record<string, string | string[]>>;
  status: "not_ready" | "partial";
  summary?: Record<string, string>;
  available_components?: string[];
  missing_inputs: string[];
  blocked_components: string[];
  warnings: string[];
};

export type BalanceAnalysisWorkbookCard = {
  key: string;
  label: string;
  value: DecimalLike;
  note?: string | null;
};

export type BalanceAnalysisWorkbookColumn = {
  key: string;
  label: string;
};

export type BalanceAnalysisWorkbookSectionKind =
  | "table"
  | "decision_items"
  | "event_calendar"
  | "risk_alerts";

export type BalanceAnalysisSeverity = "low" | "medium" | "high";

export type BalanceAnalysisDecisionStatus = "pending" | "confirmed" | "dismissed";

export type BalanceAnalysisWorkbookTable = {
  key: string;
  title: string;
  section_kind: "table";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: Array<Record<string, unknown>>;
};

export type BalanceAnalysisDecisionItemRow = {
  title: string;
  action_label: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
};

export type BalanceAnalysisDecisionStatusRecord = {
  decision_key: string;
  status: BalanceAnalysisDecisionStatus;
  updated_at: string | null;
  updated_by: string | null;
  comment?: string | null;
};

export type BalanceAnalysisCurrentUserPayload = {
  user_id: string;
  role: string;
  identity_source: "header" | "env" | "system" | "fallback";
  can_write_decision_status: boolean | null;
};

export type BalanceAnalysisDecisionItemStatusRow = {
  decision_key: string;
  title: string;
  action_label: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
  latest_status: BalanceAnalysisDecisionStatusRecord;
};

export type BalanceAnalysisDecisionItemsSection = {
  key: "decision_items";
  title: string;
  section_kind: "decision_items";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisDecisionItemRow[];
};

export type BalanceAnalysisEventCalendarRow = {
  event_date: string;
  event_type: string;
  title: string;
  source: string;
  impact_hint: string;
  source_section: string;
};

export type BalanceAnalysisEventCalendarSection = {
  key: "event_calendar";
  title: string;
  section_kind: "event_calendar";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisEventCalendarRow[];
};

export type BalanceAnalysisRiskAlertRow = {
  title: string;
  severity: BalanceAnalysisSeverity;
  reason: string;
  source_section: string;
  rule_id: string;
  rule_version: string;
};

export type BalanceAnalysisRiskAlertsSection = {
  key: "risk_alerts";
  title: string;
  section_kind: "risk_alerts";
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisRiskAlertRow[];
};

export type BalanceAnalysisWorkbookOperationalSection =
  | BalanceAnalysisDecisionItemsSection
  | BalanceAnalysisEventCalendarSection
  | BalanceAnalysisRiskAlertsSection;

export type BalanceAnalysisDecisionItemsPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  columns: BalanceAnalysisWorkbookColumn[];
  rows: BalanceAnalysisDecisionItemStatusRow[];
};

export type BalanceAnalysisWorkbookPayload = {
  report_date: string;
  position_scope: BalancePositionScope;
  currency_basis: BalanceCurrencyBasis;
  cards: BalanceAnalysisWorkbookCard[];
  tables: BalanceAnalysisWorkbookTable[];
  operational_sections: BalanceAnalysisWorkbookOperationalSection[];
};

export type BalanceAnalysisSummaryExportPayload = {
  filename: string;
  content: string;
};

export type BalanceAnalysisWorkbookExportPayload = {
  filename: string;
  content: Blob;
};

export type BalanceAnalysisRefreshPayload = {
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
  zqtz_rows?: number;
  tyw_rows?: number;
  detail?: string | null;
  error_message?: string | null;
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

export type QdbGlMonthlyAnalysisDatesPayload = {
  report_months: string[];
};

export type QdbGlMonthlyAnalysisSheet = {
  key: string;
  title: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
};

export type QdbGlMonthlyAnalysisWorkbookPayload = {
  report_month: string;
  sheets: QdbGlMonthlyAnalysisSheet[];
};

export type QdbGlMonthlyAnalysisScenarioPayload = QdbGlMonthlyAnalysisWorkbookPayload & {
  scenario_name: string;
  applied_overrides: Record<string, unknown>;
};

export type QdbGlMonthlyAnalysisWorkbookExportPayload = {
  filename: string;
  content: Blob;
};

export type QdbGlMonthlyAnalysisManualAdjustmentRequest = {
  report_month: string;
  adjustment_class: "mapping_adjustment" | "analysis_adjustment";
  target: Record<string, unknown>;
  operator: "ADD" | "DELTA" | "OVERRIDE";
  value: string;
  approval_status: "approved" | "pending" | "rejected";
};

export type QdbGlMonthlyAnalysisManualAdjustmentPayload = {
  adjustment_id: string;
  event_type: string;
  created_at: string;
  stream: string;
  report_month: string;
  adjustment_class: "mapping_adjustment" | "analysis_adjustment";
  target: Record<string, unknown>;
  operator: string;
  value: string;
  approval_status: string;
};

export type QdbGlMonthlyAnalysisManualAdjustmentListPayload = {
  report_month: string;
  adjustment_count: number;
  adjustments: QdbGlMonthlyAnalysisManualAdjustmentPayload[];
  events: QdbGlMonthlyAnalysisManualAdjustmentPayload[];
};

export type QdbGlMonthlyAnalysisManualAdjustmentExportPayload = {
  filename: string;
  content: string;
};

export type LedgerMoneyValue = {
  yuan: string;
  yi: string;
  wan?: string;
};

export type LedgerPnlDatesPayload = {
  dates: string[];
};

export type LedgerPnlDataItem = {
  account_code: string;
  account_name: string;
  currency: string;
  beginning_balance: LedgerMoneyValue;
  ending_balance: LedgerMoneyValue;
  monthly_pnl: LedgerMoneyValue;
  daily_avg_balance: LedgerMoneyValue;
  days_in_period: number;
};

export type LedgerPnlDataPayload = {
  data_status?: "ready" | "no_data";
  report_date: string;
  items: LedgerPnlDataItem[];
  summary: {
    total_pnl_cnx: LedgerMoneyValue;
    total_pnl_cny: LedgerMoneyValue;
    total_pnl: LedgerMoneyValue;
    count: number;
  };
};

export type LedgerPnlSummaryByCurrency = {
  currency: string;
  total_pnl: LedgerMoneyValue;
};

export type LedgerPnlSummaryByAccount = {
  account_code: string;
  account_name: string;
  total_pnl: LedgerMoneyValue;
  count: number;
};

export type LedgerPnlSummaryPayload = {
  data_status?: "ready" | "no_data";
  report_date: string;
  source_version: string;
  ledger_total_assets: LedgerMoneyValue;
  ledger_total_liabilities: LedgerMoneyValue;
  ledger_net_assets: LedgerMoneyValue;
  ledger_monthly_pnl_core: LedgerMoneyValue;
  ledger_monthly_pnl_all: LedgerMoneyValue;
  by_currency: LedgerPnlSummaryByCurrency[];
  by_account: LedgerPnlSummaryByAccount[];
};

export type LedgerPnlAnalysisDirection = "positive" | "negative" | "flat" | "unavailable";

export type LedgerPnlAnalysisOtherEffect = "support" | "drag" | "neutral" | "unavailable";

export type LedgerPnlAnalysisAvailability = "ready" | "no_data";

export type LedgerPnlAnalysisBridgeComponent = {
  metric_key: "core_pnl" | "other_5_pnl";
  metric_name: string;
  amount: LedgerMoneyValue | null;
};

export type LedgerPnlAnalysisBasisMetricKey =
  | "assets"
  | "liabilities"
  | "net_assets"
  | "core_pnl"
  | "all_pnl"
  | "other_5_pnl";

export type LedgerPnlAnalysisBasisComparisonRow = {
  metric_key: LedgerPnlAnalysisBasisMetricKey;
  metric_name: string;
  cnx: LedgerMoneyValue | null;
  cny: LedgerMoneyValue | null;
  cnx_minus_cny: LedgerMoneyValue | null;
  availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  evidence_rows: {
    CNX: number;
    CNY: number;
  };
};

export type LedgerPnlAnalysisContributor = {
  rank: number;
  account_code: string;
  account_name: string;
  amount: LedgerMoneyValue;
  count: number;
};

export type LedgerPnlAnalysisPeriodStatus =
  | "available"
  | "no_previous_period"
  | "current_basis_no_data"
  | "previous_basis_no_data";

export type LedgerPnlAnalysisPeriodRow = {
  metric_key: "core_pnl" | "other_5_pnl" | "all_pnl";
  metric_name: string;
  current: LedgerMoneyValue;
  previous: LedgerMoneyValue;
  change: LedgerMoneyValue;
};

export type LedgerPnlAnalysisPayload = {
  report_date: string;
  source_version: string;
  currency_basis: "CNX" | "CNY";
  basis_availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  analysis_status: "ready" | "no_data";
  metric_status: "candidate";
  conclusion: {
    direction: LedgerPnlAnalysisDirection;
    other_effect: LedgerPnlAnalysisOtherEffect;
    core_pnl: LedgerMoneyValue | null;
    other_5_pnl: LedgerMoneyValue | null;
    all_pnl: LedgerMoneyValue | null;
  };
  pnl_bridge: {
    components: LedgerPnlAnalysisBridgeComponent[];
    total: LedgerMoneyValue | null;
    residual: LedgerMoneyValue | null;
  };
  basis_comparison: LedgerPnlAnalysisBasisComparisonRow[];
  contributors: {
    positive_total: LedgerMoneyValue | null;
    negative_total: LedgerMoneyValue | null;
    net_total: LedgerMoneyValue | null;
    top_positive: LedgerPnlAnalysisContributor[];
    top_negative: LedgerPnlAnalysisContributor[];
  };
  period_comparison: {
    status: LedgerPnlAnalysisPeriodStatus;
    previous_report_date: string | null;
    previous_source_version: string | null;
    rows: LedgerPnlAnalysisPeriodRow[];
  };
  calculation_basis: {
    core_pnl_prefixes: string[];
    all_pnl_prefixes: string[];
    other_5_pnl_formula: string;
    other_5_pnl_boundary: string;
    basis_difference_formula: string;
    basis_boundary: string;
    basis_availability_boundary: string;
    metric_boundary: string;
    previous_period_rule: string;
    [key: string]: string | string[] | undefined;
  };
};

export type LedgerPnlAccountDetailPeriodStatus =
  | "available"
  | "current_account_no_data"
  | "no_previous_period"
  | "previous_account_no_data";

export type LedgerPnlAccountDetailBasisSnapshot = {
  report_date: string;
  source_version: string;
  cnx: LedgerMoneyValue | null;
  cny: LedgerMoneyValue | null;
  cnx_minus_cny: LedgerMoneyValue | null;
  availability: {
    CNX: LedgerPnlAnalysisAvailability;
    CNY: LedgerPnlAnalysisAvailability;
  };
  evidence_rows: {
    CNX: number;
    CNY: number;
  };
};

export type LedgerPnlAccountDetailCanonicalEvidenceRow = {
  period: "current" | "previous";
  report_date: string;
  source_version: string;
  account_code: string;
  account_name: string;
  currency: "CNX" | "CNY";
  beginning_balance: LedgerMoneyValue;
  ending_balance: LedgerMoneyValue;
  monthly_pnl: LedgerMoneyValue;
  days_in_period: number;
};

export type LedgerPnlAccountDetailPayload = {
  report_date: string;
  source_version: string;
  currency_basis: "CNX" | "CNY";
  analysis_status: "ready" | "no_data";
  metric_status: "candidate";
  account: {
    account_code: string;
    account_name: string | null;
  };
  period_comparison: {
    status: LedgerPnlAccountDetailPeriodStatus;
    previous_report_date: string | null;
    previous_source_version: string | null;
    current_monthly_pnl: LedgerMoneyValue | null;
    previous_monthly_pnl: LedgerMoneyValue | null;
    change: LedgerMoneyValue | null;
    current_evidence_rows: number;
    previous_evidence_rows: number;
  };
  basis_comparison: {
    current: LedgerPnlAccountDetailBasisSnapshot;
    previous: LedgerPnlAccountDetailBasisSnapshot | null;
  };
  canonical_evidence_rows: LedgerPnlAccountDetailCanonicalEvidenceRow[];
  calculation_basis: {
    account_match: "exact";
    amount_field: "monthly_pnl";
    change_formula: "current_monthly_pnl - previous_monthly_pnl";
    basis_difference_formula: "CNX - CNY";
    basis_boundary: string;
    previous_period_rule: string;
    evidence_boundary: string;
    metric_boundary: string;
  };
};

export type LedgerPnlFormalIndicatorSourceStatus =
  | "formal_pending"
  | "candidate_qdb_aligned"
  | "needs_reconciliation";

export type LedgerPnlCandidateFinancialIndicatorCalculationStatus =
  | "ready"
  | "warning"
  | "error"
  | "no_data";

export type LedgerPnlCandidateFinancialIndicatorMetricStatus =
  | "ok"
  | "warning"
  | "manual_default"
  | "error";

export type LedgerPnlCandidateFinancialIndicatorSource = {
  source_kind: "ledger" | "daily";
  file_name: string;
  exists: boolean;
  sha256: string | null;
  locked_sha256: string | null;
  locked_hash_match: boolean | null;
  sheets: string[];
  periods: LedgerPnlCandidateFinancialIndicatorPeriod[];
};

export type LedgerPnlCandidateFinancialIndicatorPeriod = {
  evidence_id:
    | "ledger"
    | "daily_ytd"
    | "daily_month"
    | "microloan_ytd"
    | "microloan_month"
    | "microloan_ledger";
  start: string;
  end: string;
  source_cell: string;
};

export type LedgerPnlCandidateFinancialIndicatorAccountLineage = {
  lineage_type: "account";
  source: "main" | "microloan" | "ledger" | "microloan_ledger";
  basis: "point" | "ytd_average" | "month_average" | "cumulative" | null;
  level: "l1" | "l2" | "l3" | "full";
  code: string;
  weight: string;
  observed: boolean;
  raw_yuan: string;
  contribution_yi: string;
  evidence_refs: string[];
};

export type LedgerPnlCandidateFinancialIndicatorMetricLineage = {
  lineage_type: "metric";
  metric_id: string;
  weight: string;
  metric_value_yi: string | null;
  contribution_yi: string | null;
  dependency_status: LedgerPnlCandidateFinancialIndicatorMetricStatus;
};

export type LedgerPnlCandidateFinancialIndicatorManualLineage = {
  lineage_type: "manual";
  supplied: boolean;
  value_yi: string;
};

export type LedgerPnlCandidateFinancialIndicatorLineage =
  | LedgerPnlCandidateFinancialIndicatorAccountLineage
  | LedgerPnlCandidateFinancialIndicatorMetricLineage
  | LedgerPnlCandidateFinancialIndicatorManualLineage;

export type LedgerPnlCandidateFinancialIndicatorMetric = {
  metric_id: string;
  name: string;
  category: string;
  basis: "point" | "ytd_average" | "month_average" | "cumulative";
  unit: "亿元";
  value: string | null;
  status: LedgerPnlCandidateFinancialIndicatorMetricStatus;
  reasons: string[];
  lineage: LedgerPnlCandidateFinancialIndicatorLineage[];
};

export type LedgerPnlCandidateFinancialIndicatorValidation = {
  validation_id: string;
  severity: "warning" | "error";
  passed: boolean;
  message: string;
  delta_yi: string | null;
  sample: string[];
};

export type LedgerPnlCandidateFinancialIndicatorGap = {
  gap_id: string;
  severity: "info" | "warning" | "error";
  kind:
    | "source_missing"
    | "source_hash"
    | "source_parse"
    | "validation"
    | "missing_account"
    | "manual_input"
    | "calculation";
  title: string;
  detail: string;
  metric_ids: string[];
};

export type LedgerPnlCandidateFinancialIndicatorPromotionCheck = {
  check_id:
    | "rule_asset"
    | "source_evidence"
    | "validation_controls"
    | "manual_inputs"
    | "account_coverage"
    | "formal_contract";
  label: string;
  status: "passed" | "blocked" | "not_evaluated";
  blocking: boolean;
  summary: string;
  evidence_refs: string[];
  action: string;
};

export type LedgerPnlCandidatePromotionOwnerRequirement = {
  requirement_id: string;
  category:
    | "source_evidence"
    | "validation_control"
    | "manual_input"
    | "account_coverage"
    | "formal_contract"
    | "business_owner_approval";
  status: "awaiting_owner_input";
  submitted_value: null;
  evidence_refs: string[];
  required_evidence: string[];
  action: string;
};

export type LedgerPnlCandidatePromotionEvidencePack = {
  contract_version: "candidate-promotion-evidence-v1";
  evidence_pack_key: string;
  report_month: string;
  report_date: string;
  rule_version: "qdb-finance-2026-v1.0.0" | "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  source_version: string;
  source_alignment: "matched" | "mismatch" | "not_applicable" | "incomplete";
  candidate_idempotency_key: string;
  readiness_contract_version: "promotion-readiness-v1";
  readiness_evidence_key: string;
  metric_status: "candidate";
  formal_use_allowed: false;
  owner_approval_required: true;
  contains_metric_values: false;
  contains_formal_values: false;
  certification_effect: "none";
  blocking_count: number;
  check_total: 6;
  formal_contract_status: "missing_contract" | "contract_fixture" | "unavailable";
  formal_sample_id: string;
  formal_source_version: string;
  formal_release_gate_status: string | null;
  formal_metric_count: number;
  checks: LedgerPnlCandidateFinancialIndicatorPromotionCheck[];
  owner_requirement_count: number;
  owner_requirements: LedgerPnlCandidatePromotionOwnerRequirement[];
  outcome_status: "blocked" | "awaiting_owner_approval";
};

export type LedgerPnlCandidateFinancialIndicatorPromotionReadiness = {
  readiness_contract_version: "promotion-readiness-v1";
  readiness_evidence_key: string;
  status: "blocked" | "review_required";
  blocking_count: number;
  check_total: 6;
  candidate_idempotency_key: string;
  formal_contract_status: "missing_contract" | "contract_fixture" | "unavailable";
  formal_use_allowed: false;
  owner_approval_required: true;
  next_action: string;
  checks: LedgerPnlCandidateFinancialIndicatorPromotionCheck[];
  evidence_pack: LedgerPnlCandidatePromotionEvidencePack;
};

export type LedgerPnlCandidateSourceVersionImpact = {
  contract_version: "candidate-source-version-impact-v1";
  impact_asset_sha256: string;
  status: "numerically_unchanged" | "numeric_digest_mismatch" | "comparison_incomplete";
  comparison_basis: "canonical_decimal_value";
  report_month: string;
  reference_rule_version: "qdb-finance-2026-v1.0.0";
  current_rule_version: "qdb-finance-2026-v1.0.1";
  reference_result_sha256: string;
  reference_ledger_sha256: string;
  current_ledger_sha256: string;
  daily_sha256: string;
  metric_total: 186;
  compared_metric_count: number;
  reference_numeric_digest: string;
  current_numeric_digest: string;
  numeric_changed_count: number | null;
  serialization_only_count: number;
  serialization_only_metric_ids: string[];
  formal_use_allowed: false;
  certification_effect: "none";
};

export type LedgerPnlCandidateFinancialIndicatorsPayload = {
  report_month: string;
  report_date: string;
  currency: "CNX";
  basis: "ledger";
  metric_status: "candidate";
  formal_use_allowed: false;
  calculation_status: LedgerPnlCandidateFinancialIndicatorCalculationStatus;
  source_alignment: "matched" | "mismatch" | "not_applicable" | "incomplete";
  source_version: string;
  rule_version: "qdb-finance-2026-v1.0.0" | "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  idempotency_key: string;
  requested_metric_id: string | null;
  include_lineage: boolean;
  source_version_impact?: LedgerPnlCandidateSourceVersionImpact | null;
  promotion_readiness: LedgerPnlCandidateFinancialIndicatorPromotionReadiness;
  sources: LedgerPnlCandidateFinancialIndicatorSource[];
  summary: {
    metric_total: 186;
    metric_evaluated: number;
    metric_returned: number;
    ok_count: number;
    warning_count: number;
    manual_default_count: number;
    error_count: number;
    validation_total: 12;
    validation_evaluated: number;
    validation_passed: number;
    validation_warning_failed: number;
    validation_error_failed: number;
  };
  metrics: LedgerPnlCandidateFinancialIndicatorMetric[];
  validations: LedgerPnlCandidateFinancialIndicatorValidation[];
  gaps: LedgerPnlCandidateFinancialIndicatorGap[];
};

export type LedgerPnlCandidateFinancialIndicatorsFilters = {
  report_month: string;
  include_lineage: boolean;
  metric_id: string | null;
};

export type LedgerPnlCandidateFinancialIndicatorsResultMeta = Omit<
  ResultMeta,
  | "basis"
  | "result_kind"
  | "formal_use_allowed"
  | "cache_key"
  | "quality_flag"
  | "vendor_status"
  | "fallback_mode"
  | "requested_report_date"
  | "resolved_report_date"
  | "scenario_flag"
  | "as_of_date"
  | "date_basis"
  | "fallback_date"
  | "filters_applied"
  | "tables_used"
  | "evidence_rows"
  | "next_drill"
  | "source_surface"
> & {
  basis: "ledger";
  result_kind: "ledger_pnl.candidate_financial_indicators";
  formal_use_allowed: false;
  amount_currency_basis: "CNX";
  amount_currency_basis_note: string;
  cache_key: string;
  quality_flag: "ok" | "warning" | "error";
  vendor_status: "ok";
  fallback_mode: "none";
  requested_report_date: string;
  resolved_report_date: string;
  scenario_flag: false;
  as_of_date: string;
  date_basis: "report_month_end";
  fallback_date: null;
  filters_applied: LedgerPnlCandidateFinancialIndicatorsFilters;
  tables_used: string[];
  evidence_rows: number;
  next_drill: ResultNextDrill[];
  source_surface: null;
};

export type LedgerPnlCandidateFinancialIndicatorsEnvelope = {
  result_meta: LedgerPnlCandidateFinancialIndicatorsResultMeta;
  result: LedgerPnlCandidateFinancialIndicatorsPayload;
};

export type LedgerPnlCandidateFinancialIndicatorManualOverride = {
  value_yi: string;
  submitted_evidence_refs: string[];
};

export type LedgerPnlCandidateFinancialIndicatorRevalidationRequest = {
  base_candidate_idempotency_key: string;
  base_evidence_pack_key: string;
  manual_overrides: Record<string, LedgerPnlCandidateFinancialIndicatorManualOverride>;
};

export type LedgerPnlCandidateRequirementResolutionStatus =
  | "awaiting_owner_input"
  | "evidence_received"
  | "validation_failed"
  | "verified";

export type LedgerPnlCandidateRequirementResolutionItem = {
  requirement_id: string;
  status: LedgerPnlCandidateRequirementResolutionStatus;
  status_detail: string;
  submitted_evidence_refs: string[];
  validation_evidence_refs: string[];
};

export type LedgerPnlCandidateRequirementResolution = {
  contract_version: "candidate-promotion-resolution-v1";
  resolution_key: string;
  base_evidence_pack_key: string;
  result_evidence_pack_key: string;
  base_requirement_ids: string[];
  requirements: LedgerPnlCandidateRequirementResolutionItem[];
};

export type LedgerPnlCandidateFinancialIndicatorRevalidationReceipt = {
  contract_version: "candidate-financial-indicator-revalidation-v1";
  revalidation_effect: "none";
  persisted: false;
  formal_use_allowed: false;
  base_candidate_idempotency_key: string;
  base_evidence_pack_key: string;
  manual_override_count: number;
  requirement_resolution: LedgerPnlCandidateRequirementResolution;
  result: LedgerPnlCandidateFinancialIndicatorsEnvelope;
};

export type LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus =
  | "ok"
  | "warning"
  | "manual_default"
  | "error"
  | "missing";

export type LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod = {
  month: string;
  report_date: string;
  ledger_file_name: string;
  ledger_sha256: string;
  locked_sha256: string | null;
  lock_status: "locked_match" | "locked_mismatch" | "unlocked";
};

export type LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric = {
  metric_id: string;
  metric_name: string;
  basis: "calendar_month_from_cumulative" | "month_end_point";
  method: "finance_metric_cumulative_mom" | "finance_metric_point_to_point";
  unit: "亿元";
  comparison_status: "comparable" | "not_comparable";
  current_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  previous_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  two_month_prior_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus | null;
  current_value_yi: string | null;
  previous_value_yi: string | null;
  current_source_value_yi: string | null;
  previous_source_value_yi: string | null;
  two_month_prior_source_value_yi: string | null;
  delta_yi: string | null;
  change_rate: string | null;
  rate_reason: "zero_denominator" | "missing_reference" | "metric_status_not_ok" | null;
  reasons: string[];
  driver_status: "unclear";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_comparable";
};

export type LedgerPnlCandidateFinancialIndicatorNetInterestComponent = {
  metric_id: string;
  metric_name: string;
  formula_weight: -1 | 1;
  current_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  previous_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  two_month_prior_metric_status: LedgerPnlCandidateFinancialIndicatorComparisonMetricStatus;
  current_value_yi: string | null;
  previous_value_yi: string | null;
  current_source_value_yi: string | null;
  previous_source_value_yi: string | null;
  two_month_prior_source_value_yi: string | null;
  component_delta_yi: string | null;
  contribution_to_net_delta_yi: string | null;
  reasons: string[];
};

export type LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge = {
  analysis_kind: "accounting_component_bridge";
  status: "available" | "not_evaluable";
  metric_id: "income.interest.net";
  basis: "calendar_month_from_cumulative";
  method: "finance_metric_component_contribution";
  unit: "亿元";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_evaluable";
  foot_status: "passed" | "failed" | "not_evaluable";
  net_delta_yi: string | null;
  component_contribution_total_yi: string | null;
  reconciliation_delta_yi: string | null;
  reasons: string[];
  components: LedgerPnlCandidateFinancialIndicatorNetInterestComponent[];
};

export type LedgerPnlCandidateFinancialIndicatorFullScopeGap = {
  reason_code:
    | "missing_source_file"
    | "missing_required_sheet"
    | "source_parse_error"
    | "full_replay_incomplete"
    | "source_evaluation_error";
  source_kind: "ledger" | "daily";
  month: string;
  required_sheet: string | null;
};

export type LedgerPnlCandidateFinancialIndicatorPeriodComparison = {
  contract_version: "candidate-financial-indicator-period-comparison-v2";
  report_month: string;
  report_date: string;
  comparison_month: string;
  two_month_prior: string;
  comparison_scope: "ledger_only_key_metrics";
  full_scope_status: "available" | "unavailable";
  full_scope_reason_code:
    | "available"
    | "missing_source_file"
    | "missing_required_sheet"
    | "source_parse_error"
    | "full_replay_incomplete"
    | "source_evaluation_error";
  full_scope_detail: string;
  full_scope_gaps: LedgerPnlCandidateFinancialIndicatorFullScopeGap[];
  overall_status: "available" | "partial" | "unavailable";
  metric_status: "candidate";
  formal_use_allowed: false;
  certification_effect: "none";
  driver_status: "unclear";
  rule_version: "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  idempotency_key: string;
  source_periods: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[];
  net_interest_component_bridge: LedgerPnlCandidateFinancialIndicatorNetInterestComponentBridge;
  metrics: LedgerPnlCandidateFinancialIndicatorPeriodComparisonMetric[];
};

export type LedgerPnlCandidateFinancialIndicatorComponentMetricId =
  | "income.interest.loan.total"
  | "expense.interest.deposit.total"
  | "income.interest.investment"
  | "income.interest.interbank_net";

export type LedgerPnlCandidateFinancialIndicatorComponentMatchedTerm = {
  source: "ledger";
  level: "l1" | "l2" | "l3" | "full";
  code: string;
  weight: string;
};

export type LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence = {
  month: string;
  report_date: string;
  ledger_file_name: string;
  ledger_sha256: string;
  locked_sha256: string | null;
  lock_status: "locked_match" | "unlocked";
  sheet: "综本";
  row: number;
  account_code_cell: string;
  ending_cell: string;
  ending_yuan: string;
};

export type LedgerPnlCandidateFinancialIndicatorComponentDetailRow = {
  row_status: "contributing" | "excluded_offset";
  account_code: string;
  account_name: string;
  currency: "CNX";
  effective_component_weight: string;
  effective_net_weight: string;
  matched_terms: LedgerPnlCandidateFinancialIndicatorComponentMatchedTerm[];
  current_ending_yuan: string;
  previous_ending_yuan: string;
  two_month_prior_ending_yuan: string;
  current_value_yi: string;
  previous_value_yi: string;
  component_delta_yi: string;
  contribution_to_net_delta_yi: string;
  source_evidence: LedgerPnlCandidateFinancialIndicatorComponentSourceEvidence[];
};

export type LedgerPnlCandidateFinancialIndicatorComponentDetail = {
  contract_version: "candidate-financial-indicator-component-detail-v1";
  analysis_kind: "accounting_component_account_detail";
  report_month: string;
  report_date: string;
  comparison_month: string;
  two_month_prior: string;
  metric_id: LedgerPnlCandidateFinancialIndicatorComponentMetricId;
  metric_name: string;
  formula_weight: -1 | 1;
  currency: "CNX";
  basis: "calendar_month_from_cumulative";
  method: "finance_metric_account_contribution";
  unit: "亿元";
  status: "available" | "not_evaluable" | "stale_parent";
  quality_status: "standard_candidate" | "degraded_candidate" | "not_evaluable";
  foot_status: "passed" | "failed" | "not_evaluable";
  formal_use_allowed: false;
  certification_effect: "none";
  driver_status: "unclear";
  rule_version: "qdb-finance-2026-v1.0.1";
  rule_hash: string;
  parent_idempotency_key: string;
  idempotency_key: string;
  source_periods: LedgerPnlCandidateFinancialIndicatorComparisonSourcePeriod[];
  parent_current_value_yi: string | null;
  parent_previous_value_yi: string | null;
  parent_component_delta_yi: string | null;
  parent_contribution_to_net_delta_yi: string | null;
  account_current_total_yi: string | null;
  account_previous_total_yi: string | null;
  account_component_delta_total_yi: string | null;
  account_contribution_total_yi: string | null;
  current_reconciliation_yi: string | null;
  previous_reconciliation_yi: string | null;
  component_delta_reconciliation_yi: string | null;
  contribution_reconciliation_yi: string | null;
  reasons: string[];
  rows: LedgerPnlCandidateFinancialIndicatorComponentDetailRow[];
};

export type LedgerPnlFormalFinancialIndicatorMetric = {
  metric_key: string;
  metric_name: string;
  scope: string;
  excel_value: string;
  unit: string;
  excel_ref: string;
  formula: string;
  source_status: LedgerPnlFormalIndicatorSourceStatus;
  system_metric: string | null;
  system_value: string | null;
  reconciliation_gap?: string | null;
  value: string | number | null;
  basis: "formal_financial_indicator_source_contract";
  formal_use_allowed: boolean;
  source_version: string;
  rule_version: string;
  consolidation_scope: string;
  cell_ref: string;
  golden_sample_ref: string;
  missing_reason: string;
};

export type LedgerPnlFormalFinancialIndicatorRemediation = {
  required: boolean;
  action_label: string;
  action_detail: string;
  required_artifact: string;
  artifact_status?: "missing" | "available" | string;
  blocking_reason?: string;
  acceptance_criteria?: string[];
  registration_package?: {
    fixture_target?: string;
    registry_target?: string;
    contract_builder?: string;
    release_gate?: string;
  };
  registration_package_guard?: {
    status?: string;
    required_fields?: string[];
    missing_fields?: string[];
    blocking_rule?: string;
  };
  readback_acceptance?: {
    label?: string;
    readback_query?: string;
    target_state?: string;
    release_state?: string;
    formal_use_guard?: string;
    source_guard?: string;
    verification?: string;
  };
  registration_target: string;
  verification: string;
};

export type LedgerPnlFormalFinancialIndicatorContractPayload = {
  sample_id: string;
  sample_status: string;
  surface: string;
  report_month: string;
  report_date: string;
  source_workbook: string;
  source_sheet: string;
  source_basis: string;
  source_version: string;
  rule_version: string;
  formal_use_allowed: boolean;
  contract_note: string;
  release_gate?: {
    status?: string;
    blocking_reason?: string;
    required_evidence?: string[];
    readback_action?: string;
  };
  status_semantics: Record<LedgerPnlFormalIndicatorSourceStatus, string>;
  remediation?: LedgerPnlFormalFinancialIndicatorRemediation;
  metrics: LedgerPnlFormalFinancialIndicatorMetric[];
};

export type LedgerPnlRatioRecomputationStatus = "matched" | "mismatch" | "insufficient_inputs";

export type LedgerPnlRatioRecomputationCheck = {
  check_key: string;
  metric_name: string;
  contract_metric_key: string;
  contract_value: string;
  unit: string;
  status: LedgerPnlRatioRecomputationStatus;
  formula?: string;
  numerator_metric_key?: string;
  numerator_value?: string;
  denominator_metric_key?: string;
  denominator_value?: string;
  recomputed_value?: string;
  diff?: string;
  tolerance?: string;
  missing_inputs?: string[];
  note?: string;
};

export type LedgerPnlAdditivityCheckStatus = "exact" | "residual_present";

export type LedgerPnlAdditivityComponent = {
  metric_key: string;
  value: string;
};

export type LedgerPnlAdditivityCheck = {
  check_key: string;
  metric_name: string;
  total_metric_key: string;
  total_value: string;
  components: LedgerPnlAdditivityComponent[];
  components_sum: string;
  residual: string;
  unit: string;
  status: LedgerPnlAdditivityCheckStatus;
  note?: string;
};

export type LedgerPnlArrangementRuleStatus =
  | "pass"
  | "fail"
  | "insufficient_inputs"
  | "informational"
  | "summary";

export type LedgerPnlArrangementRule = {
  rule_key: string;
  rule_name: string;
  source_ref: string;
  status: LedgerPnlArrangementRuleStatus;
  missing_inputs?: string[];
  note?: string;
  quarter_end_type?: string;
  actual_value?: string;
  target_value?: string;
  comparator?: string;
  unit?: string;
  assumption_value?: string;
  assumption_unit?: string;
  referenced_additivity_check_keys?: string[];
  exact_count?: number;
  residual_present_count?: number;
};

export type LedgerPnlFormalIndicatorRuleChecksSummary = {
  ratio_recomputation: { matched: number; mismatch: number; insufficient_inputs: number; total: number };
  additivity_checks: { exact: number; residual_present: number; total: number };
  arrangement_rules: {
    pass: number;
    fail: number;
    insufficient_inputs: number;
    informational: number;
    summary: number;
    total: number;
  };
  total_checks: number;
};

export type LedgerPnlFormalIndicatorRuleChecksPayload = {
  report_month: string;
  report_date: string;
  basis: string;
  formal_use_allowed: boolean;
  sample_status: string;
  source_version: string;
  rule_version: string;
  contract_note: string;
  ratio_recomputation: LedgerPnlRatioRecomputationCheck[];
  additivity_checks: LedgerPnlAdditivityCheck[];
  arrangement_rules: LedgerPnlArrangementRule[];
  summary: LedgerPnlFormalIndicatorRuleChecksSummary;
  remediation?: LedgerPnlFormalFinancialIndicatorRemediation;
};
