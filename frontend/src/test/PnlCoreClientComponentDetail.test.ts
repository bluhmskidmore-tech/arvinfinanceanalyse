import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import type { LedgerPnlCandidateFinancialIndicatorComponentMetricId } from "../api/contracts";

describe("candidate financial indicator component detail client", () => {
  it("returns the requested synthetic component detail in demo mode", async () => {
    const client = createApiClient({ mode: "mock" });
    const comparison = await client.getLedgerPnlCandidateFinancialIndicatorPeriodComparison(
      "202606",
    );

    const response = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      comparison.idempotency_key,
    );

    expect(response).toMatchObject({
      contract_version: "candidate-financial-indicator-component-detail-v1",
      report_month: "202606",
      metric_id: "income.interest.investment",
      parent_idempotency_key: comparison.idempotency_key,
      status: "available",
    });
    expect(response.rows[0]).toMatchObject({
      account_code: "51402010003",
      effective_component_weight: "-1",
      effective_net_weight: "-1",
      contribution_to_net_delta_yi: "-1.3160266974",
      matched_terms: [{ source: "ledger", level: "l1", code: "514", weight: "-1" }],
    });
  });

  it("keeps all four demo details compatible with the frozen direct rules", async () => {
    const client = createApiClient({ mode: "mock" });
    const parentKey = "d".repeat(64);
    const cases = [
      ["income.interest.loan.total", /^(501|50206)/, "-1", "-1", "501", "-1"],
      ["expense.interest.deposit.total", /^521/, "1", "-1", "521", "1"],
      ["income.interest.investment", /^514/, "-1", "-1", "514", "-1"],
      ["income.interest.interbank_net", /^(502(?!06)|522|523)/, "-1", "-1", "522", "-1"],
    ] as const;

    for (const [metricId, accountPattern, componentWeight, netWeight, termCode, termWeight] of cases) {
      const detail = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
        "202606",
        metricId,
        parentKey,
      );
      expect(detail.rows[0].account_code).toMatch(accountPattern);
      expect(detail.rows[0]).toMatchObject({
        row_status: "contributing",
        effective_component_weight: componentWeight,
        effective_net_weight: netWeight,
        matched_terms: [expect.objectContaining({ code: termCode, weight: termWeight })],
      });
    }
  });

  it("binds demo detail idempotency keys to the metric and parent key", async () => {
    const client = createApiClient({ mode: "mock" });
    const investment = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "a".repeat(64),
    );
    const loan = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.loan.total",
      "a".repeat(64),
    );
    const changedParent = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );

    expect(new Set([
      investment.idempotency_key,
      loan.idempotency_key,
      changedParent.idempotency_key,
    ]).size).toBe(3);
  });

  it("binds the normalized query and AbortSignal to the direct-response endpoint", async () => {
    const directResponse = { idempotency_key: "e".repeat(64) };
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
    const parentKey = "d".repeat(64);

    const response = await client.getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      " 202606 ",
      " income.interest.investment " as unknown as LedgerPnlCandidateFinancialIndicatorComponentMetricId,
      ` ${parentKey} `,
      { signal: controller.signal },
    );

    expect(response).toEqual(directResponse);
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail?report_month=202606&metric_id=income.interest.investment&parent_idempotency_key=${parentKey}`,
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
        signal: controller.signal,
      }),
    );
  });
});
