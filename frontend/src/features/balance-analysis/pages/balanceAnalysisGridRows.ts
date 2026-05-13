import type {
  BalanceAnalysisDetailRow,
  BalanceAnalysisTableRow,
} from "../../../api/contracts";

export type BalanceAnalysisDetailGridRow = BalanceAnalysisDetailRow & { __gridId: string };

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
