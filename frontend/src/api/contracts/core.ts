/** Shared API surface: envelope, health, and cross-cutting enums. */
/**
 * Shared governed numeric primitive.
 * Mirrors backend ``backend/app/schemas/common_numeric.py::Numeric``.
 * See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 3.
 */
export type NumericUnit = "yuan" | "pct" | "bp" | "ratio" | "years" | "count" | "dv01" | "yi";

export type Numeric = {
  /** 兼容近似数值，保留后端原始浮点/number 形态；正式精度比较不要依赖它。 */
  raw: number | null;
  /** 可选无损十进制权威文本；存在时优先作为精度/缩放边界输入。 */
  raw_text?: string | null;
  unit: NumericUnit;
  display: string;
  precision: number;
  sign_aware: boolean;
};

export type ApiBasis = "formal" | "scenario" | "analytical" | "ledger" | "mock";

export type PnlBasis = "formal" | "analytical";

export type ApiQuality = "ok" | "warning" | "error" | "stale" | "missing";

export type ResultNextDrill = string | Record<string, unknown>;

export type HealthCheckStatus = {
  ok: boolean;
  detail: string;
};

export type HealthResponse = {
  status: "ok" | "degraded" | "down";
  checks?: Record<string, HealthCheckStatus>;
};

/** GET /health/live 与 GET /health — 后端返回的最简 `{ status: string }` 载荷。 */
export type HealthStatusResponse = {
  status: string;
};

export type ResultMeta = {
  trace_id: string;
  basis: ApiBasis;
  result_kind: string;
  formal_use_allowed: boolean;
  /** 金额币种口径（后端 ResultMeta 基类字段；analysis_view_tool 等实际输出）。 */
  amount_currency_basis?: string | null;
  amount_currency_basis_note?: string | null;
  source_version: string;
  vendor_version: string;
  rule_version: string;
  cache_version: string;
  cache_key?: string | null;
  quality_flag: ApiQuality;
  vendor_status: "ok" | "vendor_stale" | "vendor_unavailable";
  fallback_mode: "none" | "latest_snapshot";
  source_surface?: string | null;
  scenario_flag: boolean;
  requested_report_date?: string | null;
  resolved_report_date?: string | null;
  as_of_date?: string | null;
  date_basis?: string | null;
  fallback_date?: string | null;
  /** 响应组装时刻，不是数据新鲜度信号：刚生成的响应可能承载数天前物化的数据。 */
  generated_at: string;
  /** 数据物化完成时刻（来自治理流 cache_build_run.finished_at）；无已完成构建终态时为空。 */
  data_built_at?: string | null;
  tables_used?: string[];
  filters_applied?: Record<string, unknown>;
  evidence_rows?: number;
  next_drill?: ResultNextDrill[];
};

export type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
  /** 可选：标识本响应依赖的正式事实表族（如 bond_analytics vs balance_analysis）。 */
  data_source?: string;
};
