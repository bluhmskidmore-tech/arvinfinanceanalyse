import { useDeferredValue, useEffect, useRef, useState, type FormEvent } from "react";

import { runPollingTask, type PollingTaskPayload } from "../../app/jobs/polling";
import type { AgentPageContext, AgentQueryRequest, AgentSuggestedAction } from "../../api/contracts";
import { shellTokens as t } from "../../theme/tokens";
import { AgentAnswerPanel } from "./components/AgentAnswerPanel";
import { AgentEvidencePanel } from "./components/AgentEvidencePanel";
import { AgentGenericCardsGrid } from "./components/AgentGenericCardsGrid";
import { AgentQueryForm } from "./components/AgentQueryForm";
import { AgentRepoMemoryPanel } from "./components/AgentRepoMemoryPanel";
import { AgentResultMetaPanel } from "./components/AgentResultMetaPanel";
import { AgentSuggestedActionsPanel } from "./components/AgentSuggestedActionsPanel";
import { GitNexusResultView as AgentGitNexusResultView } from "./components/GitNexusResultView";

type AgentResultCard = {
  title: string;
  value?: string | null;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown> | null;
  spec?: Record<string, unknown> | null;
};

type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  evidence_rows: number;
  quality_flag: string;
};

type AgentNextDrill = {
  dimension: string;
  label: string;
};

type AgentQueryResult = {
  answer: string;
  cards: AgentResultCard[];
  evidence: AgentEvidence;
  result_meta: Record<string, unknown>;
  next_drill: AgentNextDrill[];
  suggested_actions: AgentSuggestedAction[];
};

type AgentRunStatus = "queued" | "starting" | "running" | "completed" | "failed";

type AgentRunPayload = PollingTaskPayload & {
  run_id: string;
  status: AgentRunStatus;
  question?: string | null;
  provider?: string;
  model?: string;
  transport?: string;
  toolsets?: string;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_seconds?: number | null;
  result?: AgentQueryResult | null;
};

type AgentQueryError =
  | {
      kind: "disabled";
      detail: string;
      phase: string;
    }
  | {
      kind: "request";
      message: string;
    };

type AgentWorkbenchPageProps = {
  pageContext?: AgentPageContext;
};

type AgentPanelProps = AgentWorkbenchPageProps & {
  showHeader?: boolean;
};

class AgentDisabledQueryError extends Error {
  detail: string;
  phase: string;

  constructor(detail: string, phase: string) {
    super(detail);
    this.name = "AgentDisabledQueryError";
    this.detail = detail;
    this.phase = phase;
  }
}

const AGENT_RUN_STATUSES = new Set<AgentRunStatus>([
  "queued",
  "starting",
  "running",
  "completed",
  "failed",
]);

const LATEST_AGENT_RUN_ID_KEY = "moss.agent.latestRunId.v1";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentQueryResult(value: unknown): value is AgentQueryResult {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.answer === "string" &&
    Array.isArray(value.cards) &&
    value.cards.every(isAgentResultCard) &&
    isAgentEvidence(value.evidence) &&
    Array.isArray(value.next_drill) &&
    value.next_drill.every(isAgentNextDrill) &&
    (value.suggested_actions === undefined ||
      (Array.isArray(value.suggested_actions) && value.suggested_actions.every(isAgentSuggestedAction))) &&
    isRecord(value.result_meta)
  );
}

function isAgentResultCard(value: unknown): value is AgentResultCard {
  return (
    isRecord(value) &&
    typeof value.title === "string" &&
    (value.value == null || typeof value.value === "string") &&
    typeof value.type === "string" &&
    (value.data == null ||
      isRecord(value.data) ||
      (Array.isArray(value.data) && value.data.every(isRecord))) &&
    (value.spec == null || isRecord(value.spec))
  );
}

function isAgentEvidence(value: unknown): value is AgentEvidence {
  return (
    isRecord(value) &&
    Array.isArray(value.tables_used) &&
    value.tables_used.every((item) => typeof item === "string") &&
    isRecord(value.filters_applied) &&
    typeof value.evidence_rows === "number" &&
    typeof value.quality_flag === "string"
  );
}

function isAgentNextDrill(value: unknown): value is AgentNextDrill {
  return (
    isRecord(value) &&
    typeof value.dimension === "string" &&
    typeof value.label === "string"
  );
}

function isAgentSuggestedAction(value: unknown): value is AgentSuggestedAction {
  return (
    isRecord(value) &&
    typeof value.type === "string" &&
    typeof value.label === "string" &&
    isRecord(value.payload) &&
    typeof value.requires_confirmation === "boolean"
  );
}

function isDisabledPayload(value: unknown): value is {
  enabled: false;
  phase: string;
  detail: string;
} {
  return (
    isRecord(value) &&
    value.enabled === false &&
    typeof value.phase === "string" &&
    typeof value.detail === "string"
  );
}

function isAgentRunStatus(value: unknown): value is AgentRunStatus {
  return typeof value === "string" && AGENT_RUN_STATUSES.has(value as AgentRunStatus);
}

function isAgentRunPayload(value: unknown): value is AgentRunPayload {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.run_id === "string" &&
    isAgentRunStatus(value.status) &&
    (value.question == null || typeof value.question === "string") &&
    (value.provider === undefined || typeof value.provider === "string") &&
    (value.model === undefined || typeof value.model === "string") &&
    (value.transport === undefined || typeof value.transport === "string") &&
    (value.toolsets === undefined || typeof value.toolsets === "string") &&
    (value.queued_at == null || typeof value.queued_at === "string") &&
    (value.started_at == null || typeof value.started_at === "string") &&
    (value.finished_at == null || typeof value.finished_at === "string") &&
    (value.elapsed_seconds == null || typeof value.elapsed_seconds === "number") &&
    (value.error_message == null || typeof value.error_message === "string") &&
    (value.result == null || isAgentQueryResult(value.result))
  );
}

function normalizeAgentResult(result: AgentQueryResult): AgentQueryResult {
  result.suggested_actions = result.suggested_actions ?? [];
  return result;
}

function normalizeAgentRunPayload(payload: AgentRunPayload): AgentRunPayload {
  if (payload.result) {
    payload.result = normalizeAgentResult(payload.result);
  }
  return payload;
}

function buildErrorMessage(error: unknown) {
  if (isFetchNetworkError(error)) {
    return "无法连接 Agent 后端。请确认 7888 后端、5888 前端代理和 Hermes 桥接服务正在运行。";
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "智能体查询失败，请稍后重试。";
}

function isFetchNetworkError(error: unknown) {
  if (!(error instanceof TypeError)) {
    return false;
  }
  const message = error.message.trim().toLowerCase();
  return (
    message.includes("failed to fetch") ||
    message.includes("networkerror when attempting to fetch resource") ||
    message === "load failed"
  );
}

function hasEvidenceContent(evidence: AgentEvidence) {
  return (
    evidence.tables_used.length > 0 ||
    Object.keys(evidence.filters_applied).length > 0 ||
    evidence.evidence_rows > 0 ||
    evidence.quality_flag.trim().length > 0
  );
}

function hasRenderableResult(result: AgentQueryResult) {
  return (
    result.answer.trim().length > 0 ||
    result.cards.length > 0 ||
    hasEvidenceContent(result.evidence) ||
    result.next_drill.length > 0 ||
    result.suggested_actions.length > 0
  );
}

function buildResultMetaEntries(resultMeta: Record<string, unknown>) {
  const orderedKeys = ["trace_id", "basis", "generated_at"];
  const seen = new Set<string>();
  const entries: Array<[string, unknown]> = [];

  for (const key of orderedKeys) {
    if (key in resultMeta) {
      entries.push([key, resultMeta[key]]);
      seen.add(key);
    }
  }

  for (const [key, value] of Object.entries(resultMeta)) {
    if (seen.has(key)) {
      continue;
    }
    entries.push([key, value]);
  }

  return entries;
}

function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "string") {
    return value.trim().length > 0 ? value : "--";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function formatRuntimeLabel(value: unknown, fallback: string) {
  if (typeof value !== "string") {
    return fallback;
  }
  const normalized = value.trim();
  return normalized || fallback;
}

function formatProviderLabel(value: unknown, fallback: string) {
  const label = formatRuntimeLabel(value, fallback);
  return label.toLowerCase() === "hermes" ? "Hermes" : label;
}

function formatAgentRunStatusLabel(status: AgentRunStatus | undefined, fallback = "--") {
  switch (status) {
    case "queued":
      return "排队中";
    case "starting":
      return "启动中";
    case "running":
      return "运行中";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    default:
      return fallback;
  }
}

function formatAgentWaitTitle(status: AgentRunStatus | undefined) {
  switch (status) {
    case "queued":
      return "Hermes 已排队";
    case "starting":
      return "Hermes 正在启动";
    case "running":
      return "Hermes 正在分析";
    case "completed":
      return "Hermes 托管任务完成";
    case "failed":
      return "Hermes 托管任务失败";
    default:
      return "Hermes 正在分析";
  }
}

function formatAgentRunElapsed(agentRun: AgentRunPayload | null, fallbackSeconds: number) {
  if (typeof agentRun?.elapsed_seconds === "number" && Number.isFinite(agentRun.elapsed_seconds)) {
    return Math.max(0, Math.round(agentRun.elapsed_seconds));
  }
  return fallbackSeconds;
}

function buildRuntimeStatus(
  result: AgentQueryResult | null,
  loading: boolean,
  agentRun: AgentRunPayload | null,
) {
  const filters = result?.evidence.filters_applied ?? {};
  const statusLabel = formatAgentRunStatusLabel(agentRun?.status, loading ? "分析中" : "--");
  return {
    provider: formatProviderLabel(agentRun?.provider ?? filters.provider, loading ? "Hermes" : "待连接"),
    transport: formatRuntimeLabel(agentRun?.transport ?? filters.transport, loading ? "bridge" : "等待提问"),
    model: formatRuntimeLabel(agentRun?.model ?? filters.model, "--"),
    toolsets: formatRuntimeLabel(agentRun?.toolsets ?? filters.toolsets, "--"),
    quality: formatRuntimeLabel(result?.evidence.quality_flag, statusLabel),
  };
}

const GITNEXUS_QUICK_EXAMPLES = [
  "解释当前页面的主要结论和风险点",
  "组合概览：规模、损益、久期和信用风险有什么变化？",
  "本日损益主要由什么驱动？请给证据和下一步复核建议。",
  "当前久期和信用集中度有什么异常？",
  "请给我看 GitNexus 状态",
  "请给我看 GitNexus context",
  "请给我看 GitNexus processes",
] as const;
const RECENT_REPO_PATHS_KEY = "moss.agent.gitnexus.recentRepoPaths.v1";
const PINNED_REPO_PATHS_KEY = "moss.agent.gitnexus.pinnedRepoPaths.v1";
const MAX_RECENT_REPO_PATHS = 5;
const MAX_PINNED_REPO_PATHS = 5;
const GITNEXUS_PROCESS_CARD_TITLE = "GitNexus Processes Table";

function buildAgentRequestBody(
  question: string,
  repoPath: string,
  processName: string,
  pageContext?: AgentPageContext,
): AgentQueryRequest {
  return {
    question,
    basis: "formal",
    filters: buildFilters(question, repoPath, processName),
    position_scope: "all",
    currency_basis: "CNY",
    context: {
      user_id: "web-user",
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

function normalizeStoredRepoPaths(paths: string[], limit: number) {
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

function loadStoredRepoPaths(storageKey: string, limit: number) {
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

function persistStoredRepoPaths(storageKey: string, paths: string[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(paths));
}

function loadLatestAgentRunId() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(LATEST_AGENT_RUN_ID_KEY)?.trim() ?? "";
}

function persistLatestAgentRunId(runId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LATEST_AGENT_RUN_ID_KEY, runId);
}

function clearLatestAgentRunId() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(LATEST_AGENT_RUN_ID_KEY);
}

function isGitNexusCard(card: AgentResultCard) {
  return card.title.startsWith("GitNexus ");
}

function isGitNexusResult(result: AgentQueryResult) {
  return result.result_meta.result_kind === "agent.gitnexus_status";
}

function extractProcessNames(cards: AgentResultCard[]) {
  const processCard = cards.find((card) => card.title === GITNEXUS_PROCESS_CARD_TITLE);
  if (!processCard || !Array.isArray(processCard.data)) {
    return [];
  }
  return processCard.data
    .map((row) => (isRecord(row) && typeof row.name === "string" ? row.name : ""))
    .filter((name) => name.trim().length > 0);
}

function buildFilters(question: string, repoPath: string, processName?: string) {
  const filters: Record<string, string> = {};
  if (repoPath.trim()) {
    filters.repo_path = repoPath.trim();
  }
  if (
    processName &&
    processName.trim() &&
    /gitnexus\s+process(?:\/|\s)/i.test(question) &&
    !/gitnexus\s+processes/i.test(question)
  ) {
    filters.process_name = processName.trim();
  }
  return filters;
}

function loadRecentRepoPaths() {
  return loadStoredRepoPaths(RECENT_REPO_PATHS_KEY, MAX_RECENT_REPO_PATHS);
}

function loadPinnedRepoPaths() {
  return loadStoredRepoPaths(PINNED_REPO_PATHS_KEY, MAX_PINNED_REPO_PATHS);
}

function persistRecentRepoPaths(paths: string[]) {
  persistStoredRepoPaths(RECENT_REPO_PATHS_KEY, paths);
}

function persistPinnedRepoPaths(paths: string[]) {
  persistStoredRepoPaths(PINNED_REPO_PATHS_KEY, paths);
}

function rememberRepoPathValue(currentPaths: string[], nextPath: string, limit = MAX_RECENT_REPO_PATHS) {
  const normalized = nextPath.trim();
  if (!normalized) {
    return currentPaths;
  }
  return normalizeStoredRepoPaths(
    [normalized, ...currentPaths.filter((path) => path !== normalized)],
    limit,
  );
}

function pinRepoPathValue(currentPaths: string[], nextPath: string) {
  return rememberRepoPathValue(currentPaths, nextPath, MAX_PINNED_REPO_PATHS);
}

function unpinRepoPathValue(currentPaths: string[], targetPath: string) {
  return currentPaths.filter((path) => path !== targetPath);
}

function movePinnedRepoPathValue(
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

export function AgentPanel({ pageContext, showHeader = false }: AgentPanelProps = {}) {
  const [recentRepoPaths, setRecentRepoPaths] = useState<string[]>(() => loadRecentRepoPaths());
  const [pinnedRepoPaths, setPinnedRepoPaths] = useState<string[]>(() => loadPinnedRepoPaths());
  const [query, setQuery] = useState("");
  const [repoPath, setRepoPath] = useState(() => loadRecentRepoPaths()[0] ?? "");
  const [availableProcesses, setAvailableProcesses] = useState<string[]>([]);
  const [processSearch, setProcessSearch] = useState("");
  const [selectedProcess, setSelectedProcess] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentWaitSeconds, setAgentWaitSeconds] = useState(0);
  const [processLoading, setProcessLoading] = useState(false);
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRunPayload | null>(null);
  const [activeSuggestedActionPayload, setActiveSuggestedActionPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<AgentQueryError | null>(null);
  const repoPathRef = useRef(repoPath);
  const processStateRequestVersionRef = useRef(0);
  const deferredProcessSearch = useDeferredValue(processSearch);
  const filteredProcesses = availableProcesses.filter((processName) =>
    processName.toLowerCase().includes(deferredProcessSearch.trim().toLowerCase()),
  );
  const recentUnpinnedRepoPaths = recentRepoPaths.filter((path) => !pinnedRepoPaths.includes(path));
  const isCurrentRepoPinned = pinnedRepoPaths.includes(repoPath.trim());
  const runtimeStatus = buildRuntimeStatus(result, loading, agentRun);
  repoPathRef.current = repoPath;

  function beginProcessStateRequest() {
    processStateRequestVersionRef.current += 1;
    return processStateRequestVersionRef.current;
  }

  function canCommitProcessState(requestVersion: number, requestRepoPath: string) {
    return (
      processStateRequestVersionRef.current === requestVersion &&
      requestRepoPath === repoPathRef.current.trim()
    );
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

  useEffect(() => {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    if (!normalizedRepoPath) {
      setAvailableProcesses([]);
      setSelectedProcess("");
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadGitNexusProcesses(normalizedRepoPath, requestVersion);
    }, 350);
    return () => window.clearTimeout(timeoutId);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- debounce repo path changes only
  }, [repoPath]);

  useEffect(() => {
    if (!filteredProcesses.length) {
      setSelectedProcess("");
      return;
    }
    if (!selectedProcess || !filteredProcesses.includes(selectedProcess)) {
      setSelectedProcess(filteredProcesses[0] ?? "");
    }
  }, [filteredProcesses, selectedProcess]);

  useEffect(() => {
    if (!loading) {
      return;
    }
    const intervalId = window.setInterval(() => {
      setAgentWaitSeconds((currentSeconds) => currentSeconds + 1);
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [loading]);

  useEffect(() => {
    const latestRunId = loadLatestAgentRunId();
    if (!latestRunId) {
      return;
    }

    let cancelled = false;
    void fetchAgentRunStatus(latestRunId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setAgentRun(payload);
        if (payload.status === "completed" && payload.result) {
          setResult(payload.result);
          setActiveSuggestedActionPayload(null);
        }
        if (payload.status === "failed") {
          setError({
            kind: "request",
            message: payload.error_message || "Hermes 托管任务失败，请稍后重试。",
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearLatestAgentRunId();
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function fetchAgentRunStatus(runId: string): Promise<AgentRunPayload> {
    const response = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}`, {
      method: "GET",
    });
    const payload = (await response.json()) as unknown;
    if (!response.ok) {
      throw new Error(`智能体任务状态获取失败（${response.status}）`);
    }
    if (!isAgentRunPayload(payload)) {
      throw new Error("智能体返回结果格式无效。");
    }
    return normalizeAgentRunPayload(payload);
  }

  async function createAgentRun(requestBody: AgentQueryRequest): Promise<AgentRunPayload> {
    const response = await fetch("/api/agent/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });
    const payload = (await response.json()) as unknown;

    if (response.status === 503 && isDisabledPayload(payload)) {
      throw new AgentDisabledQueryError(payload.detail, payload.phase);
    }

    if (!response.ok) {
      throw new Error(`智能体查询失败（${response.status}）`);
    }

    if (isAgentQueryResult(payload)) {
      const result = normalizeAgentResult(payload);
      return {
        run_id: "agent_run:sync_compat",
        status: "completed",
        provider: formatRuntimeLabel(result.evidence.filters_applied.provider, "hermes"),
        model: formatRuntimeLabel(result.evidence.filters_applied.model, "default"),
        transport: formatRuntimeLabel(result.evidence.filters_applied.transport, "bridge"),
        toolsets: formatRuntimeLabel(result.evidence.filters_applied.toolsets, "default"),
        result,
      };
    }

    if (!isAgentRunPayload(payload)) {
      throw new Error("智能体返回结果格式无效。");
    }

    persistLatestAgentRunId(payload.run_id);
    return normalizeAgentRunPayload(payload);
  }

  async function executeManagedAgentRun(question: string) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    const requestBody = buildAgentRequestBody(question, normalizedRepoPath, selectedProcess, pageContext);
    setAgentRun(null);
    try {
      const finalPayload = await runPollingTask<AgentRunPayload>({
        start: () => createAgentRun(requestBody),
        getStatus: fetchAgentRunStatus,
        onUpdate: (payload) => {
          setAgentRun(payload);
        },
      });

      if (finalPayload.status === "failed") {
        throw new Error(finalPayload.error_message || "Hermes 托管任务失败，请稍后重试。");
      }

      if (!finalPayload.result) {
        throw new Error("智能体任务完成但未返回结果。");
      }

      if (!canCommitProcessState(requestVersion, normalizedRepoPath)) {
        return;
      }

      const payload = finalPayload.result;
      const nextProcesses = extractProcessNames(payload.cards);
      if (nextProcesses.length > 0) {
        setAvailableProcesses(nextProcesses);
        setSelectedProcess((current) => (current && nextProcesses.includes(current) ? current : nextProcesses[0] ?? ""));
      }

      if (normalizedRepoPath.length > 0) {
        rememberRepoPath(normalizedRepoPath);
      }
      setResult(payload);
      setActiveSuggestedActionPayload(null);
    } catch (requestError) {
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        if (requestError instanceof AgentDisabledQueryError) {
          setError({
            kind: "disabled",
            detail: requestError.detail,
            phase: requestError.phase,
          });
          return;
        }
        setError({
          kind: "request",
          message: buildErrorMessage(requestError),
        });
      }
    }
  }

  async function executeAgentQuery(question: string, mode: "query" | "processes" = "query") {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    try {
      const requestBody = buildAgentRequestBody(question, normalizedRepoPath, selectedProcess, pageContext);

      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      const payload = (await response.json()) as unknown;

      if (response.status === 503 && isDisabledPayload(payload)) {
        if (!canCommitProcessState(requestVersion, normalizedRepoPath)) {
          return;
        }
        setError({
          kind: "disabled",
          detail: payload.detail,
          phase: payload.phase,
        });
        return;
      }

      if (!response.ok) {
        throw new Error(`智能体查询失败（${response.status}）`);
      }

      if (!isAgentQueryResult(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      normalizeAgentResult(payload);

      const nextProcesses = extractProcessNames(payload.cards);
      if (nextProcesses.length > 0 && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setAvailableProcesses(nextProcesses);
        setSelectedProcess((current) => (current && nextProcesses.includes(current) ? current : nextProcesses[0] ?? ""));
      } else if (mode === "processes" && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setAvailableProcesses([]);
        setSelectedProcess("");
      }

      if (normalizedRepoPath.length > 0 && canCommitProcessState(requestVersion, normalizedRepoPath)) {
        rememberRepoPath(normalizedRepoPath);
      }
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setResult(payload);
        setActiveSuggestedActionPayload(null);
      }
      return payload;
    } catch (requestError) {
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        setError({
          kind: "request",
          message: buildErrorMessage(requestError),
        });
      }
    }
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();

    const question = query.trim();
    if (!question) {
      setResult(null);
      setError({
        kind: "request",
        message: "请输入查询问题。",
      });
      return;
    }

    setAgentWaitSeconds(0);
    setLoading(true);
    setError(null);
    try {
      await executeManagedAgentRun(question);
    } finally {
      setLoading(false);
    }
  }

  async function loadGitNexusProcesses(repoPathOverride: string, requestVersion?: number) {
    const normalizedRepoPath = repoPathOverride.trim();
    const activeRequestVersion = requestVersion ?? beginProcessStateRequest();
    if (!normalizedRepoPath) {
      setError({
        kind: "request",
        message: "请先输入 GitNexus 仓库路径。",
      });
      return;
    }

    setProcessLoading(true);
    setError(null);
    try {
      const requestBody: AgentQueryRequest = {
        question: "请给我看 GitNexus processes",
        basis: "formal",
        filters: { repo_path: normalizedRepoPath },
        position_scope: "all",
        currency_basis: "CNY",
        context: {
          user_id: "web-user",
        },
        ...(pageContext ? { page_context: pageContext } : {}),
      };

      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      const payload = (await response.json()) as unknown;
      if (!response.ok || !isAgentQueryResult(payload)) {
        throw new Error(
          !response.ok
            ? `智能体查询失败（${response.status}）`
            : "智能体返回结果格式无效。",
        );
      }
      normalizeAgentResult(payload);

      const nextProcesses = extractProcessNames(payload.cards);
      if (canCommitProcessState(activeRequestVersion, normalizedRepoPath)) {
        setAvailableProcesses(nextProcesses);
        setProcessSearch("");
        setSelectedProcess(nextProcesses[0] ?? "");
        rememberRepoPath(normalizedRepoPath);
        setResult(payload);
        setActiveSuggestedActionPayload(null);
      }
    } catch (requestError) {
      if (canCommitProcessState(activeRequestVersion, normalizedRepoPath)) {
        setError({
          kind: "request",
          message: buildErrorMessage(requestError),
        });
      }
    } finally {
      if (processStateRequestVersionRef.current === activeRequestVersion) {
        setProcessLoading(false);
      }
    }
  }

  async function viewSelectedProcess() {
    if (!selectedProcess) {
      setError({
        kind: "request",
        message: "请先从流程列表选择一个流程。",
      });
      return;
    }
    setQuery(`请给我看 GitNexus process/${selectedProcess}`);
    setAgentWaitSeconds(0);
    setLoading(true);
    setError(null);
    try {
      await executeAgentQuery(`请给我看 GitNexus process/${selectedProcess}`, "query");
    } finally {
      setLoading(false);
    }
  }

  function applyQuickExample(nextQuery: string) {
    setQuery(nextQuery);
    setError(null);
  }

  function applyRecentRepoPath(nextRepoPath: string) {
    setRepoPath(nextRepoPath);
  }

  function pinCurrentRepo() {
    const normalized = repoPath.trim();
    if (!normalized) {
      setError({
        kind: "request",
        message: "请先输入 GitNexus 仓库路径。",
      });
      return;
    }
    pinRepoPath(normalized);
  }

  function unpinRepo(path: string) {
    unpinRepoPath(path);
  }

  function handleSuggestedAction(action: AgentSuggestedAction) {
    if (action.type === "inspect_drill" || action.type === "refine_query") {
      setQuery(`请基于当前 evidence 继续下钻：${action.label}`);
      setError(null);
      return;
    }
    setActiveSuggestedActionPayload(action.payload);
  }

  function formatPageContextSummary(context: AgentPageContext) {
    return JSON.stringify({
      page_id: context.page_id,
      current_filters: context.current_filters,
      selected_rows: context.selected_rows,
      context_note: context.context_note ?? null,
    });
  }

  return (
    <section className="agent-workbench-shell">
      {showHeader ? (
        <header className="agent-workbench-header">
          <div>
            <div className="agent-workbench-header__eyebrow">Agent Workbench</div>
            <h1>智能体对话</h1>
            <p>像聊天一样提问；智能体只读取已有分析服务和证据，返回结论、依据、页面上下文和下一步建议。</p>
          </div>
          <div className="agent-workbench-header__cue" aria-hidden="true">
            MOSS / Hermes
          </div>
        </header>
      ) : null}

      <div className="agent-runtime-strip" aria-label="agent-runtime-status">
        <div className="agent-runtime-strip__state">
          <span className={loading ? "agent-runtime-strip__dot agent-runtime-strip__dot--active" : "agent-runtime-strip__dot"} />
          <span>{loading ? "分析中" : result ? "已连接" : "待提问"}</span>
        </div>
        <div className="agent-runtime-strip__item">
          <span>Engine</span>
          <strong>{runtimeStatus.provider}</strong>
        </div>
        <div className="agent-runtime-strip__item">
          <span>Transport</span>
          <strong>{runtimeStatus.transport}</strong>
        </div>
        <div className="agent-runtime-strip__item">
          <span>Model</span>
          <strong>{runtimeStatus.model}</strong>
        </div>
        <div className="agent-runtime-strip__item">
          <span>Tools</span>
          <strong>{runtimeStatus.toolsets}</strong>
        </div>
        <div className="agent-runtime-strip__item">
          <span>Quality</span>
          <strong>{runtimeStatus.quality}</strong>
        </div>
      </div>

      {pageContext ? (
        <div
          style={{
            marginTop: 14,
            padding: 12,
            borderRadius: 14,
            border: `1px solid ${t.colorBorderSoft}`,
            background: t.colorBgSurface,
            color: t.colorTextSecondary,
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          <div style={{ color: t.colorTextMuted, marginBottom: 6 }}>页面上下文</div>
          <code style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {formatPageContextSummary(pageContext)}
          </code>
        </div>
      ) : null}

      <AgentQueryForm
        pageContext={pageContext}
        repoPath={repoPath}
        onRepoPathChange={setRepoPath}
        quickExamples={GITNEXUS_QUICK_EXAMPLES}
        onQuickExample={applyQuickExample}
        isCurrentRepoPinned={isCurrentRepoPinned}
        onPinCurrentRepo={pinCurrentRepo}
        onUnpinCurrentRepo={() => unpinRepo(repoPath.trim())}
        processLoading={processLoading}
        onLoadProcesses={() => void loadGitNexusProcesses(repoPath)}
        processSearch={processSearch}
        onProcessSearchChange={setProcessSearch}
        selectedProcess={selectedProcess}
        filteredProcesses={filteredProcesses}
        onSelectedProcessChange={setSelectedProcess}
        onViewSelectedProcess={() => void viewSelectedProcess()}
        loading={loading}
        query={query}
        onQueryChange={setQuery}
        onSubmit={handleSubmit}
      />

      <AgentRepoMemoryPanel
        pinnedRepoPaths={pinnedRepoPaths}
        recentUnpinnedRepoPaths={recentUnpinnedRepoPaths}
        onApplyRecentRepoPath={applyRecentRepoPath}
        onMovePinnedRepoPath={movePinnedRepoPath}
        onUnpinRepo={unpinRepo}
        onPinRepoPath={pinRepoPath}
      />

      {loading || agentRun ? (
        <div className="agent-wait-status" role="status" aria-live="polite">
          <div className="agent-wait-status__title">{formatAgentWaitTitle(agentRun?.status)}</div>
          <div className="agent-wait-status__detail">
            <span>{formatAgentRunStatusLabel(agentRun?.status, "运行中")}</span>
            <span>已等待 {formatAgentRunElapsed(agentRun, agentWaitSeconds)} 秒</span>
            {agentRun?.run_id ? <span>run_id: {agentRun.run_id}</span> : null}
            <span>后端会托管 Hermes bridge，页面刷新后可恢复最近任务。</span>
          </div>
        </div>
      ) : null}

      {error?.kind === "disabled" ? (
        <div
          style={{
            padding: 24,
            borderRadius: 16,
            border: `1px solid ${t.colorBorderWarning}`,
            background: t.colorBgWarningSoft,
            color: t.colorTextWarning,
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          智能体当前未启用。设置环境变量 MOSS_AGENT_ENABLED=true 后重启后端即可使用。
        </div>
      ) : null}

      {error?.kind === "request" ? (
        <div className="agent-callout agent-callout--error" role="alert">
          <strong>请求没有送达</strong>
          <span>{error.message}</span>
        </div>
      ) : null}

      {result ? (
        <div className="agent-result-shell">
          {hasRenderableResult(result) ? (
            <div className="agent-result-grid">
              <div className="agent-result-main">
                <AgentAnswerPanel answer={result.answer} />

                {result.cards.length > 0 ? (
                  (() => {
                    const gitNexusCards = isGitNexusResult(result)
                      ? result.cards
                      : result.cards.filter(isGitNexusCard);
                    const genericCards = isGitNexusResult(result)
                      ? []
                      : result.cards.filter((card) => !isGitNexusCard(card));
                    return (
                      <div className="agent-result-card-stack">
                        {gitNexusCards.length > 0 ? <AgentGitNexusResultView cards={gitNexusCards} /> : null}
                        <AgentGenericCardsGrid cards={genericCards} formatValue={formatMetaValue} />
                      </div>
                    );
                  })()
                ) : null}

                {result.next_drill.length > 0 ? (
                  <div className="agent-next-drill-row">
                    {result.next_drill.map((drill) => (
                      <span key={drill.dimension}>{drill.label}</span>
                    ))}
                  </div>
                ) : null}

                <AgentSuggestedActionsPanel
                  actions={result.suggested_actions}
                  formatValue={formatMetaValue}
                  activePayload={activeSuggestedActionPayload}
                  onActionClick={handleSuggestedAction}
                />
              </div>

              <aside className="agent-result-side">
                {hasEvidenceContent(result.evidence) ? (
                  <AgentEvidencePanel
                    tablesUsed={result.evidence.tables_used}
                    filtersApplied={result.evidence.filters_applied}
                    evidenceRows={result.evidence.evidence_rows}
                    qualityFlag={result.evidence.quality_flag}
                  />
                ) : null}
                <AgentResultMetaPanel
                  entries={buildResultMetaEntries(result.result_meta)}
                  formatValue={formatMetaValue}
                />
              </aside>
            </div>
          ) : (
            <div
              style={{
                padding: 20,
                borderRadius: 16,
                border: `1px solid ${t.colorBorderSoft}`,
                background: t.colorBgCanvas,
                color: t.colorTextSecondary,
                fontSize: 15,
                lineHeight: 1.75,
              }}
            >
              本次查询未返回可展示结果。请调整问题后重试。
            </div>
          )}

          {!hasRenderableResult(result) ? (
            <AgentResultMetaPanel
              entries={buildResultMetaEntries(result.result_meta)}
              formatValue={formatMetaValue}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function AgentWorkbenchPage({ pageContext }: AgentWorkbenchPageProps = {}) {
  return <AgentPanel pageContext={pageContext} showHeader />;
}
