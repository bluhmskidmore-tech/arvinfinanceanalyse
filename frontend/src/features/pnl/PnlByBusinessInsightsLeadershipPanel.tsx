import { Link } from "react-router-dom";

import type { PnlByBusinessInsightsLeadershipModel } from "./pnlByBusinessInsightsModel";
import styles from "./PnlByBusinessInsightsLeadershipPanel.module.css";

export function PnlByBusinessInsightsLeadershipPanel({
  model,
  year,
  asOfDate,
  onSelectRow,
}: {
  model: PnlByBusinessInsightsLeadershipModel;
  year: number;
  asOfDate: string;
  onSelectRow: (rowKey: string) => void;
}) {
  const detailHref = `/pnl-by-business-insights?year=${encodeURIComponent(String(year))}&as_of_date=${encodeURIComponent(asOfDate)}`;
  return (
    <section className={styles.panel} data-testid="pnl-by-business-insights-leadership-panel">
      <div className={styles.header}>
        <div className={styles.heading}>
          <span className={styles.eyebrow}>Approved structure view</span>
          <h2 className={styles.title}>正式结构分析</h2>
          <span className={styles.meta}>
            {model.resolvedDate ? `截止 ${model.resolvedDate}` : "与当前YTD截止日联动"}
            {model.traceId ? ` · Trace ${model.traceId}` : ""}
          </span>
        </div>
        <Link
          className={styles.link}
          to={detailHref}
          data-testid="pnl-by-business-insights-leadership-detail-link"
        >
          查看完整分析 →
        </Link>
      </div>

      {model.status === "loading" ? (
        <div className={styles.review}>结构分析加载中…</div>
      ) : model.status === "review" ? (
        <div className={styles.review} data-testid="pnl-by-business-insights-leadership-review">
          <strong>结构分析待复核</strong>
          <span>{model.reason}</span>
        </div>
      ) : (
        <>
          {model.qualityWarning ? (
            <div className={styles.notice} data-testid="pnl-by-business-insights-leadership-warning">
              质量提示：{model.reason}。指标仍按正式定义展示，汇报时应保留该提示。
            </div>
          ) : null}
          <div className={styles.grid}>
            {model.items.map((item) => {
              const content = (
                <>
                  <span className={styles.label}>{item.label}</span>
                  <span className={styles.value}>{item.value}</span>
                  <span className={styles.detail}>{item.detail}</span>
                </>
              );
              return item.rowKey ? (
                <button
                  key={item.key}
                  type="button"
                  className={styles.item}
                  data-testid={`pnl-by-business-insights-leadership-${item.key}`}
                  onClick={() => onSelectRow(item.rowKey as string)}
                >
                  {content}
                </button>
              ) : (
                <article
                  key={item.key}
                  className={styles.item}
                  data-testid={`pnl-by-business-insights-leadership-${item.key}`}
                >
                  {content}
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
