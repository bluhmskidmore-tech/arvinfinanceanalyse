import { shellTokens as t } from "../../../theme/tokens";

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

export function AgentResultMetaPanel({ entries, formatValue }: AgentResultMetaPanelProps) {
  return (
    <div
      style={{
        padding: 16,
        borderRadius: 14,
        border: `1px solid ${t.colorBorderSoft}`,
        background: t.colorBgSurface,
      }}
    >
      <div
        style={{
          color: t.colorTextMuted,
          fontSize: 12,
          marginBottom: 8,
        }}
      >
        结果元信息
      </div>
      <div
        style={{
          fontSize: 13,
          color: t.colorTextSecondary,
          lineHeight: 1.7,
        }}
      >
        {entries.map(([key, value]) => (
          <div key={key}>
            {metaKeyLabels[key] ?? key}: {formatValue(value)}
          </div>
        ))}
      </div>
    </div>
  );
}
