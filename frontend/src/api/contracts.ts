export type HealthResponse = {
  service: string;
  status: "ok" | "degraded" | "down";
  checkedAt: string;
};

export type ResultMeta = {
  trace_id: string;
  basis: "mock" | "formal" | "scenario";
  result_kind: string;
  scenario_flag: boolean;
  source_version: string;
  rule_version: string;
  cache_version: string;
  quality_flag: "ok" | "stale" | "warning";
  generated_at: string;
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
};

export type ShellCard = {
  id: string;
  title: string;
  value: string;
  detail: string;
};

export type DashboardSnapshot = {
  title: string;
  subtitle: string;
  cards: ShellCard[];
};

export type PlaceholderSnapshot = {
  title: string;
  summary: string;
  highlights: string[];
};
