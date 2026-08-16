import type { AgentConversationTurn } from "../lib/agentWorkbenchModel";

type AgentTurnErrorCalloutProps = {
  turn: AgentConversationTurn;
  loading: boolean;
  canRetry: boolean;
  onEditQuestion: (turn: AgentConversationTurn) => void;
  onRetry: (turn: AgentConversationTurn) => void;
};

export function AgentTurnErrorCallout({
  turn,
  loading,
  canRetry,
  onEditQuestion,
  onRetry,
}: AgentTurnErrorCalloutProps) {
  if (turn.error?.kind === "disabled") {
    return (
      <div
        className="agent-callout agent-callout--warning"
        role="status"
        aria-label="Agent 暂不可用"
      >
        智能体当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。
      </div>
    );
  }

  if (turn.error?.kind === "request") {
    return (
      <div className="agent-callout agent-callout--error" role="alert">
        <strong>请求没有送达</strong>
        <span>{turn.error.message}</span>
        {canRetry ? (
          <div className="agent-callout__actions">
            <button
              type="button"
              className="agent-callout__action"
              aria-label={`编辑这句：${turn.question}`}
              onClick={() => onEditQuestion(turn)}
              disabled={loading}
            >
              编辑这句
            </button>
            <button
              type="button"
              className="agent-callout__action"
              aria-label={`重试这一轮：${turn.question}`}
              onClick={() => onRetry(turn)}
              disabled={loading}
            >
              重试这一轮
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  return null;
}
