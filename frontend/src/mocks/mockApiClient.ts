/**
 * Mock/demo ApiClient composition.
 *
 * This module is loaded lazily by client.ts only when mock mode is active, so
 * demo factories and their mock payloads stay out of the real-mode bundle.
 */
import type { ApiClient } from "../api/client";
import { createDemoBalanceAnalysisClient } from "./balanceAnalysisMockClient";
import {
  createDemoBondAnalyticsClient,
  createDemoBondDashboardClient,
} from "./bondAnalyticsMockClient";
import { createDemoCashflowClient } from "./cashflowMockClient";
import { createDemoExecutiveClient } from "./executiveMockClient";
import { createDemoHealthClient } from "./healthMockClient";
import { createDemoLiabilityAdbClient } from "./liabilityAdbMockClient";
import { createMockPnlBusinessClient } from "./pnlMockClient";
import { createDemoPnlCoreClient } from "./pnlCoreMockClient";
import { createDemoPnlAttributionClient } from "./pnlAttributionMockClient";
import { createDemoProductCategoryClient } from "./productCategoryMockClient";
import { createDemoQdbGlMonthlyAnalysisClient } from "./qdbGlMonthlyAnalysisMockClient";
import { createDemoPositionsClient } from "./positionsMockClient";
import { createMockBalanceMovementClient } from "./balanceMovementMockClient";
import { createMockLedgerClient } from "./ledgerMockClient";
import { createMockMarketDataClient } from "./marketDataMockClient";
import { createMockMacroToolkitClient } from "./macroToolkitMockClient";
import { createMockKpiClient } from "./kpiMockClient";
import { createMockTeamPerformanceClient } from "./teamPerformanceMockClient";
import { createMockCubeClient } from "./cubeMockClient";
import { createDemoAgentClient } from "./agentMockClient";
import { dashboardWorkbenchDemoEndpoints } from "./workbenchDashboardMockApi";
import { bondDashboardDemoEndpoints } from "./bondDashboardWorkbenchMockEndpoints";

type Delay = () => Promise<void>;

type MockClientBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
> &
  typeof import("./workbench");

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
    ...createMockTeamPerformanceClient(),
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
