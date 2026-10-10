import { useState } from "react";
import { type PnlByBusinessAnalysisDimension, type PnlByBusinessAnalysisRow } from "../../api/contracts";
import { DataTable, type DataTableColumn } from "../../components/layout";
import { formatAnalysisYieldPct, formatAvgBalanceYi, toneFromSigned } from "./pnlByBusinessPageModel";
import { formatPnlWan, formatYuanAsYiCell } from "./pnlByBusinessDisplay";
import { ANALYSIS_DIMENSION_LABELS } from "./pnlByBusinessAnalysisOptions";

export function AnalysisRowsTable({
  rows,
  dimension,
  testId = "pnl-by-business-analysis-table",
}: {
  rows: PnlByBusinessAnalysisRow[];
  dimension: PnlByBusinessAnalysisDimension;
  testId?: string;
}) {
  const [view, setView] = useState<"results" | "composition" | "all">("results");
  const columns: DataTableColumn<PnlByBusinessAnalysisRow>[] = [
    {
      key: "dimension_label",
      title: ANALYSIS_DIMENSION_LABELS[dimension],
      width: view === "results" ? 160 : 180,
      render: (row) => row.dimension_label,
    },
    {
      key: "avg_balance",
      title: "日均(亿元)",
      align: "numeric",
      render: (row) => formatAvgBalanceYi(row.avg_balance),
    },
    {
      key: "current_balance",
      title: "期末余额(亿元)",
      align: "numeric",
      render: (row) => formatYuanAsYiCell(row.current_balance),
    },
    {
      key: "interest_income",
      title: "利息收入（万元）",
      align: "numeric",
      render: (row) => formatPnlWan(row.interest_income),
    },
    {
      key: "fair_value_change",
      title: "公允价值变动（万元）",
      align: "numeric",
      render: (row) => formatPnlWan(row.fair_value_change),
    },
    {
      key: "capital_gain",
      title: "资本利得（万元）",
      align: "numeric",
      render: (row) => formatPnlWan(row.capital_gain),
    },
    {
      key: "manual_adjustment",
      title: "手工调整（万元）",
      align: "numeric",
      render: (row) => formatPnlWan(row.manual_adjustment),
    },
    {
      key: "total_pnl",
      title: "合计损益（万元）",
      align: "numeric",
      render: (row) => (
        <strong className="pnl-by-business-table__decision-cell" data-pnl-tone={toneFromSigned(row.total_pnl)}>
          {formatPnlWan(row.total_pnl)}
        </strong>
      ),
    },
    {
      key: "annualized_yield_pct",
      title: "年化收益率",
      align: "numeric",
      render: (row) => formatAnalysisYieldPct(row.annualized_yield_pct),
    },
    {
      key: "ftp_cost",
      title: "FTP成本（万元）",
      align: "numeric",
      render: (row) => formatPnlWan(row.ftp_cost),
    },
    {
      key: "ftp_net_pnl",
      title: "FTP后收益（万元）",
      align: "numeric",
      render: (row) => (
        <strong className="pnl-by-business-table__decision-cell" data-pnl-tone={toneFromSigned(row.ftp_net_pnl)}>
          {formatPnlWan(row.ftp_net_pnl)}
        </strong>
      ),
    },
    {
      key: "ftp_net_annualized_yield_pct",
      title: "FTP后收益率",
      align: "numeric",
      render: (row) => formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct),
    },
    {
      key: "asset_count",
      title: "资产数",
      align: "numeric",
      render: (row) => row.asset_count,
    },
  ];
  const visibleKeys = view === "results"
    ? ["dimension_label", "avg_balance", "total_pnl", "annualized_yield_pct", "ftp_net_pnl", "ftp_net_annualized_yield_pct"]
    : ["dimension_label", "interest_income", "fair_value_change", "capital_gain", "manual_adjustment", "total_pnl", "ftp_cost", "ftp_net_pnl"];
  const visibleColumns = view === "all" ? columns : columns.filter((column) => visibleKeys.includes(column.key));

  return (
    <div className="pnl-by-business-analysis-table" data-testid={testId} data-view={view}>
      <div className="pnl-by-business-analysis-table__toolbar">
        <div
          className="pnl-by-business-selected-trend__tabs"
          role="group"
          aria-label={`${ANALYSIS_DIMENSION_LABELS[dimension]}表格内容`}
        >
          {([
            ["results", "规模与收益"],
            ["composition", "损益构成"],
            ["all", "完整明细"],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={view === key}
              aria-controls={`${testId}-content`}
              onClick={() => setView(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="pnl-by-business-analysis-table__count">共 {rows.length} 项</span>
      </div>
      <div id={`${testId}-content`}>
        <DataTable
          rows={rows}
          rowKey="dimension_key"
          columns={visibleColumns}
          ariaLabel={`${ANALYSIS_DIMENSION_LABELS[dimension]}损益明细`}
          testId={`${testId}-grid`}
        />
      </div>
    </div>
  );
}
