import { describe, expect, it, vi } from "vitest";

import { createDeferredApiClient } from "../api/clientContext";

vi.mock("../api/client", () => {
  throw new Error("Positions and risk reads must not load the full API composition");
});

describe("positions and risk deferred domain clients", () => {
  it("preserves all page and drill requests without loading unrelated clients", async () => {
    const envelope = { result_meta: { basis: "analytical", formal_use_allowed: false }, result: {} };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(envelope)));
    const client = createDeferredApiClient({ mode: "real", baseUrl: "https://backend.test/", fetchImpl });
    const responses = await Promise.all([
      client.getPositionsBondSubTypes("2026-01-31"),
      client.getPositionsBondsList({ reportDate: "2026-01-31", page: 2, pageSize: 20 }),
      client.getPositionsCounterpartyBonds({ startDate: "2026-01-01", endDate: "2026-01-31", topN: 50, page: 1, pageSize: 50 }),
      client.getPositionsInterbankProductTypes("2026-01-31"),
      client.getPositionsInterbankList({ reportDate: "2026-01-31", page: 1, pageSize: 20, direction: "Asset" }),
      client.getPositionsCounterpartyInterbankSplit({ startDate: "2026-01-01", endDate: "2026-01-31", topN: 50 }),
      client.getPositionsStatsRating({ startDate: "2026-01-01", endDate: "2026-01-31" }),
      client.getPositionsStatsIndustry({ startDate: "2026-01-01", endDate: "2026-01-31", topN: 10 }),
      client.getPositionsCustomerDetails({ customerName: "客户甲", reportDate: "2026-01-31" }),
      client.getPositionsCustomerTrend({ customerName: "客户甲", endDate: "2026-01-31", days: 30 }),
      client.getRiskTensorDates(),
      client.getRiskTensor("2026-01-31"),
      client.getRiskScenarioStress("2026-01-31"),
    ]);
    expect(responses).toEqual(Array.from({ length: 13 }, () => envelope));
    expect(fetchImpl).toHaveBeenCalledTimes(13);
    const requests = fetchImpl.mock.calls as unknown as [string, RequestInit][];
    const urls = requests.map(([url]) => new URL(url));
    expect(urls.map((url) => url.pathname)).toEqual([
      "/api/positions/bonds/sub_types", "/api/positions/bonds", "/api/positions/counterparty/bonds",
      "/api/positions/interbank/product_types", "/api/positions/interbank", "/api/positions/counterparty/interbank/split",
      "/api/positions/stats/rating", "/api/positions/stats/industry", "/api/positions/customer/details",
      "/api/positions/customer/trend", "/api/risk/tensor/dates", "/api/risk/tensor", "/api/risk/scenario-stress",
    ]);
    expect(urls.every((url) => url.origin === "https://backend.test")).toBe(true);
    expect(urls[1].searchParams.get("page")).toBe("2");
    expect(urls[2].searchParams.get("top_n")).toBe("50");
    expect(urls[8].searchParams.get("customer_name")).toBe("客户甲");
    expect(urls[11].searchParams.get("report_date")).toBe("2026-01-31");
    expect(requests.every(([, init]) => new Headers(init.headers).get("Accept") === "application/json")).toBe(true);
  });

  it("retains transport errors instead of returning mock data", async () => {
    const client = createDeferredApiClient({ mode: "real", fetchImpl: vi.fn(async () => new Response("unavailable", { status: 503 })) });
    await expect(client.getRiskTensor("2026-01-31")).rejects.toThrow("503");
    await expect(client.getPositionsBondSubTypes("2026-01-31")).rejects.toThrow("503");
  });

  it("uses the existing domain fixtures in explicit mock mode", async () => {
    const fetchImpl = vi.fn(() => { throw new Error("Mock reads must not fetch"); });
    const client = createDeferredApiClient({ mode: "mock", fetchImpl });
    const positions = await client.getPositionsBondsList({ reportDate: "2025-12-31", page: 1, pageSize: 20 });
    const risk = await client.getRiskTensorDates();
    expect(positions.result_meta).toMatchObject({ basis: "analytical", formal_use_allowed: false });
    expect(risk.result.report_dates.length).toBeGreaterThan(0);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
