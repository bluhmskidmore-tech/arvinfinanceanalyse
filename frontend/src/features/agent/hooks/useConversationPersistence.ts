import { useEffect, useRef, useState } from "react";

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

const COMPOSER_DRAFT_PERSIST_IDLE_MS = 250;

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
  const composerDraftPersistTimerRef = useRef<number | null>(null);
  const latestComposerDraftRef = useRef(query);
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

  useEffect(() => {
    return () => {
      if (composerDraftPersistTimerRef.current !== null) {
        window.clearTimeout(composerDraftPersistTimerRef.current);
        composerDraftPersistTimerRef.current = null;
      }
      if (!shouldPersistConversation) {
        return;
      }
      if (latestComposerDraftRef.current.trim()) {
        persistComposerDraft(latestComposerDraftRef.current);
      } else {
        clearComposerDraft();
      }
    };
  }, [shouldPersistConversation]);

  function cancelScheduledComposerDraftPersistence() {
    if (composerDraftPersistTimerRef.current === null) {
      return;
    }
    window.clearTimeout(composerDraftPersistTimerRef.current);
    composerDraftPersistTimerRef.current = null;
  }

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
    latestComposerDraftRef.current = nextQuery;
    if (!shouldPersistConversation) {
      return;
    }
    cancelScheduledComposerDraftPersistence();
    composerDraftPersistTimerRef.current = window.setTimeout(() => {
      composerDraftPersistTimerRef.current = null;
      persistComposerDraft(latestComposerDraftRef.current);
    }, COMPOSER_DRAFT_PERSIST_IDLE_MS);
  }

  function clearComposerDraftState() {
    setQuery("");
    latestComposerDraftRef.current = "";
    cancelScheduledComposerDraftPersistence();
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
