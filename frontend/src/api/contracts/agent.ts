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
  /** @deprecated Prefer `page_context`. Frontend AgentPanel no longer sends this field. */
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
