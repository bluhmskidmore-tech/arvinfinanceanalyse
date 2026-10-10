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
  AgentModelCatalog,
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

/** 同步查询的中止入口：调用方停止/切换回合后不再等待这条响应。 */
export type AgentQueryCallOptions = {
  signal?: AbortSignal;
};

export type AgentClientMethods = {
  getAgentModels: () => Promise<AgentModelCatalog>;
  queryAgent: (request: AgentQueryRequest, options?: AgentQueryCallOptions) => Promise<AgentEnvelope>;
  createAgentRun: (request: AgentQueryRequest) => Promise<AgentRunCreateResult>;
  createAgentLabRun: (request: AgentQueryRequest) => Promise<AgentRunCreateResult>;
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
    async queryAgent(
      request: AgentQueryRequest,
      options?: AgentQueryCallOptions,
    ): Promise<AgentEnvelope> {
      return requestAgentJson<AgentEnvelope>("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        ...(options?.signal ? { signal: options.signal } : {}),
      });
    },
    async getAgentModels(): Promise<AgentModelCatalog> {
      return requestAgentJson<AgentModelCatalog>("/api/agent/models", { method: "GET" });
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
    async createAgentLabRun(request: AgentQueryRequest): Promise<AgentRunCreateResult> {
      return requestAgentJson<AgentRunCreateResult>("/api/agent/lab/runs", {
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
