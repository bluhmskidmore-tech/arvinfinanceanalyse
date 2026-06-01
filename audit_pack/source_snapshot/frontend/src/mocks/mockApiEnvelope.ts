import type { ApiEnvelope, ResultMeta } from "../api/contracts";

export function buildMockMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `mock_${resultKind}`,
    basis: "mock",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_mock_dashboard_v2",
    vendor_version: "vv_none",
    rule_version: "rv_dashboard_mock_v2",
    cache_version: "cv_dashboard_mock_v2",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-09T10:30:00Z",
  };
}

export function buildMockApiEnvelope<T>(
  resultKind: string,
  result: T,
  metaOverrides?: Partial<ResultMeta>,
): ApiEnvelope<T> {
  return {
    result_meta: { ...buildMockMeta(resultKind), ...metaOverrides },
    result,
  };
}
