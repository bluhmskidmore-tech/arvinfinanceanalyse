/**
 * Agent 前后端契约防漂移测试。
 *
 * 机制：
 * 1. 直接读取后端 `backend/app/agent/schemas/*.py` 源码，解析每个 Pydantic 模型的字段名
 *    与 Literal 取值（后端本轮只读，不引入任何后端改动）。
 * 2. 前端侧用 `satisfies Record<keyof T, true>` 把字段清单绑定到 TS 契约类型：
 *    - 后端加/删字段 → 与解析结果比对失败（运行时报错）；
 *    - 前端契约改形状但忘更新清单 → tsc 编译失败。
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { createRealAgentClient, type AgentClientMethods } from "../api/agentClient";
import type {
  AgentArtifact,
  AgentArtifactListResponse,
  AgentCard,
  AgentConversation,
  AgentConversationCreateRequest,
  AgentConversationListResponse,
  AgentDisabledResponse,
  AgentDrill,
  AgentEnvelope,
  AgentErrorCode,
  AgentErrorDetail,
  AgentErrorResponse,
  AgentEvidence,
  AgentMessage,
  AgentMessageListResponse,
  AgentMessageRole,
  AgentPageContext,
  AgentProject,
  AgentProjectCreateRequest,
  AgentProjectListResponse,
  AgentProjectUpdateRequest,
  AgentQueryRequest,
  AgentResultMeta,
  AgentRunCreateResponse,
  AgentRunListResponse,
  AgentRunStatus,
  AgentRunStatusResponse,
  AgentSuggestedAction,
  ResultMeta,
} from "../api/contracts";
import {
  AGENT_RUN_STATUSES,
  isAgentRunPayload,
  isAgentRunStatus,
  isTerminalAgentRunStatus,
} from "../features/agent/lib/agentWorkbenchModel";

const BACKEND_SCHEMA_SOURCES = {
  agentRequest: readBackendSchema("agent_request.py"),
  agentResponse: readBackendSchema("agent_response.py"),
  agentRun: readBackendSchema("agent_run.py"),
  agentWorkspace: readBackendSchema("agent_workspace.py"),
};

const BACKEND_ROUTE_SOURCES = {
  agent: readBackendRoute("agent.py"),
  agentWorkspace: readBackendRoute("agent_workspace.py"),
};

/** ResultMeta 基类在 backend/app/schemas（非 agent/schemas），AgentResultMeta 继承它。 */
const BACKEND_BASE_SCHEMA_SOURCES = {
  resultMeta: readFileSync(
    resolve(process.cwd(), "../backend/app/schemas/result_meta.py"),
    "utf8",
  ),
};

function readBackendSchema(fileName: string) {
  return readFileSync(
    resolve(process.cwd(), "../backend/app/agent/schemas", fileName),
    "utf8",
  );
}

function readBackendRoute(fileName: string) {
  return readFileSync(
    resolve(process.cwd(), "../backend/app/api/routes", fileName),
    "utf8",
  );
}

/** 解析一个 Pydantic 模型类体内声明的字段名（4 空格缩进的 `name: annotation` 行）。 */
function parsePydanticModelFields(source: string, className: string): string[] {
  const classStart = source.indexOf(`class ${className}(`);
  if (classStart < 0) {
    throw new Error(`backend schema is missing class ${className}`);
  }
  const rest = source.slice(classStart);
  const nextClassOffset = rest.slice(1).search(/\r?\nclass /);
  const block = nextClassOffset >= 0 ? rest.slice(0, nextClassOffset + 1) : rest;
  const fields: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    const match = /^ {4}([a-z_][a-zA-Z0-9_]*):/.exec(line);
    if (match && match[1] !== "model_config") {
      fields.push(match[1]);
    }
  }
  return fields;
}

/** 解析模块级 `Symbol = Literal[...]` 的取值列表。 */
function parseLiteralValues(source: string, symbol: string): string[] {
  const match = new RegExp(`${symbol} = Literal\\[([^\\]]*)\\]`).exec(source);
  if (!match) {
    throw new Error(`backend schema is missing Literal ${symbol}`);
  }
  return [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]);
}

function expectFieldParity(
  source: string,
  className: string,
  contractFields: Record<string, true>,
) {
  expect(parsePydanticModelFields(source, className).sort()).toEqual(
    Object.keys(contractFields).sort(),
  );
}

/** 解析路由源码中的机器可判定错误码常量（`*_CODE = "AGENT_..."`）。 */
function parseRouteErrorCodes(source: string): string[] {
  return [...source.matchAll(/^_?[A-Z][A-Z0-9_]*_CODE\s*=\s*"([A-Z0-9_]+)"/gm)].map(
    (match) => match[1],
  );
}

/** 解析路由源码中结构化 detail 字面量的键（形如 `"code": SOME_CONSTANT`）。 */
function parseStructuredDetailKeys(source: string): string[] {
  return [...source.matchAll(/"([a-z_]+)":\s*_?[A-Z][A-Z0-9_]*\s*,?\s*$/gm)].map(
    (match) => match[1],
  );
}

// —— 编译期绑定：清单键必须与契约类型的 keyof 完全一致（多、少、拼错均无法通过 tsc）。 ——

const AGENT_RUN_STATUS_VALUES = {
  queued: true,
  starting: true,
  running: true,
  completed: true,
  failed: true,
  cancelled: true,
} as const satisfies Record<AgentRunStatus, true>;

const AGENT_MESSAGE_ROLE_VALUES = {
  user: true,
  assistant: true,
  system_notice: true,
} as const satisfies Record<AgentMessageRole, true>;

const AGENT_QUERY_REQUEST_FIELDS = {
  question: true,
  basis: true,
  filters: true,
  position_scope: true,
  currency_basis: true,
  context: true,
  page_context: true,
} as const satisfies Record<keyof AgentQueryRequest, true>;

const AGENT_PAGE_CONTEXT_FIELDS = {
  page_id: true,
  current_filters: true,
  selected_rows: true,
  context_note: true,
} as const satisfies Record<keyof AgentPageContext, true>;

const AGENT_DRILL_FIELDS = {
  dimension: true,
  label: true,
} as const satisfies Record<keyof AgentDrill, true>;

const AGENT_SUGGESTED_ACTION_FIELDS = {
  type: true,
  label: true,
  payload: true,
  requires_confirmation: true,
  confirmation_token: true,
} as const satisfies Record<keyof AgentSuggestedAction, true>;

const AGENT_CARD_FIELDS = {
  type: true,
  title: true,
  value: true,
  data: true,
  spec: true,
} as const satisfies Record<keyof AgentCard, true>;

const AGENT_EVIDENCE_FIELDS = {
  tables_used: true,
  filters_applied: true,
  sql_executed: true,
  evidence_rows: true,
  quality_flag: true,
  evidence_strength: true,
} as const satisfies Record<keyof AgentEvidence, true>;

/**
 * ResultMeta 基类字段清单（contracts/core.ts ↔ backend/app/schemas/result_meta.py）。
 * 消除"基类字段盲区"：AgentResultMeta 的 parity 只覆盖子类重声明字段，
 * 基类新增字段（如 amount_currency_basis）需要这份全量清单兜底。
 */
const RESULT_META_BASE_FIELDS = {
  trace_id: true,
  basis: true,
  result_kind: true,
  formal_use_allowed: true,
  amount_currency_basis: true,
  amount_currency_basis_note: true,
  source_version: true,
  vendor_version: true,
  rule_version: true,
  cache_version: true,
  cache_key: true,
  quality_flag: true,
  vendor_status: true,
  fallback_mode: true,
  requested_report_date: true,
  resolved_report_date: true,
  scenario_flag: true,
  as_of_date: true,
  date_basis: true,
  fallback_date: true,
  generated_at: true,
  filters_applied: true,
  tables_used: true,
  evidence_rows: true,
  next_drill: true,
  source_surface: true,
} as const satisfies Record<keyof ResultMeta, true>;

/**
 * AgentResultMeta 后端继承 ResultMeta，只比对子类内重声明/新增的字段；
 * Partial 绑定保证清单键都存在于 TS AgentResultMeta 上（拼错/删除会被 tsc 拦截）。
 */
const AGENT_RESULT_META_EXTRA_FIELDS = {
  tables_used: true,
  filters_applied: true,
  sql_executed: true,
  evidence_rows: true,
  evidence_strength: true,
  next_drill: true,
} as const satisfies Partial<Record<keyof AgentResultMeta, true>>;

const AGENT_ENVELOPE_FIELDS = {
  answer: true,
  cards: true,
  evidence: true,
  result_meta: true,
  next_drill: true,
  suggested_actions: true,
} as const satisfies Record<keyof AgentEnvelope, true>;

const AGENT_DISABLED_RESPONSE_FIELDS = {
  enabled: true,
  phase: true,
  detail: true,
} as const satisfies Record<keyof AgentDisabledResponse, true>;

const AGENT_RUN_STATUS_RESPONSE_FIELDS = {
  run_id: true,
  status: true,
  conversation_id: true,
  retry_of_run_id: true,
  artifact_refs: true,
  question: true,
  provider: true,
  model: true,
  transport: true,
  toolsets: true,
  queued_at: true,
  started_at: true,
  finished_at: true,
  elapsed_seconds: true,
  error_message: true,
  result: true,
} as const satisfies Record<keyof AgentRunStatusResponse, true>;

const AGENT_RUN_CREATE_RESPONSE_FIELDS = {
  run_id: true,
  status: true,
  conversation_id: true,
  retry_of_run_id: true,
  artifact_refs: true,
  provider: true,
  model: true,
  transport: true,
  toolsets: true,
  queued_at: true,
} as const satisfies Record<keyof AgentRunCreateResponse, true>;

const AGENT_RUN_LIST_RESPONSE_FIELDS = {
  items: true,
} as const satisfies Record<keyof AgentRunListResponse, true>;

const AGENT_PROJECT_CREATE_REQUEST_FIELDS = {
  name: true,
  default_scope: true,
  default_currency_basis: true,
} as const satisfies Record<keyof AgentProjectCreateRequest, true>;

const AGENT_PROJECT_UPDATE_REQUEST_FIELDS = {
  name: true,
  archived: true,
} as const satisfies Record<keyof AgentProjectUpdateRequest, true>;

const AGENT_PROJECT_FIELDS = {
  project_id: true,
  owner_user_id: true,
  name: true,
  default_scope: true,
  default_currency_basis: true,
  archived_at: true,
  created_at: true,
  updated_at: true,
} as const satisfies Record<keyof AgentProject, true>;

const AGENT_PROJECT_LIST_RESPONSE_FIELDS = {
  items: true,
  corrupt_records: true,
} as const satisfies Record<keyof AgentProjectListResponse, true>;

const AGENT_CONVERSATION_CREATE_REQUEST_FIELDS = {
  title: true,
} as const satisfies Record<keyof AgentConversationCreateRequest, true>;

const AGENT_CONVERSATION_FIELDS = {
  conversation_id: true,
  project_id: true,
  owner_user_id: true,
  title: true,
  last_run_id: true,
  created_at: true,
  updated_at: true,
} as const satisfies Record<keyof AgentConversation, true>;

const AGENT_CONVERSATION_LIST_RESPONSE_FIELDS = {
  items: true,
  corrupt_records: true,
} as const satisfies Record<keyof AgentConversationListResponse, true>;

const AGENT_MESSAGE_FIELDS = {
  message_id: true,
  conversation_id: true,
  role: true,
  content: true,
  run_id: true,
  artifact_refs: true,
  created_at: true,
  result: true,
} as const satisfies Record<keyof AgentMessage, true>;

const AGENT_MESSAGE_LIST_RESPONSE_FIELDS = {
  items: true,
  corrupt_records: true,
} as const satisfies Record<keyof AgentMessageListResponse, true>;

const AGENT_ARTIFACT_FIELDS = {
  artifact_id: true,
  conversation_id: true,
  run_id: true,
  kind: true,
  title: true,
  content: true,
  result_meta: true,
  created_at: true,
} as const satisfies Record<keyof AgentArtifact, true>;

const AGENT_ARTIFACT_LIST_RESPONSE_FIELDS = {
  items: true,
  corrupt_records: true,
} as const satisfies Record<keyof AgentArtifactListResponse, true>;

const AGENT_ERROR_CODE_VALUES = {
  AGENT_PROVIDER_EXECUTION_FAILED: true,
  AGENT_WORKSPACE_RECORD_CORRUPT: true,
} as const satisfies Record<AgentErrorCode, true>;

const AGENT_ERROR_DETAIL_FIELDS = {
  code: true,
  message: true,
} as const satisfies Record<keyof AgentErrorDetail, true>;

const AGENT_ERROR_RESPONSE_FIELDS = {
  detail: true,
} as const satisfies Record<keyof AgentErrorResponse, true>;

describe("Agent 前后端契约防漂移（backend schemas ↔ contracts/agent.ts）", () => {
  it("AgentRunStatus 取值与后端 Literal 一致（含 cancelled）", () => {
    expect(Object.keys(AGENT_RUN_STATUS_VALUES).sort()).toEqual(
      parseLiteralValues(BACKEND_SCHEMA_SOURCES.agentRun, "AgentRunStatus").sort(),
    );
  });

  it("AgentMessageRole 取值与后端 Literal 一致", () => {
    expect(Object.keys(AGENT_MESSAGE_ROLE_VALUES).sort()).toEqual(
      parseLiteralValues(BACKEND_SCHEMA_SOURCES.agentWorkspace, "AgentMessageRole").sort(),
    );
  });

  it("agent_request.py 模型字段与前端契约一致", () => {
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentRequest, "AgentQueryRequest", AGENT_QUERY_REQUEST_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentRequest, "AgentPageContext", AGENT_PAGE_CONTEXT_FIELDS);
  });

  it("ResultMeta 基类字段与后端 schemas/result_meta.py 一致（含 amount_currency_basis）", () => {
    expectFieldParity(
      BACKEND_BASE_SCHEMA_SOURCES.resultMeta,
      "ResultMeta",
      RESULT_META_BASE_FIELDS,
    );
  });

  it("agent_response.py 模型字段与前端契约一致", () => {
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentDrill", AGENT_DRILL_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentSuggestedAction", AGENT_SUGGESTED_ACTION_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentCard", AGENT_CARD_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentEvidence", AGENT_EVIDENCE_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentResultMeta", AGENT_RESULT_META_EXTRA_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentEnvelope", AGENT_ENVELOPE_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentResponse, "AgentDisabledResponse", AGENT_DISABLED_RESPONSE_FIELDS);
  });

  it("agent_run.py 模型字段与前端契约一致", () => {
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentRun, "AgentRunStatusResponse", AGENT_RUN_STATUS_RESPONSE_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentRun, "AgentRunCreateResponse", AGENT_RUN_CREATE_RESPONSE_FIELDS);
    expectFieldParity(BACKEND_SCHEMA_SOURCES.agentRun, "AgentRunListResponse", AGENT_RUN_LIST_RESPONSE_FIELDS);
  });

  it("agent_workspace.py 模型字段与前端契约一致", () => {
    const source = BACKEND_SCHEMA_SOURCES.agentWorkspace;
    expectFieldParity(source, "AgentProjectCreateRequest", AGENT_PROJECT_CREATE_REQUEST_FIELDS);
    expectFieldParity(source, "AgentProjectUpdateRequest", AGENT_PROJECT_UPDATE_REQUEST_FIELDS);
    expectFieldParity(source, "AgentProject", AGENT_PROJECT_FIELDS);
    expectFieldParity(source, "AgentProjectListResponse", AGENT_PROJECT_LIST_RESPONSE_FIELDS);
    expectFieldParity(source, "AgentConversationCreateRequest", AGENT_CONVERSATION_CREATE_REQUEST_FIELDS);
    expectFieldParity(source, "AgentConversation", AGENT_CONVERSATION_FIELDS);
    expectFieldParity(source, "AgentConversationListResponse", AGENT_CONVERSATION_LIST_RESPONSE_FIELDS);
    expectFieldParity(source, "AgentMessage", AGENT_MESSAGE_FIELDS);
    expectFieldParity(source, "AgentMessageListResponse", AGENT_MESSAGE_LIST_RESPONSE_FIELDS);
    expectFieldParity(source, "AgentArtifact", AGENT_ARTIFACT_FIELDS);
    expectFieldParity(source, "AgentArtifactListResponse", AGENT_ARTIFACT_LIST_RESPONSE_FIELDS);
  });
});

/** 解析 workspace 路由源码中的 GET 路径模板（挂载前缀为 /api/agent，见 agent.py include_router）。 */
function parseWorkspaceGetRoutePaths(source: string): string[] {
  return [...source.matchAll(/@router\.get\(\s*"([^"]+)"/g)].map((match) => `/api/agent${match[1]}`);
}

/**
 * 只读客户端覆盖清单：key 为后端路由模板；调用时以模板占位符字面量作 id，
 * 解码请求 URL 后应还原出同一模板（同时锁方法名与路径的映射关系）。
 */
const WORKSPACE_READ_CLIENT_CALLS: Record<
  string,
  (client: AgentClientMethods) => Promise<unknown>
> = {
  "/api/agent/projects": (client) => client.listAgentProjects(),
  "/api/agent/projects/{project_id}": (client) => client.getAgentProject("{project_id}"),
  "/api/agent/projects/{project_id}/conversations": (client) =>
    client.listAgentConversations("{project_id}"),
  "/api/agent/conversations/{conversation_id}": (client) =>
    client.getAgentConversation("{conversation_id}"),
  "/api/agent/conversations/{conversation_id}/messages": (client) =>
    client.listAgentConversationMessages("{conversation_id}"),
  "/api/agent/conversations/{conversation_id}/artifacts": (client) =>
    client.listAgentConversationArtifacts("{conversation_id}"),
  "/api/agent/artifacts/{artifact_id}": (client) => client.getAgentArtifact("{artifact_id}"),
};

describe("workspace 只读客户端与后端路由防漂移（agentClient.ts ↔ agent_workspace.py）", () => {
  it("后端全部 workspace GET 路由都有对应的只读客户端方法", () => {
    expect(parseWorkspaceGetRoutePaths(BACKEND_ROUTE_SOURCES.agentWorkspace).sort()).toEqual(
      Object.keys(WORKSPACE_READ_CLIENT_CALLS).sort(),
    );
  });

  it.each(Object.entries(WORKSPACE_READ_CLIENT_CALLS))(
    "客户端方法以 GET 命中路由模板 %s",
    async (routeTemplate, invoke) => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      const client = createRealAgentClient({
        fetchImpl: fetchImpl as unknown as typeof fetch,
        baseUrl: "",
      });

      await invoke(client);

      expect(fetchImpl).toHaveBeenCalledTimes(1);
      const [requestUrl, requestInit] = fetchImpl.mock.calls[0] as unknown as [
        string,
        RequestInit,
      ];
      expect(requestInit.method).toBe("GET");
      expect(decodeURIComponent(requestUrl)).toBe(routeTemplate);
    },
  );
});

describe("错误响应契约防漂移（backend routes ↔ contracts/agent.ts）", () => {
  it("AgentErrorCode 枚举覆盖后端路由的全部机器可判定错误码", () => {
    const backendCodes = new Set([
      ...parseRouteErrorCodes(BACKEND_ROUTE_SOURCES.agent),
      ...parseRouteErrorCodes(BACKEND_ROUTE_SOURCES.agentWorkspace),
    ]);
    expect([...backendCodes].sort()).toEqual(
      Object.keys(AGENT_ERROR_CODE_VALUES).sort(),
    );
  });

  it("后端结构化错误 detail 字面量只使用 code/message 两个键", () => {
    const backendKeys = new Set([
      ...parseStructuredDetailKeys(BACKEND_ROUTE_SOURCES.agent),
      ...parseStructuredDetailKeys(BACKEND_ROUTE_SOURCES.agentWorkspace),
    ]);
    expect([...backendKeys].sort()).toEqual(
      Object.keys(AGENT_ERROR_DETAIL_FIELDS).sort(),
    );
    expect(Object.keys(AGENT_ERROR_RESPONSE_FIELDS)).toEqual(["detail"]);
  });
});

describe("cancelled 运行时判定", () => {
  it("运行时状态守卫接受全部后端状态（含 cancelled）", () => {
    const backendStatuses = parseLiteralValues(BACKEND_SCHEMA_SOURCES.agentRun, "AgentRunStatus");
    expect([...AGENT_RUN_STATUSES].sort()).toEqual([...backendStatuses].sort());
    for (const status of backendStatuses) {
      expect(isAgentRunStatus(status), `isAgentRunStatus(${status})`).toBe(true);
    }
  });

  it("cancelled 的 run payload 不再被判定为格式无效", () => {
    expect(
      isAgentRunPayload({
        run_id: "agent_run:cancel_check",
        status: "cancelled",
        provider: "hermes",
        model: "default",
        transport: "bridge",
        toolsets: "default",
        error_message: null,
      }),
    ).toBe(true);
  });

  it("cancelled 属于终态，completed/failed 语义保持不变", () => {
    expect(isTerminalAgentRunStatus("cancelled")).toBe(true);
    expect(isTerminalAgentRunStatus("completed")).toBe(true);
    expect(isTerminalAgentRunStatus("failed")).toBe(true);
    expect(isTerminalAgentRunStatus("running")).toBe(false);
    expect(isTerminalAgentRunStatus("queued")).toBe(false);
    expect(isTerminalAgentRunStatus("starting")).toBe(false);
  });
});
