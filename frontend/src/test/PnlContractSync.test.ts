/**
 * PnL by-business / YTD / manual-adjustment 前后端契约防漂移测试（Wave3 F08，仅新增测试）。
 *
 * 机制沿用 `AgentContractSync.test.ts`（Wave1 F04）；解析辅助来自本任务新增的
 * `./contractSyncUtils`（`AgentContractSync.test.ts` 自身不做修改）。
 *
 * 覆盖后端 `backend/app/schemas/pnl.py` 中 `PnlByBusiness*`（by-business 主表）、
 * `PnlByBusinessYtd*`（YTD 聚合）、`PnlByBusinessManualAdjustment*`（人工调整）三组
 * 与前端 `contracts/pnl.ts` / `api/pnlByBusinessContracts.ts` 的对应类型。
 *
 * 本轮解析未发现真实字段级契约漂移（字段名、可空性、Literal 取值均一致）。
 */
import { describe, expect, it } from "vitest";

import type {
  PnlByBusinessAnalysisPayload,
  PnlByBusinessAnalysisRow,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessManualAdjustmentRequest,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessMonthlyItem,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessPayload,
  PnlByBusinessRow,
  PnlByBusinessUntracedBreakdownRow,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdPayload,
  PnlByBusinessYtdSummary,
  PnlByBusinessYtdUnallocatedBreakdownRow,
  PnlByBusinessYtdUnallocatedItem,
} from "../api/contracts";
import type { PnlByBusinessSummary } from "../api/pnlByBusinessContracts";
import {
  expectFieldDefaultParity,
  expectFieldParity,
  expectNullableFieldParity,
  parseFieldLiteralValues,
  parseLiteralValues,
  readBackendFile,
} from "./contractSyncUtils";

const BACKEND_PNL_SCHEMA = readBackendFile("backend/app/schemas/pnl.py");

// —— 编译期绑定：清单键必须与契约类型的 keyof 完全一致（多、少、拼错均无法通过 tsc）。 ——

const PNL_BY_BUSINESS_ROW_FIELDS = {
  report_date: true,
  business_type_primary: true,
  business_type: true,
  currency_basis: true,
  interest_income_514: true,
  fair_value_change_516: true,
  capital_gain_517: true,
  manual_adjustment: true,
  total_pnl: true,
  scale_amount: true,
  yield_pct: true,
  pnl_row_count: true,
  balance_row_count: true,
} as const satisfies Record<keyof PnlByBusinessRow, true>;

const PNL_BY_BUSINESS_UNTRACED_BREAKDOWN_ROW_FIELDS = {
  reason_code: true,
  invest_type_std: true,
  pnl_row_count: true,
  total_pnl: true,
  abs_pnl: true,
  interest_income_514: true,
  fair_value_change_516: true,
  capital_gain_517: true,
  manual_adjustment: true,
} as const satisfies Record<keyof PnlByBusinessUntracedBreakdownRow, true>;

const PNL_BY_BUSINESS_SUMMARY_FIELDS = {
  business_count: true,
  total_pnl: true,
  total_scale_amount: true,
  interest_income_514: true,
  fair_value_change_516: true,
  capital_gain_517: true,
  manual_adjustment: true,
  pnl_row_count: true,
  traced_pnl_row_count: true,
  untraced_pnl_row_count: true,
  untraced_breakdown: true,
} as const satisfies Record<keyof PnlByBusinessSummary, true>;

const PNL_BY_BUSINESS_PAYLOAD_FIELDS = {
  report_date: true,
  source_tables: true,
  summary: true,
  rows: true,
} as const satisfies Record<keyof PnlByBusinessPayload, true>;

describe("pnl.py ↔ contracts/pnl.ts + pnlByBusinessContracts.ts（by-business 主表）", () => {
  it("行/未追溯明细/汇总/顶层 payload 模型字段与前端契约一致", () => {
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessRow", PNL_BY_BUSINESS_ROW_FIELDS);
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessUntracedBreakdownRow",
      PNL_BY_BUSINESS_UNTRACED_BREAKDOWN_ROW_FIELDS,
    );
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessSummary", PNL_BY_BUSINESS_SUMMARY_FIELDS);
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessPayload", PNL_BY_BUSINESS_PAYLOAD_FIELDS);
  });

  it("PnlByBusinessRow.yield_pct 可空，其余数值列均非空", () => {
    expectNullableFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessRow", ["yield_pct"]);
  });

  it("PnlByBusinessUntracedReason 未追溯原因码 Literal 与前端联合类型一致", () => {
    // reason_code 标注为模块级类型别名 `PnlByBusinessUntracedReason`（非行内
    // Literal[...]），用模块级解析辅助读取该别名定义。
    expect(parseLiteralValues(BACKEND_PNL_SCHEMA, "PnlByBusinessUntracedReason").sort()).toEqual(
      [
        "position_absent_before_maturity",
        "matured_before_or_on_report_date",
        "never_seen_in_zqtz_asset_balance",
        "same_day_balance_without_primary_type",
        "same_day_balance_multiple_primary_types",
        "unexpected_untraced",
      ].sort(),
    );
  });
});

// —— PnlByBusinessYtd* ——

const PNL_BY_BUSINESS_YTD_ITEM_FIELDS = {
  row_key: true,
  sort_order: true,
  business_type: true,
  interest_income: true,
  fair_value_change: true,
  capital_gain: true,
  manual_adjustment: true,
  total_pnl: true,
  avg_balance: true,
  current_balance: true,
  balance_yield_pct: true,
  annualized_yield_pct: true,
  ftp_rate_pct: true,
  ftp_cost: true,
  ftp_net_pnl: true,
  ftp_net_annualized_yield_pct: true,
  source_kind: true,
  source_note: true,
  proportion: true,
  assets_count: true,
} as const satisfies Record<keyof PnlByBusinessYtdItem, true>;

const PNL_BY_BUSINESS_YTD_UNALLOCATED_BREAKDOWN_ROW_FIELDS = {
  reason_code: true,
  source_kind: true,
  invest_type_std: true,
  accounting_basis: true,
  portfolio_name: true,
  cost_center: true,
  pnl_row_count: true,
  total_pnl: true,
  abs_pnl: true,
  sample_instrument_codes: true,
} as const satisfies Record<keyof PnlByBusinessYtdUnallocatedBreakdownRow, true>;

const PNL_BY_BUSINESS_YTD_UNALLOCATED_ITEM_FIELDS = {
  report_date: true,
  reason_code: true,
  source_kind: true,
  instrument_code: true,
  portfolio_name: true,
  cost_center: true,
  invest_type_std: true,
  accounting_basis: true,
  currency_basis: true,
  interest_income_514: true,
  fair_value_change_516: true,
  capital_gain_517: true,
  manual_adjustment: true,
  total_pnl: true,
  abs_pnl: true,
} as const satisfies Record<keyof PnlByBusinessYtdUnallocatedItem, true>;

const PNL_BY_BUSINESS_YTD_SUMMARY_FIELDS = {
  interest_income: true,
  fair_value_change: true,
  capital_gain: true,
  manual_adjustment: true,
  total_pnl: true,
  avg_balance: true,
  current_balance: true,
  annualized_yield_pct: true,
  ftp_rate_pct: true,
  ftp_cost: true,
  ftp_net_pnl: true,
  ftp_net_annualized_yield_pct: true,
  proportion: true,
  assets_count: true,
} as const satisfies Record<keyof PnlByBusinessYtdSummary, true>;

const PNL_BY_BUSINESS_YTD_PAYLOAD_FIELDS = {
  avg_balance_basis: true,
  balance_quality_issues: true,
  year: true,
  period_type: true,
  period_label: true,
  period_start_date: true,
  period_end_date: true,
  total_pnl: true,
  coverage_days: true,
  expected_days: true,
  sample_filled: true,
  sample_fill_method: true,
  classified_parent_total_pnl: true,
  summary: true,
  unallocated_pnl: true,
  unallocated_abs_pnl: true,
  unallocated_row_count: true,
  reconciliation_delta: true,
  unallocated_breakdown: true,
  unallocated_items: true,
  source_tables: true,
  items: true,
} as const satisfies Record<keyof PnlByBusinessYtdPayload, true>;

const PNL_BY_BUSINESS_MONTHLY_ITEM_FIELDS = {
  row_key: true,
  sort_order: true,
  business_type: true,
  interest_income: true,
  fair_value_change: true,
  capital_gain: true,
  manual_adjustment: true,
  total_pnl: true,
  avg_balance: true,
  current_balance: true,
  annualized_yield_pct: true,
  ftp_rate_pct: true,
  ftp_cost: true,
  ftp_net_pnl: true,
  ftp_net_annualized_yield_pct: true,
  proportion: true,
  asset_count: true,
  source_note: true,
} as const satisfies Record<keyof PnlByBusinessMonthlyItem, true>;

const PNL_BY_BUSINESS_MONTHLY_BUCKET_FIELDS = {
  balance_quality_issues: true,
  month_key: true,
  period_start_date: true,
  period_end_date: true,
  calendar_days: true,
  coverage_days: true,
  expected_days: true,
  sample_filled: true,
  sample_fill_method: true,
  source_total_pnl: true,
  classified_parent_total_pnl: true,
  unallocated_pnl: true,
  unallocated_abs_pnl: true,
  unallocated_row_count: true,
  reconciliation_delta: true,
  unallocated_breakdown: true,
  unallocated_items: true,
  unallocated_evidence_complete: true,
  summary: true,
  items: true,
} as const satisfies Record<keyof PnlByBusinessMonthlyBucket, true>;

const PNL_BY_BUSINESS_MONTHLY_PAYLOAD_FIELDS = {
  avg_balance_basis: true,
  balance_quality_issues: true,
  year: true,
  as_of_date: true,
  source_tables: true,
  months: true,
  management_change: true,
} as const satisfies Record<keyof PnlByBusinessMonthlyPayload, true>;

const PNL_BY_BUSINESS_ANALYSIS_ROW_FIELDS = {
  dimension_key: true,
  dimension_label: true,
  interest_income: true,
  fair_value_change: true,
  capital_gain: true,
  manual_adjustment: true,
  total_pnl: true,
  avg_balance: true,
  current_balance: true,
  annualized_yield_pct: true,
  ftp_rate_pct: true,
  ftp_cost: true,
  ftp_net_pnl: true,
  ftp_net_annualized_yield_pct: true,
  asset_count: true,
} as const satisfies Record<keyof PnlByBusinessAnalysisRow, true>;

const PNL_BY_BUSINESS_ANALYSIS_PAYLOAD_FIELDS = {
  avg_balance_basis: true,
  balance_quality_issues: true,
  year: true,
  as_of_date: true,
  business_key: true,
  dimension: true,
  period_start_date: true,
  period_end_date: true,
  coverage_days: true,
  expected_days: true,
  sample_filled: true,
  sample_fill_method: true,
  source_tables: true,
  rows: true,
  merged_bucket_rows: true,
} as const satisfies Record<keyof PnlByBusinessAnalysisPayload, true>;

describe("pnl.py ↔ contracts/pnl.ts（PnlByBusinessYtd* / Monthly* / Analysis* 聚合）", () => {
  it("YTD 明细项/未分类明细/汇总/顶层 payload 模型字段与前端契约一致", () => {
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessYtdItem", PNL_BY_BUSINESS_YTD_ITEM_FIELDS);
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessYtdUnallocatedBreakdownRow",
      PNL_BY_BUSINESS_YTD_UNALLOCATED_BREAKDOWN_ROW_FIELDS,
    );
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessYtdUnallocatedItem",
      PNL_BY_BUSINESS_YTD_UNALLOCATED_ITEM_FIELDS,
    );
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessYtdSummary", PNL_BY_BUSINESS_YTD_SUMMARY_FIELDS);
    expectFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessYtdPayload", PNL_BY_BUSINESS_YTD_PAYLOAD_FIELDS);
  });

  it("Monthly 明细项/月桶/顶层 payload 模型字段与前端契约一致", () => {
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessMonthlyItem",
      PNL_BY_BUSINESS_MONTHLY_ITEM_FIELDS,
    );
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessMonthlyBucket",
      PNL_BY_BUSINESS_MONTHLY_BUCKET_FIELDS,
    );
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessMonthlyPayload",
      PNL_BY_BUSINESS_MONTHLY_PAYLOAD_FIELDS,
    );
  });

  it("多维分析行/payload 模型字段与前端契约一致（含 bond_bucket 合并展示桶）", () => {
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessAnalysisRow",
      PNL_BY_BUSINESS_ANALYSIS_ROW_FIELDS,
    );
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessAnalysisPayload",
      PNL_BY_BUSINESS_ANALYSIS_PAYLOAD_FIELDS,
    );
  });

  it("YTD 明细项可空字段与前端一致（avg_balance 等 None≠真零 的字段）", () => {
    expectNullableFieldParity(BACKEND_PNL_SCHEMA, "PnlByBusinessYtdItem", [
      "avg_balance",
      "balance_yield_pct",
      "annualized_yield_pct",
      "ftp_cost",
      "ftp_net_pnl",
      "ftp_net_annualized_yield_pct",
      "source_kind",
      "source_note",
      "proportion",
    ]);
  });

  it("PnlByBusinessAnalysisDimension 维度 Literal 与前端联合类型一致", () => {
    expect(parseLiteralValues(BACKEND_PNL_SCHEMA, "PnlByBusinessAnalysisDimension").sort()).toEqual(
      [
        "monthly",
        "portfolio",
        "accounting",
        "currency",
        "cost_center",
        "instrument",
        "bond_bucket",
        "bond_bucket_monthly",
      ].sort(),
    );
  });
});

// —— PnlByBusinessManualAdjustment* ——

const PNL_BY_BUSINESS_MANUAL_ADJUSTMENT_REQUEST_FIELDS = {
  report_date: true,
  row_key: true,
  business_type: true,
  operator: true,
  approval_status: true,
  manual_adjustment: true,
  reason: true,
} as const satisfies Record<keyof PnlByBusinessManualAdjustmentRequest, true>;

const PNL_BY_BUSINESS_MANUAL_ADJUSTMENT_PAYLOAD_FIELDS = {
  adjustment_id: true,
  event_type: true,
  created_at: true,
  stream: true,
  report_date: true,
  row_key: true,
  business_type: true,
  operator: true,
  approval_status: true,
  manual_adjustment: true,
  reason: true,
  created_by: true,
  approved_by: true,
} as const satisfies Record<keyof PnlByBusinessManualAdjustmentPayload, true>;

describe("pnl.py ↔ contracts/pnl.ts（PnlByBusinessManualAdjustment* 人工调整）", () => {
  it("人工调整请求/回执模型字段与前端契约一致", () => {
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessManualAdjustmentRequest",
      PNL_BY_BUSINESS_MANUAL_ADJUSTMENT_REQUEST_FIELDS,
    );
    expectFieldParity(
      BACKEND_PNL_SCHEMA,
      "PnlByBusinessManualAdjustmentPayload",
      PNL_BY_BUSINESS_MANUAL_ADJUSTMENT_PAYLOAD_FIELDS,
    );
  });

  it("operator / approval_status Literal 取值与前端联合类型一致", () => {
    expect(
      parseFieldLiteralValues(
        BACKEND_PNL_SCHEMA,
        "PnlByBusinessManualAdjustmentRequest",
        "operator",
      ).sort(),
    ).toEqual(["ADD", "DELTA", "OVERRIDE"].sort());
    expect(
      parseFieldLiteralValues(
        BACKEND_PNL_SCHEMA,
        "PnlByBusinessManualAdjustmentRequest",
        "approval_status",
      ).sort(),
    ).toEqual(["approved", "pending", "rejected"].sort());
  });

  it("人工调整请求字段默认口径未静默漂移：business_type/operator/approval_status/reason", () => {
    // 后端这些字段带默认值（business_type=""、operator="DELTA"、
    // approval_status="pending"、reason=""），前端契约把它们标为必填是"更严格"
    // 而非漂移——调用方总能显式传值满足默认口径。这里锁定后端默认口径本身，
    // 避免默认值静默变化（如 approval_status 默认从 pending 改成 approved）。
    expectFieldDefaultParity(BACKEND_PNL_SCHEMA, "PnlByBusinessManualAdjustmentRequest", {
      business_type: '""',
      operator: '"DELTA"',
      approval_status: '"pending"',
      reason: '""',
    });
  });
});
