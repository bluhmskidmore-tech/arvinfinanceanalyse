import { describe, expect, it, vi } from "vitest";

import { getReturnDecompositionContext } from "./dashboardApi";

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
