import { formatAgentRunStopReason } from "../lib/agentWorkbenchModel";
import type { AgentConversationTurn } from "../lib/agentWorkbenchModel";

type AgentTurnErrorCalloutProps = {
  turn: AgentConversationTurn;
  loading: boolean;
  canRetry: boolean;
  canReconnect?: boolean;
  onEditQuestion: (turn: AgentConversationTurn) => void;
  onRetry: (turn: AgentConversationTurn) => void;
};

export function AgentTurnErrorCallout({
  turn,
  loading,
  canRetry,
  canReconnect = false,
  onEditQuestion,
  onRetry,
}: AgentTurnErrorCalloutProps) {
  const stopReasonText = formatAgentRunStopReason(turn.agentRun?.stop_reason);

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
        <strong>{canReconnect ? "连接中断" : turn.agentRun?.status === "failed" ? "任务执行失败" : turn.agentRun?.status === "completed" ? "任务未返回结果" : "请求没有送达"}</strong>
        <span>{turn.error.message}</span>
        {stopReasonText ? <span>{stopReasonText}</span> : null}
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
              aria-label={`${canReconnect ? "重新连接" : "重试这一轮"}：${turn.question}`}
              onClick={() => onRetry(turn)}
              disabled={loading}
            >
              {canReconnect ? "重新连接" : "重试这一轮"}
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  if (stopReasonText) {
    return (
      <div className="agent-callout agent-callout--stopped" role="status">
        <span>{stopReasonText}</span>
      </div>
    );
  }

  return null;
}
