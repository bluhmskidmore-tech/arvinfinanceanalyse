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
} from "../api/contracts";
import type {
  AgentClientDelay,
  AgentClientMethods,
  AgentQueryCallOptions,
  ListAgentProjectsOptions,
} from "../api/agentClient";

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
      // 后端 AgentEvidence 默认 evidence_strength="local_fallback"，并在
      // evidence_strength 属于 {provider_runtime, local_fallback, mixed} 时
      // 把 quality_flag 从 "ok" 降级为 "warning"（agent_response.py 的
      // _downgrade_non_governed_quality）。demo 桩不经过后端校验，必须显式
      // 复现这个降级结果，否则 demo 比正式治理更乐观。
      quality_flag: "warning",
      evidence_strength: "local_fallback",
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
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: now,
      filters_applied: {},
      tables_used: [],
      evidence_rows: 0,
      sql_executed: [],
      evidence_strength: "local_fallback",
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
    async getAgentModels(): Promise<AgentModelCatalog> {
      await delay();
      return { provider: "mock", default_model: "", models: [], source: "configured" };
    },
    async queryAgent(
      _request: AgentQueryRequest,
      _options?: AgentQueryCallOptions,
    ): Promise<AgentEnvelope> {
      await delay();
      return buildStableDemoAgentEnvelope();
    },
    async createAgentRun(request: AgentQueryRequest): Promise<AgentRunCreateResult> {
      await delay();
      return buildDemoAgentRunPayload(request);
    },
    async createAgentLabRun(request: AgentQueryRequest): Promise<AgentRunCreateResult> {
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
