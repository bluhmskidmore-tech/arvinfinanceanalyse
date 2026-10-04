import { Link } from "react-router-dom";

import type { ProductCategoryPnlRow } from "../../../api/contracts";
import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import { EM_DASH } from "../../../utils/format";
import {
  formatProductCategoryForeignDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryYieldValue,
  toneForProductCategoryForeignDisplayValue,
  toneForProductCategoryValue,
} from "../../product-category-pnl/pages/productCategoryPnlPageModel";
import styles from "./BusinessContributionTable.module.css";

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
    return EM_DASH;
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
    <PageAsyncSection
      title="经营贡献（产品分类损益）"
      fillHeight={false}
      isLoading={loading}
      isError={error}
      isEmpty={false}
      onRetry={() => {
        onRetry?.();
      }}
      extra={
        <Link to="/product-category-pnl" aria-label="进入产品分类损益">
          <strong>进入产品分类损益</strong>
        </Link>
      }
    >
      {reportDate ? (
        <p data-testid="operations-contribution-table-provenance" className={styles.provenance}>
          报告日 <strong>{reportDate}</strong>，{view === "monthly" ? "月度" : view}产品分类损益，金额单位为亿元。
          {readProvenanceLine ? (
            <>
              <br />
              {readProvenanceLine}
            </>
          ) : null}
        </p>
      ) : (
        <p className={styles.provenanceEmpty}>暂无可用报告日。</p>
      )}

      <div data-testid="operations-contribution-total-summary" className={styles.summary}>
        <div>
          <div className={styles.summaryLabel}>总收益（合计）</div>
          <div
            style={{
              marginTop: 2,
              color: totalIncomeTone,
              fontSize: 22,
              fontWeight: 600,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {formatProductCategoryValue(grandTotal?.business_net_income)}
            <span className={styles.summaryUnit}>亿元</span>
          </div>
        </div>
        <div className={styles.summaryMeta}>
          当前场景：<span className={styles.summaryMetaValue}>{formatRatePct(currentRate)}</span>
        </div>
        <div className={styles.summaryMeta}>
          基准场景：<span className={styles.summaryMetaValue}>{formatRatePct(baselineRate)}</span>
        </div>
        <div className={`${styles.summaryMeta} ${styles.summaryMetaRight}`}>
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

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr className={styles.headRow}>
              <th className={styles.th}>产品分类</th>
              <th className={styles.th}>侧别</th>
              <th className={styles.thRight}>综本日均</th>
              <th className={styles.thRight}>人民币FTP</th>
              <th className={styles.thRight}>人民币净收入</th>
              <th className={styles.thRight}>外币净收入</th>
              <th className={styles.thRight}>经营净收入</th>
              <th className={styles.thRight}>加权收益率</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading ? (
              <tr>
                <td colSpan={8} className={styles.emptyCell}>
                  暂无产品分类行
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.category_id}
                  style={{
                    borderTop: "1px solid var(--dh-api-line-soft)",
                    background: row.is_total ? "var(--dh-api-panel-3)" : "var(--dh-api-panel)",
                    fontWeight: row.is_total ? 700 : 400,
                  }}
                >
                  <td className={styles.nameCell}>
                    <span style={{ paddingLeft: row.level * 14 }}>{row.category_name}</span>
                  </td>
                  <td className={styles.sideCell}>{formatSide(row.side)}</td>
                  <td className={styles.numCell}>{formatProductCategoryRowDisplayValue(row, row.cnx_scale)}</td>
                  <td className={styles.numCell}>{formatProductCategoryRowDisplayValue(row, row.cny_ftp)}</td>
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
                      color: toneForProductCategoryForeignDisplayValue(row, row.foreign_net),
                    }}
                  >
                    {formatProductCategoryForeignDisplayValue(row, row.foreign_net)}
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
                  <td className={styles.numCell}>{formatProductCategoryYieldValue(row.weighted_yield)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div data-testid="operations-contribution-footer-total" className={styles.footerTotal}>
          全部市场科目 + 投资收益合计：{formatProductCategoryValue(grandTotal?.business_net_income)}
        </div>
      </div>
    </PageAsyncSection>
  );
}
