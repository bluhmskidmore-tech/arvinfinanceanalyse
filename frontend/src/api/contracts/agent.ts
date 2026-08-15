import type { ApiQuality, ResultMeta } from "./core";

/** Agent / multi-batch tooling contracts (separate from UI envelope-only pages). */
export type AgentPageContext = {
  page_id: string;
  current_filters: Record<string, unknown>;
  selected_rows: Array<Record<string, unknown>>;
  context_note?: string | null;
};

export type AgentConversationContextTurn = {
  question: string;
  answer: string;
  run_id?: string | null;
  trace_id?: string | null;
  result_kind?: string | null;
};

export type AgentConversationContext = {
  recent_turns: AgentConversationContextTurn[];
};

export type AgentRequestContext = {
  user_id?: string;
  user_role?: string;
  identity_source?: string;
  workflow_mode?: "execute" | string;
  intent?: string;
  conversation?: AgentConversationContext;
  [key: string]: unknown;
};

/** POST /api/agent/query — 字段缺省时由后端填入默认值（见 backend AgentQueryRequest）。 */
export type AgentQueryRequest = {
  question: string;
  basis?: "formal" | "scenario" | "analytical";
  filters?: Record<string, unknown>;
  position_scope?: string;
  currency_basis?: string;
  /**
   * 运行时请求上下文：页面上下文改走 `page_context`；`context` 仍承载
   * user_id / conversation / intent / suggested_action（含确认 token）等运行时字段，
   * 前端每次请求都会发送（后端确认 token 校验与会话续接依赖它）。
   */
  context?: AgentRequestContext;
  page_context?: AgentPageContext | null;
};

export type AgentDrill = {
  dimension: string;
  label: string;
};

export type AgentSuggestedAction = {
  type: string;
  label: string;
  payload: Record<string, unknown>;
  requires_confirmation: boolean;
  confirmation_token?: string | null;
};

export type AgentCard = {
  type: string;
  title: string;
  value?: string;
  data?: Record<string, unknown> | Array<Record<string, unknown>>;
  spec?: Record<string, unknown>;
};

export type AgentEvidence = {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  quality_flag: ApiQuality;
  evidence_strength?: string;
};

export type AgentResultMeta = ResultMeta & {
  tables_used: string[];
  filters_applied: Record<string, unknown>;
  sql_executed: string[];
  evidence_rows: number;
  evidence_strength?: string;
  next_drill: AgentDrill[];
};

export type AgentEnvelope = {
  answer: string;
  cards: AgentCard[];
  evidence: AgentEvidence;
  result_meta: AgentResultMeta;
  next_drill: AgentDrill[];
  suggested_actions: AgentSuggestedAction[];
};

export type AgentDisabledResponse = {
  enabled: false;
  phase: "phase1";
  detail: string;
};

/** 机器可判定的稳定错误码——与后端 routes/agent*.py 的 `*_CODE` 常量防漂移比对。 */
export type AgentErrorCode =
  | "AGENT_PROVIDER_EXECUTION_FAILED"
  | "AGENT_WORKSPACE_RECORD_CORRUPT";

/** 机器可判定错误的结构化 detail（如 provider 执行失败 503、workspace 损坏记录 409）。 */
export type AgentErrorDetail = {
  code: AgentErrorCode;
  message: string;
};

/** FastAPI 请求体校验失败（422）时数组 detail 的单个条目（RequestValidationError 序列化形状）。 */
export type AgentValidationErrorItem = {
  loc: Array<string | number>;
  msg: string;
  type: string;
  [key: string]: unknown;
};

/**
 * agent 端点稳定错误契约：
 * - 禁用态 503：所有 agent 端点统一返回扁平 AgentDisabledResponse（无 detail 包装）；
 * - 机器可判定错误：`{ detail: AgentErrorDetail }`；
 * - FastAPI 请求校验失败 422：`{ detail: AgentValidationErrorItem[] }`（数组 detail）；
 * - 其余错误（业务校验/权限/404/生命周期冲突）：`{ detail: string }`。
 */
export type AgentErrorResponse = {
  detail: string | AgentErrorDetail | AgentValidationErrorItem[];
};

/** Mirrors backend `agent_run.py::AgentRunStatus`（含 cancelled 终态）。 */
export type AgentRunStatus =
  | "queued"
  | "starting"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/**
 * GET /api/agent/runs/{run_id}、SSE run_update 事件负载 — mirrors backend `AgentRunStatusResponse`。
 * 路由使用 `response_model_exclude_none=True`：值为 null 的字段会整体缺省，故可空字段均为可选。
 */
export type AgentRunStatusResponse = {
  run_id: string;
  status: AgentRunStatus;
  conversation_id?: string | null;
  retry_of_run_id?: string | null;
  artifact_refs?: string[] | null;
  question?: string | null;
  provider: string;
  model: string;
  transport: string;
  toolsets: string;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_seconds?: number | null;
  error_message?: string | null;
  result?: AgentEnvelope | null;
};

/** GET /api/agent/runs — mirrors backend `AgentRunListResponse`. */
export type AgentRunListResponse = {
  items: AgentRunStatusResponse[];
};

/** POST /api/agent/runs（排队分支）— mirrors backend `AgentRunCreateResponse`（同样 exclude_none）。 */
export type AgentRunCreateResponse = {
  run_id: string;
  status: AgentRunStatus;
  conversation_id?: string | null;
  retry_of_run_id?: string | null;
  artifact_refs?: string[] | null;
  provider: string;
  model: string;
  transport: string;
  toolsets: string;
  queued_at: string;
};

/**
 * POST /api/agent/runs 的完整响应契约：后端 response_model 已收窄为
 * `AgentRunCreateResponse | AgentDisabledResponse`——正常路径只返回排队回执
 * （disabled 时为 503 + AgentDisabledResponse，经错误通道抛出），不再同步短路返回 AgentEnvelope。
 * AgentRunStatusResponse 分支仅由前端 demo 桩返回（带 result 的终态 payload，驱动本地完成路径）。
 */
export type AgentRunCreateResult = AgentRunCreateResponse | AgentRunStatusResponse;

/** POST /api/agent/projects — mirrors backend `AgentProjectCreateRequest`（缺省值由后端填入）。 */
export type AgentProjectCreateRequest = {
  name: string;
  default_scope?: string;
  default_currency_basis?: string;
};

/** PATCH /api/agent/projects/{project_id} — 后端要求至少提供一个字段。 */
export type AgentProjectUpdateRequest = {
  name?: string | null;
  archived?: boolean | null;
};

/** Workspace 响应未启用 exclude_none：可空字段以显式 null 序列化。 */
export type AgentProject = {
  project_id: string;
  owner_user_id: string;
  name: string;
  default_scope: string;
  default_currency_basis: string;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentProjectListResponse = {
  items: AgentProject[];
  /** 读取时跳过的损坏记录数；后端默认 0，缺省视为 0。 */
  corrupt_records?: number;
};

/** POST /api/agent/projects/{project_id}/conversations — mirrors backend `AgentConversationCreateRequest`. */
export type AgentConversationCreateRequest = {
  title: string;
};

export type AgentConversation = {
  conversation_id: string;
  project_id: string;
  owner_user_id: string;
  title: string;
  last_run_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentConversationListResponse = {
  items: AgentConversation[];
  /** 读取时跳过的损坏记录数；后端默认 0，缺省视为 0。 */
  corrupt_records?: number;
};

/** Mirrors backend `agent_workspace.py::AgentMessageRole`. */
export type AgentMessageRole = "user" | "assistant" | "system_notice";

export type AgentMessage = {
  message_id: string;
  conversation_id: string;
  role: AgentMessageRole;
  content: string;
  run_id: string;
  artifact_refs: string[];
  created_at: string;
  result: AgentEnvelope | null;
};

export type AgentMessageListResponse = {
  items: AgentMessage[];
  /** 读取时跳过的损坏记录数；后端默认 0，缺省视为 0。 */
  corrupt_records?: number;
};

export type AgentArtifact = {
  artifact_id: string;
  conversation_id: string;
  run_id: string;
  kind: "agent_envelope";
  title: string;
  content: AgentEnvelope;
  result_meta: AgentResultMeta;
  created_at: string;
};

export type AgentArtifactListResponse = {
  items: AgentArtifact[];
  /** 读取时跳过的损坏记录数；后端默认 0，缺省视为 0。 */
  corrupt_records?: number;
};
