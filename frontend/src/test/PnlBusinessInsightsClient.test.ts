import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("pnl by-business approved insights client", () => {
  it("requests the formal insights endpoint with year and exact cutoff", async () => {
    const payload = { result_meta: {}, result: {} };
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await expect(client.getPnlByBusinessInsights(2026, "2026-06-30")).resolves.toEqual(payload);

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/pnl/by-business-insights?year=2026&as_of_date=2026-06-30",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("keeps empty mock concentration unavailable instead of fabricating zero metrics", async () => {
    const client = createApiClient({ mode: "mock" });

    const envelope = await client.getPnlByBusinessInsights(2026, "2026-06-30");

    expect(envelope.result.concentration.total_avg_balance).toBeNull();
    expect(envelope.result.concentration.hhi_pct).toBeNull();
    expect(envelope.result.concentration.top_n_share_pct).toBeNull();
  });

  it("clamps a leap-day cutoff to the prior year's valid same-period date", async () => {
    const client = createApiClient({ mode: "mock" });

    const envelope = await client.getPnlByBusinessInsights(2024, "2024-02-29");

    expect(envelope.result.baseline_requested_report_date).toBe("2023-02-28");
  });
});
