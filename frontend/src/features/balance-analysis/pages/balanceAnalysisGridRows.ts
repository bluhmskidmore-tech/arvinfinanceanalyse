import type {
  BalanceAnalysisDetailRow,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisTableRow,
} from "../../../api/contracts";

export type BalanceAnalysisDetailGridRow = BalanceAnalysisDetailRow & { __gridId: string };
export type BalanceAnalysisSummaryGridRow = BalanceAnalysisSummaryRow & { __gridId: string };

export function getBalanceSummaryGridRowId(row: BalanceAnalysisTableRow): string {
  return [
    row.source_family,
    row.position_scope,
    row.currency_basis,
    row.invest_type_std,
    row.accounting_basis,
    row.display_name,
    row.owner_name,
    row.category_name,
    row.row_key,
  ].join("|");
}

export function getBalanceDetailGridRowId(row: BalanceAnalysisDetailRow): string {
  return [
    row.source_family,
    row.report_date,
    row.position_scope,
    row.currency_basis,
    row.invest_type_std,
    row.accounting_basis,
    row.display_name,
    row.row_key,
  ].join("|");
}

export function buildBalanceDetailGridRows(
  rows: readonly BalanceAnalysisDetailRow[],
): BalanceAnalysisDetailGridRow[] {
  return rows.map((row, index) => ({
    ...row,
    __gridId: [getBalanceDetailGridRowId(row), index].join("|"),
  }));
}

export function getBalanceDetailSummaryGridRowId(row: BalanceAnalysisSummaryRow): string {
  return [
    row.source_family,
    row.position_scope,
    row.currency_basis,
    row.row_count,
    row.market_value_amount,
    row.amortized_cost_amount,
    row.accrued_interest_amount,
  ].join("|");
}

export function buildBalanceDetailSummaryGridRows(
  rows: readonly BalanceAnalysisSummaryRow[],
): BalanceAnalysisSummaryGridRow[] {
  return rows.map((row, index) => ({
    ...row,
    __gridId: [getBalanceDetailSummaryGridRowId(row), index].join("|"),
  }));
}
