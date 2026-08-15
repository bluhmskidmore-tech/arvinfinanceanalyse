import type { AgentSuggestedAction } from "../../../api/contracts";

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

export function normalizeAgentResult(result: AgentQueryResult): AgentQueryResult {
  result.suggested_actions = result.suggested_actions ?? [];
  return result;
}
