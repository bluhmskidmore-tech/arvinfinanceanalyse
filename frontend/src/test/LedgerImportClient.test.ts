import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { createRealLedgerClient, LedgerRequestError } from "../api/ledgerClient";

describe("Ledger import client", () => {
  it("stays exposed through the ApiClient composition boundary", () => {
    const client = createApiClient({ mode: "mock" });

    expect(client.importLedger).toBeTypeOf("function");
    expect(client.getLedgerImportStatus).toBeTypeOf("function");
  });

  it("uploads the selected file as multipart data and preserves the queued run", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 202,
      json: async () => ({
        data: {
          status: "queued",
          run_id: "ledger_import:run 1",
          file_name: "ledger.xlsx",
        },
        trace: {
          request_id: "req_ledger_import",
          run_id: "ledger_import:run 1",
        },
      }),
    }));
    const client = createRealLedgerClient({
      fetchImpl: fetchMock as unknown as typeof fetch,
      baseUrl: "http://localhost:8000",
    });
    const file = new File(["ledger"], "ledger.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await expect(client.importLedger(file)).resolves.toMatchObject({
      data: {
        status: "queued",
        run_id: "ledger_import:run 1",
        file_name: "ledger.xlsx",
      },
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/ledger/import");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ Accept: "application/json" });
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("encodes run_id when reading import status", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        data: {
          status: "succeeded",
          run_id: "ledger_import:run/1",
          file_name: "ledger.xlsx",
          batch_id: 9,
          finished_at: "2026-07-11T04:00:00Z",
        },
        trace: {
          request_id: "req_ledger_status",
          run_id: "ledger_import:run/1",
        },
      }),
    }));
    const client = createRealLedgerClient({
      fetchImpl: fetchMock as unknown as typeof fetch,
      baseUrl: "http://localhost:8000",
    });

    const controller = new AbortController();
    await expect(
      client.getLedgerImportStatus("ledger_import:run/1", controller.signal),
    ).resolves.toMatchObject({
      data: { status: "succeeded", batch_id: 9 },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/ledger/import-status?run_id=ledger_import%3Arun%2F1",
      expect.objectContaining({
        headers: { Accept: "application/json" },
        signal: controller.signal,
      }),
    );
  });

  it("keeps backend error code and HTTP status distinguishable", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({
        error: {
          code: "LEDGER_READ_FORBIDDEN",
          message: "Ledger read access denied.",
          retryable: false,
        },
      }),
    }));
    const client = createRealLedgerClient({
      fetchImpl: fetchMock as unknown as typeof fetch,
      baseUrl: "http://localhost:8000",
    });

    const error = await client.getLedgerImportStatus("ledger_import:denied").catch((reason) => reason);

    expect(error).toBeInstanceOf(LedgerRequestError);
    expect(error).toMatchObject({
      code: "LEDGER_READ_FORBIDDEN",
      status: 403,
      retryable: false,
    });
  });
  it("sends normalized currency to positions and export", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ data: { items: [], page: 1, page_size: 20, total: 0 }, metadata: {}, trace: {} }),
      blob: async () => new Blob(["xlsx"]),
    }));
    const client = createRealLedgerClient({ fetchImpl: fetchMock as unknown as typeof fetch, baseUrl: "http://localhost:8000" });
    await client.getLedgerPositions({ asOfDate: "2026-03-17", currency: " usd ", direction: "UNCLASSIFIED", page: 1, pageSize: 20 });
    await client.exportLedgerPositions({ asOfDate: "2026-03-17", currency: " usd ", direction: "UNCLASSIFIED" });
    const calls = fetchMock.mock.calls as unknown as Array<[string, RequestInit?]>;
    expect(calls[0][0]).toContain("currency=USD");
    expect(calls[0][0]).toContain("direction=UNCLASSIFIED");
    expect(calls[1][0]).toContain("currency=USD");
    expect(calls[1][0]).toContain("direction=UNCLASSIFIED");
  });
});
