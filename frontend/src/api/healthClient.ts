import type { HealthResponse, HealthStatusResponse } from "./contracts";
import { requestPlainJson } from "./transport";

type FetchLike = typeof fetch;

export type HealthClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

export type HealthClientMethods = {
  getHealth: () => Promise<HealthResponse>;
  getHealthLive: () => Promise<HealthStatusResponse>;
  getHealthSummary: () => Promise<HealthStatusResponse>;
};

type Delay = () => Promise<void>;

export function createDemoHealthClient(delay: Delay): HealthClientMethods {
  return {
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getHealthLive() {
      await delay();
      return { status: "ok" };
    },
    async getHealthSummary() {
      await delay();
      return { status: "ok" };
    },
  };
}

export const createMockHealthClient = createDemoHealthClient;

/**
 * Health payloads are plain `{ status }` JSON (no ApiEnvelope), served via the
 * shared transport: status-only error messages plus the default 60s timeout
 * (previously a bare fetch that could hang forever).
 */
function requestHealthJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<T> {
  return requestPlainJson<T>(fetchImpl, baseUrl, path);
}

export function createRealHealthClient(
  options: HealthClientFactoryOptions,
): HealthClientMethods {
  const { fetchImpl, baseUrl } = options;

  return {
    getHealth: () =>
      requestHealthJson<HealthResponse>(fetchImpl, baseUrl, "/health/ready"),
    getHealthLive: () =>
      requestHealthJson<HealthStatusResponse>(
        fetchImpl,
        baseUrl,
        "/health/live",
      ),
    getHealthSummary: () =>
      requestHealthJson<HealthStatusResponse>(fetchImpl, baseUrl, "/health"),
  };
}
