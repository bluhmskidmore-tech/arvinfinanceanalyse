import { Link } from "react-router-dom";

import type { ProductCategoryPnlRow } from "../../../api/contracts";
import { SectionCard } from "../../../components/SectionCard";
import {
  formatProductCategoryValue,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryYieldValue,
  toneForProductCategoryValue,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";

function formatSide(side: string): string {
  if (side === "asset") {
    return "资产";
  }
  if (side === "liability") {
    return "负债";
  }
  return side;
}

function formatRatePct(value: ProductCategoryPnlRow["baseline_ftp_rate_pct"] | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return `${value}%`;
  }
  return `${parsed.toFixed(2).replace(/\.?0+$/, "")}%`;
}

export type BusinessContributionTableProps = {
  reportDate: string | null;
  view: string;
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  loading: boolean;
  error: boolean;
  onRetry?: () => void;
  /** 受治理 result_meta 一行，由页面注入；不新增指标口径解释。 */
  readProvenanceLine?: string;
};

export function BusinessContributionTable({
  reportDate,
  view,
  rows,
  assetTotal,
  liabilityTotal,
  grandTotal,
  loading,
  error,
  onRetry,
  readProvenanceLine,
}: BusinessContributionTableProps) {
  const currentRate = grandTotal?.scenario_rate_pct ?? grandTotal?.baseline_ftp_rate_pct;
  const baselineRate = grandTotal?.baseline_ftp_rate_pct;
  const totalIncomeTone = toneForProductCategoryValue(grandTotal?.business_net_income);

  return (
    <SectionCard
      title="经营贡献（产品分类损益读面）"
      loading={loading}
      error={error}
      onRetry={onRetry}
      extra={
        <Link to="/product-category-pnl" aria-label="进入产品分类损益">
          <strong>进入产品分类损益</strong>
        </Link>
      }
    >
      {reportDate ? (
        <p
          data-testid="operations-contribution-table-provenance"
          style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82", lineHeight: 1.6 }}
        >
          报告日 <strong>{reportDate}</strong>，数据来自{" "}
          <code>/ui/pnl/product-category</code>
          ，view={view}；由总账对账 + 日均配对链路生成，表格直接展示后端产品分类行，不在前端重算合计或改写类别。
          {readProvenanceLine ? (
            <>
              <br />
              {readProvenanceLine}
            </>
          ) : null}
        </p>
      ) : (
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#5c6b82" }}>暂无可用报告日。</p>
      )}

      <div
        data-testid="operations-contribution-total-summary"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(180px, 1.4fr) repeat(3, minmax(120px, 1fr))",
          gap: 12,
          margin: "0 0 12px",
          padding: "12px 14px",
          border: "1px solid #dbe4f0",
          borderRadius: 8,
          background: "#f8fbff",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>总收益（合计）</div>
          <div
            style={{
              marginTop: 2,
              color: totalIncomeTone,
              fontSize: 22,
              fontWeight: 800,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {formatProductCategoryValue(grandTotal?.business_net_income)}
            <span style={{ marginLeft: 4, color: "#64748b", fontSize: 12, fontWeight: 600 }}>亿元</span>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "#475569", fontWeight: 700 }}>
          当前场景：<span style={{ color: "#111827" }}>{formatRatePct(currentRate)}</span>
        </div>
        <div style={{ fontSize: 12, color: "#475569", fontWeight: 700 }}>
          基准场景：<span style={{ color: "#111827" }}>{formatRatePct(baselineRate)}</span>
        </div>
        <div style={{ fontSize: 12, color: "#475569", fontWeight: 700, textAlign: "right" }}>
          资产 / 负债：
          <span style={{ color: toneForProductCategoryValue(assetTotal?.business_net_income) }}>
            {formatProductCategoryValue(assetTotal?.business_net_income)}
          </span>
          {" / "}
          <span style={{ color: toneForProductCategoryValue(liabilityTotal?.business_net_income) }}>
            {formatProductCategoryValue(liabilityTotal?.business_net_income)}
          </span>
        </div>
      </div>

      <div
        style={{
          overflowX: "auto",
          borderRadius: 8,
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
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>产品分类</th>
              <th style={{ padding: "10px 12px", fontWeight: 600 }}>侧别</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>综本日均</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>人民币FTP</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>人民币净收入</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>外币净收入</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>经营净收入</th>
              <th style={{ padding: "10px 12px", fontWeight: 600, textAlign: "right" }}>加权收益率</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading ? (
              <tr>
                <td colSpan={8} style={{ padding: 16, color: "#94a3b8", textAlign: "center" }}>
                  暂无产品分类行
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.category_id}
                  style={{
                    borderTop: "1px solid #eef2f7",
                    background: row.is_total ? "#f3f7ff" : "#ffffff",
                    fontWeight: row.is_total ? 700 : 400,
                  }}
                >
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "#162033" }}>
                    <span style={{ paddingLeft: row.level * 14 }}>{row.category_name}</span>
                  </td>
                  <td style={{ padding: "10px 12px", color: "#475569" }}>{formatSide(row.side)}</td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums", textAlign: "right" }}>
                    {formatProductCategoryRowDisplayValue(row, row.cnx_scale)}
                  </td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums", textAlign: "right" }}>
                    {formatProductCategoryRowDisplayValue(row, row.cny_ftp)}
                  </td>
                  <td
                    style={{
                      padding: "10px 12px",
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                      color: toneForProductCategoryValue(row.cny_net),
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.cny_net)}
                  </td>
                  <td
                    style={{
                      padding: "10px 12px",
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                      color: toneForProductCategoryValue(row.foreign_net),
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.foreign_net)}
                  </td>
                  <td
                    style={{
                      padding: "10px 12px",
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                      color: toneForProductCategoryValue(row.business_net_income),
                    }}
                  >
                    {formatProductCategoryRowDisplayValue(row, row.business_net_income)}
                  </td>
                  <td style={{ padding: "10px 12px", fontVariantNumeric: "tabular-nums", textAlign: "right" }}>
                    {formatProductCategoryYieldValue(row.weighted_yield)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div
          data-testid="operations-contribution-footer-total"
          style={{
            padding: "12px 16px",
            background: "#111827",
            color: "#fff",
            fontSize: 14,
            fontWeight: 800,
            textAlign: "center",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          全部市场科目 + 投资收益合计：{formatProductCategoryValue(grandTotal?.business_net_income)}
        </div>
      </div>
    </SectionCard>
  );
}
