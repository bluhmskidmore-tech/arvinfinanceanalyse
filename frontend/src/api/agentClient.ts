/**
 * Agent API domain client. Keep endpoint ownership here; client.ts only composes it.
 */
import type {
  AgentArtifact,
  AgentArtifactListResponse,
  AgentConversation,
  AgentConversationListResponse,
  AgentEnvelope,
  AgentMessageListResponse,
  AgentProject,
  AgentProjectListResponse,
  AgentQueryRequest,
  AgentRunCreateResult,
  AgentRunStatusResponse,
} from "./contracts";

type FetchLike = typeof fetch;

export type AgentClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type ListAgentProjectsOptions = {
  includeArchived?: boolean;
};

export type AgentClientMethods = {
  queryAgent: (request: AgentQueryRequest) => Promise<AgentEnvelope>;
  createAgentRun: (request: AgentQueryRequest) => Promise<AgentRunCreateResult>;
  getAgentRun: (runId: string) => Promise<AgentRunStatusResponse>;
  cancelAgentRun: (runId: string) => Promise<AgentRunStatusResponse>;
  /** 只读 workspace 端点（backend routes/agent_workspace.py 的 GET 面）。 */
  listAgentProjects: (options?: ListAgentProjectsOptions) => Promise<AgentProjectListResponse>;
  getAgentProject: (projectId: string) => Promise<AgentProject>;
  listAgentConversations: (projectId: string) => Promise<AgentConversationListResponse>;
  getAgentConversation: (conversationId: string) => Promise<AgentConversation>;
  listAgentConversationMessages: (conversationId: string) => Promise<AgentMessageListResponse>;
  listAgentConversationArtifacts: (conversationId: string) => Promise<AgentArtifactListResponse>;
  getAgentArtifact: (artifactId: string) => Promise<AgentArtifact>;
};

export type AgentClientDelay = () => Promise<void>;

export class AgentDisabledError extends Error {
  readonly code = "AGENT_DISABLED" as const;
  readonly phase: string;

  constructor(message = "Agent is currently disabled.", phase = "phase1") {
    super(message);
    this.name = "AgentDisabledError";
    this.phase = phase;
  }
}

export class AgentApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly payload: unknown;

  constructor(message: string, opts: { status: number; path: string; payload: unknown }) {
    super(message);
    this.name = "AgentApiError";
    this.status = opts.status;
    this.path = opts.path;
    this.payload = opts.payload;
  }
}

function isAgentDisabledPayload(value: unknown): value is { enabled: false; detail?: string; phase?: string } {
  return Boolean(
    value &&
      typeof value === "object" &&
      "enabled" in value &&
      (value as { enabled?: boolean }).enabled === false,
  );
}

export function buildStableDemoAgentEnvelope(): AgentEnvelope {
  const now = new Date().toISOString();
  return {
    answer: "Agent is running in demo mode.",
    cards: [],
    evidence: {
      tables_used: [],
      filters_applied: {},
      sql_executed: [],
      evidence_rows: 0,
      quality_flag: "ok",
    },
    result_meta: {
      trace_id: "tr_agent_frontend_mock",
      basis: "mock",
      result_kind: "agent.frontend_mock",
      formal_use_allowed: false,
      source_version: "sv_agent_frontend_mock",
      vendor_version: "vv_none",
      rule_version: "rv_agent_frontend_mock",
      cache_version: "cv_agent_frontend_mock",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: now,
      filters_applied: {},
      tables_used: [],
      evidence_rows: 0,
      sql_executed: [],
      next_drill: [],
    },
    next_drill: [],
    suggested_actions: [
      {
        type: "demo_chip",
        label: "Demo suggested action",
        payload: {},
        requires_confirmation: true,
      },
    ],
  };
}

/** run_kind 为前端本地增强字段，后端契约不返回；demo 载荷保留以驱动本地 UI 分支。 */
function buildDemoAgentRunPayload(
  request: AgentQueryRequest,
  runId = "agent_run:frontend_mock",
): AgentRunStatusResponse & { run_kind: "sync" } {
  return {
    run_id: runId,
    status: "completed",
    run_kind: "sync",
    question: request.question,
    provider: "mock",
    model: "frontend-demo",
    transport: "mock",
    toolsets: "demo",
    result: buildStableDemoAgentEnvelope(),
  };
}

/** Workspace demo 桩数据的固定时间戳；默认口径镜像后端缺省（all / CNY）。 */
const DEMO_AGENT_WORKSPACE_TIMESTAMP = "2026-01-01T00:00:00Z";

function buildDemoAgentProject(projectId = "agent_project:frontend_mock"): AgentProject {
  return {
    project_id: projectId,
    owner_user_id: "frontend-demo",
    name: "Demo workspace project",
    default_scope: "all",
    default_currency_basis: "CNY",
    archived_at: null,
    created_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
    updated_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
  };
}

function buildDemoAgentConversation(
  conversationId = "agent_conversation:frontend_mock",
): AgentConversation {
  return {
    conversation_id: conversationId,
    project_id: "agent_project:frontend_mock",
    owner_user_id: "frontend-demo",
    title: "Demo conversation",
    last_run_id: "agent_run:frontend_mock",
    created_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
    updated_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
  };
}

function buildDemoAgentArtifact(artifactId = "agent_artifact:frontend_mock"): AgentArtifact {
  const envelope = buildStableDemoAgentEnvelope();
  return {
    artifact_id: artifactId,
    conversation_id: "agent_conversation:frontend_mock",
    run_id: "agent_run:frontend_mock",
    kind: "agent_envelope",
    title: "Demo artifact",
    content: envelope,
    result_meta: envelope.result_meta,
    created_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
  };
}

export function createDemoAgentClient(delay: AgentClientDelay): AgentClientMethods {
  return {
    async queryAgent(_request: AgentQueryRequest): Promise<AgentEnvelope> {
      await delay();
      return buildStableDemoAgentEnvelope();
    },
    async createAgentRun(request: AgentQueryRequest): Promise<AgentRunCreateResult> {
      await delay();
      return buildDemoAgentRunPayload(request);
    },
    async getAgentRun(runId: string): Promise<AgentRunStatusResponse> {
      await delay();
      return buildDemoAgentRunPayload({ question: "Agent demo run" }, runId);
    },
    async cancelAgentRun(runId: string): Promise<AgentRunStatusResponse> {
      await delay();
      return {
        ...buildDemoAgentRunPayload({ question: "Agent demo run" }, runId),
        status: "cancelled",
        result: null,
      };
    },
    async listAgentProjects(
      options?: ListAgentProjectsOptions,
    ): Promise<AgentProjectListResponse> {
      await delay();
      const project = buildDemoAgentProject();
      return {
        items: options?.includeArchived
          ? [project, { ...buildDemoAgentProject("agent_project:frontend_mock_archived"), archived_at: DEMO_AGENT_WORKSPACE_TIMESTAMP }]
          : [project],
        corrupt_records: 0,
      };
    },
    async getAgentProject(projectId: string): Promise<AgentProject> {
      await delay();
      return buildDemoAgentProject(projectId);
    },
    async listAgentConversations(_projectId: string): Promise<AgentConversationListResponse> {
      await delay();
      return { items: [buildDemoAgentConversation()], corrupt_records: 0 };
    },
    async getAgentConversation(conversationId: string): Promise<AgentConversation> {
      await delay();
      return buildDemoAgentConversation(conversationId);
    },
    async listAgentConversationMessages(
      conversationId: string,
    ): Promise<AgentMessageListResponse> {
      await delay();
      const envelope = buildStableDemoAgentEnvelope();
      return {
        items: [
          {
            message_id: "agent_message:frontend_mock",
            conversation_id: conversationId,
            role: "assistant",
            content: envelope.answer,
            run_id: "agent_run:frontend_mock",
            artifact_refs: ["agent_artifact:frontend_mock"],
            created_at: DEMO_AGENT_WORKSPACE_TIMESTAMP,
            result: envelope,
          },
        ],
        corrupt_records: 0,
      };
    },
    async listAgentConversationArtifacts(
      _conversationId: string,
    ): Promise<AgentArtifactListResponse> {
      await delay();
      return { items: [buildDemoAgentArtifact()], corrupt_records: 0 };
    },
    async getAgentArtifact(artifactId: string): Promise<AgentArtifact> {
      await delay();
      return buildDemoAgentArtifact(artifactId);
    },
  };
}

export function createRealAgentClient(options: AgentClientFactoryOptions): AgentClientMethods {
  const { fetchImpl, baseUrl } = options;

  async function requestAgentJson<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetchImpl(`${baseUrl}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
    });

    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      parsed = undefined;
    }

    if (response.status === 503 && isAgentDisabledPayload(parsed)) {
      throw new AgentDisabledError(
        typeof parsed.detail === "string" && parsed.detail.trim()
          ? parsed.detail
          : undefined,
        typeof parsed.phase === "string" && parsed.phase.trim()
          ? parsed.phase
          : undefined,
      );
    }

    if (!response.ok) {
      throw new AgentApiError(`Request failed: ${path} (${response.status})`, {
        status: response.status,
        path,
        payload: parsed,
      });
    }

    return parsed as T;
  }

  return {
    async queryAgent(request: AgentQueryRequest): Promise<AgentEnvelope> {
      return requestAgentJson<AgentEnvelope>("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });
    },
    async createAgentRun(request: AgentQueryRequest): Promise<AgentRunCreateResult> {
      return requestAgentJson<AgentRunCreateResult>("/api/agent/runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });
    },
    async getAgentRun(runId: string): Promise<AgentRunStatusResponse> {
      return requestAgentJson<AgentRunStatusResponse>(`/api/agent/runs/${encodeURIComponent(runId)}`, {
        method: "GET",
      });
    },
    async cancelAgentRun(runId: string): Promise<AgentRunStatusResponse> {
      return requestAgentJson<AgentRunStatusResponse>(
        `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
        { method: "POST" },
      );
    },
    async listAgentProjects(
      options?: ListAgentProjectsOptions,
    ): Promise<AgentProjectListResponse> {
      const query = options?.includeArchived ? "?include_archived=true" : "";
      return requestAgentJson<AgentProjectListResponse>(`/api/agent/projects${query}`, {
        method: "GET",
      });
    },
    async getAgentProject(projectId: string): Promise<AgentProject> {
      return requestAgentJson<AgentProject>(
        `/api/agent/projects/${encodeURIComponent(projectId)}`,
        { method: "GET" },
      );
    },
    async listAgentConversations(projectId: string): Promise<AgentConversationListResponse> {
      return requestAgentJson<AgentConversationListResponse>(
        `/api/agent/projects/${encodeURIComponent(projectId)}/conversations`,
        { method: "GET" },
      );
    },
    async getAgentConversation(conversationId: string): Promise<AgentConversation> {
      return requestAgentJson<AgentConversation>(
        `/api/agent/conversations/${encodeURIComponent(conversationId)}`,
        { method: "GET" },
      );
    },
    async listAgentConversationMessages(
      conversationId: string,
    ): Promise<AgentMessageListResponse> {
      return requestAgentJson<AgentMessageListResponse>(
        `/api/agent/conversations/${encodeURIComponent(conversationId)}/messages`,
        { method: "GET" },
      );
    },
    async listAgentConversationArtifacts(
      conversationId: string,
    ): Promise<AgentArtifactListResponse> {
      return requestAgentJson<AgentArtifactListResponse>(
        `/api/agent/conversations/${encodeURIComponent(conversationId)}/artifacts`,
        { method: "GET" },
      );
    },
    async getAgentArtifact(artifactId: string): Promise<AgentArtifact> {
      return requestAgentJson<AgentArtifact>(
        `/api/agent/artifacts/${encodeURIComponent(artifactId)}`,
        { method: "GET" },
      );
    },
  };
}
