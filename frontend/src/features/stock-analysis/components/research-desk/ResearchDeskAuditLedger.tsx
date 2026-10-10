import styles from "../../pages/StockAnalysisResearchDesk.module.css";
import { statusTone } from "./researchDeskFormatters";
import type { ResearchDeskAuditRow } from "./types";

type ResearchDeskAuditLedgerProps = {
  selectedStockName: string | null;
  rows: ResearchDeskAuditRow[];
  totalVisibleRows: number;
  emptyDetail?: string;
};

export function ResearchDeskAuditLedger({
  selectedStockName,
  rows,
  totalVisibleRows,
  emptyDetail,
}: ResearchDeskAuditLedgerProps) {
  return (
    <section className={styles.audit} data-testid="stock-analysis-research-audit">
      <div className={styles.auditHeader}>
        <div className={styles.auditHeaderLine}>
          <h3>研究审计日志</h3>
          <div className={styles.auditFilters} aria-label="研究审计筛选条件">
            <span>时间范围：<strong>最近 30 日</strong></span>
            <span>事件类型：<strong>全部</strong></span>
            <span>标的：<strong>{selectedStockName ?? "全部"}</strong></span>
            <span>操作人：<strong>全部</strong></span>
          </div>
        </div>
      </div>
      {rows.length === 0 ? (
        <div className={styles.empty}>
          <strong>暂无审计记录</strong>
          <p>{emptyDetail || "候选历史、证据和风险轨道补齐后，这里会自动串成一条研究日志。"}</p>
        </div>
      ) : (
        <div className={styles.auditTable} role="region" aria-label="研究审计日志明细" tabIndex={0}>
          <div className={styles.auditTableHead}>
            <span>时间</span>
            <span>事件类型</span>
            <span>标的</span>
            <span>事件 / 操作描述</span>
            <span>证据 / 来源</span>
            <span>信号强度 / 得分</span>
            <span>状态</span>
            <span>操作人</span>
          </div>
          {rows.map((row, index) => (
            <div key={`${row.time}-${row.kind}-${index}`} className={styles.auditTableRow}>
              <span>{row.time}</span>
              <span>{row.kind}</span>
              <span>{row.subject}</span>
              <span>{row.detail}</span>
              <span>{row.source}</span>
              <span>{row.score}</span>
              <span data-tone={statusTone(row.status)}>{row.status}</span>
              <span>{row.owner}</span>
            </div>
          ))}
        </div>
      )}
      <div className={styles.auditFooter}>
        <span>当前展示 {rows.length} 条</span>
        <span>共 {totalVisibleRows} 条可见记录</span>
      </div>
    </section>
  );
}
