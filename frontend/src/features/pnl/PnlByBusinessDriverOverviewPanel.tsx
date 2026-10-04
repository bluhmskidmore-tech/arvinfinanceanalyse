import { type PnlByBusinessYtdItem } from "../../api/contracts";
import { type PnlByBusinessAdbEvidenceStatus, formatAnalysisYieldPct } from "./pnlByBusinessPageModel";
import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";
import { numeric, formatPnlWan, formatYuanAsYiCell } from "./pnlByBusinessDisplay";

export function DriverOverviewPanel({
  rows,
  adbAvgByBusinessType,
  adbEvidenceStatus,
}: {
  rows: PnlByBusinessYtdItem[];
  adbAvgByBusinessType: Map<string, number>;
  adbEvidenceStatus: PnlByBusinessAdbEvidenceStatus;
}) {
  const topRows = [...rows]
    .filter((row) => (numeric(row.total_pnl) ?? 0) > 0)
    .sort((left, right) => (numeric(right.total_pnl) ?? 0) - (numeric(left.total_pnl) ?? 0))
    .slice(0, 5);
  const bottomRows = [...rows]
    .filter((row) => (numeric(row.total_pnl) ?? 0) < 0)
    .sort((left, right) => (numeric(left.total_pnl) ?? 0) - (numeric(right.total_pnl) ?? 0))
    .slice(0, 5);
  const yieldRows = [...rows]
    .map((row) => {
      return { row, yieldPct: numeric(row.annualized_yield_pct) };
    })
    .filter((item) => item.yieldPct !== null)
    .sort((left, right) => Math.abs(right.yieldPct ?? 0) - Math.abs(left.yieldPct ?? 0))
    .slice(0, 5);
  const gapRows = [...rows]
    .map((row) => {
      const adbAvg = resolveAdbAvgYuan(row.business_type, adbAvgByBusinessType, row.avg_balance);
      const current = numeric(row.current_balance) ?? 0;
      return {
        row,
        gap: adbAvg !== undefined ? current - adbAvg.valueYuan : null,
        adbSource: adbAvg?.source,
      };
    })
    .filter((item) => item.gap !== null)
    .sort((left, right) => Math.abs(right.gap ?? 0) - Math.abs(left.gap ?? 0))
    .slice(0, 5);
  const gapUsesYtdParentField =
    adbEvidenceStatus === "comparison" && gapRows.some((item) => item.adbSource === "ytd_row");

  return (
    <section className="pnl-by-business-analysis-block" data-testid="pnl-by-business-driver-overview">
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>驱动概览</h2>
          <p>
            按 YTD 损益、分项、年化收益率和日均/期末差异看业务种类贡献；日均来源：
            {adbEvidenceStatus === "pnl_primary"
              ? "损益主表账面日均（与期末余额一致，含应计利息）"
              : adbEvidenceStatus === "comparison"
              ? gapUsesYtdParentField
                ? "ADB 补充复核（父级行日均消费 YTD 主端点后端字段，不做前端子类求和）"
                : "ADB 补充复核"
              : adbEvidenceStatus === "loading"
                ? "YTD 主端点（ADB 补充复核读取中）"
                : "YTD 主端点（ADB 补充复核不可用）"}
            。
          </p>
        </div>
      </div>
      <div className="pnl-by-business-driver-grid">
        <div className="pnl-by-business-mini-table">
          <h3>Top 贡献</h3>
          <table>
            <tbody>
              {topRows.length > 0 ? (
                topRows.map((row) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatPnlWan(row.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>暂无正贡献</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>Bottom 拖累</h3>
          <table>
            <tbody>
              {bottomRows.length > 0 ? (
                bottomRows.map((row) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatPnlWan(row.total_pnl)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>暂无负贡献</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>收益率排行</h3>
          <table>
            <tbody>
              {yieldRows.length > 0 ? (
                yieldRows.map(({ row, yieldPct }) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatAnalysisYieldPct(yieldPct)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>日均缺失</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="pnl-by-business-mini-table">
          <h3>日均 vs 期末</h3>
          <table>
            <tbody>
              {gapRows.length > 0 ? (
                gapRows.map(({ row, gap }) => (
                  <tr key={row.row_key}>
                    <td>{row.business_type}</td>
                    <td>{formatYuanAsYiCell(gap ?? 0)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2}>日均缺失</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
