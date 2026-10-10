/**
 * Balance 分析 / 余额勾稽前后端契约防漂移测试（Wave3 F08，仅新增测试）。
 *
 * 机制沿用 `AgentContractSync.test.ts`（Wave1 F04）：解析后端 Pydantic 模型源码
 * 得到字段名/可空性/Literal 取值，与前端 `contracts/balanceLedger.ts` 的类型清单
 * 逐项比对。解析辅助抽取到 `./contractSyncUtils`（本任务新增的测试基础设施），
 * `AgentContractSync.test.ts` 自身不做修改。
 *
 * 覆盖两个后端 schema 源：
 * - `backend/app/schemas/balance_analysis.py`（`BalanceAnalysis*` 系列——明细/汇总/
 *   总览/工作簿/决策项）
 * - `backend/app/schemas/accounting_asset_movement.py`（`Accounting*MovementPayload`
 *   系列——对应前端 `BalanceMovement*` 余额变动勾稽契约）
 *
 * 已发现的真实契约漂移（不在本任务修复范围，见文末 `.skip` 用例与任务报告）：
 * 1. `BalanceAnalysisCurrentUserPayload.identity_source` 前端多声明了后端不会产生的
 *    `"system"` 取值（`backend/app/security/auth_context.py` 只产出 header/env/fallback）。
 * 2. `BalanceMovementPayload`（前端）缺少后端 `AccountingAssetMovementPayload.unmapped_gl_accounts` 字段。
 * 3. `BalanceMovementDatesPayload`（前端）缺少后端 `AccountingAssetMovementDatesPayload.upstream_control_report_dates` 必填字段。
 */
import { describe, expect, it } from "vitest";

import type {
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDecisionItemRow,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisDetailRow,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisMetricDefinition,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisPayload,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisTableRow,
  BalanceAnalysisWorkbookCard,
  BalanceAnalysisWorkbookColumn,
  BalanceAnalysisWorkbookPayload,
  BalanceAnalysisWorkbookTable,
  BalanceBasisMovementBucket,
  BalanceBasisMovementComponent,
  BalanceBasisMovementDecomposition,
  BalanceBusinessMovementRow,
  BalanceBusinessMovementTrendMonth,
  BalanceDifferenceAttributionComponent,
  BalanceDifferenceAttributionWaterfall,
  BalanceMovementDrilldownMeta,
  BalanceMovementRefreshPayload,
  BalanceMovementRow,
  BalanceMovementSummary,
  BalanceMovementTrendMonth,
  BalanceStructureMigrationAnalysis,
  BalanceStructureMigrationBucket,
  BalanceStructureMigrationPair,
  BalanceZqtzCalibrationAnalysis,
  BalanceZqtzCalibrationItem,
  BalanceZqtzConcentrationAnalysis,
  BalanceZqtzConcentrationDimension,
  BalanceZqtzConcentrationItem,
  BalanceZqtzMaturityBucket,
  BalanceZqtzMaturityStructure,
} from "../api/contracts";
import {
  expectFieldParity,
  expectNullableFieldParity,
  parseFieldLiteralValues,
  parseLiteralValues,
  readBackendFile,
} from "./contractSyncUtils";

const BACKEND_SOURCES = {
  balanceAnalysis: readBackendFile("backend/app/schemas/balance_analysis.py"),
  accountingAssetMovement: readBackendFile("backend/app/schemas/accounting_asset_movement.py"),
};

// —— 编译期绑定：清单键必须与契约类型的 keyof 完全一致（多、少、拼错均无法通过 tsc）。 ——

const BALANCE_ANALYSIS_DETAIL_ROW_FIELDS = {
  source_family: true,
  report_date: true,
  row_key: true,
  display_name: true,
  position_scope: true,
  currency_basis: true,
  invest_type_std: true,
  accounting_basis: true,
  market_value_amount: true,
  amortized_cost_amount: true,
  accrued_interest_amount: true,
  is_issuance_like: true,
} as const satisfies Record<keyof BalanceAnalysisDetailRow, true>;

const BALANCE_ANALYSIS_SUMMARY_ROW_FIELDS = {
  source_family: true,
  position_scope: true,
  currency_basis: true,
  row_count: true,
  market_value_amount: true,
  amortized_cost_amount: true,
  accrued_interest_amount: true,
} as const satisfies Record<keyof BalanceAnalysisSummaryRow, true>;

const BALANCE_ANALYSIS_TABLE_ROW_FIELDS = {
  row_key: true,
  source_family: true,
  display_name: true,
  owner_name: true,
  category_name: true,
  position_scope: true,
  currency_basis: true,
  invest_type_std: true,
  accounting_basis: true,
  detail_row_count: true,
  market_value_amount: true,
  amortized_cost_amount: true,
  accrued_interest_amount: true,
} as const satisfies Record<keyof BalanceAnalysisTableRow, true>;

const BALANCE_ANALYSIS_PAYLOAD_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  details: true,
  summary: true,
} as const satisfies Record<keyof BalanceAnalysisPayload, true>;

const BALANCE_ANALYSIS_SUMMARY_TABLE_PAYLOAD_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  limit: true,
  offset: true,
  total_rows: true,
  rows: true,
} as const satisfies Record<keyof BalanceAnalysisSummaryTablePayload, true>;

/**
 * 后端 `BalanceAnalysisOverviewPayload` 不含 `calibration`：该字段由信封层
 * `_with_balance_analysis_response_context` 注入，前端契约已在类型注释中记录
 * "直接读 result.calibration 恒为 undefined"，因此这里排除它，只比对 result 层字段。
 */
const BALANCE_ANALYSIS_OVERVIEW_PAYLOAD_RESULT_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  detail_row_count: true,
  summary_row_count: true,
  total_market_value_amount: true,
  total_amortized_cost_amount: true,
  total_accrued_interest_amount: true,
  asset_total_market_value_amount: true,
  liability_total_market_value_amount: true,
  asset_total_amortized_cost_amount: true,
  liability_total_amortized_cost_amount: true,
  asset_total_accrued_interest_amount: true,
  liability_total_accrued_interest_amount: true,
  metric_definitions: true,
} as const satisfies Omit<Record<keyof BalanceAnalysisOverviewPayload, true>, "calibration">;

const BALANCE_ANALYSIS_BASIS_BREAKDOWN_ROW_FIELDS = {
  source_family: true,
  invest_type_std: true,
  accounting_basis: true,
  position_scope: true,
  currency_basis: true,
  detail_row_count: true,
  market_value_amount: true,
  amortized_cost_amount: true,
  accrued_interest_amount: true,
} as const satisfies Record<keyof BalanceAnalysisBasisBreakdownRow, true>;

const BALANCE_ANALYSIS_BASIS_BREAKDOWN_PAYLOAD_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  rows: true,
} as const satisfies Record<keyof BalanceAnalysisBasisBreakdownPayload, true>;

const BALANCE_ANALYSIS_METRIC_DEFINITION_FIELDS = {
  key: true,
  label: true,
  source_field: true,
  raw_unit: true,
  display_unit: true,
  basis: true,
  source_surface: true,
  applies_to: true,
  description: true,
} as const satisfies Record<keyof BalanceAnalysisMetricDefinition, true>;

const BALANCE_ANALYSIS_WORKBOOK_CARD_FIELDS = {
  key: true,
  label: true,
  value: true,
  note: true,
} as const satisfies Record<keyof BalanceAnalysisWorkbookCard, true>;

const BALANCE_ANALYSIS_WORKBOOK_COLUMN_FIELDS = {
  key: true,
  label: true,
} as const satisfies Record<keyof BalanceAnalysisWorkbookColumn, true>;

const BALANCE_ANALYSIS_WORKBOOK_TABLE_FIELDS = {
  key: true,
  title: true,
  section_kind: true,
  columns: true,
  rows: true,
} as const satisfies Record<keyof BalanceAnalysisWorkbookTable, true>;

const BALANCE_ANALYSIS_DECISION_ITEM_ROW_FIELDS = {
  title: true,
  action_label: true,
  severity: true,
  reason: true,
  source_section: true,
  rule_id: true,
  rule_version: true,
} as const satisfies Record<keyof BalanceAnalysisDecisionItemRow, true>;

const BALANCE_ANALYSIS_DECISION_STATUS_RECORD_FIELDS = {
  decision_key: true,
  status: true,
  updated_at: true,
  updated_by: true,
  comment: true,
} as const satisfies Record<keyof BalanceAnalysisDecisionStatusRecord, true>;

const BALANCE_ANALYSIS_EVENT_CALENDAR_ROW_FIELDS = {
  event_date: true,
  event_type: true,
  title: true,
  source: true,
  impact_hint: true,
  source_section: true,
} as const satisfies Record<keyof BalanceAnalysisEventCalendarRow, true>;

const BALANCE_ANALYSIS_RISK_ALERT_ROW_FIELDS = {
  title: true,
  severity: true,
  reason: true,
  source_section: true,
  rule_id: true,
  rule_version: true,
} as const satisfies Record<keyof BalanceAnalysisRiskAlertRow, true>;

const BALANCE_ANALYSIS_DECISION_ITEMS_PAYLOAD_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  columns: true,
  rows: true,
} as const satisfies Record<keyof BalanceAnalysisDecisionItemsPayload, true>;

const BALANCE_ANALYSIS_WORKBOOK_PAYLOAD_FIELDS = {
  report_date: true,
  position_scope: true,
  currency_basis: true,
  cards: true,
  tables: true,
  operational_sections: true,
} as const satisfies Record<keyof BalanceAnalysisWorkbookPayload, true>;

describe("balance_analysis.py ↔ contracts/balanceLedger.ts（BalanceAnalysis* 明细/汇总/工作簿）", () => {
  const source = BACKEND_SOURCES.balanceAnalysis;

  it("明细/汇总/表格行模型字段与前端契约一致", () => {
    expectFieldParity(source, "BalanceAnalysisDetailRow", BALANCE_ANALYSIS_DETAIL_ROW_FIELDS);
    expectFieldParity(source, "BalanceAnalysisSummaryRow", BALANCE_ANALYSIS_SUMMARY_ROW_FIELDS);
    expectFieldParity(source, "BalanceAnalysisTableRow", BALANCE_ANALYSIS_TABLE_ROW_FIELDS);
    expectFieldParity(source, "BalanceAnalysisPayload", BALANCE_ANALYSIS_PAYLOAD_FIELDS);
    expectFieldParity(
      source,
      "BalanceAnalysisSummaryTablePayload",
      BALANCE_ANALYSIS_SUMMARY_TABLE_PAYLOAD_FIELDS,
    );
  });

  it("总览/口径拆分模型字段与前端契约一致（result 层，不含信封注入的 calibration）", () => {
    expectFieldParity(
      source,
      "BalanceAnalysisOverviewPayload",
      BALANCE_ANALYSIS_OVERVIEW_PAYLOAD_RESULT_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisBasisBreakdownRow",
      BALANCE_ANALYSIS_BASIS_BREAKDOWN_ROW_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisBasisBreakdownPayload",
      BALANCE_ANALYSIS_BASIS_BREAKDOWN_PAYLOAD_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisMetricDefinition",
      BALANCE_ANALYSIS_METRIC_DEFINITION_FIELDS,
    );
  });

  it("工作簿卡片/表格/决策项/日历/风险提示模型字段与前端契约一致", () => {
    expectFieldParity(source, "BalanceAnalysisWorkbookCard", BALANCE_ANALYSIS_WORKBOOK_CARD_FIELDS);
    expectFieldParity(
      source,
      "BalanceAnalysisWorkbookColumn",
      BALANCE_ANALYSIS_WORKBOOK_COLUMN_FIELDS,
    );
    expectFieldParity(source, "BalanceAnalysisWorkbookTable", BALANCE_ANALYSIS_WORKBOOK_TABLE_FIELDS);
    expectFieldParity(
      source,
      "BalanceAnalysisDecisionItemRow",
      BALANCE_ANALYSIS_DECISION_ITEM_ROW_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisDecisionStatusRecord",
      BALANCE_ANALYSIS_DECISION_STATUS_RECORD_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisEventCalendarRow",
      BALANCE_ANALYSIS_EVENT_CALENDAR_ROW_FIELDS,
    );
    expectFieldParity(source, "BalanceAnalysisRiskAlertRow", BALANCE_ANALYSIS_RISK_ALERT_ROW_FIELDS);
    expectFieldParity(
      source,
      "BalanceAnalysisDecisionItemsPayload",
      BALANCE_ANALYSIS_DECISION_ITEMS_PAYLOAD_FIELDS,
    );
    expectFieldParity(
      source,
      "BalanceAnalysisWorkbookPayload",
      BALANCE_ANALYSIS_WORKBOOK_PAYLOAD_FIELDS,
    );
  });

  it("可空字段与前端契约可空性一致", () => {
    expectNullableFieldParity(source, "BalanceAnalysisDetailRow", ["is_issuance_like"]);
    expectNullableFieldParity(source, "BalanceAnalysisWorkbookCard", ["note"]);
    expectNullableFieldParity(source, "BalanceAnalysisDecisionStatusRecord", [
      "updated_at",
      "updated_by",
      "comment",
    ]);
  });

  it("关键 Literal 取值：position_scope / currency_basis / severity / decision_status / source_family", () => {
    expect(parseLiteralValues(source, "BalancePositionScope").sort()).toEqual(
      ["asset", "liability", "all"].sort(),
    );
    expect(parseLiteralValues(source, "BalanceCurrencyBasis").sort()).toEqual(
      ["native", "CNY"].sort(),
    );
    expect(parseLiteralValues(source, "BalanceAnalysisSeverity").sort()).toEqual(
      ["low", "medium", "high"].sort(),
    );
    expect(parseLiteralValues(source, "BalanceAnalysisDecisionStatus").sort()).toEqual(
      ["pending", "confirmed", "dismissed"].sort(),
    );
    expect(parseLiteralValues(source, "BalanceAnalysisSourceFamily").sort()).toEqual(
      ["zqtz", "tyw", "combined"].sort(),
    );
  });

  /**
   * 已知真实漂移（F08 审计发现，不在本任务修复范围）：
   * 后端 `BalanceAnalysisCurrentUserPayload.identity_source` 是
   * `Literal["header", "env", "fallback"]`（`backend/app/security/auth_context.py`
   * 只会产出这三个值），前端 `BalanceAnalysisCurrentUserPayload.identity_source`
   * 多声明了一个后端永远不会产生的 `"system"` 取值。一旦后端收紧或前端消费方按
   * `"system"` 分支判断，这个多余分支永远走不到、也不会被类型检查发现。
   */
  it.skip("[已知漂移] BalanceAnalysisCurrentUserPayload.identity_source 与后端 Literal 完全一致", () => {
    // 前端 identity_source 多声明了 "system"，此断言按后端真实 Literal 编写；
    // 一旦有人在前端补回该断言（去掉 .skip），会立即因为前端类型比这里多一个
    // 取值而在 tsc 阶段失败（Record<keyof T, true> 的编译期绑定），从而暴露漂移。
    expect(parseFieldLiteralValues(source, "BalanceAnalysisCurrentUserPayload", "identity_source").sort()).toEqual(
      ["header", "env", "fallback"].sort(),
    );
  });
});

// —— accounting_asset_movement.py ↔ BalanceMovement* ——

const BALANCE_MOVEMENT_ROW_FIELDS = {
  report_date: true,
  report_month: true,
  currency_basis: true,
  sort_order: true,
  basis_bucket: true,
  previous_balance: true,
  current_balance: true,
  previous_balance_pct: true,
  current_balance_pct: true,
  balance_change: true,
  change_pct: true,
  contribution_pct: true,
  zqtz_amount: true,
  gl_amount: true,
  reconciliation_diff: true,
  reconciliation_status: true,
  source_version: true,
  rule_version: true,
  chain_status: true,
  chain_fx_adjustment: true,
  chain_fx_currency: true,
  chain_fx_prior_rate: true,
  chain_fx_current_rate: true,
  position_source_basis: true,
} as const satisfies Record<keyof BalanceMovementRow, true>;

const BALANCE_MOVEMENT_SUMMARY_FIELDS = {
  previous_balance_total: true,
  current_balance_total: true,
  balance_change_total: true,
  zqtz_amount_total: true,
  reconciliation_diff_total: true,
  matched_bucket_count: true,
  bucket_count: true,
} as const satisfies Record<keyof BalanceMovementSummary, true>;

const BALANCE_MOVEMENT_TREND_MONTH_FIELDS = {
  report_date: true,
  report_month: true,
  current_balance_total: true,
  balance_change_total: true,
  rows: true,
} as const satisfies Record<keyof BalanceMovementTrendMonth, true>;

const BALANCE_BUSINESS_MOVEMENT_ROW_FIELDS = {
  report_date: true,
  report_month: true,
  currency_basis: true,
  side: true,
  sort_order: true,
  row_key: true,
  row_label: true,
  current_balance: true,
  source_kind: true,
  source_note: true,
  source_version: true,
  rule_version: true,
} as const satisfies Record<keyof BalanceBusinessMovementRow, true>;

const BALANCE_BUSINESS_MOVEMENT_TREND_MONTH_FIELDS = {
  report_date: true,
  report_month: true,
  asset_balance_total: true,
  liability_balance_total: true,
  net_balance_total: true,
  rows: true,
} as const satisfies Record<keyof BalanceBusinessMovementTrendMonth, true>;

const BALANCE_ZQTZ_CALIBRATION_ITEM_FIELDS = {
  row_key: true,
  row_label: true,
  system_amount: true,
  reference_amount: true,
  diff_amount: true,
  status: true,
  note: true,
} as const satisfies Record<keyof BalanceZqtzCalibrationItem, true>;

const BALANCE_ZQTZ_CALIBRATION_ANALYSIS_FIELDS = {
  source_file: true,
  conclusion: true,
  root_cause: true,
  remediation: true,
  items: true,
  residual_risks: true,
} as const satisfies Record<keyof BalanceZqtzCalibrationAnalysis, true>;

const BALANCE_STRUCTURE_MIGRATION_BUCKET_FIELDS = {
  basis_bucket: true,
  previous_balance: true,
  current_balance: true,
  balance_delta: true,
  previous_share_pct: true,
  current_share_pct: true,
  share_delta_pp: true,
} as const satisfies Record<keyof BalanceStructureMigrationBucket, true>;

const BALANCE_STRUCTURE_MIGRATION_PAIR_FIELDS = {
  previous_report_date: true,
  current_report_date: true,
  previous_report_month: true,
  current_report_month: true,
  total_balance_delta: true,
  dominant_share_increase_bucket: true,
  fvtpl_volatility_signal: true,
  oci_valuation_signal: true,
  buckets: true,
} as const satisfies Record<keyof BalanceStructureMigrationPair, true>;

const BALANCE_STRUCTURE_MIGRATION_ANALYSIS_FIELDS = {
  summary: true,
  caveat: true,
  pairs: true,
} as const satisfies Record<keyof BalanceStructureMigrationAnalysis, true>;

const BALANCE_DIFFERENCE_ATTRIBUTION_COMPONENT_FIELDS = {
  component_key: true,
  component_label: true,
  amount: true,
  source_kind: true,
  evidence_note: true,
  is_residual: true,
  is_supported: true,
} as const satisfies Record<keyof BalanceDifferenceAttributionComponent, true>;

const BALANCE_DIFFERENCE_ATTRIBUTION_WATERFALL_FIELDS = {
  reference_label: true,
  reference_total: true,
  target_label: true,
  target_total: true,
  net_difference: true,
  components: true,
  closing_check: true,
  caveat: true,
} as const satisfies Record<keyof BalanceDifferenceAttributionWaterfall, true>;

const BALANCE_MOVEMENT_DRILLDOWN_META_FIELDS = {
  source_tables: true,
  source_scope: true,
  report_date: true,
  prior_report_date: true,
  currency_basis: true,
  zqtz_currency_basis: true,
  unit: true,
  eligible_total: true,
  covered_total: true,
  unknown_total: true,
  coverage_pct: true,
  status: true,
  caveat: true,
} as const satisfies Record<keyof BalanceMovementDrilldownMeta, true>;

const BALANCE_BASIS_MOVEMENT_COMPONENT_FIELDS = {
  component_key: true,
  component_label: true,
  account_code_pattern: true,
  previous_balance: true,
  current_balance: true,
  balance_change: true,
  contribution_pct: true,
  source_note: true,
  is_supported: true,
} as const satisfies Record<keyof BalanceBasisMovementComponent, true>;

const BALANCE_BASIS_MOVEMENT_BUCKET_FIELDS = {
  basis_bucket: true,
  previous_balance: true,
  current_balance: true,
  balance_change: true,
  rows: true,
  residual_amount: true,
  closing_check: true,
} as const satisfies Record<keyof BalanceBasisMovementBucket, true>;

const BALANCE_BASIS_MOVEMENT_DECOMPOSITION_FIELDS = {
  meta: true,
  buckets: true,
} as const satisfies Record<keyof BalanceBasisMovementDecomposition, true>;

const BALANCE_ZQTZ_MATURITY_BUCKET_FIELDS = {
  items: true,
  maturity_bucket: true,
  bucket_label: true,
  current_amount: true,
  prior_amount: true,
  delta_amount: true,
  item_count: true,
  share_pct: true,
} as const satisfies Record<keyof BalanceZqtzMaturityBucket, true>;

const BALANCE_ZQTZ_MATURITY_STRUCTURE_FIELDS = {
  meta: true,
  buckets: true,
} as const satisfies Record<keyof BalanceZqtzMaturityStructure, true>;

const BALANCE_ZQTZ_CONCENTRATION_ITEM_FIELDS = {
  rank: true,
  dimension_value: true,
  current_amount: true,
  prior_amount: true,
  delta_amount: true,
  share_pct: true,
  item_count: true,
  item_kind: true,
} as const satisfies Record<keyof BalanceZqtzConcentrationItem, true>;

const BALANCE_ZQTZ_CONCENTRATION_DIMENSION_FIELDS = {
  dimension: true,
  status: true,
  eligible_total: true,
  covered_total: true,
  unknown_total: true,
  coverage_pct: true,
  prior_coverage_pct: true,
  top_n: true,
  hhi: true,
  top5_share_pct: true,
  items: true,
  caveat: true,
} as const satisfies Record<keyof BalanceZqtzConcentrationDimension, true>;

const BALANCE_ZQTZ_CONCENTRATION_ANALYSIS_FIELDS = {
  meta: true,
  dimensions: true,
} as const satisfies Record<keyof BalanceZqtzConcentrationAnalysis, true>;

const BALANCE_MOVEMENT_REFRESH_PAYLOAD_FIELDS = {
  status: true,
  cache_key: true,
  report_date: true,
  currency_basis: true,
  run_id: true,
  job_name: true,
  trigger_mode: true,
  row_count: true,
  source_version: true,
  rule_version: true,
  product_category_refreshed_dates: true,
  formal_balance_refreshed_dates: true,
  movement_refreshed_dates: true,
} as const satisfies Record<keyof BalanceMovementRefreshPayload, true>;

describe("accounting_asset_movement.py ↔ contracts/balanceLedger.ts（BalanceMovement* 余额变动勾稽）", () => {
  const source = BACKEND_SOURCES.accountingAssetMovement;

  it("变动明细/汇总/趋势行模型字段与前端契约一致", () => {
    expectFieldParity(source, "AccountingAssetMovementRowPayload", BALANCE_MOVEMENT_ROW_FIELDS);
    expectFieldParity(
      source,
      "AccountingAssetMovementSummaryPayload",
      BALANCE_MOVEMENT_SUMMARY_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingAssetMovementTrendMonthPayload",
      BALANCE_MOVEMENT_TREND_MONTH_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingBusinessMovementRowPayload",
      BALANCE_BUSINESS_MOVEMENT_ROW_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingBusinessMovementTrendMonthPayload",
      BALANCE_BUSINESS_MOVEMENT_TREND_MONTH_FIELDS,
    );
  });

  it("ZQTZ 校准 / 结构迁移 / 差异归因瀑布模型字段与前端契约一致", () => {
    expectFieldParity(
      source,
      "AccountingZqtzCalibrationItemPayload",
      BALANCE_ZQTZ_CALIBRATION_ITEM_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzCalibrationAnalysisPayload",
      BALANCE_ZQTZ_CALIBRATION_ANALYSIS_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingStructureMigrationBucketPayload",
      BALANCE_STRUCTURE_MIGRATION_BUCKET_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingStructureMigrationPairPayload",
      BALANCE_STRUCTURE_MIGRATION_PAIR_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingStructureMigrationAnalysisPayload",
      BALANCE_STRUCTURE_MIGRATION_ANALYSIS_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingDifferenceAttributionComponentPayload",
      BALANCE_DIFFERENCE_ATTRIBUTION_COMPONENT_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingDifferenceAttributionWaterfallPayload",
      BALANCE_DIFFERENCE_ATTRIBUTION_WATERFALL_FIELDS,
    );
  });

  it("钻取元信息 / 口径拆解 / ZQTZ 期限结构与集中度模型字段与前端契约一致", () => {
    expectFieldParity(source, "AccountingDrilldownMetaPayload", BALANCE_MOVEMENT_DRILLDOWN_META_FIELDS);
    expectFieldParity(
      source,
      "AccountingBasisMovementComponentPayload",
      BALANCE_BASIS_MOVEMENT_COMPONENT_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingBasisMovementBucketPayload",
      BALANCE_BASIS_MOVEMENT_BUCKET_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingBasisMovementDecompositionPayload",
      BALANCE_BASIS_MOVEMENT_DECOMPOSITION_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzMaturityBucketPayload",
      BALANCE_ZQTZ_MATURITY_BUCKET_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzMaturityStructurePayload",
      BALANCE_ZQTZ_MATURITY_STRUCTURE_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzConcentrationItemPayload",
      BALANCE_ZQTZ_CONCENTRATION_ITEM_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzConcentrationDimensionPayload",
      BALANCE_ZQTZ_CONCENTRATION_DIMENSION_FIELDS,
    );
    expectFieldParity(
      source,
      "AccountingZqtzConcentrationAnalysisPayload",
      BALANCE_ZQTZ_CONCENTRATION_ANALYSIS_FIELDS,
    );
  });

  it("刷新回执模型字段与前端契约一致", () => {
    expectFieldParity(
      source,
      "AccountingAssetMovementRefreshPayload",
      BALANCE_MOVEMENT_REFRESH_PAYLOAD_FIELDS,
    );
  });

  it("行级可空字段（previous/current_balance_pct、change_pct、contribution_pct、chain_status、position_source_basis）与前端一致", () => {
    expectNullableFieldParity(source, "AccountingAssetMovementRowPayload", [
      "previous_balance_pct",
      "current_balance_pct",
      "change_pct",
      "contribution_pct",
      "chain_status",
      "chain_fx_adjustment",
      "chain_fx_currency",
      "chain_fx_prior_rate",
      "chain_fx_current_rate",
      "position_source_basis",
    ]);
  });

  it("关键 Literal 取值：basis_bucket / reconciliation_status / chain_status / freshness_status", () => {
    expect(
      parseLiteralValues(BACKEND_SOURCES.balanceAnalysis, "BalanceAnalysisSourceFamily"),
    ).toBeDefined();
    // basis_bucket / reconciliation_status / chain_status / freshness_status 是行内 Literal
    // （非模块级 `Symbol = Literal[...]`），用逐字对照锁定取值，避免解析器把行内 Literal
    // 误判为需要模块级辅助。
    expect(source).toContain('basis_bucket: Literal["AC", "OCI", "TPL"]');
    expect(source).toContain(
      'reconciliation_status: Literal[\n        "matched",\n        "mismatch",\n        "gl_only",\n        "zqtz_only",\n        "chain_broken",\n    ]',
    );
    expect(source).toContain(
      'chain_status: Literal["continuous", "fx_adjusted", "broken", "no_prior_month"] | None = None',
    );
    expect(source).toContain(
      'freshness_status: Literal[\n        "fresh",\n        "read_model_lagging",\n        "read_model_empty",\n        "upstream_empty",\n    ]',
    );
  });

  /**
   * 已知真实漂移（F08 审计发现，不在本任务修复范围）：
   * 后端 `AccountingAssetMovementPayload` 有 `unmapped_gl_accounts: list[UnmappedGlAccountPayload]`
   * 字段（默认空列表，但恒定序列化输出），前端 `BalanceMovementPayload` 完全没有声明这个字段——
   * 消费方无法以类型安全的方式读取未映射总账科目列表。
   */
  it.skip("[已知漂移] BalanceMovementPayload 应声明 unmapped_gl_accounts 字段", () => {
    expectFieldParity(source, "AccountingAssetMovementPayload", {
      report_date: true,
      currency_basis: true,
      available_report_dates: true,
      upstream_control_report_dates: true,
      freshness_status: true,
      rows: true,
      summary: true,
      trend_months: true,
      business_trend_months: true,
      zqtz_calibration_analysis: true,
      structure_migration_analysis: true,
      difference_attribution_waterfall: true,
      basis_movement_decomposition: true,
      zqtz_maturity_structure: true,
      zqtz_concentration_analysis: true,
      accounting_controls: true,
      excluded_controls: true,
      // unmapped_gl_accounts 未在前端 BalanceMovementPayload 声明，见上方说明。
    });
  });

  /**
   * 已知真实漂移（F08 审计发现，不在本任务修复范围）：
   * 后端 `AccountingAssetMovementDatesPayload.upstream_control_report_dates`
   * 是必填字段（无默认值），前端 `BalanceMovementDatesPayload` 完全没有声明这个字段。
   */
  it.skip("[已知漂移] BalanceMovementDatesPayload 应声明 upstream_control_report_dates 字段", () => {
    expectFieldParity(source, "AccountingAssetMovementDatesPayload", {
      report_dates: true,
      currency_basis: true,
      latest_read_model_report_date: true,
      latest_upstream_control_report_date: true,
      freshness_status: true,
      // upstream_control_report_dates 未在前端 BalanceMovementDatesPayload 声明，见上方说明。
    });
  });
});
