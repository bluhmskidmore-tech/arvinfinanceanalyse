import type { ColDef, ValueFormatterParams } from "ag-grid-community";

import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisTableRow,
  BalanceAnalysisWorkbookColumn,
} from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import {
  formatBalanceAmountToYiFromYuan,
  formatBalanceBusinessTextDisplay,
  formatBalanceGridThousandsValue,
  formatBalanceWorkbookWanAmountDisplay,
  formatBalanceWorkbookWanTextDisplay,
} from "./balanceAnalysisPageModel";
import type {
  BalanceAnalysisDetailGridRow,
  BalanceAnalysisSummaryGridRow,
} from "./balanceAnalysisGridRows";

function thousandsValueFormatter(params: ValueFormatterParams) {
  return formatBalanceGridThousandsValue(params.value);
}

function yuanAmountValueFormatter(params: ValueFormatterParams) {
  return formatBalanceAmountToYiFromYuan(params.value);
}

const workbookWanAmountFieldKeys = new Set([
  "asset_amount",
  "asset_total_amount",
  "balance_amount",
  "bond_amount",
  "bond_assets_amount",
  "bond_maturity_amount",
  "book_value_amount",
  "coupon_income_amount",
  "cumulative_gap_amount",
  "cumulative_net_cashflow_amount",
  "face_value_amount",
  "floating_pnl_amount",
  "full_scope_gap_amount",
  "full_scope_liability_amount",
  "gap_amount",
  "hqla_amount",
  "interbank_asset_amount",
  "interbank_asset_maturity_amount",
  "interbank_assets_amount",
  "interbank_liability_amount",
  "interbank_liability_maturity_amount",
  "interbank_liabilities_amount",
  "issuance_amount",
  "issuance_maturity_amount",
  "liability_amount",
  "market_value_amount",
  "net_cashflow_amount",
  "net_position_amount",
  "notional_amount",
  "price_return_amount",
  "spread_income_amount",
  "total_amount",
  "amortized_cost_amount",
]);

function isWorkbookWanAmountField(field: unknown): field is string {
  return typeof field === "string" && workbookWanAmountFieldKeys.has(field);
}

function workbookCellFormatter(params: ValueFormatterParams): string {
  if (isWorkbookWanAmountField(params.colDef.field)) {
    return formatBalanceWorkbookWanAmountDisplay(params.value);
  }
  if (typeof params.value === "string" && /(?:wan yuan|万元)/i.test(params.value)) {
    return formatBalanceWorkbookWanTextDisplay(params.value);
  }
  const formattedValue = formatBalanceGridThousandsValue(params.value);
  return typeof params.value === "string" && formattedValue === params.value
    ? formatBalanceBusinessTextDisplay(params.value)
    : formattedValue;
}

function businessTextValueFormatter(params: ValueFormatterParams): string {
  return formatBalanceBusinessTextDisplay(params.value);
}

function formatInvestAccountingDisplay(data: {
  invest_type_std?: unknown;
  accounting_basis?: unknown;
} | null | undefined): string {
  if (!data) {
    return "";
  }
  const investType = data.invest_type_std == null ? "" : formatBalanceBusinessTextDisplay(data.invest_type_std);
  const accountingBasis =
    data.accounting_basis == null ? "" : formatBalanceBusinessTextDisplay(data.accounting_basis);
  const parts = [investType, accountingBasis].filter((part) => part && part !== EM_DASH);
  return parts.length > 0 ? parts.join(" / ") : EM_DASH;
}

export const balanceSummaryColDefs: ColDef<BalanceAnalysisTableRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "display_name", headerName: "展示名" },
  { field: "owner_name", headerName: "组合名称" },
  { field: "category_name", headerName: "分类" },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "market_value_amount",
    headerName: "规模(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "detail_row_count",
    headerName: "明细行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    colId: "invest_accounting",
    headerName: "会计口径",
    valueGetter: (p) => formatInvestAccountingDisplay(p.data),
  },
];

export const balanceDetailColDefs: ColDef<BalanceAnalysisDetailGridRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "display_name", headerName: "标识" },
  { field: "report_date", headerName: "报告日" },
  { field: "position_scope", headerName: "范围", valueFormatter: businessTextValueFormatter },
  {
    colId: "invest_accounting",
    headerName: "会计口径",
    valueGetter: (p) => formatInvestAccountingDisplay(p.data),
  },
  {
    field: "market_value_amount",
    headerName: "规模(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "is_issuance_like",
    headerName: "发行类",
    valueFormatter: (p) =>
      p.value === null || p.value === undefined ? EM_DASH : p.value ? "是" : "否",
  },
];

export const balanceDetailSummaryColDefs: ColDef<BalanceAnalysisSummaryGridRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "row_count",
    headerName: "行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "market_value_amount",
    headerName: "市值(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
];

export const balanceBasisBreakdownColDefs: ColDef<BalanceAnalysisBasisBreakdownRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "invest_type_std", headerName: "投资类型", valueFormatter: businessTextValueFormatter },
  { field: "accounting_basis", headerName: "会计口径", valueFormatter: businessTextValueFormatter },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "detail_row_count",
    headerName: "明细行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "market_value_amount",
    headerName: "市值(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
];

const workbookColumnLabelDisplay: Record<string, string> = {
  Month: "月份",
  "Bond Maturity Amount": "债券到期金额",
  "Bond Maturity Count": "债券到期笔数",
  "Interbank Asset Maturity Amount": "同业资产到期金额",
  "Interbank Asset Maturity Count": "同业资产到期笔数",
  "Interbank Liability Maturity Amount": "同业负债到期金额",
  "Interbank Liability Maturity Count": "同业负债到期笔数",
  "Issuance Maturity Amount": "发行类到期金额",
  "Issuance Maturity Count": "发行类到期笔数",
  "Net Cashflow Amount": "净现金流金额",
  "Cumulative Net Cashflow Amount": "累计净现金流金额",
  Cumulative: "累计值",
  指标键: "指标",
  指标名称: "指标名称",
  参考阈值: "参考线",
  状态: "判断",
  口径说明: "口径",
};

function formatWorkbookColumnLabelDisplay(label: string): string {
  return workbookColumnLabelDisplay[label] ?? formatBalanceBusinessTextDisplay(label);
}

export function buildWorkbookGridColumnDefs(columns: BalanceAnalysisWorkbookColumn[]): ColDef[] {
  return columns.map((col) => ({
    field: col.key,
    headerName: formatWorkbookColumnLabelDisplay(col.label),
    valueFormatter: workbookCellFormatter,
    cellStyle: { ...tabularNumsStyle },
  }));
}
