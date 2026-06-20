/**
 * Agent MVP — POST /api/agent/query。实现放在此模块；`client.ts` 仅做组合。
 */
import type { AgentEnvelope, AgentQueryRequest } from "./contracts";

type FetchLike = typeof fetch;

export type AgentClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type AgentClientMethods = {
  queryAgent: (request: AgentQueryRequest) => Promise<AgentEnvelope>;
};

export type AgentClientDelay = () => Promise<void>;

export class AgentDisabledError extends Error {
  readonly code = "AGENT_DISABLED" as const;

  constructor(message = "Agent 当前未启用") {
    super(message);
    this.name = "AgentDisabledError";
  }
}

function isAgentDisabledPayload(value: unknown): value is { enabled: false } {
  return Boolean(value && typeof value === "object" && "enabled" in value && (value as { enabled?: boolean }).enabled === false);
}

/** Mock / 演示：稳定结构，answer 固定文案。 */
export function buildStableDemoAgentEnvelope(): AgentEnvelope {
  const now = new Date().toISOString();
  return {
    answer: "Agent 当前为演示模式",
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
        label: "演示建议动作",
        payload: {},
        requires_confirmation: true,
      },
    ],
  };
}

export function createDemoAgentClient(delay: AgentClientDelay): AgentClientMethods {
  return {
    async queryAgent(_request: AgentQueryRequest): Promise<AgentEnvelope> {
      await delay();
      return buildStableDemoAgentEnvelope();
    },
  };
}

export function createRealAgentClient(options: AgentClientFactoryOptions): AgentClientMethods {
  const { fetchImpl, baseUrl } = options;

  return {
    async queryAgent(request: AgentQueryRequest): Promise<AgentEnvelope> {
      const response = await fetchImpl(`${baseUrl}/api/agent/query`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });

      if (response.status === 503) {
        let parsed: unknown;
        try {
          parsed = await response.json();
        } catch {
          throw new AgentDisabledError();
        }
        if (isAgentDisabledPayload(parsed)) {
          throw new AgentDisabledError("Agent 当前未启用");
        }
        const detail =
          parsed &&
          typeof parsed === "object" &&
          "detail" in parsed &&
          typeof (parsed as { detail?: unknown }).detail === "string"
            ? (parsed as { detail: string }).detail
            : `Agent 请求失败（503）`;
        throw new Error(detail);
      }

      if (!response.ok) {
        throw new Error(`Request failed: /api/agent/query (${response.status})`);
      }

      return (await response.json()) as AgentEnvelope;
    },
  };
}
