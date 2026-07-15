import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("pnl by-business precompute client", () => {
  it("reads status and posts a controlled rebuild for the selected year", async () => {
    const payload = {
      year: 2025,
      status: "queued" as const,
      serving_mode: "live_fallback" as const,
      is_current: false,
      run_id: "pnl_by_business_precompute:test",
      report_date: null,
      latest_available_as_of_date: "2025-12-31",
      source_version: "sv_pnl_by_business_precompute_pending",
      rule_version: "rv_pnl_by_business_precompute_v6",
      queued_at: "2026-07-15T12:00:00Z",
      started_at: null,
      finished_at: null,
      generated_at: null,
      record_count: null,
      error_message: null,
      failure_category: null,
      trigger_reason: "manual_retry",
      retry_attempt: 0,
      retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
    };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await expect(client.getPnlByBusinessPrecomputeStatus(2025, "2025-06-30")).resolves.toEqual(payload);
    await expect(client.rebuildPnlByBusinessPrecompute(2025, "2025-06-30")).resolves.toEqual(payload);

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://backend.local/api/pnl/by-business/precompute-status?year=2025&as_of_date=2025-06-30",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://backend.local/api/pnl/by-business/precompute-rebuild?year=2025&as_of_date=2025-06-30",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });
});
