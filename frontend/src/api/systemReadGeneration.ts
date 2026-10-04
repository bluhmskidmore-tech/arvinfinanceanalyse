import type { ApiClient } from "./client";
import { getApiClientFactoryRecord } from "./clientFactoryOptions";
import { fetchWithOptionalTimeout } from "./transport";

export const SYSTEM_READ_GENERATION_HEADER = "X-MOSS-Read-Generation";
export const SYSTEM_READ_PUBLICATION_PATH = "/api/system-read-publication";

export type SystemReadPublication = {
  enabled: boolean;
  generation: string | null;
  coverage_dates: Record<string, string[]>;
};

export class SystemReadGenerationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SystemReadGenerationError";
  }
}

function describeGeneration(value: string | null): string {
  return value === null ? "missing" : JSON.stringify(value);
}

function assertCoverageDates(value: unknown): asserts value is Record<string, string[]> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new SystemReadGenerationError(
      "Invalid system read publication: `coverage_dates` must be an object.",
    );
  }
  for (const [domain, dates] of Object.entries(value)) {
    if (!domain || !Array.isArray(dates) || dates.some((date) => typeof date !== "string")) {
      throw new SystemReadGenerationError(
        "Invalid system read publication: `coverage_dates` contains an invalid entry.",
      );
    }
  }
}

function parsePublication(payload: unknown, responseGeneration: string | null): SystemReadPublication {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new SystemReadGenerationError("Invalid system read publication response.");
  }

  const record = payload as Record<string, unknown>;
  if (typeof record.enabled !== "boolean") {
    throw new SystemReadGenerationError(
      "Invalid system read publication: `enabled` must be boolean.",
    );
  }
  assertCoverageDates(record.coverage_dates);

  if (!record.enabled) {
    if (record.generation !== null) {
      throw new SystemReadGenerationError(
        "Invalid system read publication: disabled mode must not select a generation.",
      );
    }
    return {
      enabled: false,
      generation: null,
      coverage_dates: record.coverage_dates,
    };
  }

  const generation = typeof record.generation === "string" ? record.generation.trim() : "";
  if (!generation) {
    throw new SystemReadGenerationError(
      "Invalid system read publication: enabled mode requires a generation.",
    );
  }
  if (responseGeneration !== generation) {
    throw new SystemReadGenerationError(
      `System read generation mismatch: expected ${JSON.stringify(generation)}, received ${describeGeneration(responseGeneration)}.`,
    );
  }

  return {
    enabled: true,
    generation,
    coverage_dates: record.coverage_dates,
  };
}

export async function getSystemReadPublication(
  client: ApiClient,
  signal?: AbortSignal,
): Promise<SystemReadPublication> {
  if (client.mode === "mock") {
    return { enabled: false, generation: null, coverage_dates: {} };
  }

  const factory = getApiClientFactoryRecord(client);
  if (!factory) {
    throw new SystemReadGenerationError(
      "Cannot open a fixed system read interaction because this API client has no factory options.",
    );
  }

  return fetchWithOptionalTimeout(
    factory.options.fetchImpl,
    `${factory.options.baseUrl}${SYSTEM_READ_PUBLICATION_PATH}`,
    { headers: { Accept: "application/json" }, signal },
    15_000,
    SYSTEM_READ_PUBLICATION_PATH,
    async (response) => {
      if (!response.ok) {
        throw new SystemReadGenerationError(
          `System read publication handshake failed (${response.status}).`,
        );
      }
      return parsePublication(
        await response.json(),
        response.headers.get(SYSTEM_READ_GENERATION_HEADER),
      );
    },
  );
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  if (typeof Request !== "undefined" && input instanceof Request) {
    return input.method.toUpperCase();
  }
  return "GET";
}

function requestPath(input: RequestInfo | URL, baseUrl: string): string {
  const rawUrl =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
  const path = new URL(rawUrl, "http://moss.local").pathname;
  const basePath = new URL(baseUrl || "/", "http://moss.local").pathname.replace(/\/$/, "");
  return basePath && path.startsWith(`${basePath}/`) ? path.slice(basePath.length) : path;
}

const LIVE_GET_PATHS = new Set([
  "/health",
  "/health/live",
  "/api/bond-analytics/refresh-status",
  "/ui/balance-analysis/current-user",
  "/ui/balance-analysis/refresh-status",
]);

function isGenerationScopedGet(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  baseUrl: string,
): boolean {
  return requestMethod(input, init) === "GET" && !LIVE_GET_PATHS.has(requestPath(input, baseUrl));
}

function mergeRequestHeaders(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  generation: string,
): Headers {
  const headers = new Headers(
    typeof Request !== "undefined" && input instanceof Request ? input.headers : undefined,
  );
  new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
  headers.set(SYSTEM_READ_GENERATION_HEADER, generation);
  return headers;
}

export function createGenerationScopedApiClient(
  client: ApiClient,
  generation: string,
): ApiClient {
  const factory = getApiClientFactoryRecord(client);
  if (!factory) {
    throw new SystemReadGenerationError(
      "Cannot clone a fixed system read interaction because this API client has no factory options.",
    );
  }

  const scopedFetch: typeof fetch = async (input, init) => {
    const isCubeRead = requestMethod(input, init) === "POST"
      && requestPath(input, factory.options.baseUrl) === "/api/cube/query";
    if (!isGenerationScopedGet(input, init, factory.options.baseUrl) && !isCubeRead) {
      return factory.options.fetchImpl(input, init);
    }

    const response = await factory.options.fetchImpl(input, {
      ...init,
      headers: mergeRequestHeaders(input, init, generation),
    });
    const responseGeneration = response.headers.get(SYSTEM_READ_GENERATION_HEADER);
    if (responseGeneration !== generation) {
      throw new SystemReadGenerationError(
        `System read generation mismatch: expected ${JSON.stringify(generation)}, received ${describeGeneration(responseGeneration)}.`,
      );
    }
    return response;
  };

  return factory.create({ ...factory.options, fetchImpl: scopedFetch });
}
