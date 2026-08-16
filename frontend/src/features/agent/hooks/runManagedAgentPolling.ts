import type { AgentQueryRequest } from "../../../api/contracts";
import {
  AgentRunCancelledError,
  formatManagedRunFailureMessage,
  getAgentRequestClockMs,
  normalizeAgentRunRequestLatencyMs,
} from "../lib/agentWorkbenchModel";
import type { AgentQueryResult, AgentRunPayload } from "../lib/agentWorkbenchModel";
import {
  waitForAgentRunTerminal,
  type StreamAgentRunEvents,
} from "./agentRunStatusOrchestrator";

type RunManagedAgentPollingOptions = {
  requestBody: AgentQueryRequest;
  createAgentRun: (requestBody: AgentQueryRequest) => Promise<AgentRunPayload>;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  canCommit: () => boolean;
  onRunAccepted: (payload: AgentRunPayload, requestLatencyMs: number | undefined) => void;
  onRunUpdate: (payload: AgentRunPayload) => void;
  streamAgentRunEvents?: StreamAgentRunEvents;
  signal?: AbortSignal;
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
  streamAgentRunEvents,
  signal,
}: RunManagedAgentPollingOptions): Promise<AgentRunPayload & { result: AgentQueryResult }> {
  const runRequestStartedAtMs = getAgentRequestClockMs();
  const initialPayload = await createAgentRun(requestBody);
  const runRequestLatencyMs = normalizeAgentRunRequestLatencyMs(
    getAgentRequestClockMs() - runRequestStartedAtMs,
  );
  if (canCommit()) {
    onRunAccepted(initialPayload, runRequestLatencyMs);
  }

  const finalPayload = await waitForAgentRunTerminal({
    runId: initialPayload.run_id,
    initialPayload,
    streamAgentRunEvents,
    fetchAgentRunStatus,
    canCommit,
    onRunUpdate,
    signal,
  });

  if (finalPayload.status === "failed") {
    throw new Error(
      finalPayload.error_message || formatManagedRunFailureMessage(finalPayload.provider),
    );
  }
  if (finalPayload.status === "cancelled") {
    throw new AgentRunCancelledError(finalPayload);
  }
  if (!finalPayload.result) {
    throw new Error("智能体任务完成但未返回结果。");
  }
  return { ...finalPayload, result: finalPayload.result };
}
