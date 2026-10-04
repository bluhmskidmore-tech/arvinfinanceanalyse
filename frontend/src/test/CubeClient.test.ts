import { describe, expect, it, vi } from "vitest";

import { createRealCubeClient } from "../api/cubeClient";

describe("Cube client safety contract", () => {
  it("preserves an explicit analysis basis and single-value filters", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ rows: [] })));
    const client = createRealCubeClient({ fetchImpl, baseUrl: "" });
    const request = {
      report_date: "2026-03-31", fact_table: "balance", basis: "analytical" as const,
      measures: ["sum(market_value)"], filters: { currency_basis: ["CNY"] },
    };
    await client.executeCubeQuery(request);
    expect(JSON.parse(fetchImpl.mock.calls[0]![1]!.body as string)).toEqual(request);
  });

  it("surfaces structured 503 detail without replacing it with sample rows", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ detail: "Cube formal use is not promoted" }), { status: 503 }));
    const client = createRealCubeClient({ fetchImpl, baseUrl: "" });
    await expect(client.executeCubeQuery({ report_date: "2026-03-31", fact_table: "balance", measures: ["sum(market_value)"] }))
      .rejects.toMatchObject({ message: "Cube formal use is not promoted", status: 503 });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
