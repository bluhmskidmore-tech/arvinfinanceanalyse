import type { PollingTaskPayload } from "../../../app/jobs/polling";
import { AgentApiError } from "../../../api/agentClient";
import { EM_DASH } from "../../../utils/format";
import type {
  AgentConversationContext,
  AgentPageContext,
  AgentQueryRequest,
  AgentRunStatus,
  AgentSuggestedAction,
} from "../../../api/contracts";

export type { AgentRunStatus };

export type AgentResultCard = {
  title: string;
  value?: string | null;
  type: string;
  data?: Record<string, unknown>[] | Record<string, unknown> | null;
  spec?: Record<string, unknown> | null;
};

export type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed?: string[];
  evidence_rows: number;
  quality_flag: string;
  evidence_strength?: string;
};

export type AgentNextDrill = {
  dimension: string;
  label: string;
};

export type AgentQueryResult = {
  answer: string;
  cards: AgentResultCard[];
  evidence: AgentEvidence;
  result_meta: Record<string, unknown>;
  next_drill: AgentNextDrill[];
  suggested_actions: AgentSuggestedAction[];
};

export type AgentCopyFeedback = { turnId: string; status: "success" | "error" };

export type PendingSuggestedActionConfirmation = { turnId: string; actionKey: string };

export type AgentRunPayload = PollingTaskPayload & {
  run_id: string;
  status: AgentRunStatus;
  run_kind?: "managed" | "workflow" | "sync";
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

export type AgentQueryError =
  | {
      kind: "disabled";
      detail: string;
      phase: string;
    }
  | {
      kind: "request";
      message: string;
    };

export type AgentConversationTurn = {
  id: string;
  question: string;
  conversationContext?: AgentConversationContext;
  retryMode?: "ordinary";
  stopped?: boolean;
  runRequestLatencyMs?: number;
  agentRun: AgentRunPayload | null;
  result: AgentQueryResult | null;
  error: AgentQueryError | null;
  activeSuggestedActionPayload: Record<string, unknown> | null;
};

export type AgentWorkbenchPageProps = {
  pageContext?: AgentPageContext;
};

export type AgentCopilotVariant = "embedded" | "workbench";

export type EmbeddedAgentCopilotProps = AgentWorkbenchPageProps & {
  variant?: AgentCopilotVariant;
  showHeader?: boolean;
  /**
   * 只读语义：禁止执行 execute_intent 类建议动作（仅展示），
   * 输入提问与追问填入（inspect_drill / next_drill）仍然可用。
   */
  readOnly?: boolean;
  defaultQuestion?: string;
};

export type AgentOrdinaryConversationMode = "unknown" | "managed" | "local_sync";

export type FinancialWorkflowShortcut = {
  id: string;
  title: string;
  slashCommand: string;
  description: string;
  mappedIntents: string[];
};

export type ResearchDomain = "stock" | "macro";

export type ResearchShortcut = {
  id: string;
  title: string;
  question: string;
  description: string;
  domain?: ResearchDomain;
  basis?: "formal" | "analytical";
  filters?: Record<string, unknown>;
  context?: Record<string, unknown>;
  commandLabel?: string;
};

export class AgentDisabledQueryError extends Error {
  detail: string;
  phase: string;

  constructor(detail: string, phase: string) {
    super(detail);
    this.name = "AgentDisabledQueryError";
    this.detail = detail;
    this.phase = phase;
  }
}

export class AgentManagedRunRequiresHermesError extends Error {
  detail: string;

  constructor(detail: string) {
    super(detail);
    this.name = "AgentManagedRunRequiresHermesError";
    this.detail = detail;
  }
}

/** 托管 run 在等待期间进入 cancelled 终态：携带终态载荷，供 UI 渲染取消态而非错误态。 */
export class AgentRunCancelledError extends Error {
  readonly payload: AgentRunPayload;

  constructor(payload: AgentRunPayload) {
    super(payload.error_message || "这次回答的任务已取消。");
    this.name = "AgentRunCancelledError";
    this.payload = payload;
  }
}

export const AGENT_RUN_STATUSES = new Set<AgentRunStatus>([
  "queued",
  "starting",
  "running",
  "completed",
  "failed",
  "cancelled",
]);

/** 后端 AgentRunStatus 终态集合：cancelled 与 completed/failed 一样结束 SSE/轮询等待。 */
export const AGENT_RUN_TERMINAL_STATUSES = new Set<string>(["completed", "failed", "cancelled"]);

export function isTerminalAgentRunStatus(status: string) {
  return AGENT_RUN_TERMINAL_STATUSES.has(status);
}

export const MAX_AGENT_CONTEXT_TURNS = 4;

export const MAX_AGENT_STORED_TURNS = 4;

export const MAX_AGENT_QUEUED_QUERIES = 4;

export const MAX_AGENT_CONTEXT_QUESTION_LENGTH = 800;

export const MAX_AGENT_CONTEXT_ANSWER_LENGTH = 1400;

export const AGENT_RUN_POLL_MAX_ATTEMPTS = 240;

/** 轮询遇到瞬时错误（网络抖动等）时允许的最大连续重试次数。 */
export const AGENT_RUN_POLL_TRANSIENT_RETRY_LIMIT = 3;

/** 瞬时错误重试退避：500ms → 1s → 2s（consecutiveErrorCount 从 1 起）。 */
export function getAgentRunPollTransientRetryDelayMs(consecutiveErrorCount: number) {
  return Math.min(2000, 500 * 2 ** Math.max(0, consecutiveErrorCount - 1));
}

export const AGENT_RUN_POLL_NETWORK_RECOVERABLE_MESSAGE =
  "网络连接不稳定，已暂停等待。任务可能仍在后台运行：可稍后重试这一轮，或刷新页面尝试恢复。";

export const AGENT_RUN_POLL_TIMEOUT_RECOVERABLE_MESSAGE =
  "等待超时：任务可能仍在后台运行。可刷新页面尝试恢复，或重试这一轮。";

export const AGENT_STICKY_BOTTOM_THRESHOLD_PX = 96;

export const latestAgentRunStatusRequests = new Map<string, Promise<AgentRunPayload>>();

export const ANALYSIS_CHAT_PATTERNS = [
  "analysis",
  "analyze",
  "explain",
  "summarize",
  "summary",
  "judge",
  "risk",
  "what does this mean",
  "continue",
  "follow up",
  "分析",
  "解释",
  "总结",
  "判断",
  "风险",
  "结论",
  "说明",
  "继续",
  "追问",
];

export const GOVERNED_AGENT_PATTERNS = [
  "gitnexus",
  "repo graph",
  "code graph",
  "processes",
  "产品损益",
  "ftp",
  "桥接",
  "归因",
  "拆解",
  "bridge",
  "attribution",
  "风险张量",
  "krd",
  "久期",
  "dv01",
  "duration",
  "信用",
  "利差",
  "集中度",
  "credit",
  "spread",
  "concentration",
  "组合概览",
  "资产规模",
  "总览",
  "portfolio overview",
  "market value",
  "portfolio value",
  "asset size",
  "损益",
  "收益",
  "pnl",
  "宏观",
  "利率",
  "市场数据",
  "macro",
  "market data",
  "macro data",
  "rates data",
  "新闻",
  "事件",
  "news",
  "headline",
  "latest news",
];

export const LOCAL_AGENT_QUERY_INTENT_PATTERNS = [
  {
    intent: "portfolio_overview",
    patterns: [
      "组合概览",
      "资产规模",
      "总览",
      "portfolio overview",
      "market value",
      "portfolio value",
      "asset size",
    ],
  },
];

export const LOCAL_OPEN_CHAT_EXACT = new Set([
  "?",
  "??",
  "在吗",
  "在么",
  "你好",
  "您好",
  "hello",
  "hi",
  "hey",
  "ping",
]);

export const LOCAL_OPEN_CHAT_PATTERNS = [
  "你能做什么",
  "能做什么",
  "你会什么",
  "怎么用",
  "如何使用",
  "你是谁",
  "闲聊",
  "随便聊聊",
  "聊聊天",
  "帮我想想",
  "给点建议",
  "有什么建议",
  "该关注什么",
  "需要关注什么",
  "早上好",
  "晚上好",
  "谢谢",
  "没事",
  "what can you do",
  "who are you",
  "how do i use",
  "help me think",
  "chat",
];

export const PROVIDER_CHAT_CARD_TITLES = new Set(["Hermes Agent", "Provider", "Model"]);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isAgentQueryResult(value: unknown): value is AgentQueryResult {
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

export function isAgentResultCard(value: unknown): value is AgentResultCard {
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

export function isAgentEvidence(value: unknown): value is AgentEvidence {
  return (
    isRecord(value) &&
    Array.isArray(value.tables_used) &&
    value.tables_used.every((item) => typeof item === "string") &&
    isRecord(value.filters_applied) &&
    (value.sql_executed == null ||
      (Array.isArray(value.sql_executed) &&
        value.sql_executed.every((item) => typeof item === "string"))) &&
    typeof value.evidence_rows === "number" &&
    typeof value.quality_flag === "string" &&
    (value.evidence_strength === undefined || typeof value.evidence_strength === "string")
  );
}

export function isAgentNextDrill(value: unknown): value is AgentNextDrill {
  return (
    isRecord(value) &&
    typeof value.dimension === "string" &&
    typeof value.label === "string"
  );
}

export function isAgentSuggestedAction(value: unknown): value is AgentSuggestedAction {
  return (
    isRecord(value) &&
    typeof value.type === "string" &&
    typeof value.label === "string" &&
    isRecord(value.payload) &&
    typeof value.requires_confirmation === "boolean" &&
    (value.confirmation_token === undefined ||
      value.confirmation_token === null ||
      typeof value.confirmation_token === "string")
  );
}

export function getExecutableSuggestedIntent(action: AgentSuggestedAction): string | null {
  if (action.type !== "execute_intent") {
    return null;
  }
  const intent = action.payload.intent;
  return typeof intent === "string" && intent.trim().length > 0 ? intent.trim() : null;
}

export function getSuggestedActionKey(action: AgentSuggestedAction) {
  return `${action.type}:${action.label}:${JSON.stringify(action.payload)}:${action.confirmation_token ?? ""}`;
}

export function isPlainAnalysisConversationQuestion(question: string) {
  const normalized = question.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return (
    ANALYSIS_CHAT_PATTERNS.some((pattern) => normalized.includes(pattern)) &&
    !GOVERNED_AGENT_PATTERNS.some((pattern) => normalized.includes(pattern))
  );
}

export function isLocalOpenChatQuestion(question: string) {
  const normalized = question.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  const compact = normalized.replace(/\s+/g, "");
  if (LOCAL_OPEN_CHAT_EXACT.has(compact)) {
    return true;
  }
  if (GOVERNED_AGENT_PATTERNS.some((pattern) => normalized.includes(pattern) || compact.includes(pattern))) {
    return false;
  }
  return (
    compact.length <= 32 &&
    LOCAL_OPEN_CHAT_PATTERNS.some((pattern) => normalized.includes(pattern) || compact.includes(pattern))
  );
}

export function getLocalAgentQueryIntent(question: string) {
  const normalized = question.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return (
    LOCAL_AGENT_QUERY_INTENT_PATTERNS.find(({ patterns }) =>
      patterns.some((pattern) => normalized.includes(pattern)),
    )?.intent ?? null
  );
}

export function shouldUseLocalAnalysisConversation(
  question: string,
  conversationContext?: AgentConversationContext,
) {
  if (!isPlainAnalysisConversationQuestion(question)) {
    return false;
  }
  const recentTurns = conversationContext?.recent_turns ?? [];
  if (recentTurns.length === 0) {
    return true;
  }
  const latestTurn = recentTurns[recentTurns.length - 1];
  return latestTurn?.result_kind === "agent.analysis_chat";
}

export function isResearchRadarResult(result: AgentQueryResult) {
  return result.result_meta.result_kind === "agent.research_radar_brief";
}

export function isAgentConversationContext(value: unknown): value is AgentConversationContext {
  return (
    isRecord(value) &&
    Array.isArray(value.recent_turns) &&
    value.recent_turns.every(
      (turn) =>
        isRecord(turn) &&
        typeof turn.question === "string" &&
        typeof turn.answer === "string" &&
        (turn.run_id === undefined || turn.run_id === null || typeof turn.run_id === "string") &&
        (turn.trace_id === undefined || turn.trace_id === null || typeof turn.trace_id === "string") &&
        (turn.result_kind === undefined || turn.result_kind === null || typeof turn.result_kind === "string"),
    )
  );
}

export function isAgentQueryError(value: unknown): value is AgentQueryError {
  if (!isRecord(value) || typeof value.kind !== "string") {
    return false;
  }
  if (value.kind === "request") {
    return typeof value.message === "string";
  }
  return value.kind === "disabled" && typeof value.detail === "string" && typeof value.phase === "string";
}

export function getManagedRunRequiresHermesDetail(value: unknown) {
  if (!isRecord(value) || typeof value.detail !== "string") {
    return null;
  }
  const detail = value.detail.trim();
  if (!detail.startsWith("Agent runs require MOSS_AGENT_PROVIDER=")) {
    return null;
  }
  return detail;
}

export function isAgentRunStatus(value: unknown): value is AgentRunStatus {
  return typeof value === "string" && AGENT_RUN_STATUSES.has(value as AgentRunStatus);
}

export function isAgentRunPayload(value: unknown): value is AgentRunPayload {
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

export function normalizeAgentResult(result: AgentQueryResult): AgentQueryResult {
  result.suggested_actions = result.suggested_actions ?? [];
  return result;
}

export function normalizeAgentRunPayload(payload: AgentRunPayload): AgentRunPayload {
  if (payload.result) {
    payload.result = normalizeAgentResult(payload.result);
  }
  return payload;
}

export function createAgentConversationTurn(
  question: string,
  conversationContext?: AgentConversationContext,
  retryMode?: "ordinary",
): AgentConversationTurn {
  return {
    id: `turn:${Date.now()}:${Math.random().toString(16).slice(2)}`,
    question,
    conversationContext,
    retryMode,
    stopped: false,
    agentRun: null,
    result: null,
    error: null,
    activeSuggestedActionPayload: null,
  };
}

export function formatConversationContextBadge(conversationContext?: AgentConversationContext) {
  const turnCount = conversationContext?.recent_turns.length ?? 0;
  return turnCount > 0 ? `已带入 ${turnCount} 轮上下文` : null;
}

export function trimAgentContextText(value: string, limit: number) {
  const normalized = value.trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 3)}...`;
}

export function formatQueuedComposerHint(queuedQuery: string, queuedCount: number) {
  const preview = trimAgentContextText(queuedQuery.replace(/\s+/g, " "), 48);
  return queuedCount > 1 ? `${queuedCount} 句已排队 · 刚加入：${preview}` : `已接住下一句：${preview} · 回答完自动发送`;
}

export function buildConversationContext(turns: AgentConversationTurn[]): AgentConversationContext | undefined {
  const history = turns
    .filter((turn) => turn.question.trim() && turn.result?.answer.trim())
    .slice(-MAX_AGENT_CONTEXT_TURNS)
    .map((turn) => {
      const traceId = turn.result?.result_meta.trace_id;
      const resultKind = turn.result?.result_meta.result_kind;
      return {
        question: trimAgentContextText(turn.question, MAX_AGENT_CONTEXT_QUESTION_LENGTH),
        answer: trimAgentContextText(turn.result?.answer ?? "", MAX_AGENT_CONTEXT_ANSWER_LENGTH),
        run_id: turn.agentRun?.run_id ?? null,
        trace_id: typeof traceId === "string" ? traceId : null,
        result_kind: typeof resultKind === "string" ? resultKind : null,
      };
    });

  return history.length > 0 ? { recent_turns: history } : undefined;
}

export function buildRestoredManagedTurn(payload: AgentRunPayload): AgentConversationTurn {
  const restoredQuestion = payload.question?.trim() || formatManagedRunRestoreQuestion(payload.provider);
  const nextError: AgentQueryError | null =
    payload.status === "failed"
      ? {
          kind: "request",
          message: payload.error_message || formatManagedRunFailureMessage(payload.provider),
        }
      : null;
  return {
    id: `restored:${payload.run_id}`,
    question: restoredQuestion,
    retryMode: "ordinary",
    agentRun: payload,
    result: payload.status === "completed" && payload.result ? payload.result : null,
    error: nextError,
    activeSuggestedActionPayload: null,
  };
}

export function mergeRestoredManagedTurn(
  currentTurns: AgentConversationTurn[],
  payload: AgentRunPayload,
): AgentConversationTurn[] {
  const restoredTurn = buildRestoredManagedTurn(payload);
  const matchingIndex = currentTurns.findIndex(
    (turn) =>
      turn.agentRun?.run_id === payload.run_id ||
      turn.id === restoredTurn.id ||
      (turn.retryMode === "ordinary" &&
        !turn.agentRun &&
        turn.question.trim() &&
        payload.question?.trim() === turn.question.trim()),
  );
  if (matchingIndex < 0) {
    return [...currentTurns, restoredTurn].slice(-MAX_AGENT_STORED_TURNS);
  }

  const nextTurns = [...currentTurns];
  const currentTurn = nextTurns[matchingIndex];
  nextTurns[matchingIndex] = {
    ...restoredTurn,
    id: currentTurn.id,
    question: currentTurn.question.trim() ? currentTurn.question : restoredTurn.question,
    conversationContext: currentTurn.conversationContext,
    retryMode: currentTurn.retryMode ?? restoredTurn.retryMode,
  };
  return nextTurns.slice(-MAX_AGENT_STORED_TURNS);
}

export function buildErrorMessage(error: unknown) {
  if (isFetchNetworkError(error)) {
    return "无法连接 Agent 后端。请确认 7888 后端、5888 前端代理和 Hermes 桥接服务正在运行。";
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "智能体查询失败，请稍后重试。";
}

export function getAgentApiErrorPayload(error: unknown) {
  return error instanceof AgentApiError ? error.payload : null;
}

export function getAgentApiErrorStatus(error: unknown) {
  return error instanceof AgentApiError ? error.status : null;
}

export function isFetchNetworkError(error: unknown) {
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

export function hasEvidenceContent(evidence: AgentEvidence) {
  return (
    evidence.tables_used.length > 0 ||
    Object.keys(evidence.filters_applied).length > 0 ||
    (evidence.sql_executed?.length ?? 0) > 0 ||
    evidence.evidence_rows > 0 ||
    evidence.quality_flag.trim().length > 0
  );
}

export const GOVERNANCE_QUALITY_FLAG_NOTICES: Record<string, string> = {
  stale: "证据数据可能陈旧，请核对报告日期后再使用",
  warning: "证据质量存在预警，结论请人工复核",
};

export function buildGovernanceNotices(result: AgentQueryResult) {
  const notices: string[] = [];
  const evidenceStrength = String(
    result.evidence.evidence_strength ?? result.result_meta.evidence_strength ?? "",
  ).trim();
  const hasSpecificEvidenceWarning =
    evidenceStrength === "provider_runtime" ||
    evidenceStrength === "local_fallback" ||
    evidenceStrength === "mixed";
  if (evidenceStrength === "provider_runtime") {
    notices.push("当前仅有外部模型与工具运行证据，未证明 MOSS 指标口径");
  } else if (evidenceStrength === "local_fallback") {
    notices.push("当前为本地降级回答，未运行受治理指标查询");
  } else if (evidenceStrength === "mixed") {
    notices.push("当前回答由外部模型基于 MOSS 只读上下文生成，不等同受治理指标结论");
  }
  const qualityNotice = GOVERNANCE_QUALITY_FLAG_NOTICES[result.evidence.quality_flag.trim()];
  if (qualityNotice && !(result.evidence.quality_flag.trim() === "warning" && hasSpecificEvidenceWarning)) {
    notices.push(qualityNotice);
  }
  const fallbackMode = result.result_meta.fallback_mode;
  if (typeof fallbackMode === "string" && fallbackMode.trim() && fallbackMode.trim() !== "none") {
    notices.push(
      fallbackMode.trim() === "latest_snapshot"
        ? "结果使用最新快照降级数据，未命中请求日期"
        : `结果处于降级模式：${fallbackMode.trim()}`,
    );
  }
  if (result.result_meta.formal_use_allowed === false) {
    notices.push("本结果不可作为正式口径，仅供分析参考");
  }
  return notices;
}

export function hasRenderableResult(result: AgentQueryResult) {
  return (
    result.answer.trim().length > 0 ||
    result.cards.length > 0 ||
    hasEvidenceContent(result.evidence) ||
    result.next_drill.length > 0 ||
    result.suggested_actions.length > 0
  );
}

export function isCompactProviderChatResult(result: AgentQueryResult) {
  const resultKind = String(result.result_meta.result_kind ?? "").trim();
  if (resultKind === "agent.hermes_fallback" || resultKind === "agent.local_chat") {
    return true;
  }
  return (
    resultKind === "agent.hermes" &&
    result.cards.length > 0 &&
    result.cards.every((card) => PROVIDER_CHAT_CARD_TITLES.has(card.title.trim()))
  );
}

export function isCompactProviderChatTurn(turn: AgentConversationTurn) {
  return Boolean(turn.result && isCompactProviderChatResult(turn.result));
}

export function buildResultMetaEntries(resultMeta: Record<string, unknown>) {
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

export function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return EM_DASH;
  }
  if (typeof value === "string") {
    return value.trim().length > 0 ? value : EM_DASH;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function formatRuntimeLabel(value: unknown, fallback: string) {
  if (typeof value !== "string") {
    return fallback;
  }
  const normalized = value.trim();
  return normalized || fallback;
}

export function formatProviderLabel(value: unknown, fallback: string) {
  const label = formatRuntimeLabel(value, fallback);
  switch (label.toLowerCase()) {
    case "hermes":
      return "Hermes";
    case "dexter":
      return "Dexter";
    default:
      return label;
  }
}

export function formatManagedProviderLabel(provider: unknown) {
  if (typeof provider !== "string" || provider.trim().length === 0) {
    return null;
  }
  return formatProviderLabel(provider, "托管运行时");
}

export function formatManagedRunTitle(status: AgentRunStatus | undefined, provider: unknown) {
  const providerLabel = formatManagedProviderLabel(provider);
  if (!status) {
    return "已收到问题";
  }
  switch (status) {
    case "queued":
      return providerLabel ? `${providerLabel} 已排队` : "托管任务已排队";
    case "starting":
      return providerLabel ? `${providerLabel} 正在启动` : "托管任务启动中";
    case "running":
      return providerLabel ? `${providerLabel} 正在分析` : "托管任务分析中";
    case "completed":
      return providerLabel ? `${providerLabel} 托管任务完成` : "托管任务完成";
    case "failed":
      return providerLabel ? `${providerLabel} 托管任务失败` : "托管任务失败";
    case "cancelled":
      return providerLabel ? `${providerLabel} 托管任务已取消` : "托管任务已取消";
    default:
      return providerLabel ? `${providerLabel} 正在分析` : "托管任务分析中";
  }
}

export function formatManagedRunFailureMessage(provider: unknown) {
  const providerLabel = formatManagedProviderLabel(provider);
  return providerLabel
    ? `${providerLabel} 托管任务失败，请稍后重试。`
    : "托管任务失败，请稍后重试。";
}

export function formatManagedRunRestoreQuestion(provider: unknown) {
  const providerLabel = formatManagedProviderLabel(provider);
  return providerLabel ? `恢复上一次 ${providerLabel} 对话` : "恢复上一次托管对话";
}

export function formatAgentRunStatusLabel(status: AgentRunStatus | undefined, fallback = EM_DASH) {
  if (!status) {
    return fallback;
  }
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
    case "cancelled":
      return "已取消";
    default:
      return fallback;
  }
}

export function formatAgentTurnWaitTitle(agentRun: AgentRunPayload | null) {
  if (agentRun?.run_kind === "workflow") {
    if (agentRun.status === "failed") {
      return "Workflow 执行失败";
    }
    if (agentRun.status === "completed") {
      return "Workflow 执行完成";
    }
    return "Workflow 执行进行中";
  }
  if (agentRun?.run_kind === "sync") {
    if (agentRun.status === "failed") {
      return "本地查询失败";
    }
    if (agentRun.status === "completed") {
      return "本地查询完成";
    }
    return "本地查询进行中";
  }
  return formatManagedRunTitle(agentRun?.status, agentRun?.provider);
}

export function formatAgentWaitPhase(agentRun: AgentRunPayload | null) {
  if (agentRun?.run_kind === "workflow") {
    if (agentRun.status === "running") {
      return "正在执行本地模板";
    }
    if (agentRun.status === "starting") {
      return "正在准备本地模板";
    }
    if (agentRun.status === "queued") {
      return "等待本地模板";
    }
  }
  if (agentRun?.run_kind === "sync") {
    if (agentRun.status === "running") {
      return "正在快速整理";
    }
    if (agentRun.status === "starting") {
      return "准备本地查询";
    }
    if (agentRun.status === "queued") {
      return "等待本地查询";
    }
  }
  const status = agentRun?.status;
  if (!status) {
    return "正在选择回答路径";
  }
  if (status === "queued") {
    return "等待开始";
  }
  if (status === "starting") {
    return "正在准备";
  }
  if (status === "running") {
    return "正在整理回答";
  }
  return formatAgentRunStatusLabel(status, "运行中");
}

export function formatAgentRunElapsed(agentRun: AgentRunPayload | null, fallbackSeconds: number) {
  if (typeof agentRun?.elapsed_seconds === "number" && Number.isFinite(agentRun.elapsed_seconds)) {
    return Math.max(0, Math.round(agentRun.elapsed_seconds));
  }
  return fallbackSeconds;
}

export function normalizeAgentRunRequestLatencyMs(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return undefined;
  }
  return Math.round(value);
}

export function getAgentRequestClockMs() {
  return Date.now();
}

export function formatAgentConnectionElapsed(latencyMs: number | undefined) {
  const normalizedLatencyMs = normalizeAgentRunRequestLatencyMs(latencyMs);
  if (normalizedLatencyMs === undefined) {
    return null;
  }
  const seconds = normalizedLatencyMs / 1000;
  if (seconds < 10) {
    return `${seconds.toFixed(1)} 秒`;
  }
  return `${Math.round(seconds)} 秒`;
}

export function formatAgentWaitHint(agentRun: AgentRunPayload | null, waitSeconds: number) {
  if (agentRun?.run_kind === "workflow") {
    if (agentRun.status === "queued" || agentRun.status === "starting") {
      return "本地模板正在准备，结果会直接出现在这里。";
    }
    if (agentRun.status === "running" && waitSeconds >= 10) {
      return "本地模板还在处理，复杂问题通常会多等一会儿。";
    }
    if (agentRun.status === "running") {
      return "本地模板正在生成结果，页面会自动更新。";
    }
    if (agentRun.status === "completed") {
      return "结果已返回，可以继续追问。";
    }
    if (agentRun.status === "failed") {
      return "这次 workflow 没有完成，可以调整问题后重试。";
    }
  }
  if (agentRun?.run_kind === "sync") {
    if (agentRun.status === "queued" || agentRun.status === "starting") {
      return "正在准备快速回答，结果会直接出现在这里。";
    }
    if (agentRun.status === "running" && waitSeconds >= 10) {
      return "本地查询还在处理，复杂问题通常会多等一会儿。";
    }
    if (agentRun.status === "running") {
      return "正在快速整理，页面会自动更新。";
    }
    if (agentRun.status === "completed") {
      return "结果已返回，可以继续追问。";
    }
    if (agentRun.status === "failed") {
      return "这次本地查询没有完成，可以调整问题后重试。";
    }
  }
  const status = agentRun?.status;
  if (!status) {
    if (waitSeconds >= 12) {
      return "还没拿到运行状态，可以停止等待后重试，或继续输入下一句。";
    }
    if (waitSeconds >= 6) {
      return "还在连接回答通道；拿到状态后会继续更新。";
    }
    return "已收到，我正在判断是直接回答还是先查证据。";
  }
  if (status === "queued") {
    return "已排队；如果前面还有回答，会按顺序处理。";
  }
  if (status === "starting") {
    return "正在准备回答环境，马上开始整理。";
  }
  if (status === "running" && waitSeconds >= 10) {
    return "还在查证据和组织回答，复杂问题通常会多等一会儿。";
  }
  if (status === "running") {
    return "正在查证据并整理回答，页面会自动更新。";
  }
  if (status === "completed") {
    return "可以离开或刷新，回来后会继续显示这次结果。";
  }
  if (status === "failed") {
    return "这次没有完成，可以调整问题后重试。";
  }
  if (status === "cancelled") {
    return "这次任务已取消，可编辑问题后重新发送。";
  }
  return "可以离开或刷新，回来后会继续显示这次结果。";
}

export function formatAgentThinkingLabel(agentRun: AgentRunPayload | null, waitSeconds: number) {
  if (!agentRun?.status) {
    if (waitSeconds >= 12) {
      return "还在连接";
    }
    if (waitSeconds >= 6) {
      return "连接中";
    }
    return "已收到";
  }
  if (agentRun.status === "queued" || agentRun.status === "starting") {
    return "正在准备";
  }
  if (agentRun.status === "running") {
    return "正在整理";
  }
  return "正在更新";
}

export function formatAgentThinkingText(agentRun: AgentRunPayload | null, waitSeconds: number) {
  if (!agentRun?.status) {
    if (waitSeconds >= 12) {
      return "还没拿到运行状态，可以停止等待，或继续输入下一句。";
    }
    if (waitSeconds >= 6) {
      return "还在连接回答通道，页面会继续自动更新。";
    }
    return "我先判断该直接回答，还是先查证据。";
  }
  if (agentRun.run_kind === "sync") {
    return waitSeconds >= 6 ? "正在快速整理，稍后直接给你结果。" : "走快速回答通道，正在整理。";
  }
  if (agentRun.run_kind === "workflow") {
    return waitSeconds >= 10 ? "本地模板还在处理，可以继续输入下一句。" : "本地模板已开始处理。";
  }
  if (agentRun.status === "queued") {
    return "已经排上队，轮到后会自动更新。";
  }
  if (agentRun.status === "starting") {
    return "正在准备回答环境。";
  }
  if (agentRun.status === "running" && waitSeconds >= 10) {
    return "还在查证据，复杂问题会多等一会儿。";
  }
  if (agentRun.status === "running") {
    return "正在查证据并组织回答。";
  }
  return "状态有更新，我会继续刷新这一轮。";
}

export function getAgentRunProgressIndex(agentRun: AgentRunPayload | null) {
  if (!agentRun?.status) {
    return 1;
  }
  if (agentRun.status === "queued") {
    return 2;
  }
  if (agentRun.status === "starting") {
    return 2;
  }
  if (agentRun.status === "running") {
    return 3;
  }
  if (agentRun.status === "completed") {
    return 4;
  }
  return 0;
}

export function shouldDisplayAgentRunId(agentRun: AgentRunPayload | null) {
  if (!agentRun?.run_id) {
    return false;
  }
  if (agentRun.run_kind === "sync") {
    return false;
  }
  return agentRun.run_id !== "agent_run:sync_compat";
}

export function getAgentRunPollIntervalMs(_payload: AgentRunPayload, attempt: number) {
  if (attempt < 5) {
    return 120;
  }
  if (attempt < 20) {
    return 500;
  }
  return 1000;
}

export function buildRuntimeStatus(
  result: AgentQueryResult | null,
  loading: boolean,
  agentRun: AgentRunPayload | null,
) {
  const filters = result?.evidence.filters_applied ?? {};
  const statusLabel = formatAgentRunStatusLabel(agentRun?.status, loading ? "分析中" : EM_DASH);
  return {
    provider: formatProviderLabel(agentRun?.provider ?? filters.provider, loading ? "托管运行时" : "待连接"),
    transport: formatRuntimeLabel(agentRun?.transport ?? filters.transport, loading ? "bridge" : "等待提问"),
    model: formatRuntimeLabel(agentRun?.model ?? filters.model, EM_DASH),
    toolsets: formatRuntimeLabel(agentRun?.toolsets ?? filters.toolsets, EM_DASH),
    quality: formatRuntimeLabel(result?.evidence.quality_flag, statusLabel),
  };
}

export function findLatestTurnWithResult(turns: AgentConversationTurn[]) {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    if (turns[index]?.result) {
      return turns[index];
    }
  }
  return null;
}

export function findLatestTurnWithRun(turns: AgentConversationTurn[]) {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    if (turns[index]?.agentRun) {
      return turns[index];
    }
  }
  return null;
}

export const GITNEXUS_QUICK_EXAMPLES = [
  "解释当前页面的主要结论和风险点",
  "组合概览：规模、损益、久期和信用风险有什么变化？",
  "本日损益主要由什么驱动？请给证据和下一步复核建议。",
  "当前久期和信用集中度有什么异常？",
  "请给我看 GitNexus 状态",
  "请给我看 GitNexus context",
  "请给我看 GitNexus processes",
] as const;

export const FINANCIAL_WORKFLOWS: FinancialWorkflowShortcut[] = [
  {
    id: "portfolio_review",
    title: "组合复核",
    slashCommand: "/portfolio-review",
    description: "组合规模、久期和信用暴露",
    mappedIntents: ["portfolio_overview", "duration_risk", "credit_exposure"],
  },
  {
    id: "pnl_review",
    title: "损益复核",
    slashCommand: "/pnl-review",
    description: "损益摘要、归因桥和产品损益",
    mappedIntents: ["pnl_summary", "pnl_bridge", "product_pnl"],
  },
  {
    id: "risk_memo",
    title: "风险纪要",
    slashCommand: "/risk-memo",
    description: "久期、信用暴露和风险张量",
    mappedIntents: ["duration_risk", "credit_exposure", "risk_tensor"],
  },
  {
    id: "market_brief",
    title: "市场简报",
    slashCommand: "/market-brief",
    description: "市场数据和新闻入口",
    mappedIntents: ["market_data", "news"],
  },
];

export const RESEARCH_SHORTCUTS: ResearchShortcut[] = [
  {
    id: "research_radar_brief",
    title: "研究速读",
    question: "研究速读",
    description: "分析口径的新闻速读入口，先看原始事件证据，再看解释和后续检查链接。",
    basis: "analytical",
    filters: {},
    context: {
      intent: "research_radar_brief",
      workflow_id: "research_radar_brief",
    },
    commandLabel: "local analytical",
  },
  {
    id: "stock_research",
    title: "股票研究",
    question: "Review landed stock research context",
    description: "复核已刷新的股票数据、证据和限制。",
    domain: "stock",
    filters: { research_domain: "stock" },
  },
  {
    id: "macro_research",
    title: "宏观研究",
    question: "Review landed macro research context",
    description: "复核已刷新的宏观序列、证据和限制。",
    domain: "macro",
    filters: { research_domain: "macro" },
  },
];

export const AGENT_FOLLOW_UP_CHIPS = [
  {
    label: "展开依据",
    question: "请基于上一轮回答展开证据依据和关键假设。",
  },
  {
    label: "给下一步",
    question: "请基于上一轮回答给出最值得执行的下一步行动。",
  },
  {
    label: "转检查清单",
    question: "请把上一轮回答转成可执行的复核检查清单。",
  },
] as const;

export const GITNEXUS_PROCESS_CARD_TITLE = "GitNexus Processes Table";

export function buildAgentRequestBody(
  question: string,
  repoPath: string,
  processName: string,
  conversationContext?: AgentConversationContext,
  pageContext?: AgentPageContext,
  contextPatch?: Record<string, unknown>,
): AgentQueryRequest {
  return {
    question,
    basis: "formal",
    filters: buildFilters(question, repoPath, processName),
    position_scope: "all",
    currency_basis: "CNY",
    context: {
      user_id: "web-user",
      ...(conversationContext ? { conversation: conversationContext } : {}),
      ...(contextPatch ?? {}),
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

export function shouldScrollComposerInputIntoView(input: HTMLTextAreaElement) {
  const visualViewport = window.visualViewport;
  const viewportTop = visualViewport?.offsetTop ?? 0;
  const viewportHeight = visualViewport?.height ?? window.innerHeight ?? document.documentElement.clientHeight;
  const viewportBottom = viewportTop + viewportHeight;
  const rect = input.getBoundingClientRect();
  return rect.top < viewportTop || rect.bottom > viewportBottom;
}

export function buildFinancialWorkflowRequestBody(
  workflow: FinancialWorkflowShortcut,
  pageContext?: AgentPageContext,
): AgentQueryRequest {
  return {
    question: workflow.slashCommand,
    basis: "formal",
    filters: {},
    position_scope: "all",
    currency_basis: "CNY",
    context: {
      user_id: "web-user",
      workflow_mode: "execute",
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

export function buildResearchRequestBody(
  shortcut: ResearchShortcut,
  pageContext?: AgentPageContext,
): AgentQueryRequest {
  return {
    question: shortcut.question,
    basis: shortcut.basis ?? "formal",
    filters: shortcut.filters ?? (shortcut.domain ? { research_domain: shortcut.domain } : {}),
    position_scope: "all",
    currency_basis: "CNY",
    context: {
      user_id: "web-user",
      ...(shortcut.context ?? {}),
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

export function buildLocalSyncAgentRun(
  runId: string,
  question: string,
  status: AgentRunStatus,
  result?: AgentQueryResult | null,
  errorMessage?: string,
): AgentRunPayload {
  const filters = result?.evidence.filters_applied ?? {};
  return {
    run_id: runId,
    status,
    run_kind: "sync",
    question,
    provider: formatRuntimeLabel(filters.provider, "local"),
    model: formatRuntimeLabel(filters.model, "default"),
    transport: formatRuntimeLabel(filters.transport, "sync"),
    toolsets: formatRuntimeLabel(filters.toolsets, "default"),
    error_message: errorMessage,
    result: result ?? null,
  };
}

export function buildPendingAgentRun(
  runId: string,
  question: string,
  runKind: "workflow" | "sync",
): AgentRunPayload {
  return {
    run_id: runId,
    status: "starting",
    run_kind: runKind,
    question,
    provider: "local",
    model: runKind === "workflow" ? "MOSS intents" : "default",
    transport: "sync",
    toolsets: runKind === "workflow" ? "workflow" : "GitNexus",
    result: null,
  };
}

export function isGitNexusCard(card: AgentResultCard) {
  return card.title.startsWith("GitNexus ");
}

export function isGitNexusResult(result: AgentQueryResult) {
  return result.result_meta.result_kind === "agent.gitnexus_status";
}

export function extractProcessNames(cards: AgentResultCard[]) {
  const processCard = cards.find((card) => card.title === GITNEXUS_PROCESS_CARD_TITLE);
  if (!processCard || !Array.isArray(processCard.data)) {
    return [];
  }
  return processCard.data
    .map((row) => (isRecord(row) && typeof row.name === "string" ? row.name : ""))
    .filter((name) => name.trim().length > 0);
}

export function buildFilters(question: string, repoPath: string, processName?: string) {
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
