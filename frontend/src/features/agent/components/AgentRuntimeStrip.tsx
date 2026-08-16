import type { buildRuntimeStatus } from "../lib/agentWorkbenchModel";

type AgentRuntimeStatus = ReturnType<typeof buildRuntimeStatus>;

export function AgentRuntimeStrip({
  loading,
  stateLabel,
  runtimeStatus,
}: {
  loading: boolean;
  stateLabel: string;
  runtimeStatus: AgentRuntimeStatus;
}) {
  return (
    <div
      className="agent-runtime-strip"
      role="status"
      aria-label="Agent 连接状态"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="agent-runtime-strip__summary">
        <div className="agent-runtime-strip__state">
          <span className={loading ? "agent-runtime-strip__dot agent-runtime-strip__dot--active" : "agent-runtime-strip__dot"} />
          <span>{stateLabel}</span>
          <span className="agent-runtime-strip__provider">{runtimeStatus.provider}</span>
        </div>
      </div>
      <details className="agent-runtime-strip__details">
        <summary>运行详情</summary>
        <div className="agent-runtime-strip__detail-grid">
          <div className="agent-runtime-strip__item">
            <span>Engine</span>
            <strong>{runtimeStatus.provider}</strong>
          </div>
          <div className="agent-runtime-strip__item">
            <span>Transport</span>
            <strong>{runtimeStatus.transport}</strong>
          </div>
          <div className="agent-runtime-strip__item">
            <span>Model</span>
            <strong>{runtimeStatus.model}</strong>
          </div>
          <div className="agent-runtime-strip__item">
            <span>Tools</span>
            <strong>{runtimeStatus.toolsets}</strong>
          </div>
          <div className="agent-runtime-strip__item">
            <span>Quality</span>
            <strong>{runtimeStatus.quality}</strong>
          </div>
        </div>
      </details>
    </div>
  );
}
