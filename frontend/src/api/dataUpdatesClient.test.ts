import { describe, expect, it, vi } from "vitest";

import { createDataUpdatesClient } from "./dataUpdatesClient";

describe("data update client", () => {
  it("sends an explicit date and idempotency key without accepting a command", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      run_id: "run-1", report_date: "2026-08-31", workflow: "core_financial", status: "queued", message: "已受理。",
      updated_at: "2026-09-01T00:00:00Z", steps: [],
    }), { status: 202 }));
    const api = createDataUpdatesClient({ baseUrl: "http://fixture", fetchImpl });
    await api.requestCore("2026-08-31", true, "same-request");
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("http://fixture/api/data-updates/core");
    expect(init.headers["Idempotency-Key"]).toBe("same-request");
    expect(JSON.parse(init.body)).toEqual({ report_date: "2026-08-31", wait_for_inputs: true, workflow: "core_financial" });
  });

  it("rejects malformed overview data instead of rendering it as success", async () => {
    const api = createDataUpdatesClient({ fetchImpl: vi.fn().mockResolvedValue(new Response("{}")) });
    await expect(api.overview()).rejects.toThrow("runs");
  });

  it("rejects malformed nested dates and permissions before the page renders", async () => {
    const payload = {
      runs: [], financial_dates: [null], schedule: { tasks: [] }, steps: [], input_directory: "F:/fixture",
      permissions: { core: true, balance: "false", market: true },
    };
    const api = createDataUpdatesClient({ fetchImpl: vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))) });
    await expect(api.overview()).rejects.toThrow(/permissions.balance|financial_dates\[0\]/);
  });

  it("keeps historical core requests without a workflow field readable", async () => {
    const payload = {
      runs: [{ run_id: "old-core", report_date: "2026-08-31", status: "failed",
        updated_at: "2026-09-01T00:00:00Z", message: "旧请求失败", steps: [] }],
      financial_dates: [], schedule: { status: "available", detail: "已启用", tasks: [] },
      steps: [], input_directory: "F:/fixture", permissions: { core: true, market: false },
    };
    const api = createDataUpdatesClient({ fetchImpl: vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))) });
    await expect(api.overview()).resolves.toMatchObject({ runs: [{ run_id: "old-core" }] });
  });

  it("rejects malformed preflight checks before offering an update", async () => {
    const payload = { report_date: "2026-08-31", workflow: "balance_daily", ready: true,
      input_directory: "F:/fixture", checks: [null] };
    const api = createDataUpdatesClient({ fetchImpl: vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))) });
    await expect(api.preflight("2026-08-31", "balance_daily")).rejects.toThrow("checks[0]");
  });

  it("rejects an accepted response without a request receipt", async () => {
    const api = createDataUpdatesClient({ fetchImpl: vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "queued" }), { status: 202 }),
    ) });
    await expect(api.requestCore("2026-08-31", false, "receipt-required")).rejects.toThrow("run_id");
  });

  it("preserves an actionable backend error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "该报告日的文件尚未到齐。" }), { status: 409 }));
    const api = createDataUpdatesClient({ fetchImpl });
    await expect(api.requestCore("2026-08-31", false, "retry-key")).rejects.toThrow("尚未到齐");
  });
});
