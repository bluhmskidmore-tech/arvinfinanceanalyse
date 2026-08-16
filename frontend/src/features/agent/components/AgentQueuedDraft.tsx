import { CloseOutlined, EditOutlined } from "@ant-design/icons";

type AgentQueuedDraftProps = {
  queuedQueries: string[];
  onRestoreToComposer: () => void;
  onCancel: () => void;
};

export function AgentQueuedDraft({
  queuedQueries,
  onRestoreToComposer,
  onCancel,
}: AgentQueuedDraftProps) {
  const queuedQuery = queuedQueries[0] ?? "";
  if (!queuedQuery) {
    return null;
  }

  return (
    <div
      className="agent-queued-draft"
      role="status"
      aria-live="polite"
      aria-label="待发送的下一句"
    >
      <div className="agent-queued-draft__copy">
        <div className="agent-queued-draft__header">
          <span className="agent-queued-draft__label">下一句</span>
          <span className="agent-queued-draft__count">{queuedQueries.length} 句待发送</span>
        </div>
        <span className="agent-queued-draft__text">{queuedQuery}</span>
        {queuedQueries.length > 1 ? (
          <ol className="agent-queued-draft__queue" aria-label="待发送的后续问题">
            {queuedQueries.slice(1).map((queuedItem, index) => (
              <li key={`${queuedItem}-${index}`}>
                <span>#{index + 2}</span>
                <span>{queuedItem}</span>
              </li>
            ))}
          </ol>
        ) : null}
        <span className="agent-queued-draft__hint">当前回答完成后发送</span>
      </div>
      <div className="agent-queued-draft__actions">
        <button
          type="button"
          className="agent-queued-draft__action"
          aria-label={`编辑草稿：${queuedQuery}`}
          onClick={onRestoreToComposer}
        >
          <EditOutlined aria-hidden="true" />
          <span>编辑草稿</span>
        </button>
        <button
          type="button"
          className="agent-queued-draft__action"
          aria-label={`取消草稿：${queuedQuery}`}
          onClick={onCancel}
        >
          <CloseOutlined aria-hidden="true" />
          <span>取消草稿</span>
        </button>
      </div>
    </div>
  );
}
