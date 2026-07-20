import type { AgentRunEventHandler, AgentRunStreamOptions } from "../../../api/agentRunStream";
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
  _options: WaitForAgentRunTerminalOptions,
): Promise<AgentRunPayload> {
  throw new Error("Agent run status orchestration is not implemented.");
}
