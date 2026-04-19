import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";

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
    it('defaults to "mock" with console.warn', () => {
      vi.stubEnv("VITE_DATA_SOURCE", "");
      vi.stubEnv("PROD", false);
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
      const client = createApiClient();
      expect(client.mode).toBe("mock");
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
      vi.stubEnv("PROD", true);
      // VITE_DATA_SOURCE undefined
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

    it("does NOT throw when explicitly set to mock", () => {
      vi.stubEnv("VITE_DATA_SOURCE", "mock");
      vi.stubEnv("PROD", true);
      expect(() => createApiClient()).not.toThrow();
    });
  });

  describe("mode override via options", () => {
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
