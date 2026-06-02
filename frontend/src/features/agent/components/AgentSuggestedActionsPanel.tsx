type AgentSuggestedAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
};

type AgentSuggestedActionsPanelProps = {
  actions: AgentSuggestedAction[];
  formatValue: (value: unknown) => string;
  activePayload: Record<string, unknown> | null;
  onActionClick: (action: AgentSuggestedAction) => void;
};

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
    <section className="agent-suggested-actions" aria-label="接下来可以做">
      <div className="agent-suggested-actions__title">接下来可以做</div>
      <div className="agent-suggested-actions__list">
        {actions.map((action, index) => (
          <article className="agent-suggested-actions__item" key={`${action.type}-${action.label}-${index}`}>
            <div className="agent-suggested-actions__main">
              <button
                type="button"
                className="agent-suggested-actions__button"
                onClick={() => onActionClick(action)}
              >
                {action.label}
              </button>
              <span
                className={
                  action.requires_confirmation
                    ? "agent-suggested-actions__badge agent-suggested-actions__badge--warning"
                    : "agent-suggested-actions__badge"
                }
              >
                {action.requires_confirmation ? "需确认后执行" : "可直接继续"}
              </span>
            </div>
            <details className="agent-suggested-actions__details">
              <summary>查看参数</summary>
              <div className="agent-suggested-actions__type">类型：{action.type}</div>
              <pre>{formatValue(action.payload)}</pre>
            </details>
          </article>
        ))}
      </div>
      {activePayload ? (
        <div className="agent-suggested-actions__active">
          <div className="agent-suggested-actions__active-title">已选择的参数</div>
          <pre>{formatValue(activePayload)}</pre>
        </div>
      ) : null}
    </section>
  );
}
