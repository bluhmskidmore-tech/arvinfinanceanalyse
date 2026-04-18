import type {
  ApiEnvelope,
  CashflowMaturingAsset,
  CashflowMonthlyBucket,
  CashflowProjectionPayload,
  Numeric,
  ResultMeta,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";

export type CashflowBucketVM = {
  yearMonth: string;
  assetInflow: Numeric;
  liabilityOutflow: Numeric;
  netCashflow: Numeric;
  cumulativeNet: Numeric;
};

export type CashflowMaturingAssetVM = {
  instrumentCode: string;
  instrumentName: string;
  maturityDate: string;
  faceValue: Numeric;
  marketValue: Numeric;
  currencyCode: string;
};

export type CashflowProjectionVM = {
  reportDate: string;
  kpis: {
    durationGap: Numeric;
    assetDuration: Numeric;
    liabilityDuration: Numeric;
    equityDuration: Numeric;
    rateSensitivity1bp: Numeric;
    reinvestmentRisk12m: Numeric;
  };
  monthlyBuckets: CashflowBucketVM[];
  topMaturingAssets: CashflowMaturingAssetVM[];
  warnings: string[];
};

export type CashflowAdapterOutput = {
  vm: CashflowProjectionVM | null;
  state: DataSectionState;
  meta: ResultMeta | null;
};

export type AdaptCashflowInput = {
  envelope: ApiEnvelope<CashflowProjectionPayload> | undefined;
  isLoading: boolean;
  isError: boolean;
};

function mapBucket(b: CashflowMonthlyBucket): CashflowBucketVM {
  return {
    yearMonth: b.year_month,
    assetInflow: b.asset_inflow,
    liabilityOutflow: b.liability_outflow,
    netCashflow: b.net_cashflow,
    cumulativeNet: b.cumulative_net,
  };
}

function mapAsset(a: CashflowMaturingAsset): CashflowMaturingAssetVM {
  return {
    instrumentCode: a.instrument_code,
    instrumentName: a.instrument_name,
    maturityDate: a.maturity_date,
    faceValue: a.face_value,
    marketValue: a.market_value,
    currencyCode: a.currency_code,
  };
}

function deriveState(
  envelope: ApiEnvelope<CashflowProjectionPayload> | undefined,
  isLoading: boolean,
  isError: boolean,
): DataSectionState {
  if (isLoading) return { kind: "loading" };
  if (isError) return { kind: "error" };
  if (!envelope) return { kind: "empty" };

  const meta = envelope.result_meta;
  if (meta.vendor_status === "vendor_unavailable") {
    return { kind: "vendor_unavailable" };
  }
  if (typeof meta.source_version === "string" && meta.source_version.includes("explicit_miss")) {
    return {
      kind: "explicit_miss",
      requested_date: readFilterDate(meta.filters_applied),
    };
  }
  if (meta.fallback_mode === "latest_snapshot") {
    return {
      kind: "fallback",
      effective_date: readFilterDate(meta.filters_applied),
    };
  }
  if (meta.vendor_status === "vendor_stale" || meta.quality_flag === "stale") {
    return {
      kind: "stale",
      effective_date: readFilterDate(meta.filters_applied),
    };
  }
  const payload = envelope.result;
  if (!payload || (payload.monthly_buckets.length === 0 && payload.top_maturing_assets_12m.length === 0)) {
    return { kind: "empty" };
  }
  return { kind: "ok" };
}

function readFilterDate(filters: Record<string, unknown> | undefined): string | undefined {
  if (!filters) return undefined;
  const rd = filters["report_date"];
  return typeof rd === "string" ? rd : undefined;
}

export function adaptCashflowProjection(input: AdaptCashflowInput): CashflowAdapterOutput {
  const state = deriveState(input.envelope, input.isLoading, input.isError);
  const envelope = input.envelope;
  if (!envelope || state.kind === "loading" || state.kind === "error") {
    return { vm: null, state, meta: envelope?.result_meta ?? null };
  }
  const p = envelope.result;
  const vm: CashflowProjectionVM = {
    reportDate: p.report_date,
    kpis: {
      durationGap: p.duration_gap,
      assetDuration: p.asset_duration,
      liabilityDuration: p.liability_duration,
      equityDuration: p.equity_duration,
      rateSensitivity1bp: p.rate_sensitivity_1bp,
      reinvestmentRisk12m: p.reinvestment_risk_12m,
    },
    monthlyBuckets: p.monthly_buckets.map(mapBucket),
    topMaturingAssets: p.top_maturing_assets_12m.map(mapAsset),
    warnings: p.warnings ?? [],
  };
  return { vm, state, meta: envelope.result_meta };
}
