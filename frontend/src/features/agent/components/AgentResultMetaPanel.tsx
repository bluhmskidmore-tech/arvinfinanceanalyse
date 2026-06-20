type AgentResultMetaPanelProps = {
  entries: Array<[string, unknown]>;
  formatValue: (value: unknown) => string;
};

const metaKeyLabels: Record<string, string> = {
  trace_id: "追踪编号",
  basis: "口径",
  generated_at: "生成时间",
  result_kind: "结果类型",
  formal_use_allowed: "正式可用",
  source_version: "来源版本",
  vendor_version: "供应商版本",
  rule_version: "规则版本",
  cache_version: "缓存版本",
  quality_flag: "质量标记",
  vendor_status: "供应商状态",
  fallback_mode: "降级模式",
  scenario_flag: "情景标记",
};

const visibleMetaKeys = [
  "trace_id",
  "basis",
  "generated_at",
  "formal_use_allowed",
  "source_version",
  "vendor_version",
  "rule_version",
  "cache_version",
  "quality_flag",
  "vendor_status",
  "fallback_mode",
  "scenario_flag",
];

function formatMetaValue(key: string, value: unknown, fallback: (value: unknown) => string) {
  if (key === "basis") {
    if (value === "formal") return "正式口径";
    if (value === "analytical") return "分析口径";
  }
  if (key === "formal_use_allowed") {
    if (value === true) return "可正式使用";
    if (value === false) return "仅作分析参考";
  }
  if (key === "quality_flag") {
    const labels: Record<string, string> = {
      ok: "正常",
      warning: "预警",
      error: "错误",
      stale: "陈旧",
    };
    if (typeof value === "string" && labels[value]) return labels[value];
  }
  if (key === "vendor_status") {
    const labels: Record<string, string> = {
      ok: "正常",
      vendor_stale: "供应商陈旧",
      vendor_unavailable: "供应商不可用",
    };
    if (typeof value === "string" && labels[value]) return labels[value];
  }
  if (key === "fallback_mode") {
    if (value === "none") return "未降级";
    if (value === "latest_snapshot") return "最新快照降级";
  }
  return fallback(value);
}

function buildVisibleEntries(entries: Array<[string, unknown]>) {
  const entryMap = new Map(entries);
  const visibleEntries = visibleMetaKeys
    .filter((key) => entryMap.has(key))
    .map((key) => [key, entryMap.get(key)] as [string, unknown]);
  return visibleEntries.length > 0 ? visibleEntries : entries.slice(0, 3);
}

export function AgentResultMetaPanel({ entries, formatValue }: AgentResultMetaPanelProps) {
  const visibleEntries = buildVisibleEntries(entries);

  return (
    <div className="agent-side-panel agent-side-panel--meta">
      <div className="agent-side-panel__title">运行信息</div>
      <div className="agent-side-panel__body agent-side-panel__body--rows">
        {visibleEntries.map(([key, value]) => (
          <div className="agent-side-panel__row" key={key}>
            <span>{metaKeyLabels[key] ?? key}</span>
            <strong>{formatMetaValue(key, value, formatValue)}</strong>
          </div>
        ))}
      </div>
      {entries.length > visibleEntries.length ? (
        <details className="agent-side-panel__details">
          <summary>查看全部运行信息</summary>
          <div className="agent-side-panel__body agent-side-panel__body--rows">
            {entries.map(([key, value]) => (
              <div className="agent-side-panel__row" key={key}>
                <span>{metaKeyLabels[key] ?? key}</span>
                <strong>{formatMetaValue(key, value, formatValue)}</strong>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
