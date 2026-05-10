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

type AgentConversationTurn = {
  id: string;
  question: string;
  agentRun: AgentRunPayload | null;
  result: AgentQueryResult | null;
  error: AgentQueryError | null;
  activeSuggestedActionPayload: Record<string, unknown> | null;
};

type AgentWorkbenchPageProps = {
  pageContext?: AgentPageContext;
};

type AgentPanelProps = AgentWorkbenchPageProps & {
  showHeader?: boolean;
};

type AgentOrdinaryConversationMode = "unknown" | "managed" | "local_sync";

type FinancialWorkflowShortcut = {
  id: string;
  title: string;
  slashCommand: string;
  description: string;
  mappedIntents: string[];
};

type ResearchDomain = "stock" | "macro";

type ResearchShortcut = {
  id: string;
  title: string;
  question: string;
  description: string;
  domain: ResearchDomain;
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

class AgentManagedRunRequiresHermesError extends Error {
  detail: string;

  constructor(detail: string) {
    super(detail);
    this.name = "AgentManagedRunRequiresHermesError";
    this.detail = detail;
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
const MAX_AGENT_CONTEXT_TURNS = 4;
const MAX_AGENT_CONTEXT_QUESTION_LENGTH = 800;
const MAX_AGENT_CONTEXT_ANSWER_LENGTH = 1400;
const AGENT_RUN_POLL_MAX_ATTEMPTS = 240;
const latestAgentRunStatusRequests = new Map<string, Promise<AgentRunPayload>>();

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

function getManagedRunRequiresHermesDetail(value: unknown) {
  if (!isRecord(value) || typeof value.detail !== "string") {
    return null;
  }
  const detail = value.detail.trim();
  if (!detail.startsWith("Agent runs require MOSS_AGENT_PROVIDER=")) {
    return null;
  }
  return detail;
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

function createAgentConversationTurn(question: string): AgentConversationTurn {
  return {
    id: `turn:${Date.now()}:${Math.random().toString(16).slice(2)}`,
    question,
    agentRun: null,
    result: null,
    error: null,
    activeSuggestedActionPayload: null,
  };
}

function trimAgentContextText(value: string, limit: number) {
  const normalized = value.trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 3)}...`;
}

function buildConversationContext(turns: AgentConversationTurn[]) {
  const history = turns
    .filter((turn) => turn.question.trim() && turn.result?.answer.trim())
    .slice(-MAX_AGENT_CONTEXT_TURNS)
    .map((turn) => ({
      question: trimAgentContextText(turn.question, MAX_AGENT_CONTEXT_QUESTION_LENGTH),
      answer: trimAgentContextText(turn.result?.answer ?? "", MAX_AGENT_CONTEXT_ANSWER_LENGTH),
      run_id: turn.agentRun?.run_id ?? null,
      trace_id: turn.result?.result_meta.trace_id ?? null,
    }));

  return history.length > 0 ? { recent_turns: history } : undefined;
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
  switch (label.toLowerCase()) {
    case "hermes":
      return "Hermes";
    case "dexter":
      return "Dexter";
    default:
      return label;
  }
}

function formatManagedProviderLabel(provider: unknown) {
  if (typeof provider !== "string" || provider.trim().length === 0) {
    return null;
  }
  return formatProviderLabel(provider, "托管运行时");
}

function formatManagedRunTitle(status: AgentRunStatus | undefined, provider: unknown) {
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
    default:
      return providerLabel ? `${providerLabel} 正在分析` : "托管任务分析中";
  }
}

function formatManagedRunFailureMessage(provider: unknown) {
  const providerLabel = formatManagedProviderLabel(provider);
  return providerLabel
    ? `${providerLabel} 托管任务失败，请稍后重试。`
    : "托管任务失败，请稍后重试。";
}

function formatManagedRunRestoreQuestion(provider: unknown) {
  const providerLabel = formatManagedProviderLabel(provider);
  return providerLabel ? `恢复上一次 ${providerLabel} 对话` : "恢复上一次托管对话";
}

function formatAgentRunStatusLabel(status: AgentRunStatus | undefined, fallback = "--") {
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
    default:
      return fallback;
  }
}

function formatAgentTurnWaitTitle(agentRun: AgentRunPayload | null) {
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

function formatAgentWaitPhase(agentRun: AgentRunPayload | null) {
  if (agentRun?.run_kind === "workflow") {
    if (agentRun.status === "running") {
      return "本地 workflow 执行中";
    }
    if (agentRun.status === "starting") {
      return "准备本地 workflow";
    }
    if (agentRun.status === "queued") {
      return "等待本地 workflow";
    }
  }
  if (agentRun?.run_kind === "sync") {
    if (agentRun.status === "running") {
      return "同步处理中";
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
    return "正在交给托管运行时";
  }
  return formatAgentRunStatusLabel(status, "运行中");
}

function formatAgentRunElapsed(agentRun: AgentRunPayload | null, fallbackSeconds: number) {
  if (typeof agentRun?.elapsed_seconds === "number" && Number.isFinite(agentRun.elapsed_seconds)) {
    return Math.max(0, Math.round(agentRun.elapsed_seconds));
  }
  return fallbackSeconds;
}

function formatAgentWaitHint(agentRun: AgentRunPayload | null, waitSeconds: number) {
  if (agentRun?.run_kind === "workflow") {
    if (agentRun.status === "queued" || agentRun.status === "starting") {
      return "本地 workflow 正在准备，本页会直接显示结果。";
    }
    if (agentRun.status === "running" && waitSeconds >= 10) {
      return "本地 workflow 仍在处理，复杂问题通常会多等一会儿。";
    }
    if (agentRun.status === "running") {
      return "本地 workflow 正在生成结果，本页会直接更新答案。";
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
      return "本地同步查询正在准备，本页会直接显示结果。";
    }
    if (agentRun.status === "running" && waitSeconds >= 10) {
      return "本地查询仍在处理，复杂问题通常会多等一会儿。";
    }
    if (agentRun.status === "running") {
      return "本地查询正在生成结果，本页会直接更新答案。";
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
    return "先把问题放进队列，拿到 run_id 后会继续更新。";
  }
  if (status === "queued") {
    return "任务已入队；如果前面还有回答，会按顺序处理。";
  }
  if (status === "starting") {
    const providerLabel = formatManagedProviderLabel(agentRun?.provider);
    return providerLabel ? `${providerLabel} 正在准备运行环境。` : "托管任务正在准备运行环境。";
  }
  if (status === "running" && waitSeconds >= 10) {
    const providerLabel = formatManagedProviderLabel(agentRun?.provider);
    return providerLabel
      ? `${providerLabel} 还在思考，复杂问题通常会多等一会儿。`
      : "托管任务仍在处理中，复杂问题通常会多等一会儿。";
  }
  if (status === "running") {
    const providerLabel = formatManagedProviderLabel(agentRun?.provider);
    return providerLabel
      ? `${providerLabel} 正在分析，本页会自动更新结果。`
      : "托管任务正在分析，本页会自动更新结果。";
  }
  if (status === "completed") {
    return "可以离开或刷新，回来后会继续显示这次结果。";
  }
  if (status === "failed") {
    return "这次没有完成，可以调整问题后重试。";
  }
  return "可以离开或刷新，回来后会继续显示这次结果。";
}

function getAgentRunPollIntervalMs(_payload: AgentRunPayload, attempt: number) {
  if (attempt < 5) {
    return 120;
  }
  if (attempt < 20) {
    return 500;
  }
  return 1000;
}

function buildRuntimeStatus(
  result: AgentQueryResult | null,
  loading: boolean,
  agentRun: AgentRunPayload | null,
) {
  const filters = result?.evidence.filters_applied ?? {};
  const statusLabel = formatAgentRunStatusLabel(agentRun?.status, loading ? "分析中" : "--");
  return {
    provider: formatProviderLabel(agentRun?.provider ?? filters.provider, loading ? "托管运行时" : "待连接"),
    transport: formatRuntimeLabel(agentRun?.transport ?? filters.transport, loading ? "bridge" : "等待提问"),
    model: formatRuntimeLabel(agentRun?.model ?? filters.model, "--"),
    toolsets: formatRuntimeLabel(agentRun?.toolsets ?? filters.toolsets, "--"),
    quality: formatRuntimeLabel(result?.evidence.quality_flag, statusLabel),
  };
}

function findLatestTurnWithResult(turns: AgentConversationTurn[]) {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    if (turns[index]?.result) {
      return turns[index];
    }
  }
  return null;
}

function findLatestTurnWithRun(turns: AgentConversationTurn[]) {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    if (turns[index]?.agentRun) {
      return turns[index];
    }
  }
  return null;
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

const FINANCIAL_WORKFLOWS: FinancialWorkflowShortcut[] = [
  {
    id: "portfolio_review",
    title: "Portfolio Review",
    slashCommand: "/portfolio-review",
    description: "组合规模、久期和信用暴露",
    mappedIntents: ["portfolio_overview", "duration_risk", "credit_exposure"],
  },
  {
    id: "pnl_review",
    title: "PnL Review",
    slashCommand: "/pnl-review",
    description: "损益摘要、归因桥和产品损益",
    mappedIntents: ["pnl_summary", "pnl_bridge", "product_pnl"],
  },
  {
    id: "risk_memo",
    title: "Risk Memo",
    slashCommand: "/risk-memo",
    description: "久期、信用暴露和风险张量",
    mappedIntents: ["duration_risk", "credit_exposure", "risk_tensor"],
  },
  {
    id: "market_brief",
    title: "Market Brief",
    slashCommand: "/market-brief",
    description: "市场数据和新闻入口",
    mappedIntents: ["market_data", "news"],
  },
];

const RESEARCH_SHORTCUTS: ResearchShortcut[] = [
  {
    id: "stock_research",
    title: "Stock Research",
    question: "Review landed stock research context",
    description: "Review refreshed stock rows with evidence and limits.",
    domain: "stock",
  },
  {
    id: "macro_research",
    title: "Macro Research",
    question: "Review landed macro research context",
    description: "Review refreshed macro series with evidence and limits.",
    domain: "macro",
  },
];

const RECENT_REPO_PATHS_KEY = "moss.agent.gitnexus.recentRepoPaths.v1";
const PINNED_REPO_PATHS_KEY = "moss.agent.gitnexus.pinnedRepoPaths.v1";
const MAX_RECENT_REPO_PATHS = 5;
const MAX_PINNED_REPO_PATHS = 5;
const GITNEXUS_PROCESS_CARD_TITLE = "GitNexus Processes Table";

function buildAgentRequestBody(
  question: string,
  repoPath: string,
  processName: string,
  conversationContext?: Record<string, unknown>,
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
      ...(conversationContext ? { conversation: conversationContext } : {}),
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

function buildFinancialWorkflowRequestBody(
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

function buildResearchRequestBody(
  shortcut: ResearchShortcut,
  pageContext?: AgentPageContext,
): AgentQueryRequest {
  return {
    question: shortcut.question,
    basis: "formal",
    filters: { research_domain: shortcut.domain },
    position_scope: "all",
    currency_basis: "CNY",
    context: {
      user_id: "web-user",
    },
    ...(pageContext ? { page_context: pageContext } : {}),
  };
}

function buildLocalSyncAgentRun(
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

function buildPendingAgentRun(
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
  const [conversationTurns, setConversationTurns] = useState<AgentConversationTurn[]>([]);
  const [ordinaryConversationMode, setOrdinaryConversationMode] =
    useState<AgentOrdinaryConversationMode>("unknown");
  const [repoPath, setRepoPath] = useState(() => loadRecentRepoPaths()[0] ?? "");
  const [availableProcesses, setAvailableProcesses] = useState<string[]>([]);
  const [processSearch, setProcessSearch] = useState("");
  const [selectedProcess, setSelectedProcess] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentWaitSeconds, setAgentWaitSeconds] = useState(0);
  const [processLoading, setProcessLoading] = useState(false);
  const [result, setResult] = useState<AgentQueryResult | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRunPayload | null>(null);
  const [error, setError] = useState<AgentQueryError | null>(null);
  const repoPathRef = useRef(repoPath);
  const conversationRef = useRef<HTMLElement | null>(null);
  const processStateRequestVersionRef = useRef(0);
  const deferredProcessSearch = useDeferredValue(processSearch);
  const filteredProcesses = availableProcesses.filter((processName) =>
    processName.toLowerCase().includes(deferredProcessSearch.trim().toLowerCase()),
  );
  const recentUnpinnedRepoPaths = recentRepoPaths.filter((path) => !pinnedRepoPaths.includes(path));
  const isCurrentRepoPinned = pinnedRepoPaths.includes(repoPath.trim());
  const latestConversationTurn = conversationTurns[conversationTurns.length - 1] ?? null;
  const latestResultTurn = findLatestTurnWithResult(conversationTurns);
  const latestRunTurn = findLatestTurnWithRun(conversationTurns);
  const runtimeResult = loading ? null : latestResultTurn?.result ?? result;
  const runtimeRun = (
    loading
      ? latestConversationTurn?.agentRun ?? agentRun ?? latestRunTurn?.agentRun
      : latestRunTurn?.agentRun ?? agentRun
  ) ?? null;
  const runtimeStatus = buildRuntimeStatus(
    runtimeResult,
    loading,
    runtimeRun,
  );
  const hasConversation = conversationTurns.length > 0 || Boolean(result || error);
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

  function updateConversationTurn(
    turnId: string,
    updater: (turn: AgentConversationTurn) => AgentConversationTurn,
  ) {
    setConversationTurns((currentTurns) =>
      currentTurns.map((turn) => (turn.id === turnId ? updater(turn) : turn)),
    );
  }

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
    if (!hasConversation) {
      return;
    }
    const scrollIntoView = conversationRef.current?.scrollIntoView;
    if (typeof scrollIntoView === "function") {
      scrollIntoView.call(conversationRef.current, { behavior: "smooth", block: "end" });
    }
  }, [
    hasConversation,
    latestConversationTurn?.id,
    latestConversationTurn?.agentRun?.status,
    latestConversationTurn?.result,
    latestConversationTurn?.error,
  ]);

  useEffect(() => {
    const latestRunId = loadLatestAgentRunId();
    if (!latestRunId) {
      return;
    }

    let cancelled = false;
    let restoreRequest = latestAgentRunStatusRequests.get(latestRunId);
    if (!restoreRequest) {
      restoreRequest = fetchAgentRunStatus(latestRunId).finally(() => {
        latestAgentRunStatusRequests.delete(latestRunId);
      });
      latestAgentRunStatusRequests.set(latestRunId, restoreRequest);
    }
    void restoreRequest
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setOrdinaryConversationMode("managed");
        setAgentRun(payload);
        const restoredQuestion = payload.question?.trim() || formatManagedRunRestoreQuestion(payload.provider);
        setConversationTurns([
          {
            id: `restored:${payload.run_id}`,
            question: restoredQuestion,
            agentRun: payload,
            result: payload.status === "completed" && payload.result ? payload.result : null,
            error:
              payload.status === "failed"
                ? {
                    kind: "request",
                    message: payload.error_message || formatManagedRunFailureMessage(payload.provider),
                  }
                : null,
            activeSuggestedActionPayload: null,
          },
        ]);
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

    const managedRunRequiresHermesDetail = response.status === 400 ? getManagedRunRequiresHermesDetail(payload) : null;
    if (managedRunRequiresHermesDetail) {
      throw new AgentManagedRunRequiresHermesError(managedRunRequiresHermesDetail);
    }

    if (!response.ok) {
      throw new Error(`智能体查询失败（${response.status}）`);
    }

    if (isAgentQueryResult(payload)) {
      const result = normalizeAgentResult(payload);
      return {
        run_id: "agent_run:sync_compat",
        status: "completed",
        provider: formatRuntimeLabel(result.evidence.filters_applied.provider, "managed"),
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

  async function executeManagedAgentRun(
    question: string,
    turnId: string,
    conversationContext?: Record<string, unknown>,
    options?: {
      rethrowLocalProviderFallback?: boolean;
    },
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    const requestBody = buildAgentRequestBody(
      question,
      normalizedRepoPath,
      selectedProcess,
      conversationContext,
      pageContext,
    );
    setAgentRun(null);
    setResult(null);
    try {
      const finalPayload = await runPollingTask<AgentRunPayload>({
        start: () => createAgentRun(requestBody),
        getStatus: fetchAgentRunStatus,
        getIntervalMs: getAgentRunPollIntervalMs,
        maxAttempts: AGENT_RUN_POLL_MAX_ATTEMPTS,
        onUpdate: (payload) => {
          setOrdinaryConversationMode("managed");
          setAgentRun(payload);
          updateConversationTurn(turnId, (turn) => ({
            ...turn,
            agentRun: payload,
          }));
        },
      });

      if (finalPayload.status === "failed") {
        throw new Error(finalPayload.error_message || formatManagedRunFailureMessage(finalPayload.provider));
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
      updateConversationTurn(turnId, (turn) => ({
        ...turn,
        agentRun: finalPayload,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
    } catch (requestError) {
      if (
        requestError instanceof AgentManagedRunRequiresHermesError &&
        options?.rethrowLocalProviderFallback
      ) {
        throw requestError;
      }
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        if (requestError instanceof AgentDisabledQueryError) {
          const disabledError: AgentQueryError = {
            kind: "disabled",
            detail: requestError.detail,
            phase: requestError.phase,
          };
          setError(disabledError);
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: disabledError }));
          return;
        }
        const nextError: AgentQueryError = {
          kind: "request",
          message: buildErrorMessage(requestError),
        };
        setError(nextError);
        updateConversationTurn(turnId, (turn) => ({ ...turn, error: nextError }));
      }
    }
  }

  async function executeAgentQuery(
    question: string,
    mode: "query" | "processes" = "query",
    turnId?: string,
    conversationContext?: Record<string, unknown>,
  ) {
    const normalizedRepoPath = repoPath.trim();
    const requestVersion = beginProcessStateRequest();
    try {
      const requestBody = buildAgentRequestBody(
        question,
        normalizedRepoPath,
        selectedProcess,
        conversationContext,
        pageContext,
      );

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
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: payload.detail,
          phase: payload.phase,
        };
        setError(disabledError);
        if (turnId) {
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: disabledError }));
        }
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
      }
      return payload;
    } catch (requestError) {
      if (canCommitProcessState(requestVersion, normalizedRepoPath)) {
        const nextError: AgentQueryError = {
          kind: "request",
          message: buildErrorMessage(requestError),
        };
        setError(nextError);
        if (turnId) {
          updateConversationTurn(turnId, (turn) => ({ ...turn, error: nextError }));
        }
        return undefined;
      }
    }
  }

  async function executeLocalSyncConversation(
    question: string,
    turnId: string,
    conversationContext?: Record<string, unknown>,
  ) {
    const syncRunId = `agent_run:sync:${turnId}`;
    const runningSyncRun = buildLocalSyncAgentRun(syncRunId, question, "running");
    setOrdinaryConversationMode("local_sync");
    setAgentRun(runningSyncRun);
    setResult(null);
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      agentRun: runningSyncRun,
      error: null,
    }));

    const payload = await executeAgentQuery(question, "query", turnId, conversationContext);
    if (!payload) {
      const failedSyncRun = buildLocalSyncAgentRun(
        syncRunId,
        question,
        "failed",
        null,
        "本地查询失败，请稍后重试。",
      );
      setAgentRun(failedSyncRun);
      updateConversationTurn(turnId, (turn) => ({
        ...turn,
        agentRun: failedSyncRun,
      }));
      return;
    }

    const completedSyncRun = buildLocalSyncAgentRun(syncRunId, question, "completed", payload);
    setAgentRun(completedSyncRun);
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      agentRun: completedSyncRun,
      result: payload,
      error: null,
      activeSuggestedActionPayload: null,
    }));
  }

  async function executeOrdinaryConversation(
    question: string,
    turnId: string,
    conversationContext?: Record<string, unknown>,
  ) {
    if (ordinaryConversationMode === "local_sync") {
      await executeLocalSyncConversation(question, turnId, conversationContext);
      return;
    }
    if (ordinaryConversationMode === "managed") {
      await executeManagedAgentRun(question, turnId, conversationContext);
      return;
    }

    try {
      await executeManagedAgentRun(question, turnId, conversationContext, {
        rethrowLocalProviderFallback: true,
      });
    } catch (requestError) {
      if (requestError instanceof AgentManagedRunRequiresHermesError) {
        await executeLocalSyncConversation(question, turnId, conversationContext);
        return;
      }
      throw requestError;
    }
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (loading) {
      return;
    }

    const question = query.trim();
    if (!question) {
      const nextError: AgentQueryError = {
        kind: "request",
        message: "请输入查询问题。",
      };
      setError(nextError);
      return;
    }

    const context = buildConversationContext(conversationTurns);
    const turn = createAgentConversationTurn(question);
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [...currentTurns, turn]);
    setQuery("");
    setLoading(true);
    setError(null);
    try {
      await executeOrdinaryConversation(question, turn.id, context);
    } finally {
      setLoading(false);
    }
  }

  async function executeFinancialWorkflow(workflow: FinancialWorkflowShortcut) {
    if (loading) {
      return;
    }

    const turn = createAgentConversationTurn(workflow.slashCommand);
    const pendingWorkflowRun = buildPendingAgentRun(
      `agent_run:workflow:${workflow.id}:pending`,
      workflow.slashCommand,
      "workflow",
    );
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingWorkflowRun,
      },
    ]);
    setLoading(true);
    setAgentRun(pendingWorkflowRun);
    setResult(null);
    setError(null);

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildFinancialWorkflowRequestBody(workflow, pageContext)),
      });
      const payload = (await response.json()) as unknown;

      if (response.status === 503 && isDisabledPayload(payload)) {
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: payload.detail,
          phase: payload.phase,
        };
        setError(disabledError);
        updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: disabledError }));
        return;
      }

      if (!response.ok) {
        throw new Error(`智能体查询失败（${response.status}）`);
      }

      if (!isAgentQueryResult(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      normalizeAgentResult(payload);

      const workflowRun: AgentRunPayload = {
        run_id: `agent_run:workflow:${workflow.id}`,
        status: "completed",
        run_kind: "workflow",
        provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
        model: formatRuntimeLabel(payload.evidence.filters_applied.model, "MOSS intents"),
        transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
        toolsets: workflow.mappedIntents.join(", "),
        result: payload,
      };
      setOrdinaryConversationMode("local_sync");
      setAgentRun(workflowRun);
      setResult(payload);
      updateConversationTurn(turn.id, (currentTurn) => ({
        ...currentTurn,
        agentRun: workflowRun,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
    } catch (requestError) {
      const nextError: AgentQueryError = {
        kind: "request",
        message: buildErrorMessage(requestError),
      };
      setError(nextError);
      updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: nextError }));
    } finally {
      setLoading(false);
    }
  }

  async function executeResearchShortcut(shortcut: ResearchShortcut) {
    if (loading) {
      return;
    }

    const turn = createAgentConversationTurn(shortcut.question);
    const pendingRun = buildPendingAgentRun(
      `agent_run:research:${shortcut.id}:pending`,
      shortcut.question,
      "sync",
    );
    setAgentWaitSeconds(0);
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingRun,
      },
    ]);
    setLoading(true);
    setAgentRun(pendingRun);
    setResult(null);
    setError(null);

    try {
      const response = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildResearchRequestBody(shortcut, pageContext)),
      });
      const payload = (await response.json()) as unknown;

      if (response.status === 503 && isDisabledPayload(payload)) {
        const disabledError: AgentQueryError = {
          kind: "disabled",
          detail: payload.detail,
          phase: payload.phase,
        };
        setError(disabledError);
        updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: disabledError }));
        return;
      }

      if (!response.ok) {
        throw new Error(`智能体查询失败（${response.status}）`);
      }

      if (!isAgentQueryResult(payload)) {
        throw new Error("智能体返回结果格式无效。");
      }
      normalizeAgentResult(payload);

      const researchRun: AgentRunPayload = {
        run_id: `agent_run:research:${shortcut.id}`,
        status: "completed",
        run_kind: "sync",
        question: shortcut.question,
        provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "dexter"),
        model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
        transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
        toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "research"),
        result: payload,
      };
      setOrdinaryConversationMode("local_sync");
      setAgentRun(researchRun);
      setResult(payload);
      updateConversationTurn(turn.id, (currentTurn) => ({
        ...currentTurn,
        agentRun: researchRun,
        result: payload,
        error: null,
        activeSuggestedActionPayload: null,
      }));
    } catch (requestError) {
      const nextError: AgentQueryError = {
        kind: "request",
        message: buildErrorMessage(requestError),
      };
      setError(nextError);
      updateConversationTurn(turn.id, (currentTurn) => ({ ...currentTurn, error: nextError }));
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
        setConversationTurns((currentTurns) => [
          ...currentTurns,
          {
            id: `processes:${Date.now()}:${Math.random().toString(16).slice(2)}`,
            question: requestBody.question,
            agentRun: {
              run_id: "agent_run:sync_processes",
              status: "completed",
              run_kind: "sync",
              provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
              model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
              transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
              toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "GitNexus"),
              result: payload,
            },
            result: payload,
            error: null,
            activeSuggestedActionPayload: null,
          },
        ]);
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
    const question = `请给我看 GitNexus process/${selectedProcess}`;
    const turn = createAgentConversationTurn(question);
    const pendingSyncRun = buildPendingAgentRun(
      `agent_run:sync:${selectedProcess}:pending`,
      question,
      "sync",
    );
    setConversationTurns((currentTurns) => [
      ...currentTurns,
      {
        ...turn,
        agentRun: pendingSyncRun,
      },
    ]);
    setAgentWaitSeconds(0);
    setAgentRun(pendingSyncRun);
    setLoading(true);
    setError(null);
    try {
      const payload = await executeAgentQuery(question, "query", turn.id);
      if (payload) {
        updateConversationTurn(turn.id, (currentTurn) => ({
          ...currentTurn,
          agentRun: {
            run_id: "agent_run:sync_query",
            status: "completed",
            run_kind: "sync",
            provider: formatRuntimeLabel(payload.evidence.filters_applied.provider, "local"),
            model: formatRuntimeLabel(payload.evidence.filters_applied.model, "default"),
            transport: formatRuntimeLabel(payload.evidence.filters_applied.transport, "sync"),
            toolsets: formatRuntimeLabel(payload.evidence.filters_applied.toolsets, "default"),
            result: payload,
          },
          result: payload,
          error: null,
          activeSuggestedActionPayload: null,
        }));
      }
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

  function handleSuggestedAction(turnId: string, action: AgentSuggestedAction) {
    if (action.type === "inspect_drill" || action.type === "refine_query") {
      setQuery(`请基于当前 evidence 继续下钻：${action.label}`);
      setError(null);
      return;
    }
    updateConversationTurn(turnId, (turn) => ({
      ...turn,
      activeSuggestedActionPayload: action.payload,
    }));
  }

  function renderFinancialWorkflowPanel() {
    return (
      <section className="agent-financial-workflows" aria-label="financial-workflows">
        <div className="agent-financial-workflows__header">
          <div>
            <div className="agent-financial-workflows__eyebrow">金融工作流</div>
            <h2>本地 MOSS intents 快捷入口</h2>
          </div>
          <span>不接外部数据</span>
        </div>
        <div className="agent-financial-workflows__grid">
          {FINANCIAL_WORKFLOWS.map((workflow) => (
            <button
              key={workflow.id}
              type="button"
              className="agent-financial-workflows__button"
              onClick={() => void executeFinancialWorkflow(workflow)}
              disabled={loading}
            >
              <span className="agent-financial-workflows__title">{workflow.title}</span>
              <span className="agent-financial-workflows__command">{workflow.slashCommand}</span>
              <span className="agent-financial-workflows__description">{workflow.description}</span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  function renderResearchShortcutPanel() {
    return (
      <section className="agent-financial-workflows" aria-label="research-shortcuts">
        <div className="agent-financial-workflows__header">
          <div>
            <div className="agent-financial-workflows__eyebrow">DEXTER Research</div>
            <h2>Landed data review</h2>
          </div>
          <span>Refresh first</span>
        </div>
        <div className="agent-financial-workflows__grid">
          {RESEARCH_SHORTCUTS.map((shortcut) => (
            <button
              key={shortcut.id}
              type="button"
              className="agent-financial-workflows__button"
              onClick={() => void executeResearchShortcut(shortcut)}
              disabled={loading}
            >
              <span className="agent-financial-workflows__title">{shortcut.title}</span>
              <span className="agent-financial-workflows__command">{shortcut.domain}</span>
              <span className="agent-financial-workflows__description">{shortcut.description}</span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  function renderAgentTurnResult(turn: AgentConversationTurn) {
    const turnResult = turn.result;
    if (!turnResult) {
      return null;
    }

    return (
      <div className="agent-result-shell">
        {hasRenderableResult(turnResult) ? (
          <div className="agent-result-grid">
            <div className="agent-result-main">
              <AgentAnswerPanel answer={turnResult.answer} />

              {turnResult.cards.length > 0 ? (
                (() => {
                  const gitNexusCards = isGitNexusResult(turnResult)
                    ? turnResult.cards
                    : turnResult.cards.filter(isGitNexusCard);
                  const genericCards = isGitNexusResult(turnResult)
                    ? []
                    : turnResult.cards.filter((card) => !isGitNexusCard(card));
                  return (
                    <div className="agent-result-card-stack">
                      {gitNexusCards.length > 0 ? <AgentGitNexusResultView cards={gitNexusCards} /> : null}
                      <AgentGenericCardsGrid cards={genericCards} formatValue={formatMetaValue} />
                    </div>
                  );
                })()
              ) : null}

              {turnResult.next_drill.length > 0 ? (
                <div className="agent-next-drill-row">
                  {turnResult.next_drill.map((drill) => (
                    <span key={drill.dimension}>{drill.label}</span>
                  ))}
                </div>
              ) : null}

              <AgentSuggestedActionsPanel
                actions={turnResult.suggested_actions}
                formatValue={formatMetaValue}
                activePayload={turn.activeSuggestedActionPayload}
                onActionClick={(action) => handleSuggestedAction(turn.id, action)}
              />
            </div>

            <aside className="agent-result-side">
              {hasEvidenceContent(turnResult.evidence) ? (
                <AgentEvidencePanel
                  tablesUsed={turnResult.evidence.tables_used}
                  filtersApplied={turnResult.evidence.filters_applied}
                  evidenceRows={turnResult.evidence.evidence_rows}
                  qualityFlag={turnResult.evidence.quality_flag}
                />
              ) : null}
              <AgentResultMetaPanel
                entries={buildResultMetaEntries(turnResult.result_meta)}
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

        {!hasRenderableResult(turnResult) ? (
          <AgentResultMetaPanel
            entries={buildResultMetaEntries(turnResult.result_meta)}
            formatValue={formatMetaValue}
          />
        ) : null}
      </div>
    );
  }

  function renderAgentTurnError(turn: AgentConversationTurn) {
    if (turn.error?.kind === "disabled") {
      return (
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
      );
    }

    if (turn.error?.kind === "request") {
      return (
        <div className="agent-callout agent-callout--error" role="alert">
          <strong>请求没有送达</strong>
          <span>{turn.error.message}</span>
        </div>
      );
    }

    return null;
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
            MOSS / Agent
          </div>
        </header>
      ) : null}

      <div className="agent-runtime-strip" aria-label="agent-runtime-status">
        <div className="agent-runtime-strip__state">
          <span className={loading ? "agent-runtime-strip__dot agent-runtime-strip__dot--active" : "agent-runtime-strip__dot"} />
          <span>{loading ? "分析中" : latestResultTurn?.result ? "已连接" : "待提问"}</span>
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

      {renderResearchShortcutPanel()}

      {renderFinancialWorkflowPanel()}

      {!hasConversation ? (
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
      ) : null}

      {hasConversation ? (
        <section className="agent-conversation" aria-label="agent-conversation" ref={conversationRef}>
          {conversationTurns.map((turn) => (
            <div key={turn.id} className="agent-turn">
              <div className="agent-message agent-message--user">
                <div className="agent-message__speaker">我</div>
                <div className="agent-message__body">{turn.question}</div>
              </div>

              <div className="agent-message agent-message--assistant">
                <div className="agent-message__speaker">智能体</div>
                <div className="agent-message__body">
                  {(turn === latestConversationTurn && loading) || turn.agentRun ? (
                    <div className="agent-wait-status" role="status" aria-live="polite">
                      <div className="agent-wait-status__title">{formatAgentTurnWaitTitle(turn.agentRun)}</div>
                      <div className="agent-wait-status__detail">
                        <span>{formatAgentWaitPhase(turn.agentRun)}</span>
                        <span>已等待 {formatAgentRunElapsed(turn.agentRun, turn === latestConversationTurn ? agentWaitSeconds : 0)} 秒</span>
                        {turn.agentRun?.run_id ? <span>run_id: {turn.agentRun.run_id}</span> : null}
                        <span>{formatAgentWaitHint(turn.agentRun, turn === latestConversationTurn ? agentWaitSeconds : 0)}</span>
                      </div>
                    </div>
                  ) : null}

                  {renderAgentTurnError(turn)}
                  {renderAgentTurnResult(turn)}
                </div>
              </div>
            </div>
          ))}

          {conversationTurns.length === 0 && error ? (
            <div className="agent-message agent-message--assistant">
              <div className="agent-message__speaker">智能体</div>
              <div className="agent-message__body">
                {renderAgentTurnError({
                  id: "page-error",
                  question: "",
                  agentRun: null,
                  result: null,
                  error,
                  activeSuggestedActionPayload: null,
                })}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {hasConversation ? (
        <div className="agent-composer-dock">
          <AgentQueryForm
            compact
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
        </div>
      ) : null}

      <AgentRepoMemoryPanel
        pinnedRepoPaths={pinnedRepoPaths}
        recentUnpinnedRepoPaths={recentUnpinnedRepoPaths}
        onApplyRecentRepoPath={applyRecentRepoPath}
        onMovePinnedRepoPath={movePinnedRepoPath}
        onUnpinRepo={unpinRepo}
        onPinRepoPath={pinRepoPath}
      />
    </section>
  );
}

export default function AgentWorkbenchPage({ pageContext }: AgentWorkbenchPageProps = {}) {
  return <AgentPanel pageContext={pageContext} showHeader />;
}
