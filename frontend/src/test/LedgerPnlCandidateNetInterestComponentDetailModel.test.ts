import { describe, expect, it } from "vitest";

import { buildCandidateNetInterestComponentDetailViewModel } from "../features/ledger-pnl/models/candidateNetInterestComponentDetailModel";
import { buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail } from "../mocks/ledgerPnlMocks";

describe("candidate net-interest component detail model", () => {
  it("fails closed instead of throwing for a runtime metric outside the fixed bridge", () => {
    const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );
    payload.metric_id = "income.interest.investment.extra" as never;

    expect(() => buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment.extra" as never,
      "b".repeat(64),
    )).not.toThrow();
    expect(buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment.extra" as never,
      "b".repeat(64),
    )).toMatchObject({ state: "invalid_contract", rows: [] });
  });

  it("accepts a stale parent only when the response exposes a different valid parent key", () => {
    const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );
    Object.assign(payload, {
      status: "stale_parent",
      quality_status: "not_evaluable",
      foot_status: "not_evaluable",
      parent_idempotency_key: "c".repeat(64),
      parent_current_value_yi: null,
      parent_previous_value_yi: null,
      parent_component_delta_yi: null,
      parent_contribution_to_net_delta_yi: null,
      account_current_total_yi: null,
      account_previous_total_yi: null,
      account_component_delta_total_yi: null,
      account_contribution_total_yi: null,
      current_reconciliation_yi: null,
      previous_reconciliation_yi: null,
      component_delta_reconciliation_yi: null,
      contribution_reconciliation_yi: null,
      reasons: ["parent_idempotency_key_mismatch"],
      rows: [],
    });

    expect(buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    )).toMatchObject({
      state: "stale_parent",
      rows: [],
    });
  });

  it("consumes backend Decimal strings without deriving official amounts in JavaScript", () => {
    const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );
    Object.assign(payload, {
      parent_current_value_yi: "12345678901234567890.123456789",
      parent_previous_value_yi: "12345678901234567889.000000000",
      parent_component_delta_yi: "1.123456789",
      parent_contribution_to_net_delta_yi: "1.123456789",
      account_current_total_yi: "12345678901234567890.123456789",
      account_previous_total_yi: "12345678901234567889.000000000",
      account_component_delta_total_yi: "1.123456789",
      account_contribution_total_yi: "1.123456789",
      current_reconciliation_yi: "0",
      previous_reconciliation_yi: "0",
      component_delta_reconciliation_yi: "0",
      contribution_reconciliation_yi: "0",
    });

    const model = buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );

    expect(model.state).toBe("available");
    if (model.state !== "available") {
      throw new Error(`expected available detail, received ${model.state}`);
    }
    expect(model.summary.componentDeltaDisplay).toBe("1.1235");
    expect(model.summary.contributionDisplay).toBe("1.1235");
  });
});
