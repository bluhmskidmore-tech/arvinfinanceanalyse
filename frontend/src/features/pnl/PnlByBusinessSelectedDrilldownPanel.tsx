import { useMemo } from "react";
import { type PnlByBusinessAnalysisRow, type PnlByBusinessYtdItem } from "../../api/contracts";
import { buildPnlByBusinessSelectedDrilldownModel, formatAnalysisYieldPct, formatAvgBalanceYi, formatAvgBalanceYiMetric, formatPnlByBusinessFtpStatus, formatYuanAsWanUnit } from "./pnlByBusinessPageModel";
import { EM_DASH } from "../../utils/format";
import { numeric, formatPnlWan } from "./pnlByBusinessDisplay";

function SelectedDrilldownRowsTable({
  title,
  rows,
  valueField,
  emptyText,
}: {
  title: string;
  rows: PnlByBusinessAnalysisRow[];
  valueField: "total_pnl" | "ftp_net_pnl";
  emptyText: string;
}) {
  return (
    <div className="pnl-by-business-mini-table pnl-by-business-selected-drilldown__table">
      <h3>{title}</h3>
      {rows.length === 0 ? (
        <p className="pnl-by-business-selected-drilldown__empty">{emptyText}</p>
      ) : (
        <table>
          <tbody>
            {rows.map((row) => (
              <tr key={`${title}-${row.dimension_key}`}>
                <td>
                  <strong>{row.dimension_label}</strong>
                  <span>
                    日均 {formatAvgBalanceYi(row.avg_balance)} 亿元 · 资产数 {row.asset_count}
                  </span>
                </td>
                <td>{formatPnlWan(row[valueField])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function SelectedBusinessDrilldownPanel({
  selectedRow,
  rows,
  isLoading,
  isError,
}: {
  selectedRow: PnlByBusinessYtdItem | undefined;
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  const drilldown = useMemo(() => buildPnlByBusinessSelectedDrilldownModel(rows), [rows]);
  const avgBalance = selectedRow?.avg_balance ?? null;
  const ftpStatus = formatPnlByBusinessFtpStatus(selectedRow?.total_pnl, selectedRow?.ftp_net_pnl);
  const dataLimit =
    avgBalance === null
      ? "缺日均，收益率/FTP 仅能对账"
      : numeric(avgBalance) === 0
        ? "日均为0，收益率/FTP 暂不计算"
        : "日均已接入，可看收益率与 FTP 后结果";

  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-selected-drilldown">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>证券级下钻</h2>
          <p>{selectedRow?.business_type ?? EM_DASH} · 从业务种类落到具体券，先看贡献、拖累和 FTP 后为负。</p>
        </div>
      </div>
      <div className="pnl-by-business-selected-drilldown__summary">
        <div>
          <small>选中业务</small>
          <strong>{selectedRow?.business_type ?? EM_DASH}</strong>
          <span>{rows.length} 条证券级记录</span>
        </div>
        <div>
          <small>YTD 合计损益</small>
          <strong>{formatYuanAsWanUnit(selectedRow?.total_pnl)}</strong>
          <span>
            利息 {formatPnlWan(selectedRow?.interest_income)} / 估值 {formatPnlWan(selectedRow?.fair_value_change)} / 资本利得{" "}
            {formatPnlWan(selectedRow?.capital_gain)}
          </span>
        </div>
        <div data-testid="pnl-by-business-selected-ftp-status">
          <small>FTP 后判断</small>
          <strong>{ftpStatus}</strong>
          <span>
            {formatYuanAsWanUnit(selectedRow?.ftp_net_pnl)} · {formatAnalysisYieldPct(selectedRow?.ftp_net_annualized_yield_pct)}
          </span>
        </div>
        <div>
          <small>数据限制</small>
          <strong>{dataLimit}</strong>
          <span>日均 {formatAvgBalanceYiMetric(avgBalance)}</span>
        </div>
      </div>
      {isLoading && rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">证券级明细加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">证券级明细读取失败</div>
      ) : rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无证券级下钻明细</div>
      ) : (
        <div className="pnl-by-business-selected-drilldown__grid">
          <SelectedDrilldownRowsTable
            title="Top 贡献券"
            rows={drilldown.topContributionRows}
            valueField="total_pnl"
            emptyText="暂无贡献券"
          />
          <SelectedDrilldownRowsTable
            title="Top 拖累券"
            rows={drilldown.topDragRows}
            valueField="total_pnl"
            emptyText="暂无总损益为负的证券"
          />
          <SelectedDrilldownRowsTable
            title="FTP 后为负"
            rows={drilldown.negativeFtpRows}
            valueField="ftp_net_pnl"
            emptyText="暂无 FTP 后为负的证券"
          />
        </div>
      )}
    </section>
  );
}
