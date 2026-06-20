import {
  BarChartOutlined,
  DatabaseOutlined,
  FireOutlined,
  StockOutlined,
} from "@ant-design/icons";

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

export function StockAnalysisDeepZoneHeader({
  gateSummary,
  auditRows,
}: {
  gateSummary: StockDeepAnalysisGateSummary;
  auditRows: StockDeepZoneAuditRow[];
}) {
  return (
    <div className="stock-analysis-page__deep-zone-head">
      <div className="stock-analysis-page__deep-zone-title">
        <h2>供数闭环</h2>
        <p
          className="stock-analysis-page__deep-zone-gate-summary"
          data-testid="stock-analysis-deep-zone-gate-summary"
          data-tone={gateSummary.tone}
        >
          {gateSummary.line}
        </p>
      </div>
      <div className="stock-analysis-page__deep-zone-audit-strip" data-testid="stock-analysis-deep-zone-audit-strip">
        {auditRows.map((row) => (
          <div
            key={row.key}
            className="stock-analysis-page__deep-zone-audit-item"
            data-tone={row.tone}
          >
            <span className="stock-analysis-page__deep-zone-audit-icon">{DEEP_ZONE_AUDIT_ICONS[row.key]}</span>
            <span className="stock-analysis-page__deep-zone-audit-label">{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
