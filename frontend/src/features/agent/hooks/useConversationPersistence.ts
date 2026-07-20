import { useEffect, useState } from "react";

import type { AgentConversationTurn } from "../lib/agentWorkbenchModel";
import {
  clearComposerDraft,
  clearLatestAgentRunId,
  clearStoredQueuedQueries,
  loadComposerDraft,
  loadLatestAgentRunId,
  loadPinnedRepoPaths,
  loadQueuedQueries,
  loadRecentRepoPaths,
  loadStoredConversationTurns,
  movePinnedRepoPathValue,
  persistComposerDraft,
  persistLatestAgentRunId,
  persistPinnedRepoPaths,
  persistQueuedQueries,
  persistRecentRepoPaths,
  persistStoredConversationTurns,
  pinRepoPathValue,
  rememberRepoPathValue,
  unpinRepoPathValue,
} from "../lib/agentWorkbenchStorage";

type UseConversationPersistenceOptions = {
  shouldPersistConversation: boolean;
  defaultQuestion: string;
  variant: "workbench" | "embedded";
};

/**
 * Owns workbench localStorage-backed conversation state and the write-through
 * effects for turns / queued queries. Behavior matches the previous in-page
 * useState + useEffect wiring.
 */
export function useConversationPersistence({
  shouldPersistConversation,
  defaultQuestion,
  variant,
}: UseConversationPersistenceOptions) {
  const [recentRepoPaths, setRecentRepoPaths] = useState<string[]>(() => loadRecentRepoPaths());
  const [pinnedRepoPaths, setPinnedRepoPaths] = useState<string[]>(() => loadPinnedRepoPaths());
  const [query, setQuery] = useState(() =>
    defaultQuestion || (variant === "workbench" ? loadComposerDraft() : ""),
  );
  const [conversationTurns, setConversationTurns] = useState<AgentConversationTurn[]>(() =>
    shouldPersistConversation ? loadStoredConversationTurns() : [],
  );
  const [queuedQueries, setQueuedQueries] = useState<string[]>(() =>
    shouldPersistConversation ? loadQueuedQueries() : [],
  );
  const [initialRestoringRunId] = useState(() =>
    shouldPersistConversation ? loadLatestAgentRunId() : "",
  );

  useEffect(() => {
    if (!shouldPersistConversation) {
      return;
    }
    persistStoredConversationTurns(conversationTurns);
  }, [conversationTurns, shouldPersistConversation]);

  useEffect(() => {
    if (!shouldPersistConversation) {
      return;
    }
    persistQueuedQueries(queuedQueries);
  }, [queuedQueries, shouldPersistConversation]);

  function rememberRepoPath(nextRepoPath: string) {
    setRecentRepoPaths((currentPaths) => {
      const nextPaths = rememberRepoPathValue(currentPaths, nextRepoPath);
      persistRecentRepoPaths(nextPaths);
      return nextPaths;
    });
  }

  function pinRepoPath(nextRepoPath: string) {
    setPinnedRepoPaths((currentPaths) => {
      const nextPaths = pinRepoPathValue(currentPaths, nextRepoPath);
      persistPinnedRepoPaths(nextPaths);
      return nextPaths;
    });
  }

  function unpinRepoPath(path: string) {
    setPinnedRepoPaths((currentPaths) => {
      const nextPaths = unpinRepoPathValue(currentPaths, path);
      persistPinnedRepoPaths(nextPaths);
      return nextPaths;
    });
  }

  function movePinnedRepoPath(path: string, direction: "up" | "down") {
    setPinnedRepoPaths((currentPaths) => {
      const nextPaths = movePinnedRepoPathValue(currentPaths, path, direction);
      persistPinnedRepoPaths(nextPaths);
      return nextPaths;
    });
  }

  function writeComposerDraft(nextQuery: string) {
    setQuery(nextQuery);
    if (shouldPersistConversation) {
      persistComposerDraft(nextQuery);
    }
  }

  function clearComposerDraftState() {
    setQuery("");
    if (shouldPersistConversation) {
      clearComposerDraft();
    }
  }

  function clearQueuedQueries() {
    setQueuedQueries([]);
    if (shouldPersistConversation) {
      clearStoredQueuedQueries();
    }
  }

  function clearPersistedLatestRunId() {
    if (shouldPersistConversation) {
      clearLatestAgentRunId();
    }
  }

  function persistPersistedLatestRunId(runId: string) {
    if (shouldPersistConversation) {
      persistLatestAgentRunId(runId);
    }
  }

  function persistConversationTurnsNow(turns: AgentConversationTurn[]) {
    if (shouldPersistConversation) {
      persistStoredConversationTurns(turns);
    }
  }

  return {
    recentRepoPaths,
    pinnedRepoPaths,
    query,
    setQuery,
    conversationTurns,
    setConversationTurns,
    queuedQueries,
    setQueuedQueries,
    initialRestoringRunId,
    rememberRepoPath,
    pinRepoPath,
    unpinRepoPath,
    movePinnedRepoPath,
    writeComposerDraft,
    clearComposerDraftState,
    clearQueuedQueries,
    clearPersistedLatestRunId,
    persistPersistedLatestRunId,
    persistConversationTurnsNow,
  };
}
