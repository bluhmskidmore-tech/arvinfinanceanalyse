import { useEffect, useRef } from "react";

import {
  formatManagedRunFailureMessage,
  getAgentApiErrorStatus,
  isTerminalAgentRunStatus,
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
import { isAbortError, pollAgentRunUntilTerminal } from "./agentRunStatusOrchestrator";

type UseAgentRunRestoreOptions = {
  shouldPersistConversation: boolean;
  currentConversationSession: () => number;
  isCurrentConversationSession: (session: number) => boolean;
  fetchAgentRunStatus: (runId: string) => Promise<AgentRunPayload>;
  setRestoringRunId: (runId: string) => void;
  setRestoreErrorRunId: (runId: string, retryable?: boolean) => void;
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
 *
 * 回调经由 ref 读取最新闭包，effect 只依赖 `shouldPersistConversation`：既保持
 * "每次挂载只恢复一次"的既有语义，又不需要关闭 exhaustive-deps 规则。
 * 恢复到终态（completed/failed/cancelled）后清除 latest run id，避免每次挂载都
 * 重复 GET 一个已经结束的 run。
 */
export function useAgentRunRestore(options: UseAgentRunRestoreOptions) {
  const { shouldPersistConversation } = options;
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    if (!shouldPersistConversation) {
      return;
    }
    const latestRunId = loadLatestAgentRunId();
    if (!latestRunId) {
      return;
    }

    let cancelled = false;
    const abortController = new AbortController();
    const restoreSession = optionsRef.current.currentConversationSession();
    let lastFetchErrorStatus: number | null = null;
    const fetchAgentRunStatus = async (runId: string) => {
      try {
        const payload = await optionsRef.current.fetchAgentRunStatus(runId);
        lastFetchErrorStatus = null;
        return payload;
      } catch (error) {
        lastFetchErrorStatus = getAgentApiErrorStatus(error);
        throw error;
      }
    };
    const isCurrentRestoreSession = () =>
      optionsRef.current.isCurrentConversationSession(restoreSession);
    optionsRef.current.setRestoringRunId(latestRunId);
    let restoreRequest = latestAgentRunStatusRequests.get(latestRunId);
    if (!restoreRequest) {
      restoreRequest = fetchAgentRunStatus(latestRunId).finally(() => {
        latestAgentRunStatusRequests.delete(latestRunId);
      });
      latestAgentRunStatusRequests.set(latestRunId, restoreRequest);
    }
    void restoreRequest
      .then((payload) =>
        pollAgentRunUntilTerminal({
          runId: latestRunId,
          initialPayload: payload,
          fetchAgentRunStatus,
          signal: abortController.signal,
          onUpdate: (nextPayload) => {
            if (cancelled || !isCurrentRestoreSession()) {
              return;
            }
            optionsRef.current.setOrdinaryConversationMode("managed");
            optionsRef.current.setAgentRun(nextPayload);
            optionsRef.current.setConversationTurns((currentTurns) =>
              mergeRestoredManagedTurn(currentTurns, nextPayload),
            );
          },
        }),
      )
      .then((payload) => {
        if (cancelled || !isCurrentRestoreSession()) {
          return;
        }
        optionsRef.current.setRestoringRunId("");
        optionsRef.current.setRestoreErrorRunId("");
        optionsRef.current.setOrdinaryConversationMode("managed");
        optionsRef.current.setAgentRun(payload);
        optionsRef.current.setConversationTurns((currentTurns) =>
          mergeRestoredManagedTurn(currentTurns, payload),
        );
        if (payload.status === "completed" && payload.result) {
          optionsRef.current.setResult(payload.result);
        }
        if (payload.status === "failed") {
          optionsRef.current.setError({
            kind: "request",
            message: payload.error_message || formatManagedRunFailureMessage(payload.provider),
          });
        }
        if (
          isTerminalAgentRunStatus(payload.status) &&
          loadLatestAgentRunId() === latestRunId
        ) {
          // 已结束的 run 没有后续状态可接回：清除标记，下次挂载不再重复 GET。
          clearLatestAgentRunId();
        }
      })
      .catch((error) => {
        if (cancelled || isAbortError(error) || !isCurrentRestoreSession()) {
          return;
        }
        // 轮询耗尽重试后会包装错误，仍按最后一次 GET 区分任务不可访问与暂时断线。
        const status = getAgentApiErrorStatus(error) ?? lastFetchErrorStatus;
        optionsRef.current.setRestoringRunId("");
        optionsRef.current.setRestoreErrorRunId(latestRunId, status !== 403 && status !== 404);
        if ((status === 403 || status === 404) && loadLatestAgentRunId() === latestRunId) {
          clearLatestAgentRunId();
        }
      });
    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [shouldPersistConversation]);
}
