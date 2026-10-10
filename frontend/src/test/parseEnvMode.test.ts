import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { createDeferredApiClient } from "../api/clientContext";

describe("createApiClient · parseEnvMode", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  describe("explicit VITE_DATA_SOURCE", () => {
    it('returns mode "real" when VITE_DATA_SOURCE="real"', () => {
      vi.stubEnv("VITE_DATA_SOURCE", "real");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      const client = createApiClient();
      expect(client.mode).toBe("real");
    });

    it('returns mode "mock" when VITE_DATA_SOURCE="mock"', () => {
      vi.stubEnv("VITE_DATA_SOURCE", "mock");
      const client = createApiClient();
      expect(client.mode).toBe("mock");
    });

    it("is case-insensitive for explicit values", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "REAL");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      const client = createApiClient();
      expect(client.mode).toBe("real");
    });

    it("trims whitespace around explicit values", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "  real  ");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      const client = createApiClient();
      expect(client.mode).toBe("real");
    });
  });

  describe("dev / test mode (PROD=false) · unset VITE_DATA_SOURCE", () => {
    it('defaults to "real" with console.warn', () => {
      vi.stubEnv("VITE_DATA_SOURCE", "");
      vi.stubEnv("PROD", false);
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
      const client = createApiClient();
      expect(client.mode).toBe("real");
      expect(warnSpy).toHaveBeenCalled();
    });
  });

  describe("production mode (PROD=true) · unset VITE_DATA_SOURCE", () => {
    it("throws Error when VITE_DATA_SOURCE is empty string", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "");
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).toThrow(/VITE_DATA_SOURCE/);
    });

    it("throws Error when VITE_DATA_SOURCE is unset", () => {
      vi.stubEnv("VITE_DATA_SOURCE", undefined);
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).toThrow(/VITE_DATA_SOURCE/);
    });

    it("throws Error when VITE_DATA_SOURCE is a bogus value", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "bogus");
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).toThrow(/VITE_DATA_SOURCE/);
    });

    it("does NOT throw when explicitly set to real", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "real");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).not.toThrow();
    });

    it("throws when explicitly set to mock", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "mock");
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).toThrow(/mock/i);
    });
  });

  describe("mode override via options", () => {
    it.each([
      ["eager", createApiClient],
      ["deferred", createDeferredApiClient],
    ])("rejects an explicit mock override in production (%s client)", (_name, createClient) => {
      vi.stubEnv("VITE_DATA_SOURCE", "real");
      vi.stubEnv("PROD", true);
      expect(() => createClient({ mode: "mock" })).toThrow(/mock.*production/i);
    });

    it("options.mode overrides env parsing", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "real");
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      const client = createApiClient({ mode: "mock" });
      expect(client.mode).toBe("mock");
    });

    it("options.mode='real' does not trigger fail-fast even in PROD without env", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "");
      vi.stubEnv("PROD", true);
      vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8080");
      const client = createApiClient({ mode: "real" });
      expect(client.mode).toBe("real");
    });
  });
});

describe("deferred API client data-source boundary", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it.each(["", "bogus", "mock"])("rejects production environment mode %j", (mode) => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_DATA_SOURCE", mode);
    expect(() => createDeferredApiClient()).toThrow(/VITE_DATA_SOURCE/);
  });

  it("keeps explicit local demonstration mode available", () => {
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_DATA_SOURCE", "real");
    expect(createDeferredApiClient({ mode: "mock" }).mode).toBe("mock");
  });

  it("accepts explicit production real mode without an environment default", () => {
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_DATA_SOURCE", "");
    expect(createDeferredApiClient({ mode: "real" }).mode).toBe("real");
  });
});
