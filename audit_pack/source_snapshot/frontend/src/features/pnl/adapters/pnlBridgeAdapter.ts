import type {
  ApiEnvelope,
  PnlBridgePayload,
  PnlBridgeRow,
  PnlBridgeSummary,
  ResultMeta,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";

export type PnlBridgeVM = {
  reportDate: string;
  summary: PnlBridgeSummary;
  rows: PnlBridgeRow[];
  warnings: string[];
};

export type PnlBridgeAdapterOutput = {
  vm: PnlBridgeVM | null;
  state: DataSectionState;
  meta: ResultMeta | null;
};

export type AdaptPnlBridgeInput = {
  envelope: ApiEnvelope<PnlBridgePayload> | undefined;
  isLoading: boolean;
  isError: boolean;
};

function readFilterDate(filters: Record<string, unknown> | undefined): string | undefined {
  if (!filters) return undefined;
  const v = filters["report_date"];
  return typeof v === "string" ? v : undefined;
}

function deriveState(
  env: ApiEnvelope<PnlBridgePayload> | undefined,
  isLoading: boolean,
  isError: boolean,
): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error" };
  if (!env) return { kind: "empty" };
  const meta = env.result_meta;
  if (meta.vendor_status === "vendor_unavailable") return { kind: "vendor_unavailable" };
  if (typeof meta.source_version === "string" && meta.source_version.includes("explicit_miss")) {
    return { kind: "explicit_miss", requested_date: readFilterDate(meta.filters_applied) };
  }
  if (meta.fallback_mode === "latest_snapshot") {
    return { kind: "fallback", effective_date: readFilterDate(meta.filters_applied) };
  }
  if (meta.vendor_status === "vendor_stale" || meta.quality_flag === "stale") {
    return { kind: "stale", effective_date: readFilterDate(meta.filters_applied) };
  }
  const p = env.result;
  if (!p || (p.rows.length === 0 && p.summary.row_count === 0)) return { kind: "empty" };
  return { kind: "ok" };
}

export function adaptPnlBridge(input: AdaptPnlBridgeInput): PnlBridgeAdapterOutput {
  const state = deriveState(input.envelope, input.isLoading, input.isError);
  const env = input.envelope;
  if (!env || state.kind === "loading" || state.kind === "error") {
    return { vm: null, state, meta: env?.result_meta ?? null };
  }
  const p = env.result;
  const vm: PnlBridgeVM = {
    reportDate: p.report_date,
    summary: p.summary,
    rows: p.rows,
    warnings: p.warnings ?? [],
  };
  return { vm, state, meta: env.result_meta };
}
