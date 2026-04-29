import { shellTokens as t } from "../../../theme/tokens";

type AgentSuggestedAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
};

type AgentSuggestedActionPresentation = AgentSuggestedAction & {
  detailsLabel: string;
  detailsExpanded: boolean;
};

type AgentSuggestedActionsPanelProps = {
  actions: AgentSuggestedActionPresentation[];
  formatValue: (value: unknown) => string;
  activePayload: Record<string, unknown> | null;
  onActionClick: (action: AgentSuggestedAction) => void;
};

function resolveActionButtonLabel(action: AgentSuggestedAction) {
  if (action.type === "inspect_drill" || action.type === "refine_query") {
    return action.label;
  }
  return `${action.label} · 查看详情`;
}

export function AgentSuggestedActionsPanel({
  actions,
  formatValue,
  activePayload,
  onActionClick,
}: AgentSuggestedActionsPanelProps) {
  if (actions.length === 0) {
    return null;
  }

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
          marginBottom: 10,
        }}
      >
        建议动作
      </div>
      <div
        style={{
          display: "grid",
          gap: 10,
        }}
      >
        {actions.map((action, index) => (
          <div
            key={`${action.type}-${action.label}-${index}`}
            style={{
              display: "grid",
              gap: 8,
              padding: 12,
              borderRadius: 12,
              border: `1px solid ${t.colorBorderSoft}`,
              background: t.colorBgCanvas,
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <button
                type="button"
                onClick={() => onActionClick(action)}
                aria-expanded={action.detailsExpanded}
                style={{
                  padding: "7px 11px",
                  borderRadius: 999,
                  border: `1px solid ${t.colorBorder}`,
                  background: action.detailsExpanded ? t.colorAccentSoft : t.colorBgSurface,
                  color: t.colorTextPrimary,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {resolveActionButtonLabel(action)}
              </button>
              <span style={{ color: t.colorTextSecondary, fontSize: 12 }}>{action.type}</span>
              {action.requires_confirmation ? (
                <span style={{ color: t.colorTextWarning, fontSize: 12 }}>需确认后执行</span>
              ) : null}
              <span style={{ color: t.colorTextMuted, fontSize: 12 }}>{action.detailsLabel}</span>
            </div>
            <pre
              style={{
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                color: t.colorTextSecondary,
                fontSize: 12,
                lineHeight: 1.6,
              }}
            >
              {formatValue(action.payload)}
            </pre>
          </div>
        ))}
      </div>
      {activePayload ? (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 12,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgMuted,
          }}
        >
          <div style={{ color: t.colorTextMuted, fontSize: 12, marginBottom: 8 }}>
            动作载荷 / 血缘信息
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              color: t.colorTextSecondary,
              fontSize: 12,
              lineHeight: 1.6,
            }}
          >
            {formatValue(activePayload)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
