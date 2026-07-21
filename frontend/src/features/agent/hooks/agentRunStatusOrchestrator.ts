import {
  streamAgentRunEvents as defaultStreamAgentRunEvents,
  type AgentRunEventHandler,
  type AgentRunStreamOptions,
} from "../../../api/agentRunStream";
import { runPollingTask } from "../../../app/jobs/polling";
import {
  AGENT_RUN_POLL_MAX_ATTEMPTS,
  getAgentRunPollIntervalMs,
  isAgentRunPayload,
  normalizeAgentRunPayload,
} from "../lib/agentWorkbenchModel";
import type { AgentRunPayload } from "../lib/agentWorkbenchModel";

export type StreamAgentRunEvents = (
  runId: string,
  onEvent: AgentRunEventHandler,
  options?: AgentRunStreamOptions,
) => Promise<void>;

type WaitForAgentRunTerminalOptions = {
  runId: string;
  initialPayload?: AgentRunPayload;
  streamAgentRunEvents?: StreamAgentRunEvents;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  canCommit: () => boolean;
  onRunUpdate: (payload: AgentRunPayload) => void;
  signal?: AbortSignal;
};

export async function waitForAgentRunTerminal(
  options: WaitForAgentRunTerminalOptions,
): Promise<AgentRunPayload> {
  const {
    runId,
    initialPayload,
    fetchAgentRunStatus,
    canCommit,
    onRunUpdate,
    signal,
  } = options;
  const streamAgentRunEvents = options.streamAgentRunEvents ?? defaultStreamAgentRunEvents;
  let latestPayload = initialPayload;
  let terminalPayload = isTerminalPayload(initialPayload) ? initialPayload : undefined;
  let lastSnapshot = initialPayload ? JSON.stringify(initialPayload) : undefined;

  const publishSnapshot = (payload: AgentRunPayload) => {
    latestPayload = payload;
    const snapshot = JSON.stringify(payload);
    if (snapshot === lastSnapshot) {
      return;
    }
    lastSnapshot = snapshot;
    if (canCommit()) {
      onRunUpdate(payload);
    }
  };

  if (terminalPayload) {
    return terminalPayload;
  }

  let streamPayloadInvalid = false;
  try {
    await streamAgentRunEvents(
      runId,
      (value) => {
        if (!isAgentRunPayload(value) || value.run_id !== runId) {
          streamPayloadInvalid = true;
          return true;
        }
        const payload = normalizeAgentRunPayload(value);
        publishSnapshot(payload);
        if (isTerminalPayload(payload)) {
          terminalPayload = payload;
          return true;
        }
        return false;
      },
      { signal },
    );
  } catch {
    // A disconnected or unsupported SSE path falls through to GET polling.
  }

  if (terminalPayload) {
    return terminalPayload;
  }
  throwIfAborted(signal);

  const fallbackPayload = await runPollingTask<AgentRunPayload>({
    start: async () => latestPayload ?? fetchAgentRunStatus(runId),
    getStatus: fetchAgentRunStatus,
    getIntervalMs: getAgentRunPollIntervalMs,
    maxAttempts: AGENT_RUN_POLL_MAX_ATTEMPTS,
    onUpdate: publishSnapshot,
  });

  if (streamPayloadInvalid && fallbackPayload.run_id !== runId) {
    throw new Error("Agent run status response does not match the requested run.");
  }
  return fallbackPayload;
}

function isTerminalPayload(payload: AgentRunPayload | undefined): payload is AgentRunPayload {
  return payload?.status === "completed" || payload?.status === "failed";
}

function throwIfAborted(signal: AbortSignal | undefined) {
  if (!signal?.aborted) {
    return;
  }
  const error = new Error("Agent run wait was aborted.");
  error.name = "AbortError";
  throw error;
}
