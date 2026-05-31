import { afterEach, describe, expect, it, vi } from "vitest";

async function loadRoutes() {
  vi.resetModules();
  return import("../router/routes");
}

describe("Equity prototype route gating", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("does not register the public prototype route by default", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_DATA_SOURCE", "real");

    const { workbenchRoutes } = await loadRoutes();

    expect(
      workbenchRoutes.some((route) => route.path === "/prototype/equity-cockpit"),
    ).toBe(false);
  });

  it("registers the prototype route only for explicit dev mock sessions", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_DATA_SOURCE", "mock");

    const { workbenchRoutes } = await loadRoutes();

    expect(
      workbenchRoutes.some((route) => route.path === "/prototype/equity-cockpit"),
    ).toBe(true);
  });
});
