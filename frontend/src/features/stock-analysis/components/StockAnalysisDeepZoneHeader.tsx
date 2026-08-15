import {
  BarChartOutlined,
  DatabaseOutlined,
  FireOutlined,
  StockOutlined,
} from "@ant-design/icons";

import "../pages/StockAnalysisDeepResearch.css";

import type {
  StockDeepAnalysisGateSummary,
  StockDeepZoneAuditRow,
} from "../lib/stockAnalysisPageModel";

const DEEP_ZONE_AUDIT_ICONS = {
  supply: <DatabaseOutlined aria-hidden="true" />,
  replay: <BarChartOutlined aria-hidden="true" />,
  review: <StockOutlined aria-hidden="true" />,
  events: <FireOutlined aria-hidden="true" />,
} as const;

const DEEP_ZONE_STATUS_FLOW = [
  { label: "阻断", detail: "不可出正式信号" },
  { label: "待复核", detail: "进入人工判断" },
  { label: "证据待齐", detail: "缺口进入队列" },
  { label: "已就绪", detail: "可进入回测" },
] as const;

export function StockAnalysisDeepZoneHeader({
  gateSummary,
  auditRows,
}: {
  gateSummary: StockDeepAnalysisGateSummary;
  auditRows: StockDeepZoneAuditRow[];
}) {
  return (
    <div className="stock-analysis-page__deep-zone-header stock-analysis-page__deep-zone-header--compact">
      <div className="stock-analysis-page__deep-zone-header-row">
        <h2 className="stock-analysis-page__deep-zone-heading">供数闭环</h2>
        <p
          className="stock-analysis-page__deep-zone-gate-summary"
          data-testid="stock-analysis-deep-zone-gate-summary"
          data-tone={gateSummary.tone}
        >
          {gateSummary.line}
        </p>
      </div>
      <details className="stock-analysis-page__deep-zone-detail-shell" data-testid="stock-analysis-deep-zone-detail-shell">
        <summary className="stock-analysis-page__deep-zone-detail-summary">
          <span className="stock-analysis-page__deep-zone-detail-label">供数 / 回放 / 候选 / 事件明细</span>
          <small className="stock-analysis-page__deep-zone-detail-snapshot">
            {auditRows.map((row) => `${row.label} ${row.value}`).join("，")}
          </small>
        </summary>
        <div
          className="stock-analysis-page__deep-zone-audit-strip"
          data-testid="stock-analysis-deep-zone-audit-strip"
        >
          {auditRows.map((row) => (
            <div
              key={row.key}
              className="stock-analysis-page__deep-zone-audit-item"
              data-tone={row.tone}
            >
              <span className="stock-analysis-page__deep-zone-audit-icon">
                {DEEP_ZONE_AUDIT_ICONS[row.key]}
              </span>
              <span className="stock-analysis-page__deep-zone-audit-label">{row.label}</span>
              <strong className="stock-analysis-page__deep-zone-audit-value">{row.value}</strong>
            </div>
          ))}
        </div>
        <div
          className="stock-analysis-page__deep-zone-status-flow"
          data-testid="stock-analysis-deep-zone-status-flow"
          aria-label="状态口径"
        >
          <span className="stock-analysis-page__deep-zone-status-label">状态口径</span>
          {DEEP_ZONE_STATUS_FLOW.map((item, idx) => (
            <div key={item.label} className="stock-analysis-page__deep-zone-status-item">
              {idx > 0 && <span className="stock-analysis-page__deep-zone-status-arrow">→</span>}
              <span className="stock-analysis-page__deep-zone-status-copy">
                <strong className="stock-analysis-page__deep-zone-status-name">{item.label}</strong>
                <em className="stock-analysis-page__deep-zone-status-detail">{item.detail}</em>
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
