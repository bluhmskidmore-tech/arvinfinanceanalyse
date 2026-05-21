import type { Query } from "@tanstack/react-query";

import type { ApiEnvelope, ResultMeta } from "../api/contracts";
import {
  EXTERNAL_REFRESH_INTERVALS_MS,
  externalDataQueryOptions,
  externalDataRefetchInterval,
} from "./externalDataRefreshPolicy";

function resultMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_refresh_policy_test",
    basis: "analytical",
    result_kind: "market_data.test",
    formal_use_allowed: false,
    source_version: "sv_refresh_policy_test",
    vendor_version: "vv_refresh_policy_test",
    rule_version: "rv_refresh_policy_test",
    cache_version: "cv_refresh_policy_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-05-21T09:00:00Z",
    ...partial,
  };
}

function envelope(meta: ResultMeta): ApiEnvelope<{ ok: true }> {
  return {
    result_meta: meta,
    result: { ok: true },
  };
}

function queryFor(
  data: unknown,
  fetchFailureCount = 0,
): Query<unknown, Error, unknown, readonly unknown[]> {
  return {
    state: {
      data,
      fetchFailureCount,
    },
  } as Query<unknown, Error, unknown, readonly unknown[]>;
}

describe("externalDataRefreshPolicy", () => {
  it("keeps stable/date-slice data on long cache with no automatic polling", () => {
    const point = {
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      quality_flag: "ok",
    };
    const query = queryFor(envelope(resultMeta()), 0);

    expect(externalDataRefetchInterval(query, point)).toBe(false);
    expect(externalDataQueryOptions(point).staleTime).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.stableStaleTime,
    );
    expect(externalDataQueryOptions(point).refetchIntervalInBackground).toBe(false);
  });

  it("polls stale or latest-snapshot data while the page is visible", () => {
    const staleMeta = resultMeta({ vendor_status: "vendor_stale" });
    const fallbackMeta = resultMeta({ fallback_mode: "latest_snapshot" });

    expect(externalDataRefetchInterval(queryFor(envelope(staleMeta)))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview,
    );
    expect(externalDataRefetchInterval(queryFor(envelope(fallbackMeta)))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview,
    );
  });

  it("uses a long interval for vendor unavailable data", () => {
    const unavailableMeta = resultMeta({ vendor_status: "vendor_unavailable" });

    expect(externalDataRefetchInterval(queryFor(envelope(unavailableMeta)))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.unavailableReview,
    );
  });

  it("backs off repeated failed stale refreshes exponentially", () => {
    const staleMeta = resultMeta({ quality_flag: "stale" });

    expect(externalDataRefetchInterval(queryFor(envelope(staleMeta), 1))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview * 2,
    );
    expect(externalDataRefetchInterval(queryFor(envelope(staleMeta), 2))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview * 4,
    );
    expect(externalDataRefetchInterval(queryFor(envelope(staleMeta), 9))).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.maxBackoff,
    );
  });

  it("derives freshness from section-level metadata when mixed payloads share a page", () => {
    const stablePoint = { refresh_tier: "stable", fetch_mode: "date_slice" };
    const stalePoint = { refresh_tier: "fallback", quality_flag: "warning" };

    expect(externalDataRefetchInterval(queryFor(envelope(resultMeta())), stablePoint)).toBe(false);
    expect(externalDataRefetchInterval(queryFor(envelope(resultMeta())), stalePoint)).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview,
    );
  });

  it("polls fallback latest sections even when the result meta is otherwise healthy", () => {
    const fallbackLatestPoint = { refresh_tier: "fallback", fetch_mode: "latest" };

    expect(externalDataRefetchInterval(queryFor(envelope(resultMeta())), fallbackLatestPoint)).toBe(
      EXTERNAL_REFRESH_INTERVALS_MS.staleReview,
    );
  });
});
