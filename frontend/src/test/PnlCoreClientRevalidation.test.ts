import { describe, expect, it, vi } from "vitest";

import {
  createDemoPnlCoreClient,
  createRealPnlCoreClient,
  type PnlCoreClientFactoryOptions,
} from "../api/pnlCoreClient";

describe("PnL core candidate revalidation client", () => {
  it("fails explicitly instead of inventing a persisted-looking demo receipt", async () => {
    const client = createDemoPnlCoreClient(async () => undefined);

    await expect(client.revalidateLedgerPnlCandidateFinancialIndicators("202606", {
      base_candidate_idempotency_key: "a".repeat(64),
      base_evidence_pack_key: "b".repeat(64),
      manual_overrides: {},
    })).rejects.toThrow("requires the real API client");
  });

  it("posts the strict dry-run request with the report month in the query", async () => {
    const receipt = { contract_version: "candidate-financial-indicator-revalidation-v1" };
    const requestActionJson = vi.fn(async () => receipt);
    const client = createRealPnlCoreClient({
      fetchImpl: vi.fn() as unknown as typeof fetch,
      baseUrl: "http://localhost:8000",
      requestJson: vi.fn(),
      requestActionJson,
    } as unknown as PnlCoreClientFactoryOptions);
    const request = {
      base_candidate_idempotency_key: "a".repeat(64),
      base_evidence_pack_key: "b".repeat(64),
      manual_overrides: {
        "input.adjustment.noninterest.r010": {
          value_yi: "0",
          submitted_evidence_refs: ["voucher://202606/r010"],
        },
      },
    };

    await expect(
      client.revalidateLedgerPnlCandidateFinancialIndicators(" 202606 ", request),
    ).resolves.toBe(receipt);
    expect(requestActionJson).toHaveBeenCalledWith(
      expect.any(Function),
      "http://localhost:8000",
      "/api/ledger-pnl/candidate-financial-indicators/revalidate?report_month=202606",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
    );
  });
});
