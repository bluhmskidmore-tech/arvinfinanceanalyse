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

// Lazy-load demo composition; cache module import only (not instances).
let demoClientModulePromise: Promise<typeof import("./mockApiClient")> | null = null;
let cachedApiClientMethodNames: string[] | null = null;
let demoSurfaceAsserted = false;

/** Public method names from a throwaway real client (built once). */
function getApiClientMethodNames(): string[] {
  cachedApiClientMethodNames ??= Object.keys(
    createApiClient({ mode: "real", baseUrl: "", fetchImpl: defaultFetch }),
  );
  return cachedApiClientMethodNames;
}

function createLazyDemoClient(methodNames: string[]): ApiClient {
  // Fresh composition per call so mutable demo state does not leak.
  demoClientModulePromise ??= import("./mockApiClient");
  const demoPromise = demoClientModulePromise.then(({ createMockApiClient }) => {
    const composed = createMockApiClient(delay, ensureMockClientBundle);
    if (!demoSurfaceAsserted && (import.meta.env.DEV || import.meta.env.MODE === "test")) {
      demoSurfaceAsserted = true;
      const keys = new Set(Object.keys(composed));
      const missing = methodNames.filter((n) => n !== "mode" && !keys.has(n));
      if (missing.length) throw new Error(`Demo ApiClient missing methods: ${missing.join(", ")}`);
    }
    return composed;
  });
  // Plain object (not Proxy): spread / Object.keys / spies match eager client.
  const client = { mode: "mock" } as unknown as Record<string, unknown>;
  for (const name of methodNames) {
    if (name === "mode") continue;
    // Classic function keeps call-site `this` for bundle assembly + overrides.
    client[name] = async function (this: unknown, ...args: unknown[]) {
      const composed = await demoPromise;
      const value = composed[name as keyof ApiClient];
      if (typeof value !== "function") return value;
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
    demoClientModulePromise ??= import("./mockApiClient");
    return createLazyDemoClient(getApiClientMethodNames());
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
    ...createRealExecutiveClient({ fetchImpl, baseUrl, requestJson }),
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
      fetchImpl, baseUrl, requestJson, requestActionJson, requestText, requestActionWithBody,
    }),
    ...createRealQdbGlMonthlyAnalysisClient({
      fetchImpl, baseUrl, requestJson, requestActionJson, requestText, requestBlob, requestActionWithBody,
    }),
    ...createRealBalanceAnalysisClient({
      fetchImpl, baseUrl, requestJson, requestActionJson, requestText, requestBlob,
    }),
  };
}
