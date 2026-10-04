import { type PnlByBusinessAnalysisRow, type PnlByBusinessYtdItem } from "../../api/contracts";
import { KpiCard } from "../../components/KpiCard";
import { buildNegativeFtpList, formatAnalysisYieldPct, formatYuanAsWanUnit, toneFromSigned } from "./pnlByBusinessPageModel";
import { EM_DASH } from "../../utils/format";
import { numeric, formatFtpRatePct } from "./pnlByBusinessDisplay";
import { AnalysisRowsTable } from "./PnlByBusinessAnalysisRowsTable";

export function BondBucketAnalysisPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  const ftpRateDisplay = formatFtpRatePct(rows[0]?.ftp_rate_pct);
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-bond-bucket-analysis">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>投资资产四类统计</h2>
          <p>覆盖全部投资资产，归入利率债、信用债、金融债、其他投资资产；其他投资资产含外国债券、公募基金、非底层投资资产及其他债权融资类产品。FTP 年化利率为 {ftpRateDisplay}。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">投资资产四类数据读取失败</div>
      ) : rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无投资资产四类数据</div>
      ) : (
        <AnalysisRowsTable rows={rows} dimension="bond_bucket" testId="pnl-by-business-bond-bucket-table" />
      )}
    </section>
  );
}

export function FtpBridgePanel({
  selectedRow,
}: {
  selectedRow: PnlByBusinessYtdItem | undefined;
}) {
  const avgBalance = selectedRow?.avg_balance ?? null;
  const ftpRateDisplay = formatFtpRatePct(selectedRow?.ftp_rate_pct);
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-ftp-bridge">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>FTP后收益桥</h2>
          <p>{selectedRow?.business_type ?? EM_DASH} · FTP 年化利率 {ftpRateDisplay}</p>
        </div>
      </div>
      <div className="pnl-by-business-analysis-kpis">
        <KpiCard
          label="合计损益"
          value={formatYuanAsWanUnit(selectedRow?.total_pnl)}
          detail="扣 FTP 前"
        />
        <KpiCard
          label="FTP成本"
          value={formatYuanAsWanUnit(selectedRow?.ftp_cost)}
          detail={avgBalance === null ? "日均缺失" : numeric(avgBalance) === 0 ? "日均为0" : `日均 × ${ftpRateDisplay} × 期间自然日数 ÷ 365`}
        />
        <KpiCard
          label="FTP后收益"
          value={formatYuanAsWanUnit(selectedRow?.ftp_net_pnl)}
          detail="合计损益 - FTP成本"
          tone={toneFromSigned(selectedRow?.ftp_net_pnl)}
        />
        <KpiCard
          label="FTP后收益率"
          value={formatAnalysisYieldPct(selectedRow?.ftp_net_annualized_yield_pct)}
          detail={`年化收益率 - ${ftpRateDisplay}`}
          tone={toneFromSigned(selectedRow?.ftp_net_annualized_yield_pct)}
        />
      </div>
    </section>
  );
}

export function BondBucketMonthlyPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-bond-bucket-monthly">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>投资资产四类月度趋势</h2>
          <p>按月观察利率债、信用债、金融债和其他投资资产的 FTP 后收益变化。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">投资资产四类月度趋势读取失败</div>
      ) : rows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">暂无投资资产四类月度趋势</div>
      ) : (
        <AnalysisRowsTable
          rows={rows}
          dimension="bond_bucket_monthly"
          testId="pnl-by-business-bond-bucket-monthly-table"
        />
      )}
    </section>
  );
}

export function NegativeFtpListPanel({
  rows,
  isLoading,
  isError,
}: {
  rows: PnlByBusinessAnalysisRow[];
  isLoading: boolean;
  isError: boolean;
}) {
  const { topRows: negativeRows, negativeCount, calculatedCount, unavailableRows } = buildNegativeFtpList(rows);
  const ftpRateDisplay = formatFtpRatePct(negativeRows[0]?.ftp_rate_pct ?? rows[0]?.ftp_rate_pct);
  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-negative-ftp-list">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>负FTP后收益清单（拖累前十项）</h2>
          <p>仅筛选已计算 {ftpRateDisplay} FTP 的资产，按 FTP 后亏损金额展示前十项。</p>
        </div>
      </div>
      {isLoading ? (
        <div className="pnl-by-business-analysis-state">加载中</div>
      ) : isError ? (
        <div className="pnl-by-business-analysis-state">负 FTP 后收益清单读取失败</div>
      ) : negativeRows.length === 0 ? (
        <div className="pnl-by-business-analysis-state">已计算 FTP 的资产中暂无负收益项。</div>
      ) : (
        <AnalysisRowsTable rows={negativeRows} dimension="instrument" testId="pnl-by-business-negative-ftp-table" />
      )}
      {!isLoading && !isError ? (
        <>
          <p>已计算 FTP {calculatedCount} 笔，其中负收益 {negativeCount} 笔；另有 {unavailableRows.length} 笔 FTP 未计算，未参与筛选。</p>
          {unavailableRows.length > 0 ? (
            <details>
              <summary>查看 FTP 未计算资产及扣 FTP 前损益（{unavailableRows.length} 笔）</summary>
              <AnalysisRowsTable rows={unavailableRows} dimension="instrument" testId="pnl-by-business-unavailable-ftp-table" />
            </details>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
