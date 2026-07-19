import type { ApiEnvelope } from "./contracts";
import {
  createRealBalanceAnalysisClient,
  type BalanceAnalysisClientMethods,
} from "./balanceAnalysisClient";
import {
  createRealBondAnalyticsClient,
  createRealBondDashboardClient,
  type BondAnalyticsClientMethods,
} from "./bondAnalyticsClient";
import {
  createRealCashflowClient,
  type CashflowClientMethods,
} from "./cashflowClient";
import {
  createRealExecutiveClient,
  type ExecutiveClientMethods,
} from "./executiveClient";
import {
  createRealHealthClient,
  type HealthClientMethods,
} from "./healthClient";
import {
  createRealLiabilityAdbClient,
  type LiabilityAdbClientMethods,
} from "./liabilityAdbClient";
import type { MarketDataClientMethods } from "./marketDataClient";
import type { MacroToolkitClientMethods } from "./macroToolkitClient";
import {
  createRealPnlBusinessClient,
  type PnlClientMethods,
} from "./pnlClient";
import {
  createRealPnlCoreClient,
  type PnlCoreClientMethods,
} from "./pnlCoreClient";
import {
  createRealPnlAttributionClient,
  type PnlAttributionClientMethods,
} from "./pnlAttributionClient";
import {
  createRealProductCategoryClient,
  type ProductCategoryClientMethods,
} from "./productCategoryClient";
import {
  createRealQdbGlMonthlyAnalysisClient,
  type QdbGlMonthlyAnalysisClientMethods,
} from "./qdbGlMonthlyAnalysisClient";
import {
  createRealPositionsClient,
  type PositionsClientMethods,
} from "./positionsClient";
import {
  createRealBalanceMovementClient,
  type BalanceMovementClientMethods,
} from "./balanceMovementClient";
import {
  createRealLedgerClient,
  type LedgerClientMethods,
} from "./ledgerClient";
import { createRealMarketDataClient } from "./marketDataClient";
import { createRealMacroToolkitClient } from "./macroToolkitClient";
import {
  createRealKpiClient,
  type KpiClientMethods,
} from "./kpiClient";
import {
  createRealCubeClient,
  type CubeClientMethods,
} from "./cubeClient";
import {
  createRealAgentClient,
  type AgentClientMethods,
} from "./agentClient";
import {
  dashboardWorkbenchLiveEndpoints,
  type DashboardClientMethods,
} from "./workbenchDashboardApi";
import { bondDashboardLiveEndpoints } from "./bondDashboardWorkbenchEndpoints";

export type DataSourceMode = "mock" | "real";
export { ApiClientProvider, useApiClient } from "./clientContext";
// Re-export domain method types for consumers who want fine-grained imports
export type { BalanceAnalysisClientMethods } from "./balanceAnalysisClient";
export type { BondAnalyticsClientMethods } from "./bondAnalyticsClient";
export type { CashflowClientMethods } from "./cashflowClient";
export type { DashboardClientMethods } from "./workbenchDashboardApi";
export type { ExecutiveClientMethods } from "./executiveClient";
export type { MarketDataClientMethods } from "./marketDataClient";
export type { MacroToolkitClientMethods } from "./macroToolkitClient";
export type { PnlClientMethods } from "./pnlClient";
export type { PnlCoreClientMethods } from "./pnlCoreClient";
export type { PnlAttributionClientMethods } from "./pnlAttributionClient";
export type { ProductCategoryClientMethods } from "./productCategoryClient";
export type { QdbGlMonthlyAnalysisClientMethods } from "./qdbGlMonthlyAnalysisClient";
export type { PositionsClientMethods } from "./positionsClient";
export type { LedgerClientMethods } from "./ledgerClient";
export type { KpiClientMethods } from "./kpiClient";
export type { CubeClientMethods } from "./cubeClient";
export type { AgentClientMethods } from "./agentClient";
export type { HealthClientMethods } from "./healthClient";
export type { LiabilityAdbClientMethods } from "./liabilityAdbClient";

export type ApiClient = {
  mode: DataSourceMode;
} & HealthClientMethods
  & ExecutiveClientMethods
  & DashboardClientMethods
  & PnlCoreClientMethods
  & PnlAttributionClientMethods
  & PnlClientMethods
  & ProductCategoryClientMethods
  & QdbGlMonthlyAnalysisClientMethods
  & BalanceMovementClientMethods
  & CashflowClientMethods
  & BondAnalyticsClientMethods
  & BalanceAnalysisClientMethods
  & PositionsClientMethods & LiabilityAdbClientMethods
  & MarketDataClientMethods
  & MacroToolkitClientMethods
  & LedgerClientMethods
  & KpiClientMethods
  & CubeClientMethods
  & AgentClientMethods;

export type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

type MockClientBundle = Pick<typeof import("../mocks/mockApiEnvelope"), "buildMockApiEnvelope"> & typeof import("../mocks/workbench");
let mockClientBundleCache: MockClientBundle | null = null;

async function loadMockClientBundle(): Promise<MockClientBundle> {
  const [apiEnvelopeModule, workbench] =
    await Promise.all([
      import("../mocks/mockApiEnvelope"),
      import("../mocks/workbench"),
    ]);
  return {
    buildMockApiEnvelope: apiEnvelopeModule.buildMockApiEnvelope,
    ...workbench,
  };
}

async function ensureMockClientBundle(): Promise<MockClientBundle> {
  mockClientBundleCache ??= await loadMockClientBundle();
  return mockClientBundleCache;
}

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  const isProd = import.meta.env.PROD === true;

  if (envValue === "real") return "real";
  if (envValue === "mock") {
    if (isProd) throw new Error("VITE_DATA_SOURCE='mock' is not allowed in production.");
    return "mock";
  }

  // Not explicitly set (or invalid value)
  if (isProd) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' or 'mock' in production build. " +
        "Refusing to silently fall back to mock. " +
        "See docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md § 9.1.",
    );
  }

  // dev / test: default to real; mock requires an explicit local switch.
  console.warn("[client] VITE_DATA_SOURCE not set or invalid (raw=%o). Defaulting to real.", raw);
  return "real";
};

const parseBaseUrl = () => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  return normalizeBaseUrl(typeof raw === "string" ? raw.trim() : undefined);
};


export class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  /** Top-level `error_message` from the JSON body when present. */
  readonly errorMessage?: string;
  /** Raw `detail` field from the JSON body (string, object, or array). */
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    const nestedMsg = d.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = d.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((p) => p.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
}

const DEFAULT_REQUEST_JSON_TIMEOUT_MS = 60_000;

const requestJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  timeoutMs: number = DEFAULT_REQUEST_JSON_TIMEOUT_MS,
): Promise<ApiEnvelope<T>> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, {
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });
  } catch (error) {
    const errorName =
      typeof error === "object" && error !== null && "name" in error
        ? (error as { name?: unknown }).name
        : undefined;
    if (errorName === "AbortError") {
      throw new Error(`Request timed out: ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as ApiEnvelope<T>;
};

const requestActionJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessageField =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage: errorMessageField,
      detail: rawDetail,
    });
  }

  return (await response.json()) as T;
};

const requestText = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.csv",
): Promise<{ content: string; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.text(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

function parseDownloadFilename(contentDisposition: string, fallbackFilename: string) {
  const utf8Match = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return filenameMatch?.[1] ?? fallbackFilename;
}

const requestBlob = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.bin",
): Promise<{ content: Blob; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.blob(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

const requestActionWithBody = async <TResponse, TBody>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as TResponse;
};

// Cache only the mockApiClient *module* import so real-mode bundles stay free
// of mock payloads. Each createApiClient({ mode: "mock" }) call still builds a
// fresh composition so mutable mock state does not leak across callers/tests.
let mockApiClientModulePromise: Promise<typeof import("./mockApiClient")> | null = null;
let cachedApiClientMethodNames: string[] | null = null;
let mockSurfaceAsserted = false;

function loadMockApiClientModule(): Promise<typeof import("./mockApiClient")> {
  mockApiClientModulePromise ??= import("./mockApiClient");
  return mockApiClientModulePromise;
}

function getApiClientMethodNames(): string[] {
  // Discover the public surface from a throwaway real client once. Mock calls
  // must not rebuild the full real composition on every createApiClient().
  cachedApiClientMethodNames ??= Object.keys(
    createApiClient({ mode: "real", baseUrl: "", fetchImpl: defaultFetch }),
  );
  return cachedApiClientMethodNames;
}

function assertMockClientSurface(methodNames: string[], mockClient: ApiClient): void {
  if (mockSurfaceAsserted) {
    return;
  }
  if (!(import.meta.env.DEV || import.meta.env.MODE === "test")) {
    return;
  }
  mockSurfaceAsserted = true;
  const mockKeys = new Set(Object.keys(mockClient));
  const missing = methodNames.filter((name) => name !== "mode" && !mockKeys.has(name));
  if (missing.length > 0) {
    throw new Error(
      `Mock ApiClient is missing methods expected by the real surface: ${missing.join(", ")}`,
    );
  }
}

function createLazyMockClient(methodNames: string[]): ApiClient {
  // Per-instance composition (not a module singleton).
  const mockClientPromise = loadMockApiClientModule().then(({ createMockApiClient }) => {
    const mockClient = createMockApiClient(delay, ensureMockClientBundle);
    assertMockClientSurface(methodNames, mockClient);
    return mockClient;
  });

  // A plain object (not a Proxy) so object spread, Object.keys, and test spies
  // behave exactly like the eager mock client did. Method names come from the
  // real composition, which implements the same ApiClient surface.
  const client = { mode: "mock" } as unknown as Record<string, unknown>;
  for (const name of methodNames) {
    if (name === "mode") {
      continue;
    }
    // Classic function preserves call-site `this` so fetchBondDashboardBundle
    // can resolve sibling methods on the composed client (and test overrides).
    client[name] = async function (this: unknown, ...args: unknown[]) {
      const mockClient = await mockClientPromise;
      const value = mockClient[name as keyof ApiClient];
      if (typeof value !== "function") {
        return value;
      }
      return (value as (this: unknown, ...methodArgs: unknown[]) => unknown).call(
        this ?? client,
        ...args,
      );
    };
  }
  return client as unknown as ApiClient;
}

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;

  if (mode === "mock") {
    void ensureMockClientBundle();
    void loadMockApiClientModule();
    return createLazyMockClient(getApiClientMethodNames());
  }

  return {
    mode,
    ...createRealHealthClient({ fetchImpl, baseUrl }),
    ...createRealBalanceMovementClient({ fetchImpl, baseUrl }),
    ...createRealLedgerClient({ fetchImpl, baseUrl }),
    ...createRealMarketDataClient({ fetchImpl, baseUrl }),
    ...createRealMacroToolkitClient({ fetchImpl, baseUrl }),
    ...createRealKpiClient({ fetchImpl, baseUrl }),
    ...createRealCubeClient({ fetchImpl, baseUrl }),
    ...createRealPnlBusinessClient({ fetchImpl, baseUrl }),
    ...createRealAgentClient({ fetchImpl, baseUrl }),
    ...createRealExecutiveClient({
      fetchImpl,
      baseUrl,
      requestJson,
    }),
    ...dashboardWorkbenchLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ...bondDashboardLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ...createRealBondAnalyticsClient({ fetchImpl, baseUrl, requestJson, requestActionJson }),
    ...createRealBondDashboardClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealPnlCoreClient({ fetchImpl, baseUrl, requestJson, requestActionJson }),
    ...createRealPnlAttributionClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealPositionsClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealCashflowClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealLiabilityAdbClient({ fetchImpl, baseUrl, requestJson }),
    ...createRealProductCategoryClient({
      fetchImpl,
      baseUrl,
      requestJson,
      requestActionJson,
      requestText,
      requestActionWithBody,
    }),
    ...createRealQdbGlMonthlyAnalysisClient({
      fetchImpl,
      baseUrl,
      requestJson,
      requestActionJson,
      requestText,
      requestBlob,
      requestActionWithBody,
    }),
    ...createRealBalanceAnalysisClient({
      fetchImpl,
      baseUrl,
      requestJson,
      requestActionJson,
      requestText,
      requestBlob,
    }),
  };
}
