export type ApiBasis = "formal" | "scenario" | "analytical" | "mock";
export type ApiQuality = "ok" | "warning" | "error" | "stale";

export type HealthCheckStatus = {
  ok: boolean;
  detail: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  checks?: Record<string, HealthCheckStatus>;
};

export type ResultMeta = {
  trace_id: string;
  basis: ApiBasis;
  result_kind: string;
  formal_use_allowed: boolean;
  source_version: string;
  vendor_version: string;
  rule_version: string;
  cache_version: string;
  quality_flag: ApiQuality;
  scenario_flag: boolean;
  generated_at: string;
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
};

export type ExecutiveMetric = {
  id: string;
  label: string;
  value: string;
  delta: string;
  tone: "positive" | "neutral" | "warning" | "negative";
  detail: string;
};

export type OverviewPayload = {
  title: string;
  metrics: ExecutiveMetric[];
};

export type SummaryPoint = {
  id: string;
  label: string;
  tone: "positive" | "neutral" | "warning";
  text: string;
};

export type SummaryPayload = {
  title: string;
  narrative: string;
  points: SummaryPoint[];
};

export type AttributionSegment = {
  id: string;
  label: string;
  amount: number;
  display_amount: string;
  tone: "positive" | "neutral" | "negative";
};

export type PnlAttributionPayload = {
  title: string;
  total: string;
  segments: AttributionSegment[];
};

export type RiskSignal = {
  id: string;
  label: string;
  value: string;
  status: "stable" | "watch" | "warning";
  detail: string;
};

export type RiskOverviewPayload = {
  title: string;
  signals: RiskSignal[];
};

export type ContributionRow = {
  id: string;
  name: string;
  owner: string;
  contribution: string;
  completion: number;
  status: string;
};

export type ContributionPayload = {
  title: string;
  rows: ContributionRow[];
};

export type AlertItem = {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  occurred_at: string;
  detail: string;
};

export type AlertsPayload = {
  title: string;
  items: AlertItem[];
};

export type PlaceholderSnapshot = {
  title: string;
  summary: string;
  highlights: string[];
};
