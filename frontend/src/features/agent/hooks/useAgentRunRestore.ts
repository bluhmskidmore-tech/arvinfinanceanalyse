import { useEffect } from "react";

import {
  AGENT_RUN_POLL_MAX_ATTEMPTS,
  formatManagedRunFailureMessage,
  getAgentRunPollIntervalMs,
  latestAgentRunStatusRequests,
  mergeRestoredManagedTurn,
} from "../lib/agentWorkbenchModel";
import type {
  AgentOrdinaryConversationMode,
  AgentQueryError,
  AgentQueryResult,
  AgentRunPayload,
  AgentConversationTurn,
} from "../lib/agentWorkbenchModel";
import { clearLatestAgentRunId, loadLatestAgentRunId } from "../lib/agentWorkbenchStorage";
import { runPollingTask } from "../../../app/jobs/polling";

type UseAgentRunRestoreOptions = {
  shouldPersistConversation: boolean;
  currentConversationSession: () => number;
  isCurrentConversationSession: (session: number) => boolean;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  setRestoringRunId: (runId: string) => void;
  setRestoreErrorRunId: (runId: string) => void;
  setOrdinaryConversationMode: (mode: AgentOrdinaryConversationMode) => void;
  setAgentRun: (run: AgentRunPayload | null) => void;
  setConversationTurns: (
    updater: (currentTurns: AgentConversationTurn[]) => AgentConversationTurn[],
  ) => void;
  setResult: (result: AgentQueryResult | null) => void;
  setError: (error: AgentQueryError | null) => void;
};

/**
 * Restores the latest managed Hermes/Dexter/local run after a workbench remount.
 * Dependency array intentionally matches the previous in-page effect: only
 * `shouldPersistConversation`, so the fetch closure is captured from the first
 * render the same way as before.
 */
export function useAgentRunRestore({
  shouldPersistConversation,
  currentConversationSession,
  isCurrentConversationSession,
  fetchAgentRunStatus,
  setRestoringRunId,
  setRestoreErrorRunId,
  setOrdinaryConversationMode,
  setAgentRun,
  setConversationTurns,
  setResult,
  setError,
}: UseAgentRunRestoreOptions) {
  useEffect(() => {
    if (!shouldPersistConversation) {
      return;
    }
    const latestRunId = loadLatestAgentRunId();
    if (!latestRunId) {
      return;
    }

    let cancelled = false;
    const restoreSession = currentConversationSession();
    setRestoringRunId(latestRunId);
    let restoreRequest = latestAgentRunStatusRequests.get(latestRunId);
    if (!restoreRequest) {
      restoreRequest = fetchAgentRunStatus(latestRunId).finally(() => {
        latestAgentRunStatusRequests.delete(latestRunId);
      });
      latestAgentRunStatusRequests.set(latestRunId, restoreRequest);
    }
    void restoreRequest
      .then((payload) =>
        runPollingTask<AgentRunPayload>({
          start: async () => payload,
          getStatus: fetchAgentRunStatus,
          getIntervalMs: getAgentRunPollIntervalMs,
          maxAttempts: AGENT_RUN_POLL_MAX_ATTEMPTS,
          onUpdate: (nextPayload) => {
            if (cancelled || !isCurrentConversationSession(restoreSession)) {
              return;
            }
            setOrdinaryConversationMode("managed");
            setAgentRun(nextPayload);
            setConversationTurns((currentTurns) => mergeRestoredManagedTurn(currentTurns, nextPayload));
          },
        }),
      )
      .then((payload) => {
        if (cancelled || !isCurrentConversationSession(restoreSession)) {
          return;
        }
        setRestoringRunId("");
        setRestoreErrorRunId("");
        setOrdinaryConversationMode("managed");
        setAgentRun(payload);
        setConversationTurns((currentTurns) => mergeRestoredManagedTurn(currentTurns, payload));
        if (payload.status === "completed" && payload.result) {
          setResult(payload.result);
        }
        if (payload.status === "failed") {
          setError({
            kind: "request",
            message: payload.error_message || formatManagedRunFailureMessage(payload.provider),
          });
        }
      })
      .catch(() => {
        if (cancelled || !isCurrentConversationSession(restoreSession)) {
          return;
        }
        setRestoringRunId("");
        setRestoreErrorRunId(latestRunId);
        clearLatestAgentRunId();
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preserve prior restore effect deps
  }, [shouldPersistConversation]);
}
