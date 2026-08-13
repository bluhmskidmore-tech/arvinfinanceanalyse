import {
  requestActionJson,
  requestActionWithBody,
  requestBlob,
  requestJson,
  requestText,
} from "./transport";
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
// Shared HTTP transport now lives in ./transport; ActionRequestError is
// re-exported so existing `import { ActionRequestError } from "./client"`
// call sites keep working.
export { ActionRequestError } from "./transport";
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
  const client: Record<string, unknown> = { mode: "mock" };
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
  // 动态拼装面收窄为单跳；dev/test 启动断言（上方 missing 检查）保证方法面完整。
  return client as ApiClient;
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
