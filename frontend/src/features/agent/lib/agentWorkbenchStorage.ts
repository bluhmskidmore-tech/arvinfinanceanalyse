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

export const DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE = "user:web-user";

export const AGENT_WORKBENCH_STORAGE_BYTE_BUDGET = 256 * 1024;

const STORAGE_SCOPE_SEPARATOR = "::";

const textEncoder = typeof TextEncoder !== "undefined" ? new TextEncoder() : null;

function getUtf8ByteLength(value: string) {
  return textEncoder ? textEncoder.encode(value).length : new Blob([value]).size;
}

function isQuotaExceededError(error: unknown) {
  return (
    error instanceof DOMException &&
    (error.name === "QuotaExceededError" || error.name === "NS_ERROR_DOM_QUOTA_REACHED")
  );
}

function sanitizeStorageScope(scope: string) {
  return encodeURIComponent(scope.trim() || DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE);
}

export function getScopedAgentWorkbenchStorageKey(
  storageKey: string,
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  return `${storageKey}${STORAGE_SCOPE_SEPARATOR}${sanitizeStorageScope(storageScope)}`;
}

function migrateLegacyStorageItem(storageKey: string, storageScope: string) {
  const scopedKey = getScopedAgentWorkbenchStorageKey(storageKey, storageScope);
  if (window.localStorage.getItem(scopedKey) !== null) {
    return scopedKey;
  }
  const legacyValue = window.localStorage.getItem(storageKey);
  if (legacyValue === null) {
    return scopedKey;
  }
  try {
    window.localStorage.setItem(scopedKey, legacyValue);
    window.localStorage.removeItem(storageKey);
  } catch (storageError) {
    console.warn(
      `[agent] localStorage 迁移失败（${storageKey}），继续使用空的命名空间存储。`,
      storageError,
    );
  }
  return scopedKey;
}

function resolveStorageKey(storageKey: string, storageScope: string) {
  return migrateLegacyStorageItem(storageKey, storageScope);
}

function readLocalStorageItem(storageKey: string, storageScope: string) {
  try {
    return window.localStorage.getItem(resolveStorageKey(storageKey, storageScope));
  } catch (storageError) {
    console.warn(
      `[agent] localStorage 读取失败（${storageKey}），继续使用空值。`,
      storageError,
    );
    return null;
  }
}

function removeLocalStorageItem(storageKey: string) {
  try {
    window.localStorage.removeItem(storageKey);
  } catch (storageError) {
    console.warn(
      `[agent] localStorage 清除失败（${storageKey}），本次清除已跳过。`,
      storageError,
    );
  }
}

/**
 * localStorage 写入统一降级：配额超限（QuotaExceededError）等异常不能击穿
 * 渲染/提交链路——失败时放弃本次持久化并 console.warn。
 */
function writeLocalStorageItem(storageKey: string, value: string, retryValue?: string) {
  try {
    window.localStorage.setItem(storageKey, value);
  } catch (storageError) {
    if (retryValue !== undefined && isQuotaExceededError(storageError)) {
      try {
        window.localStorage.setItem(storageKey, retryValue);
        return;
      } catch (retryError) {
        console.warn(
          `[agent] localStorage 写入失败（${storageKey}），收缩后重试仍失败。`,
          retryError,
        );
        return;
      }
    }
    console.warn(
      `[agent] localStorage 写入失败（${storageKey}），本次持久化已跳过。`,
      storageError,
    );
  }
}

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

export function loadStoredRepoPaths(
  storageKey: string,
  limit: number,
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  if (typeof window === "undefined") {
    return [] as string[];
  }

  try {
    const raw = window.localStorage.getItem(resolveStorageKey(storageKey, storageScope));
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

export function persistStoredRepoPaths(
  storageKey: string,
  paths: string[],
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  if (typeof window === "undefined") {
    return;
  }
  writeLocalStorageItem(getScopedAgentWorkbenchStorageKey(storageKey, storageScope), JSON.stringify(paths));
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
      const storedAgentRun = isAgentRunPayload(item.agentRun)
        ? normalizeAgentRunPayload(item.agentRun)
        : null;
      // 序列化时剥离了 agentRun.result（envelope 去重），恢复时回填，保持内存形状不变。
      const agentRun =
        storedAgentRun && !storedAgentRun.result && result
          ? { ...storedAgentRun, result }
          : storedAgentRun;
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

export function loadStoredConversationTurns(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return [] as AgentConversationTurn[];
  }

  try {
    const raw = window.localStorage.getItem(
      resolveStorageKey(AGENT_CONVERSATION_TURNS_KEY, storageScope),
    );
    return normalizeStoredConversationTurns(raw ? (JSON.parse(raw) as unknown) : []);
  } catch {
    return [];
  }
}

export function serializeConversationTurn(turn: AgentConversationTurn) {
  // envelope 去重：turn.result 与 turn.agentRun.result 是同一份 AgentEnvelope，
  // 双份序列化会成倍消耗 localStorage 配额。存储侧剥离 agentRun.result，
  // 恢复时（normalizeStoredConversationTurns）从 turn.result 回填。
  const agentRun =
    turn.agentRun && turn.agentRun.result && turn.result
      ? { ...turn.agentRun, result: null }
      : turn.agentRun;
  return {
    id: turn.id,
    question: turn.question,
    ...(turn.conversationContext ? { conversationContext: turn.conversationContext } : {}),
    ...(turn.retryMode ? { retryMode: turn.retryMode } : {}),
    ...(turn.runRequestLatencyMs !== undefined ? { runRequestLatencyMs: turn.runRequestLatencyMs } : {}),
    ...(agentRun ? { agentRun } : {}),
    ...(turn.result ? { result: turn.result } : {}),
    ...(turn.error ? { error: turn.error } : {}),
    ...(turn.stopped ? { stopped: true } : {}),
  };
}

function stripPersistedTurnSqlExecuted(turn: ReturnType<typeof serializeConversationTurn>) {
  return {
    ...turn,
    result: turn.result
      ? {
          ...turn.result,
          evidence: { ...turn.result.evidence, sql_executed: [] },
        }
      : turn.result,
    agentRun: turn.agentRun?.result
      ? {
          ...turn.agentRun,
          result: {
            ...turn.agentRun.result,
            evidence: { ...turn.agentRun.result.evidence, sql_executed: [] },
          },
        }
      : turn.agentRun,
  };
}

function shrinkStoredTurnsToBudget(
  storedTurns: ReturnType<typeof serializeConversationTurn>[],
  byteBudget: number,
) {
  let nextTurns = storedTurns;
  let serialized = JSON.stringify(nextTurns);
  if (getUtf8ByteLength(serialized) <= byteBudget) {
    return serialized;
  }

  nextTurns = nextTurns.map(stripPersistedTurnSqlExecuted);
  serialized = JSON.stringify(nextTurns);
  while (nextTurns.length > 1 && getUtf8ByteLength(serialized) > byteBudget) {
    nextTurns = nextTurns.slice(1);
    serialized = JSON.stringify(nextTurns);
  }
  return serialized;
}

function buildQuotaRetryTurnsPayload(storedTurns: ReturnType<typeof serializeConversationTurn>[]) {
  const strippedTurns = storedTurns.map(stripPersistedTurnSqlExecuted);
  if (JSON.stringify(strippedTurns) !== JSON.stringify(storedTurns)) {
    return shrinkStoredTurnsToBudget(strippedTurns, AGENT_WORKBENCH_STORAGE_BYTE_BUDGET);
  }
  return storedTurns.length > 1
    ? shrinkStoredTurnsToBudget(storedTurns.slice(1), AGENT_WORKBENCH_STORAGE_BYTE_BUDGET)
    : undefined;
}

export function persistStoredConversationTurns(
  turns: AgentConversationTurn[],
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
  byteBudget = AGENT_WORKBENCH_STORAGE_BYTE_BUDGET,
) {
  if (typeof window === "undefined") {
    return;
  }
  const storedTurns = turns.slice(-MAX_AGENT_STORED_TURNS).map(serializeConversationTurn);
  const storageValue = shrinkStoredTurnsToBudget(storedTurns, byteBudget);
  writeLocalStorageItem(
    getScopedAgentWorkbenchStorageKey(AGENT_CONVERSATION_TURNS_KEY, storageScope),
    storageValue,
    buildQuotaRetryTurnsPayload(storedTurns),
  );
}

export function loadLatestAgentRunId(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return "";
  }
  return readLocalStorageItem(LATEST_AGENT_RUN_ID_KEY, storageScope)?.trim() ?? "";
}

export function persistLatestAgentRunId(
  runId: string,
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  if (typeof window === "undefined") {
    return;
  }
  writeLocalStorageItem(getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY, storageScope), runId);
}

export function clearLatestAgentRunId(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return;
  }
  removeLocalStorageItem(getScopedAgentWorkbenchStorageKey(LATEST_AGENT_RUN_ID_KEY, storageScope));
}

export function loadComposerDraft(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return "";
  }
  return readLocalStorageItem(AGENT_COMPOSER_DRAFT_KEY, storageScope) ?? "";
}

export function persistComposerDraft(draft: string, storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return;
  }
  if (!draft.trim()) {
    removeLocalStorageItem(getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY, storageScope));
    return;
  }
  writeLocalStorageItem(getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY, storageScope), draft);
}

export function clearComposerDraft(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return;
  }
  removeLocalStorageItem(getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY, storageScope));
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

export function loadQueuedQueries(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return [] as string[];
  }

  try {
    const raw = window.localStorage.getItem(resolveStorageKey(AGENT_QUEUED_QUERIES_KEY, storageScope));
    return normalizeQueuedQueries(raw ? (JSON.parse(raw) as unknown) : []);
  } catch {
    return [];
  }
}

export function persistQueuedQueries(queries: string[], storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return;
  }
  const nextQueries = normalizeQueuedQueries(queries);
  if (nextQueries.length === 0) {
    removeLocalStorageItem(getScopedAgentWorkbenchStorageKey(AGENT_QUEUED_QUERIES_KEY, storageScope));
    return;
  }
  writeLocalStorageItem(
    getScopedAgentWorkbenchStorageKey(AGENT_QUEUED_QUERIES_KEY, storageScope),
    JSON.stringify(nextQueries),
  );
}

export function clearStoredQueuedQueries(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  if (typeof window === "undefined") {
    return;
  }
  removeLocalStorageItem(getScopedAgentWorkbenchStorageKey(AGENT_QUEUED_QUERIES_KEY, storageScope));
}

export function loadRecentRepoPaths(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  return loadStoredRepoPaths(RECENT_REPO_PATHS_KEY, MAX_RECENT_REPO_PATHS, storageScope);
}

export function loadPinnedRepoPaths(storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE) {
  return loadStoredRepoPaths(PINNED_REPO_PATHS_KEY, MAX_PINNED_REPO_PATHS, storageScope);
}

export function persistRecentRepoPaths(
  paths: string[],
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  persistStoredRepoPaths(RECENT_REPO_PATHS_KEY, paths, storageScope);
}

export function persistPinnedRepoPaths(
  paths: string[],
  storageScope = DEFAULT_AGENT_WORKBENCH_STORAGE_SCOPE,
) {
  persistStoredRepoPaths(PINNED_REPO_PATHS_KEY, paths, storageScope);
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
