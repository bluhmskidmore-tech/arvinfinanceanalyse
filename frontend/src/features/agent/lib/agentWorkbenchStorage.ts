import {
  MAX_AGENT_QUEUED_QUERIES,
  MAX_AGENT_STORED_TURNS,
  isAgentConversationContext,
  isAgentQueryError,
  isAgentQueryResult,
  isAgentRunPayload,
  isRecord,
  normalizeAgentResult,
  normalizeAgentRunPayload,
  normalizeAgentRunRequestLatencyMs,
} from "./agentWorkbenchModel";
import type {
  AgentConversationTurn,
} from "./agentWorkbenchModel";

export const LATEST_AGENT_RUN_ID_KEY = "moss.agent.latestRunId.v1";

export const AGENT_CONVERSATION_TURNS_KEY = "moss.agent.conversationTurns.v1";

export const AGENT_QUEUED_QUERIES_KEY = "moss.agent.queuedQueries.v1";

export const RECENT_REPO_PATHS_KEY = "moss.agent.gitnexus.recentRepoPaths.v1";

export const PINNED_REPO_PATHS_KEY = "moss.agent.gitnexus.pinnedRepoPaths.v1";

export const AGENT_COMPOSER_DRAFT_KEY = "moss.agent.composerDraft.v1";

export const MAX_RECENT_REPO_PATHS = 5;

export const MAX_PINNED_REPO_PATHS = 5;

export function normalizeStoredRepoPaths(paths: string[], limit: number) {
  const normalizedPaths: string[] = [];
  for (const path of paths) {
    const normalized = path.trim();
    if (!normalized || normalizedPaths.includes(normalized)) {
      continue;
    }
    normalizedPaths.push(normalized);
    if (normalizedPaths.length >= limit) {
      break;
    }
  }
  return normalizedPaths;
}

export function loadStoredRepoPaths(storageKey: string, limit: number) {
  if (typeof window === "undefined") {
    return [] as string[];
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return normalizeStoredRepoPaths(
      parsed.filter((item): item is string => typeof item === "string"),
      limit,
    );
  } catch {
    return [];
  }
}

export function persistStoredRepoPaths(storageKey: string, paths: string[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(paths));
}

export function normalizeStoredConversationTurns(value: unknown): AgentConversationTurn[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .flatMap((item): AgentConversationTurn[] => {
      if (!isRecord(item) || typeof item.id !== "string" || typeof item.question !== "string") {
        return [];
      }
      const result = isAgentQueryResult(item.result) ? normalizeAgentResult(item.result) : null;
      const agentRun = isAgentRunPayload(item.agentRun) ? normalizeAgentRunPayload(item.agentRun) : null;
      const error = isAgentQueryError(item.error) ? item.error : null;
      const conversationContext = isAgentConversationContext(item.conversationContext)
        ? item.conversationContext
        : undefined;
      const runRequestLatencyMs = normalizeAgentRunRequestLatencyMs(item.runRequestLatencyMs);
      return [
        {
          id: item.id,
          question: item.question,
          conversationContext,
          retryMode: item.retryMode === "ordinary" ? "ordinary" : undefined,
          ...(runRequestLatencyMs !== undefined ? { runRequestLatencyMs } : {}),
          agentRun,
          result,
          error,
          stopped: item.stopped === true,
          activeSuggestedActionPayload: null,
        },
      ];
    })
    .slice(-MAX_AGENT_STORED_TURNS);
}

export function loadStoredConversationTurns() {
  if (typeof window === "undefined") {
    return [] as AgentConversationTurn[];
  }

  try {
    const raw = window.localStorage.getItem(AGENT_CONVERSATION_TURNS_KEY);
    return normalizeStoredConversationTurns(raw ? (JSON.parse(raw) as unknown) : []);
  } catch {
    return [];
  }
}

export function serializeConversationTurn(turn: AgentConversationTurn) {
  return {
    id: turn.id,
    question: turn.question,
    ...(turn.conversationContext ? { conversationContext: turn.conversationContext } : {}),
    ...(turn.retryMode ? { retryMode: turn.retryMode } : {}),
    ...(turn.runRequestLatencyMs !== undefined ? { runRequestLatencyMs: turn.runRequestLatencyMs } : {}),
    ...(turn.agentRun ? { agentRun: turn.agentRun } : {}),
    ...(turn.result ? { result: turn.result } : {}),
    ...(turn.error ? { error: turn.error } : {}),
    ...(turn.stopped ? { stopped: true } : {}),
  };
}

export function persistStoredConversationTurns(turns: AgentConversationTurn[]) {
  if (typeof window === "undefined") {
    return;
  }
  const storedTurns = turns.slice(-MAX_AGENT_STORED_TURNS).map(serializeConversationTurn);
  window.localStorage.setItem(AGENT_CONVERSATION_TURNS_KEY, JSON.stringify(storedTurns));
}

export function loadLatestAgentRunId() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)?.trim() ?? "";
}

export function persistLatestAgentRunId(runId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, runId);
}

export function clearLatestAgentRunId() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(LATEST_AGENT_RUN_ID_KEY);
}

export function loadComposerDraft() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(AGENT_COMPOSER_DRAFT_KEY) ?? "";
}

export function persistComposerDraft(draft: string) {
  if (typeof window === "undefined") {
    return;
  }
  if (!draft.trim()) {
    window.localStorage.removeItem(AGENT_COMPOSER_DRAFT_KEY);
    return;
  }
  window.localStorage.setItem(AGENT_COMPOSER_DRAFT_KEY, draft);
}

export function clearComposerDraft() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AGENT_COMPOSER_DRAFT_KEY);
}

export function normalizeQueuedQueries(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as string[];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, MAX_AGENT_QUEUED_QUERIES);
}

export function loadQueuedQueries() {
  if (typeof window === "undefined") {
    return [] as string[];
  }

  try {
    const raw = window.localStorage.getItem(AGENT_QUEUED_QUERIES_KEY);
    return normalizeQueuedQueries(raw ? (JSON.parse(raw) as unknown) : []);
  } catch {
    return [];
  }
}

export function persistQueuedQueries(queries: string[]) {
  if (typeof window === "undefined") {
    return;
  }
  const nextQueries = normalizeQueuedQueries(queries);
  if (nextQueries.length === 0) {
    window.localStorage.removeItem(AGENT_QUEUED_QUERIES_KEY);
    return;
  }
  window.localStorage.setItem(AGENT_QUEUED_QUERIES_KEY, JSON.stringify(nextQueries));
}

export function clearStoredQueuedQueries() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AGENT_QUEUED_QUERIES_KEY);
}

export function loadRecentRepoPaths() {
  return loadStoredRepoPaths(RECENT_REPO_PATHS_KEY, MAX_RECENT_REPO_PATHS);
}

export function loadPinnedRepoPaths() {
  return loadStoredRepoPaths(PINNED_REPO_PATHS_KEY, MAX_PINNED_REPO_PATHS);
}

export function persistRecentRepoPaths(paths: string[]) {
  persistStoredRepoPaths(RECENT_REPO_PATHS_KEY, paths);
}

export function persistPinnedRepoPaths(paths: string[]) {
  persistStoredRepoPaths(PINNED_REPO_PATHS_KEY, paths);
}

export function rememberRepoPathValue(currentPaths: string[], nextPath: string, limit = MAX_RECENT_REPO_PATHS) {
  const normalized = nextPath.trim();
  if (!normalized) {
    return currentPaths;
  }
  return normalizeStoredRepoPaths(
    [normalized, ...currentPaths.filter((path) => path !== normalized)],
    limit,
  );
}

export function pinRepoPathValue(currentPaths: string[], nextPath: string) {
  return rememberRepoPathValue(currentPaths, nextPath, MAX_PINNED_REPO_PATHS);
}

export function unpinRepoPathValue(currentPaths: string[], targetPath: string) {
  return currentPaths.filter((path) => path !== targetPath);
}

export function movePinnedRepoPathValue(
  currentPaths: string[],
  targetPath: string,
  direction: "up" | "down",
) {
  const currentIndex = currentPaths.indexOf(targetPath);
  if (currentIndex < 0) {
    return currentPaths;
  }

  const nextIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
  if (nextIndex < 0 || nextIndex >= currentPaths.length) {
    return currentPaths;
  }

  const nextPaths = [...currentPaths];
  [nextPaths[currentIndex], nextPaths[nextIndex]] = [nextPaths[nextIndex], nextPaths[currentIndex]];
  return nextPaths;
}
