type AgentEvidencePanelProps = {
  tablesUsed: string[];
  filtersApplied: Record<string, unknown>;
  sqlExecuted?: string[];
  evidenceRows: number;
  qualityFlag: string;
};

const qualityLabels: Record<string, string> = {
  ok: "正常",
  warning: "需留意",
  error: "异常",
  stale: "可能陈旧",
};

function formatEvidenceValue(value: unknown): string {
  if (value === null) return "空";
  if (Array.isArray(value)) return value.map(formatEvidenceValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function formatFilterSummary(filtersApplied: Record<string, unknown>) {
  const entries = Object.entries(filtersApplied);
  if (entries.length === 0) {
    return "未应用额外筛选";
  }
  return entries.map(([key, value]) => `${key}: ${formatEvidenceValue(value)}`).join("；");
}

export function AgentEvidencePanel({
  tablesUsed,
  filtersApplied,
  sqlExecuted = [],
  evidenceRows,
  qualityFlag,
}: AgentEvidencePanelProps) {
  const rawFilters = JSON.stringify(filtersApplied, null, 2);

  return (
    <div className="agent-side-panel agent-side-panel--evidence">
      <div className="agent-side-panel__title">回答依据</div>
      <div className="agent-side-panel__body agent-side-panel__body--rows">
        <div className="agent-side-panel__row">
          <span>来源</span>
          <strong>{tablesUsed.length > 0 ? tablesUsed.join(", ") : "未返回来源表"}</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>过滤</span>
          <strong>{formatFilterSummary(filtersApplied)}</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>证据行数</span>
          <strong>{evidenceRows} 行</strong>
        </div>
        <div className="agent-side-panel__row">
          <span>质量</span>
          <strong>{qualityLabels[qualityFlag] ?? qualityFlag}</strong>
        </div>
      </div>
      <details className="agent-side-panel__details">
        <summary>查看筛选参数</summary>
        <pre>{rawFilters}</pre>
      </details>
      {sqlExecuted.length > 0 ? (
        <details className="agent-side-panel__details" data-testid="agent-evidence-sql">
          <summary>查看执行 SQL · {sqlExecuted.length} 条</summary>
          <div className="agent-side-panel__sql-list">
            {sqlExecuted.map((sql, index) => (
              <pre key={`sql-${index}`}>{sql}</pre>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
