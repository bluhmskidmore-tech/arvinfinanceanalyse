import { shellTokens as t } from "../../../theme/tokens";

type AgentResultMetaPanelProps = {
  entries: Array<[string, unknown]>;
  formatValue: (value: unknown) => string;
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
            {key}: {formatValue(value)}
          </div>
        ))}
      </div>
    </div>
  );
}
