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

const DEEP_ZONE_STATUS_FLOW = [
  { label: "阻断", detail: "不可出正式信号" },
  { label: "待复核", detail: "进入人工判断" },
  { label: "证据待齐", detail: "缺口进入队列" },
  { label: "已就绪", detail: "可进入回测" },
] as const;

const getSummaryToneClasses = (tone: string) => {
  switch (tone) {
    case 'positive': return 'text-green-700 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-950/50 dark:border-green-900';
    case 'warning': return 'text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-950/50 dark:border-amber-900';
    case 'critical': return 'text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950/50 dark:border-red-900';
    case 'neutral':
    default:
      return 'text-zinc-700 bg-zinc-50 border-zinc-200 dark:text-zinc-400 dark:bg-zinc-900 dark:border-zinc-800';
  }
};

const getAuditItemClasses = (tone: string) => {
  switch (tone) {
    case 'positive': return 'border-green-200 bg-green-50/50 dark:border-green-900/50 dark:bg-green-950/20';
    case 'warning': return 'border-amber-200 bg-amber-50/50 dark:border-amber-900/50 dark:bg-amber-950/20';
    case 'critical': return 'border-red-200 bg-red-50/50 dark:border-red-900/50 dark:bg-red-950/20';
    case 'neutral':
    default:
      return 'border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/50';
  }
};

export function StockAnalysisDeepZoneHeader({
  gateSummary,
  auditRows,
}: {
  gateSummary: StockDeepAnalysisGateSummary;
  auditRows: StockDeepZoneAuditRow[];
}) {
  return (
    <div className="stock-analysis-page__deep-zone-header--compact flex flex-col gap-6 p-6 bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">供数闭环</h2>
        <p
          className={`stock-analysis-page__deep-zone-gate-summary px-3 py-1 text-sm rounded-full font-medium border ${getSummaryToneClasses(gateSummary.tone)}`}
          data-testid="stock-analysis-deep-zone-gate-summary"
          data-tone={gateSummary.tone}
        >
          {gateSummary.line}
        </p>
      </div>
      <details className="stock-analysis-page__deep-zone-detail-shell" data-testid="stock-analysis-deep-zone-detail-shell">
        <summary className="stock-analysis-page__deep-zone-detail-summary">
          <span>供数 / 回放 / 候选 / 事件明细</span>
          <small>{auditRows.map((row) => `${row.label} ${row.value}`).join(" · ")}</small>
        </summary>
      <div className="stock-analysis-page__deep-zone-audit-strip grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="stock-analysis-deep-zone-audit-strip">
        {auditRows.map((row) => (
          <div
            key={row.key}
            className={`stock-analysis-page__deep-zone-audit-item flex flex-col gap-1 p-4 rounded-lg border ${getAuditItemClasses(row.tone)}`}
            data-tone={row.tone}
          >
            <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400 mb-1">
              <span className="text-lg">{DEEP_ZONE_AUDIT_ICONS[row.key]}</span>
              <span className="text-xs">{row.label}</span>
            </div>
            <strong className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{row.value}</strong>
          </div>
        ))}
      </div>
      <div
        className="stock-analysis-page__deep-zone-status-flow flex flex-wrap items-center gap-4 pt-4 border-t border-zinc-100 dark:border-zinc-800/50"
        data-testid="stock-analysis-deep-zone-status-flow"
        aria-label="状态口径"
      >
        <span className="text-xs text-zinc-400 dark:text-zinc-500 font-medium uppercase tracking-wider">状态口径</span>
        {DEEP_ZONE_STATUS_FLOW.map((item, idx) => (
          <div key={item.label} className="flex items-center gap-2">
            {idx > 0 && <span className="text-zinc-300 dark:text-zinc-700">→</span>}
            <span className="flex items-center gap-1.5 text-xs">
              <strong className="text-zinc-700 dark:text-zinc-300 font-medium">{item.label}</strong>
              <em className="text-zinc-400 dark:text-zinc-500 not-italic">{item.detail}</em>
            </span>
          </div>
        ))}
      </div>
      </details>
    </div>
  );
}
