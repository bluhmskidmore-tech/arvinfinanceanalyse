import { describe, expect, it, vi } from "vitest";

import { createRealKpiClient } from "../api/kpiClient";

const BASE_URL = "http://kpi.test";

type FetchArgs = { url: string; init: RequestInit | undefined };

function jsonResponse(payload: unknown, ok = true, status = 200, text = ""): Response {
  return {
    ok,
    status,
    json: async () => payload,
    text: async () => text,
  } as unknown as Response;
}

function buildClient(payload: unknown = {}, ok = true, status = 200, text = "") {
  const calls: FetchArgs[] = [];
  const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return jsonResponse(payload, ok, status, text);
  });
  const client = createRealKpiClient({
    fetchImpl: fetchImpl as unknown as typeof fetch,
    baseUrl: BASE_URL,
  });
  return { client, calls };
}

describe("kpiClient read/write path contract", () => {
  it("reads values with owner/date/trace query params and passes the payload through", async () => {
    const payload = {
      owner_id: 7,
      owner_name: "固定收益部",
      as_of_date: "2025-12-31",
      metrics: [],
      total: 0,
    };
    const { client, calls } = buildClient(payload);

    const result = await client.getKpiValues({
      owner_id: 7,
      as_of_date: "2025-12-31",
      include_trace: true,
    });

    expect(calls).toHaveLength(1);
    expect(calls[0]!.url).toBe(
      `${BASE_URL}/api/kpi/values?owner_id=7&as_of_date=2025-12-31&include_trace=true`,
    );
    // 读路径不得携带 method（默认 GET）也不得携带 body
    expect(calls[0]!.init?.method).toBeUndefined();
    expect(calls[0]!.init?.body).toBeUndefined();
    expect(result).toEqual(payload);
  });

  it("omits undefined and empty query params instead of serializing them", async () => {
    const { client, calls } = buildClient({ metrics: [], total: 0 });

    await client.getKpiMetrics({ owner_id: undefined, year: 2026, is_active: true });
    await client.getKpiOwners();

    expect(calls[0]!.url).toBe(`${BASE_URL}/api/kpi/metrics?year=2026&is_active=true`);
    // 无参数时路径保持干净，不带问号
    expect(calls[1]!.url).toBe(`${BASE_URL}/api/kpi/owners`);
  });

  it("creates a metric value via POST /values with the exact JSON body", async () => {
    const { client, calls } = buildClient({
      value_id: 99,
      metric_id: 3,
      as_of_date: "2025-12-31",
      actual_value: "88.5",
      completion_ratio: null,
      progress_pct: null,
      score_value: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    await client.createKpiValue({
      metric_id: 3,
      as_of_date: "2025-12-31",
      actual_value: "88.5",
    });

    expect(calls[0]!.url).toBe(`${BASE_URL}/api/kpi/values`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]!.init?.body))).toEqual({
      metric_id: 3,
      as_of_date: "2025-12-31",
      actual_value: "88.5",
    });
  });

  it("updates via PUT /values/:id when value_id exists and falls back to POST create when missing", async () => {
    const { client, calls } = buildClient({
      value_id: 55,
      metric_id: 3,
      as_of_date: "2025-12-31",
      actual_value: "90",
      completion_ratio: null,
      progress_pct: null,
      score_value: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    await client.updateKpiValue(55, 3, "2025-12-31", { actual_value: "90" });
    await client.updateKpiValue(0, 3, "2025-12-31", { actual_value: "90" });

    // 已有 value_id：走 PUT，body 不重复 metric_id/as_of_date
    expect(calls[0]!.url).toBe(`${BASE_URL}/api/kpi/values/55`);
    expect(calls[0]!.init?.method).toBe("PUT");
    expect(JSON.parse(String(calls[0]!.init?.body))).toEqual({ actual_value: "90" });

    // 无 value_id：降级为 POST 新建，body 合并 metric_id 与 as_of_date
    expect(calls[1]!.url).toBe(`${BASE_URL}/api/kpi/values`);
    expect(calls[1]!.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[1]!.init?.body))).toEqual({
      metric_id: 3,
      as_of_date: "2025-12-31",
      actual_value: "90",
    });
  });

  it("batch-updates values via POST /values/batch with as_of_date and items", async () => {
    const { client, calls } = buildClient({ success_count: 1, failed_count: 0, errors: [] });

    const result = await client.batchUpdateKpiValues("2025-12-31", [
      { metric_id: 1, actual_value: "10" },
      { metric_id: 2, progress_pct: "50" },
    ]);

    expect(calls[0]!.url).toBe(`${BASE_URL}/api/kpi/values/batch`);
    expect(calls[0]!.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]!.init?.body))).toEqual({
      as_of_date: "2025-12-31",
      items: [
        { metric_id: 1, actual_value: "10" },
        { metric_id: 2, progress_pct: "50" },
      ],
    });
    expect(result.success_count).toBe(1);
  });

  it("throws the backend text on non-ok responses and falls back to a status message", async () => {
    const withText = buildClient({}, false, 500, "kpi backend exploded");
    await expect(
      withText.client.getKpiValues({ owner_id: 1, as_of_date: "2025-12-31" }),
    ).rejects.toThrow("kpi backend exploded");

    const withoutText = buildClient({}, false, 502, "");
    await expect(withoutText.client.getKpiOwners()).rejects.toThrow("KPI API 502");
  });
});
