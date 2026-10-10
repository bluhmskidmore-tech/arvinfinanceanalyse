import { Fragment, useMemo } from "react";
import { type PnlByBusinessAnalysisRow, type PnlByBusinessYtdItem, type PnlByBusinessYtdSummary } from "../../api/contracts";
import { formatAnnualizedYieldPctDisplay } from "./pnlByBusinessAnnualizedYield";
import { formatAnalysisYieldPct, formatAvgBalanceYi, formatRatioPct, isDetailZqtzBusinessRow, isParentZqtzBusinessRow, toneFromSigned } from "./pnlByBusinessPageModel";
import { EM_DASH } from "../../utils/format";
import { numeric, formatPnlWan } from "./pnlByBusinessDisplay";

export function BusinessRowsTable({
  rows,
  selectedRowKey,
  inlineCurrencyRows,
  summary,
  unallocatedPnl,
  unallocatedRowCount,
  onSelectRow,
}: {
  rows: PnlByBusinessYtdItem[];
  selectedRowKey: string | null;
  inlineCurrencyRows: PnlByBusinessAnalysisRow[];
  summary?: PnlByBusinessYtdSummary;
  unallocatedPnl?: string;
  unallocatedRowCount?: number;
  onSelectRow: (row: PnlByBusinessYtdItem) => void;
}) {
  const parentRows = useMemo(() => rows.filter(isParentZqtzBusinessRow), [rows]);
  const detailRows = useMemo(() => rows.filter(isDetailZqtzBusinessRow), [rows]);

  const renderRow = (row: PnlByBusinessYtdItem, selectable: boolean) => {
    const avgDisplay = formatAvgBalanceYi(row.avg_balance);
    const totalPnlTone = toneFromSigned(row.total_pnl);
    const ftpNetPnlTone = toneFromSigned(row.ftp_net_pnl);
    return (
      <tr
        key={row.row_key}
        className={selectable && row.row_key === selectedRowKey ? "pnl-by-business-table-row-selected" : undefined}
        onClick={selectable ? () => onSelectRow(row) : undefined}
        onKeyDown={
          selectable
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectRow(row);
                }
              }
            : undefined
        }
        role={selectable ? "button" : undefined}
        tabIndex={selectable ? 0 : undefined}
      >
        <td className="pnl-by-business-table__business-cell">
          <span>{row.business_type}</span>
          {totalPnlTone !== "default" ? (
            <small className={`pnl-by-business-table__signal pnl-by-business-table__signal--${totalPnlTone}`}>
              {totalPnlTone === "negative" ? "拖累" : "贡献"}
            </small>
          ) : null}
        </td>
        <td>{avgDisplay}</td>
        <td>{formatPnlWan(row.interest_income)}</td>
        <td>{formatPnlWan(row.fair_value_change)}</td>
        <td>{formatPnlWan(row.capital_gain)}</td>
        <td>{formatPnlWan(row.manual_adjustment)}</td>
        <td className="pnl-by-business-table__decision-cell" data-pnl-tone={totalPnlTone}>
          {formatPnlWan(row.total_pnl)}
        </td>
        <td>{formatAnnualizedYieldPctDisplay(row.annualized_yield_pct)}</td>
        <td className="pnl-by-business-table__decision-cell" data-pnl-tone={ftpNetPnlTone}>
          {formatPnlWan(row.ftp_net_pnl)}
        </td>
        <td>{formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct)}</td>
        <td>{formatRatioPct(row.proportion)}</td>
        <td>{row.assets_count}</td>
      </tr>
    );
  };

  const renderCurrencyRow = (row: PnlByBusinessAnalysisRow) => {
    const totalPnlTone = toneFromSigned(row.total_pnl);
    const ftpNetPnlTone = toneFromSigned(row.ftp_net_pnl);
    return (
      <tr
        key={`currency-${row.dimension_key}`}
        className="pnl-by-business-table-row-currency-child"
        data-testid={`pnl-by-business-inline-currency-row-${row.dimension_key}`}
      >
        <td className="pnl-by-business-table__business-cell pnl-by-business-table__currency-cell">
          <span className="pnl-by-business-table__currency-label">
            <span aria-hidden="true">↳</span>
            {row.dimension_label}
          </span>
          <small>父级拆分 · 金额折人民币</small>
        </td>
        <td>{formatAvgBalanceYi(row.avg_balance)}</td>
        <td>{formatPnlWan(row.interest_income)}</td>
        <td>{formatPnlWan(row.fair_value_change)}</td>
        <td>{formatPnlWan(row.capital_gain)}</td>
        <td>{formatPnlWan(row.manual_adjustment)}</td>
        <td className="pnl-by-business-table__decision-cell" data-pnl-tone={totalPnlTone}>
          {formatPnlWan(row.total_pnl)}
        </td>
        <td>{formatAnnualizedYieldPctDisplay(row.annualized_yield_pct)}</td>
        <td className="pnl-by-business-table__decision-cell" data-pnl-tone={ftpNetPnlTone}>
          {formatPnlWan(row.ftp_net_pnl)}
        </td>
        <td>{formatAnalysisYieldPct(row.ftp_net_annualized_yield_pct)}</td>
        <td title="币种拆分占比未由接口返回">—</td>
        <td>{row.asset_count}</td>
      </tr>
    );
  };

  return (
    <>
      <div
        className="pnl-by-business-table-shell"
        data-testid="pnl-by-business-table"
        tabIndex={0}
        aria-label="年累计业务种类损益表，可横向滚动"
      >
        <table className="pnl-by-business-table">
          <thead>
            <tr>
              <th>业务种类</th>
              <th>日均(亿元)</th>
              <th>利息收入（万元）</th>
              <th>公允价值变动（万元）</th>
              <th>资本利得（万元）</th>
              <th>手工调整（万元）</th>
              <th>合计损益（万元）</th>
              <th>年化收益率</th>
              <th>FTP后收益（万元）</th>
              <th>FTP后收益率</th>
              <th>占比</th>
              <th>资产数</th>
            </tr>
          </thead>
          <tbody>
            {parentRows.map((row) => (
              <Fragment key={row.row_key}>
                {renderRow(row, true)}
                {row.row_key === selectedRowKey ? inlineCurrencyRows.map(renderCurrencyRow) : null}
              </Fragment>
            ))}
          </tbody>
          {parentRows.length > 0 ? (
            <tfoot>
              <tr data-testid="pnl-by-business-table-parent-footer">
                <td className="pnl-by-business-table-footer-cell">父级损益（系统汇总）</td>
                <td className="pnl-by-business-table-footer-cell">{formatAvgBalanceYi(summary?.avg_balance)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.interest_income)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.fair_value_change)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.capital_gain)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.manual_adjustment)}</td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.total_pnl)}</td>
                <td className="pnl-by-business-table-footer-cell">
                  {formatAnnualizedYieldPctDisplay(summary?.annualized_yield_pct)}
                </td>
                <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary?.ftp_net_pnl)}</td>
                <td className="pnl-by-business-table-footer-cell">
                  {formatAnalysisYieldPct(summary?.ftp_net_annualized_yield_pct)}
                </td>
                <td className="pnl-by-business-table-footer-cell">{formatRatioPct(summary?.proportion)}</td>
                <td className="pnl-by-business-table-footer-cell">{summary?.assets_count ?? EM_DASH}</td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      {(unallocatedRowCount ?? 0) > 0 || (numeric(unallocatedPnl) ?? 0) !== 0 ? (
        <div
          className="pnl-by-business-detail-warning"
          data-testid="pnl-by-business-table-unallocated-footer"
        >
          未分类差额：{formatPnlWan(unallocatedPnl)} 万元（{unallocatedRowCount ?? 0} 条）；该金额未并入父级汇总，
          分类映射或来源信息待核对。
        </div>
      ) : null}
      {detailRows.length > 0 ? (
        <details
          className="pnl-by-business-detail-block pnl-by-business-detail-disclosure"
          data-testid="pnl-by-business-detail-table"
        >
          <summary
            className="pnl-by-business-detail-disclosure__summary"
            data-testid="pnl-by-business-detail-table-toggle"
          >
            <span>
              <strong>其中项明细</strong>
              <small>已包含在父级行中，不可与父级或其他其中项相加；展开查看拆解。</small>
            </span>
            <span className="pnl-by-business-detail-disclosure__action" aria-hidden="true">
              展开明细
            </span>
          </summary>
          <div className="pnl-by-business-detail-warning" data-testid="pnl-by-business-detail-overlap-warning">
            以下金额已包含在上方父级行中，与父级行金额存在重叠，不可与父级行相加，也不可跨行相加。
          </div>
          <div className="pnl-by-business-detail-heading">
            <p>这些行为父级分类的拆解项，不参与父级汇总和资产数加总。</p>
          </div>
          <div
            className="pnl-by-business-table-shell"
            tabIndex={0}
            aria-label="年累计其中项明细表，可横向滚动"
          >
            <table className="pnl-by-business-table">
              <thead>
                <tr>
                  <th>业务种类</th>
                  <th>日均(亿元)</th>
                  <th>利息收入（万元）</th>
                  <th>公允价值变动（万元）</th>
                  <th>资本利得（万元）</th>
                  <th>手工调整（万元）</th>
                  <th>合计损益（万元）</th>
                  <th>年化收益率</th>
                  <th>FTP后收益（万元）</th>
                  <th>FTP后收益率</th>
                  <th>占比</th>
                  <th>资产数</th>
                </tr>
              </thead>
              <tbody>{detailRows.map((row) => renderRow(row, false))}</tbody>
            </table>
          </div>
        </details>
      ) : null}
    </>
  );
}
