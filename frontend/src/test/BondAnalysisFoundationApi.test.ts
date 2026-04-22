import { describe, expect, it, vi } from "vitest";

import type { OrderCreateRequest } from "../bond-analysis-foundation/data-structures/OrderModel";
import { ApiError, buildRealtimeStreamUrl, createBondApiService } from "../bond-analysis-foundation/react-components/services/api";

describe("bond-analysis foundation api service", () => {
  it("serializes bond query filters, sorting, and pagination for GET /api/bonds", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        items: [],
        total: 0,
        page: 2,
        pageSize: 50,
      }),
    }));

    const service = createBondApiService({
      baseUrl: "https://api.example.com",
      fetcher: fetchMock as unknown as typeof fetch,
    });

    await service.getBonds({
      query: "国开债",
      page: 2,
      pageSize: 50,
      sortBy: "yieldToMaturity",
      sortOrder: "desc",
      issuerTypes: ["policy_bank"],
      ratings: ["AAA"],
      markets: ["CIBM"],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const firstCall = fetchMock.mock.calls[0] as unknown[] | undefined;

    expect(firstCall).toBeDefined();

    const requestUrl = firstCall?.at(0);
    const requestInit = firstCall?.at(1);
    const url = new URL(String(requestUrl));

    expect(url.origin).toBe("https://api.example.com");
    expect(url.pathname).toBe("/api/bonds");
    expect(url.searchParams.get("query")).toBe("国开债");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("pageSize")).toBe("50");
    expect(url.searchParams.get("sortBy")).toBe("yieldToMaturity");
    expect(url.searchParams.get("sortOrder")).toBe("desc");
    expect(url.searchParams.getAll("issuerTypes")).toEqual(["policy_bank"]);
    expect(url.searchParams.getAll("ratings")).toEqual(["AAA"]);
    expect(url.searchParams.getAll("markets")).toEqual(["CIBM"]);
    expect(requestInit).toEqual(
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
  });

  it("posts order payloads to POST /api/orders and returns the created order", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        orderId: "ORD-1001",
        bondCode: "240210",
        side: "BUY",
        quantity: 1000000,
        price: 101.25,
        feeAmount: 1250,
        status: "PENDING",
        createdAt: "2026-04-21T09:30:00Z",
      }),
    }));

    const service = createBondApiService({
      baseUrl: "https://api.example.com",
      fetcher: fetchMock as unknown as typeof fetch,
    });
    const payload: OrderCreateRequest = {
      bondCode: "240210",
      side: "BUY",
      quantity: 1000000,
      price: 101.25,
      feeAmount: 1250,
      orderType: "LIMIT",
      traderId: "TRADER-01",
    };

    const order = await service.createOrder(payload);

    expect(order.orderId).toBe("ORD-1001");

    const firstCall = fetchMock.mock.calls[0] as unknown[] | undefined;

    expect(firstCall).toBeDefined();
    const requestInit = firstCall?.at(1);
    expect(requestInit).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("raises ApiError when the backend returns a non-ok response", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 429,
      json: async () => ({
        message: "rate limit exceeded",
      }),
    }));

    const service = createBondApiService({
      baseUrl: "https://api.example.com",
      fetcher: fetchMock as unknown as typeof fetch,
    });

    await expect(service.getOrders()).rejects.toBeInstanceOf(ApiError);
  });

  it("builds websocket urls from an https api base", () => {
    const url = buildRealtimeStreamUrl("https://api.example.com", "bond-prices", {
      portfolioId: "PF-001",
      watchlistId: "WL-core",
    });

    expect(url).toBe(
      "wss://api.example.com/live/bond-prices?portfolioId=PF-001&watchlistId=WL-core",
    );
  });
});
