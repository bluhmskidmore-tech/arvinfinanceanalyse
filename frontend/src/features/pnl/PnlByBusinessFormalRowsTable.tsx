import { type PnlByBusinessPayload, type PnlByBusinessRow } from "../../api/contracts";
import { numeric, formatPnlWan, formatAdbAvgYiCell, formatFormalYieldPctPoints } from "./pnlByBusinessDisplay";

export function FormalBusinessRowsTable({
  rows,
  summary,
}: {
  rows: PnlByBusinessRow[];
  summary?: PnlByBusinessPayload["summary"];
}) {
  return (
    <div className="pnl-by-business-table-shell" data-testid="pnl-by-business-formal-table">
      <table className="pnl-by-business-table">
        <thead>
          <tr>
            <th>业务种类（primary）</th>
            <th>币种</th>
            <th>规模(亿元)</th>
            <th>利息收入（万元）</th>
            <th>公允价值变动（万元）</th>
            <th>资本利得（万元）</th>
            <th>手工调整（万元）</th>
            <th>合计损益（万元）</th>
            <th>表内收益率</th>
            <th>损益行数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.report_date}-${row.business_type_primary}-${row.currency_basis}`}>
              <td>{row.business_type_primary}</td>
              <td>{row.currency_basis}</td>
              <td>{formatAdbAvgYiCell(numeric(row.scale_amount) ?? 0)}</td>
              <td>{formatPnlWan(row.interest_income_514)}</td>
              <td>{formatPnlWan(row.fair_value_change_516)}</td>
              <td>{formatPnlWan(row.capital_gain_517)}</td>
              <td>{formatPnlWan(row.manual_adjustment)}</td>
              <td>{formatPnlWan(row.total_pnl)}</td>
              <td>{formatFormalYieldPctPoints(row.yield_pct)}</td>
              <td>{row.pnl_row_count}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 && summary ? (
          <tfoot>
            {/* 全表合计直读后端 summary（与明细行同一批正式数值），前端不再本地累加。 */}
            <tr data-testid="pnl-by-business-formal-table-footer">
              <td className="pnl-by-business-table-footer-cell">全表合计</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">
                {formatAdbAvgYiCell(numeric(summary.total_scale_amount) ?? 0)}
              </td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary.interest_income_514)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary.fair_value_change_516)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary.capital_gain_517)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary.manual_adjustment)}</td>
              <td className="pnl-by-business-table-footer-cell">{formatPnlWan(summary.total_pnl)}</td>
              <td className="pnl-by-business-table-footer-cell">—</td>
              <td className="pnl-by-business-table-footer-cell">{summary.pnl_row_count}</td>
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}
