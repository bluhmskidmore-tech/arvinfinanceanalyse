import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type { ApiClient, ApiClientOptions, DataSourceMode } from "./client";

export type { ApiClient, DataSourceMode } from "./client";

export type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const parseDeferredEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  const isProd = import.meta.env.PROD === true;

  if (envValue === "real") return "real";
  if (envValue === "mock") {
    if (isProd) throw new Error("VITE_DATA_SOURCE='mock' is not allowed in production.");
    return "mock";
  }

  if (isProd) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' or 'mock' in production build. " +
        "Refusing to silently fall back to mock. " +
        "See docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md section 9.1.",
    );
  }

  console.warn("[client] VITE_DATA_SOURCE not set or invalid (raw=%o). Defaulting to real.", raw);
  return "real";
};

export function createDeferredApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseDeferredEnvMode();
  let clientPromise: Promise<ApiClient> | null = null;

  const loadClient = () => {
    if (!clientPromise) {
      clientPromise = import("./client").then(({ createApiClient }) =>
        createApiClient({ ...options, mode }),
      );
    }
    return clientPromise;
  };

  return new Proxy(
    { mode } as ApiClient,
    {
      get(target, property, receiver) {
        if (property === "mode") {
          return mode;
        }
        if (property === "then") {
          return undefined;
        }
        if (typeof property === "symbol") {
          return Reflect.get(target, property, receiver);
        }

        return async (...args: unknown[]) => {
          const client = await loadClient();
          const value = client[property as keyof ApiClient];
          if (typeof value !== "function") {
            return value;
          }
          const method = value as (...methodArgs: unknown[]) => unknown;
          return method(...args);
        };
      },
    },
  );
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createDeferredApiClient(),
    [client],
  );

  return createElement(
    ApiClientContext.Provider,
    { value: resolvedClient },
    children,
  );
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error("ApiClientProvider is missing");
  }

  return client;
}
