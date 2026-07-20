import { getAgentRunProgressIndex } from "../lib/agentWorkbenchModel";
import type { AgentRunPayload } from "../lib/agentWorkbenchModel";

const AGENT_RUN_STAGES = ["收到问题", "选择路径", "整理回答"];

export function AgentRunProgress({
  agentRun,
  question,
}: {
  agentRun: AgentRunPayload | null;
  question: string;
}) {
  const currentIndex = getAgentRunProgressIndex(agentRun);

  return (
    <div className="agent-run-progress" aria-label={`回答进度：${question}`}>
      {AGENT_RUN_STAGES.map((stage, index) => {
        const stageIndex = index + 1;
        const isCurrent = stageIndex === currentIndex;
        const isComplete = stageIndex < currentIndex;
        return (
          <div
            key={stage}
            className={
              isCurrent
                ? "agent-run-progress__step agent-run-progress__step--current"
                : isComplete
                  ? "agent-run-progress__step agent-run-progress__step--complete"
                  : "agent-run-progress__step"
            }
            data-current={isCurrent ? "true" : undefined}
          >
            <span className="agent-run-progress__dot" aria-hidden="true" />
            <span>{stage}</span>
          </div>
        );
      })}
    </div>
  );
}
