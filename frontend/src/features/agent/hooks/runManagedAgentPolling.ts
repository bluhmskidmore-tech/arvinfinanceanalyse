import type { AgentQueryRequest } from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import {
  AGENT_RUN_POLL_MAX_ATTEMPTS,
  formatManagedRunFailureMessage,
  getAgentRequestClockMs,
  getAgentRunPollIntervalMs,
  normalizeAgentRunRequestLatencyMs,
} from "../lib/agentWorkbenchModel";
import type { AgentRunPayload } from "../lib/agentWorkbenchModel";

type RunManagedAgentPollingOptions = {
  requestBody: AgentQueryRequest;
  createAgentRun: (requestBody: AgentQueryRequest) => Promise<AgentRunPayload>;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  canCommit: () => boolean;
  onRunAccepted: (payload: AgentRunPayload, requestLatencyMs: number) => void;
  onRunUpdate: (payload: AgentRunPayload) => void;
};

/**
 * Owns only managed-run polling orchestration. State mutations remain callbacks
 * so the workbench preserves its existing request-version and React update
 * ordering.
 */
export async function runManagedAgentPolling({
  requestBody,
  createAgentRun,
  fetchAgentRunStatus,
  canCommit,
  onRunAccepted,
  onRunUpdate,
}: RunManagedAgentPollingOptions): Promise<AgentRunPayload> {
  const finalPayload = await runPollingTask<AgentRunPayload>({
    start: async () => {
      const runRequestStartedAtMs = getAgentRequestClockMs();
      const payload = await createAgentRun(requestBody);
      const runRequestLatencyMs = normalizeAgentRunRequestLatencyMs(
        getAgentRequestClockMs() - runRequestStartedAtMs,
      );
      if (canCommit()) {
        onRunAccepted(payload, runRequestLatencyMs);
      }
      return payload;
    },
    getStatus: fetchAgentRunStatus,
    getIntervalMs: getAgentRunPollIntervalMs,
    maxAttempts: AGENT_RUN_POLL_MAX_ATTEMPTS,
    onUpdate: (payload) => {
      if (canCommit()) {
        onRunUpdate(payload);
      }
    },
  });

  if (finalPayload.status === "failed") {
    throw new Error(
      finalPayload.error_message || formatManagedRunFailureMessage(finalPayload.provider),
    );
  }
  if (!finalPayload.result) {
    throw new Error("智能体任务完成但未返回结果。");
  }
  return finalPayload;
}
