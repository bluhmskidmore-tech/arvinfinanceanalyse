import { expect, it, vi } from "vitest";

const mockModule = vi.hoisted(() => ({ importCount: 0 }));

vi.mock("./mockApiClient", async (importOriginal) => {
  mockModule.importCount += 1;
  return importOriginal();
});

it("loads the mock composition only when a client method is invoked", async () => {
  const { createApiClient } = await import("./client");
  const client = createApiClient({ mode: "mock" });
  const keys = Object.keys(client);
  const copy = { ...client };

  expect(client.mode).toBe("mock");
  expect(keys).toContain("getHealth");
  expect(Object.keys(copy)).toEqual(keys);
  expect(typeof copy.getHealth).toBe("function");

  // Flush any dynamic import started by construction or enumeration.
  await vi.dynamicImportSettled();
  expect(mockModule.importCount).toBe(0);

  await expect(Promise.all([client.getHealth(), client.getHealthLive()]))
    .resolves.toEqual([{ status: "ok" }, { status: "ok" }]);
  expect(mockModule.importCount).toBe(1);
});
