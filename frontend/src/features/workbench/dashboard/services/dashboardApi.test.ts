import { describe, expect, it, vi } from "vitest";

import { getCampisiAttributionContext, getReturnDecompositionContext } from "./dashboardApi";

describe("dashboardApi return decomposition context", () => {
  it("keeps full detail by default and requests summary only when asked", async () => {
    const getBondAnalyticsReturnDecomposition = vi.fn(async () => ({
      result_meta: { result_kind: "bond_analytics.return_decomposition" },
      result: {},
    }));
    const client = {
      getBondAnalyticsReturnDecomposition,
    } as unknown as Parameters<typeof getReturnDecompositionContext>[0];

    await getReturnDecompositionContext(client, "2026-06-30");
    await getReturnDecompositionContext(client, "2026-06-30", { detail: "summary" });

    expect(getBondAnalyticsReturnDecomposition).toHaveBeenNthCalledWith(
      1,
      "2026-06-30",
      "MoM",
      {
        assetClass: "all",
        accountingClass: "all",
      },
    );
    expect(getBondAnalyticsReturnDecomposition).toHaveBeenNthCalledWith(
      2,
      "2026-06-30",
      "MoM",
      {
        assetClass: "all",
        accountingClass: "all",
        detail: "summary",
      },
    );
  });
});

describe("dashboardApi monthly Campisi context", () => {
  it.each([
    ["2026-08-31", "2026-07-31"],
    ["2026-04-30", "2026-03-31"],
    ["2026-02-28", "2026-01-31"],
    ["2024-02-29", "2024-01-31"],
    ["2026-01-31", "2025-12-31"],
  ])("uses the preceding month-end for report %s", async (endDate, startDate) => {
    const getPnlCampisiFourEffects = vi.fn(async () => ({}));
    const client = {
      getPnlCampisiFourEffects,
    } as unknown as Parameters<typeof getCampisiAttributionContext>[0];

    await getCampisiAttributionContext(client, endDate, { detail: "summary" });

    expect(getPnlCampisiFourEffects).toHaveBeenCalledWith({
      startDate,
      endDate,
      lookbackDays: 30,
      detail: "summary",
    });
  });
});
