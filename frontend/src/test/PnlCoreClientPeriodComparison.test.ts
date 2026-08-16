import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

describe("candidate financial indicator period comparison client", () => {
  it("returns deterministic synthetic comparison data in demo mode", async () => {
    const client = createApiClient({ mode: "mock" });

    const response = await client.getLedgerPnlCandidateFinancialIndicatorPeriodComparison(
      "202606",
    );

    expect(response).toMatchObject({
      contract_version: "candidate-financial-indicator-period-comparison-v2",
      report_month: "202606",
      comparison_month: "202605",
      two_month_prior: "202604",
      overall_status: "partial",
      metric_status: "candidate",
      formal_use_allowed: false,
      net_interest_component_bridge: {
        status: "available",
        foot_status: "passed",
        net_delta_yi: "2.5000",
        reconciliation_delta_yi: "0.0000",
      },
    });
    expect(response.metrics).toHaveLength(7);
    expect(response.metrics.filter((item) => item.comparison_status === "comparable")).toHaveLength(5);
    const unavailableMetrics = response.metrics.filter(
      (item) => item.comparison_status === "not_comparable",
    );
    expect(unavailableMetrics).toHaveLength(2);
    for (const metric of unavailableMetrics) {
      expect(metric).toMatchObject({
        current_metric_status: "warning",
        previous_metric_status: "warning",
        two_month_prior_metric_status: "warning",
        rate_reason: "metric_status_not_ok",
      });
      expect(metric.current_source_value_yi).not.toBeNull();
      expect(metric.previous_source_value_yi).not.toBeNull();
      expect(metric.two_month_prior_source_value_yi).not.toBeNull();
      expect(metric.reasons).toEqual(expect.arrayContaining([
        "current:status=warning",
        "previous:manual_required_not_supplied",
        "two_month_prior:status=warning",
      ]));
      expect(metric.reasons.some((reason) => reason.includes(":missing_account:"))).toBe(true);
      expect(metric.reasons.join(" ")).not.toContain("微贷");
    }
    expect(JSON.stringify(response)).not.toContain("57.3617558215");
  });

  it("calls the fixed direct-response endpoint with only the normalized report month", async () => {
    const directResponse = {
      contract_version: "candidate-financial-indicator-period-comparison-v1",
      report_month: "202606",
    };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(directResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });
    const controller = new AbortController();

    const response = await client.getLedgerPnlCandidateFinancialIndicatorPeriodComparison(
      " 202606 ",
      { signal: controller.signal },
    );

    expect(response).toEqual(directResponse);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/ledger-pnl/candidate-financial-indicators/period-comparison?report_month=202606",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
        signal: controller.signal,
      }),
    );
  });
});
