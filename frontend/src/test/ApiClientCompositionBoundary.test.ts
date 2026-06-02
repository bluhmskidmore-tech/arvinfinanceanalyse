import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";

const clientSource = readFileSync(resolve(process.cwd(), "src/api/client.ts"), "utf8");
const clientContextSource = readFileSync(resolve(process.cwd(), "src/api/clientContext.ts"), "utf8");
const providersSource = readFileSync(resolve(process.cwd(), "src/app/providers.tsx"), "utf8");
const shellSource = readFileSync(resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"), "utf8");
const dataModeRibbonSource = readFileSync(resolve(process.cwd(), "src/components/DataModeRibbon.tsx"), "utf8");
const marketDataSource = readFileSync(resolve(process.cwd(), "src/api/marketDataClient.ts"), "utf8");
const kpiSource = readFileSync(resolve(process.cwd(), "src/api/kpiClient.ts"), "utf8");
const cubeSource = readFileSync(resolve(process.cwd(), "src/api/cubeClient.ts"), "utf8");

describe("ApiClient composition boundary", () => {
  it("keeps the public market-data source preview surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getSourceFoundation).toBe("function");
    expect(typeof client.refreshSourcePreview).toBe("function");
    expect(typeof client.getSourcePreviewRefreshStatus).toBe("function");
    expect(typeof client.getSourceFoundationHistory).toBe("function");
    expect(typeof client.getSourceFoundationRows).toBe("function");
    expect(typeof client.getSourceFoundationTraces).toBe("function");
    expect(typeof client.getChoiceNewsEvents).toBe("function");
    expect(typeof client.ingestTushareNprNews).toBe("function");
    expect(typeof client.getResearchCalendarEvents).toBe("function");
    expect(typeof client.getKpiOwners).toBe("function");
    expect(typeof client.fetchAndRecalcKpi).toBe("function");
    expect(typeof client.getCubeDimensions).toBe("function");
    expect(typeof client.executeCubeQuery).toBe("function");
  });

  it("keeps extracted domain implementation out of client.ts", () => {
    expect(clientSource).not.toContain("MOCK_SOURCE_FOUNDATION_SUMMARIES");
    expect(clientSource).not.toContain("MOCK_CHOICE_NEWS_EVENTS");
    expect(clientSource).not.toContain("buildMockResearchCalendarEvents");
    expect(clientSource).not.toContain("buildMockChoiceNewsEnvelope");
    expect(clientSource).not.toContain("requestKpiJson");
    expect(clientSource).not.toContain("kpiQueryString");
    expect(clientSource).not.toContain("dimensionMap");
    expect(clientSource).not.toMatch(/async getSourceFoundation\(/);
    expect(clientSource).not.toMatch(/async refreshSourcePreview\(/);
    expect(clientSource).not.toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationHistory\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationRows\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationTraces\(/);
    expect(clientSource).not.toMatch(/async getChoiceNewsEvents\(/);
    expect(clientSource).not.toMatch(/async getResearchCalendarEvents\(/);
    expect(clientSource).not.toMatch(/async ingestTushareNprNews\(/);
    expect(clientSource).not.toMatch(/async getKpiOwners\(/);
    expect(clientSource).not.toMatch(/async fetchAndRecalcKpi\(/);
    expect(clientSource).not.toMatch(/async getCubeDimensions\(/);
    expect(clientSource).not.toMatch(/async executeCubeQuery\(/);
  });

  it("requires marketDataClient.ts to own the extracted market-data composition slice", () => {
    expect(marketDataSource).toMatch(/async getSourceFoundation\(/);
    expect(marketDataSource).toMatch(/async refreshSourcePreview\(/);
    expect(marketDataSource).toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationHistory\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationRows\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationTraces\(/);
    expect(marketDataSource).toMatch(/async getChoiceNewsEvents\(/);
    expect(marketDataSource).toMatch(/async getResearchCalendarEvents\(/);
    expect(marketDataSource).toMatch(/async ingestTushareNprNews\(/);
  });

  it("requires KPI and cube clients to own their extracted composition slices", () => {
    expect(kpiSource).toContain("requestKpiJson");
    expect(kpiSource).toMatch(/async getKpiOwners\(/);
    expect(kpiSource).toMatch(/async fetchAndRecalcKpi\(/);
    expect(cubeSource).toMatch(/async getCubeDimensions\(/);
    expect(cubeSource).toMatch(/async executeCubeQuery\(/);
  });

  it("keeps first-screen providers and shell on the lightweight API context boundary", () => {
    expect(providersSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(providersSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(shellSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(shellSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(dataModeRibbonSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(dataModeRibbonSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(clientContextSource).toContain("createDeferredApiClient");
    expect(clientContextSource).not.toMatch(/import\s+\{[^}]*createApiClient/);
    expect(clientSource).toContain("from \"./clientContext\"");
  });
});
