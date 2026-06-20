import type { Query, QueryKey, RefetchOptions } from "@tanstack/react-query";

import type { ApiEnvelope, ResultMeta } from "../api/contracts";

type FreshnessMeta = Pick<
  ResultMeta,
  "vendor_status" | "fallback_mode" | "quality_flag" | "as_of_date"
>;

type ExternalRefreshSignal = {
  refresh_tier?: "stable" | "fallback" | "isolated" | string | null;
  fetch_mode?: "date_slice" | "latest" | string | null;
  quality_flag?: ResultMeta["quality_flag"] | string | null;
};

export const EXTERNAL_REFRESH_INTERVALS_MS = {
  stableStaleTime: 30 * 60 * 1000,
  defaultStaleTime: 5 * 60 * 1000,
  staleReview: 3 * 60 * 1000,
  unavailableReview: 30 * 60 * 1000,
  maxBackoff: 60 * 60 * 1000,
} as const;

export const nonCancellingRefetchOptions: RefetchOptions = {
  cancelRefetch: false,
};

function isApiEnvelope(value: unknown): value is ApiEnvelope<unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    "result_meta" in value &&
    typeof (value as { result_meta?: unknown }).result_meta === "object"
  );
}

export function readFreshnessMeta(value: unknown): FreshnessMeta | undefined {
  if (isApiEnvelope(value)) {
    return value.result_meta;
  }
  if (typeof value === "object" && value !== null && "result_meta" in value) {
    const meta = (value as { result_meta?: unknown }).result_meta;
    if (typeof meta === "object" && meta !== null) {
      return meta as FreshnessMeta;
    }
  }
  return undefined;
}

export function externalDataRefetchInterval<
  TQueryFnData,
  TData,
  TQueryKey extends QueryKey,
>(
  query: Query<TQueryFnData, Error, TData, TQueryKey>,
  sectionSignal?: ExternalRefreshSignal | null,
): number | false {
  const meta = readFreshnessMeta(query.state.data);
  const status = meta?.vendor_status;
  const fallbackMode = meta?.fallback_mode;
  const quality = sectionSignal?.quality_flag ?? meta?.quality_flag;
  if (status === "vendor_unavailable") {
    return applyFailureBackoff(EXTERNAL_REFRESH_INTERVALS_MS.unavailableReview, query);
  }

  if (
    status === "vendor_stale" ||
    fallbackMode === "latest_snapshot" ||
    quality === "stale" ||
    quality === "warning"
  ) {
    return applyFailureBackoff(EXTERNAL_REFRESH_INTERVALS_MS.staleReview, query);
  }

  return false;
}

export function externalDataQueryOptions(
  sectionSignal?: ExternalRefreshSignal | null,
) {
  const stableDateSlice =
    (sectionSignal?.refresh_tier ?? "stable") === "stable" &&
    (sectionSignal?.fetch_mode ?? "date_slice") === "date_slice";

  return {
    staleTime: stableDateSlice
      ? EXTERNAL_REFRESH_INTERVALS_MS.stableStaleTime
      : EXTERNAL_REFRESH_INTERVALS_MS.defaultStaleTime,
    refetchInterval: <TQueryFnData, TData, TQueryKey extends QueryKey>(
      query: Query<TQueryFnData, Error, TData, TQueryKey>,
    ) =>
      externalDataRefetchInterval(query, sectionSignal),
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  };
}

function applyFailureBackoff<
  TQueryFnData,
  TData,
  TQueryKey extends QueryKey,
>(
  baseIntervalMs: number,
  query: Query<TQueryFnData, Error, TData, TQueryKey>,
) {
  const failureCount = Math.max(0, query.state.fetchFailureCount);
  if (failureCount === 0) {
    return baseIntervalMs;
  }
  const multiplier = 2 ** Math.min(failureCount, 6);
  return Math.min(baseIntervalMs * multiplier, EXTERNAL_REFRESH_INTERVALS_MS.maxBackoff);
}
