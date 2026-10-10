import { describe, expect, it } from "vitest";

import {
  buildCandidateNetInterestComponentDetailViewModel,
  filterCandidateNetInterestComponentDetailRows,
} from "../features/ledger-pnl/models/candidateNetInterestComponentDetailModel";
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

  it.each([
    ["0.0000004109", "<0.0001", "0.0000"],
    ["0.0000000757", "<0.0001", "0.0000"],
    ["-0.0000328143", ">−0.0001", "−0.0000"],
    ["-0.0000000004", ">−0.0001", "−0.0000"],
  ])(
    "keeps the real 202606 nonzero row contribution %s visible without changing summary precision",
    (contribution, expectedRowDisplay, expectedSummaryDisplay) => {
      const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
        "202606",
        "income.interest.investment",
        "b".repeat(64),
      );
      payload.parent_contribution_to_net_delta_yi = contribution;
      payload.account_contribution_total_yi = contribution;
      payload.rows[0].contribution_to_net_delta_yi = contribution;

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
      expect(model.summary.contributionDisplay).toBe(expectedSummaryDisplay);
      expect(model.rows[0].currentDisplay).toBe("−3.3160");
      expect(model.rows[0].contributionDisplay).toBe(expectedRowDisplay);
    },
  );

  it("keeps backend positions, raw Decimal strings, rules, and evidence on every row", () => {
    const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );
    const duplicateCodeRow = structuredClone(payload.rows[0]);
    duplicateCodeRow.account_name = "同代码的第二条后端记录";
    duplicateCodeRow.current_value_yi = "-999999999999999999.000000001";
    duplicateCodeRow.source_evidence[0].ending_yuan = duplicateCodeRow.current_ending_yuan;
    payload.rows.push(duplicateCodeRow);

    const model = buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );

    expect(model.state).toBe("available");
    if (model.state !== "available") throw new Error(`expected available, received ${model.state}`);
    expect(model.rows).toHaveLength(2);
    expect(model.rows.map((row) => row.backendPosition)).toEqual([1, 2]);
    expect(model.rows[1]).toMatchObject({
      accountCode: "51402010003",
      accountName: "同代码的第二条后端记录",
      currentValueYi: "-999999999999999999.000000001",
      effectiveComponentWeight: "-1",
      effectiveNetWeight: "-1",
    });
    expect(model.rows[1].matchedTerms).toEqual(duplicateCodeRow.matched_terms);
    expect(model.rows[1].sourceEvidence).toEqual(duplicateCodeRow.source_evidence);
  });

  it("filters by normalized text and row status without changing backend relative order", () => {
    const payload = buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );
    const offsetRow = structuredClone(payload.rows[0]);
    Object.assign(offsetRow, {
      row_status: "excluded_offset" as const,
      account_code: "51402010004",
      account_name: "规则 Offset 科目",
      effective_component_weight: "0",
      effective_net_weight: "0",
      current_value_yi: "0",
      previous_value_yi: "0",
      component_delta_yi: "0",
      contribution_to_net_delta_yi: "0",
      matched_terms: [{ source: "ledger" as const, level: "l1" as const, code: "514", weight: "-1" }],
    });
    const trailingRow = structuredClone(payload.rows[0]);
    trailingRow.account_code = "51402010005";
    trailingRow.account_name = "ALPHA 收益";
    payload.rows = [payload.rows[0], offsetRow, trailingRow];

    const model = buildCandidateNetInterestComponentDetailViewModel(
      payload,
      "202606",
      "income.interest.investment",
      "b".repeat(64),
    );

    expect(model.state).toBe("available");
    if (model.state !== "available") throw new Error(`expected available, received ${model.state}`);
    expect(filterCandidateNetInterestComponentDetailRows(model.rows, {
      query: "  alpha  ",
      status: "all",
    }).map((row) => row.backendPosition)).toEqual([3]);
    expect(filterCandidateNetInterestComponentDetailRows(model.rows, {
      query: "5140201",
      status: "contributing",
    }).map((row) => row.backendPosition)).toEqual([1, 3]);
    expect(filterCandidateNetInterestComponentDetailRows(model.rows, {
      query: "",
      status: "excluded_offset",
    }).map((row) => row.backendPosition)).toEqual([2]);
    expect(filterCandidateNetInterestComponentDetailRows(model.rows, {
      query: "   ",
      status: "all",
    }).map((row) => row.backendPosition)).toEqual([1, 2, 3]);
  });
});
