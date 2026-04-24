import { Link } from "react-router-dom";

import type { BalanceAnalysisTableRow } from "../../../api/contracts";
import { SectionCard } from "../../../components/SectionCard";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";

function formatCell(raw: string | number | null | undefined): string {
  return formatBalanceAmountToYiFromYuan(raw);
}

export type BusinessContributionTableProps = {
  reportDate: string | null;
  rows: BalanceAnalysisTableRow[];
  loading: boolean;
  error: boolean;
  onRetry?: () => void;
};

export function BusinessContributionTable({
  reportDate,
  rows,
  loading,
  error,
  onRetry,
}: BusinessContributionTableProps) {
  return (
    <SectionCard
      title="经营贡献（余额汇总读面）"
      loading={loading}
      error={error}
      onRetry={onRetry}
      extra={
        <Link to="/balance-analysis" style={{ fontWeight: 600 }} aria-label="进入资产负债分析">
          进入资产负债分析
        </Link>
      }
    >
      {reportDate ? (
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}>
          报告日 <strong>{reportDate}</strong>，数据来自{" "}
          <code style={{ fontSize: 12 }}>/ui/balance-analysis/summary</code>，列示正式物化汇总行（示意经营贡献，非损益瀑布同一口径）。
        </p>
      ) : (
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82" }}>暂无可用报告日。</p>
      )}
      <div
        style={{
          overflowX: "auto",
          borderRadius: 12,
          border: "1px solid #e4ebf5",
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 13,
            background: "#fff",
          }}
        >
          <thead>
            <tr style={{ background: "#f8fafc", color: "#475569", textAlign: "left" }}>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>项目</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>台账</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>资产负债</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>市值</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>摊余</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>应计利息</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading ? (
              <tr>
                <td colSpan={6} style={{ padding: 16, color: "#94a3b8", textAlign: "center" }}>
                  暂无汇总行
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.row_key} style={{ borderTop: "1px solid #eef2f7" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "#162033" }}>
                    {row.display_name}
                  </td>
                  <td style={{ padding: "10px 12px", color: "#475569" }}>{row.source_family}</td>
                  <td style={{ padding: "10px 12px", color: "#475569" }}>{row.position_scope}</td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums" }}>
                    {formatCell(row.market_value_amount)}
                  </td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums" }}>
                    {formatCell(row.amortized_cost_amount)}
                  </td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums" }}>
                    {formatCell(row.accrued_interest_amount)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}
