/**
 * Mock/demo ApiClient composition.
 *
 * This module is loaded lazily by client.ts only when mock mode is active, so
 * demo factories and their mock payloads stay out of the real-mode bundle.
 */
import type { ApiClient } from "./client";
import { createDemoBalanceAnalysisClient } from "./balanceAnalysisClient";
import {
  createDemoBondAnalyticsClient,
  createDemoBondDashboardClient,
} from "./bondAnalyticsMockClient";
import { createDemoCashflowClient } from "./cashflowMockClient";
import { createDemoExecutiveClient } from "./executiveClient";
import { createDemoHealthClient } from "./healthClient";
import { createDemoLiabilityAdbClient } from "./liabilityAdbClient";
import { createMockPnlBusinessClient } from "./pnlMockClient";
import { createDemoPnlCoreClient } from "./pnlCoreMockClient";
import { createDemoPnlAttributionClient } from "./pnlAttributionMockClient";
import { createDemoProductCategoryClient } from "./productCategoryClient";
import { createDemoQdbGlMonthlyAnalysisClient } from "./qdbGlMonthlyAnalysisClient";
import { createDemoPositionsClient } from "./positionsMockClient";
import { createMockBalanceMovementClient } from "./balanceMovementMockClient";
import { createMockLedgerClient } from "./ledgerClient";
import { createMockMarketDataClient } from "./marketDataMockClient";
import { createMockMacroToolkitClient } from "./macroToolkitMockClient";
import { createMockKpiClient } from "./kpiClient";
import { createMockCubeClient } from "./cubeMockClient";
import { createDemoAgentClient } from "./agentClient";
import { dashboardWorkbenchDemoEndpoints } from "./workbenchDashboardApi";
import { bondDashboardDemoEndpoints } from "./bondDashboardWorkbenchEndpoints";

type Delay = () => Promise<void>;

type MockClientBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  typeof import("../mocks/workbench");

type EnsureMockClientBundle = () => Promise<MockClientBundle>;

export function createMockApiClient(
  delay: Delay,
  ensureMockClientBundle: EnsureMockClientBundle,
): ApiClient {
  return {
    mode: "mock",
    ...createDemoHealthClient(delay),
    ...createMockBalanceMovementClient(),
    ...createMockLedgerClient(),
    ...createMockMarketDataClient(),
    ...createMockMacroToolkitClient(),
    ...createMockKpiClient(),
    ...createMockCubeClient(),
    ...createMockPnlBusinessClient(),
    ...createDemoAgentClient(delay),
    ...createDemoExecutiveClient(delay, ensureMockClientBundle),
    ...dashboardWorkbenchDemoEndpoints(delay, ensureMockClientBundle),
    ...bondDashboardDemoEndpoints(delay, ensureMockClientBundle),
    ...createDemoBondAnalyticsClient(delay, ensureMockClientBundle),
    ...createDemoBondDashboardClient(delay, ensureMockClientBundle),
    ...createDemoPnlCoreClient(delay),
    ...createDemoPnlAttributionClient(delay),
    ...createDemoProductCategoryClient(delay),
    ...createDemoQdbGlMonthlyAnalysisClient(delay, ensureMockClientBundle),
    ...createDemoBalanceAnalysisClient(delay, ensureMockClientBundle),
    ...createDemoPositionsClient(delay, ensureMockClientBundle),
    ...createDemoLiabilityAdbClient(delay, ensureMockClientBundle),
    ...createDemoCashflowClient(delay),
  };
}
