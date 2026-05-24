import type { HealthResponse, HealthStatusResponse } from "./contracts";

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

async function requestHealthJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<T> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as T;
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
