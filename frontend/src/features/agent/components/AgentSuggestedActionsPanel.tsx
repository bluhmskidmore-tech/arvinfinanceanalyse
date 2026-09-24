type AgentSuggestedAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
  confirmation_token?: string | null;
};

type AgentSuggestedActionsPanelProps = {
  actions: AgentSuggestedAction[];
  formatValue: (value: unknown) => string;
  readOnly?: boolean;
  activePayload: Record<string, unknown> | null;
  pendingConfirmationKey: string | null;
  getActionKey: (action: AgentSuggestedAction) => string;
  onActionClick: (action: AgentSuggestedAction, sourceElement: HTMLElement) => void;
};

export function AgentSuggestedActionsPanel({
  actions,
  formatValue,
  readOnly = false,
  activePayload,
  pendingConfirmationKey,
  getActionKey,
  onActionClick,
}: AgentSuggestedActionsPanelProps) {
  if (actions.length === 0) {
    return null;
  }

  const primaryAction = actions[0];
  const secondaryActions = actions.slice(1);
  if (!primaryAction) {
    return null;
  }

  function closeSecondaryActionsDrawer(sourceElement: HTMLElement) {
    const secondaryActionsDrawer = sourceElement.closest(".agent-suggested-actions__more");
    if (secondaryActionsDrawer instanceof HTMLDetailsElement) {
      secondaryActionsDrawer.open = false;
    }
  }

  function renderActionItem(action: AgentSuggestedAction, index: number) {
    const isReadOnlyExecuteAction = readOnly && action.type === "execute_intent";
    const isPendingConfirmation =
      !isReadOnlyExecuteAction &&
      action.requires_confirmation &&
      getActionKey(action) === pendingConfirmationKey;
    const actionLabel = isPendingConfirmation ? `确认执行：${action.label}` : action.label;
    const badgeLabel = isReadOnlyExecuteAction
      ? "只读 · 仅展示"
      : action.requires_confirmation
        ? "需确认后执行"
        : "可直接继续";

    return (
      <article className="agent-suggested-actions__item" key={`${action.type}-${action.label}-${index}`}>
        <div className="agent-suggested-actions__main">
          <button
            type="button"
            className={
              isPendingConfirmation
                ? "agent-suggested-actions__button agent-suggested-actions__button--confirm"
                : "agent-suggested-actions__button"
            }
            disabled={isReadOnlyExecuteAction}
            onClick={(event) => {
              if (!action.requires_confirmation || isPendingConfirmation) {
                closeSecondaryActionsDrawer(event.currentTarget);
              }
              onActionClick(action, event.currentTarget);
            }}
          >
            {actionLabel}
          </button>
          <span
            className={
              !isReadOnlyExecuteAction && action.requires_confirmation
                ? "agent-suggested-actions__badge agent-suggested-actions__badge--warning"
                : "agent-suggested-actions__badge"
            }
          >
            {badgeLabel}
          </span>
        </div>
        <details className="agent-suggested-actions__details">
          <summary>查看参数</summary>
          <div className="agent-suggested-actions__type">类型：{action.type}</div>
          <pre>{formatValue(action.payload)}</pre>
        </details>
      </article>
    );
  }

  return (
    <section className="agent-suggested-actions" aria-label="接下来可以做">
      <div className="agent-suggested-actions__title">接下来可以做</div>
      <div className="agent-suggested-actions__list">
        {renderActionItem(primaryAction, 0)}
        {secondaryActions.length > 0 ? (
          <details className="agent-suggested-actions__more">
            <summary>更多建议 · {secondaryActions.length} 项</summary>
            <div className="agent-suggested-actions__more-list">
              {secondaryActions.map((action, index) => renderActionItem(action, index + 1))}
            </div>
          </details>
        ) : null}
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
